"""Regulatory figures and lender-policy defaults for the Income & Rental Qualification Desk.

``VERIFIED`` values were read on the cited OSFI or CMHC page on the ``CHECKED`` date. ``LENDER_POLICY`` values
are not regulation: each lender sets its own, so they are parameters with a typical default, and every result
that uses one lists it under ``assumptions``.
"""
from __future__ import annotations

from ..engines import qualify

CHECKED = "2026-10-29"

OSFI_MQR = ("https://www.osfi-bsif.gc.ca/en/supervision/financial-institutions/banks/"
            "minimum-qualifying-rate-uninsured-mortgages")
CMHC_GDS_TDS = ("https://www.cmhc-schl.gc.ca/en/professionals/project-funding-and-mortgage-financing/"
                "mortgage-loan-insurance/calculating-gds-tds")
CMHC_INCOME_PROPERTY = ("https://cmhc-schl.gc.ca/en/finance-and-investing/mortgage-loan-insurance/"
                        "mortgage-loan-insurance-homeownership-programs/cmhc-income-property")
CMHC_SELF_EMPLOYED = ("https://www.cmhc-schl.gc.ca/en/professionals/project-funding-and-mortgage-financing/"
                      "mortgage-loan-insurance/mortgage-loan-insurance-homeownership-programs/cmhc-self-employed")


def _v(value, url: str, note: str) -> dict:
    return {"value": value, "source": url, "checked": CHECKED, "note": note}


VERIFIED = {
    "qualifying_rate_floor_pct": _v(qualify.MIN_QUALIFYING_RATE, OSFI_MQR,
                                    "greater of the contract rate plus 2% or 5.25%"),
    "qualifying_rate_buffer_pct": _v(2.0, OSFI_MQR, "added to the contract rate"),
    "gds_limit_pct": _v(qualify.GDS_LIMIT, CMHC_GDS_TDS, "CMHC maximum gross debt service ratio"),
    "tds_limit_pct": _v(qualify.TDS_LIMIT, CMHC_GDS_TDS, "CMHC maximum total debt service ratio"),
    "condo_fee_pct": _v(50.0, CMHC_GDS_TDS, "50% of condominium fees are included in GDS and TDS"),
    "subject_rent_addback_max_pct": _v(50.0, CMHC_GDS_TDS,
                                       "up to 50% of gross rent from the subject property may be added to income; "
                                       "taxes and heat may then be excluded from the ratios"),
    "two_unit_owner_occupied_rent_max_pct": _v(100.0, CMHC_GDS_TDS,
                                               "up to 100% of the secondary suite's gross rent, owner-occupied 2-unit"),
    "investment_property_net_rent": _v(True, CMHC_GDS_TDS, "net rental income of a separate investment property "
                                                           "can form part of gross annual income"),
    "rental_min_equity_pct": _v(20.0, CMHC_INCOME_PROPERTY, "CMHC Income Property (2-4 units, non-owner occupied): "
                                                            "minimum equity 20%"),
    "self_employed_gross_up_pct": _v(15.0, CMHC_SELF_EMPLOYED, "sole proprietors and partnerships: income may be "
                                                               "grossed up by 15% or eligible deductions added back"),
    "self_employed_months_recommended": _v(24, CMHC_SELF_EMPLOYED, "24 months recommended, or experience in the same "
                                                                   "line of work"),
}

LENDER_POLICY = {
    "addback_pct": (50.0, "percent of gross rent added to income (add-back method)"),
    "offset_pct": (80.0, "percent of gross rent netted against the property's PITH (offset method); 50-100 is seen"),
    "offset_surplus_to_income": (False, "whether rent above PITH under the offset method is added to income"),
    "addback_excludes_tax_heat": (False, "exclude a rental's taxes and heat when its rent is added back"),
    "net_rental_add_back_interest": (True, "add mortgage interest back to T776 net rent, since P&I is counted in TDS"),
    "variable_min_years": (2, "years of overtime/bonus/commission/contract history required to use it"),
    "support_requires_order": (True, "support income counted only with a court order or separation agreement"),
    "include_ccb": (False, "whether Canada Child Benefit is counted as income"),
    "continuity_years": (3, "benefits and support must continue at least this many years"),
    "nontaxable_gross_up_pct": (0.0, "gross-up of non-taxable income (support, CCB); some lenders use up to 25%"),
    "min_dscr": (1.0, "minimum rental DSCR per property"),
    "vacancy_pct": (0.0, "vacancy allowance on gross rent in NOI"),
}


def policy(overrides: dict | None = None) -> dict:
    """Lender-policy values with ``overrides`` applied; unknown keys are rejected so typos never pass silently."""
    overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
    bad = set(overrides) - set(LENDER_POLICY)
    if bad:
        raise ValueError(f"unknown lender policy keys: {sorted(bad)}")
    return {k: overrides.get(k, default) for k, (default, _) in LENDER_POLICY.items()}


def assumptions(pol: dict, keys) -> dict:
    """``{key: "value (description) - lender policy, varies"}`` for the policy keys a result relied on."""
    return {k: f"{pol[k]} ({LENDER_POLICY[k][1]}) - lender policy, varies" for k in keys}


def sources(*keys: str) -> list[dict]:
    return [{"fact": k, "value": VERIFIED[k]["value"], "url": VERIFIED[k]["source"], "checked": CHECKED,
             "note": VERIFIED[k]["note"]} for k in keys]
