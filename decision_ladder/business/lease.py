"""Equipment lease versus buy-with-a-loan: after-tax net present value with capital cost allowance (CCA).

Method (standard Canadian lease-or-buy analysis): both choices are discounted at the after-tax cost of
borrowing, because buying is assumed to be financed with debt and lease payments displace debt. Buying costs the
price up front, saves tax on CCA (declining balance; first-year factor per the half-year rule or the accelerated
investment incentive), and recovers the salvage value; leasing costs the after-tax lease payments.
"""
from __future__ import annotations

from datetime import date

from ..engines import payments
from . import cashflow as cf
from .params import CCA as P, assumptions, sources, val

AII_START = date(2018, 11, 21)   # AII applies to property acquired after 2018-11-20


def first_year_factor(acquired: str | None, available_for_use: str | None) -> dict:
    """First-year CCA as a multiple of (class rate x cost): 0.5 under the half-year rule, 1.0 or 1.5 under the
    accelerated investment incentive (AII) and its Bill C-15 reinstatement (RII), by acquisition and
    available-for-use dates (YYYY-MM-DD). Applies to classes normally subject to the half-year rule."""
    if not acquired or not available_for_use:
        return {"factor": 0.5, "rule": "half-year rule (dates not given)"}
    acq, avail = date.fromisoformat(acquired[:10]), date.fromisoformat(available_for_use[:10])
    if avail < acq:
        raise ValueError("property cannot be available for use before it is acquired")
    if acq.year >= 2025 and avail.year <= 2029:
        return {"factor": val(P, "rii_acquired_after_2024_available_before_2030"), "rule": "RII: acquired after 2024, available before 2030"}
    if acq.year >= 2025 and avail.year <= 2033:
        return {"factor": val(P, "rii_available_2030_2033"), "rule": "RII phase-out: available 2030-2033"}
    if acq >= AII_START and avail.year <= 2023:
        return {"factor": val(P, "aii_before_2024"), "rule": "AII: available for use before 2024"}
    if acq >= AII_START and avail.year <= 2027:
        return {"factor": val(P, "aii_2024_2027"), "rule": "AII phase-out: available 2024-2027"}
    return {"factor": 0.5, "rule": "half-year rule"}


def cca_schedule(cost: float, rate_pct: float, years: int, factor: float = 0.5) -> list[dict]:
    """Year-by-year CCA on one asset in its own class: year 1 = factor x rate x cost, then rate x opening UCC."""
    d = rate_pct / 100
    if not 0 < d <= 1 or factor * d > 1:
        raise ValueError("CCA rate must be in (0, 100%] and first-year CCA cannot exceed cost")
    ucc, rows = cost, []
    for t in range(1, years + 1):
        cca = ucc * d * (factor if t == 1 else 1.0)
        ucc -= cca
        rows.append({"year": t, "cca": cca, "closing_ucc": ucc})
    return rows


def pv_cca_shield(cost: float, rate_pct: float, tax_rate_pct: float, k: float, years: int, salvage: float = 0.0,
                  factor: float = 0.5) -> dict:
    """PV of CCA tax savings over ``years`` (year-end), salvage deducted from the pool at year ``years``, and the
    remaining pool written off as a perpetual declining balance: PV_N = UCC x d x T / (d + k)."""
    d, T = rate_pct / 100, tax_rate_pct / 100
    rows = cca_schedule(cost, rate_pct, years, factor)
    pv = sum(r["cca"] * T / (1 + k) ** r["year"] for r in rows)
    pool = rows[-1]["closing_ucc"] - salvage
    recapture = 0.0
    if pool < 0:   # salvage above the pool: recaptured CCA is taxed at year N, pool closes at zero
        recapture, pool = -pool, 0.0
    pv_tail = (pool * d * T / (d + k) - recapture * T) / (1 + k) ** years
    return {"pv": pv + pv_tail, "pv_within_term": pv, "pv_after_term": pv_tail, "ucc_after_salvage": pool,
            "recapture": recapture, "schedule": rows}


def lease_vs_buy(cost: float, lease_payment: float, lease_term_years: int, borrow_rate_pct: float, tax_rate_pct: float,
                 cca_rate_pct: float, salvage_value: float = 0.0, lease_payments_per_year: int = 12,
                 lease_in_advance: bool = True, lease_upfront_fees: float = 0.0, buy_annual_operating_cost: float = 0.0,
                 first_year_factor_override: float | None = None, acquired: str | None = None,
                 available_for_use: str | None = None) -> dict:
    """Net advantage to leasing (NAL) = PV cost of buying - PV cost of leasing; positive means lease.

    ``borrow_rate_pct`` is the pre-tax loan rate (nominal, compounded at the lease payment frequency).
    ``buy_annual_operating_cost`` is any cost the owner pays that the lease includes (e.g. maintenance), year-end.
    Lease payments are deductible when paid; the lessee is assumed not to keep the asset at the end.
    """
    if cost <= 0 or lease_payment <= 0 or lease_term_years <= 0 or not 0 <= tax_rate_pct < 100:
        raise ValueError("cost, lease payment and term must be positive; tax rate in [0, 100)")
    m, T = int(lease_payments_per_year), tax_rate_pct / 100
    i = borrow_rate_pct / 100 / m * (1 - T)             # after-tax rate per lease period
    k = cf.ear_from_periodic(i, m)                       # after-tax effective annual rate
    n = lease_term_years * m
    pv_lease = cf.annuity_pv(lease_payment * (1 - T), i, n, due=lease_in_advance) + lease_upfront_fees * (1 - T)
    fy = ({"factor": first_year_factor_override, "rule": "override"} if first_year_factor_override is not None
          else first_year_factor(acquired, available_for_use))
    shield = pv_cca_shield(cost, cca_rate_pct, tax_rate_pct, k, lease_term_years, salvage_value, fy["factor"])
    pv_salvage = salvage_value / (1 + k) ** lease_term_years
    pv_opex = cf.annuity_pv(buy_annual_operating_cost * (1 - T), k, lease_term_years)
    pv_buy = cost - shield["pv"] - pv_salvage + pv_opex
    nal = pv_buy - pv_lease
    # lease payment at which the two are equal (break-even), from the same annuity factor
    be = (pv_buy - lease_upfront_fees * (1 - T)) / ((1 - T) * cf.annuity_pv(1.0, i, n, due=lease_in_advance))
    return {"decision": "lease" if nal > 0 else "buy" if nal < 0 else "indifferent",
            "net_advantage_to_leasing": round(nal, 2), "pv_cost_lease": round(pv_lease, 2), "pv_cost_buy": round(pv_buy, 2),
            "buy_components": {"price": cost, "pv_cca_tax_shield": round(shield["pv"], 2),
                               "pv_salvage": round(pv_salvage, 2), "pv_after_tax_operating_cost": round(pv_opex, 2),
                               "recapture": round(shield["recapture"], 2)},
            "breakeven_lease_payment": round(be, 2), "after_tax_discount_rate_pct": round(k * 100, 4),
            "first_year_cca": fy, "loan_payment_if_buying": round(
                payments.payment(cost, borrow_rate_pct, lease_term_years, "monthly"), 2) if m == 12 else None,
            "cca_schedule": [{"year": r["year"], "cca": round(r["cca"], 2), "tax_saving": round(r["cca"] * T, 2),
                              "closing_ucc": round(r["closing_ucc"], 2)} for r in shield["schedule"]],
            "engine": "business.lease.lease_vs_buy", "source": sources(P),
            "assumptions": assumptions("half_year_rule_default", "cca_pool_continues")}
