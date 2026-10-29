import json

import pytest

from decision_ladder.llm.client import (LLMError, NemotronClient, parse_json_object, strip_reasoning, tool_args)


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, path, payload, method="POST"):
        self.calls.append((path, payload, method))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def ok(content="hi", tool_calls=None, usage=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"model": "m", "choices": [{"message": msg, "finish_reason": "stop"}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5}}


def http_error(status):
    e = LLMError(f"HTTP {status}")
    e.status = status
    return e


def test_requires_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(LLMError, match="NEBIUS_API_KEY"):
        NemotronClient()


def test_defaults_are_nvidia_models_on_token_factory(monkeypatch):
    for k in ("DL_MODEL_REASONER", "DL_MODEL_FAST", "NEBIUS_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    c = NemotronClient(Recorder([]))
    assert c.base_url == "https://api.tokenfactory.nebius.com/v1/"
    assert c.reasoner.startswith("nvidia/") and "nemotron" in c.reasoner.lower()
    assert c.fast.startswith("nvidia/") and "nemotron" in c.fast.lower()


def test_env_overrides_models(monkeypatch):
    monkeypatch.setenv("DL_MODEL_REASONER", "nvidia/x")
    monkeypatch.setenv("DL_MODEL_FAST", "nvidia/y")
    c = NemotronClient(Recorder([]))
    assert (c.reasoner, c.fast) == ("nvidia/x", "nvidia/y")


def test_chat_payload_and_usage():
    rec = Recorder([ok("answer")])
    c = NemotronClient(rec)
    res = c.chat([{"role": "user", "content": "q"}], tools=[{"type": "function", "function": {"name": "t"}}])
    path, payload, _ = rec.calls[0]
    assert path == "chat/completions"
    assert payload["model"] == c.reasoner and payload["tool_choice"] == "auto" and payload["temperature"] == 0.0
    assert res.content == "answer"
    assert c.usage.calls == 1 and c.usage.prompt_tokens == 10 and c.usage.completion_tokens == 5


def test_tool_calls_normalized_and_dict_arguments_serialized():
    rec = Recorder([ok("", [{"function": {"name": "qualify_purchase", "arguments": {"price": 1}}}])])
    res = NemotronClient(rec).chat([{"role": "user", "content": "q"}])
    call = res.tool_calls[0]
    assert call["id"] == "call_0" and call["type"] == "function"
    assert json.loads(call["function"]["arguments"]) == {"price": 1}
    assert res.message["tool_calls"] == res.tool_calls


def test_retries_on_429_then_succeeds():
    sleeps = []
    rec = Recorder([http_error(429), http_error(503), ok("done")])
    c = NemotronClient(rec, sleep=sleeps.append)
    assert c.chat([{"role": "user", "content": "q"}]).content == "done"
    assert len(sleeps) == 2 and len(rec.calls) == 3


def test_no_retry_on_401():
    rec = Recorder([http_error(401), ok()])
    c = NemotronClient(rec, sleep=lambda s: None)
    with pytest.raises(LLMError):
        c.chat([{"role": "user", "content": "q"}])
    assert len(rec.calls) == 1


def test_gives_up_after_max_retries():
    rec = Recorder([http_error(500)] * 5)
    c = NemotronClient(rec, sleep=lambda s: None, max_retries=2)
    with pytest.raises(LLMError):
        c.chat([{"role": "user", "content": "q"}])
    assert len(rec.calls) == 3


def test_empty_choices_raise():
    with pytest.raises(LLMError, match="no choices"):
        NemotronClient(Recorder([{"choices": []}])).chat([{"role": "user", "content": "q"}])


def test_think_blocks_are_stripped():
    assert strip_reasoning("<think>secret plan</think>\n Final") == "Final"
    res = NemotronClient(Recorder([ok("<think>x</think>Answer")])).chat([{"role": "user", "content": "q"}])
    assert res.content == "Answer"


def test_content_parts_are_joined():
    r = {"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}
    assert NemotronClient(Recorder([r])).chat([{"role": "user", "content": "q"}]).content == "ab"


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 2}\n```', {"a": 2}),
    ('Sure! Here it is: {"a": {"b": 3}} hope that helps', {"a": {"b": 3}}),
    ('<think>{"no": 1}</think>{"a": 4}', {"a": 4}),
])
def test_parse_json_object(text, expected):
    assert parse_json_object(text) == expected


def test_parse_json_object_failure():
    with pytest.raises(LLMError):
        parse_json_object("no json here")


def test_json_mode_falls_back_when_server_rejects_response_format():
    # 1st 400: client drops the thinking flag; 2nd 400: json() drops response_format
    rec = Recorder([http_error(400), http_error(400), ok('{"fields": {}}')])
    out = NemotronClient(rec, sleep=lambda s: None).json("sys", "user")
    assert out == {"fields": {}}
    assert "response_format" in rec.calls[0][1] and "response_format" not in rec.calls[-1][1]


def test_json_uses_fast_model():
    rec = Recorder([ok('{"x": 1}')])
    c = NemotronClient(rec)
    c.json("s", "u")
    assert rec.calls[0][1]["model"] == c.fast


def test_tool_args_parsing():
    assert tool_args({"function": {"arguments": '{"a": 1}'}}) == {"a": 1}
    assert tool_args({"function": {"arguments": 'garbage {"a": 2} trailing'}}) == {"a": 2}
    with pytest.raises(LLMError):
        tool_args({"function": {"arguments": "[1, 2]"}})


def test_cost_estimate_uses_published_prices():
    c = NemotronClient(Recorder([ok(usage={"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})]))
    c.chat([{"role": "user", "content": "q"}])
    assert c.usage.cost_usd() == pytest.approx(0.30 + 0.90)


def test_list_models():
    c = NemotronClient(Recorder([{"data": [{"id": "b"}, {"id": "a"}]}]))
    assert c.list_models() == ["a", "b"]


# ---------------------------------------------------------------- live-path hardening
from decision_ladder.llm.client import parse_inline_tool_calls, pick_model  # noqa: E402

TOOLS = [{"type": "function", "function": {"name": "mortgage_payment"}}]


def test_inline_qwen_xml_tool_call_recovered():
    text = ("Let me compute.\n<tool_call>\n<function=mortgage_payment>\n<parameter=principal>\n500000\n</parameter>\n"
            "<parameter=annual_rate>\n4.5\n</parameter>\n</function>\n</tool_call>")
    res = NemotronClient(Recorder([ok(text)])).chat([{"role": "user", "content": "q"}], tools=TOOLS)
    assert res.tool_calls[0]["function"]["name"] == "mortgage_payment"
    assert json.loads(res.tool_calls[0]["function"]["arguments"]) == {"principal": 500000, "annual_rate": 4.5}
    assert res.content == "Let me compute."


def test_inline_nemotron_toolcall_json_recovered_and_unknown_names_ignored():
    text = '<TOOLCALL>[{"name": "mortgage_payment", "arguments": {"principal": 1}}, {"name": "rm_rf", "arguments": {}}]</TOOLCALL>'
    calls, rest = parse_inline_tool_calls(text, {"mortgage_payment"})
    assert [c["function"]["name"] for c in calls] == ["mortgage_payment"] and rest == ""


def test_inline_parsing_not_used_without_tools():
    text = "<tool_call>{\"name\": \"mortgage_payment\", \"arguments\": {}}</tool_call>"
    res = NemotronClient(Recorder([ok(text)])).chat([{"role": "user", "content": "q"}])
    assert res.tool_calls == []


def test_thinking_flag_sent_to_nemotron_and_dropped_on_400(monkeypatch):
    monkeypatch.setenv("DL_THINKING", "0")
    rec = Recorder([http_error(400), ok("fine")])
    c = NemotronClient(rec, sleep=lambda s: None)
    assert c.chat([{"role": "user", "content": "q"}]).content == "fine"
    assert rec.calls[0][1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in rec.calls[1][1] and not c.send_template_kwargs


def test_thinking_on_raises_token_budget_for_reasoner_only(monkeypatch):
    monkeypatch.setenv("DL_THINKING", "1")
    rec = Recorder([ok("a"), ok('{"x": 1}')])
    c = NemotronClient(rec)
    c.chat([{"role": "user", "content": "q"}], max_tokens=900)
    c.json("s", "u")
    assert rec.calls[0][1]["chat_template_kwargs"]["enable_thinking"] and rec.calls[0][1]["max_tokens"] >= 4000
    assert rec.calls[1][1]["chat_template_kwargs"]["enable_thinking"] is False


def test_empty_response_raises_after_one_retry():
    rec = Recorder([ok(""), ok("")])
    with pytest.raises(LLMError, match="empty response"):
        NemotronClient(rec).chat([{"role": "user", "content": "q"}])
    assert len(rec.calls) == 2 and "empty" in rec.calls[1][1]["messages"][-1]["content"]


def test_empty_response_recovers_on_retry():
    rec = Recorder([ok(""), ok("the answer")])
    c = NemotronClient(rec)
    assert c.chat([{"role": "user", "content": "q"}]).content == "the answer"
    assert c.log[-1]["purpose"].endswith("(retry after empty reply)")


def test_pick_model():
    avail = ["meta/llama", "nvidia/nemotron-3-super-120b-a12b-fp8", "nvidia/Nemotron-3-Nano-30B-A3B"]
    assert pick_model(avail, "nvidia/nemotron-3-super-120b-a12b-fp8", ("super",))[1] == "configured"
    m, why = pick_model(avail, "nvidia/nemotron-3-super-120b-a12b", ("super", "nemotron"))
    assert m == "nvidia/nemotron-3-super-120b-a12b-fp8" and why.startswith("auto")
    assert pick_model(avail, "x", ("nano",))[0] == "nvidia/Nemotron-3-Nano-30B-A3B"
    assert pick_model(["meta/llama"], "x", ("nano",))[1].startswith("not listed")


def test_resolve_models_switches_to_visible_ids():
    rec = Recorder([{"data": [{"id": "nvidia/nemotron-3-super-v2"}, {"id": "nvidia/nemotron-3-nano-v2"}]}])
    c = NemotronClient(rec)
    r = c.resolve_models()
    assert c.reasoner == "nvidia/nemotron-3-super-v2" and c.fast == "nvidia/nemotron-3-nano-v2"
    assert r["reasoner_reason"].startswith("auto")
