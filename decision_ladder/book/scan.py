"""Renewal book scan: a whole client book through the exit-cost and switch rungs, ranked for the broker.

Input is a CSV (one row per mortgage). For each row the scan computes the renewal payment shock, the
lender-method penalty if the client broke today, a stress-test switch check when income is known, and a
priority score. The ranked queue is what a broker works from on Monday morning. Nemotron (optional)
drafts one guardrailed outreach message per top-priority client.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from ..agent import tools as T
from ..engines import renewal
from ..llm.client import LLMError, NemotronClient

REQUIRED = ("borrower", "lender", "balance", "contract_rate", "maturity")


def _f(row: dict, k: str, default=None):
    v = row.get(k)
    if v in (None, ""):
        return default
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("%", ""))
    except ValueError:
        return default


def _months(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def parse_book(text: str) -> tuple[list[dict], list[str]]:
    rdr = csv.DictReader(io.StringIO(text.strip()))
    if not rdr.fieldnames:
        return [], ["empty file"]
    cols = {c.strip().lower(): c for c in rdr.fieldnames}
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        return [], [f"missing column(s): {', '.join(missing)}"]
    rows, errors = [], []
    for i, raw in enumerate(rdr, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        try:
            date.fromisoformat(row["maturity"])
        except ValueError:
            errors.append(f"line {i}: maturity must be YYYY-MM-DD")
            continue
        if _f(row, "balance") is None or _f(row, "contract_rate") is None:
            errors.append(f"line {i}: balance and contract_rate must be numbers")
            continue
        rows.append(row)
    return rows, errors


def scan_row(row: dict, as_of: date) -> dict:
    mat = date.fromisoformat(row["maturity"])
    months_left = _months(as_of, mat)
    bal, rate = _f(row, "balance"), _f(row, "contract_rate")
    renewal_rate = _f(row, "renewal_rate")
    out: dict = {"borrower": row["borrower"], "lender": row["lender"], "province": row.get("province") or "ON",
                 "balance": bal, "contract_rate": rate, "maturity": row["maturity"], "months_to_maturity": months_left,
                 "renewal_rate": renewal_rate}
    pct = 0.0
    if all(_f(row, k) for k in ("original_principal", "original_rate", "original_amort_years", "months_elapsed")) and renewal_rate:
        try:
            shock = renewal.renewal_shock(original_principal=_f(row, "original_principal"), original_rate=_f(row, "original_rate"),
                                          original_amort_years=_f(row, "original_amort_years"),
                                          months_elapsed=int(_f(row, "months_elapsed")), renewal_rate=renewal_rate)
            out["shock"] = shock
            pct = shock["pct_change"]
        except ValueError as e:
            out["shock_error"] = str(e)
    if months_left > 0:
        start = row.get("term_start")
        if not start:
            term_m = int(_f(row, "term_months", 60))
            y, m = divmod(mat.month - 1 - term_m, 12)
            start = date(mat.year + y, m + 1, min(mat.day, 28)).isoformat()
            out["term_start_assumed"] = True
        pen = T.run("penalty_by_lender", {"lender": row["lender"], "balance": bal, "contract_rate": rate,
                                          "term_start": start, "maturity": row["maturity"], "payout_date": as_of.isoformat(),
                                          "original_posted_rate": _f(row, "original_posted_rate")})
        est = (pen.get("estimate") or {}) if isinstance(pen, dict) else {}
        out["penalty_today"] = None if est.get("total_estimate") is None else float(est["total_estimate"])
        out["penalty_method"] = est.get("controlling_method")
        out["penalty_status"] = est.get("status") or pen.get("error")
        # Renewal Radar's lender-exact method where it is verified for this lender (Mortgage OS module)
        from .. import modules as OS
        OS.load_all()
        if "rr_bank_penalty" in T.TOOLS:
            ex = T.run("rr_bank_penalty", {"lender": row["lender"], "balance": bal, "contract_rate": rate, "start": start,
                                           "maturity": row["maturity"], "payout": as_of.isoformat(),
                                           "posted_at_origination": _f(row, "original_posted_rate")})
            if isinstance(ex, dict) and ex.get("status") == "exact-method" and ex.get("penalty") is not None:
                out["penalty_today"] = float(ex["penalty"])
                out["penalty_method"] = f"{ex.get('method')} ({ex.get('lender')} exact method, Renewal Radar)"
                out["penalty_status"] = "exact-method"
        if out["penalty_today"] is None and est.get("three_month_interest") is not None:
            out["penalty_floor"] = float(est["three_month_interest"])
    else:
        out["penalty_today"] = 0.0
        out["penalty_method"] = "matured"
    if _f(row, "annual_income") and renewal_rate:
        out["switch"] = renewal.switch_check(balance=bal, remaining_amort_years=_f(row, "remaining_amort_years", 20.0),
                                             new_rate=renewal_rate, annual_income=_f(row, "annual_income"),
                                             other_debt_monthly=_f(row, "other_debt_monthly", 0.0))
    pr = renewal.renewal_priority(months_to_maturity=months_left, pct_change=pct, balance=bal)
    out["priority"] = pr["score"]
    out["tier"] = pr["tier"]
    out["why"] = _why(out)
    return out


def _why(r: dict) -> str:
    parts = []
    if r["months_to_maturity"] <= 4:
        parts.append("inside the 120-day renewal window")
    elif r["months_to_maturity"] <= 12:
        parts.append(f"matures in {r['months_to_maturity']} months")
    if r.get("shock") and r["shock"]["pct_change"] >= 10:
        parts.append(f"payment up {r['shock']['pct_change']:.0f}% at renewal")
    if r.get("penalty_today") and r["months_to_maturity"] > 4:
        parts.append(f"penalty today about ${r['penalty_today']:,.0f}")
    elif r.get("penalty_today") is None and r["months_to_maturity"] > 4:
        if r.get("penalty_floor"):
            parts.append(f"penalty at least ${r['penalty_floor']:,.0f} (3 months' interest); IRD needs the lender's payout statement")
        else:
            parts.append("penalty needs the original posted rate or discount")
    return "; ".join(parts) or "monitor"


def scan(text: str, as_of: str | None = None, llm: NemotronClient | None = None, draft_top: int = 3) -> dict:
    rows, errors = parse_book(text)
    d = date.fromisoformat(as_of) if as_of else date.today()
    results = []
    for row in rows:
        try:
            results.append(scan_row(row, d))
        except Exception as e:  # one bad row never sinks the book
            errors.append(f"{row.get('borrower', '?')}: {type(e).__name__}: {e}")
    results.sort(key=lambda r: -r["priority"])
    summary = {"loans": len(results), "balance_total": round(sum(r["balance"] for r in results), 2),
               "call_this_week": sum(r["tier"] == "call this week" for r in results),
               "call_this_month": sum(r["tier"] == "call this month" for r in results),
               "avg_payment_change_pct": round(sum(r["shock"]["pct_change"] for r in results if r.get("shock")) /
                                               max(1, sum(1 for r in results if r.get("shock"))), 2)}
    if llm is not None:
        from ..agent.loop import draft_borrower_message
        for r in results[:draft_top]:
            try:
                r["outreach"] = draft_borrower_message(llm, purpose="mortgage renewal coming up; offer a review call",
                                                       facts={"first_name": r["borrower"].split()[0],
                                                              "months_to_maturity": r["months_to_maturity"]})
            except LLMError as e:
                r["outreach"] = {"error": str(e)}
    return {"as_of": d.isoformat(), "summary": summary, "queue": results, "errors": errors}
