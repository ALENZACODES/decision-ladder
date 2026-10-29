"""Blend-and-extend, blend-and-increase and port-and-increase, against breaking and refinancing.

Blending method used here (one formula, two special cases)::

    blended rate = sum(amount_k x months_k x rate_k) / sum(amount_k x months_k)

* the existing balance earns the OLD rate for the months left on the current term;
* the existing balance earns the NEW rate for any months added to the term (blend-and-extend);
* new funds earn the NEW rate for the whole (new) term (blend-and-increase, port-and-increase).

So blend-and-extend weights by remaining term, blend-and-increase weights by amount, and doing both weights
by amount x time. This is the common textbook blend; a lender may price the blend differently (for example
by folding the IRD into the rate) and the lender's written blended-rate quote governs.

Options are compared over a common horizon (default: the new term). An option whose term ends before the
horizon is assumed to renew at ``renewal_rate`` (default: the new rate) for the rest of it. The cost of an
option is everything the borrower pays plus the balance still owed at the horizon, less the money borrowed::

    cost = regular payments + cash paid up front (penalty, fees) + balance at horizon - (balance + new funds)

which is interest plus up-front cash, and treats a penalty added to the loan correctly (it shows up in the
balance at the horizon and in the extra interest). Break-and-refinance penalties come from the repo's
Decimal penalty engine via :func:`.prepayment.penalty_for`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..penalty.daycount import add_months
from . import frequency as F
from .prepayment import PenaltyTerms, penalty_for
from .schedule import LoanSpec, build

BLEND_METHOD = ("amount-and-time weighted average: sum(amount x months x rate) / sum(amount x months); existing balance "
                "at the old rate for the months left on the term, at the new rate for added months; new funds at the "
                "new rate for the whole new term")
REFI_MAX_LTV = 80.0   # legal maximum LTV for uninsured lending by federally regulated lenders (see heloc.OSFI_SOURCE)


@dataclass
class Current:
    balance: float
    rate: float
    remaining_term_months: int
    remaining_amort_years: float
    as_of: date
    rate_type: str = "fixed"
    frequency: str = "monthly"

    def __post_init__(self):
        if self.balance <= 0 or self.remaining_term_months <= 0 or self.remaining_amort_years <= 0:
            raise ValueError("balance, remaining term and remaining amortization must be positive")
        if self.remaining_amort_years * 12 < self.remaining_term_months:
            raise ValueError("remaining amortization cannot be shorter than the remaining term")

    @property
    def maturity(self) -> date:
        return add_months(self.as_of, self.remaining_term_months)


def blended_rate(balance: float, old_rate: float, remaining_months: int, new_rate: float, new_term_months: int,
                 new_funds: float = 0.0) -> dict:
    """Blended rate by amount and time, with the share of weight carried by each piece."""
    if new_term_months < remaining_months:
        raise ValueError("the new term cannot be shorter than the months left on the current term")
    if new_funds < 0:
        raise ValueError("new_funds cannot be negative")
    w_old = balance * remaining_months
    w_ext = balance * (new_term_months - remaining_months)
    w_new = new_funds * new_term_months
    total = w_old + w_ext + w_new
    rate = (old_rate * w_old + new_rate * (w_ext + w_new)) / total
    return {"rate": round(rate, 4), "method": BLEND_METHOD,
            "weights": {"old_rate_share": round(w_old / total, 4), "added_months_share": round(w_ext / total, 4),
                        "new_funds_share": round(w_new / total, 4)}}


def _cost(label: str, cur: Current, principal: float, rate: float, term_months: int, amort_years: float,
          horizon: int, renewal_rate: float, upfront: float, debt: float, **extra) -> dict:
    """Run one option through the schedule engine over the horizon."""
    first = F.first_payment_after(cur.as_of, cur.frequency)
    changes = [(add_months(cur.as_of, term_months), renewal_rate)] if term_months < horizon else []
    sch = build(LoanSpec(principal, rate, amort_years, first, cur.frequency, "fixed", changes, term_months=horizon))
    s = sch.summary()
    cost = s["total_regular_paid"] + upfront + sch.end_balance - debt
    return {"option": label, "rate": round(rate, 4), "principal": round(principal, 2), "term_months": term_months,
            "maturity_date": add_months(cur.as_of, term_months).isoformat(), "payment": s["initial_payment"],
            "renews_within_horizon_at": renewal_rate if changes else None,
            "interest_over_horizon": s["total_interest"], "balance_at_horizon": round(sch.end_balance, 2),
            "upfront_cash": round(upfront, 2), "cost_over_horizon": round(cost, 2), **extra}


def break_penalty(cur: Current, terms: PenaltyTerms, override: float | None) -> tuple[float, dict]:
    """Penalty to break today: caller's figure, the engine's estimate, or its three-month floor (flagged)."""
    if override is not None:
        return float(override), {"source": "caller supplied", "total_estimate": float(override)}
    p = penalty_for(cur.balance, cur.rate, cur.remaining_term_months, cur.rate_type, terms)
    if p["total_estimate"] is not None:
        return p["total_estimate"], p
    p["used_floor"] = True
    p["warnings"] = list(p["warnings"]) + ["Break cost uses the three-month-interest floor: a lower bound, not the penalty."]
    return p["three_month_interest"], p


def blend_vs_break(cur: Current, new_rate: float, new_term_months: int, *, new_funds: float = 0.0,
                   horizon_months: int | None = None, renewal_rate: float | None = None,
                   terms: PenaltyTerms | None = None, penalty_override: float | None = None,
                   refinance_costs: float = 0.0, capitalize_penalty: bool = False,
                   refinance_amort_years: float | None = None, property_value: float | None = None) -> dict:
    """Stay / blend-and-extend / blend-and-increase / break-and-refinance, ranked by cost over the horizon."""
    if new_term_months <= 0:
        raise ValueError("new_term_months must be positive")
    longest = max(new_term_months, cur.remaining_term_months)
    horizon = horizon_months or longest
    if horizon < longest:
        raise ValueError("horizon_months must cover the longest term compared")
    renew = new_rate if renewal_rate is None else renewal_rate
    debt = cur.balance + new_funds
    am = cur.remaining_amort_years
    opts = []
    if new_funds == 0:
        opts.append(_cost("stay to maturity", cur, cur.balance, cur.rate, cur.remaining_term_months, am, horizon,
                          renew, 0.0, debt))
    if new_term_months > cur.remaining_term_months:
        b = blended_rate(cur.balance, cur.rate, cur.remaining_term_months, new_rate, new_term_months, new_funds)
        opts.append(_cost("blend and extend" + (" with new funds" if new_funds else ""), cur, debt, b["rate"],
                          new_term_months, am, horizon, renew, 0.0, debt, blend=b))
    if new_funds > 0:
        b = blended_rate(cur.balance, cur.rate, cur.remaining_term_months, new_rate, cur.remaining_term_months, new_funds)
        opts.append(_cost("blend and increase (same maturity)", cur, debt, b["rate"], cur.remaining_term_months, am,
                          horizon, renew, 0.0, debt, blend=b))
    pen, pen_detail = break_penalty(cur, terms or PenaltyTerms(), penalty_override)
    principal = debt + (pen if capitalize_penalty else 0.0)
    upfront = refinance_costs + (0.0 if capitalize_penalty else pen)
    opts.append(_cost("break and refinance", cur, principal, new_rate, new_term_months, refinance_amort_years or am,
                      horizon, renew, upfront, debt, penalty=pen_detail, penalty_added_to_loan=capitalize_penalty))
    opts.sort(key=lambda o: o["cost_over_horizon"])
    for o in opts:
        o["extra_cost_vs_best"] = round(o["cost_over_horizon"] - opts[0]["cost_over_horizon"], 2)
    flags = []
    if pen_detail.get("used_floor"):
        flags.append("penalty is the three-month floor; supply comparison_posted_rate and method to price the IRD")
    if property_value:
        ltv = principal / property_value * 100
        if ltv > REFI_MAX_LTV:
            flags.append(f"refinance at {ltv:.1f}% LTV exceeds the {REFI_MAX_LTV:.0f}% uninsured maximum")
    return {"as_of": cur.as_of.isoformat(), "horizon_months": horizon, "renewal_rate_assumed": renew,
            "options": opts, "best": opts[0]["option"], "flags": flags, "blend_method": BLEND_METHOD,
            "cost_definition": "regular payments + up-front cash + balance at horizon - (balance + new funds)"}


def port_and_increase(cur: Current, new_funds: float, new_rate: float, *, new_term_months: int | None = None,
                      new_amort_years: float | None = None, sale_closing: date | None = None,
                      purchase_closing: date | None = None, port_window_days: int | None = None,
                      purchase_price: float | None = None, terms: PenaltyTerms | None = None) -> dict:
    """Port the existing mortgage to a new home and add funds at a blended rate."""
    if new_funds < 0:
        raise ValueError("new_funds cannot be negative")
    term = new_term_months or cur.remaining_term_months
    b = blended_rate(cur.balance, cur.rate, cur.remaining_term_months, new_rate, term, new_funds)
    amount = cur.balance + new_funds
    amort = new_amort_years or cur.remaining_amort_years
    comp = F.compounding_for(cur.rate_type)
    old_pmt = F.regular_payment(cur.balance, cur.rate, cur.remaining_amort_years, cur.frequency, comp)
    new_pmt = F.regular_payment(amount, b["rate"], amort, cur.frequency, comp)
    flags = []
    out = {"ported_balance": round(cur.balance, 2), "new_funds": round(new_funds, 2), "new_mortgage": round(amount, 2),
           "blend": b, "term_months": term, "maturity_date": add_months(cur.as_of, term).isoformat(),
           "amort_years": amort, "payment_before": round(old_pmt, 2), "payment_after": round(new_pmt, 2),
           "payment_change": round(new_pmt - old_pmt, 2)}
    if sale_closing and purchase_closing:
        gap = (purchase_closing - sale_closing).days
        out["closing_gap_days"] = gap
        if gap < 0:
            flags.append("purchase closes before the sale: the new funds and a bridge loan must cover the overlap")
        if port_window_days is not None and gap > port_window_days:
            flags.append(f"purchase closes {gap} days after the sale, past the {port_window_days}-day port window: "
                         "the penalty is usually charged and refunded only if the lender agrees")
    if purchase_price:
        ltv = amount / purchase_price * 100
        out["ltv_on_purchase"] = round(ltv, 2)
        if ltv > 80:
            flags.append("over 80% LTV: the ported mortgage would need default insurance, if the file is insurable")
    pen, detail = break_penalty(cur, terms or PenaltyTerms(), None)
    out["penalty_avoided_by_porting"] = {"amount": round(pen, 2), **detail}
    out["flags"] = flags
    out["method"] = ("Port-and-increase: blended rate on the combined mortgage using " + BLEND_METHOD +
                     ". Portability, window length and qualification on the new amount are lender terms.")
    return out
