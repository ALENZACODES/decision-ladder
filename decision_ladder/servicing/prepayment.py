"""Prepayment privileges: lump sums, payment increases and double-ups, checked against the contract.

Typical closed Canadian mortgages let the borrower, without penalty, in each privilege year:

* prepay a lump sum of up to ``lump_sum_pct`` of the ORIGINAL principal (10-20% is common);
* raise the regular payment by up to ``payment_increase_pct`` of the ORIGINAL payment (10-100%);
* make a double-up payment on any regular payment date (some lenders count it toward the lump-sum limit).

The privilege year runs from the funding date and each anniversary (``year_basis='anniversary'``) or by
calendar year (``'calendar'``). The exact limits, whether unused room carries forward (this model assumes it
does not) and whether double-ups count toward the lump-sum limit are contract terms the caller supplies.

A lump sum above the year's remaining room is an *overage*. Each overage is priced with the repo's Decimal
penalty engine (``penalty.engine.calculate_penalty``) with ``payout_amount`` set to the overage, so the
three-month-interest floor and the IRD are charged on the excess only. A fixed-rate overage needs a
comparison rate to price the IRD; without one the engine returns the three-month floor and says so.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from ..penalty.daycount import MonthRounding, add_months, remaining_term
from ..penalty.engine import calculate_penalty
from ..penalty.models import Method, PenaltyInputs
from .schedule import Events, LoanSpec, Schedule, build


@dataclass
class Privileges:
    lump_sum_pct: float = 15.0
    payment_increase_pct: float = 15.0
    double_up: bool = True
    double_up_counts_toward_lump: bool = False
    year_basis: str = "anniversary"

    def __post_init__(self):
        if not (0 <= self.lump_sum_pct <= 100 and 0 <= self.payment_increase_pct <= 100):
            raise ValueError("privilege percentages must be 0..100")
        if self.year_basis not in ("anniversary", "calendar"):
            raise ValueError("year_basis must be 'anniversary' or 'calendar'")

    def as_dict(self) -> dict:
        return dict(vars(self))


@dataclass
class PenaltyTerms:
    """What the penalty engine needs to price an overage."""
    lender: str = "generic"
    comparison_posted_rate: float | None = None
    documented_discount: float | None = None
    is_open: bool = False
    method: str | None = None    # explicit IRD family, e.g. 'simple_differential' (see penalty.models.Method)
    remaining_amortization_months: int | None = None   # needed only by the present-value family


def _dec(x: float | None) -> Decimal | None:
    return None if x is None else Decimal(str(round(x, 4)))


def penalty_for(balance: float, rate: float, remaining_months: int, rate_type: str, terms: PenaltyTerms,
                payout_amount: float | None = None) -> dict:
    """Run the repo's Decimal penalty engine and return its result as plain JSON values."""
    res = calculate_penalty(PenaltyInputs(
        balance=_dec(round(balance, 2)), annual_rate=_dec(rate), remaining_months=max(0, min(360, remaining_months)),
        lender=terms.lender, rate_type=rate_type, is_open=terms.is_open,  # type: ignore[arg-type]
        payout_amount=None if payout_amount is None else _dec(round(min(payout_amount, balance), 2)),
        comparison_posted_rate=_dec(terms.comparison_posted_rate), documented_discount=_dec(terms.documented_discount),
        remaining_amortization_months=terms.remaining_amortization_months,
        explicit_method=Method(terms.method) if terms.method else None, comparison_rate_source="caller supplied"))
    d = res.as_dict()
    return {"status": d["status"], "method": d["method"], "controlling_method": d["controlling_method"],
            "three_month_interest": float(d["three_month_interest"]),
            "ird": None if d["interest_rate_differential"] is None else float(d["interest_rate_differential"]),
            "total_estimate": None if d["total_estimate"] is None else float(d["total_estimate"]),
            "missing_fields": d["missing_fields"], "warnings": d["warnings"], "source_url": d["source_url"],
            "engine": "penalty.engine.calculate_penalty"}


def privilege_year(funding: date, day: date, basis: str) -> tuple[int, date, date]:
    """(index, start, end) of the privilege year containing ``day``; index 0 is the first year."""
    if basis == "calendar":
        return day.year - funding.year, date(day.year, 1, 1), date(day.year, 12, 31)
    k = day.year - funding.year
    if add_months(funding, 12 * k) > day:
        k -= 1
    return k, add_months(funding, 12 * k), add_months(funding, 12 * (k + 1))


def _years_months(periods: int, per_year: int) -> dict:
    months = round(periods * 12 / per_year)
    return {"payments": periods, "years": months // 12, "months": months % 12}


def _price_overage(spec: LoanSpec, sched: Schedule, on: date, overage: float, terms: PenaltyTerms) -> dict:
    """Penalty on prepaying ``overage`` above the privilege on ``on`` (first payment date on/after it)."""
    row = next((r for r in sched.rows if r.date >= on), None)
    if row is None:
        return {"status": "after payoff", "total_estimate": None}
    if spec.maturity is None:
        return {"status": "no term given", "total_estimate": None,
                "note": "pass term_months so the remaining term (and so the IRD) can be measured"}
    balance_before = row.balance + row.prepayment
    months = remaining_term(row.date, spec.maturity, MonthRounding.UP).months
    out = penalty_for(balance_before, row.rate, months, spec.rate_type, terms, payout_amount=overage)
    out.update(remaining_months=months, balance_before=round(balance_before, 2))
    return out


def check_privileges(spec: LoanSpec, sched: Schedule, events: Events, priv: Privileges,
                     terms: PenaltyTerms) -> dict:
    """Per privilege year: lump sums used vs allowed, payment increases vs cap, overages priced."""
    allowance = spec.principal * priv.lump_sum_pct / 100
    base_pmt = spec.scheduled_payment()
    funding = spec.funding

    def on_payment(d: date):
        """The schedule row an event dated ``d`` lands on (None after payoff or maturity)."""
        return next((r for r in sched.rows if r.date >= d), None)

    counted: list[tuple[date, float, str]] = []
    for d, a in events.prepayments:
        row = on_payment(d)
        counted.append((row.date if row else d, a, "lump sum"))
    if priv.double_up_counts_toward_lump or not priv.double_up:
        for d in events.double_ups:          # the extra payment is the regular payment in effect that day
            row = on_payment(d)
            if row:
                counted.append((row.date, row.payment, "double-up"))
    years: dict[int, dict] = {}
    overages = []
    for d, amount, kind in sorted(counted):
        idx, start, end = privilege_year(funding, d, priv.year_basis)
        y = years.setdefault(idx, {"privilege_year": idx + 1, "start": start.isoformat(), "end": end.isoformat(),
                                   "allowed": round(allowance, 2), "used": 0.0, "over": 0.0})
        room = max(0.0, allowance - y["used"])
        y["used"] += amount
        over = max(0.0, amount - room)
        if over > 0.005:
            y["over"] += over
            overages.append({"date": d.isoformat(), "kind": kind, "amount": round(amount, 2),
                             "within_privilege": round(amount - over, 2), "overage": round(over, 2),
                             "penalty": _price_overage(spec, sched, d, over, terms)})
    for y in years.values():
        y["remaining_room"] = round(max(0.0, y["allowed"] - y["used"]), 2)
        y["used"], y["over"] = round(y["used"], 2), round(y["over"], 2)

    cap = base_pmt * (1 + priv.payment_increase_pct / 100)
    increases = [{"date": d.isoformat(), "new_payment": round(p, 2),
                  "increase_pct": round((p / base_pmt - 1) * 100, 2), "max_allowed_payment": round(cap, 2),
                  "within_privilege": p <= cap + 0.005} for d, p in events.payment_changes]
    flags = [f"lump-sum overage of ${o['overage']:,.2f} on {o['date']}" for o in overages]
    flags += [f"payment increase to ${i['new_payment']:,.2f} on {i['date']} exceeds the {priv.payment_increase_pct}% "
              "privilege; most lenders decline it rather than charge a penalty" for i in increases if not i["within_privilege"]]
    if events.double_ups and not priv.double_up:
        flags.append("double-ups are not a contract privilege here; they were counted toward the lump-sum limit")
    totals = [o["penalty"]["total_estimate"] for o in overages]
    priced = None if None in totals else round(sum(float(t) for t in totals), 2)
    return {"lump_sum_allowance_per_year": round(allowance, 2), "years": sorted(years.values(), key=lambda y: y["privilege_year"]),
            "payment_increases": increases, "overages": overages,
            "overage_penalty_total": priced,
            "within_privileges": not flags, "flags": flags}


def prepayment_plan(spec: LoanSpec, events: Events, priv: Privileges | None = None,
                    terms: PenaltyTerms | None = None, rows: bool = False) -> dict:
    """Schedule with and without the prepayments, savings, and a privilege check."""
    priv, terms = priv or Privileges(), terms or PenaltyTerms()
    base_spec = replace(spec, term_months=None)
    base, plan = build(base_spec), build(base_spec, events)
    termed = build(spec, events) if spec.term_months else plan
    termed_base = build(spec) if spec.term_months else base
    b, p = base.summary(), plan.summary()
    out = {
        "baseline": {k: b[k] for k in ("initial_payment", "payments_made", "payoff_date", "total_interest")},
        "with_prepayments": {k: p[k] for k in ("initial_payment", "final_regular_payment", "payments_made",
                                               "payoff_date", "total_interest", "total_prepayments")},
        "interest_saved": round(b["total_interest"] - p["total_interest"], 2),
        "time_saved": _years_months(b["payments_made"] - p["payments_made"], spec.freq.per_year),
        "privileges": priv.as_dict(),
        "privilege_check": check_privileges(spec, termed, events, priv, terms),
    }
    if spec.term_months:
        out["over_term"] = {"maturity_date": spec.maturity.isoformat(),
                            "interest_baseline": round(termed_base.total_interest, 2),
                            "interest_with_prepayments": round(termed.total_interest, 2),
                            "balance_at_maturity_baseline": round(termed_base.end_balance, 2),
                            "balance_at_maturity_with_prepayments": round(termed.end_balance, 2)}
    if rows:
        out["schedule"] = plan.as_dict(rows=True)
    return out
