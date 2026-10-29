"""The broker copilot: a Nemotron tool-calling loop with a provenance gate.

1. Nemotron reads the question and calls tools (calculators, rate book, Tavily research).
2. Tool results are appended to the conversation and to an evidence ledger.
3. When Nemotron answers, the verifier checks every number against the ledger and the user's question.
4. If any figure is unsupported, Nemotron gets ONE repair turn listing the bad figures; if the repaired
   answer still fails, the unsupported figures are marked ``[unverified]`` in the text shown to the user.
5. Borrower-facing drafts pass the outbound guardrail before they are returned.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..engines import guardrail
from ..llm.client import LLMError, NemotronClient, tool_args
from . import tools as T
from . import verify

SYSTEM = """You are Decision Ladder, the analyst desk for a licensed Canadian mortgage broker (Ontario, Alberta, BC).
Rules you must follow:
- Every dollar amount, rate, ratio or count you state MUST come from a tool result in this conversation or from the user's message. Never do mortgage arithmetic yourself; call a tool.
- Prefer one well-chosen tool call over many. Call several tools in one turn when they are independent.
- For anything about current events (a Bank of Canada decision, a new OSFI/FSRA rule, a lender's rate change) use web_research and cite the URL.
- You support the broker; you are not the broker. Do not promise approval, quote a rate as an offer, or guarantee outcomes. Say figures are estimates to confirm.
- Be concise: short paragraphs or bullets, plain English, Canadian spelling. End with the next action for the broker."""


@dataclass
class Step:
    kind: str  # tool | answer | repair | research
    name: str = ""
    args: dict = field(default_factory=dict)
    result: Any = None
    ms: float = 0.0


@dataclass
class AgentResult:
    answer: str
    steps: list[Step]
    verification: dict
    repaired: bool
    usage: dict
    model: str

    def to_dict(self) -> dict:
        return {"answer": self.answer, "repaired": self.repaired, "verification": self.verification,
                "usage": self.usage, "model": self.model,
                "steps": [{"kind": s.kind, "name": s.name, "args": s.args, "result": s.result, "ms": round(s.ms, 1)}
                          for s in self.steps]}


def research_tool(research) -> T.Tool:
    def fn(a: dict) -> dict:
        return research.search(a["query"], scope=a.get("scope", "official"), days=a.get("days"))
    return T.Tool("web_research",
                  "Search official Canadian sources (Bank of Canada, OSFI, FSRA, CMHC, Canada.ca) or lender sites with Tavily. Use for anything newer than the rate book.",
                  T._obj({"query": T.S, "scope": {"type": "string", "enum": ["official", "lenders", "both"]},
                          "days": {"type": "integer", "description": "limit to news from the last N days"}}, ["query"]),
                  fn, "research")


class Copilot:
    def __init__(self, llm: NemotronClient, research=None, max_rounds: int = 6, tool_names: list[str] | None = None):
        self.llm = llm
        self.max_rounds = max_rounds
        self.extra = {}
        if research is not None:
            t = research_tool(research)
            self.extra[t.name] = t
        self.tool_names = tool_names

    def _specs(self) -> list[dict]:
        names = self.tool_names or list(T.TOOLS)
        return T.specs(names + [n for n in self.extra if n not in names], list(self.extra.values()))

    def ask(self, question: str, *, context: dict | None = None, history: list[dict] | None = None) -> AgentResult:
        msgs: list[dict] = [{"role": "system", "content": SYSTEM}]
        msgs += history or []
        user = question if not context else f"{question}\n\nFILE CONTEXT (JSON):\n{json.dumps(context)}"
        msgs.append({"role": "user", "content": user})
        steps: list[Step] = []
        evidence: list[Any] = [user]
        answer = ""
        for _ in range(self.max_rounds):
            res = self.llm.chat(msgs, tools=self._specs(), purpose="copilot")
            if not res.tool_calls:
                answer = res.content
                break
            msgs.append(res.message)
            for call in res.tool_calls:
                name = call["function"]["name"]
                t0 = time.perf_counter()
                try:
                    args = tool_args(call)
                except LLMError as e:
                    args, out = {}, {"error": str(e)}
                else:
                    out = T.run(name, args, self.extra)
                steps.append(Step("research" if name == "web_research" else "tool", name, args, out,
                                  (time.perf_counter() - t0) * 1000))
                evidence.append(out)
                msgs.append({"role": "tool", "tool_call_id": call["id"], "content": T.dumps(out)[:12000]})
        else:
            res = self.llm.chat(msgs + [{"role": "user", "content": "Answer now using only the tool results above."}],
                                purpose="copilot-final")
            answer = res.content

        rep = verify.verify(answer, *evidence)
        repaired = False
        if not rep.ok:
            bad = ", ".join(c.text for c in rep.unsupported)
            msgs.append({"role": "assistant", "content": answer})
            msgs.append({"role": "user", "content":
                         f"These figures do not appear in any tool result or in my message: {bad}. "
                         "Rewrite the answer. Either call a tool to compute them or remove them."})
            fix = self.llm.chat(msgs, tools=self._specs(), purpose="copilot-repair")
            if fix.tool_calls:
                msgs.append(fix.message)
                for call in fix.tool_calls:
                    name = call["function"]["name"]
                    try:
                        args = tool_args(call)
                        out = T.run(name, args, self.extra)
                    except LLMError as e:
                        args, out = {}, {"error": str(e)}
                    steps.append(Step("repair", name, args, out))
                    evidence.append(out)
                    msgs.append({"role": "tool", "tool_call_id": call["id"], "content": T.dumps(out)[:12000]})
                fix = self.llm.chat(msgs, purpose="copilot-repair-final")
            rep2 = verify.verify(fix.content, *evidence)
            if fix.content and len(rep2.unsupported) <= len(rep.unsupported):
                answer, rep, repaired = fix.content, rep2, True
            answer = verify.annotate(answer, rep)
        steps.append(Step("answer", result=answer))
        return AgentResult(answer, steps, rep.to_dict(), repaired, self.llm.usage.to_dict(), self.llm.reasoner)


def draft_borrower_message(llm: NemotronClient, *, purpose: str, facts: dict, channel: str = "sms") -> dict:
    """Nemotron drafts a short borrower message; the guardrail decides whether it can be sent."""
    limit = 300 if channel == "sms" else 900
    sys = ("Write a short, warm message from a Canadian mortgage broker's office to a client. "
           f"Max {limit} characters. No interest rates, no percentages, no promises of approval, no urgency language, "
           "never ask for SIN, passwords or card numbers. Invite them to book a call. Plain text only.")
    res = llm.chat([{"role": "system", "content": sys},
                    {"role": "user", "content": f"Purpose: {purpose}\nFacts: {json.dumps(facts)}"}],
                   model=llm.fast, max_tokens=300, temperature=0.3, purpose="draft-message")
    text = res.content.strip()[:limit]
    chk = guardrail.check(text)
    return {"draft": text, "guardrail": chk, "send_text": text if chk["allowed"] else guardrail.safe_replacement(),
            "blocked": not chk["allowed"]}
