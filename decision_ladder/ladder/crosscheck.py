"""Cross-checks: independently built engines must agree before a number is trusted.

The author built several of these calculators separately, in different languages, at different times:
MortgageLoanOps and Renewal Radar (Python), the Canadian Mortgage Suite, Cash to Close, Renewal Check,
the Pre-Underwriting Check and Mortgage Decision Lab (JavaScript). Where two or more of them compute the same
quantity for the same inputs, the OS runs all of them and reports agreement. A disagreement is never hidden:
it is shown with each engine's value and, where the cause is known, why they differ.

This is N-version checking applied to mortgage math. During integration it caught a real issue: the
Python stress test (MortgageLoanOps) left the CMHC premium out of the qualifying loan, while the Suite
added it. The OS engine now includes the premium; the Pre-Underwriting Check still qualifies on the base
loan, and that known difference is labelled instead of being reported as an error.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from ..engines import insurance, ird, payments, qualify

JS = None


class _CachedJS:
    """Memoises identical bridge calls within one run (the same app is often asked the same question twice)."""

    def __init__(self, mod):
        self.mod, self.cache = mod, {}

    def call(self, module: str, fn: str, args: dict):
        import json as _json
        k = (module, fn, _json.dumps(args, sort_keys=True, default=str))
        if k not in self.cache:
            self.cache[k] = self.mod.call(module, fn, args)
        return self.cache[k]


def _js() -> Any:
    from ..modules import jsapps
    return _CachedJS(jsapps)


def _num(x: Any) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _check(quantity: str, unit: str, tol: float, engines: list[tuple[str, Callable[[], Any]]],
           note: str = "", known: dict[str, str] | None = None) -> dict:
    vals = []
    for name, fn in engines:
        try:
            v = fn()
            if isinstance(v, dict) and "error" in v:
                vals.append({"engine": name, "value": None, "error": v["error"]})
            else:
                vals.append({"engine": name, "value": None if _num(v) is None else round(float(v), 2)})
        except Exception as e:  # noqa: BLE001 - an engine failure is a result, not a crash
            vals.append({"engine": name, "value": None, "error": f"{type(e).__name__}: {e}"})
    known = known or {}
    compared = [v for v in vals if v["value"] is not None and v["engine"] not in known]
    agree = None
    spread = None
    if len(compared) >= 2:
        xs = [v["value"] for v in compared]
        spread = round(max(xs) - min(xs), 2)
        agree = spread <= tol
    for v in vals:
        if v["engine"] in known:
            v["note"] = known[v["engine"]]
    return {"quantity": quantity, "unit": unit, "tolerance": tol, "engines": vals, "agree": agree,
            "spread": spread, "note": note}


def _months_left(f: dict) -> int:
    today = date.fromisoformat(f["as_of"]) if f.get("as_of") else date.today()
    mat = date.fromisoformat(f["maturity"])
    return max(0, (mat.year - today.year) * 12 + (mat.month - today.month) - (1 if mat.day < today.day else 0))


def purchase_checks(f: dict) -> list[dict]:
    J = _js()
    review = {}

    def puc() -> dict:
        if not review:
            review.update(J.call("pre-underwriting-copilot", "review", {"text": loan_file_text(f)}))
        return review
    price, down = float(f["price"]), float(f["down_payment"])
    am = int(f.get("amort_years", 25))
    prov = (f.get("province") or "ON").upper()
    ftb, nb = bool(f.get("first_time_buyer")), bool(f.get("new_build"))
    out = []
    loan = price - down
    if loan / price > 0.80 and price < insurance.insured.PRICE_CAP:
        out.append(_check("Mortgage default insurance premium", "$", 1.0, [
            ("Decision Ladder engine (Python)", lambda: insurance.premium(price=price, down_payment=down, amort_years=am,
                                                                         province=prov).premium),
            ("Canadian Mortgage Suite (JS)", lambda: J.call("canadian-mortgage-suite", "insurancePremium", {
                "price": price, "down": down, "amortization": am, "firstTime": ftb, "newBuild": nb, "province": prov}).get("premium")),
        ]))
    rate = float(f["contract_rate"])
    out.append(_check("B-20 qualifying rate", "%", 0.001, [
        ("MortgageLoanOps qualify (Python)", lambda: qualify.qualifying_rate(rate)),
        ("Canadian Mortgage Suite (JS)", lambda: J.call("canadian-mortgage-suite", "affordability", {
            "income": float(f["annual_income"]), "rate": rate, "down": down, "years": am}).get("qualifyingRate")),
        ("Pre-Underwriting Check (JS)", lambda: puc()["ratios"]["qr"]),
    ]))
    # Qualifying payment on the BASE loan (before any premium) is the like-for-like comparison across all three.
    out.append(_check("Qualifying payment on the base loan", "$/mo", 0.05, [
        ("MortgageLoanOps payments (Python)", lambda: payments.payment(loan, qualify.qualifying_rate(rate), am)),
        ("Pre-Underwriting Check (JS)", lambda: puc()["ratios"]["qualPmt"]),
    ], note="Before any insurance premium is added, so every engine computes the same loan."))
    if prov == "ON":
        out.append(_check("Ontario land transfer tax (before first-time refund)", "$", 0.5, [
            ("Cash to Close (JS)", lambda: J.call("cash-to-close", "plan", {"price": price, "savings": 0, "down": down,
                                                                           "first_time": ftb}).get("lttGross")),
            ("Canadian Mortgage Suite (JS)", lambda: J.call("canadian-mortgage-suite", "landTransferTax", {
                "price": price, "province": "ON", "firstTime": False}).get("provincial")),
        ]))
        if ftb:
            out.append(_check("Ontario first-time buyer LTT refund", "$", 0.5, [
                ("Cash to Close (JS)", lambda: J.call("cash-to-close", "plan", {"price": price, "savings": 0, "down": down,
                                                                               "first_time": True}).get("lttRefund")),
                ("Canadian Mortgage Suite (JS)", lambda: J.call("canadian-mortgage-suite", "landTransferTax", {
                    "price": price, "province": "ON", "firstTime": True}).get("rebate")),
            ]))
    return out


def renewal_checks(f: dict) -> list[dict]:
    J = _js()
    out = []
    bal, rem = float(f["balance"]), float(f.get("remaining_amort_years", 20))
    new_rate = float(f.get("renewal_rate") or f.get("new_rate") or f["contract_rate"])
    out.append(_check("Payment at the renewal rate", "$/mo", 0.05, [
        ("MortgageLoanOps payments (Python)", lambda: payments.payment(bal, new_rate, rem)),
        ("Renewal Check (JS)", lambda: J.call("renewal-check", "check", {"balance": bal, "years": rem,
                                                                         "currentRate": float(f["contract_rate"]),
                                                                         "offerRate": new_rate}).get("newPay")),
    ]))
    if f.get("original_posted_rate") and f.get("maturity") and f.get("term_start"):
        months = _months_left(f)
        if months > 0:
            from ..agent import tools as T
            book = T.run("penalty_by_lender", {"lender": f.get("lender", "generic"), "balance": bal,
                                               "contract_rate": f["contract_rate"], "term_start": f["term_start"],
                                               "maturity": f["maturity"], "payout_date": f.get("as_of"),
                                               "original_posted_rate": f["original_posted_rate"]})
            comp = (book.get("comparison") or {}).get("rate") if isinstance(book, dict) else None
            used_m = book.get("remaining_months", months) if isinstance(book, dict) else months
            if comp is not None:
                comp = float(comp)
                posted0, c = float(f["original_posted_rate"]), float(f["contract_rate"])
                engines = [
                    ("Renewal Radar penalty engine (Python, Decimal)", lambda: (book.get("estimate") or {}).get("interest_rate_differential")),
                    ("MortgageLoanOps IRD (Python)", lambda: ird.ird_posted(bal, c, posted0, comp, used_m)),
                    ("Renewal Check (JS)", lambda: J.call("renewal-check", "penalty", {
                        "balance": bal, "contractRate": c, "monthsLeft": used_m, "method": "discount",
                        "postedAtSigning": posted0, "postedNowForTerm": comp}).get("ird")),
                ]
                known = {}
                exact = T.run("rr_bank_penalty", {"lender": f.get("lender", "generic"), "balance": bal, "contract_rate": c,
                                                  "start": f["term_start"], "maturity": f["maturity"],
                                                  "payout": f.get("as_of"), "posted_at_origination": posted0})
                if isinstance(exact, dict) and exact.get("status") == "exact-method":
                    lbl = f"Renewal Radar {exact.get('lender')} exact method (day-exact)"
                    engines.append((lbl, lambda: exact.get("ird")))
                    known[lbl] = (f"Uses {exact.get('remaining_months')} months, day-exact, as the lender's own calculator does; "
                                  f"the three engines above round the time left up to {used_m} whole months.")
                out.append(_check("IRD penalty, posted-rate-minus-discount method", "$", 1.0, engines,
                                  note=f"Same inputs for the first three: {used_m} months left, comparison posted rate {comp}% "
                                       "from the lender's own rate table in the rate book.", known=known))
    return out


def run_checks(f: dict) -> list[dict]:
    purpose = (f.get("purpose") or "purchase").lower()
    if purpose == "purchase" and all(f.get(k) is not None for k in ("price", "down_payment", "contract_rate", "annual_income")):
        return purchase_checks(f)
    if purpose in ("renewal", "refinance") and all(f.get(k) is not None for k in ("balance", "contract_rate")):
        return renewal_checks(f)
    return []


DOC_TYPE_TO_PUC = {"pay_stub": "Pay stub", "employment_letter": "Employment letter", "noa": "NOA", "t4": "T4",
                   "id": "ID", "bank_statement": "Down payment statement", "purchase_agreement": "Purchase agreement"}


def loan_file_text(f: dict) -> str:
    """The structured file in the Pre-Underwriting Check's plain-text format ('Field: value' + 'Documents:')."""
    as_of = f.get("as_of") or date.today().isoformat()
    name = f.get("borrower_name") or "Borrower"
    lines = [("# [EXAMPLE] " if f.get("example") else "# ") + "loan file generated by Decision Ladder Mortgage OS",
             f"Borrower: {name}", f"Province: {f.get('province', 'ON')}", f"Application date: {as_of}",
             f"Employment: {f.get('employment', 'Salaried')}", f"Annual income: {f.get('annual_income', '')}",
             f"Credit score: {f.get('credit_score', '')}", f"Purchase price: {f.get('price', '')}",
             f"Down payment: {f.get('down_payment', '')}", f"Gift: {'Yes' if f.get('gift') else 'No'}",
             f"Contract rate: {f.get('contract_rate', '')}", f"Amortization: {f.get('amort_years', 25)}",
             f"Property tax: {f.get('property_tax_annual', 0)}",
             f"Heating: {round(float(f.get('heat_annual', 1800)) / 12, 2)}",
             f"Condo fees: {f.get('condo_fees_monthly', 0)}", f"Monthly debts: {f.get('other_debt_monthly', 0)}",
             "Documents:"]
    for d in f.get("documents") or []:
        t = DOC_TYPE_TO_PUC.get(d.get("type") or "", None)
        if t:
            lines.append(f"- {t} | {d.get('date') or as_of} | {d.get('name') or name}")
    for d in f.get("documents_on_file") or []:   # e.g. ["ID", "Purchase agreement"]
        lines.append(f"- {d} | {as_of} | {name}")
    return "\n".join(lines) + "\n"
