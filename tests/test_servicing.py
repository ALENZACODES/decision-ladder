"""Servicing Desk: each figure is re-derived here from first principles, not read back from the engine."""
from datetime import date, timedelta

import pytest

import decision_ladder.modules.servicing  # noqa: F401  (registers the tools)
from decision_ladder.agent import tools as T
from decision_ladder.engines.payments import payment as monthly_payment
from decision_ladder.servicing import blend as BL
from decision_ladder.servicing import deferral as DF
from decision_ladder.servicing import frequency as F
from decision_ladder.servicing import heloc as HE
from decision_ladder.servicing import prepayment as PP
from decision_ladder.servicing.schedule import Events, LoanSpec, build, compare_frequencies, trigger_rate

FUND = date(2026, 11, 1)


def spec(freq="monthly", **kw) -> LoanSpec:
    base = dict(principal=500_000, annual_rate=5.0, amort_years=25, first_payment=F.first_payment_after(FUND, freq),
                frequency=freq)
    base.update(kw)
    return LoanSpec(**base)


def semi_periodic(rate, n):         # independent: Interest Act semi-annual equivalence
    return (1 + rate / 200) ** (2 / n) - 1


def monthly_periodic(rate, n):
    return (1 + rate / 1200) ** (12 / n) - 1


# ------------------------------------------------------------------------------------------- frequencies
@pytest.mark.parametrize("freq", list(F.FREQUENCIES))
@pytest.mark.parametrize("rate_type", ["fixed", "variable"])
def test_full_amortization_ends_at_zero_and_principal_sums_to_loan(freq, rate_type):
    s = build(spec(freq, rate_type=rate_type))
    assert s.rows[-1].balance == 0.0
    assert sum(r.principal + r.prepayment for r in s.rows) == pytest.approx(500_000, abs=0.01)
    assert sum(r.paid for r in s.rows) - 500_000 == pytest.approx(s.total_interest, abs=0.01)


@pytest.mark.parametrize("freq", ["monthly", "semi_monthly", "biweekly", "weekly"])
def test_regular_frequencies_take_exactly_the_amortization(freq):
    n = F.get(freq).per_year
    s = build(spec(freq))
    assert len(s.rows) == 25 * n
    i = semi_periodic(5.0, n)
    assert s.rows[0].payment == pytest.approx(500_000 * i / (1 - (1 + i) ** -(25 * n)), abs=1e-6)


def test_monthly_matches_engine_and_known_value():
    assert F.regular_payment(500_000, 5.0, 25, "monthly", "semi") == pytest.approx(monthly_payment(500_000, 5.0, 25))
    assert round(monthly_payment(500_000, 5.0, 25), 2) == 2908.02


def test_accelerated_is_monthly_divided():
    m = monthly_payment(500_000, 5.0, 25)
    assert F.regular_payment(500_000, 5.0, 25, "accelerated_biweekly", "semi") == pytest.approx(m / 2)
    assert F.regular_payment(500_000, 5.0, 25, "accelerated_weekly", "semi") == pytest.approx(m / 4)
    rows = compare_frequencies(500_000, 5.0, 25, FUND)
    by = {r["frequency"]: r for r in rows}
    assert by["accelerated_biweekly"]["annual_outlay"] == pytest.approx(13 * m, abs=26 * 0.005)
    assert by["accelerated_biweekly"]["years_to_payoff"] < 22 < by["biweekly"]["years_to_payoff"]
    assert by["accelerated_weekly"]["interest_saved_vs_monthly"] > 50_000


def test_periodic_rate_conventions():
    for n in (12, 24, 26, 52):
        assert F.periodic_rate(5.0, n, "semi") == pytest.approx(semi_periodic(5.0, n), rel=1e-12)
        assert F.periodic_rate(5.0, n, "monthly") == pytest.approx(monthly_periodic(5.0, n), rel=1e-12)
        assert F.annual_from_periodic(semi_periodic(6.1, n), n, "semi") == pytest.approx(6.1)


def test_payment_dates():
    bw = build(spec("biweekly"))
    assert all((b.date - a.date).days == 14 for a, b in zip(bw.rows, bw.rows[1:]))
    assert F.payment_date(date(2027, 1, 31), "monthly", 1) == date(2027, 2, 28)
    sm = [F.payment_date(date(2027, 1, 1), "semi_monthly", k) for k in range(4)]
    assert sm == [date(2027, 1, 1), date(2027, 1, 16), date(2027, 2, 1), date(2027, 2, 15)]
    assert F.get("Accelerated Bi-Weekly").key == "accelerated_biweekly"
    with pytest.raises(ValueError):
        F.get("fortnightly-ish")


def test_each_row_interest_is_balance_times_periodic_rate():
    s = build(spec("weekly"))
    i = semi_periodic(5.0, 52)
    prev = 500_000
    for r in s.rows[:60]:
        assert r.interest == pytest.approx(prev * i, abs=1e-9)
        prev = r.balance


# ------------------------------------------------------------------------------------------- variable / trigger
def test_rate_change_mid_period_split_by_days():
    s = build(spec(rate_type="variable", rate_changes=[(date(2027, 1, 11), 6.0)]))
    jan = s.rows[1]                                    # paid 2027-01-01: period untouched by the change
    feb = s.rows[2]                                    # paid 2027-02-01: 10 days at 5%, 21 days at 6%
    g = (1 + 0.05 / 12) ** (10 / 31) * (1 + 0.06 / 12) ** (21 / 31)
    assert feb.interest == pytest.approx(jan.balance * (g - 1), rel=1e-12)
    assert feb.payment == s.rows[0].payment            # fixed-payment variable: payment held


def test_adjustable_variable_and_fixed_renewal_reamortize():
    adj = build(spec(rate_type="variable", variable_payment="adjustable", rate_changes=[(date(2027, 5, 1), 6.0)]))
    reset = adj.resets[0]
    k = next(i for i, r in enumerate(adj.rows) if r.date.isoformat() == reset["date"])
    expected = F.regular_payment(adj.rows[k - 1].balance, 6.0, 25 - k / 12, "monthly", "monthly")
    assert reset["new_payment"] == round(expected, 2)
    assert adj.rows[-1].balance == 0.0 and len(adj.rows) == 300   # still pays off on schedule
    renew = build(spec(rate_changes=[(date(2031, 11, 1), 6.5)]))
    assert renew.resets and len(renew.rows) == 300 and renew.rows[-1].balance == 0.0


def test_trigger_rate_recomputes_to_payment():
    pmt = monthly_payment(500_000, 4.5, 25, "monthly")
    tr = trigger_rate(500_000, pmt, "monthly")
    assert 500_000 * monthly_periodic(tr, 12) == pytest.approx(pmt, abs=1e-6)
    tr_bw = trigger_rate(400_000, 1100, "biweekly")
    assert 400_000 * monthly_periodic(tr_bw, 26) == pytest.approx(1100, abs=1e-6)


def test_trigger_rate_and_point_detected_on_schedule():
    sv = spec(rate_type="variable", annual_rate=4.5, rate_changes=[(date(2027, 3, 1), 7.5)], term_months=60)
    s = build(sv)
    summ = s.summary()["trigger"]
    assert summ["trigger_rate_at_start"] < 7.5
    hit = next(r for r in s.rows if "rate above trigger rate" in r.flags)
    assert hit.interest > hit.payment and hit.principal < 0
    i = s.rows.index(hit)
    assert hit.balance > s.rows[i - 1].balance                       # negative amortization
    assert summ["first_date_trigger_point_reached"] is not None
    first_over = next(r for r in s.rows if r.balance > 500_000)
    assert summ["first_date_trigger_point_reached"] == first_over.date.isoformat()
    reset = build(LoanSpec(**{**vars(sv), "on_trigger_point": "reset", "trigger_point_pct": 100.5}))
    assert any(x["reason"] == "trigger point" for x in reset.resets)
    assert max(r.balance for r in reset.rows) < max(r.balance for r in s.rows)


def test_term_stops_at_maturity():
    s = build(spec(term_months=60))
    assert s.rows[-1].date == date(2031, 11, 1) and len(s.rows) == 60
    from decision_ladder.engines.payments import balance_after
    assert s.end_balance == pytest.approx(balance_after(500_000, 5.0, 25, 60), abs=0.01)


# ------------------------------------------------------------------------------------------- prepayment
def test_prepayment_saves_interest_and_stays_within_privilege():
    ev = Events(prepayments=[(date(2027, 6, 1), 50_000)])
    out = PP.prepayment_plan(spec(term_months=60), ev)
    assert out["interest_saved"] > 0 and out["time_saved"]["payments"] > 0
    chk = out["privilege_check"]
    assert chk["within_privileges"] and chk["years"][0]["remaining_room"] == 25_000.0
    plan = build(spec(), ev)
    assert sum(r.principal + r.prepayment for r in plan.rows) == pytest.approx(500_000, abs=0.01)


def test_overage_priced_on_excess_only():
    terms = PP.PenaltyTerms(comparison_posted_rate=4.0, method="simple_differential")
    ev = Events(prepayments=[(date(2027, 3, 10), 50_000), (date(2027, 9, 1), 40_000)])
    out = PP.prepayment_plan(spec(term_months=60), ev, PP.Privileges(lump_sum_pct=15), terms)
    ov = out["privilege_check"]["overages"]
    assert len(ov) == 1 and ov[0]["overage"] == 15_000.0
    months = ov[0]["penalty"]["remaining_months"]
    assert months == 50                                   # 2027-09-01 to 2031-11-01, part months rounded up
    assert ov[0]["penalty"]["ird"] == round(15_000 * 0.01 * months / 12, 2)
    assert ov[0]["penalty"]["three_month_interest"] == round(15_000 * 0.05 / 4, 2)
    floor = PP.prepayment_plan(spec(term_months=60), ev)["privilege_check"]
    assert floor["overages"][0]["penalty"]["status"] == "floor_only" and floor["overage_penalty_total"] is None


def test_payment_increase_and_double_up_rules():
    base = spec().scheduled_payment()
    ev = Events(payment_changes=[(date(2027, 1, 1), base * 1.20)], double_ups=[date(2027, 5, 1)])
    chk = PP.prepayment_plan(spec(), ev, PP.Privileges(payment_increase_pct=15))["privilege_check"]
    assert chk["payment_increases"][0]["within_privilege"] is False and not chk["within_privileges"]
    no_du = PP.prepayment_plan(spec(), ev, PP.Privileges(payment_increase_pct=25, double_up=False))["privilege_check"]
    assert no_du["years"][0]["used"] == pytest.approx(round(base * 1.20, 2), abs=0.01)
    assert PP.privilege_year(FUND, date(2027, 10, 31), "anniversary")[0] == 0
    assert PP.privilege_year(FUND, date(2027, 11, 1), "anniversary")[0] == 1


# ------------------------------------------------------------------------------------------- blends / port
def test_blended_rate_weights():
    assert BL.blended_rate(400_000, 2.49, 24, 4.29, 60)["rate"] == round((2.49 * 24 + 4.29 * 36) / 60, 4)
    assert BL.blended_rate(400_000, 2.49, 24, 4.29, 24, 100_000)["rate"] == round((4e5 * 2.49 + 1e5 * 4.29) / 5e5, 4)
    both = BL.blended_rate(400_000, 3.0, 12, 5.0, 60, 100_000)["rate"]
    assert both == round((4e5 * 12 * 3 + 4e5 * 48 * 5 + 1e5 * 60 * 5) / (5e5 * 60), 4)
    with pytest.raises(ValueError):
        BL.blended_rate(400_000, 3.0, 24, 5.0, 12)


def test_blend_vs_break_costs():
    cur = BL.Current(400_000, 2.49, 24, 22, FUND)
    out = BL.blend_vs_break(cur, 4.29, 60, penalty_override=2_490)
    by = {o["option"]: o for o in out["options"]}
    stay, brk = by["stay to maturity"], by["break and refinance"]
    assert stay["cost_over_horizon"] == pytest.approx(stay["interest_over_horizon"], abs=0.02)
    assert brk["cost_over_horizon"] == pytest.approx(brk["interest_over_horizon"] + 2_490, abs=0.02)
    assert out["best"] == "stay to maturity" and by["blend and extend"]["rate"] == 3.57
    cap = BL.blend_vs_break(cur, 4.29, 60, penalty_override=2_490, capitalize_penalty=True)
    brk2 = next(o for o in cap["options"] if o["option"] == "break and refinance")
    assert brk2["principal"] == 402_490 and brk2["upfront_cash"] == 0
    # capitalized: paid = interest + (402,490 - end balance), so cost = interest + the penalty borrowed
    assert brk2["cost_over_horizon"] == pytest.approx(brk2["interest_over_horizon"] + 2_490, abs=0.02)
    assert brk2["interest_over_horizon"] > brk["interest_over_horizon"]
    floor = BL.blend_vs_break(cur, 4.29, 60)
    assert floor["flags"] and floor["options"][-1]["option"] == "break and refinance"


def test_port_and_increase():
    cur = BL.Current(400_000, 2.49, 24, 22, FUND)
    out = BL.port_and_increase(cur, 200_000, 4.29, sale_closing=date(2027, 1, 10), purchase_closing=date(2027, 3, 30),
                               port_window_days=30, purchase_price=700_000)
    assert out["blend"]["rate"] == round((4e5 * 2.49 + 2e5 * 4.29) / 6e5, 4)
    assert out["payment_after"] == round(monthly_payment(600_000, out["blend"]["rate"], 22), 2)
    assert out["closing_gap_days"] == 79 and len(out["flags"]) == 2      # past window, over 80% LTV
    assert out["penalty_avoided_by_porting"]["amount"] == round(400_000 * 0.0249 / 4, 2)


# ------------------------------------------------------------------------------------------- HELOC
def test_heloc_limits_and_minimum_payment():
    out = HE.readvanceable(1_000_000, [{"balance": 600_000}], 150_000, 6.45, as_of=date(2026, 11, 15))
    assert out["revolving_limit"] == 200_000 and out["available_room"] == 50_000
    assert out["limit_bound_by"] == "80% combined cap" and out["combined_ltv_pct"] == 75.0
    assert out["minimum_payment_interest_only"] == round(150_000 * 0.0645 * 30 / 365, 2)
    low = HE.readvanceable(1_000_000, [{"balance": 100_000}], 0, 6.45, as_of=FUND, basis="monthly")
    assert low["revolving_limit"] == 650_000 and low["limit_bound_by"] == "65% revolving cap"
    capped = HE.readvanceable(1_000_000, [{"balance": 100_000}], 0, 6.45, authorized_limit=300_000)
    assert capped["revolving_limit"] == 300_000 and capped["limit_bound_by"] == "authorized limit"
    over = HE.readvanceable(800_000, [{"balance": 560_000}], 100_000, 6.45)
    assert len(over["flags"]) == 3
    assert HE.OSFI_SOURCE["url"].startswith("https://www.osfi-bsif.gc.ca/") and HE.OSFI_SOURCE["checked"]


def test_heloc_readvance_projection_grows_with_paydown():
    out = HE.readvanceable(1_000_000, [{"balance": 600_000, "rate": 4.5, "amort_years": 25}], 150_000, 6.45,
                           as_of=FUND, projection_years=3)
    proj = out["projection"]
    sched = build(LoanSpec(600_000, 4.5, 25, date(2026, 12, 1)))
    assert proj[0]["amortizing_balance"] == round(sched.balance_on(date(2027, 11, 1)), 2)
    assert proj[0]["revolving_limit"] == pytest.approx(800_000 - proj[0]["amortizing_balance"], abs=0.01)
    assert proj[0]["available_room"] < proj[1]["available_room"] < proj[2]["available_room"]


# ------------------------------------------------------------------------------------------- deferral / arrears
def test_deferral_capitalizes_interest():
    out = DF.defer_payments(spec(), date(2027, 6, 1), 3)
    i = semi_periodic(5.0, 12)
    before = out["balance_before_deferral"]
    assert out["balance_after_deferral"] == pytest.approx(before * (1 + i) ** 3, abs=0.02)
    assert out["capitalized_interest"] == pytest.approx(before * ((1 + i) ** 3 - 1), abs=0.02)
    assert out["reamortize"]["payoff_date"] == out["baseline"]["payoff_date"]
    assert out["keep_payment"]["payoff_date"] > out["baseline"]["payoff_date"]
    assert 0 < out["reamortize"]["extra_interest"] < out["keep_payment"]["extra_interest"]


def test_arrears_amount_to_cure():
    i = semi_periodic(5.0, 12)
    out = DF.arrears(2_000, 5.0, 2, fees_per_missed=50)
    assert out["amount_to_cure"] == round(2_000 * (1 + i) + 2_000 + 100, 2)


# ------------------------------------------------------------------------------------------- tools
def test_tools_registered_with_engine_and_method():
    names = ["servicing_schedule", "servicing_frequency_compare", "variable_trigger_rate", "servicing_prepayment",
             "blend_vs_break", "port_and_increase", "heloc_room", "payment_deferral", "mortgage_arrears"]
    assert all(n in T.TOOLS for n in names)
    from decision_ladder.agent.router import stage_tools
    assert set(names) <= stage_tools()["servicing"]
    loan = {"principal": 400_000, "annual_rate": 4.0, "amort_years": 25, "funding_date": "2026-11-01"}
    r = T.run("servicing_schedule", loan)
    assert r["engine"] == "decision_ladder.servicing" and r["method"] and "rows" not in r
    assert len(T.run("servicing_schedule", {**loan, "rows": True})["rows"]) == 300
    assert "error" in T.run("servicing_schedule", {**loan, "frequency": "daily"})
    h = T.run("heloc_room", {"property_value": 900_000, "heloc_rate": 6.2, "amortizing": [{"balance": 400_000}]})
    assert h["source"] == HE.OSFI_SOURCE["url"] and h["revolving_limit"] == 320_000
    t = T.run("variable_trigger_rate", {"balance": 500_000, "payment": 2_770, "current_rate": 5.0})
    assert t["interest_at_trigger_rate"] == 2_770 and t["above_trigger"] is False


def test_tool_prepayment_end_to_end():
    r = T.run("servicing_prepayment", {"principal": 500_000, "annual_rate": 5, "amort_years": 25,
                                       "funding_date": "2026-11-01", "term_months": 60,
                                       "lump_sums": [{"date": "2027-05-01", "amount": 100_000}],
                                       "comparison_posted_rate": 4.0, "penalty_method": "simple_differential"})
    ov = r["privilege_check"]["overages"][0]
    assert ov["overage"] == 25_000 and ov["penalty"]["total_estimate"] == round(25_000 * 0.01 * 54 / 12, 2)
    assert r["over_term"]["balance_at_maturity_with_prepayments"] < r["over_term"]["balance_at_maturity_baseline"]


def test_first_payment_after_funding():
    assert F.first_payment_after(FUND, "biweekly") == FUND + timedelta(days=14)
    assert F.first_payment_after(FUND, "monthly") == date(2026, 12, 1)
    assert F.first_payment_after(FUND, "semi_monthly") == date(2026, 11, 16)
