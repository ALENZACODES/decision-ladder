"""Program and legal parameters for the Business Lending Desk, each with where it came from.

``VERIFIED`` values were read on the cited government page (or, where noted, a law-firm summary of the
regulation) on the ``checked`` date. ``ASSUMPTIONS`` are modelling choices or figures that could not be
confirmed on a primary source in that check; every result that relies on one lists it.
"""
from __future__ import annotations

CHECKED = "2026-10-29"

CSBFP_ABOUT = ("https://ised-isde.canada.ca/site/canada-small-business-financing-program/en/"
               "find-loan-your-small-business/about-program/helping-small-businesses-get-loans")
CSBFP_2022 = ("https://ised-isde.canada.ca/site/canada-small-business-financing-program/en/"
              "documentation-centre/bulletins/2022-changes-canada-small-business-financing-program")
CIR_REGS = "https://gazette.gc.ca/rp-pr/p2/2024/2024-06-19/html/sor-dors114-eng.html"
CIR_SUMMARY = "https://www.mccarthy.ca/en/insights/articles/amendments-criminal-rate-interest-provisions-come-force"
CRA_AII = "https://www.canada.ca/taxes-accelerated-investment-income"
RII_BILL = ("https://taxnews.ey.com/news/2025-2564-canada-tables-bill-with-accelerated-capital-cost-allowance-"
            "and-other-immediate-expensing-measures")
C15_ASSENT = ("https://www.canada.ca/en/department-finance/news/2026/03/"
              "legislation-passes-to-implement-budget-2025-canada-strong.html")


def _v(value, url: str, note: str = "") -> dict:
    return {"value": value, "source": url, "checked": CHECKED, **({"note": note} if note else {})}


CSBFP = {
    "max_gross_revenue": _v(10_000_000, CSBFP_ABOUT, "gross annual revenues of $10 million or less"),
    "farming_excluded": _v(True, CSBFP_ABOUT, "program is closed to farming businesses"),
    "max_per_borrower": _v(1_150_000, CSBFP_2022, "borrower and related borrowers combined"),
    "max_term_loans": _v(1_000_000, CSBFP_2022),
    "max_equipment_and_leasehold": _v(500_000, CSBFP_2022, "within the term-loan limit"),
    "max_intangibles_and_working_capital": _v(150_000, CSBFP_2022, "within the term-loan limit"),
    "max_line_of_credit": _v(150_000, CSBFP_2022, "working capital, in addition to term loans"),
    "registration_fee_pct": _v(2.0, CSBFP_ABOUT, "on amount loaned (term) or authorized (LOC); may be financed"),
    "admin_fee_annual_pct": _v(1.25, CSBFP_2022, "term loans: on end-of-month balances; LOC: on daily/average daily balance"),
    "max_spread_floating_term": _v(3.0, CSBFP_ABOUT, "over the lender's prime rate"),
    "max_spread_fixed_term": _v(3.0, CSBFP_ABOUT, "over the lender's single-family residential mortgage rate for the term"),
    "max_spread_line_of_credit": _v(5.0, CSBFP_ABOUT, "over the lender's prime rate"),
    "max_term_years": _v(15, CSBFP_2022, "term loans made on or after 2022-07-04, all asset classes"),
    "max_loc_term_years": _v(5, CSBFP_2022),
}

CRIMINAL_RATE = {
    "general_cap_apr_pct": _v(35.0, CIR_REGS, "Criminal Code s.347 as amended by Budget Implementation Act, 2023, "
                                              "No. 1, in force 2025-01-01 (was 60% effective annual rate)"),
    "in_force": _v("2025-01-01", CIR_SUMMARY),
    "commercial_mid_band": _v({"above": 10_000, "up_to": 500_000, "cap_apr_pct": 48.0}, CIR_REGS,
                              "borrower not a natural person and borrowing for a business or commercial purpose"),
    "commercial_exempt_above": _v(500_000, CIR_REGS, "no criminal rate applies above this credit advanced, same conditions"),
    "pawn_band": _v({"below": 1_000, "cap_apr_pct": 48.0}, CIR_REGS, "pawnbroker, tangible personal property other than a vehicle"),
}

CCA = {
    "aii_before_2024": _v(1.5, CRA_AII, "first-year CCA = 1.5 x class rate x cost (3x the half-year amount); half-year rule suspended"),
    "aii_2024_2027": _v(1.0, CRA_AII, "phase-out: 2x the half-year amount = 1.0 x class rate x cost"),
    "rii_acquired_after_2024_available_before_2030": _v(1.5, RII_BILL, "Bill C-15 'reaccelerated investment incentive'"),
    "rii_available_2030_2033": _v(1.0, RII_BILL),
    "bill_c15_royal_assent": _v("2026-03-26", C15_ASSENT, "release lists the Productivity Super-Deduction among the measures"),
}

ASSUMPTIONS = {
    "apr_method": ("APR is the nominal annual rate compounded at the payment frequency (per-period IRR x periods per "
                   "year), with all fees counted as interest; the Criminal Code's own APR calculation text was not "
                   "retrieved in the 2026-10-29 check."),
    "credit_advanced_net_of_fees": ("'Credit advanced' for the exemption bands is taken as cash actually advanced net of "
                                    "fees and required deposits (long-standing s.347 definition, not re-read in this check)."),
    "mca_characterization": ("A merchant cash advance is usually documented as a purchase of future receivables; whether "
                             "s.347 applies depends on its legal characterization. The implied APR is shown either way."),
    "factoring_characterization": ("Factoring is usually a sale of receivables, not a loan; with full recourse a court may "
                                   "treat it as secured credit. The APR is shown for comparison either way."),
    "factoring_cost_basis": ("Cost is measured on the incremental flows: the advance received at funding versus the "
                             "advance plus fees given up when the invoice is paid (or repurchased under recourse). The "
                             "customer's payment itself happens with or without factoring."),
    "csbfp_admin_fee_borne_by": ("The 1.25% administration fee is remitted by the lender; the borrower bears it only to the "
                                 "extent the lender prices it into the rate (ISED pages do not say who pays)."),
    "csbfp_rate_compounding": "CSBFP and unsecured term loans: quoted rate is nominal, compounded at the payment frequency.",
    "half_year_rule_default": ("Without an AII/RII-eligible date the half-year rule applies (first-year CCA = 0.5 x rate x "
                               "cost). Classes with immediate expensing or special rules (e.g. 53, 43.1/43.2, 54-56) are "
                               "not modelled; pass first_year_factor to override."),
    "cca_pool_continues": ("Undepreciated capital left after salvage is written off as a continuing declining-balance pool "
                           "(perpetuity of tax shields), i.e. the class is not closed and no recapture/terminal loss."),
    "factoring_period_rounding": "Per-period factoring fees are charged for each started period unless prorate=true.",
}


def assumptions(*keys: str) -> dict:
    return {k: ASSUMPTIONS[k] for k in keys}


def sources(*groups: dict) -> list[dict]:
    """Unique (source, checked) pairs for the parameter groups a result used."""
    seen: dict[str, dict] = {}
    for g in groups:
        for p in g.values():
            seen.setdefault(p["source"], {"url": p["source"], "checked": p["checked"]})
    return list(seen.values())


def val(group: dict, key: str):
    return group[key]["value"]
