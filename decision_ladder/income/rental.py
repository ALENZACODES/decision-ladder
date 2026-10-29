"""Rental income treatment: add-back, offset and net-rental, each producing GDS and TDS for the same file.

* **add-back**: a percent of gross rent is added to income; each rental's full PITH is a TDS liability.
* **offset**: a percent of gross rent is netted against that property's PITH; a shortfall is a TDS liability
  (a surplus is ignored unless the lender adds it to income).
* **net-rental**: T776 net rent plus CCA (and mortgage interest, since P&I is counted in TDS) is added to income;
  each rental's P&I is a TDS liability. Without a T776, a pro forma net is built from rent less taxes, heat,
  condo fees and other expenses.

Owner-occupied properties count in GDS. Their suite rent is added back under the add-back and net-rental
methods (CMHC treats owner-occupied rent as gross, investment properties as net) and offsets the housing cost
under the offset method. A *new* mortgage is stress-tested at the B-20 qualifying rate; existing mortgages
use the actual payment.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

from ..engines import payments, qualify
from . import params as P

METHODS = ("add_back", "offset", "net_rental")
CONDO_SHARE = P.VERIFIED["condo_fee_pct"]["value"] / 100
POLICY_KEYS = {"add_back": ("addback_pct", "addback_excludes_tax_heat"),
               "offset": ("offset_pct", "offset_surplus_to_income"),
               "net_rental": ("net_rental_add_back_interest", "addback_pct")}


@dataclass
class Property:
    name: str = "property"
    value: float = 0.0
    balance: float = 0.0
    rate: float = 0.0                       # contract rate, percent
    amort_years: float = 25.0               # remaining amortization
    rent_monthly: float = 0.0               # gross rent
    taxes_annual: float = 0.0
    heat_annual: float = 0.0                # 0 when the tenant pays heat
    condo_fees_monthly: float = 0.0
    other_expenses_annual: float = 0.0      # insurance, repairs, management
    owner_occupied: bool = False
    new_mortgage: bool = False              # stress-test at the qualifying rate
    payment_monthly: float | None = None    # actual P&I if known
    t776_net_income: float | None = None
    cca_claimed: float = 0.0
    mortgage_interest_annual: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Property":
        names = {f.name for f in fields(cls)}
        bad = set(d) - names
        if bad:
            raise ValueError(f"unknown property fields: {sorted(bad)}")
        p = cls(**{k: v for k, v in d.items() if v is not None})
        if p.balance < 0 or p.rent_monthly < 0 or p.value < 0:
            raise ValueError(f"{p.name}: value, balance and rent must be >= 0")
        return p

    def pi_monthly(self) -> float:
        if self.payment_monthly is not None:
            return float(self.payment_monthly)
        if self.balance <= 0:
            return 0.0
        r = qualify.qualifying_rate(self.rate) if self.new_mortgage else self.rate
        return payments.payment(self.balance, r, self.amort_years)

    def tax_heat_condo_monthly(self) -> float:
        return self.taxes_annual / 12 + self.heat_annual / 12 + CONDO_SHARE * self.condo_fees_monthly

    def pith_monthly(self) -> float:
        return self.pi_monthly() + self.tax_heat_condo_monthly()

    def interest_year1(self) -> float:
        """Interest paid in the next 12 months at the contract rate (what a T776 deducts)."""
        if self.mortgage_interest_annual is not None:
            return float(self.mortgage_interest_annual)
        if self.balance <= 0:
            return 0.0
        pmt = payments.payment(self.balance, self.rate, self.amort_years)
        return 12 * pmt - (self.balance - payments.balance_after(self.balance, self.rate, self.amort_years, 12))

    def net_rent_annual(self, add_back_interest: bool) -> float:
        """T776 net plus CCA (plus interest), or a pro forma net when no T776 is on file."""
        interest = self.interest_year1()
        if self.t776_net_income is not None:
            return self.t776_net_income + self.cca_claimed + (interest if add_back_interest else 0.0)
        before_interest = (12 * self.rent_monthly - self.taxes_annual - self.heat_annual
                           - 12 * self.condo_fees_monthly - self.other_expenses_annual)
        return before_interest - (0.0 if add_back_interest else interest)


def as_properties(items) -> list[Property]:
    return [p if isinstance(p, Property) else Property.from_dict(p) for p in (items or [])]


def _treat(p: Property, method: str, pol: dict) -> dict:
    """One property's effect: income added (annual), GDS housing and TDS liability (monthly)."""
    rent12, add_pct = 12 * p.rent_monthly, pol["addback_pct"] / 100
    if p.owner_occupied:
        if method == "offset":
            housing = max(0.0, p.pith_monthly() - pol["offset_pct"] / 100 * p.rent_monthly)
            return {"income": 0.0, "gds": housing, "tds": 0.0,
                    "treatment": f"PITH less {pol['offset_pct']:g}% of rent in GDS"}
        return {"income": add_pct * rent12, "gds": p.pith_monthly(), "tds": 0.0,
                "treatment": f"PITH in GDS; {pol['addback_pct']:g}% of suite rent added to income"}
    if method == "add_back":
        cost = p.pi_monthly() + (CONDO_SHARE * p.condo_fees_monthly if pol["addback_excludes_tax_heat"]
                                 else p.tax_heat_condo_monthly())
        return {"income": add_pct * rent12, "gds": 0.0, "tds": cost,
                "treatment": f"{pol['addback_pct']:g}% of rent to income; "
                             + ("P&I and condo fees" if pol["addback_excludes_tax_heat"] else "full PITH") + " in TDS"}
    if method == "offset":
        net = p.pith_monthly() - pol["offset_pct"] / 100 * p.rent_monthly
        if net >= 0:
            return {"income": 0.0, "gds": 0.0, "tds": net, "treatment": f"PITH less {pol['offset_pct']:g}% of rent; "
                                                                       "shortfall in TDS"}
        surplus = -12 * net if pol["offset_surplus_to_income"] else 0.0
        return {"income": surplus, "gds": 0.0, "tds": 0.0,
                "treatment": "rent covers PITH; surplus " + ("added to income" if surplus else "ignored")}
    if method == "net_rental":
        src = "T776" if p.t776_net_income is not None else "pro forma"
        return {"income": p.net_rent_annual(pol["net_rental_add_back_interest"]), "gds": 0.0, "tds": p.pi_monthly(),
                "treatment": f"{src} net rent + CCA" + (" + interest" if pol["net_rental_add_back_interest"] else "")
                             + " to income; P&I in TDS"}
    raise ValueError(f"method must be one of {METHODS}")


def ratios(income_annual: float, properties, *, method: str, other_debt_monthly: float = 0.0,
           policy: dict | None = None) -> dict:
    """GDS and TDS (percent) for the borrower's whole file under one rental method."""
    pol = P.policy(policy)
    props = as_properties(properties)
    rows, added, gds_m, rent_tds = [], 0.0, 0.0, 0.0
    for p in props:
        t = _treat(p, method, pol)
        added += t["income"]
        gds_m += t["gds"]
        rent_tds += t["tds"]
        rows.append({"name": p.name, "treatment": t["treatment"], "income_added_annual": round(t["income"], 2),
                     "gds_monthly": round(t["gds"], 2), "tds_monthly": round(t["tds"], 2)})
    income = income_annual + added
    tds_m = gds_m + rent_tds + other_debt_monthly
    out = {"method": method, "base_income_annual": round(income_annual, 2), "rental_income_added_annual": round(added, 2),
           "qualifying_income_annual": round(income, 2), "gds_housing_monthly": round(gds_m, 2),
           "rental_liabilities_monthly": round(rent_tds, 2), "other_debt_monthly": round(other_debt_monthly, 2),
           "tds_obligations_monthly": round(tds_m, 2), "properties": rows}
    if income <= 0:
        return {**out, "gds": None, "tds": None, "passes": False, "housing_capacity_monthly": 0.0,
                "reasons": ["qualifying income is zero or negative"]}
    m = income / 12
    gds, tds = gds_m / m * 100, tds_m / m * 100
    room = min(qualify.GDS_LIMIT / 100 * m - gds_m, qualify.TDS_LIMIT / 100 * m - tds_m)
    reasons = ([f"GDS {gds:.2f}% exceeds {qualify.GDS_LIMIT:g}%"] if gds > qualify.GDS_LIMIT else []) + \
              ([f"TDS {tds:.2f}% exceeds {qualify.TDS_LIMIT:g}%"] if tds > qualify.TDS_LIMIT else [])
    return {**out, "gds": round(gds, 2), "tds": round(tds, 2), "passes": not reasons,
            "housing_capacity_monthly": round(room, 2), "reasons": reasons}


def compare_methods(income_annual: float, properties, *, other_debt_monthly: float = 0.0,
                    policy: dict | None = None, methods=METHODS) -> dict:
    """Run every method on the same file; the best is the one leaving the most housing payment room."""
    pol = P.policy(policy)
    props = as_properties(properties)
    if not props:
        raise ValueError("at least one property is required")
    res = {m: ratios(income_annual, props, method=m, other_debt_monthly=other_debt_monthly, policy=pol)
           for m in methods}
    best = max(res, key=lambda m: res[m]["housing_capacity_monthly"])
    keys = sorted({k for m in methods for k in POLICY_KEYS[m]})
    return {"engine": "income.rental.compare_methods", "method": "add-back vs offset vs net-rental at B-20 limits",
            "results": res, "best_method": best, "qualifies_under": [m for m in methods if res[m]["passes"]],
            "summary": [{"method": m, "gds": r["gds"], "tds": r["tds"], "passes": r["passes"],
                         "housing_capacity_monthly": r["housing_capacity_monthly"]} for m, r in res.items()],
            "assumptions": {**P.assumptions(pol, keys),
                            "existing_mortgages": "existing mortgages use the actual payment; new mortgages are "
                                                  "stress-tested at max(contract + 2%, 5.25%)"},
            "source": P.sources("qualifying_rate_floor_pct", "gds_limit_pct", "tds_limit_pct", "condo_fee_pct",
                                "subject_rent_addback_max_pct", "investment_property_net_rent")}
