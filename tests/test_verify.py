import pytest

from decision_ladder.agent import verify


def test_supported_money_with_display_rounding():
    ev = {"stressed_payment": 4054.58, "max_price": 707000.0}
    r = verify.verify("Stressed payment is $4,054.58, about $4,055, and the max price is $707K.", ev)
    assert r.ok, r.to_dict()
    assert r.to_dict()["checked"] == 3


def test_unsupported_money_is_flagged():
    r = verify.verify("The penalty is $18,200.", {"penalty": 17013.33})
    assert not r.ok
    assert r.unsupported[0].value == 18200


def test_percentages_match_to_a_tenth():
    ev = {"gds": 39.92, "qualifying_rate": 6.19}
    assert verify.verify("GDS 39.9% at a 6.19% qualifying rate", ev).ok
    assert not verify.verify("GDS 41% at a 6.19% qualifying rate", ev).ok


def test_ratio_written_as_percent():
    assert verify.verify("an LTV of 87%", {"ltv_ratio": 0.87}).ok


def test_bps_converted():
    assert verify.verify("a spread of 125 bps", {"spread": 1.25}).ok


def test_years_dates_and_small_counts_ignored():
    r = verify.verify("In 2026, on 2026-10-14 and Oct 14, 2026, rung 3 of 11 passed.", {})
    assert r.to_dict()["checked"] == 0


def test_numbers_from_user_message_are_evidence():
    assert verify.verify("At $185,000 of income", "my income is 185000").ok


def test_millions_suffix():
    assert verify.verify("a $1.1M home", {"price": 1_100_000}).ok


def test_negative_values_match_absolute():
    assert verify.verify("a net cost of $11,816", {"net_saving_over_term": -11816.2}).ok


def test_string_numbers_in_evidence():
    assert verify.verify("penalty $17,013.33", {"total_estimate": "17013.33"}).ok


def test_annotate_marks_unsupported():
    text = "Payment $3,000 and rate 4.29%"
    r = verify.verify(text, {"rate": 4.29})
    assert verify.annotate(text, r) == "Payment $3,000 [unverified] and rate 4.29%"


@pytest.mark.parametrize("e,v,kind,ok", [
    (25110.0, 25100.0, "money", True),
    (25110.0, 25000.0, "money", True),   # rounded to thousands
    (25110.0, 26000.0, "money", False),
    (3343.27, 3343.0, "money", True),
    (3343.27, 3300.0, "money", True),    # hundreds
    (3343.27, 3400.0, "money", False),
])
def test_rounding_rules(e, v, kind, ok):
    assert verify._matches(v, e, kind) is ok
