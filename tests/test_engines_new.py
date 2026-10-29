import random

import pytest

from decision_ladder.engines import affordability, insurance, qualify, ratebook, renewal
from decision_ladder.engines.payments import balance_after, payment

FILE = dict(price=900_000, down_payment=90_000, annual_income=150_000, contract_rate=4.29,
            property_tax_annual=6_000, other_debt_monthly=900, amort_years=25)


# ------------------------------------------------------------------ insurance
@pytest.mark.parametrize("ltv,am,rate", [(65, 25, 0.60), (75, 25, 1.70), (80, 25, 2.40), (85, 25, 2.80),
                                         (90, 25, 3.10), (95, 25, 4.00), (95, 30, 4.20), (90.01, 25, 4.00)])
def test_premium_schedule(ltv, am, rate):
    assert insurance.premium_rate(ltv, am) == rate


def test_premium_over_95_rejected():
    with pytest.raises(ValueError):
        insurance.premium_rate(95.5, 25)


def test_premium_example_ontario():
    p = insurance.premium(price=650_000, down_payment=40_000, amort_years=25, province="ON")
    assert p.insured and p.ltv == pytest.approx(93.85, abs=0.01)
    assert p.premium == pytest.approx(610_000 * 0.04)
    assert p.pst_on_premium == pytest.approx(p.premium * 0.08, abs=0.01)
    assert p.total_loan == pytest.approx(610_000 + p.premium)


def test_premium_alberta_has_no_pst():
    assert insurance.premium(price=500_000, down_payment=25_000, province="AB").pst_on_premium == 0


def test_conventional_and_cap():
    assert not insurance.premium(price=800_000, down_payment=160_000).insured
    assert not insurance.premium(price=1_600_000, down_payment=320_000).insured


# ------------------------------------------------------------------ affordability
def test_max_price_passes_and_one_step_above_fails():
    res = affordability.max_purchase_price(FILE)
    assert res["qualification"]["passes"]
    ratio = FILE["property_tax_annual"] / FILE["price"]
    above = res["max_price"] + 2_000
    assert not qualify.qualify(**{**FILE, "price": above, "property_tax_annual": above * ratio}).passes


def test_min_down_payment_respects_legal_minimum():
    res = affordability.min_down_payment_to_pass(FILE)
    assert res["min_down_payment"] >= res["regulatory_minimum"]
    assert qualify.qualify(**{**FILE, "down_payment": res["min_down_payment"]}).passes


def test_min_income():
    res = affordability.min_income_to_pass(FILE)
    assert qualify.qualify(**{**FILE, "annual_income": res["min_annual_income"]}).passes
    assert not qualify.qualify(**{**FILE, "annual_income": res["min_annual_income"] - 2_000}).passes


def test_remediation_when_passing_is_empty():
    ok = {**FILE, "annual_income": 400_000}
    r = affordability.remediation_options(ok)
    assert r["passes_now"] and r["options"] == []


def test_debt_lever_reports_none_when_gds_binds():
    r = affordability.max_other_debt(FILE)
    assert r["max_other_debt_monthly"] is None


def test_remediation_options_are_all_verified():
    r = affordability.remediation_options(FILE)
    for o in r["options"]:
        if "qualification" in o and o.get("lever") != "30_year_amortization":
            assert o["qualification"]["passes"], o


@pytest.mark.parametrize("seed", range(5))
def test_max_price_monotone_in_income(seed):
    rnd = random.Random(seed)
    f = dict(FILE, annual_income=rnd.uniform(90_000, 300_000), contract_rate=rnd.uniform(3, 6))
    lo = affordability.max_purchase_price(f)["max_price"] or 0
    hi = affordability.max_purchase_price({**f, "annual_income": f["annual_income"] * 1.2})["max_price"] or 0
    assert hi >= lo


# ------------------------------------------------------------------ renewal
def test_renewal_shock_consistent_with_payments():
    r = renewal.renewal_shock(original_principal=600_000, original_rate=1.99, original_amort_years=25,
                              months_elapsed=59, renewal_rate=4.84)
    bal = balance_after(600_000, 1.99, 25, 59)
    assert r["balance_at_renewal"] == pytest.approx(bal, abs=0.01)
    assert r["payment_after"] == pytest.approx(payment(bal, 4.84, 25 - 59 / 12), abs=0.01)
    assert r["pct_change"] > 20


def test_renewal_shock_bounds():
    with pytest.raises(ValueError):
        renewal.renewal_shock(original_principal=1, original_rate=2, original_amort_years=25, months_elapsed=0, renewal_rate=3)


def test_offer_comparison_sorts_and_measures():
    r = renewal.offer_comparison(balance=500_000, remaining_amort_years=20, term_years=5,
                                 offers=[{"label": "A", "rate": 4.84}, {"label": "B", "rate": 4.29},
                                         {"label": "C", "rate": 4.29, "fees": 3000}])
    assert r["lowest_net_cost"] == "B"
    by = {o["label"]: o for o in r["offers"]}
    assert by["C"]["extra_cost_vs_best"] == pytest.approx(3000, abs=0.01)
    assert by["A"]["extra_cost_vs_best"] > 0


def test_offer_comparison_requires_offers():
    with pytest.raises(ValueError):
        renewal.offer_comparison(balance=1, remaining_amort_years=1, term_years=1, offers=[])


def test_switch_check_rules():
    base = dict(balance=500_000, remaining_amort_years=20, new_rate=4.5, annual_income=60_000)
    straight = renewal.switch_check(**base)
    assert not straight["would_pass_stress_test"] and straight["can_switch"] and not straight["stress_test_required"]
    more = renewal.switch_check(**base, increases_amount_or_amort=True)
    assert more["stress_test_required"] and not more["can_switch"]
    ins = renewal.switch_check(**base, insured=True, increases_amount_or_amort=True)
    assert not ins["stress_test_required"]


def test_priority_ordering():
    urgent = renewal.renewal_priority(months_to_maturity=1, pct_change=30, balance=800_000)
    later = renewal.renewal_priority(months_to_maturity=11, pct_change=5, balance=200_000)
    assert urgent["score"] > later["score"] and urgent["tier"] == "call this week" and later["tier"] == "watch"


# ------------------------------------------------------------------ rate book
def test_market_snapshot_has_provenance():
    s = ratebook.market_snapshot()
    for k in ("policy_rate", "prime", "big6_typical_posted_5y"):
        assert s[k]["date"] and s[k]["source"]
    assert set(s["goc_curve"]) == {24, 36, 60, 84, 120}
    assert s["fixed_mortgage_spread"]["value_pct_points"] == pytest.approx(
        s["effective_new_lending"]["actual_rate_new_uninsured"][60]["rate"] - s["goc_curve"][60]["rate"], abs=0.005)


def test_point_in_time_lookup_never_looks_ahead():
    r = ratebook.policy_rate("2022-03-01")
    assert r["date"] <= "2022-03-01"


def test_bank_tables_and_aliases():
    assert ratebook.canonical_bank("Royal Bank of Canada") == "RBC"
    assert ratebook.canonical_bank("scotia") == "Scotiabank"
    t = ratebook.bank_posted_table("td")
    assert t["bank"] == "TD" and 60 in t["posted"]
    assert all(p["kind"] in ("captured", "gap_fill") for p in t["provenance"].values())
    with pytest.raises(ValueError):
        ratebook.bank_posted_table("Not A Bank")


def test_rate_change_and_history():
    ch = ratebook.rate_change("policy_rate", start="2022-01-01", end="2023-12-31")
    assert ch["change_pct_points"] > 0
    h = ratebook.history("prime", start="2025-01-01", every=10)
    assert h and all(set(x) == {"date", "rate"} for x in h)


def test_lender_directory():
    big6 = ratebook.find_lenders(group="big6")
    books = [b["residential_book_$M"] or 0 for b in big6]
    assert len(big6) >= 6 and books == sorted(books, reverse=True)
    assert ratebook.find_lenders("meridian")
