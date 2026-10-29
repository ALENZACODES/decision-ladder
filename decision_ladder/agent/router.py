"""Nemotron Nano as the router: pick the lifecycle stages a question touches, so Nemotron Super only sees
the tools of the apps that matter.

With 14 apps the OS exposes 50+ tools. Sending every schema on every call costs tokens and makes tool
choice harder. The router is one cheap Nano call in JSON mode; the stages it returns select the tool
subset. If the router fails or returns nothing usable, every tool is offered (never a silent dead end).
"""
from __future__ import annotations

import json
import re

from ..llm.client import LLMError, NemotronClient
from . import tools as T

# Core Decision Ladder tools by lifecycle stage (module tools come from the module registry).
CORE_STAGE = {
    "qualify_purchase": ["underwriting", "prequal"], "insurance_premium": ["prequal", "closing"],
    "find_path_to_yes": ["underwriting", "prequal"], "max_purchase_price": ["prequal", "underwriting"],
    "mortgage_payment": ["prequal", "servicing"], "penalty_by_lender": ["servicing"], "penalty_quick": ["servicing"],
    "renewal_payment_shock": ["servicing"], "compare_renewal_offers": ["servicing"], "switch_lender_check": ["servicing"],
    "home_value_estimate": ["property"], "market_snapshot": ["market"], "bank_rates": ["market", "servicing"],
    "rate_change": ["market"], "lender_match": ["underwriting"], "lender_directory": ["underwriting", "lead"],
    "penalty_methods": ["servicing"], "message_guardrail": ["lead"], "identity_screening": ["documents"],
    "web_research": ["market"], "lender_rate_check": ["market", "servicing"],
}
ALWAYS = {"market_snapshot"}   # cheap, frequently useful context

ROUTER_SYSTEM = ("You route questions for a Canadian mortgage broker's operating system to the lifecycle stages that "
                 "can answer them. Return JSON {\"stages\": [stage keys], \"reason\": \"one short sentence\"}. Pick 1 to 3 "
                 "stages; pick more only if the question clearly spans them.")

KEYWORDS = {
    "lead": r"\b(lead|referral|first call|outreach|message|text|email the client)\b",
    "prequal": r"\b(afford|pre-?qual|pre-?approv|max(imum)? (price|purchase)|how much can|rent (vs|or) buy|down payment plan|fhsa|rrsp|hbp)\b",
    "documents": r"\b(document|paperwork|checklist|t4|noa|pay ?stub|job letter|employment letter|id\b|gift letter)\b",
    "underwriting": r"\b(stress test|qualif|gds|tds|b-20|underwrit|readiness|lender (fit|match)|path to yes|decline|approve)\b",
    "property": r"\b(home value|house price|benchmark|apprais|worth|valuation|avm|postal|neighbou?rhood)\b",
    "closing": r"\b(clos(e|ing)|land transfer|ltt|mltt|lawyer|title insurance|cash to close|pst)\b",
    "servicing": r"\b(renew|penalty|ird|break|refinanc|prepay|switch|maturity|payout)\b",
    "market": r"\b(bank of canada|boc|policy rate|prime|bond|yield|inflation|cpi|market|rate cycle|news|osfi|fsra|latest)\b",
    "commercial": r"\b(commercial|private credit|dscr|noi|cap rate|debt yield|multifamily|mezz|bridge loan|investor)\b",
}


def stage_tools() -> dict[str, set[str]]:
    from .. import modules as OS
    OS.load_all()
    out: dict[str, set[str]] = {k: set() for k, _ in OS.STAGES}
    for name, stages in CORE_STAGE.items():
        for s in stages:
            out.setdefault(s, set()).add(name)
    for m in OS.MODULES.values():
        for t in m.tools:
            for s in m.stages:
                out.setdefault(s, set()).add(t)
    return out


def keyword_stages(question: str) -> list[str]:
    q = question.lower()
    return [s for s, rx in KEYWORDS.items() if re.search(rx, q)]


def route(llm: NemotronClient | None, question: str, available: set[str]) -> dict:
    """Return {"stages": [...], "tools": [...], "by": "nemotron-nano"|"keywords"|"all", "reason": str}."""
    from .. import modules as OS
    st = stage_tools()
    stage_desc = "\n".join(f"- {k}: {n}" for k, n in OS.STAGES)
    stages, by, reason = [], "all", ""
    if llm is not None:
        try:
            out = llm.json(ROUTER_SYSTEM, f"Stages:\n{stage_desc}\n\nQuestion: {question[:1500]}", max_tokens=200,
                           purpose="route")
            stages = [s for s in (out.get("stages") or []) if s in st]
            reason = str(out.get("reason") or "")[:200]
            by = "offline stand-in (keywords)" if llm.offline else "nemotron-nano"
        except LLMError as e:
            reason = f"router error: {e}"
    if not stages:
        stages = keyword_stages(question)
        if stages:
            by = "keywords"
    tools = set()
    for s in stages:
        tools |= st.get(s, set())
    tools = (tools | ALWAYS) & available
    if not stages or len(tools) <= len(ALWAYS):
        return {"stages": [], "tools": sorted(available), "by": "all", "reason": reason or "no stage matched; all tools offered"}
    if "web_research" in available and ("market" in stages or re.search(KEYWORDS["market"], question.lower())):
        tools.add("web_research")
    return {"stages": stages, "tools": sorted(tools), "by": by, "reason": reason}


def offline_route_reply(user: str) -> str:
    """Scripted stand-in reply for the router prompt (keywords only, labelled by the transport)."""
    q = user.split("Question:", 1)[-1]
    return json.dumps({"stages": keyword_stages(q)[:3], "reason": "offline keyword routing"})
