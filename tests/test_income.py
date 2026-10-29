"""Income & Rental Qualification Desk: hand-checked figures, method comparisons, declining income, edge cases."""
import re
from pathlib import Path

import pytest

import decision_ladder.modules.income as IM
from decision_ladder.agent import router, tools as T
from decision_ladder.engines import qualify
from decision_ladder.income import params as P, portfolio, rental, solve, sources
from decision_ladder.income.rental import Property


def src(**kw):
    return sources.qualify_source(kw)


# ------------------------------------------------------------------ parameters
def test_verified_figures_match_the_qualify_engine_and_cite_sources():
    assert P.VERIFIED["qualifying_rate_floor_pct"]["value"] == 5.25 == qualify.MIN_QUALIFYING_RATE
    assert (P.VERIFIED["gds_limit_pct"]["value"], P.VERIFIED["tds_limit_pct"]["value"]) == (39.0, 44.0)
    assert qualify.qualifying_rate(2.99) == 5.25 and qualify.qualifying_rate(4.5) == 6.5
    for v in P.VERIFIED.values():
        assert v["source"].startswith("https://") and v["checked"] == P.CHECKED
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", v["checked"])


def test_policy_overrides_and_typos():
    pol = P.policy({"offset_pct": 100, "addback_pct": None})
    assert pol["offset_pct"] == 100 and pol["addback_pct"] == 50.0
    with pytest.raises(ValueError, match="offset_pc"):
        P.policy({"offset_pc": 90})
    assert all("lender policy, varies" in s for s in P.assumptions(pol, ["offset_pct", "min_dscr"]).values())


# ------------------------------------------------------------------ qualifying income by source
def test_salary_and_hourly():
    assert src(type="salary", annual_amount=92000)["qualifying_annual"] == 92000
    h = src(type="hourly", hourly_rate=31.5, guaranteed_hours_per_week=37.5)
    assert h["qualifying_annual"] == 61425.0                         # 31.50 x 37.5 x 52
    with pytest.raises(ValueError, match="guaranteed"):
        src(type="hourly", hourly_rate=31.5)


def test_variable_income_rising_uses_average_and_declining_uses_lower_year():
    up = src(type="bonus", history=[5000, 8000, 10000])              # last two: (8000 + 10000) / 2
    assert up["qualifying_annual"] == 9000 and not up["flags"]
    down = src(type="commission", history=[15000, 9000])             # 9000 < 15000: 40% lower
    assert down["qualifying_annual"] == 9000
    assert "declining" in down["flags"][0] and "40.0%" in down["flags"][0]
    assert "T4s and NOAs" in down["documents"][0]


def test_variable_income_needs_two_years_unless_policy_allows_one():
    one = src(type="overtime", history=[12000])
    assert one["qualifying_annual"] == 0 and "less than 2 years" in one["flags"][0]
    pol = P.policy({"variable_min_years": 1})
    assert sources.qualify_source({"type": "overtime", "history": [12000]}, pol)["qualifying_annual"] == 12000


def test_self_employed_add_backs_average():
    r = src(type="self_employed", years=[{"net_income": 60000, "cca": 4000, "business_use_of_home": 2000},
                                         {"net_income": 70000, "cca": 3000, "business_use_of_home": 2400}])
    # 60000 + 4000 + 2000 = 66000 ; 70000 + 3000 + 2400 = 75400 ; average 70700
    assert r["qualifying_annual"] == 70700 and "add-backs" in r["method"]


def test_self_employed_gross_up_and_lender_specific_flag():
    yrs = [{"net_income": 60000}, {"net_income": 70000}]
    assert src(type="self_employed", years=yrs, income_method="gross_up")["qualifying_annual"] == 74750  # 65000 x 1.15
    alt = src(type="self_employed", years=yrs, income_method="gross_up", gross_up_pct=25)
    assert alt["qualifying_annual"] == 81250 and "lender-specific" in alt["flags"][0]                     # 65000 x 1.25
    with pytest.raises(ValueError):
        src(type="self_employed", years=yrs, income_method="stated")


def test_self_employed_declining_and_short_history():
    r = src(type="self_employed", years=[{"net_income": 80000}, {"net_income": 60000}], months_in_business=18)
    assert r["qualifying_annual"] == 60000
    assert any("declining" in f for f in r["flags"]) and any("18 months" in f for f in r["flags"])
    loss = src(type="self_employed", years=[{"net_income": -5000}, {"net_income": -1000}])
    assert loss["qualifying_annual"] == 0                             # losses never qualify as negative income


def test_support_court_order_continuity_and_ccb_policy():
    assert src(type="child_support", annual_amount=9600)["qualifying_annual"] == 0
    assert src(type="child_support", annual_amount=9600, court_order=True)["qualifying_annual"] == 9600
    short = src(type="spousal_support", annual_amount=12000, court_order=True, years_remaining=2)
    assert short["qualifying_annual"] == 0 and "within 3 years" in short["flags"][0]
    assert src(type="ccb", annual_amount=7200)["qualifying_annual"] == 0
    pol = P.policy({"include_ccb": True, "nontaxable_gross_up_pct": 25})
    assert sources.qualify_source({"type": "ccb", "annual_amount": 7200}, pol)["qualifying_annual"] == 9000  # x 1.25


def test_pension_government_probation_and_unknown_type():
    assert src(type="cpp", annual_amount=9000)["documents"][0].startswith("T4A(P)")
    assert src(type="pension", annual_amount=30000)["qualifying_annual"] == 30000
    assert "probation" in src(type="salary", annual_amount=70000, probation=True)["flags"][0]
    assert "renewal" in src(type="contract", history=[70000, 72000], months_remaining=3)["flags"][0]
    with pytest.raises(ValueError, match="unknown income type"):
        src(type="lottery", annual_amount=1)


def test_qualifying_income_total_and_reduced_sources():
    r = sources.qualifying_income([{"type": "salary", "annual_amount": 100000},
                                   {"type": "bonus", "history": [12000, 8000], "annual_amount": 8000},
                                   {"type": "child_support", "label": "support", "annual_amount": 6000}])
    assert r["total_qualifying_annual"] == 108000                    # 100000 + 8000 + 0 (no court order)
    assert r["excluded_or_reduced"] == ["support"] and len(r["flags"]) == 2
    with pytest.raises(ValueError):
        sources.qualifying_income([])


# ------------------------------------------------------------------ rental methods
HOME = {"name": "home", "owner_occupied": True, "payment_monthly": 2000, "taxes_annual": 4800, "heat_annual": 1200}
RENTAL = {"name": "rental", "payment_monthly": 1800, "taxes_annual": 2400, "condo_fees_monthly": 400,
          "rent_monthly": 2500, "t776_net_income": 6000, "cca_claimed": 1500, "mortgage_interest_annual": 12000}
# home PITH = 2000 + 400 + 100 = 2500 ; rental PITH = 1800 + 200 + 0 + 50% x 400 = 2200 ; income 10,000/month


def test_add_back_hand_checked():
    r = rental.ratios(120000, [HOME, RENTAL], method="add_back", other_debt_monthly=500)
    assert r["qualifying_income_annual"] == 135000                    # + 50% x 2500 x 12
    assert r["gds"] == pytest.approx(22.22, abs=0.01)                 # 2500 / 11250
    assert r["tds"] == pytest.approx(46.22, abs=0.01)                 # (2500 + 2200 + 500) / 11250
    assert not r["passes"] and r["housing_capacity_monthly"] == -250  # 0.44 x 11250 - 5200


def test_offset_hand_checked():
    r = rental.ratios(120000, [HOME, RENTAL], method="offset", other_debt_monthly=500)
    assert r["rental_liabilities_monthly"] == 200                     # 2200 - 80% x 2500
    assert (r["gds"], r["tds"]) == (25.0, 32.0)                       # 2500/10000 ; (2500 + 200 + 500)/10000
    assert r["housing_capacity_monthly"] == 1200                      # min(3900 - 2500, 4400 - 3200)


def test_net_rental_hand_checked_t776_and_pro_forma():
    r = rental.ratios(120000, [HOME, RENTAL], method="net_rental", other_debt_monthly=500)
    assert r["rental_income_added_annual"] == 19500                   # 6000 + 1500 CCA + 12000 interest
    assert r["tds"] == pytest.approx(41.29, abs=0.01)                 # (2500 + 1800 + 500) / 11625
    assert r["housing_capacity_monthly"] == 315                       # 0.44 x 11625 - 4800
    pro = {**RENTAL, "t776_net_income": None, "other_expenses_annual": 1000}
    # 30000 rent - 2400 tax - 4800 condo (100%) - 1000 other; interest added back
    assert Property.from_dict(pro).net_rent_annual(True) == 21800
    assert Property.from_dict(pro).net_rent_annual(False) == 21800 - 12000


def test_compare_methods_picks_most_room():
    c = rental.compare_methods(120000, [HOME, RENTAL], other_debt_monthly=500)
    assert c["best_method"] == "offset" and c["qualifies_under"] == ["offset", "net_rental"]
    assert {s["method"] for s in c["summary"]} == set(rental.METHODS)
    assert "lender policy, varies" in c["assumptions"]["offset_pct"]


def test_policy_variants_tax_heat_exclusion_and_offset_surplus():
    r = rental.ratios(120000, [HOME, RENTAL], method="add_back", other_debt_monthly=500,
                      policy={"addback_excludes_tax_heat": True})
    assert r["rental_liabilities_monthly"] == 2000                    # 1800 P&I + 50% x 400 condo
    rich = {**RENTAL, "rent_monthly": 3000}                           # 80% x 3000 = 2400 > 2200 PITH
    assert rental.ratios(120000, [rich], method="offset")["qualifying_income_annual"] == 120000
    s = rental.ratios(120000, [rich], method="offset", policy={"offset_surplus_to_income": True})
    assert s["rental_income_added_annual"] == 2400                    # 200/month surplus x 12


def test_owner_occupied_suite_rent():
    home = {**HOME, "rent_monthly": 1000}
    assert rental.ratios(120000, [home], method="offset")["gds_housing_monthly"] == 1700       # 2500 - 800
    for m in ("add_back", "net_rental"):                                                       # 50% x 12000
        assert rental.ratios(120000, [home], method=m)["rental_income_added_annual"] == 6000


def test_new_mortgage_stress_test_and_year_one_interest():
    def pmt(p, rate, years):
        i = (1 + rate / 200) ** (1 / 6) - 1
        return p * i / (1 - (1 + i) ** -(years * 12))
    new = Property(balance=400000, rate=3.0, amort_years=25, new_mortgage=True)
    old = Property(balance=400000, rate=3.0, amort_years=25)
    assert new.pi_monthly() == pytest.approx(pmt(400000, 5.25, 25), abs=0.01)   # floor 5.25 > 3 + 2
    assert old.pi_monthly() == pytest.approx(pmt(400000, 3.0, 25), abs=0.01)
    bal, i, interest = 400000.0, (1 + 0.015) ** (1 / 6) - 1, 0.0
    for _ in range(12):
        interest += bal * i
        bal -= pmt(400000, 3.0, 25) - bal * i
    assert old.interest_year1() == pytest.approx(interest, abs=0.01)
    assert new.interest_year1() == old.interest_year1()               # interest is paid at the contract rate


def test_ratio_edge_cases():
    assert rental.ratios(0, [RENTAL], method="offset")["passes"] is False
    with pytest.raises(ValueError, match="unknown property fields"):
        Property.from_dict({"name": "x", "rnet": 1})
    with pytest.raises(ValueError):
        Property.from_dict({"balance": -1})
    with pytest.raises(ValueError):
        rental.ratios(1, [RENTAL], method="gross")
    with pytest.raises(ValueError):
        rental.compare_methods(100000, [])


# ------------------------------------------------------------------ portfolio
R1 = {"name": "r1", "value": 500000, "balance": 350000, "rent_monthly": 3000, "taxes_annual": 3600,
      "other_expenses_annual": 2400, "payment_monthly": 2000}
R2 = {"name": "r2", "value": 400000, "balance": 300000, "rent_monthly": 1800, "taxes_annual": 3000,
      "other_expenses_annual": 1800, "payment_monthly": 1900}


def test_portfolio_ltv_noi_dscr_hand_checked():
    a = portfolio.analyze([R1, R2])
    p1, p2 = a["properties"]
    assert (p1["ltv_pct"], p1["noi"], p1["dscr"], p1["cash_flow_monthly"]) == (70.0, 30000, 1.25, 500)
    # r2: NOI 21600 - 3000 - 1800 = 16800 ; ADS 22800 ; DSCR 0.737
    assert p2["noi"] == 16800 and p2["dscr"] == pytest.approx(0.737, abs=0.001) and p2["below_min_dscr"]
    assert a["portfolio"]["ltv_pct"] == pytest.approx(72.22, abs=0.01)           # 650000 / 900000
    assert a["portfolio"]["total_annual_debt_service"] == 46800
    assert a["portfolio"]["rental_dscr"] == 1.0                          # NOI 46800 / ADS 46800
    assert a["below_min_dscr"] == ["r2"] and "ratios" not in a


def test_portfolio_vacancy_and_owner_occupied():
    a = portfolio.analyze([R1, HOME], policy={"vacancy_pct": 5})
    assert a["properties"][0]["noi"] == 28200                         # 36000 x 0.95 - 3600 - 2400
    assert a["properties"][1]["dscr"] is None and a["portfolio"]["rentals"] == 1


def test_portfolio_tds_drag_leave_one_out():
    a = portfolio.analyze([R1, R2], income_annual=120000, method="offset")
    # r1: 2300 PITH - 2400 offset = surplus (ignored) ; r2: 2150 - 1440 = 710 shortfall
    assert a["ratios"]["tds"] == 7.1
    drag = {d["name"]: d for d in a["tds_drag"]}
    assert drag["r2"]["tds_impact_pts"] == 7.1 and drag["r1"]["tds_impact_pts"] == 0
    assert a["drags_tds"] == ["r2"]


# ------------------------------------------------------------------ solvers
BUYER = dict(income_annual=120000, down_payment=150000, contract_rate=4.5, property_tax_rate_pct=1.0)


def test_max_price_without_rent_matches_qualify_boundary():
    r = solve.max_purchase_price(**BUYER)
    prices = {v["max_price"] for v in r["results"].values()}
    assert len(prices) == 1                                           # no rent: methods cannot differ
    best = prices.pop()

    def q(p):
        return qualify.qualify(price=p, down_payment=150000, annual_income=120000, contract_rate=4.5,
                               property_tax_annual=p * 0.01, heat_annual=1800)
    assert q(best).passes and not q(best + 1000).passes
    assert r["results"]["offset"]["qualifying_rate"] == 6.5


def test_max_price_subject_rent_raises_the_ceiling():
    base = solve.max_purchase_price(**BUYER, method="add_back")["max_price"]
    with_suite = solve.max_purchase_price(**BUYER, method="add_back", rent_monthly=1500)["max_price"]
    assert with_suite > base


def test_max_price_investment_purchase_needs_twenty_percent():
    r = solve.max_purchase_price(income_annual=250000, down_payment=100000, contract_rate=4.5, owner_occupied=False,
                                 rent_monthly=3500, method="offset")
    assert r["max_price"] <= 500000                                   # 100000 / 20%
    poor = solve.max_purchase_price(income_annual=3000, down_payment=50000, contract_rate=4.5)
    assert poor["max_price"] is None and poor["best_method"] is None
    with pytest.raises(ValueError):
        solve.max_purchase_price(**BUYER, method="gross")


def test_existing_rentals_change_max_price_by_method():
    r = solve.max_purchase_price(**BUYER, properties=[RENTAL])
    res = r["results"]
    assert res["offset"]["max_price"] > res["add_back"]["max_price"]
    assert r["best_method"] == max(res, key=lambda m: res[m]["max_price"] or 0)


def test_rent_needed_hand_checked():
    home = {**HOME}
    rent = {k: v for k, v in RENTAL.items() if k not in ("t776_net_income", "cca_claimed")}
    r = solve.rent_needed(income_annual=120000, properties=[home, rent], target="rental", other_debt_monthly=500)
    res = r["results"]
    # offset: 2500 + 500 + (2200 - 0.8R) <= 4400  -> R >= 1000
    assert 1000 <= res["offset"]["min_rent_monthly"] <= 1001
    # add-back: 5200 <= 0.44 x (10000 + 0.5R)    -> R >= 3636.36
    assert res["add_back"]["min_rent_monthly"] == 3637
    # net (pro forma, interest added back): 4800 <= 0.44 x (10000 + R - 600) -> R >= 1509.09
    assert res["net_rental"]["min_rent_monthly"] == 1510
    assert r["most_forgiving_method"] == "offset" and res["add_back"]["shortfall_monthly"] == 1137
    with pytest.raises(ValueError, match="no property"):
        solve.rent_needed(income_annual=1, properties=[rent], target="nope")


# ------------------------------------------------------------------ tools, routing, desk page
def test_tools_registered_and_routed():
    from decision_ladder.agent.router import stage_tools
    st = stage_tools()
    for t in IM.TOOLS:
        assert T.TOOLS[t.name] is t and router.CORE_STAGE[t.name] == ["prequal", "underwriting"]
        assert t.name in st["prequal"] and t.name in st["underwriting"]


def test_tool_results_carry_engine_method_and_sources():
    calls = {
        "income_qualifying": {"income_sources": [{"type": "salary", "annual_amount": 90000}]},
        "rental_method_compare": {"annual_income": 120000, "properties": [HOME, RENTAL], "other_debt_monthly": 500},
        "rental_portfolio": {"properties": [R1, R2], "annual_income": 120000},
        "income_max_purchase": {"annual_income": 120000, "down_payment": 150000, "contract_rate": 4.5},
        "rental_rent_needed": {"annual_income": 120000, "properties": [HOME, RENTAL], "target": "rental"},
        "income_policy_reference": {},
    }
    assert set(calls) == {t.name for t in IM.TOOLS}
    for name, args in calls.items():
        r = T.run(name, args)
        assert "error" not in r, (name, r)
        assert r["engine"].startswith("income.") and r["method"] and r["source"]
        assert all(s["url"].startswith("https://") and s["checked"] == P.CHECKED for s in r["source"])


def test_tool_income_sources_flow_through_and_errors():
    srcs = [{"type": "salary", "annual_amount": 100000}, {"type": "bonus", "history": [30000, 10000]}]
    via = T.run("rental_method_compare", {"income_sources": srcs, "properties": [RENTAL]})
    direct = T.run("rental_method_compare", {"annual_income": 110000, "properties": [RENTAL]})
    assert via["results"] == direct["results"] and via["income"]["total_qualifying_annual"] == 110000
    assert "error" in T.run("rental_method_compare", {"properties": [RENTAL]})
    assert "error" in T.run("income_qualifying", {"income_sources": [{"type": "salary"}], "policy": {"bogus": 1}})


def test_desk_page_loads_external_script_calling_real_tools():
    d = Path(__file__).resolve().parent.parent / "decision_ladder" / "web" / "static" / "desks"
    html, js = (d / "income.html").read_text(encoding="utf-8"), (d / "income.js").read_text(encoding="utf-8")
    assert '<script src="income.js"></script>' in html
    assert not re.search(r"<script>(?!\s*</script>)", html) and not re.search(r"\son[a-z]+=", html)
    assert "/api/tool" in js
    assert set(re.findall(r'tool: "([a-z_]+)"', js)) <= set(T.TOOLS)
