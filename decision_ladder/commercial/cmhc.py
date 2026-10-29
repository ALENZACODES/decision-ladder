"""CMHC multi-unit (5+ units) mortgage loan insurance: MLI Select points and sizing, and MLI Standard.

Verified against CMHC (checked 2026-10-29):

* MLI Select page (published Sept 21, 2026 per page metadata): points tiers 50/70/100; existing properties
  max LTV 85% / 95% / 95% and new construction max LTC 95% at every tier; max amortization 40 / 45 / 50
  years; minimum DCR 1.10 for standard rental; recourse at 50 and 70 points, limited recourse at 100;
  scoring grids for affordability, energy efficiency and accessibility.
* MLI Select PDF (ref 66792 20251029-008A): existing 100 points up to 95% LTV; minimum 5 units; affordability
  commitment at least 10 years, 20+ years earns 30 additional points; DCR 1.10 standard rental, 1.20 other
  shelter models, 1.40 non-residential; non-residential component capped at 75%.
* Standard Rental Housing page: max LTV 85%; amortization up to 40 years existing, 50 years new construction.
* Notice July 3, 2025: new standardized premium approach for all multi-unit MLI, effective July 14, 2025,
  with an MLI Select discount schedule; existing premium surcharges unchanged.

Assumptions (CMHC's fees-and-premiums PDF could not be retrieved for this check):

* Premium grid and the 10/20/30% Select discounts are taken from REIC's Sept 5, 2025 summary of the July 14,
  2025 grid (secondary source). REIC applies the discount after surcharges; its table puts the 20% tier at
  75 points while its text says 70: this module uses 70, matching CMHC's tiers.
* Amortization surcharge +0.25 points per 5 years beyond 25 (REIC); 45- and 50-year values extend that rule.
* MLI Standard minimum DCR 1.20 is not stated on CMHC's page.
* Premium is financed; DCR is tested on the loan including premium; LTV/LTC caps apply to the base loan.
"""
from __future__ import annotations

from .common import loan_for_debt_service, monthly_payment, pct, positive, r2

SOURCES = {
    "mli_select": "https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/mortgage-loan-insurance/"
                  "multi-unit-insurance/mliselect",
    "mli_select_pdf": "https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/project-funding-and-mortgage-financing/"
                      "mortgage-loan-insurance/multi-unit-insurance/mliselect/mli-select.pdf",
    "standard_rental": "https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/mortgage-loan-insurance/"
                       "multi-unit-insurance/standard-rental-housing",
    "premium_notice_2025": "https://www.cmhc-schl.gc.ca/media-newsroom/notices/2025/cmhc-to-update-multi-unit-mortgage-loan-"
                           "insurance-premiums",
    "premium_grid_secondary": "https://www.reic.ca/article-sept5-25.html",
    "checked": "2026-10-29",
}
MIN_UNITS = 5

# purpose -> [(min points, max LTV or LTC %, max amortization years, recourse)]
SELECT_TIERS = {
    "existing": [(50, 85.0, 40, "recourse"), (70, 95.0, 45, "recourse"), (100, 95.0, 50, "limited recourse")],
    "new_construction": [(50, 95.0, 40, "recourse"), (70, 95.0, 45, "recourse"), (100, 95.0, 50, "limited recourse")],
}
SELECT_DCR_MIN = {"standard_rental": 1.10, "other_shelter": 1.20}
STANDARD = {"ltv_max_pct": 85.0, "amort_max": {"existing": 40, "new_construction": 50},
            "dcr_min": 1.20}  # dcr_min: assumption

# Scoring grids: (threshold, points), highest threshold met wins.
AFFORDABILITY = {"existing": [(40, 50), (60, 70), (80, 100)],          # % of units at <= 30% of median renter income
                 "new_construction": [(10, 50), (15, 70), (25, 100)]}
LONG_COMMITMENT_YEARS, LONG_COMMITMENT_POINTS, MIN_COMMITMENT_YEARS = 20, 30, 10
ENERGY_EXISTING = [(15, 20), (25, 35), (40, 50)]                         # % reduction vs current performance
ENERGY_NEW = {"necb": [(25, 20), (50, 35), (60, 50)],                    # % better than NECB / NBC Tier 1
              "nbc": [(20, 20), (40, 35), (70, 50)]}
ACCESSIBILITY = {"none": 0, "level_1": 20, "level_2": 30}
ACCESSIBILITY_TEXT = {
    "level_1": "15%+ accessible units (CSA B651:23), or 15%+ universal design, or Rick Hansen v4.0 60-79%",
    "level_2": "15%+ accessible plus 85%+ universal design, or 100% universal design, or 100% accessible, "
               "or Rick Hansen v4.0 Gold (80%+)",
}

# Standard rental base premium (% of loan) by LTV band: construction, all other purposes (secondary source).
PREMIUM_GRID = [(65, 3.25, 2.60), (70, 3.75, 2.85), (75, 4.25, 3.35), (80, 5.00, 4.35), (85, 6.00, 5.35),
                (90, 6.75, 5.90), (95, 7.00, 6.15)]
SELECT_DISCOUNT = [(50, 0.10), (70, 0.20), (100, 0.30)]
AMORT_SURCHARGE_PER_5Y = 0.25


def _grid(value: float, grid: list[tuple[float, int]]) -> int:
    pts = 0
    for threshold, p in grid:
        if value >= threshold:
            pts = p
    return pts


def score(*, purpose: str = "existing", affordable_units_pct: float = 0.0, affordability_years: int = 10,
          energy_reduction_pct: float = 0.0, energy_standard: str = "necb", accessibility: str = "none") -> dict:
    """MLI Select points. ``energy_reduction_pct`` is the reduction vs current performance (existing) or the
    improvement over NECB / NBC Tier 1 (new construction, per ``energy_standard``)."""
    if purpose not in SELECT_TIERS:
        raise ValueError("purpose must be 'existing' or 'new_construction'")
    if accessibility not in ACCESSIBILITY:
        raise ValueError(f"accessibility must be one of {sorted(ACCESSIBILITY)}")
    aff = _grid(affordable_units_pct, AFFORDABILITY[purpose]) if affordability_years >= MIN_COMMITMENT_YEARS else 0
    bonus = LONG_COMMITMENT_POINTS if aff and affordability_years >= LONG_COMMITMENT_YEARS else 0
    if purpose == "existing":
        energy = _grid(energy_reduction_pct, ENERGY_EXISTING)
    else:
        if energy_standard not in ENERGY_NEW:
            raise ValueError("energy_standard must be 'necb' or 'nbc'")
        energy = _grid(energy_reduction_pct, ENERGY_NEW[energy_standard])
    acc = ACCESSIBILITY[accessibility]
    total = aff + bonus + energy + acc
    t = tier(purpose, total)
    nxt = next((p for p, *_ in SELECT_TIERS[purpose] if p > total), None)
    notes = []
    if affordable_units_pct and affordability_years < MIN_COMMITMENT_YEARS:
        notes.append(f"affordability needs a commitment of at least {MIN_COMMITMENT_YEARS} years")
    if acc:
        notes.append("accessibility points also require 100% visitable units and barrier-free common areas")
    return {"purpose": purpose,
            "points": {"affordability": aff, "affordability_20yr_bonus": bonus, "energy_efficiency": energy,
                       "accessibility": acc},
            "total_points": total, "tier": t,
            "points_to_next_tier": None if nxt is None else nxt - total,
            "accessibility_definition": ACCESSIBILITY_TEXT.get(accessibility), "notes": notes}


def tier(purpose: str, points: float) -> dict | None:
    best = None
    for min_pts, ltv, amort, recourse in SELECT_TIERS[purpose]:
        if points >= min_pts:
            best = {"min_points": min_pts, ("max_ltv_pct" if purpose == "existing" else "max_ltc_pct"): ltv,
                    "max_amort_years": amort, "recourse": recourse,
                    "premium_discount_pct": pct(dict(SELECT_DISCOUNT)[min_pts], 0)}
    return best


def premium_rate(*, ltv_pct: float, amort_years: float, construction: bool, points: float = 0.0) -> dict:
    """Premium as % of the loan: base by LTV band, plus amortization surcharge, less any MLI Select discount."""
    band = next((row for row in PREMIUM_GRID if ltv_pct <= row[0] + 1e-9), None)
    if band is None or ltv_pct <= 0:
        raise ValueError("LTV must be above 0% and at most 95%")
    base = band[1] if construction else band[2]
    surcharge = AMORT_SURCHARGE_PER_5Y * max(0, -(-(amort_years - 25) // 5))
    disc = 0.0
    for p, d in SELECT_DISCOUNT:
        if points >= p:
            disc = d
    rate = (base + surcharge) * (1 - disc)
    return {"ltv_band_max_pct": band[0], "base_pct": base, "amort_surcharge_pct": surcharge,
            "select_discount_pct": pct(disc, 0), "premium_pct": round(rate, 4)}


def _max_base_loan(cap_base: float, total_cap: float, value: float, amort: float, construction: bool, points: float):
    """Largest base loan with base <= cap_base and base x (1 + premium(LTV)) <= total_cap. Premium rises with
    LTV, so base x (1 + premium) is increasing: scan the bands from the top and take the first that fits."""
    lo_edges = [0.0] + [row[0] for row in PREMIUM_GRID[:-1]]
    for (hi, *_), lo in zip(reversed(PREMIUM_GRID), reversed(lo_edges)):
        if cap_base <= value * lo / 100:
            continue
        prem = premium_rate(ltv_pct=hi, amort_years=amort, construction=construction, points=points)
        cand = min(cap_base, value * hi / 100, total_cap / (1 + prem["premium_pct"] / 100))
        if cand > value * lo / 100 or lo == 0.0:
            return cand, premium_rate(ltv_pct=max(cand / value * 100, 1e-9), amort_years=amort,
                                      construction=construction, points=points)
    raise AssertionError("unreachable")


def _size(program: str, purpose: str, value: float, noi: float, rate: float, amort: float, cap_pct: float,
          dcr_min: float, points: float, compounding: str, requested: float | None) -> dict:
    construction = purpose == "new_construction"
    by_ltv = value * cap_pct / 100
    total_cap = loan_for_debt_service(noi / dcr_min, rate, amort, compounding=compounding)
    loan, prem = _max_base_loan(min(by_ltv, requested) if requested else by_ltv, total_cap, value, amort,
                                construction, points)
    if requested and loan >= requested - 0.005:
        binding = "requested"
    else:
        binding = "ltv" if loan >= by_ltv - 0.005 else "dcr"
    premium = loan * prem["premium_pct"] / 100
    total = loan + premium
    ads = monthly_payment(total, rate, amort, compounding=compounding) * 12
    key = "ltc_pct" if construction else "ltv_pct"
    out = {"program": program, "purpose": purpose, "base_loan": r2(loan), "premium": r2(premium), "total_loan": r2(total),
           "binding_constraint": binding, "cap_by_ltv": r2(by_ltv), "cap_by_dcr_total_loan": r2(total_cap),
           key: pct(loan / value), "max_" + key: cap_pct, "amort_years": amort,
           "monthly_payment": r2(ads / 12), "annual_debt_service": r2(ads), "dcr": round(noi / ads, 3) if ads else None,
           "dcr_min": dcr_min, "premium_detail": prem}
    if requested:
        out["requested_fits"] = binding == "requested"
    return out


def size(*, noi: float, value: float, rate: float, units: int, purpose: str = "existing", amort_years: float | None = None,
         affordable_units_pct: float = 0.0, affordability_years: int = 10, energy_reduction_pct: float = 0.0,
         energy_standard: str = "necb", accessibility: str = "none", shelter: str = "standard_rental",
         compounding: str = "semi", requested_loan: float | None = None) -> dict:
    """Size MLI Standard and MLI Select side by side. ``value`` is lending value (existing) or total cost (new build)."""
    if int(units) < MIN_UNITS:
        raise ValueError(f"CMHC multi-unit insurance needs at least {MIN_UNITS} units")
    noi, value = positive("noi", noi), positive("value", value)
    if shelter not in SELECT_DCR_MIN:
        raise ValueError(f"shelter must be one of {sorted(SELECT_DCR_MIN)}")
    pts = score(purpose=purpose, affordable_units_pct=affordable_units_pct, affordability_years=affordability_years,
                energy_reduction_pct=energy_reduction_pct, energy_standard=energy_standard, accessibility=accessibility)
    std_amort = STANDARD["amort_max"][purpose]
    std = _size("MLI Standard", purpose, value, noi, rate, min(amort_years or std_amort, std_amort),
                STANDARD["ltv_max_pct"], STANDARD["dcr_min"], 0, compounding, requested_loan)
    out = {"units": int(units), "score": pts, "standard": std, "select": None, "best": "MLI Standard"}
    t = pts["tier"]
    if t:
        sel_amort = min(amort_years or t["max_amort_years"], t["max_amort_years"])
        cap = t.get("max_ltv_pct") or t.get("max_ltc_pct")
        sel = _size(f"MLI Select ({t['min_points']} points)", purpose, value, noi, rate, sel_amort, cap,
                    SELECT_DCR_MIN[shelter], pts["total_points"], compounding, requested_loan)
        sel["recourse"] = t["recourse"]
        out["select"] = sel
        out["extra_proceeds_vs_standard"] = r2(sel["base_loan"] - std["base_loan"])
        out["payment_change_vs_standard"] = r2(sel["monthly_payment"] - std["monthly_payment"])
        if sel["base_loan"] > std["base_loan"] + 0.005 or (abs(sel["base_loan"] - std["base_loan"]) <= 0.005
                                                            and sel["monthly_payment"] < std["monthly_payment"]):
            out["best"] = sel["program"]
    out["sources"] = SOURCES
    out["assumptions"] = [
        "premium grid and Select discounts (10/20/30%) from REIC's summary of CMHC's July 14, 2025 grid, not CMHC's own PDF",
        "amortization surcharge +0.25 pts per 5 years over 25; 45/50-year values extrapolate the rule",
        "MLI Standard minimum DCR 1.20 is an assumption (not stated on CMHC's page)",
        "premium financed; DCR tested on base loan plus premium; LTV/LTC cap on the base loan",
        "the 20-year commitment bonus is applied only when affordability points are earned",
        "CMHC sets its own lending value and underwriting rate; the inputs stand in for both",
        "non-residential space (75% cap, 1.40 DCR) is not modelled",
    ]
    out["engine"] = "commercial.cmhc"
    return out

