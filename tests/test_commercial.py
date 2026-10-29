"""Commercial Lending Desk: hand-checked numbers, binding constraints and edge cases."""
import re
from pathlib import Path

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.commercial import bridge, cmhc, construction, rentroll, underwriting
from decision_ladder.commercial.common import debt_constant, irr, loan_for_debt_service, monthly_payment
from decision_ladder.modules import commercial as M  # noqa: F401  (registers the tools)

DESK = Path(__file__).resolve().parent.parent / "decision_ladder" / "web" / "static" / "desks" / "commercial.html"
TOOL_NAMES = ["commercial_underwrite", "cmhc_mli_size", "cmhc_mli_select_points", "construction_draw_schedule",
              "private_bridge_cost", "rent_roll_analysis"]


def semi_monthly(rate_pct):
    return (1 + rate_pct / 200) ** (1 / 6) - 1


# ------------------------------------------------------------------ common maths
def test_semi_annual_payment_matches_published_table():
    # 5% fixed, 25 years: $581.60 per $100,000 (standard Canadian payment table)
    assert monthly_payment(100_000, 5.0, 25) == pytest.approx(581.60, abs=0.01)


def test_loan_for_debt_service_inverts_the_constant():
    k = debt_constant(6.0, 30)
    assert loan_for_debt_service(120_000, 6.0, 30) * k == pytest.approx(120_000)
    io = debt_constant(6.0, 30, interest_only=True)
    assert io == pytest.approx(semi_monthly(6.0) * 12)
    with pytest.raises(ValueError):
        loan_for_debt_service(1000, 0.0, 25, interest_only=True)


def test_irr_on_known_bond():
    # pay 95 for 1 period, receive 100: 5.263%
    assert irr([-95, 100]) == pytest.approx(100 / 95 - 1)
    with pytest.raises(ValueError):
        irr([100, 50])


# ------------------------------------------------------------------ conventional underwriting
def test_noi_from_expense_ratio():
    inc = underwriting.noi(gross_potential_rent=600_000, vacancy_pct=3, expense_ratio_pct=35)
    assert inc["effective_gross_income"] == 582_000
    assert inc["total_expenses"] == pytest.approx(203_700)
    assert inc["noi"] == pytest.approx(378_300)


def test_noi_itemized_with_management_and_reserves():
    inc = underwriting.noi(gross_potential_rent=200_000, other_income=5_000, vacancy_pct=5,
                           expenses={"taxes": 20_000, "insurance": 6_000, "utilities": 14_000},
                           management_pct=4, reserves_per_unit=300, units=12)
    egi = 200_000 * 0.95 + 5_000
    assert inc["effective_gross_income"] == pytest.approx(egi)
    assert inc["total_expenses"] == pytest.approx(40_000 + egi * 0.04 + 3_600)
    assert inc["noi"] == pytest.approx(egi - 40_000 - egi * 0.04 - 3_600)
    with pytest.raises(ValueError):
        underwriting.noi(gross_potential_rent=100_000)


def test_dscr_binding_back_solves_to_the_floor():
    r = underwriting.size_loan(noi=378_300, contract_rate=5.0, value=8_000_000)
    assert r["binding_constraint"] == "dscr"
    loan = r["max_loan"]
    ads = monthly_payment(loan, 5.0, 25) * 12            # recompute independently of the engine
    assert 378_300 / ads == pytest.approx(1.25, abs=1e-4)
    assert r["constraints"]["ltv"] == 6_000_000
    assert r["constraints"]["debt_yield"] == pytest.approx(378_300 / 0.08)
    assert r["noi_cushion_pct"] == pytest.approx(20.0, abs=0.01)   # 1 - 1/1.25


def test_ltv_binding_when_noi_is_strong():
    r = underwriting.size_loan(noi=900_000, contract_rate=5.0, value=8_000_000)
    assert r["binding_constraint"] == "ltv" and r["max_loan"] == 6_000_000
    assert r["dscr"] > 1.25 and r["ltv_pct"] == 75.0


def test_debt_yield_binding_at_low_rate_long_amortization():
    r = underwriting.size_loan(noi=500_000, contract_rate=2.0, value=20_000_000, amort_years=30)
    assert r["binding_constraint"] == "debt_yield"
    assert r["max_loan"] == pytest.approx(500_000 / 0.08)
    assert r["debt_yield_pct"] == pytest.approx(8.0)


def test_debt_yield_test_can_be_switched_off():
    r = underwriting.size_loan(noi=500_000, contract_rate=2.0, value=20_000_000, amort_years=30, debt_yield_min_pct=0)
    assert "debt_yield" not in r["constraints"] and r["binding_constraint"] == "dscr"


def test_interest_only_sizing():
    r = underwriting.size_loan(noi=300_000, contract_rate=6.0, value=10_000_000, interest_only=True,
                               debt_yield_min_pct=0)
    expect = 300_000 / 1.25 / (semi_monthly(6.0) * 12)
    assert r["max_loan"] == pytest.approx(expect, abs=0.01)
    assert r["balance_at_term_end"] == pytest.approx(expect, abs=0.01)


def test_qualifying_rate_above_contract_leaves_headroom():
    r = underwriting.size_loan(noi=400_000, contract_rate=5.0, qualifying_rate=7.0, value=9_000_000, debt_yield_min_pct=0)
    assert r["dscr_at_qualifying_rate"] == pytest.approx(1.25, abs=1e-3)
    assert r["dscr"] > 1.4
    assert r["max_rate_meeting_dscr_pct"] == pytest.approx(7.0, abs=0.01)


def test_requested_loan_shortfall_and_cap_rate_value():
    r = underwriting.size_loan(noi=500_000, contract_rate=5.5, cap_rate_pct=5.0, requested_loan=8_000_000)
    assert r["value"] == pytest.approx(10_000_000)
    assert not r["requested_fits"]
    assert r["shortfall"] == pytest.approx(8_000_000 - r["max_loan"], abs=0.01)
    assert set(r["failed_constraints"]) >= {"ltv", "dscr"}
    assert r["max_rate_meeting_dscr_pct"] is not None and r["max_rate_meeting_dscr_pct"] < 5.5


def test_balloon_matches_payments_engine():
    r = underwriting.size_loan(noi=300_000, contract_rate=4.5, value=6_000_000, requested_loan=3_000_000, term_years=5)
    i, n = semi_monthly(4.5), 60
    pmt = monthly_payment(3_000_000, 4.5, 25)
    assert r["balance_at_term_end"] == pytest.approx(3_000_000 * (1 + i) ** n - pmt * ((1 + i) ** n - 1) / i, abs=0.01)


def test_size_loan_needs_value_or_cap_rate():
    with pytest.raises(ValueError):
        underwriting.size_loan(noi=100_000, contract_rate=5)


# ------------------------------------------------------------------ CMHC MLI Select
def test_points_existing_with_20_year_bonus():
    s = cmhc.score(purpose="existing", affordable_units_pct=40, affordability_years=20)
    assert s["points"]["affordability"] == 50 and s["points"]["affordability_20yr_bonus"] == 30
    assert s["total_points"] == 80 and s["tier"]["min_points"] == 70
    assert s["tier"]["max_ltv_pct"] == 95.0 and s["tier"]["max_amort_years"] == 45
    assert s["points_to_next_tier"] == 20


def test_points_new_construction_grids():
    s = cmhc.score(purpose="new_construction", affordable_units_pct=10, energy_reduction_pct=70, energy_standard="nbc",
                   accessibility="level_2")
    assert s["points"] == {"affordability": 50, "affordability_20yr_bonus": 0, "energy_efficiency": 50, "accessibility": 30}
    assert s["tier"]["max_ltc_pct"] == 95.0 and s["tier"]["recourse"] == "limited recourse"
    # 60% better than NBC is only 35 points (NECB 60% would be 50)
    assert cmhc.score(purpose="new_construction", energy_reduction_pct=60, energy_standard="nbc")["points"]["energy_efficiency"] == 35
    assert cmhc.score(purpose="new_construction", energy_reduction_pct=60)["points"]["energy_efficiency"] == 50


def test_points_short_commitment_earns_no_affordability():
    s = cmhc.score(affordable_units_pct=80, affordability_years=5)
    assert s["points"]["affordability"] == 0 and s["tier"] is None and s["notes"]
    with pytest.raises(ValueError):
        cmhc.score(accessibility="gold")


def test_premium_rates():
    std = cmhc.premium_rate(ltv_pct=80, amort_years=40, construction=False)
    assert std["premium_pct"] == pytest.approx(4.35 + 0.75)
    sel = cmhc.premium_rate(ltv_pct=92, amort_years=45, construction=True, points=70)
    assert sel["premium_pct"] == pytest.approx((7.00 + 1.00) * 0.8)
    assert cmhc.premium_rate(ltv_pct=65, amort_years=25, construction=False)["amort_surcharge_pct"] == 0
    with pytest.raises(ValueError):
        cmhc.premium_rate(ltv_pct=96, amort_years=25, construction=False)


def test_mli_dcr_binding_back_solve():
    r = cmhc.size(noi=400_000, value=8_000_000, rate=4.0, units=30)
    std = r["standard"]
    assert std["binding_constraint"] == "dcr"
    ads = monthly_payment(std["total_loan"], 4.0, 40) * 12
    assert 400_000 / ads == pytest.approx(1.20, abs=1e-4)
    p = std["premium_detail"]["premium_pct"]
    assert std["total_loan"] == pytest.approx(std["base_loan"] * (1 + p / 100), abs=0.02)
    assert r["select"] is None and r["best"] == "MLI Standard"


def test_mli_select_beats_standard_and_respects_caps():
    r = cmhc.size(noi=400_000, value=8_000_000, rate=4.0, units=30, affordable_units_pct=40,
                  energy_reduction_pct=25, accessibility="level_1")
    sel = r["select"]
    assert r["score"]["total_points"] == 105 and sel["amort_years"] == 50
    assert sel["premium_detail"]["select_discount_pct"] == 30
    assert sel["base_loan"] <= 0.95 * 8_000_000
    ads = monthly_payment(sel["total_loan"], 4.0, 50) * 12
    assert 400_000 / ads >= 1.10 - 1e-4
    assert r["best"].startswith("MLI Select") and r["extra_proceeds_vs_standard"] > 0


def test_mli_ltv_binding_with_strong_noi():
    r = cmhc.size(noi=2_000_000, value=10_000_000, rate=4.0, units=40)
    assert r["standard"]["binding_constraint"] == "ltv"
    assert r["standard"]["base_loan"] == pytest.approx(8_500_000)
    assert r["standard"]["premium_detail"]["ltv_band_max_pct"] == 85


def test_mli_premium_band_edge_lands_on_band_ceiling():
    # DCR room for 845,000 total: at the 80% band premium (5.10%) the base could be 804k, but crossing 80% LTV moves
    # the premium to 6.10% and only 796k fits, so the best base loan sits exactly on the 80% band ceiling.
    k = debt_constant(4.0, 40)
    r = cmhc.size(noi=845_000 * k * 1.20, value=1_000_000, rate=4.0, units=6)
    assert r["standard"]["base_loan"] == pytest.approx(800_000, abs=0.01)
    assert r["standard"]["premium_detail"]["premium_pct"] == pytest.approx(5.10)


def test_mli_requested_loan_and_minimum_units():
    r = cmhc.size(noi=2_000_000, value=10_000_000, rate=4.0, units=40, requested_loan=5_000_000)
    assert r["standard"]["base_loan"] == 5_000_000 and r["standard"]["requested_fits"]
    with pytest.raises(ValueError):
        cmhc.size(noi=100_000, value=1_000_000, rate=4.0, units=4)


def test_mli_sources_dated():
    assert cmhc.SOURCES["checked"] == "2026-10-29"
    assert all(u.startswith("https://") for k, u in cmhc.SOURCES.items() if k != "checked")


# ------------------------------------------------------------------ construction
def test_interest_reserve_hand_calc():
    r = construction.schedule(budget=[{"item": "build", "cost": 120_000, "start_month": 1, "end_month": 1}],
                              rate_pct=12.0, equity=0, holdback_pct=0, release_lag_months=0, term_months=3,
                              max_ltc_pct=100)
    # month 1 draw 120,000; month 2 interest 1,200; month 3 interest 1,212
    assert r["interest_reserve"] == pytest.approx(2_412.0)
    assert r["loan_amount"] == pytest.approx(122_412.0)
    assert r["ltc_pct"] == 100.0


def test_holdback_retained_and_released_at_completion():
    r = construction.schedule(budget=[{"cost": 1_000_000, "start_month": 1, "end_month": 10}], rate_pct=0, equity=0,
                              annual_release=False, max_ltc_pct=100)
    rows = {x["month"]: x for x in r["draws"]}
    assert rows[1]["holdback_retained"] == 10_000 and rows[1]["cash_out"] == 90_000
    assert rows[12]["holdback_released"] == 100_000
    assert r["holdback"]["peak_retained"] == 100_000 and r["loan_amount"] == 1_000_000


def test_annual_holdback_release():
    r = construction.schedule(budget=[{"cost": 2_400_000, "start_month": 1, "end_month": 24}], rate_pct=0, equity=0,
                              max_ltc_pct=100)
    rows = {x["month"]: x for x in r["draws"]}
    assert rows[16]["holdback_released"] == pytest.approx(120_000)      # year 1 accrual at anniversary + 3 months
    assert rows[26]["holdback_released"] == pytest.approx(120_000)      # year 2 remainder at completion + 2 months
    assert sum(x["holdback_released"] for x in r["draws"]) == pytest.approx(240_000)
    assert r["holdback"]["peak_retained"] == pytest.approx(150_000)     # months 13-15 accrue before the release


def test_annual_release_lowers_interest():
    args = dict(budget=[{"cost": 6_000_000, "start_month": 1, "end_month": 24}], rate_pct=8.0, equity=0, max_ltc_pct=100)
    on, off = construction.schedule(**args), construction.schedule(**args, annual_release=False)
    assert on["interest_reserve"] > off["interest_reserve"]     # released earlier, so drawn earlier
    assert on["hard_costs"] == off["hard_costs"]


def test_equity_first_and_ltc_solve():
    budget = [{"item": "building", "cost": 12_000_000, "start_month": 1, "end_month": 18},
              {"item": "soft", "cost": 1_500_000, "start_month": 1, "end_month": 20, "hard": False}]
    r = construction.schedule(budget=budget, rate_pct=7.2, equity=4_000_000, land_cost=3_000_000, lender_fee=150_000)
    assert r["draws"][0]["equity"] == 3_150_000 and r["draws"][0]["loan_draw_for_costs"] == 0
    assert r["equity_in"] == 4_000_000 and not r["ltc_ok"]
    need = r["equity_required_for_ltc"]
    assert r["equity_shortfall"] == pytest.approx(need - 4_000_000, abs=0.01)
    again = construction.schedule(budget=budget, rate_pct=7.2, equity=need, land_cost=3_000_000, lender_fee=150_000)
    assert again["ltc_pct"] == pytest.approx(75.0, abs=0.01) and again["ltc_ok"]
    assert r["total_project_cost"] == pytest.approx(3_000_000 + 150_000 + 13_500_000 + r["interest_reserve"], abs=0.02)


def test_construction_ltv_on_completion_and_bad_months():
    r = construction.schedule(budget=[{"cost": 1_000_000, "start_month": 1, "end_month": 4}], rate_pct=0, equity=0,
                              completed_value=2_000_000, max_ltv_pct=40, include_rows=False)
    assert r["ltv_on_completion_pct"] == 50.0 and r["ltv_ok"] is False and "draws" not in r
    with pytest.raises(ValueError):
        construction.schedule(budget=[{"cost": 1, "start_month": 5, "end_month": 2}], rate_pct=5, equity=0)
    with pytest.raises(ValueError):
        construction.schedule(budget=[], rate_pct=5, equity=0)


# ------------------------------------------------------------------ bridge / private
def test_no_fees_cost_equals_coupon():
    r = bridge.cost(loan=500_000, rate_pct=9.0, term_months=12)
    assert r["apr_pct"] == pytest.approx(9.0, abs=1e-4)
    assert r["effective_annual_cost_pct"] == pytest.approx(((1 + 0.0075) ** 12 - 1) * 100, abs=1e-4)
    assert r["net_advance"] == 500_000 and r["monthly_interest"] == 3_750


def test_fees_annuity_identity():
    r = bridge.cost(loan=100_000, rate_pct=12.0, term_months=12, lender_fee_pct=2.0)
    j = (1 + r["effective_annual_cost_pct"] / 100) ** (1 / 12) - 1
    # 98,000 = 1,000 x annuity(12, j) + 100,000 x v^12
    pv = 1_000 * (1 - (1 + j) ** -12) / j + 100_000 * (1 + j) ** -12
    assert pv == pytest.approx(98_000, abs=0.5)
    assert r["net_advance"] == 98_000 and r["total_cost_of_borrowing"] == pytest.approx(14_000)


def test_prepaid_interest_and_minimum_interest():
    r = bridge.cost(loan=100_000, rate_pct=12.0, term_months=6, prepaid_interest_months=3)
    assert r["fees"]["prepaid_interest"] == 3_000 and r["net_advance"] == 97_000
    assert r["cash_flows"][1:4] == [0, 0, 0] and r["cash_flows"][4] == -1_000
    m = bridge.cost(loan=100_000, rate_pct=12.0, term_months=12, min_interest_months=3)
    first = m["early_exit"][0]
    assert first["exit_month"] == 1
    # exit after 1 month with 3 months minimum: +100,000 then -(100,000 + 3,000) -> 3% for the month
    assert first["apr_pct"] == pytest.approx(36.0, abs=1e-4)


def test_lender_yield_excludes_broker_fee_and_second_position():
    r = bridge.cost(loan=400_000, rate_pct=10.99, term_months=12, lender_fee_pct=2, broker_fee_pct=1.5, other_costs=2_500,
                    value=1_200_000, prior_balance=600_000)
    assert r["lender_yield_pct"] < r["effective_annual_cost_pct"]
    assert r["position"] == "second" and r["combined_ltv_pct"] == pytest.approx(83.33, abs=0.01)
    assert r["net_advance"] == 400_000 - 8_000 - 6_000 - 2_500


def test_criminal_rate_limits():
    assert bridge.criminal_rate_limit(400_000, natural_person=True, business_purpose=True) == 35.0
    assert bridge.criminal_rate_limit(400_000, natural_person=False, business_purpose=True) == 48.0
    assert bridge.criminal_rate_limit(600_000, natural_person=False, business_purpose=True) is None
    assert bridge.criminal_rate_limit(9_000, natural_person=False, business_purpose=True) == 35.0
    hot = bridge.cost(loan=50_000, rate_pct=18.0, term_months=3, lender_fee_pct=5, natural_person=True)
    assert hot["criminal_rate_flag"] and 1 in hot["early_exits_over_limit"]


def test_semi_compounding_and_validation():
    r = bridge.cost(loan=100_000, rate_pct=8.0, term_months=12, compounding="semi")
    assert r["coupon_effective_annual_pct"] == pytest.approx(8.16, abs=1e-4)
    with pytest.raises(ValueError):
        bridge.cost(loan=100_000, rate_pct=8.0, term_months=0)
    with pytest.raises(ValueError):
        bridge.cost(loan=10_000, rate_pct=8.0, term_months=12, other_costs=10_000)


# ------------------------------------------------------------------ rent roll
LEASES = [{"tenant": "A", "area": 5000, "rent": 150_000, "market_rent": 175_000, "expiry": "2028-06-30"},
          {"tenant": "B", "area": 3000, "rent": 96_000, "market_rent": 90_000, "expiry": "2030-12-31"},
          {"tenant": "C", "area": 2000, "vacant": True, "market_rent": 60_000},
          {"tenant": "D", "area": 1000, "rent": 30_000}]


def test_rent_roll_walt_occupancy_mtm():
    r = rentroll.analyze(LEASES, "2026-10-29")
    ya, yb = (611 / 365.25), (1524 / 365.25)          # days to 2028-06-30 and 2030-12-31
    assert r["walt_years_by_rent"] == pytest.approx((150_000 * ya + 96_000 * yb) / 276_000, abs=0.005)
    assert r["walt_years_by_area"] == pytest.approx((5000 * ya + 3000 * yb) / 9000, abs=0.005)
    assert r["physical_occupancy_pct"] == pytest.approx(9000 / 11000 * 100, abs=0.01)
    assert r["economic_occupancy_pct"] == pytest.approx(276 / 336 * 100, abs=0.01)
    assert r["mark_to_market"]["gap"] == 19_000 and r["mark_to_market"]["below_market"] == 1


def test_rent_roll_rollover_concentration():
    r = rentroll.analyze(LEASES, "2026-10-29")
    years = {x["year"]: x for x in r["rollover"]}
    assert years["2028"]["pct_of_rent"] == pytest.approx(54.35, abs=0.01) and years["2028"]["flag"]
    assert years["month-to-month / expired"]["rent"] == 30_000
    assert r["largest_tenant"]["tenant"] == "A"
    assert not rentroll.analyze(LEASES, "2026-10-29", rollover_flag_pct=60)["rollover"][1]["flag"]


def test_rent_roll_units_weighting_and_expired():
    r = rentroll.analyze([{"tenant": "101", "rent": 24_000, "expiry": "2026-01-31"},
                          {"tenant": "102", "rent": 24_000, "expiry": "2027-10-29"}], "2026-10-29")
    assert r["weighting"] == "units" and r["physical_occupancy_pct"] == 100.0
    assert r["walt_years_by_rent"] == pytest.approx(365 / 365.25 / 2, abs=0.005)
    with pytest.raises(ValueError):
        rentroll.analyze([], "2026-10-29")


# ------------------------------------------------------------------ tool wiring and desk page
def test_tools_registered_with_engine_and_provenance():
    from decision_ladder.agent.router import stage_tools
    assert set(TOOL_NAMES) <= stage_tools()["commercial"]
    for n in TOOL_NAMES:
        assert n in T.TOOLS and T.TOOLS[n].rung == "commercial"
        params = T.TOOLS[n].parameters
        assert set(params["required"]) <= set(params["properties"])
    r = T.run("cmhc_mli_size", {"noi": 400_000, "value": 8_000_000, "rate": 4.0, "units": 30})
    assert r["engine"] == "commercial.cmhc" and r["sources"]["checked"] and r["assumptions"]
    assert T.run("construction_draw_schedule", {"budget": [{"cost": 100, "start_month": 1}], "rate_pct": 5,
                                                "equity": 0})["engine"] == "commercial.construction"


def test_tool_underwrite_from_rent_roll_and_errors():
    r = T.run("commercial_underwrite", {"rent_roll": LEASES, "as_of": "2026-10-29", "vacancy_pct": 5,
                                        "expense_ratio_pct": 30, "contract_rate": 5.5, "cap_rate_pct": 6.5})
    assert r["income"]["gross_potential_rent"] == 336_000 and r["rent_roll"]["flags"]
    assert r["sizing"]["binding_constraint"] in ("ltv", "dscr", "debt_yield")
    assert "error" in T.run("commercial_underwrite", {"contract_rate": 5})
    assert "error" in T.run("private_bridge_cost", {"loan": 1})
    direct = T.run("commercial_underwrite", {"noi": 378_300, "contract_rate": 5.0, "value": 8_000_000})
    assert direct["sizing"]["binding_constraint"] == "dscr"


def test_desk_page_calls_real_tools_with_known_args():
    html = DESK.read_text(encoding="utf-8")
    assert "/api/tool" in DESK.with_suffix(".js").read_text(encoding="utf-8")

    used = set(re.findall(r'data-tool="([a-z_]+)"', html))
    assert used and used <= set(T.TOOLS)
    for tool, field in re.findall(r'data-tool="([a-z_]+)"[^>]*>(.*?)</form>', html, re.S):
        for name in re.findall(r'name="([a-z_]+)"', field):
            assert name in T.TOOLS[tool].parameters["properties"], (tool, name)
