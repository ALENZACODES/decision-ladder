"""Rungs powered by the Mortgage OS modules: the author's own apps, called through their real code.

Each rung here calls one or more of the vendored apps (via ``agent.tools.run`` so failures come back as
data, never exceptions) and turns the result into a rung status a broker can act on.
"""
from __future__ import annotations

from datetime import date

from ..agent import tools as T
from ..engines import affordability, homevalue, insured, qualify
from . import crosscheck
from .rungs import FAIL, PASS, REFER, SKIP, RungResult, _months_between, _purpose, _qual_file, _today


def _err(res) -> str | None:
    return res.get("error") if isinstance(res, dict) else "no result"


def _place(f: dict) -> str | None:
    return f.get("city") or (str(f.get("postal_code") or "").replace(" ", "")[:3] or None)


# ------------------------------------------------------------------ prequal: Canadian Mortgage Suite + BoC index
def rung_affordability(f: dict, ctx: dict) -> RungResult:
    key, title = "affordability", "Affordability (max purchase price)"
    if _purpose(f) != "purchase":
        return RungResult(key, title, SKIP, "Applies to purchases.")
    a = T.run("affordability_by_income", {
        "annual_income": f["annual_income"], "contract_rate": f["contract_rate"], "down_payment": f["down_payment"],
        "amort_years": int(f.get("amort_years", 25)), "property_tax_annual": f.get("property_tax_annual", 0),
        "heat_monthly": round(float(f.get("heat_annual", 1800)) / 12, 2), "condo_fees_monthly": f.get("condo_fees_monthly", 0),
        "other_debt_monthly": f.get("other_debt_monthly", 0), "province": f.get("province", "ON"),
        "first_time": bool(f.get("first_time_buyer")), "new_build": bool(f.get("new_build"))})
    if _err(a):
        return RungResult(key, title, REFER, f"Affordability engine unavailable: {_err(a)}", {}, [], {"suite": a})
    idx = T.run("housing_affordability_index", {})
    price, mx = float(f["price"]), float(a["maxPrice"])
    metrics = {"max_price": mx, "price": price, "headroom": round(mx - price, 2), "limiting_ratio": a.get("limiting"),
               "qualifying_rate": a.get("qualifyingRate")}
    findings = []
    if not _err(idx):
        metrics.update({"boc_affordability_index_pct": idx.get("affordability_index_pct"), "index_quarter": idx.get("quarter"),
                        "index_long_run_avg_pct": idx.get("long_run_average_pct")})
        findings.append(f"National context: the Bank of Canada affordability index is {idx['affordability_index_pct']}% "
                        f"({idx['quarter']}) vs a {idx['long_run_average_pct']}% long-run average.")
    status = PASS if mx >= price else REFER
    if mx < price:
        findings.insert(0, f"Price is {price - mx:,.0f} above the {mx:,.0f} this income supports at the "
                           f"{a.get('qualifyingRate')}% qualifying rate ({a.get('limiting')} binds).")
    return RungResult(key, title, status, f"Supports up to {mx:,.0f} ({a.get('limiting')} limits); price {price:,.0f}",
                      metrics, findings, {"suite": a, "affordability_index": idx})


# ------------------------------------------------------------------ documents: Doc Quest checklist
DOC_TO_DQ = {"pay_stub": "paystub", "employment_letter": "joblet", "id": "id", "bank_statement": "bank90",
             "purchase_agreement": "aps", "gift_letter": "gift"}


def doc_checklist(f: dict) -> dict:
    emp = str(f.get("employment") or "salaried").lower()
    work = "self" if "self" in emp else "commission" if "commission" in emp else "hourly" if "hour" in emp else "salaried"
    sources = ["savings"] + (["gift"] if f.get("gift") else []) + (["fhsa"] if f.get("fhsa") else []) + \
        (["rrsp"] if f.get("rrsp_hbp") else [])
    done = sorted({DOC_TO_DQ[d.get("type")] for d in f.get("documents") or [] if d.get("type") in DOC_TO_DQ})
    return T.run("buyer_document_checklist", {"work": work, "sources": sources, "partner": bool(f.get("co_borrower")),
                                              "newcomer": bool(f.get("newcomer")), "done": done, "n": 3})


# ------------------------------------------------------------------ underwriting: Pre-Underwriting Check
def rung_readiness(f: dict, ctx: dict) -> RungResult:
    key, title = "readiness", "Pre-underwriting readiness"
    if _purpose(f) != "purchase":
        return RungResult(key, title, SKIP, "Applies to purchase files.")
    text = crosscheck.loan_file_text(f)
    r = T.run("pre_underwrite_loan_file", {"text": text})
    if _err(r):
        return RungResult(key, title, REFER, f"Pre-Underwriting Check unavailable: {_err(r)}", {}, [], {"text": text})
    flags = list(r.get("flags") or [])
    note = None
    if not f.get("example"):
        # The public demo app refuses unmarked files as a privacy guard; inside the OS the broker works on real files.
        kept = [x for x in flags if "not marked [EXAMPLE]" not in x.get("msg", "")]
        if len(kept) != len(flags):
            note = "The app's '[EXAMPLE] files only' privacy guard is for its public demo and is not applied inside the OS."
        flags = kept
    hi = sum(1 for x in flags if x["level"] == "high")
    me = sum(1 for x in flags if x["level"] == "medium")
    score = max(0, 100 - hi * 25 - me * 10 - (len(flags) - hi - me) * 3)   # the app's own scoring formula
    status_txt = "Not ready" if hi else "Conditional" if me else "Ready for lender review"
    status = PASS if status_txt.startswith("Ready") else REFER
    findings = [f"[{x['level']}] {x['msg']}" for x in flags[:8]] + ([note] if note else [])
    return RungResult(key, title, status, f"{status_txt}: readiness {score}/100, {len(flags)} flag(s)",
                      {"readiness_score": score, "status": status_txt, "flags_high": hi, "flags_medium": me,
                       "documents_checked": len(r.get("checks") or [])},
                      findings, {"review": {k: r.get(k) for k in ("ratios", "checks", "flags", "memo")}, "loan_file_text": text})


# ------------------------------------------------------------------ underwriting: cross-checks across engines
def rung_crosscheck(f: dict, ctx: dict) -> RungResult:
    key, title = "crosscheck", "Cross-check across independent engines"
    checks = crosscheck.run_checks(f)
    if not checks:
        return RungResult(key, title, SKIP, "No overlapping calculations for this file type.")
    compared = [c for c in checks if c["agree"] is not None]
    agree = [c for c in compared if c["agree"]]
    disagree = [c for c in compared if not c["agree"]]
    engines = sorted({e["engine"] for c in checks for e in c["engines"] if e.get("value") is not None})
    status = PASS if compared and not disagree else REFER
    findings = [f"{c['quantity']}: engines differ by {c['spread']} ({', '.join(str(e['value']) for e in c['engines'])})"
                for c in disagree]
    for c in agree:
        same = [e for e in c["engines"] if e.get("value") is not None and not e.get("note")]
        findings.append(f"{c['quantity']}: {len(same)} engines agree ({same[0]['value']:,})")
        for e in c["engines"]:
            if e.get("note") and e.get("value") is not None:
                findings.append(f"  {e['engine']}: {e['value']:,} ({e['note']})")
    return RungResult(key, title, status, f"{len(agree)}/{len(compared)} quantities agree across {len(engines)} engines",
                      {"checks": len(compared), "agree": len(agree), "disagree": len(disagree), "engines": len(engines)},
                      findings, {"checks": checks})


# ------------------------------------------------------------------ property: Benchmark Home Value
def rung_property(f: dict, ctx: dict) -> RungResult:
    key, title = "property", "Property value & local prices"
    purpose = _purpose(f)
    if purpose == "commercial":
        return RungResult(key, title, SKIP, "Commercial value comes from NOI and cap rate (see the commercial rung).")
    place = _place(f)
    ptype = (f.get("property_type") or "composite").lower()
    if ptype not in ("composite", "detached", "semi", "town", "condo"):
        ptype = "composite"
    bench = T.run("benchmark_home_price", {"place": place, "property_type": ptype}) if place else {"error": "no city or postal code"}
    area = T.run("postal_area_home_value", {"fsa": f["postal_code"]}) if f.get("postal_code") else None
    ev = {"benchmark": bench, "postal_area": area}
    metrics, findings = {}, []
    if not _err(bench):
        metrics.update({"area": bench["city"], "benchmark_price": bench["benchmark_price"], "property_type": ptype,
                        "benchmark_yoy_pct": bench["yoy_change_pct"], "benchmark_5y_pct": bench["change_5y_pct"],
                        "prices_as_of": bench["as_of"]})
    if purpose == "purchase":
        price = float(f["price"])
        status = PASS
        if not _err(bench):
            ratio = price / bench["benchmark_price"]
            metrics["price_vs_benchmark_pct"] = round((ratio - 1) * 100, 1)
            findings.append(f"{bench['city']} {ptype} benchmark is {bench['benchmark_price']:,.0f} "
                            f"({bench['yoy_change_pct']:+.1f}% over 12 months, {bench['change_5y_pct']:+.1f}% over 5 years).")
            if ratio > 1.25:
                status = REFER
                findings.insert(0, f"Price is {metrics['price_vs_benchmark_pct']:.0f}% above the local {ptype} benchmark: "
                                   "appraisal shortfall risk. Order the appraisal early.")
            elif bench["yoy_change_pct"] < -5:
                findings.append("Local prices are falling: an appraisal may come in under the price.")
        else:
            status = REFER
            findings.append(f"No local benchmark: {_err(bench)}")
        findings.append("Benchmarks are indicative, not an appraisal.")
        return RungResult(key, title, status, (f"{bench['city']} {ptype} benchmark {bench['benchmark_price']:,.0f}; price "
                                               f"{metrics.get('price_vs_benchmark_pct', 0):+.1f}% vs benchmark")
                          if not _err(bench) else "No local benchmark found", metrics, findings, ev)
    # renewal / refinance: value basis from Benchmark Home Value's purchase indexing, then LTV
    if f.get("property_value"):
        val, basis = float(f["property_value"]), "stated value"
    elif f.get("purchase_price") and f.get("purchase_year") and place:
        ix = T.run("index_purchase_to_today", {"purchase_price": f["purchase_price"], "purchase_year": f["purchase_year"],
                                               "purchase_month": f.get("purchase_month", 6), "place": place})
        ev["indexed"] = ix
        if _err(ix):
            hv = homevalue.indexed_value(float(f["purchase_price"]), int(f["purchase_year"]), int(f.get("purchase_month", 6)),
                                         f.get("postal_code") or "M5V")
            val, basis = hv["estimate"], "regional index (fallback engine)"
        else:
            val, basis = float(ix["value_today_rounded"]), f"purchase indexed to {ix['as_of']} (Benchmark Home Value)"
            metrics.update({"purchase_price": ix["purchase_price"], "value_change_pct": ix["change_pct"]})
    else:
        return RungResult(key, title, REFER, "No value or purchase history to estimate value.", metrics, [], ev)
    bal = float(f.get("balance", 0)) + float(f.get("new_money", 0))
    ltv = round(bal / val * 100, 2) if val else None
    metrics.update({"value_basis": val, "basis": basis, "ltv": ltv})
    status = PASS
    if ltv is not None and ltv > 80:
        if purpose == "refinance":
            status = REFER
            findings.append(f"LTV {ltv:.1f}% is above the 80% refinance limit for uninsured lending.")
        else:
            findings.append(f"LTV {ltv:.1f}%: renewing with the current lender is unaffected, but an uninsured switch above "
                            "80% may be limited at other lenders.")
    if metrics.get("value_change_pct") is not None and metrics["value_change_pct"] < 0:
        findings.append(f"Estimated value is {metrics['value_change_pct']:.1f}% below the purchase price: less equity than the client may expect.")
    return RungResult(key, title, status, f"Value basis {val:,.0f} ({basis}); LTV {ltv:.1f}%", metrics, findings, ev)


# ------------------------------------------------------------------ closing: Cash to Close / Suite closing costs
def _cash_plan(f: dict, down: float) -> dict:
    return T.run("cash_to_close_ontario", {"price": f["price"], "savings": f.get("savings") or 0, "down": down,
                                           "toronto": bool(f.get("toronto")), "first_time": bool(f.get("first_time_buyer")),
                                           "amort30": int(f.get("amort_years", 25)) > 25})


def rung_closing(f: dict, ctx: dict) -> RungResult:
    key, title = "closing", "Cash to close"
    if _purpose(f) != "purchase":
        return RungResult(key, title, SKIP, "Applies to purchases.")
    price, down = float(f["price"]), float(f["down_payment"])
    prov = (f.get("province") or "ON").upper()
    savings = f.get("savings")
    if prov == "ON":
        plan = _cash_plan(f, down)
        if _err(plan):
            return RungResult(key, title, REFER, f"Cash to Close unavailable: {_err(plan)}", {}, [], {"plan": plan})
        need = float(plan["cashToClose"])
        extras = round(need - down, 2)
        items = {i["label"]: i["amount"] for i in plan.get("items", [])}
        engine = "Cash to Close"
    else:
        cc = T.run("closing_costs_estimate", {"price": price, "province": prov, "first_time": bool(f.get("first_time_buyer"))})
        if _err(cc):
            return RungResult(key, title, REFER, f"Closing-cost engine unavailable: {_err(cc)}", {}, [], {"costs": cc})
        extras = float(cc.get("total") or 0)
        need, plan, items, engine = down + extras, cc, {}, "Canadian Mortgage Suite"
    metrics = {"cash_needed": round(need, 2), "down_payment": down, "closing_costs": extras, "engine": engine}
    findings = [f"{engine}: {need:,.0f} needed on closing day ({down:,.0f} down payment + {extras:,.0f} other costs)."]
    if savings is None:
        findings.insert(0, "Savings not stated: confirm the client can show closing costs on top of the down payment "
                           "(lenders typically want about 1.5% of the price).")
        return RungResult(key, title, REFER, f"{need:,.0f} needed on closing day; savings not stated", metrics, findings,
                          {"plan": plan, "items": items})
    savings = float(savings)
    gap = round(savings - need, 2)
    metrics.update({"savings": savings, "gap": gap})
    if gap >= 0:
        return RungResult(key, title, PASS, f"{need:,.0f} needed; savings {savings:,.0f} cover it ({gap:,.0f} spare)",
                          metrics, findings, {"plan": plan, "items": items})
    # Path to yes for closing: the largest down payment that still leaves enough cash for closing costs.
    fix = None
    if prov == "ON":
        lo, hi = insured.min_down_payment(price), down
        best = None
        for _ in range(18):
            mid = (lo + hi) / 2
            p = _cash_plan(f, mid)
            if _err(p):
                break
            if float(p["cashToClose"]) <= savings:
                best, lo = mid, mid
            else:
                hi = mid
        if best is not None:
            best = float(int(best // 500 * 500))
            p = _cash_plan(f, best)
            q = qualify.qualify(**{**_qual_file(f, ctx), "down_payment": best})
            fix = {"down_payment": best, "cash_needed": p.get("cashToClose"), "insured": p.get("insured"),
                   "premium": p.get("premium"), "pst_on_premium": p.get("pst"), "still_passes_stress_test": q.passes,
                   "gds": q.gds, "tds": q.tds}
            ctx.setdefault("closing_fix", fix)
            findings.append(f"Path to close: put {best:,.0f} down instead of {down:,.0f}, keeping cash for closing costs"
                            + (f"; the loan becomes insured (premium {p.get('premium'):,.0f}, PST {p.get('pst'):,.0f} due at closing)"
                               if p.get("insured") else "")
                            + ("; the file still passes the stress test." if q.passes else "; but the stress test then fails."))
    metrics["shortfall"] = -gap
    return RungResult(key, title, FAIL, f"Short {-gap:,.0f} on closing day ({need:,.0f} needed, {savings:,.0f} saved)",
                      metrics, findings, {"plan": plan, "items": items, "fix": fix})


# ------------------------------------------------------------------ servicing: Renewal Shock Radar (purchases)
def rung_renewal_outlook(f: dict, ctx: dict) -> RungResult:
    key, title = "renewal_outlook", "Renewal outlook (end of first term)"
    if _purpose(f) != "purchase":
        return RungResult(key, title, SKIP, "Renewal files are handled by the exit-cost rung.")
    q = ctx.get("qualification") or {}
    loan = q.get("mortgage_amount") or (float(f["price"]) - float(f["down_payment"]))
    rate, am, term = float(f["contract_rate"]), float(f.get("amort_years", 25)), float(f.get("term_years", 5))
    up = float(f.get("renewal_stress_pts", 1.0))
    r = T.run("renewal_shock_band", {"loan": loan, "origRate": rate, "amort": am, "term": term, "newRate": rate + up,
                                     "income": f.get("annual_income")})
    if _err(r):
        return RungResult(key, title, REFER, f"Renewal Shock Radar unavailable: {_err(r)}", {}, [], {"shock": r})
    band = r.get("band")
    band_name = (band.get("label") or band.get("name")) if isinstance(band, dict) else (band or "n/a")
    pct = r.get("pct")
    metrics = {"renewal_in_years": term, "rate_scenario": round(rate + up, 2),
               "payment_change_pct": round(pct, 2) if isinstance(pct, (int, float)) else pct, "band": band_name,
               "balance_at_renewal": round(r["balance"], 2) if isinstance(r.get("balance"), (int, float)) else None,
               "payment_now": round(r["oldPmt"], 2) if isinstance(r.get("oldPmt"), (int, float)) else None,
               "payment_at_renewal": round(r["newPmt"], 2) if isinstance(r.get("newPmt"), (int, float)) else None,
               "share_of_income_after_pct": round(r["shareNew"], 1) if isinstance(r.get("shareNew"), (int, float)) else None}
    severe = isinstance(pct, (int, float)) and pct >= 20
    findings = [f"If rates are {up:.1f} point higher at renewal in {term:.0f} years, the payment changes about "
                f"{pct:+.1f}% ({band_name})." if isinstance(pct, (int, float)) else "Renewal scenario computed."]
    return RungResult(key, title, REFER if severe else PASS,
                      f"+{up:.1f} pt at renewal: payment {pct:+.1f}% ({band_name})" if isinstance(pct, (int, float)) else "Computed",
                      metrics, findings, {"shock": r})


# ------------------------------------------------------------------ commercial: Private Credit Deal Screener
def rung_commercial(f: dict, ctx: dict) -> RungResult:
    key, title = "commercial", "Commercial / private credit screen"
    if _purpose(f) != "commercial":
        return RungResult(key, title, SKIP, "Residential file.")
    s = T.run("private_credit_deal_screen", {k: f[k] for k in ("loan", "value", "noi", "rate", "amort", "termYrs", "capRate",
                                                                "exitCapShift", "noiGrowth", "fees", "sponsorScore") if f.get(k) is not None})
    if _err(s):
        return RungResult(key, title, REFER, f"Private Credit Screener unavailable: {_err(s)}", {}, [], {"screen": s})
    m = s.get("metrics") or {}
    grade = s.get("grade")
    status = PASS if grade in ("A", "B") else REFER if grade == "C" else FAIL
    sens = s.get("sensitivity") or []
    top = sens[0] if sens else None
    metrics = {"grade": grade, "score": s.get("total"), **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()
                                                          if isinstance(v, (int, float))}}
    findings = []
    if top:
        findings.append(f"Grade is most sensitive to {top.get('label') or top.get('name') or top.get('key')}.")
    return RungResult(key, title, status, f"Grade {grade} (score {s.get('total')})", metrics, findings, {"screen": s})
