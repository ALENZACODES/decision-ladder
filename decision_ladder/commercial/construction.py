"""Construction loan: monthly draw schedule, Ontario Construction Act holdback, interest reserve and LTC.

Each budget line is spread evenly over its months. Hard costs are subject to the basic holdback (10% under the
Ontario Construction Act): 90% is paid when certified and 10% is retained until released. Equity goes in first
(land at month 0, then costs); the loan funds everything after that, including its own interest, which accrues
monthly on the drawn balance and is capitalized (the interest reserve).

Holdback release, two regimes:

* at completion: retained holdback is paid ``release_lag_months`` after the last hard-cost month (default 2,
  standing in for the 60-day lien period after substantial performance is certified; an assumption);
* annual release (Construction Act amendments in force Jan 1, 2026, for contracts entered on or after that
  date): holdback accrued in each contract year is released after the anniversary. The owner publishes notice
  within 14 days of the anniversary and pays 60 to 74 days later, modelled as anniversary + 3 months
  (assumption), with any remainder released at completion as above.
"""
from __future__ import annotations

from .common import pct, positive, r2, ratio

SOURCES = {
    "holdback_10pct": "https://lerners.ca/insights/knowing-when-to-holdem-calculating-basic-holdback-amounts-for-"
                      "construction-lien-claims",
    "annual_release_2026": "https://www.fasken.com/en/knowledge/2025/12/ontarios-amendments-to-the-construction-act-take-"
                           "effect-january-1-2026",
    "statute": "https://www.ontario.ca/laws/statute/90c30",
    "checked": "2026-10-29",
}
HOLDBACK_PCT = 10.0
ANNUAL_RELEASE_LAG_MONTHS = 3
DEFAULT_MAX_LTC_PCT = 75.0  # assumption: typical conventional construction lender; CMHC MLI products differ


def _monthly(budget: list[dict]) -> tuple[int, dict[int, float], dict[int, float], int | None, int | None]:
    hard, soft = {}, {}
    first_hard = last_hard = None
    end = 0
    for i, line in enumerate(budget):
        name = line.get("item") or f"line {i + 1}"
        cost = positive(f"{name} cost", line.get("cost", 0), allow_zero=True)
        s, e = int(line.get("start_month", 1)), int(line.get("end_month", line.get("start_month", 1)))
        if s < 1 or e < s:
            raise ValueError(f"{name}: months must satisfy 1 <= start_month <= end_month")
        bucket = hard if line.get("hard", True) else soft
        for m in range(s, e + 1):
            bucket[m] = bucket.get(m, 0.0) + cost / (e - s + 1)
        end = max(end, e)
        if line.get("hard", True) and cost:
            first_hard = s if first_hard is None else min(first_hard, s)
            last_hard = e if last_hard is None else max(last_hard, e)
    return end, hard, soft, first_hard, last_hard


def _simulate(equity: float, land: float, fee: float, hard: dict, soft: dict, months: int, rate_pct: float,
              holdback_pct: float, release_lag: int, annual_release: bool, first_hard: int | None,
              last_hard: int | None, keep_rows: bool) -> dict:
    i = rate_pct / 100 / 12
    h = holdback_pct / 100
    eq_left, bal, retained, year_accrued = equity, 0.0, 0.0, {}
    tot = {"interest": 0.0, "draws": 0.0, "equity_used": 0.0, "peak_holdback": 0.0, "released": 0.0}
    rows = []
    final_release = (last_hard or 0) + release_lag
    for m in range(0, max(months, final_release) + 1):
        interest = bal * i
        hc, sc = hard.get(m, 0.0), soft.get(m, 0.0)
        retain = hc * h
        retained += retain
        if first_hard is not None and hc:
            yr = (m - first_hard) // 12
            year_accrued[yr] = year_accrued.get(yr, 0.0) + retain
        release = 0.0
        if annual_release and first_hard is not None:
            for yr, amt in list(year_accrued.items()):
                if amt and m == first_hard + 12 * (yr + 1) + ANNUAL_RELEASE_LAG_MONTHS and m < final_release:
                    release += amt
                    year_accrued[yr] = 0.0
        if m == final_release:
            release = retained
            year_accrued.clear()
        retained -= release
        cash = (land + fee if m == 0 else 0.0) + hc - retain + sc + release
        from_equity = min(eq_left, cash)
        eq_left -= from_equity
        draw = cash - from_equity + interest
        bal += draw
        tot["interest"] += interest
        tot["draws"] += draw
        tot["equity_used"] += from_equity
        tot["released"] += release
        tot["peak_holdback"] = max(tot["peak_holdback"], retained)
        if keep_rows:
            rows.append({"month": m, "hard_cost": r2(hc), "soft_cost": r2(sc), "holdback_retained": r2(retain),
                         "holdback_released": r2(release), "cash_out": r2(cash), "equity": r2(from_equity),
                         "loan_draw_for_costs": r2(cash - from_equity), "interest": r2(interest), "loan_balance": r2(bal)})
    tot["balance"] = bal
    tot["equity_unused"] = eq_left
    tot["rows"] = rows
    tot["months"] = max(months, final_release)
    return tot


def schedule(*, budget: list[dict], rate_pct: float, equity: float, land_cost: float = 0.0, lender_fee: float = 0.0,
             term_months: int | None = None, max_ltc_pct: float = DEFAULT_MAX_LTC_PCT,
             completed_value: float | None = None, max_ltv_pct: float | None = None,
             holdback_pct: float = HOLDBACK_PCT, release_lag_months: int = 2, annual_release: bool = True,
             include_rows: bool = True) -> dict:
    """Draw schedule and interest reserve. Months are numbered from 1; month 0 is closing (land and lender fee).

    ``term_months``: interest accrues until this month (default: the later of the last cost month and the final
    holdback release). LTC = loan / total project cost, where total cost includes the capitalized interest.
    """
    if not budget:
        raise ValueError("budget needs at least one line")
    positive("rate_pct", rate_pct, allow_zero=True)
    equity, land, fee = (positive(n, v, allow_zero=True) for n, v in
                         (("equity", equity), ("land_cost", land_cost), ("lender_fee", lender_fee)))
    ratio("holdback_pct", holdback_pct)
    ratio("max_ltc_pct", max_ltc_pct)
    end, hard, soft, first_hard, last_hard = _monthly(budget)
    months = max(end, int(term_months or 0))

    def run(e: float, rows: bool = False) -> dict:
        return _simulate(e, land, fee, hard, soft, months, rate_pct, holdback_pct, int(release_lag_months),
                         bool(annual_release), first_hard, last_hard, rows)
    res = run(equity, include_rows)
    hard_total, soft_total = sum(hard.values()), sum(soft.values())
    base_cost = land + fee + hard_total + soft_total
    total_cost = base_cost + res["interest"]
    loan = res["balance"]
    ltc = loan / total_cost if total_cost else 0.0

    # Equity needed so loan / total cost <= max LTC: the ratio falls as equity rises, so bisect.
    target = max_ltc_pct / 100

    def over(e: float) -> bool:
        r = run(e)
        return r["balance"] > target * (base_cost + r["interest"]) + 0.005
    lo, hi = 0.0, base_cost
    if not over(lo):
        need = 0.0
    else:
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if over(mid) else (lo, mid)
        need = hi
    out = {
        "months": res["months"], "land_cost": r2(land), "lender_fee": r2(fee), "hard_costs": r2(hard_total),
        "soft_costs": r2(soft_total), "interest_reserve": r2(res["interest"]), "total_project_cost": r2(total_cost),
        "equity_in": r2(res["equity_used"]), "equity_unused": r2(res["equity_unused"]), "loan_amount": r2(loan),
        "ltc_pct": pct(ltc), "max_ltc_pct": max_ltc_pct, "ltc_ok": ltc <= target + 1e-9,
        "equity_required_for_ltc": r2(need), "equity_shortfall": r2(max(0.0, need - equity)),
        "holdback": {"pct": holdback_pct, "total_retained": r2(hard_total * holdback_pct / 100),
                     "peak_retained": r2(res["peak_holdback"]), "regime": "annual release (contracts from 2026-01-01)"
                     if annual_release else "release at completion", "final_release_month": (last_hard or 0) + int(release_lag_months)},
        "rate_pct": rate_pct, "interest_convention": "monthly compounding on drawn balance, capitalized",
    }
    if completed_value:
        v = positive("completed_value", completed_value)
        out["ltv_on_completion_pct"] = pct(loan / v)
        if max_ltv_pct is not None:
            out["ltv_ok"] = loan / v <= ratio("max_ltv_pct", max_ltv_pct) / 100 + 1e-9
    if include_rows:
        out["draws"] = res["rows"]
    out["sources"] = SOURCES
    out["assumptions"] = [
        f"basic holdback {holdback_pct:g}% on hard costs only (soft costs are not improvements supplied under a contract)",
        f"completion release {release_lag_months} months after last hard-cost month stands in for the lien period",
        f"annual release modelled at anniversary + {ANNUAL_RELEASE_LAG_MONTHS} months (14-day notice + 60-74 days)",
        f"max LTC {max_ltc_pct:g}% (default 75% is a typical conventional screen, not a rule)",
        "equity funds land, fee and costs first; the loan funds the rest and its own interest",
    ]
    out["engine"] = "commercial.construction"
    return out
