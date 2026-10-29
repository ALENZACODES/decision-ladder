"""Copilot and ladder model layer, driven by a hand-scripted transport that mimics Nemotron responses."""
import json

from decision_ladder.agent.loop import Copilot, draft_borrower_message
from decision_ladder.ladder.runner import LadderEngine
from decision_ladder.llm.client import LLMError, NemotronClient
from decision_ladder.llm.offline import OFFLINE_MODEL, offline_client
from decision_ladder.research.tavily import Research, offline_transport
from decision_ladder.samples import SAMPLES


class Script:
    """Returns queued responses; records every payload."""

    def __init__(self, *responses):
        self.q = list(responses)
        self.payloads = []

    def __call__(self, path, payload, method="POST"):
        self.payloads.append(payload)
        r = self.q.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def say(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


def call(name, args, i=0):
    return {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]},
        "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


Q = {"principal": 500000, "annual_rate": 4.5, "amort_years": 25}


def test_tool_loop_answer_is_verified():
    s = Script(call("mortgage_payment", Q), say("The payment is about $2,767 a month."))
    res = Copilot(NemotronClient(s), route=False).ask("payment on 500k at 4.5% 25y?")
    assert res.verification["ok"] and not res.repaired
    tool_msg = s.payloads[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c0"
    assert [st.kind for st in res.steps] == ["tool", "answer"]


def test_invented_number_triggers_repair_which_succeeds():
    s = Script(call("mortgage_payment", Q), say("The payment is $2,900."), say("The payment is $2,767."))
    res = Copilot(NemotronClient(s), route=False).ask("q")
    assert res.repaired and res.verification["ok"] and "2,767" in res.answer
    assert "do not appear in any tool result" in s.payloads[2]["messages"][-1]["content"]


def test_repair_that_fails_annotates_unverified():
    s = Script(call("mortgage_payment", Q), say("The payment is $2,900."), say("Still $2,900."))
    res = Copilot(NemotronClient(s), route=False).ask("q")
    assert "[unverified]" in res.answer and not res.verification["ok"]


def test_repair_can_call_tools():
    s = Script(say("Payment $2,767."), call("mortgage_payment", Q, 1), say("Payment $2,767."))
    res = Copilot(NemotronClient(s), route=False).ask("q")
    assert res.verification["ok"] and any(st.kind == "repair" for st in res.steps)


def test_bad_tool_arguments_become_tool_errors_not_crashes():
    bad = {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": "x", "type": "function", "function": {"name": "mortgage_payment", "arguments": "not json"}}]}}]}
    s = Script(bad, say("I could not compute that."))
    res = Copilot(NemotronClient(s), route=False).ask("q")
    assert res.steps[0].result.get("error")


def test_round_limit_forces_final_answer():
    s = Script(*[call("market_snapshot", {}, i) for i in range(2)], say("Done."))
    res = Copilot(NemotronClient(s), max_rounds=2, route=False).ask("q")
    assert res.answer == "Done."
    assert "tools" not in s.payloads[-1]


def test_research_tool_is_offered_and_routed():
    s = Script(call("web_research", {"query": "Bank of Canada rate decision"}), say("See the source."))
    res = Copilot(NemotronClient(s), Research(transport=offline_transport), route=False).ask("latest BoC news?")
    names = [t["function"]["name"] for t in s.payloads[0]["tools"]]
    assert "web_research" in names
    assert res.steps[0].kind == "research" and res.steps[0].result["sources"]


def test_context_is_passed_to_model():
    s = Script(say("ok"))
    Copilot(NemotronClient(s), route=False).ask("q", context={"price": 1})
    assert "FILE CONTEXT (JSON)" in s.payloads[0]["messages"][-1]["content"]


def test_draft_message_blocked_by_guardrail():
    s = Script(say("Great news, you're approved at 3.99%! Act now."))
    out = draft_borrower_message(NemotronClient(s), purpose="x", facts={})
    assert out["blocked"] and out["send_text"] != out["draft"]
    assert s.payloads[0]["model"] == NemotronClient(Script()).fast


def test_ladder_memo_from_model_with_repair():
    f = {k: v for k, v in SAMPLES["oakville_stretch"].items() if k != "label"}
    s = Script(say("VERDICT: RESTRUCTURE\nGDS is 39.9% vs 39%. Max price $1,234,567."),
               say("VERDICT: RESTRUCTURE\nGDS is 39.9% vs 39%."),
               say("Hi Priya, can we book a call this week?"))
    run = LadderEngine(NemotronClient(s)).run(f)
    assert run.memo_source == "nemotron" and run.memo_verification["ok"]
    assert run.message and not run.message["blocked"]
    assert run.usage["calls"] == 3


def test_ladder_memo_falls_back_to_template_on_model_error():
    err = LLMError("HTTP 401")
    err.status = 401
    f = {k: v for k, v in SAMPLES["brampton_first_home"].items() if k != "label"}
    run = LadderEngine(NemotronClient(Script(err, err), sleep=lambda s: None)).run(f)
    assert run.memo_source.startswith("template (model error")
    assert "error" in run.message


def test_offline_client_is_labelled():
    c = offline_client()
    assert c.offline
    res = Copilot(c).ask("What is the market doing? Bank of Canada policy rate?")
    assert "offline" in res.answer.lower()
    assert res.steps[0].kind == "route" and res.steps[0].result["by"].startswith("offline")
    assert res.steps[1].name == "market_snapshot"
    assert c.transport.requests[0]["payload"]["model"].startswith("offline/")
    assert OFFLINE_MODEL.startswith("offline/")


def test_offline_full_ladder_runs_end_to_end():
    for key, f in SAMPLES.items():
        run = LadderEngine(offline_client(), Research(transport=offline_transport)).run(
            {k: v for k, v in f.items() if k != "label"}, research_queries=["Bank of Canada"])
        assert run.memo and run.memo_verification["ok"], key
        assert run.research and run.research[0]["sources"]


# ---------------------------------------------------------------- Nano router
def test_router_limits_tools_to_chosen_stages():
    route_reply = say(json.dumps({"stages": ["closing"], "reason": "closing costs question"}))
    s = Script(route_reply, call("cash_to_close_ontario", {"price": 700000, "savings": 60000}), say("You need cash."))
    res = Copilot(NemotronClient(s)).ask("How much cash do I need on closing day for a 700k home?")
    assert s.payloads[0]["model"] == NemotronClient(Script()).fast          # Nano routes
    offered = {t["function"]["name"] for t in s.payloads[1]["tools"]}
    assert "cash_to_close_ontario" in offered and "land_transfer_tax" in offered
    assert "private_credit_deal_screen" not in offered and "penalty_by_lender" not in offered
    d = res.to_dict()
    assert d["routing"]["stages"] == ["closing"] and d["routing"]["by"] == "nemotron-nano"
    assert "Cash to Close" in d["modules_used"]


def test_router_failure_falls_back_to_keywords_then_all():
    err = LLMError("HTTP 500")
    err.status = 500
    from decision_ladder.agent.router import route
    from decision_ladder.agent import tools as T
    from decision_ladder import modules as OS
    OS.load_all()
    r = route(NemotronClient(Script(err, err, err, err), sleep=lambda s: None), "What is my land transfer tax?", set(T.TOOLS))
    assert r["by"] == "keywords" and "closing" in r["stages"] and "land_transfer_tax" in r["tools"]
    r = route(None, "hello there", set(T.TOOLS))
    assert r["by"] == "all" and len(r["tools"]) == len(T.TOOLS)


def test_router_ignores_unknown_stages():
    s = Script(say(json.dumps({"stages": ["astrology"]})), say("ok"))
    res = Copilot(NemotronClient(s)).ask("hello")
    assert res.to_dict()["routing"]["by"] == "all"
