"""Business Lending Desk: hand-checked figures for every calculator, edge cases and criminal-rate flags."""
import math
import re

import pytest

import decision_ladder.modules.business as BM
from decision_ladder.agent import tools as T
from decision_ladder.business import capacity, cashflow as cf, csbfp, factoring, lease, params, unsecured, usury


# ------------------------------------------------------------------ cash-flow core
def test_irr_textbook_case_discounts_back_to_zero():
    flows = [-100, 39, 59, 55, 20]
    r = cf.irr(flows)
    assert r == pytest.approx(0.280948, abs=1e-6)
    assert abs(cf.npv(r, flows)) < 1e-9


def test_irr_simple_and_extreme_rates():
    assert cf.irr([-100, 110]) == pytest.approx(0.10, abs=1e-12)
    assert cf.irr([-1, 100]) == pytest.approx(99.0, rel=1e-9)          # 9,900% needs the widening bracket
    assert cf.irr([-100, 50]) == pytest.approx(-0.5, abs=1e-12)        # negative return
    assert cf.irr([100, -110]) == pytest.approx(0.10, abs=1e-12)       # borrower's side, same rate


def test_irr_multiple_roots_returns_lowest_and_flags_sign_changes():
    flows = [-100, 230, -132]                                          # roots at 10% and 20%
    assert cf.sign_changes(flows) == 2
    assert cf.irr(flows) == pytest.approx(0.10, abs=1e-10)


def test_irr_rejects_flows_without_sign_change():
    with pytest.raises(ValueError):
        cf.irr([100, 50, 25])
    with pytest.raises(ValueError):
        cf.xirr([(0, -5), (30, -5)])


def test_xirr_one_year_and_long_daily_series():
    assert cf.xirr([(0, -1000), (365, 1100)]) == pytest.approx(0.10, abs=1e-12)
    daily = [(0.0, 10000.0)] + [(float(d), -60.0) for d in range(1, 200)]
    ear = cf.xirr(daily)
    assert abs(cf.xnpv(ear, daily)) < 1e-6


def test_annuity_and_rate_conversions():
    assert cf.annuity_payment(100000, 0.01, 12) == pytest.approx(8884.88, abs=0.005)
    assert cf.annuity_payment(100000, 0.01, 12, due=True) == pytest.approx(8884.88 / 1.01, abs=0.005)
    assert cf.annuity_pv(cf.annuity_payment(5000, 0.02, 7, True), 0.02, 7, True) == pytest.approx(5000)
    assert cf.annuity_payment(1200, 0.0, 12) == 100
    assert cf.ear_from_periodic(0.015, 12) == pytest.approx(1.015 ** 12 - 1)
    assert cf.apr_from_ear(cf.ear_from_periodic(0.01, 12), 12) == pytest.approx(0.12)


# ------------------------------------------------------------------ criminal rate
@pytest.mark.parametrize("credit,natural,purpose,cap", [
    (5_000, False, True, 35.0),          # $10,000 or less: general rate even for a corporation
    (10_000, False, True, 35.0),         # band starts *above* $10,000
    (10_000.01, False, True, 48.0),
    (500_000, False, True, 48.0),        # band includes $500,000
    (500_000.01, False, True, None),     # exempt above $500,000
    (50_000, True, True, 35.0),          # sole proprietor = natural person
    (50_000, False, False, 35.0),        # corporation, non-business purpose
    (2_000_000, True, True, 35.0),       # size never exempts a natural person
])
def test_applicable_cap(credit, natural, purpose, cap):
    assert usury.applicable_cap(credit, natural, purpose)["cap_apr_pct"] == cap


def test_criminal_flags():
    assert usury.check(40, 50_000)["exceeds_criminal_rate"] is False          # 48% band
    assert usury.check(40, 50_000, borrower_is_natural_person=True)["exceeds_criminal_rate"] is True
    near = usury.check(44, 50_000)
    assert near["exceeds_criminal_rate"] is False and "within 5 points" in near["flag"]
    assert usury.check(500, 600_000)["exceeds_criminal_rate"] is False         # no ceiling
    assert usury.applicable_cap(800, pawn=True, borrower_is_natural_person=True)["cap_apr_pct"] == 48.0
    with pytest.raises(ValueError):
        usury.check(20, 50_000, on="2024-12-31")
    with pytest.raises(ValueError):
        usury.applicable_cap(0)


# ------------------------------------------------------------------ unsecured products
def test_term_loan_no_fees_apr_equals_contract_rate():
    r = unsecured.term_loan(50_000, 18, 3)
    assert r["payment"] == pytest.approx(50_000 * 0.015 / (1 - 1.015 ** -36), abs=0.005)   # 1,807.62
    assert r["apr_pct"] == pytest.approx(18.0, abs=1e-6)
    assert r["ear_pct"] == pytest.approx((1.015 ** 12 - 1) * 100, abs=1e-4)
    assert r["total_interest"] == pytest.approx(r["payment"] * 36 - 50_000, abs=0.05)


def test_term_loan_fees_raise_apr_and_flows_discount_to_zero():
    r = unsecured.term_loan(50_000, 18, 3, upfront_fees=1_500, financed_fees=500)
    i = r["apr_pct"] / 1200
    pmt = cf.annuity_payment(50_500, 0.015, 36)
    assert 48_500 - cf.annuity_pv(pmt, i, 36) == pytest.approx(0, abs=0.1)   # APR is reported to 4 dp
    assert r["apr_pct"] > 18 and r["net_proceeds"] == 48_500
    assert r["total_cost_of_credit"] == pytest.approx(pmt * 36 - 48_500, abs=0.05)


def test_term_loan_criminal_flag_for_sole_proprietor():
    r = unsecured.term_loan(20_000, 39, 1, borrower_is_natural_person=True)
    assert r["criminal_rate"]["exceeds_criminal_rate"] is True and r["criminal_rate"]["cap_apr_pct"] == 35.0
    assert unsecured.term_loan(20_000, 39, 1)["criminal_rate"]["exceeds_criminal_rate"] is False


def test_amortize_last_payment_clears_balance():
    rows = unsecured.amortize(10_000, 0.01, 24)
    assert rows[-1]["balance"] == 0
    assert sum(r["principal"] for r in rows) == pytest.approx(10_000)


def test_line_of_credit_cost():
    r = unsecured.line_of_credit(100_000, 40_000, 9, standby_fee_pct=0.5, annual_fee=500, setup_fee=1_000,
                                 expected_years=2)
    interest = 40_000 * ((1 + 0.0075) ** 12 - 1)
    total = interest + 300 + 500 + 500
    assert r["annual_cost"]["total"] == pytest.approx(total, abs=0.01)
    assert r["effective_annual_cost_on_drawn_pct"] == pytest.approx(total / 40_000 * 100, abs=1e-4)
    with pytest.raises(ValueError):
        unsecured.line_of_credit(10_000, 20_000, 9)


def test_mca_one_day_hand_case():
    # $10,000 advance, factor 1.10, repaid in one remittance the next day: 10% per day -> APR 3,650%
    r = unsecured.merchant_cash_advance(10_000, 1.10, expected_remittance_days=1, days_per_week=7)
    assert r["apr_pct"] == pytest.approx(3650, rel=1e-9)
    assert r["calendar_days"] == 1 and r["criminal_rate"]["exceeds_criminal_rate"] is True


def test_mca_business_day_calendar_and_irr():
    r = unsecured.merchant_cash_advance(50_000, 1.35, expected_remittance_days=120, sensitivity_days=[60, 120, 180])
    assert r["remittances"] == 120 and r["calendar_days"] == 166        # 24 weeks of 5 days, last on a Friday
    flows = unsecured.mca_flows(50_000, 1.35, 67_500 / 120)
    assert abs(cf.xnpv(r["ear_pct"] / 100, flows)) < 0.01
    aprs = [s["apr_pct"] for s in r["sensitivity"]]
    assert aprs[0] > aprs[1] > aprs[2]                                  # faster payback, higher APR
    assert r["criminal_rate"]["cap_apr_pct"] == 48.0 and r["criminal_rate"]["exceeds_criminal_rate"] is True


def test_mca_holdback_partial_last_remittance():
    r = unsecured.merchant_cash_advance(10_000, 1.25, holdback_pct=10, expected_daily_sales=1_200)
    flows = unsecured.mca_flows(10_000, 1.25, 120)
    assert r["remittances"] == 105 and flows[-1][1] == pytest.approx(-20)   # 104 x 120 = 12,480, then 20
    assert -sum(a for _, a in flows[1:]) == pytest.approx(12_500)
    with pytest.raises(ValueError):
        unsecured.merchant_cash_advance(10_000, 1.25)
    with pytest.raises(ValueError):
        unsecured.merchant_cash_advance(10_000, 0.95, expected_remittance_days=100)


# ------------------------------------------------------------------ factoring
def test_factoring_per_period_started_periods():
    r = factoring.factor_invoice(10_000, 80, 45, fee_type="per_period", fee_pct=2)
    assert r["discount_fee"] == 400 and r["reserve_release"] == 1_600
    assert r["ear_pct"] == pytest.approx((1.05 ** (365 / 45) - 1) * 100, abs=1e-4)   # 8,400 / 8,000 over 45 days
    assert r["apr_pct"] == pytest.approx(365 * (1.05 ** (1 / 45) - 1) * 100, abs=1e-4)
    assert "factoring_period_rounding" in r["assumptions"]


def test_factoring_prorated_and_advance_basis():
    r = factoring.factor_invoice(10_000, 80, 45, fee_pct=2, prorate=True)
    assert r["discount_fee"] == pytest.approx(300)
    r2 = factoring.factor_invoice(10_000, 80, 30, fee_pct=2, fee_basis="advance")
    assert r2["discount_fee"] == pytest.approx(160)


def test_factoring_tiers_and_extension():
    tiers = [{"up_to_days": 30, "fee_pct": 2.0}, {"up_to_days": 60, "fee_pct": 3.5}]
    assert factoring.discount_fee_pct(30, "tiered", tiers=tiers) == 2.0
    assert factoring.discount_fee_pct(31, "tiered", tiers=tiers) == 3.5
    assert factoring.discount_fee_pct(75, "tiered", fee_pct=1.5, tiers=tiers) == 5.0
    with pytest.raises(ValueError):
        factoring.discount_fee_pct(75, "tiered", tiers=tiers)
    with pytest.raises(ValueError):
        factoring.discount_fee_pct(10, "tiered", tiers=[{"up_to_days": 30, "fee_pct": 3}, {"up_to_days": 60, "fee_pct": 2}])


def test_factoring_recourse_repurchase_and_non_recourse():
    r = factoring.factor_invoice(20_000, 80, 120, fee_pct=2, recourse=True, recourse_days=90)
    assert r["repurchased_under_recourse"] and r["days_outstanding"] == 90
    assert r["repurchase_payment"] == pytest.approx(16_000 + 1_200) and r["reserve_release"] is None
    nr = factoring.factor_invoice(20_000, 80, 120, fee_pct=2, recourse=False, non_recourse_premium_pct=1)
    assert not nr["repurchased_under_recourse"] and nr["discount_fee_pct"] == 9.0     # 4 periods x 2 + 1
    assert "true sale" in nr["criminal_rate"]["characterization"]


def test_factoring_fee_cannot_exceed_reserve():
    with pytest.raises(ValueError):
        factoring.factor_invoice(10_000, 95, 120, fee_pct=3, recourse=False)


def test_factoring_ledger_blends_dated_flows():
    terms = {"fee_pct": 2}
    led = factoring.factor_ledger([{"face": 10_000, "days_to_collect": 45}, {"face": 20_000, "days_to_collect": 20}],
                                  80, **terms)
    flows = [(0.0, 24_000.0), (20.0, -16_400.0), (45.0, -8_400.0)]
    assert abs(cf.xnpv(led["ear_pct"] / 100, flows)) < 0.01
    rates = [p["apr_pct"] for p in led["per_invoice"]]
    assert min(rates) < led["apr_pct"] < max(rates)
    assert led["total_cost"] == 800 and led["weighted_days"] == pytest.approx((10_000 * 45 + 20_000 * 20) / 30_000, abs=0.01)


# ------------------------------------------------------------------ CSBFP
def test_csbfp_eligibility_revenue_cap():
    assert csbfp.eligibility(10_000_000)["eligible"]
    out = csbfp.eligibility(10_000_001)
    assert not out["eligible"] and "exceeds" in out["reasons"][0]
    assert not csbfp.eligibility(1_000_000, farming=True)["eligible"]


def test_csbfp_limits_by_class():
    lim = csbfp.loan_limits({"equipment": 400_000, "leasehold_improvements": 300_000, "working_capital": 200_000,
                             "real_property": 600_000, "line_of_credit": 150_000})
    e = lim["eligible"]
    assert e["equipment"] + e["leasehold_improvements"] == pytest.approx(500_000)
    assert e["equipment"] == pytest.approx(500_000 * 4 / 7, abs=0.01)
    assert e["working_capital"] == 150_000 and e["real_property"] == 350_000
    assert lim["term_loan_total"] == 1_000_000 and lim["line_of_credit"] == 150_000
    assert lim["package_total"] == 1_150_000 and lim["shortfall"] == 500_000


def test_csbfp_existing_exposure_and_bad_class():
    lim = csbfp.loan_limits({"real_property": 500_000, "line_of_credit": 150_000}, existing_term_outstanding=700_000)
    assert lim["eligible"]["real_property"] == 300_000
    assert lim["line_of_credit"] == 150_000                      # 1.15M - 700k - 300k
    lim2 = csbfp.loan_limits({"equipment": 400_000, "line_of_credit": 150_000}, existing_term_outstanding=900_000)
    assert lim2["term_loan_total"] == 100_000 and lim2["line_of_credit"] == 150_000
    with pytest.raises(ValueError):
        csbfp.loan_limits({"inventory": 10})


def test_csbfp_max_rates():
    assert csbfp.max_rate("floating", prime_pct=4.45) == pytest.approx(7.45)
    assert csbfp.max_rate("fixed", residential_rate_pct=5.0) == pytest.approx(8.0)
    assert csbfp.max_rate("line_of_credit", prime_pct=4.45) == pytest.approx(9.45)
    with pytest.raises(ValueError):
        csbfp.max_rate("floating")


def test_csbfp_term_loan_fees_and_admin_fee():
    r = csbfp.term_loan(300_000, 7.45, 10, prime_pct=4.45)
    assert r["registration_fee"] == 6_000 and r["loan_balance_at_funding"] == 306_000
    assert r["within_max_rate"] and r["apr_pct"] > 7.45
    assert 300_000 - cf.annuity_pv(r["monthly_payment"], r["apr_pct"] / 1200, 120) == pytest.approx(0, abs=1.0)
    assert not csbfp.term_loan(300_000, 7.46, 10, prime_pct=4.45)["within_max_rate"]
    # 0% loan of 12,000 over a year, fee not financed: month-end balances 11,000..0 sum to 66,000
    z = csbfp.term_loan(12_000, 0.0, 1, prime_pct=4.45, finance_registration_fee=False)
    assert z["lender_admin_fee_total"] == pytest.approx(66_000 * 0.0125 / 12)
    assert z["monthly_payment"] == 1_000 and z["apr_pct"] > 0      # the 240 fee alone makes the APR positive
    with pytest.raises(ValueError):
        csbfp.term_loan(100_000, 7, 16, prime_pct=4)


def test_csbfp_line_of_credit():
    r = csbfp.line_of_credit(150_000, 60_000, 9.45, prime_pct=4.45, years=5)
    assert r["registration_fee"] == 3_000 and r["annual_cost"]["setup_fee_amortized"] == 600
    interest = 60_000 * ((1 + 9.45 / 1200) ** 12 - 1)
    assert r["annual_cost"]["total"] == pytest.approx(interest + 600, abs=0.01)
    assert r["within_max_rate"] and r["lender_admin_fee_annual"] == 750
    assert not csbfp.line_of_credit(100_000, 50_000, 9.5, prime_pct=4.45)["within_max_rate"]
    with pytest.raises(ValueError):
        csbfp.line_of_credit(150_001, 50_000, 9, prime_pct=4.45)
    with pytest.raises(ValueError):
        csbfp.line_of_credit(100_000, 50_000, 9, prime_pct=4.45, years=6)


def test_csbfp_assess_ineligible_has_no_package():
    out = csbfp.assess(12_000_000, {"equipment": 100_000})
    assert out["package"] is None and not out["eligibility"]["eligible"]


# ------------------------------------------------------------------ DSCR capacity
def test_normalized_ebitda_and_owner_pay():
    e = capacity.normalized_ebitda(100_000, 20_000, 25_000, 30_000, [{"label": "lawsuit", "amount": 15_000}],
                                   owner_compensation_paid=200_000, market_compensation=120_000)
    assert e["ebitda"] == 175_000 and e["adjusted_ebitda"] == 175_000 + 15_000 + 80_000


def test_dscr_hand_case_and_global():
    r = capacity.dscr(300_000, 150_000, interest_expense=40_000, income_taxes=60_000, depreciation_amortization=80_000,
                      proposed_loan={"amount": 500_000, "annual_rate_pct": 7, "amort_years": 10},
                      owner={"personal_income": 150_000, "personal_taxes": 40_000, "living_expenses": 60_000,
                             "personal_debt_service": 36_000})
    assert r["cads"] == 420_000 and r["dscr_existing"] == 2.8
    new_ds = cf.annuity_payment(500_000, 7 / 1200, 120) * 12
    assert r["proposed_debt_service"] == pytest.approx(new_ds, abs=0.01)
    assert r["dscr_pro_forma"] == pytest.approx(420_000 / (150_000 + new_ds), abs=1e-4)
    assert r["global"]["cash_flow"] == 470_000
    assert r["global"]["dscr_pro_forma"] == pytest.approx(470_000 / (150_000 + new_ds + 36_000), abs=1e-4)
    # room: 420,000 / 1.25 - 150,000 = 186,000 a year
    assert r["max_new_loan"]["annual_debt_service_room"]["business"] == 186_000
    assert r["max_new_loan"]["binding_constraint"] == "business"


def test_max_loan_lands_exactly_on_target():
    base = dict(net_income=200_000, existing_business_debt_service=50_000, depreciation_amortization=40_000,
                target_dscr=1.30, new_loan_rate_pct=8, new_loan_amort_years=7)
    amt = capacity.dscr(**base)["max_new_loan"]["amount"]
    r = capacity.dscr(**base, proposed_loan={"amount": amt, "annual_rate_pct": 8, "amort_years": 7})
    assert r["dscr_pro_forma"] == pytest.approx(1.30, abs=1e-4)


def test_global_constraint_can_bind():
    r = capacity.dscr(200_000, 0, new_loan_rate_pct=7, new_loan_amort_years=10,
                      owner={"personal_income": 50_000, "living_expenses": 120_000, "personal_debt_service": 60_000})
    assert r["max_new_loan"]["binding_constraint"] == "global"
    assert r["dscr_existing"] is None and r["passes_target"] is None


# ------------------------------------------------------------------ lease vs buy
def test_cca_shield_matches_textbook_half_year_formula():
    C, d, T, k, S, N = 100_000, 0.20, 0.265, 0.05, 10_000, 5
    got = lease.pv_cca_shield(C, 20, 26.5, k, N, S, 0.5)["pv"]
    textbook = C * d * T / (d + k) * (1 + 0.5 * k) / (1 + k) - S * d * T / (d + k) / (1 + k) ** N
    assert got == pytest.approx(textbook, abs=1e-6)


def test_cca_shield_general_first_year_factor():
    C, d, T, k = 50_000, 0.30, 0.25, 0.06
    got = lease.pv_cca_shield(C, 30, 25, k, 4, 0, 1.5)["pv"]
    closed = C * T * (1.5 * d / (1 + k) + (1 - 1.5 * d) * d / ((d + k) * (1 + k)))
    assert got == pytest.approx(closed, abs=1e-6)


def test_cca_recapture_when_salvage_exceeds_pool():
    s = lease.pv_cca_shield(100_000, 30, 26.5, 0.05, 5, 15_000, 1.5)
    assert s["recapture"] == pytest.approx(15_000 - 100_000 * 0.55 * 0.7 ** 4, abs=0.01) and s["ucc_after_salvage"] == 0


@pytest.mark.parametrize("acq,avail,factor", [
    ("2026-06-01", "2026-07-01", 1.5),      # RII
    ("2025-03-01", "2031-01-01", 1.0),      # RII phase-out
    ("2025-03-01", "2034-01-01", 0.5),
    ("2020-05-01", "2020-06-01", 1.5),      # original AII
    ("2024-02-01", "2025-06-01", 1.0),      # acquired 2024: original AII phase-out, not RII
    ("2017-05-01", "2017-06-01", 0.5),
    (None, None, 0.5),
])
def test_first_year_factor(acq, avail, factor):
    assert lease.first_year_factor(acq, avail)["factor"] == factor


def test_lease_zero_tax_breakeven_is_loan_payment_in_advance():
    # T = 0: buying costs the price; a lease whose payment (in advance) amortizes the price at the loan rate ties
    pmt = cf.annuity_payment(10_000, 0.06 / 12, 36, due=True)
    r = lease.lease_vs_buy(10_000, pmt, 3, 6, 0, 20)
    assert r["net_advantage_to_leasing"] == pytest.approx(0, abs=0.01)
    assert r["breakeven_lease_payment"] == pytest.approx(pmt, abs=0.01)


def test_lease_breakeven_and_decision():
    args = dict(cost=100_000, lease_term_years=5, borrow_rate_pct=7, tax_rate_pct=26.5, cca_rate_pct=30,
                salvage_value=15_000, acquired="2026-06-01", available_for_use="2026-07-01")
    r = lease.lease_vs_buy(lease_payment=2_000, **args)
    assert r["decision"] == "buy" and r["first_year_cca"]["factor"] == 1.5
    be = lease.lease_vs_buy(lease_payment=r["breakeven_lease_payment"], **args)
    assert be["net_advantage_to_leasing"] == pytest.approx(0, abs=0.5)    # break-even is rounded to cents
    assert lease.lease_vs_buy(lease_payment=1_500, **args)["decision"] == "lease"


def test_after_tax_rate_makes_loan_financing_npv_zero():
    # why the after-tax rate: a loan's after-tax flows (payment less interest tax saving) discount back to the loan
    T, rows = 0.265, unsecured.amortize(100_000, 0.07 / 12, 60)
    i = 0.07 / 12 * (1 - T)
    pv = sum((r["payment"] - r["interest"] * T) / (1 + i) ** r["period"] for r in rows)
    assert pv == pytest.approx(100_000, abs=1e-6)


# ------------------------------------------------------------------ parameters and tool wiring
def test_verified_parameters_have_sources_and_dates():
    for group in (params.CSBFP, params.CRIMINAL_RATE, params.CCA):
        for p in group.values():
            assert p["source"].startswith("https://") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["checked"])
    assert params.val(params.CRIMINAL_RATE, "general_cap_apr_pct") == 35.0


TOOL_NAMES = [t.name for t in BM.TOOLS]


def test_tools_registered_with_engine_and_provenance():
    assert len(TOOL_NAMES) == 10 and all(n in T.TOOLS for n in TOOL_NAMES)
    calls = {
        "csbfp_assess": {"gross_annual_revenue": 2e6, "request": {"equipment": 100_000}},
        "csbfp_term_loan": {"amount": 100_000, "annual_rate_pct": 7, "years": 5, "prime_pct": 4.45},
        "csbfp_line_of_credit": {"authorized": 100_000, "average_drawn": 40_000, "annual_rate_pct": 9, "prime_pct": 4.45},
        "invoice_factoring": {"face": 10_000, "days_to_collect": 30, "advance_rate_pct": 85, "fee_pct": 2},
        "unsecured_term_loan": {"principal": 25_000, "annual_rate_pct": 15, "years": 2},
        "business_line_of_credit": {"limit": 50_000, "average_drawn": 25_000, "annual_rate_pct": 10},
        "merchant_cash_advance": {"advance": 30_000, "factor_rate": 1.3, "expected_remittance_days": 100},
        "criminal_rate_check": {"apr_pct": 36, "credit_advanced": 8_000},
        "business_dscr": {"net_income": 150_000, "existing_business_debt_service": 40_000},
        "equipment_lease_vs_buy": {"cost": 50_000, "lease_payment": 1_000, "lease_term_years": 4, "borrow_rate_pct": 8,
                                   "tax_rate_pct": 26.5, "cca_rate_pct": 20},
    }
    for name, args in calls.items():
        out = T.run(name, args)
        assert "error" not in out, (name, out)
        assert out["engine"].startswith("business.")
        assert "source" in out or "assumptions" in out or "criminal_rate" in out
    assert T.run("criminal_rate_check", calls["criminal_rate_check"])["exceeds_criminal_rate"] is True


def test_router_offers_desk_tools_under_commercial():
    from decision_ladder.agent.router import stage_tools
    st = stage_tools()
    assert set(TOOL_NAMES) <= st["commercial"]
    assert "criminal_rate_check" in st["compliance"] and "business_dscr" in st["underwriting"]


def test_tool_errors_are_reported_not_raised():
    assert "error" in T.run("invoice_factoring", {"advance_rate_pct": 80})
    assert "missing" in T.run("unsecured_term_loan", {"principal": 1})["error"]
    assert "error" in T.run("csbfp_term_loan", {"amount": 1e5, "annual_rate_pct": 7, "years": 20, "prime_pct": 4})
    led = T.run("invoice_factoring", {"invoices": [{"face": 5_000, "days_to_collect": 30}], "advance_rate_pct": 80,
                                      "fee_pct": 1.5})
    assert led["invoices"] == 1 and math.isfinite(led["apr_pct"])
