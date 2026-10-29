"""The rungs of the Decision Ladder.

A mortgage file climbs from intake to decision. Each rung is a pure function of the file and the results
of the rungs below it, and returns a :class:`RungResult` with a status:

* ``PASS``    the rung is satisfied
* ``REFER``   a person must look (missing data, manual screening, a policy edge)
* ``FAIL``    the file as structured does not clear this rung (the ladder then searches for a path to yes)
* ``SKIP``    the rung does not apply to this file's purpose

No language model runs inside a rung. The model reads the rungs afterwards (see ``runner.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from ..agent import tools as T
from ..engines import (affordability, guardrail, homevalue, insurance, ird, kyc, lenders, qualify, ratebook,
                       renewal)

PASS, REFER, FAIL, SKIP = "PASS", "REFER", "FAIL", "SKIP"


@dataclass
class RungResult:
    key: str
    title: str
    status: str
    summary: str
    metrics: dict = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    stage: str = ""
    engines: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"key": self.key, "title": self.title, "status": self.status, "summary": self.summary,
                "stage": self.stage, "engines": self.engines,
                "metrics": self.metrics, "findings": self.findings, "evidence": self.evidence}


REQUIRED = {
    "purchase": ["borrower_name", "province", "price", "down_payment", "annual_income", "contract_rate", "credit_score"],
    "renewal": ["borrower_name", "province", "balance", "contract_rate", "maturity", "renewal_rate", "annual_income"],
    "refinance": ["borrower_name", "province", "balance", "contract_rate", "maturity", "annual_income", "property_value_or_purchase"],
    "commercial": ["borrower_name", "province", "loan", "value", "noi", "rate"],
}


def _purpose(f: dict) -> str:
    p = (f.get("purpose") or "purchase").lower()
    return p if p in REQUIRED else "purchase"


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def _today(f: dict) -> date:
    return date.fromisoformat(f["as_of"]) if f.get("as_of") else date.today()


# ------------------------------------------------------------------------------------------- rungs
def rung_intake(f: dict, ctx: dict) -> RungResult:
    purpose = _purpose(f)
    need = REQUIRED[purpose]
    missing = []
    for k in need:
        if k == "property_value_or_purchase":
            if not (f.get("property_value") or (f.get("purchase_price") and f.get("purchase_year") and f.get("postal_code"))):
                missing.append("property_value (or purchase_price + purchase_year + postal_code)")
        elif f.get(k) in (None, ""):
            missing.append(k)
    flags = []
    if f.get("contract_rate") is not None and not (0 < float(f["contract_rate"]) < 20):
        flags.append("contract_rate outside 0-20%")
    if f.get("credit_score") is not None and not (300 <= int(f["credit_score"]) <= 900):
        flags.append("credit_score outside 300-900")
    status = PASS if not missing and not flags else REFER
    return RungResult("intake", "Intake & completeness", status,
                      f"{purpose.title()} file; {len(need) - len(missing)}/{len(need)} required fields present",
                      {"purpose": purpose, "missing": missing}, [f"Missing: {m}" for m in missing] + flags)


def rung_screening(f: dict, ctx: dict) -> RungResult:
    res = kyc.screen(f.get("borrower_name") or "", f.get("watchlist_path"))
    status = REFER if res.get("requires_manual_review") else PASS
    if res["status"] == "POTENTIAL_MATCH":
        status = FAIL
    return RungResult("screening", "Identity & watch-list screening", status,
                      {"NOT_SCREENED": "Not screened: no licensed list connected. A person must verify ID.",
                       "NO_MATCH_IN_PROVIDED_LIST": "No match in the supplied list (not a clearance).",
                       "POTENTIAL_MATCH": "Potential watch-list match: escalate to compliance.",
                       "ERROR": "Borrower name missing."}.get(res["status"], res["status"]),
                      {"screening_status": res["status"]}, [res.get("detail", "")], {"screen": res})


INCOME_DOCS = ("t4", "noa", "pay_stub", "employment_letter")


def rung_documents(f: dict, ctx: dict) -> RungResult:
    docs = f.get("documents") or []
    if not docs:
        return RungResult("documents", "Document check", REFER, "No documents attached; stated figures are unverified.",
                          {"documents": 0}, ["Request income documents (T4/NOA or pay stub + employment letter)."])
    issues, notes, checked = [], [], 0
    # Income: documented income per borrower (the highest figure among that borrower's income documents),
    # summed across borrowers, against the stated household income.
    per_borrower: dict[str, float] = {}
    for i, d in enumerate(docs):
        ex = d.get("extracted") or {}
        notes += d.get("notes") or []
        if "annual_income" in ex and (d.get("type") in INCOME_DOCS or "type" not in d or d.get("type") not in
                                      ("renewal_letter", "mortgage_statement")):
            who = str(d.get("borrower") or "applicant")
            per_borrower[who] = max(per_borrower.get(who, 0.0), float(ex["annual_income"]))
        for key, tol in (("balance", 0.01), ("contract_rate", 0.0001), ("renewal_rate", 0.0001)):
            if key in ex and f.get(key) is not None:
                checked += 1
                a, b = float(ex[key]), float(f[key])
                if b and abs(a - b) / abs(b) > tol:
                    issues.append(f"{d.get('type', 'document')}: {key} on document {a:,.2f} vs stated {b:,.2f}")
        if "maturity" in ex and f.get("maturity"):
            checked += 1
        if "maturity" in ex and f.get("maturity") and ex["maturity"] != f["maturity"]:
            issues.append(f"{d.get('type', 'document')}: maturity {ex['maturity']} vs stated {f['maturity']}")
    metrics = {"documents": len(docs), "reconciled": checked}
    if per_borrower and f.get("annual_income") is not None:
        checked += 1
        documented, stated = round(sum(per_borrower.values()), 2), float(f["annual_income"])
        metrics.update({"documented_income": documented, "stated_income": stated,
                        "income_documented_pct": round(documented / stated * 100, 1) if stated else None,
                        "reconciled": checked})
        if documented < stated * 0.95:
            issues.append(f"Documented income {documented:,.0f} covers {documented / stated * 100:.0f}% of the stated "
                          f"{stated:,.0f}: request documents for the remaining income or co-borrower.")
        elif documented > stated * 1.10:
            notes.append(f"Documented income {documented:,.0f} is above the stated {stated:,.0f}: confirm which figure to use.")
    metrics["discrepancies"] = len(issues)
    status = PASS if checked and not issues else REFER
    return RungResult("documents", "Document check", status,
                      f"{len(docs)} document(s), {checked} figure(s) reconciled, {len(issues)} discrepancy(ies)",
                      metrics, issues + notes)


def rung_collateral(f: dict, ctx: dict) -> RungResult:
    purpose = _purpose(f)
    if purpose == "purchase":
        if f.get("postal_code") and f.get("price"):
            return RungResult("collateral", "Collateral", PASS, "Purchase price is the value basis (appraisal still required).",
                              {"value_basis": float(f["price"]), "basis": "purchase price"}, ["Order appraisal per lender."])
        return RungResult("collateral", "Collateral", REFER, "No postal code; cannot place the property.", {}, [])
    if f.get("property_value"):
        val, basis, ev = float(f["property_value"]), "stated value", {}
    elif f.get("purchase_price") and f.get("purchase_year") and f.get("postal_code"):
        hv = homevalue.indexed_value(float(f["purchase_price"]), int(f["purchase_year"]), int(f.get("purchase_month", 6)),
                                     f["postal_code"])
        val, basis, ev = hv["estimate"], "regional index estimate (not an appraisal)", {"home_value": hv}
    else:
        return RungResult("collateral", "Collateral", REFER, "No value or purchase history to estimate value.", {}, [])
    bal = float(f.get("balance", 0)) + float(f.get("new_money", 0))
    ltv = bal / val * 100 if val else None
    status = PASS if ltv is not None and ltv <= 80 else REFER
    findings = []
    if ltv is not None and ltv > 80:
        if purpose == "refinance":
            findings.append(f"LTV {ltv:.1f}% is above the 80% refinance limit for uninsured lending.")
        else:
            status = PASS
            findings.append(f"LTV {ltv:.1f}%: renewing with the current lender is unaffected, but an uninsured switch "
                            "above 80% may be limited at other lenders. Get a value estimate from the lender.")
    return RungResult("collateral", "Collateral", status, f"Value basis {val:,.0f} ({basis}); LTV {ltv:.1f}%",
                      {"value_basis": val, "basis": basis, "ltv": round(ltv, 2)}, findings, ev)


def rung_insurance(f: dict, ctx: dict) -> RungResult:
    if _purpose(f) != "purchase":
        return RungResult("insurance", "Default insurance", SKIP, "Applies to purchases in this build.")
    p = insurance.premium(price=float(f["price"]), down_payment=float(f["down_payment"]),
                          amort_years=int(f.get("amort_years", 25)), province=f.get("province", "ON"))
    findings = [p.note]
    mn = qualify.insured.min_down_payment(float(f["price"]))
    status = PASS
    if float(f["down_payment"]) < mn:
        status = FAIL
        findings.append(f"Down payment below the legal minimum of {mn:,.0f}.")
    ctx["insured_loan"] = p.total_loan
    return RungResult("insurance", "Default insurance", status,
                      "Insured: premium added to the loan" if p.insured else "Conventional (no insurance premium)",
                      {"insured": p.insured, "premium_rate_pct": p.premium_rate_pct, "premium": p.premium,
                       "pst_on_premium": p.pst_on_premium, "total_loan": p.total_loan, "min_down_payment": round(mn, 2)},
                      findings, {"premium": p.to_dict()})


def _qual_file(f: dict, ctx: dict) -> dict:
    keys = ("price", "down_payment", "annual_income", "contract_rate", "property_tax_annual", "heat_annual",
            "condo_fees_monthly", "other_debt_monthly", "amort_years", "first_time_buyer", "new_build")
    return {k: f[k] for k in keys if f.get(k) is not None}


def rung_qualification(f: dict, ctx: dict) -> RungResult:
    purpose = _purpose(f)
    if purpose == "commercial":
        return RungResult("qualification", "B-20 stress test (GDS/TDS)", SKIP,
                          "Commercial loans are underwritten on DSCR and debt yield (see the commercial rung).")
    if purpose == "purchase":
        qf = _qual_file(f, ctx)
        q = qualify.qualify(**qf)
        ctx["qualification"] = q.to_dict()
        metrics = {k: v for k, v in q.to_dict().items() if k != "reasons"}
        ev = {"qualification": q.to_dict()}
        if not q.passes:
            ev["path_to_yes"] = affordability.remediation_options(qf)
            ctx["path_to_yes"] = ev["path_to_yes"]
        return RungResult("qualification", "B-20 stress test (GDS/TDS)", PASS if q.passes else FAIL,
                          f"Qualifying rate {q.qualifying_rate:.2f}%: GDS {q.gds:.1f}%, TDS {q.tds:.1f}%",
                          metrics, q.reasons, ev)
    # renewal / refinance: switch check against a new lender
    rem = float(f.get("remaining_amort_years", 20))
    sc = renewal.switch_check(balance=float(f["balance"]) + float(f.get("new_money", 0)), remaining_amort_years=rem,
                              new_rate=float(f.get("renewal_rate") or f.get("new_rate") or f["contract_rate"]),
                              annual_income=float(f["annual_income"]), property_tax_annual=float(f.get("property_tax_annual", 0)),
                              other_debt_monthly=float(f.get("other_debt_monthly", 0)), insured=bool(f.get("insured")),
                              increases_amount_or_amort=purpose == "refinance" or bool(f.get("new_money")))
    ctx["switch"] = sc
    status = PASS if sc["can_switch"] else FAIL
    return RungResult("qualification", "Stress test at switch / refinance", status,
                      f"Stressed at {sc['qualifying_rate']:.2f}%: GDS {sc['gds']:.1f}%, TDS {sc['tds']:.1f}%; "
                      f"stress test {'required' if sc['stress_test_required'] else 'not required for a straight switch'}",
                      sc, [sc["rule"]], {"switch": sc})


def rung_lender(f: dict, ctx: dict) -> RungResult:
    if _purpose(f) == "commercial":
        return RungResult("lender", "Lender fit", SKIP, "Residential lender categories do not apply to commercial deals.")
    q = ctx.get("qualification") or ctx.get("switch") or {}
    ltv = q.get("ltv") or (ctx.get("rungs", {}).get("collateral", {}).get("metrics", {}).get("ltv")) or 80.0
    if f.get("credit_score") is None or not q:
        return RungResult("lender", "Lender fit", REFER, "Credit score or ratios missing.", {}, [])
    hits = lenders.match(province=(f.get("province") or "ON").upper(), credit_score=int(f["credit_score"]),
                         ltv=float(ltv), gds=float(q.get("gds", 99)), tds=float(q.get("tds", 99)))
    cats: dict[str, list[str]] = {}
    for l in hits:
        cats.setdefault(l.category, []).append(l.name)
    status = PASS if any(c in cats for c in ("BIG_BANK", "MONOLINE", "CREDIT_UNION", "PROVINCIAL_FI")) else (REFER if cats else FAIL)
    summary = (f"{len(hits)} lender(s) in {len(cats)} categor{'y' if len(cats) == 1 else 'ies'}" if hits
               else "No lender category fits as structured")
    findings = ["Illustrative category policy; confirm each lender's live guidelines."]
    if status == REFER:
        findings.insert(0, "Only alternative (B) lenders fit: expect higher rate and fees; disclose to client.")
    return RungResult("lender", "Lender fit", status, summary, {"count": len(hits), "categories": {k: len(v) for k, v in cats.items()}},
                      findings, {"by_category": cats})


def rung_market(f: dict, ctx: dict) -> RungResult:
    snap = ratebook.market_snapshot(f.get("as_of"))
    eff = snap["effective_new_lending"]
    insured = bool(ctx.get("rungs", {}).get("insurance", {}).get("metrics", {}).get("insured")) or bool(f.get("insured"))
    key = "actual_rate_new_insured" if insured else "actual_rate_new_uninsured"
    ref = (eff.get(key) or {}).get(60)
    rate = f.get("renewal_rate") if _purpose(f) == "renewal" and f.get("renewal_rate") else f.get("contract_rate")
    findings, metrics = [], {"policy_rate": (snap["policy_rate"] or {}).get("rate"), "prime": (snap["prime"] or {}).get("rate"),
                             "goc_5y": ((snap["goc_curve"] or {}).get(60) or {}).get("rate")}
    status = PASS
    if ref and rate is not None:
        gap = round(float(rate) - ref["rate"], 2)
        metrics.update({"file_rate": float(rate), "market_reference": ref["rate"], "market_reference_date": ref["date"],
                        "gap_pct_points": gap})
        if gap < -0.40:
            status = REFER
            findings.append(f"File rate is {abs(gap):.2f} points below the BoC average new {'insured' if insured else 'uninsured'} 5y+ rate: confirm the rate is available.")
        elif gap > 0.60:
            findings.append(f"File rate is {gap:.2f} points above the BoC average: the client may be able to do better.")
    ev = {"snapshot": snap}
    cyc = T.run("rate_cycle_history", {"from": "2022-01"})
    if isinstance(cyc, dict) and "error" not in cyc:
        pol, mtg = cyc["summary"]["policy"], cyc["summary"]["mortgage"]
        ev["rate_cycle"] = {k: v for k, v in cyc.items() if k != "rows"}
        if pol.get("max") and mtg.get("max"):
            metrics.update({"policy_peak": pol["max"]["value"], "policy_peak_month": pol["max"]["month"],
                            "mortgage_5y_peak": mtg["max"]["value"], "mortgage_5y_peak_month": mtg["max"]["month"]})
            findings.append(f"Rate cycle (Canada's Rate Cycle dashboard): policy rate peaked at {pol['max']['value']}% "
                            f"({pol['max']['month']}); the 5-year conventional rate peaked at {mtg['max']['value']}% ({mtg['max']['month']}).")
    sp = T.run("rate_spreads", {"as_of": f.get("as_of")} if f.get("as_of") else {})
    if isinstance(sp, dict) and "error" not in sp and sp.get("spreads"):
        ev["rate_spreads"] = sp
        s_ = sp["spreads"]
        if "posted_minus_effective_pts" in s_:
            metrics["posted_minus_effective_pts"] = s_["posted_minus_effective_pts"]
            findings.append(f"Posted 5-year is {s_['posted_minus_effective_pts']:.2f} points above what borrowers actually got "
                            f"(Bank of Canada notebooks): quote against the effective rate, not the posted one.")
        if "real_policy_rate_pts" in s_:
            metrics["real_policy_rate_pts"] = s_["real_policy_rate_pts"]
    return RungResult("market", "Market & rate check", status,
                      f"Policy {metrics['policy_rate']}% / prime {metrics['prime']}% / GoC 5y {metrics['goc_5y']}%",
                      metrics, findings, ev)


def rung_exit_cost(f: dict, ctx: dict) -> RungResult:
    purpose = _purpose(f)
    if purpose in ("purchase", "commercial"):
        return RungResult("exit_cost", "Exit cost & renewal economics", SKIP, "No existing mortgage on a purchase.")
    today = _today(f)
    mat = date.fromisoformat(f["maturity"])
    months_left = max(0, _months_between(today, mat))
    ev: dict[str, Any] = {}
    metrics: dict[str, Any] = {"months_to_maturity": months_left}
    findings: list[str] = []
    pen_total = 0.0
    if months_left > 0 and f.get("term_start"):
        pen = T.run("penalty_by_lender", {"lender": f.get("lender", "generic"), "balance": f["balance"],
                                          "contract_rate": f["contract_rate"], "term_start": f["term_start"],
                                          "maturity": f["maturity"], "payout_date": today.isoformat(),
                                          "original_posted_rate": f.get("original_posted_rate"),
                                          "contract_discount": f.get("contract_discount")})
        ev["penalty"] = pen
        est = (pen.get("estimate") or {}) if isinstance(pen, dict) else {}
        if est.get("total_estimate") is not None:
            pen_total = float(est["total_estimate"])
            metrics["penalty_estimate"] = pen_total
            metrics["penalty_method"] = est.get("controlling_method")
        generic_warnings = (pen.get("warnings") or []) if isinstance(pen, dict) else []
        # Renewal Radar's lender-exact method (reproduced against the lender's own calculator where verified)
        exact = T.run("rr_bank_penalty", {"lender": f.get("lender", "generic"), "balance": f["balance"],
                                          "contract_rate": f["contract_rate"], "start": f["term_start"],
                                          "maturity": f["maturity"], "payout": today.isoformat(),
                                          "posted_at_origination": f.get("original_posted_rate"),
                                          "discount": f.get("contract_discount")})
        ev["penalty_lender_exact"] = exact
        if isinstance(exact, dict) and exact.get("status") == "exact-method" and exact.get("penalty") is not None:
            if pen_total:
                findings.append(f"Generic posted-minus-discount estimate (whole months): {pen_total:,.2f}.")
            pen_total = float(exact["penalty"])
            metrics.update({"penalty_estimate": pen_total, "penalty_method": f"{exact.get('method')} ({exact.get('lender')} exact method)",
                            "penalty_method_source": exact.get("method_source")})
            findings.insert(0, f"Renewal Radar {exact.get('lender')} exact method: {pen_total:,.2f} "
                               f"({exact.get('remaining_months')} months left, day-exact).")
        else:
            findings += generic_warnings
    elif months_left > 0:
        findings.append("term_start missing: cannot date the penalty precisely.")
    if f.get("original_principal") and f.get("original_rate") and f.get("original_amort_years") and f.get("months_elapsed"):
        shock = renewal.renewal_shock(original_principal=float(f["original_principal"]), original_rate=float(f["original_rate"]),
                                      original_amort_years=float(f["original_amort_years"]), months_elapsed=int(f["months_elapsed"]),
                                      renewal_rate=float(f.get("renewal_rate") or f["contract_rate"]))
        ev["shock"] = shock
        metrics.update({"payment_before": shock["payment_before"], "payment_after": shock["payment_after"],
                        "payment_change_pct": shock["pct_change"]})
    offers = f.get("offers") or []
    if offers:
        cmp_ = renewal.offer_comparison(balance=float(f["balance"]), remaining_amort_years=float(f.get("remaining_amort_years", 20)),
                                        term_years=float(f.get("term_years", 5)), offers=offers)
        ev["offers"] = cmp_
        metrics["best_offer"] = cmp_["lowest_net_cost"]
        worst = max(o["extra_cost_vs_best"] for o in cmp_["offers"])
        metrics["max_saving_vs_worst_offer"] = worst
    new_rate = f.get("renewal_rate") or f.get("new_rate")
    if new_rate:
        chk = T.run("renewal_offer_check", {"balance": f["balance"], "years": float(f.get("remaining_amort_years", 20)),
                                            "currentRate": f["contract_rate"], "offerRate": new_rate})
        ev["renewal_check"] = chk
        if isinstance(chk, dict) and "error" not in chk and chk.get("keep"):
            keep = chk["keep"]
            if keep.get("covers") and keep.get("extraMonths") is not None:
                xm = keep["extraMonths"]
                metrics["keep_old_payment_extra_months"] = round(xm, 1)
                findings.append(f"Renewal Check: keeping today's payment at {new_rate}% "
                                + (f"stretches the mortgage by about {xm / 12:.1f} years." if xm >= 0 else
                                   f"pays the mortgage off about {-xm / 12:.1f} years sooner."))
            elif keep.get("covers") is False:
                findings.append("Renewal Check: today's payment would no longer cover the interest at the new rate.")
    if purpose == "renewal":
        alt = min((float(o["rate"]) for o in offers), default=None) if offers else None
        sw = T.run("rr_switch_pathway", {"balance": f["balance"], "offered_rate": f.get("renewal_rate"),
                                         "maturity_date": f["maturity"], "new_contract_rate": alt})
        ev["switch_pathway"] = sw
        if isinstance(sw, dict) and sw.get("headline"):
            findings.append(f"Renewal Radar switch pathway: {sw['headline']}.")
        plan = T.run("rr_renewal_plan", {"maturity_date": f["maturity"]})
        ev["renewal_plan"] = plan
        if alt is not None and f.get("renewal_rate") and alt < float(f["renewal_rate"]):
            neg = T.run("rr_negotiation_script", {"balance": f["balance"], "offered_rate": f["renewal_rate"],
                                                  "maturity_date": f["maturity"], "lender": f.get("lender"),
                                                  "competing_rate": alt})
            ev["negotiation"] = neg
            if isinstance(neg, dict) and neg.get("call_script"):
                findings.append("Renewal Radar drafted a retention-call script and email to ask the lender to match.")
    pr = renewal.renewal_priority(months_to_maturity=months_left, pct_change=float(metrics.get("payment_change_pct", 0) or 0),
                                  balance=float(f["balance"]))
    metrics["priority"] = pr["score"]
    metrics["priority_tier"] = pr["tier"]
    status = PASS
    if purpose == "refinance" and pen_total > 0 and f.get("new_rate"):
        refi = ird.refinance_analysis(balance=float(f["balance"]), current_rate=float(f["contract_rate"]),
                                      new_rate=float(f["new_rate"]), months_remaining=months_left,
                                      amort_years_remaining=float(f.get("remaining_amort_years", 20)),
                                      penalty_amount=pen_total, other_costs=float(f.get("closing_costs", 1500)))
        ev["refinance"] = refi
        metrics.update({"net_saving_over_term": refi["net_saving_over_term"], "break_even_months": refi["break_even_months"]})
        findings.append(f"Refinance at the new rate: net {'saving' if refi['net_saving_over_term'] > 0 else 'cost'} of "
                        f"{abs(refi['net_saving_over_term']):,.0f} over the {months_left} months left, after the penalty "
                        f"and {float(f.get('closing_costs', 1500)):,.0f} of closing costs.")
        if refi["net_saving_over_term"] <= 0:
            status = REFER
    elif months_left > 4 and pen_total > 0:
        findings.append(f"Breaking now costs about {pen_total:,.0f}; waiting until the 120-day renewal window avoids it.")
        status = REFER
    pen_txt = f"; penalty about {pen_total:,.0f} ({metrics.get('penalty_method')})" if pen_total else ""
    return RungResult("exit_cost", "Exit cost & renewal economics", status,
                      f"{months_left} month(s) to maturity{pen_txt}; priority {pr['score']} ({pr['tier']})", metrics, findings, ev)


def _disclosure_checks(f: dict, ctx: dict) -> tuple[list[str], dict, dict, bool]:
    """Disclosure & Compliance Desk on this file: Ontario cost of borrowing (APR), renewal statement timing and
    Interest Act s.10. Returns (findings, metrics, evidence, problem_found)."""
    findings: list[str] = []
    metrics: dict[str, Any] = {}
    ev: dict[str, Any] = {}
    problem = False
    purpose = _purpose(f)
    province = str(f.get("province", "ON")).upper()
    q = ctx.get("rungs", {}).get("qualification", {}).get("metrics", {})
    principal = q.get("mortgage_amount") or (f.get("price", 0) - f.get("down_payment", 0) if purpose == "purchase" else f.get("balance"))
    rate = f.get("renewal_rate") if purpose == "renewal" and f.get("renewal_rate") else f.get("contract_rate")
    if province == "ON" and purpose != "commercial" and principal and rate:
        cob = T.run("disclosure_cost_of_borrowing", {
            "principal": float(principal), "annual_rate": float(rate), "amort_years": float(f.get("amort_years") or 25),
            "term_months": int(round(float(f.get("term_years") or 5) * 12)), "charges": f.get("disclosure_charges") or []})
        if "error" not in cob:
            ev["cost_of_borrowing"] = cob
            metrics.update({"apr_pct": cob.get("apr_pct"), "cost_of_borrowing_term": cob.get("cost_of_borrowing")})
            findings.append(f"Cost of borrowing disclosure (O. Reg. 191/08): APR {cob['apr_pct']:.3f}%, "
                            f"${cob['cost_of_borrowing']:,.0f} over the {cob['term_years']:g}-year term; deliver it at least "
                            "2 business days before the borrower signs.")
    if purpose == "renewal" and f.get("maturity"):
        args = {"maturity_date": f["maturity"]}
        if f.get("renewal_statement_date"):
            args["statement_date"] = f["renewal_statement_date"]
        rt = T.run("renewal_disclosure_timing", args)
        if "error" not in rt:
            ev["renewal_timing"] = rt
            t = rt.get("timing") or {}
            if t.get("latest_compliant_date"):
                metrics["renewal_statement_latest"] = t["latest_compliant_date"]
            if f.get("renewal_statement_date"):
                if not t.get("ok", True):
                    problem = True
                    findings.append(f"Renewal statement is late: {rt.get('finding')} (21 days required).")
                else:
                    findings.append(f"Renewal statement timing OK: {rt.get('finding')}.")
            elif t.get("latest_compliant_date"):
                findings.append(f"Renewal statement must reach the borrower by {t['latest_compliant_date']} (21 days before maturity).")
    if float(f.get("term_years") or 0) > 5:
        findings.append("Term over 5 years: Interest Act s.10 lets the borrower prepay after 5 years with 3 months' interest.")
    return findings, metrics, ev, problem


def rung_compliance(f: dict, ctx: dict) -> RungResult:
    msg = f.get("outbound_message") or ctx.get("outbound_message") or ""
    chk = guardrail.check(msg) if msg else {"allowed": True, "violations": []}
    checklist = ["Disclose any conflict of interest and lender compensation before the client commits (FSRA).",
                 "Provide the mortgage cost disclosure / mortgage information to the borrower.",
                 "Keep a record of the suitability assessment for this product."]
    extra, metrics, ev, problem = _disclosure_checks(f, ctx)
    status = FAIL if not chk["allowed"] else REFER if problem else PASS
    summary = ("Outbound message clean" if msg and chk["allowed"] else
               ("Outbound message blocked: " + ", ".join(chk["violations"]) if msg else "No outbound message yet"))
    if metrics.get("apr_pct") is not None:
        summary += f"; APR {metrics['apr_pct']:.3f}%"
    return RungResult("compliance", "Compliance & outbound guardrail", status, summary,
                      {"violations": chk["violations"], **metrics}, extra + checklist, {"guardrail": chk, **ev})


def rung_decision(f: dict, ctx: dict) -> RungResult:
    rungs = ctx["rungs"]
    fails = [r for r in rungs.values() if r["status"] == FAIL]
    refers = [r for r in rungs.values() if r["status"] == REFER]
    if fails:
        verdict = "RESTRUCTURE" if ctx.get("path_to_yes") else "DECLINE AS STRUCTURED"
    elif refers:
        verdict = "GO WITH CONDITIONS"
    else:
        verdict = "GO"
    conditions = [f"{r['title']}: {r['summary']}" for r in refers]
    blockers = [f"{r['title']}: {r['summary']}" for r in fails]
    options = []
    for o in (ctx.get("path_to_yes") or {}).get("options", []):
        if o.get("max_price"):
            options.append(f"Lower the price to {o['max_price']:,.0f}")
        elif o.get("min_down_payment"):
            options.append(f"Raise the down payment to {o['min_down_payment']:,.0f} (+{o['additional_needed']:,.0f})")
        elif o.get("max_other_debt_monthly") is not None and o.get("debt_to_pay_down_monthly"):
            options.append(f"Pay down {o['debt_to_pay_down_monthly']:,.0f}/month of other debt")
        elif o.get("min_annual_income"):
            options.append(f"Add income or a co-borrower: {o['min_annual_income']:,.0f}/yr needed (+{o['shortfall']:,.0f})")
        elif o.get("lever") == "30_year_amortization" and o.get("passes"):
            options.append("Use a 30-year amortization")
    fix = ctx.get("closing_fix")
    if fix:
        options.append(f"Keep cash for closing: put {fix['down_payment']:,.0f} down"
                       + (" (insured)" if fix.get("insured") else "")
                       + ("; still passes the stress test" if fix.get("still_passes_stress_test") else "; stress test then fails"))
    return RungResult("decision", "Decision", PASS if verdict == "GO" else (REFER if verdict == "GO WITH CONDITIONS" else FAIL),
                      verdict, {"verdict": verdict, "fails": len(fails), "refers": len(refers)},
                      blockers + conditions, {"options": options})


def _staged_ladder():
    from . import os_rungs as O
    # (key, rung function, lifecycle stage, engines: module keys from the Mortgage OS registry)
    return [
        ("intake", rung_intake, "lead", ["decision-ladder"]),
        ("screening", rung_screening, "documents", ["mortgageloanops"]),
        ("documents", rung_documents, "documents", ["decision-ladder", "doc-quest"]),
        ("affordability", O.rung_affordability, "prequal", ["canadian-mortgage-suite", "canada-housing-affordability-index-1980-2026"]),
        ("readiness", O.rung_readiness, "underwriting", ["pre-underwriting-copilot", "quiet-charges", "shoebox"]),
        ("insurance", rung_insurance, "underwriting", ["decision-ladder"]),
        ("qualification", rung_qualification, "underwriting", ["mortgageloanops", "decision-ladder"]),
        ("crosscheck", O.rung_crosscheck, "underwriting", ["mortgageloanops", "canadian-mortgage-suite", "pre-underwriting-copilot",
                                                         "cash-to-close", "renewal-check", "renewal-radar"]),
        ("lender", rung_lender, "underwriting", ["mortgageloanops"]),
        ("property", O.rung_property, "property", ["benchmark-home-value"]),
        ("closing", O.rung_closing, "closing", ["cash-to-close", "canadian-mortgage-suite"]),
        ("market", rung_market, "market", ["renewal-radar", "canada-rate-cycle-dashboard", "canada-policy-rate-bond-yield-mortgage-rate"]),
        ("exit_cost", rung_exit_cost, "servicing", ["renewal-radar", "renewal-check", "mortgageloanops"]),
        ("renewal_outlook", O.rung_renewal_outlook, "servicing", ["renewal-shock-radar"]),
        ("commercial", O.rung_commercial, "commercial", ["private-credit-screener"]),
        ("compliance", rung_compliance, "compliance", ["mortgageloanops"]),
        ("decision", rung_decision, "decision", ["decision-ladder"]),
    ]


LADDER_STAGED = _staged_ladder()
LADDER: list[tuple[str, Callable[[dict, dict], RungResult]]] = [(k, fn) for k, fn, _, _ in LADDER_STAGED]
