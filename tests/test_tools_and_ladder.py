import json

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.ladder import rungs as R
from decision_ladder.ladder.runner import LadderEngine, climb, template_memo
from decision_ladder.samples import SAMPLES

GOOD_ARGS = {
    "qualify_purchase": {"price": 700000, "down_payment": 140000, "annual_income": 200000, "contract_rate": 4.2},
    "insurance_premium": {"price": 600000, "down_payment": 30000},
    "find_path_to_yes": {"price": 900000, "down_payment": 90000, "annual_income": 120000, "contract_rate": 4.5},
    "max_purchase_price": {"price": 900000, "down_payment": 90000, "annual_income": 120000, "contract_rate": 4.5},
    "mortgage_payment": {"principal": 500000, "annual_rate": 4.5, "amort_years": 25, "months_paid": 12},
    "penalty_by_lender": {"lender": "TD", "balance": 640000, "contract_rate": 5.29, "term_start": "2023-08-01",
                          "maturity": "2028-08-01", "payout_date": "2026-10-28", "original_posted_rate": 6.84},
    "penalty_quick": {"balance": 400000, "contract_rate": 5, "months_remaining": 24, "comparison_rate": 4,
                      "new_rate": 4, "amort_years_remaining": 20},
    "renewal_payment_shock": {"original_principal": 600000, "original_rate": 1.99, "original_amort_years": 25,
                              "months_elapsed": 59, "renewal_rate": 4.84},
    "compare_renewal_offers": {"balance": 500000, "remaining_amort_years": 20, "term_years": 5,
                               "offers": [{"rate": 4.8}, {"rate": 4.3}]},
    "switch_lender_check": {"balance": 500000, "remaining_amort_years": 20, "new_rate": 4.5, "annual_income": 140000},
    "home_value_estimate": {"purchase_price": 780000, "purchase_year": 2021, "purchase_month": 11, "postal_code": "L3R 2Z5"},
    "market_snapshot": {},
    "bank_rates": {"bank": "CIBC"},
    "rate_change": {"name": "policy_rate", "start": "2024-01-01"},
    "lender_match": {"province": "ON", "credit_score": 720, "ltv": 80, "gds": 30, "tds": 38},
    "lender_directory": {"query": "", "group": "credit_union", "limit": 5},
    "penalty_methods": {},
    "message_guardrail": {"text": "Hi, can we book a call this week?"},
    "identity_screening": {"name": "Jane Doe"},
}


def test_every_tool_has_a_working_example():
    assert set(GOOD_ARGS) == set(T.TOOLS)


@pytest.mark.parametrize("name", sorted(GOOD_ARGS))
def test_tool_runs_and_is_json_serializable(name):
    out = T.run(name, GOOD_ARGS[name])
    assert "error" not in out, out
    json.dumps(out)


def test_tool_specs_are_valid_openai_function_specs():
    for spec in T.specs():
        fn = spec["function"]
        assert spec["type"] == "function" and fn["name"] and fn["description"]
        assert fn["parameters"]["type"] == "object"
        for r in fn["parameters"].get("required", []):
            assert r in fn["parameters"]["properties"]


def test_run_rejects_unknown_tool_and_missing_args_and_drops_extra_args():
    assert "unknown tool" in T.run("nope", {})["error"]
    assert "missing required" in T.run("qualify_purchase", {"price": 1})["error"]
    out = T.run("mortgage_payment", {"principal": 100000, "annual_rate": 5, "amort_years": 25, "evil": "x"})
    assert "monthly_payment" in out


def test_tool_errors_are_returned_not_raised():
    out = T.run("insurance_premium", {"price": 100, "down_payment": 500})
    assert out["error"].startswith("ValueError")


def test_penalty_by_lender_uses_rate_book_and_reports_sensitivity():
    out = T.run("penalty_by_lender", GOOD_ARGS["penalty_by_lender"])
    assert out["lender_code"] == "td"
    assert float(out["estimate"]["total_estimate"]) > float(out["estimate"]["three_month_interest"])
    assert out["posted_rate_provenance"] and out["sensitivity"]


def test_guardrail_tool_blocks_bad_message():
    out = T.run("message_guardrail", {"text": "You're pre-approved at 3.99%! Act now!"})
    assert not out["allowed"] and {"RATE_QUOTE", "APPROVAL_PROMISE", "PRESSURE"} <= set(out["violations"])


# ---------------------------------------------------------------------- ladder
def _clean(f):
    return {k: v for k, v in f.items() if k != "label"}


@pytest.mark.parametrize("key,verdict", [
    ("oakville_stretch", "RESTRUCTURE"),
    ("brampton_first_home", "GO WITH CONDITIONS"),
    ("pandemic_renewal_rbc", "GO WITH CONDITIONS"),
    ("td_break_early", "GO WITH CONDITIONS"),
])
def test_sample_verdicts(key, verdict):
    rungs, _ = climb(_clean(SAMPLES[key]))
    assert rungs[-1]["summary"] == verdict
    assert [r["key"] for r in rungs] == [k for k, _ in R.LADDER]


def test_failed_file_gets_verified_path_to_yes():
    rungs, ctx = climb(_clean(SAMPLES["oakville_stretch"]))
    q = next(r for r in rungs if r["key"] == "qualification")
    assert q["status"] == R.FAIL and "path_to_yes" in q["evidence"]
    assert rungs[-1]["evidence"]["options"]


def test_insured_file_premium_on_rung():
    rungs, _ = climb(_clean(SAMPLES["brampton_first_home"]))
    ins = next(r for r in rungs if r["key"] == "insurance")
    assert ins["metrics"]["insured"] and ins["metrics"]["premium"] > 0


def test_refinance_computes_penalty_and_break_even():
    rungs, _ = climb(_clean(SAMPLES["td_break_early"]))
    ex = next(r for r in rungs if r["key"] == "exit_cost")
    assert ex["metrics"]["penalty_estimate"] > 10000 and "net_saving_over_term" in ex["metrics"]


def test_missing_fields_refer_and_never_crash():
    rungs, _ = climb({"purpose": "purchase", "borrower_name": "A B"})
    statuses = {r["key"]: r["status"] for r in rungs}
    assert statuses["intake"] == R.REFER
    assert statuses["qualification"] == R.REFER  # crashed internally -> REFER, never PASS
    assert rungs[-1]["summary"] in ("GO WITH CONDITIONS", "RESTRUCTURE", "DECLINE AS STRUCTURED")


def test_document_discrepancy_refers():
    f = _clean(SAMPLES["brampton_first_home"])
    f["documents"] = [{"type": "T4", "extracted": {"annual_income": 120000}}]
    rungs, _ = climb(f)
    d = next(r for r in rungs if r["key"] == "documents")
    assert d["status"] == R.REFER and d["metrics"]["discrepancies"] == 1


def test_watchlist_match_fails(tmp_path):
    wl = tmp_path / "list.txt"
    wl.write_text("Daniel Okafor\n")
    f = _clean(SAMPLES["brampton_first_home"]) | {"watchlist_path": str(wl)}
    rungs, _ = climb(f)
    assert next(r for r in rungs if r["key"] == "screening")["status"] == R.FAIL


def test_market_rung_flags_teaser_rate():
    f = _clean(SAMPLES["brampton_first_home"]) | {"contract_rate": 2.5}
    m = next(r for r in climb(f)[0] if r["key"] == "market")
    assert m["status"] == R.REFER and m["metrics"]["gap_pct_points"] < -0.4


def test_template_memo_contains_verdict_and_options():
    rungs, _ = climb(_clean(SAMPLES["oakville_stretch"]))
    memo = template_memo(rungs)
    assert memo.startswith("VERDICT: RESTRUCTURE") and "PATH TO YES" in memo and "Lower the price" in memo


def test_engine_without_model_uses_template_and_verifies():
    run = LadderEngine(None).run(_clean(SAMPLES["oakville_stretch"]))
    assert run.memo_source.startswith("template") and run.memo_verification["ok"]
    assert run.message is None
