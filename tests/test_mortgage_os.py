"""The Mortgage OS layer: staged ladder over the author's apps, cross-checks, Ultra memo, Tavily Extract, jobs."""
import json
import shutil

import pytest

from decision_ladder import modules as OS
from decision_ladder.ladder import crosscheck
from decision_ladder.ladder.runner import LadderEngine, climb
from decision_ladder.llm.client import LLMError, NemotronClient
from decision_ladder.research.tavily import Research, five_year_rates, lender_rate_check, offline_transport
from decision_ladder.samples import SAMPLE_BOOK_CSV, SAMPLES

NODE = shutil.which("node") is not None
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _f(key, **over):
    f = {k: v for k, v in SAMPLES[key].items() if k != "label"}
    f.update(over)
    return f


def _rung(rungs, key):
    return next(r for r in rungs if r["key"] == key)


def test_registry_has_all_fourteen_projects_and_stages():
    OS.load_all()
    assert not OS.LOAD_ERRORS
    keys = set(OS.MODULES)
    for k in ("renewal-radar", "mortgageloanops", "benchmark-home-value", "canada-home-value", "cash-to-close",
              "canadian-mortgage-suite", "mortgage-decision-lab", "pre-underwriting-copilot", "private-credit-screener",
              "renewal-check", "renewal-shock-radar", "canada-rate-cycle-dashboard", "doc-quest",
              "canada-housing-affordability-index-1980-2026"):
        assert k in keys, k
    cat = OS.catalog()
    assert cat["totals"]["module_lines"] > 70_000          # counted from the vendored source, not typed in
    assert all(m["present"] for m in cat["modules"])


def test_every_rung_has_stage_and_engines():
    rungs, _ = climb(_f("oakville_stretch"))
    assert len(rungs) == 17
    for r in rungs:
        assert r["stage"] and r["engines"], r["key"]
        assert all("name" in e for e in r["engines"])


@needs_node
def test_all_cross_checks_agree_on_every_sample():
    total = 0
    for key in SAMPLES:
        for c in crosscheck.run_checks(_f(key)):
            if c["agree"] is not None:
                total += 1
                assert c["agree"], (key, c)
    assert total >= 12


@needs_node
def test_known_difference_is_labelled_not_counted():
    checks = crosscheck.run_checks(_f("td_break_early"))
    ird = next(c for c in checks if c["quantity"].startswith("IRD"))
    noted = [e for e in ird["engines"] if e.get("note")]
    assert ird["agree"] and noted and "day-exact" in noted[0]["note"]
    assert abs(noted[0]["value"] - 16363.73) < 0.01           # TD's own calculator method via Renewal Radar
    assert all(abs(e["value"] - 17013.33) < 0.01 for e in ird["engines"] if not e.get("note"))


def test_insured_qualification_includes_the_premium():
    from decision_ladder.engines import qualify
    q = qualify.qualify(price=725_000, down_payment=50_000, annual_income=168_000, contract_rate=4.24, amort_years=30,
                        first_time_buyer=True, property_tax_annual=5_600, other_debt_monthly=400)
    assert q.insurance_premium == 28_350 and q.mortgage_amount == 703_350


@needs_node
def test_priya_journey_end_to_end():
    rungs, ctx = climb(_f("oakville_stretch"))
    assert rungs[-1]["summary"] == "RESTRUCTURE"
    closing = _rung(rungs, "closing")
    assert closing["status"] == "FAIL" and closing["metrics"]["shortfall"] == 19_875
    fix = closing["evidence"]["fix"]
    assert fix["down_payment"] < 220_000 and fix["insured"] is True      # keeps cash, becomes insured
    assert _rung(rungs, "crosscheck")["status"] == "PASS"
    assert _rung(rungs, "readiness")["metrics"]["readiness_score"] < 50
    prop = _rung(rungs, "property")
    assert prop["metrics"]["area"] == "Oakville" and prop["metrics"]["property_type"] == "semi"
    docs = _rung(rungs, "documents")
    assert docs["metrics"]["documented_income"] == 99_000                  # pay stub covers one of two incomes
    assert any("Keep cash for closing" in o for o in rungs[-1]["evidence"]["options"])


@needs_node
def test_brampton_passes_cash_to_close_and_readiness():
    rungs, _ = climb(_f("brampton_first_home"))
    assert _rung(rungs, "closing")["status"] == "PASS"
    assert _rung(rungs, "readiness")["metrics"]["readiness_score"] == 100
    assert _rung(rungs, "insurance")["metrics"]["premium"] == 28_350


def test_renewal_uses_renewal_radar_and_benchmark_value():
    rungs, _ = climb(_f("pandemic_renewal_rbc"))
    prop = _rung(rungs, "property")
    assert "Benchmark Home Value" in prop["metrics"]["basis"] and prop["metrics"]["ltv"] > 80
    ex = _rung(rungs, "exit_cost")
    assert "switch_pathway" in ex["evidence"] and "renewal_plan" in ex["evidence"]
    assert _rung(rungs, "documents")["status"] == "PASS"                   # letter reconciles balance, rate, maturity


def test_refinance_prefers_lender_exact_penalty():
    rungs, _ = climb(_f("td_break_early"))
    ex = _rung(rungs, "exit_cost")
    assert abs(ex["metrics"]["penalty_estimate"] - 16363.73) < 0.01 and "exact" in ex["metrics"]["penalty_method"]


@needs_node
def test_commercial_file_goes_to_private_credit_screen():
    rungs, _ = climb(_f("hamilton_commercial"))
    com = _rung(rungs, "commercial")
    assert com["status"] in ("PASS", "REFER", "FAIL") and com["metrics"]["grade"] in "ABCD"
    for k in ("qualification", "insurance", "closing", "lender", "exit_cost"):
        assert _rung(rungs, k)["status"] == "SKIP"


def test_rung_failure_never_passes(monkeypatch):
    from decision_ladder.agent import tools as T
    monkeypatch.setitem(T.TOOLS, "cash_to_close_ontario",
                        T.Tool("cash_to_close_ontario", "x", T._obj({"price": T.N, "savings": T.N}, []), lambda a: 1 / 0))
    rungs, _ = climb(_f("oakville_stretch"))
    assert _rung(rungs, "closing")["status"] in ("REFER", "FAIL")


# ---------------------------------------------------------------- three Nemotron tiers
class Script:
    def __init__(self, *responses):
        self.q, self.payloads = list(responses), []

    def __call__(self, path, payload, method="POST"):
        self.payloads.append(payload)
        r = self.q.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def say(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}], "usage": {}}


def test_memo_is_written_by_ultra():
    s = Script(say("VERDICT: GO WITH CONDITIONS"), say("Hi Daniel, can we book a call?"))
    c = NemotronClient(s, ultra="nvidia/nemotron-3-ultra-x")
    run = LadderEngine(c).run(_f("brampton_first_home"))
    assert s.payloads[0]["model"] == "nvidia/nemotron-3-ultra-x" and run.memo_model == "nvidia/nemotron-3-ultra-x"
    assert s.payloads[1]["model"] == c.fast


def test_memo_falls_back_to_super_when_ultra_missing():
    e = LLMError("HTTP 404 model not found")
    e.status = 404
    s = Script(e, say("VERDICT: GO WITH CONDITIONS"), say("Hi Daniel"))
    c = NemotronClient(s, ultra="nvidia/nemotron-3-ultra-missing", sleep=lambda x: None)
    run = LadderEngine(c).run(_f("brampton_first_home"))
    assert run.memo_model == c.reasoner and run.memo_source == "nemotron"


def test_resolve_models_finds_ultra_or_falls_back():
    c = NemotronClient(Script({"data": [{"id": "nvidia/nemotron-3-super-120b-a12b"}, {"id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"},
                                        {"id": "nvidia/Nemotron-3-Ultra-550B"}]}))
    r = c.resolve_models()
    assert c.ultra == "nvidia/Nemotron-3-Ultra-550B" and r["ultra_reason"].startswith("auto")
    c2 = NemotronClient(Script({"data": [{"id": "nvidia/nemotron-3-super-120b-a12b"}]}))
    c2.resolve_models()
    assert c2.ultra == c2.reasoner


# ---------------------------------------------------------------- Tavily Extract
def test_five_year_rate_parsing():
    page = "5 Year Fixed Closed 6.19% | Special 5-year fixed 4.64% | 3 Year 6.05% | 5 yr variable prime - 0.10%"
    assert five_year_rates(page) == [6.19, 4.64]


def test_lender_rate_check_confirms_book_value():
    page = {"results": [{"url": "u", "raw_content": "RBC posted rates. 5 Year Fixed Closed 6.19% ... special 5-year 4.69%"}]}
    r = Research(transport=offline_transport, extract_transport=lambda p: page)
    out = lender_rate_check(r, "RBC")
    assert out["status"] == "confirmed" and out["rate_book_5y_posted"] == 6.19 and 6.19 in out["five_year_rates_on_page"]


def test_lender_rate_check_flags_change():
    page = {"results": [{"url": "u", "raw_content": "5 Year Fixed Closed 6.49%"}]}
    out = lender_rate_check(Research(transport=offline_transport, extract_transport=lambda p: page), "TD")
    assert out["status"] == "changed_or_not_shown"


def test_extract_payload_shape():
    seen = {}
    r = Research(transport=offline_transport, extract_transport=lambda p: seen.update(p) or {"results": []})
    r.extract(["https://www.bankofcanada.ca/"], query="policy rate")
    assert seen["urls"] == ["https://www.bankofcanada.ca/"] and seen["extract_depth"] == "advanced" and seen["chunks_per_source"] == 3


def test_ladder_research_includes_lender_rate_check():
    run = LadderEngine(None, Research(transport=offline_transport)).run(_f("pandemic_renewal_rbc"), research_queries=["Bank of Canada"])
    assert any("rate_check" in r for r in run.research)


# ---------------------------------------------------------------- jobs + router
def test_renewal_book_job(tmp_path):
    from decision_ladder.jobs import main
    book = tmp_path / "book.csv"
    book.write_text(SAMPLE_BOOK_CSV)
    assert main(["renewal-book", "--input", str(book), "--out", str(tmp_path / "out"), "--as-of", "2026-10-28",
                 "--drafts", "0"]) == 0
    data = json.loads((tmp_path / "out" / "renewal_queue.json").read_text())
    assert data["summary"]["loans"] == 6 and (tmp_path / "out" / "renewal_queue.md").read_text().startswith("# Renewal call queue")


def test_router_stage_map_covers_every_tool():
    from decision_ladder.agent import tools as T
    from decision_ladder.agent.router import stage_tools
    covered = set().union(*stage_tools().values())
    assert set(T.TOOLS) <= covered
