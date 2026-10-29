"""Dated amortization schedules for Canadian mortgages.

One engine covers every servicing question in this package:

* all six Canadian payment frequencies (see :mod:`.frequency`), each payment on a real calendar date;
* fixed rates (semi-annual compounding) and variable rates (monthly compounding);
* mid-term rate changes given as ``(effective_date, rate)``. Interest for a period that straddles a change
  is split by days: ``growth = prod((1 + i_k) ** (days_k / days_in_period))``;
* payment resets. A fixed-rate mortgage (renewal) and an *adjustable*-payment variable mortgage re-amortize
  over the remaining amortization from the first payment on or after the change. A *fixed*-payment
  variable mortgage keeps its payment, so a higher rate shifts the split toward interest;
* the **trigger rate** (the rate at which the fixed payment only covers interest) and the **trigger point**
  (the balance, as a percent of the original principal, at which the lender acts). Past the trigger rate
  unpaid interest is added to the balance (negative amortization);
* prepayment events, payment changes, double-ups and skipped payments, used by the prepayment, blend and
  deferral modules.

Events dated between two payments apply on the next payment date. Money is carried unrounded and rounded
to cents only in output.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date

from ..penalty.daycount import add_months
from . import frequency as F

MAX_YEARS = 100   # stop a schedule that never amortizes


@dataclass
class LoanSpec:
    principal: float
    annual_rate: float
    amort_years: float
    first_payment: date
    frequency: str = "monthly"
    rate_type: str = "fixed"
    rate_changes: list[tuple[date, float]] = field(default_factory=list)
    variable_payment: str = "fixed"       # 'fixed' (payment held) or 'adjustable' (re-amortized at each change)
    term_months: int | None = None        # stop at term maturity; None = run to payoff
    payment: float | None = None          # override the computed regular payment
    trigger_point_pct: float = 100.0      # balance as % of original principal at which the lender acts
    on_trigger_point: str = "flag"        # 'flag' or 'reset' (payment re-amortized over remaining amortization)

    def __post_init__(self):
        if self.principal <= 0 or self.amort_years <= 0:
            raise ValueError("principal and amortization must be positive")
        if not 0 <= self.annual_rate <= 30:
            raise ValueError("annual_rate must be a percentage from 0 to 30")
        if self.variable_payment not in ("fixed", "adjustable"):
            raise ValueError("variable_payment must be 'fixed' or 'adjustable'")
        if self.on_trigger_point not in ("flag", "reset"):
            raise ValueError("on_trigger_point must be 'flag' or 'reset'")
        if self.term_months is not None and self.term_months <= 0:
            raise ValueError("term_months must be positive")
        F.get(self.frequency)
        F.compounding_for(self.rate_type)
        self.rate_changes = sorted((d, float(r)) for d, r in self.rate_changes)

    @property
    def freq(self) -> F.Frequency:
        return F.get(self.frequency)

    @property
    def compounding(self) -> str:
        return F.compounding_for(self.rate_type)

    @property
    def funding(self) -> date:
        return F.payment_date(self.first_payment, self.frequency, -1)

    @property
    def maturity(self) -> date | None:
        return add_months(self.funding, self.term_months) if self.term_months else None

    def rate_on(self, day: date) -> float:
        """Contract rate in effect on ``day``."""
        idx = bisect_right([d for d, _ in self.rate_changes], day)
        return self.rate_changes[idx - 1][1] if idx else self.annual_rate

    def scheduled_payment(self) -> float:
        if self.payment is not None:
            if self.payment <= 0:
                raise ValueError("payment must be positive")
            return self.payment
        return F.regular_payment(self.principal, self.annual_rate, self.amort_years, self.frequency, self.compounding)

    def period_growth(self, start: date, end: date) -> tuple[float, float]:
        """Growth factor of the balance from ``start`` to ``end`` and the rate in effect at the end."""
        cuts = [start] + [d for d, _ in self.rate_changes if start < d < end] + [end]
        total = (end - start).days
        g = 1.0
        for a, b in zip(cuts, cuts[1:]):
            g *= (1 + F.periodic_rate(self.rate_on(a), self.freq.per_year, self.compounding)) ** ((b - a).days / total)
        return g, self.rate_on(cuts[-2])


@dataclass
class Events:
    """Borrower actions keyed by date; each applies on the first payment date on or after it."""
    prepayments: list[tuple[date, float]] = field(default_factory=list)
    payment_changes: list[tuple[date, float]] = field(default_factory=list)   # new regular payment from then on
    double_ups: list[date] = field(default_factory=list)
    skips: list[date] = field(default_factory=list)

    def __post_init__(self):
        self.prepayments = sorted(self.prepayments)
        self.payment_changes = sorted(self.payment_changes)
        self.double_ups = sorted(self.double_ups)
        self.skips = sorted(self.skips)

    def due(self, upto: date, seen: dict) -> dict:
        """Events dated on or before ``upto`` not yet applied (``seen`` holds a cursor per list)."""
        out = {}
        for name in ("prepayments", "payment_changes", "double_ups", "skips"):
            items = getattr(self, name)
            i = j = seen.get(name, 0)
            while j < len(items) and (items[j][0] if isinstance(items[j], tuple) else items[j]) <= upto:
                j += 1
            seen[name] = j
            out[name] = items[i:j]
        return out


@dataclass
class Row:
    n: int
    date: date
    rate: float
    payment: float      # scheduled regular payment for the period
    paid: float         # amount actually paid on the regular payment (0 when skipped, 2x on a double-up)
    interest: float
    principal: float    # negative when interest exceeds the payment
    prepayment: float
    balance: float
    flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"n": self.n, "date": self.date.isoformat(), "rate": round(self.rate, 4),
                "payment": round(self.payment, 2), "paid": round(self.paid, 2), "interest": round(self.interest, 2),
                "principal": round(self.principal, 2), "prepayment": round(self.prepayment, 2),
                "balance": round(self.balance, 2), "flags": self.flags}


def trigger_rate(balance: float, payment: float, frequency: str, compounding: str = "monthly") -> float:
    """Annual rate (percent) at which one period's interest on ``balance`` equals ``payment``."""
    if balance <= 0 or payment <= 0:
        raise ValueError("balance and payment must be positive")
    return F.annual_from_periodic(payment / balance, F.get(frequency).per_year, compounding)


@dataclass
class Schedule:
    spec: LoanSpec
    rows: list[Row]
    initial_payment: float
    final_payment: float
    resets: list[dict]
    first_trigger_rate_date: date | None
    first_trigger_point_date: date | None

    @property
    def end_balance(self) -> float:
        return self.rows[-1].balance if self.rows else self.spec.principal

    @property
    def paid_off(self) -> bool:
        return self.end_balance <= 0.005

    @property
    def total_interest(self) -> float:
        return sum(r.interest for r in self.rows)

    def balance_on(self, day: date) -> float:
        """Balance after the last payment on or before ``day``."""
        bal = self.spec.principal
        for r in self.rows:
            if r.date > day:
                break
            bal = r.balance
        return bal

    def interest_between(self, start: date, end: date) -> float:
        return sum(r.interest for r in self.rows if start < r.date <= end)

    def yearly(self) -> list[dict]:
        """Calendar-year totals: compact enough for summaries and charts."""
        out: dict[int, dict] = {}
        for r in self.rows:
            y = out.setdefault(r.date.year, {"year": r.date.year, "payments": 0, "paid": 0.0, "interest": 0.0,
                                             "principal": 0.0, "prepayment": 0.0, "end_balance": 0.0})
            y["payments"] += 1
            y["paid"] += r.paid
            y["interest"] += r.interest
            y["principal"] += r.principal
            y["prepayment"] += r.prepayment
            y["end_balance"] = r.balance
        return [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in y.items()} for y in out.values()]

    def summary(self) -> dict:
        s, rows = self.spec, self.rows
        f = s.freq
        payoff = rows[-1].date if rows and self.paid_off else None
        out = {
            "frequency": f.key, "frequency_label": f.label, "payments_per_year": f.per_year,
            "rate_type": s.rate_type,
            "compounding": "semi-annual (fixed, Interest Act s.6)" if s.compounding == "semi" else "monthly (variable)",
            "principal": round(s.principal, 2), "initial_rate": s.annual_rate,
            "initial_payment": round(self.initial_payment, 2), "final_regular_payment": round(self.final_payment, 2),
            "funding_date": s.funding.isoformat(), "first_payment_date": s.first_payment.isoformat(),
            "last_payment_date": rows[-1].date.isoformat() if rows else None,
            "maturity_date": s.maturity.isoformat() if s.maturity else None,
            "payments_made": len(rows), "payments_skipped": sum(1 for r in rows if "skipped" in r.flags),
            "total_interest": round(self.total_interest, 2),
            "total_regular_paid": round(sum(r.paid for r in rows), 2),
            "total_prepayments": round(sum(r.prepayment for r in rows), 2),
            "total_principal_repaid": round(sum(r.principal + r.prepayment for r in rows), 2),
            "end_balance": round(max(0.0, self.end_balance), 2),
            "paid_off": self.paid_off, "payoff_date": payoff.isoformat() if payoff else None,
            "years_to_payoff": round((payoff - s.funding).days / 365.25, 2) if payoff else None,
            "does_not_amortize": not self.paid_off and s.term_months is None,
            "payment_resets": self.resets,
        }
        if s.rate_type == "variable":
            out["trigger"] = {
                "trigger_rate_at_start": round(trigger_rate(s.principal, self.initial_payment, f.key), 4),
                "first_date_rate_above_trigger": _iso(self.first_trigger_rate_date),
                "trigger_point_pct_of_original": s.trigger_point_pct,
                "trigger_point_balance": round(s.principal * s.trigger_point_pct / 100, 2),
                "first_date_trigger_point_reached": _iso(self.first_trigger_point_date),
                "max_balance": round(max([s.principal] + [r.balance for r in rows]), 2),
                "rule": ("Trigger rate: periodic interest equals the fixed payment, so no principal is repaid. Trigger "
                         "point: the balance reaches the stated percent of the original principal; the lender's "
                         "contract decides what happens then (this model either flags it or re-amortizes)."),
            }
        return out

    def as_dict(self, rows: bool = False) -> dict:
        out = {"summary": self.summary(), "yearly": self.yearly()}
        if rows:
            out["rows"] = [r.as_dict() for r in self.rows]
        return out


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def build(spec: LoanSpec, events: Events | None = None) -> Schedule:
    """Run the schedule to payoff, to term maturity, or to the 100-year guard."""
    events = events or Events()
    f, comp = spec.freq, spec.compounding
    pmt = spec.scheduled_payment()
    initial = pmt
    pmt_rate = spec.annual_rate
    recompute_on_change = spec.rate_type == "fixed" or spec.variable_payment == "adjustable"
    trigger_bal = spec.principal * spec.trigger_point_pct / 100
    bal = spec.principal
    rows: list[Row] = []
    resets: list[dict] = []
    seen: dict = {}
    first_trig_rate = first_trig_point = None
    maturity = spec.maturity
    k = 0
    while bal > 0.005 and k < f.per_year * MAX_YEARS:
        d = F.payment_date(spec.first_payment, spec.frequency, k)
        if maturity and d > maturity:
            break
        prev = F.payment_date(spec.first_payment, spec.frequency, k - 1)
        growth, rate = spec.period_growth(prev, d)
        remaining_years = max(1 / f.per_year, spec.amort_years - k / f.per_year)
        if rate != pmt_rate and recompute_on_change:
            pmt = F.regular_payment(bal, rate, remaining_years, spec.frequency, comp)
            resets.append({"date": d.isoformat(), "rate": rate, "new_payment": round(pmt, 2), "reason": "rate change"})
        pmt_rate = rate
        ev = events.due(d, seen)
        for _, new_pmt in ev["payment_changes"]:
            if new_pmt <= 0:
                raise ValueError("a changed payment must be positive")
            pmt = float(new_pmt)
        interest = bal * (growth - 1)
        flags = []
        if ev["skips"]:
            due, flags = 0.0, ["skipped"]
        else:
            due = pmt * (1 + len(ev["double_ups"]))
            if ev["double_ups"]:
                flags.append("double-up")
        paid = min(due, bal + interest)
        bal = bal + interest - paid
        prepay = min(sum(a for _, a in ev["prepayments"]), bal)
        if prepay < 0:
            raise ValueError("prepayments must be positive")
        bal -= prepay
        if bal < 0.005:
            bal = 0.0
        if interest > pmt and not ev["skips"]:
            flags.append("rate above trigger rate")
            first_trig_rate = first_trig_rate or d
        if bal > trigger_bal + 0.005:
            flags.append("trigger point reached")
            first_trig_point = first_trig_point or d
            if spec.on_trigger_point == "reset":
                new = F.regular_payment(bal, rate, max(1 / f.per_year, remaining_years - 1 / f.per_year),
                                        spec.frequency, comp)
                if new > pmt:
                    pmt = new
                    resets.append({"date": d.isoformat(), "rate": rate, "new_payment": round(pmt, 2),
                                   "reason": "trigger point"})
        rows.append(Row(k + 1, d, rate, pmt, paid, interest, paid - interest, prepay, bal, flags))
        k += 1
    return Schedule(spec, rows, initial, pmt, resets, first_trig_rate, first_trig_point)


def compare_frequencies(principal: float, annual_rate: float, amort_years: float, funding: date,
                        rate_type: str = "fixed") -> list[dict]:
    """Every frequency funded on the same day and run to payoff: payment, payoff date, interest vs monthly."""
    out = []
    for key in F.FREQUENCIES:
        s = build(LoanSpec(principal, annual_rate, amort_years, F.first_payment_after(funding, key), key,
                           rate_type)).summary()
        out.append({"frequency": key, "label": s["frequency_label"], "payment": s["initial_payment"],
                    "annual_outlay": round(s["initial_payment"] * s["payments_per_year"], 2),
                    "payments": s["payments_made"], "payoff_date": s["payoff_date"],
                    "years_to_payoff": s["years_to_payoff"], "total_interest": s["total_interest"]})
    base = out[0]["total_interest"]
    for r in out:
        r["interest_saved_vs_monthly"] = round(base - r["total_interest"], 2)
    return out
