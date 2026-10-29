"""Illustrative sample files. Every person, address and figure here is invented for the demo."""
from __future__ import annotations

SAMPLES: dict[str, dict] = {
    "oakville_stretch": {
        "label": "Purchase that fails the stress test (Oakville, $1.1M)",
        "purpose": "purchase", "borrower_name": "Priya Raman", "province": "ON", "postal_code": "L6J 3K2",
        "price": 1_100_000, "down_payment": 220_000, "annual_income": 185_000, "credit_score": 742,
        "contract_rate": 4.19, "amort_years": 30, "property_tax_annual": 7_900, "other_debt_monthly": 850,
        "first_time_buyer": True, "as_of": "2026-10-28",
        "documents": [{"type": "T4 2025", "extracted": {"annual_income": 184_200}}],
    },
    "brampton_first_home": {
        "label": "Insured first home that passes (Brampton, $725K)",
        "purpose": "purchase", "borrower_name": "Daniel Okafor", "province": "ON", "postal_code": "L6P 1A1",
        "price": 725_000, "down_payment": 50_000, "annual_income": 168_000, "credit_score": 701,
        "contract_rate": 4.24, "amort_years": 30, "property_tax_annual": 5_600, "other_debt_monthly": 400,
        "first_time_buyer": True, "as_of": "2026-10-28",
        "documents": [{"type": "Employment letter", "extracted": {"annual_income": 168_000}}],
    },
    "pandemic_renewal_rbc": {
        "label": "2021 pandemic mortgage renewing now (RBC, Markham)",
        "purpose": "renewal", "borrower_name": "Wei Chen", "province": "ON", "lender": "RBC",
        "balance": 504_200, "contract_rate": 1.99, "term_start": "2021-12-15", "maturity": "2026-12-15",
        "renewal_rate": 4.84, "remaining_amort_years": 20, "annual_income": 142_000, "credit_score": 768,
        "original_principal": 600_000, "original_rate": 1.99, "original_amort_years": 25, "months_elapsed": 59,
        "purchase_price": 780_000, "purchase_year": 2021, "purchase_month": 11, "postal_code": "L3R 2Z5",
        "property_tax_annual": 5_400, "other_debt_monthly": 600, "term_years": 5, "as_of": "2026-10-28",
        "offers": [{"label": "RBC renewal letter", "rate": 4.84}, {"label": "Credit union switch", "rate": 4.29, "fees": 0},
                   {"label": "Monoline switch + cashback", "rate": 4.39, "fees": 0, "cashback": 1500}],
    },
    "td_break_early": {
        "label": "Break a TD fixed mortgage 22 months early (refinance)",
        "purpose": "refinance", "borrower_name": "Marco Ferreira", "province": "ON", "lender": "TD",
        "balance": 640_000, "contract_rate": 5.29, "term_start": "2023-08-01", "maturity": "2028-08-01",
        "original_posted_rate": 6.84, "new_rate": 4.39, "renewal_rate": 4.39, "remaining_amort_years": 23,
        "annual_income": 210_000, "credit_score": 790, "property_value": 1_150_000, "new_money": 60_000,
        "property_tax_annual": 6_800, "other_debt_monthly": 1_100, "term_years": 5, "as_of": "2026-10-28",
    },
}

SAMPLE_EMAIL = """Hi John,

We finally found a place! It's a semi in Oakville listed at $1.1M. We have 220k saved for the down payment
and we're first time buyers. Our combined income is about $185,000 and my credit score is 742. We have a car
payment of $850/month. The bank mentioned 4.19% on a 5-year fixed with a 30 year amortization.
Property taxes are around $7,900 a year.

Thanks,
Priya Raman
"""

SAMPLE_BOOK_CSV = """borrower,lender,balance,contract_rate,term_start,maturity,original_posted_rate,original_principal,original_rate,original_amort_years,months_elapsed,renewal_rate,annual_income,province
Wei Chen,RBC,504200,1.99,2021-12-15,2026-12-15,4.79,600000,1.99,25,59,4.84,142000,ON
Ana Souza,TD,383700,2.39,2022-02-01,2027-02-01,4.79,450000,2.39,25,57,4.79,118000,ON
Kofi Mensah,Scotiabank,713800,1.79,2021-11-30,2026-11-30,4.79,820000,1.79,30,59,4.89,165000,ON
Lena Novak,CIBC,300900,2.14,2022-06-01,2027-06-01,5.34,350000,2.14,25,53,4.69,96000,AB
Raj Patel,BMO,463800,4.94,2024-03-01,2029-03-01,6.84,480000,4.94,25,19,4.59,151000,ON
Mei Ling,National Bank,590800,2.04,2022-01-15,2027-01-15,4.79,700000,2.04,25,58,4.84,134000,ON
"""
