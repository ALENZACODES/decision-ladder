"""Nemotron on Nebius Token Factory: a small, dependency-free OpenAI-compatible client.

Token Factory exposes an OpenAI-compatible Chat Completions API at
``https://api.tokenfactory.nebius.com/v1/``. This module talks to it with the standard library only
(``urllib``), so the whole system installs with no third-party packages.

Two NVIDIA open models are used, each for what it is good at:

* the *reasoner* (default ``nvidia/nemotron-3-super-120b-a12b``) plans the ladder, calls tools and writes
  the broker memo;
* the *fast* model (default ``nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B``) does cheap, high-volume work:
  intent routing, document field extraction and client message drafts;
* the *ultra* model (Nemotron 3 Ultra, when your key can see it) is used where the hackathon brief says to
  "reach for Ultra": the final credit decision memo over the whole client journey. If Ultra is not
  available the reasoner is used, and the run reports which model wrote the memo.

Model IDs on Token Factory change over time. Override them with ``DL_MODEL_REASONER`` /
``DL_MODEL_FAST``, and run ``python -m decision_ladder models`` to list what your key can see.

The transport is injectable. Tests and the offline demo pass a scripted transport, so no test ever needs
a network connection or an API key.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_REASONER = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_FAST = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_ULTRA = "nvidia/nemotron-3-ultra"   # resolved against /v1/models at startup; falls back to the reasoner

# USD per 1M tokens (input, output) as published for Token Factory on 2026-10-20. Used only to show an
# approximate cost next to each run; your invoice is authoritative.
PRICE_PER_M = {
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
}


class LLMError(RuntimeError):
    """The model endpoint failed or returned something unusable."""


class Transport(Protocol):
    def __call__(self, path: str, payload: dict | None, method: str = "POST") -> dict: ...


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, usage: dict | None, latency_ms: float) -> None:
        usage = usage or {}
        p, c = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        self.calls += 1
        self.prompt_tokens += p
        self.completion_tokens += c
        self.latency_ms += latency_ms
        m = self.by_model.setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
        m["calls"] += 1
        m["prompt_tokens"] += p
        m["completion_tokens"] += c

    def cost_usd(self) -> float:
        total = 0.0
        for model, m in self.by_model.items():
            pin, pout = PRICE_PER_M.get(model, (0.0, 0.0))
            total += m["prompt_tokens"] / 1e6 * pin + m["completion_tokens"] / 1e6 * pout
        return round(total, 6)

    def to_dict(self) -> dict:
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "latency_ms": round(self.latency_ms, 1),
                "approx_cost_usd": self.cost_usd(), "by_model": self.by_model}


def http_transport(base_url: str, api_key: str, timeout: float = 60.0) -> Transport:
    """Real HTTPS transport (standard library)."""
    base = base_url if base_url.endswith("/") else base_url + "/"

    def send(path: str, payload: dict | None, method: str = "POST") -> dict:
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(base + path.lstrip("/"), data=data, method=method, headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "decision-ladder/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            err = LLMError(f"HTTP {e.code} from Token Factory: {body}")
            err.status = e.code  # type: ignore[attr-defined]
            raise err from None
        except urllib.error.URLError as e:
            raise LLMError(f"cannot reach Token Factory at {base}: {e.reason}") from None

    return send


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict]
    finish_reason: str
    model: str
    raw: dict

    @property
    def message(self) -> dict:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


class NemotronClient:
    """Chat Completions with tool calling, JSON output, retries and usage accounting."""

    RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}

    def __init__(self, transport: Transport | None = None, *, api_key: str | None = None,
                 base_url: str | None = None, reasoner: str | None = None, fast: str | None = None,
                 ultra: str | None = None,
                 max_retries: int = 3, sleep: Callable[[float], None] = time.sleep, offline: bool = False):
        self.base_url = base_url or os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL)
        self.reasoner = reasoner or os.environ.get("DL_MODEL_REASONER", DEFAULT_REASONER)
        self.fast = fast or os.environ.get("DL_MODEL_FAST", DEFAULT_FAST)
        self.ultra = ultra or os.environ.get("DL_MODEL_ULTRA", DEFAULT_ULTRA)
        self.offline = offline
        if transport is None:
            key = api_key or os.environ.get("NEBIUS_API_KEY")
            if not key:
                raise LLMError("NEBIUS_API_KEY is not set. Create a key at tokenfactory.nebius.com, "
                               "or run with --offline to use the scripted demo model.")
            transport = http_transport(self.base_url, key)
        self.transport = transport
        self.max_retries = max_retries
        self.sleep = sleep
        self.usage = Usage()
        self.log: list[dict] = []
        # Nemotron 3 reasons by default. Reasoning tokens cost time and can eat max_tokens, so the default
        # is OFF; set DL_THINKING=1 to turn it on for the reasoner (memo + copilot).
        self.thinking = os.environ.get("DL_THINKING", "0") == "1"
        self.send_template_kwargs = os.environ.get("DL_SEND_THINKING_FLAG", "1") == "1"

    # ------------------------------------------------------------------ low level
    def _post(self, payload: dict) -> dict:
        attempt = 0
        while True:
            t0 = time.perf_counter()
            try:
                out = self.transport("chat/completions", payload)
                self.usage.add(payload["model"], out.get("usage"), (time.perf_counter() - t0) * 1000)
                return out
            except LLMError as e:
                status = getattr(e, "status", None)
                if attempt >= self.max_retries or (status is not None and status not in self.RETRY_STATUS):
                    raise
                attempt += 1
                self.sleep(min(8.0, 0.5 * 2 ** attempt) + random.random() * 0.25)

    def chat(self, messages: list[dict], *, model: str | None = None, tools: list[dict] | None = None,
             tool_choice: str | dict | None = None, temperature: float = 0.0, max_tokens: int = 1200,
             json_mode: bool = False, purpose: str = "") -> ChatResult:
        model = model or self.reasoner
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature,
                                   "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        think = self.thinking and model in (self.reasoner, self.ultra) and not json_mode
        if self.send_template_kwargs and "nemotron" in model.lower():
            payload["chat_template_kwargs"] = {"enable_thinking": think}
            if think:
                payload["max_tokens"] = max(max_tokens, 4000)
        try:
            out = self._post(payload)
        except LLMError as e:
            if getattr(e, "status", None) == 400 and "chat_template_kwargs" in payload:
                # endpoint does not accept the flag: stop sending it and retry once
                self.send_template_kwargs = False
                payload = {k: v for k, v in payload.items() if k != "chat_template_kwargs"}
                out = self._post(payload)
            else:
                raise
        choices = out.get("choices") or []
        if not choices:
            raise LLMError(f"no choices in response: {str(out)[:300]}")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if isinstance(content, list):  # some servers return content parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = strip_reasoning(content)
        calls = [_norm_call(c, i) for i, c in enumerate(msg.get("tool_calls") or [])]
        if not calls and tools and content:
            # some servers return the model's raw tool-call markup in content instead of tool_calls
            parsed, rest = parse_inline_tool_calls(content, {t["function"]["name"] for t in tools})
            if parsed:
                calls, content = parsed, rest
        if not calls and not content:
            # Seen live with Nemotron Super after long tool results: no content, no tool_calls, finish=stop.
            # 1) the answer or call may sit in the reasoning field; 2) otherwise ask once more, explicitly.
            reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            if isinstance(reasoning, str) and reasoning.strip():
                if tools:
                    calls, _ = parse_inline_tool_calls(reasoning, {t["function"]["name"] for t in tools})
                if not calls and not tools:
                    content = strip_reasoning(reasoning).strip()
            if not calls and not content and not getattr(self, "_retrying_empty", False):
                self._retrying_empty = True
                try:
                    nudge = {"role": "user", "content": "Your last reply was empty. Reply now: call one of the tools, "
                                                        "or give the final answer using only figures from tool results."}
                    return self.chat(messages + [nudge], model=model, tools=tools, tool_choice=tool_choice,
                                     temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
                                     purpose=(purpose + " (retry after empty reply)").strip())
                finally:
                    self._retrying_empty = False
        if not calls and not content:
            raise LLMError(f"empty response from {model} (finish_reason={choices[0].get('finish_reason')}); "
                           "if reasoning is on, raise max_tokens or set DL_THINKING=0")
        res = ChatResult(content, calls, choices[0].get("finish_reason") or "", out.get("model", model), out)
        self.log.append({"purpose": purpose, "model": model, "finish": res.finish_reason,
                         "tool_calls": [c["function"]["name"] for c in calls],
                         "usage": out.get("usage") or {}})
        return res

    def json(self, system: str, user: str, *, model: str | None = None, max_tokens: int = 900,
             purpose: str = "") -> dict:
        """Ask for a JSON object. Falls back to extracting the first {...} block if the server ignores
        response_format."""
        msgs = [{"role": "system", "content": system + "\nReply with one JSON object only."},
                {"role": "user", "content": user}]
        try:
            res = self.chat(msgs, model=model or self.fast, json_mode=True, max_tokens=max_tokens, purpose=purpose)
        except LLMError as e:
            if getattr(e, "status", None) == 400:  # server rejected response_format; retry without it
                res = self.chat(msgs, model=model or self.fast, max_tokens=max_tokens, purpose=purpose)
            else:
                raise
        return parse_json_object(res.content)

    def list_models(self) -> list[str]:
        out = self.transport("models", None, "GET")
        return sorted(m.get("id", "") for m in out.get("data", []))

    def resolve_models(self) -> dict:
        """Check the configured model IDs against /v1/models and switch to a visible Nemotron if needed."""
        ids = self.list_models()
        self.reasoner, r1 = pick_model(ids, self.reasoner, ("super", "ultra", "nemotron-3", "nemotron"))
        self.fast, r2 = pick_model(ids, self.fast, ("nano", "lightning", "mini", "nemotron"))
        if self.ultra in ids:
            r3 = "configured"
        else:
            ultras = sorted((m for m in ids if "nemotron" in m.lower() and "ultra" in m.lower()), key=len)
            if ultras:
                self.ultra, r3 = ultras[0], "auto: picked the Nemotron Ultra model listed"
            else:
                self.ultra, r3 = self.reasoner, "no Nemotron Ultra visible to this key: the reasoner writes the decision memo"
        return {"reasoner": self.reasoner, "reasoner_reason": r1, "fast": self.fast, "fast_reason": r2,
                "ultra": self.ultra, "ultra_reason": r3,
                "nemotron_models": [m for m in ids if "nemotron" in m.lower()]}


# ---------------------------------------------------------------------- helpers
def _norm_call(call: dict, i: int) -> dict:
    fn = call.get("function") or {}
    args = fn.get("arguments")
    if isinstance(args, dict):
        args = json.dumps(args)
    return {"id": call.get("id") or f"call_{i}", "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": args or "{}"}}


def strip_reasoning(text: str) -> str:
    """Nemotron reasoning modes may emit <think>...</think>; the user-facing answer is what follows."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def parse_json_object(text: str) -> dict:
    text = strip_reasoning(text or "")
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    try:
        val = json.loads(text)
        if isinstance(val, dict):
            return val
    except json.JSONDecodeError:
        pass
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    val = json.loads(text[start:i + 1])
                    if isinstance(val, dict):
                        return val
                except json.JSONDecodeError:
                    start = None
    raise LLMError(f"model did not return a JSON object: {text[:200]!r}")


_QWEN_CALL = re.compile(r"<tool_call>\s*<function=([\w.-]+)>(.*?)</function>\s*</tool_call>", re.S)
_QWEN_PARAM = re.compile(r"<parameter=([\w.-]+)>\s*(.*?)\s*</parameter>", re.S)
_JSON_BLOCKS = (re.compile(r"<TOOLCALL>\s*(\[.*?\])\s*</TOOLCALL>", re.S),
                re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S))


def _param_value(raw: str):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_inline_tool_calls(text: str, allowed: set[str]) -> tuple[list[dict], str]:
    """Recover tool calls written into the message text.

    Handles the Qwen3-Coder XML format Nemotron 3 Super emits (``<tool_call><function=name><parameter=k>v
    </parameter></function></tool_call>``), Nemotron's ``<TOOLCALL>[{...}]</TOOLCALL>`` JSON list and
    ``<tool_call>{json}</tool_call>``. Only names in ``allowed`` are accepted."""
    calls: list[dict] = []
    rest = text
    for m in _QWEN_CALL.finditer(text):
        name = m.group(1)
        if name in allowed:
            args = {k: _param_value(v) for k, v in _QWEN_PARAM.findall(m.group(2))}
            calls.append({"name": name, "arguments": args})
        rest = rest.replace(m.group(0), "")
    for rx in _JSON_BLOCKS:
        for m in rx.finditer(rest):
            try:
                val = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            for item in val if isinstance(val, list) else [val]:
                if isinstance(item, dict) and item.get("name") in allowed:
                    args = item.get("arguments") or item.get("parameters") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    calls.append({"name": item["name"], "arguments": args})
            rest = rest.replace(m.group(0), "")
    out = [{"id": f"inline_{i}", "type": "function",
            "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for i, c in enumerate(calls)]
    return out, rest.strip()


def pick_model(available: list[str], configured: str, prefer: tuple[str, ...]) -> tuple[str, str]:
    """Return (model_id, reason). Keeps ``configured`` if the key can see it, otherwise picks the best
    NVIDIA Nemotron match by preference keywords (case-insensitive)."""
    if configured in available:
        return configured, "configured"
    low = {m.lower(): m for m in available}
    if configured.lower() in low:
        return low[configured.lower()], "configured (case-insensitive match)"
    nv = [m for m in available if "nemotron" in m.lower()]
    for kw in prefer:
        hits = sorted((m for m in nv if kw in m.lower()), key=len)
        if hits:
            return hits[0], f"auto: configured id not listed; picked Nemotron model matching '{kw}'"
    if nv:
        return sorted(nv)[0], "auto: first Nemotron model listed"
    return configured, "not listed and no Nemotron model visible to this key"


def tool_args(call: dict) -> dict:
    raw = call["function"].get("arguments") or "{}"
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        val = parse_json_object(raw)
    if not isinstance(val, dict):
        raise LLMError(f"tool arguments are not an object: {raw!r}")
    return val
