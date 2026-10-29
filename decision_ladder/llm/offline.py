"""A scripted stand-in for the Token Factory endpoint, for tests and the no-key demo.

It speaks the same Chat Completions wire format as Token Factory (tool calls, JSON mode, usage), so
everything above the transport runs unchanged. It is NOT a language model: it routes with keywords and
fills answers from tool results with templates. The UI and API label every response produced this way as
``offline (scripted, no model)`` so it can never be mistaken for Nemotron output.
"""
from __future__ import annotations

import json
import re
from typing import Any

OFFLINE_MODEL = "offline/scripted-no-model"


def _num(pattern: str, text: str, cast=float) -> Any:
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    s = m.group(1).replace(",", "").replace("$", "").lower()
    mult = 1
    if s.endswith("k"):
        s, mult = s[:-1], 1_000
    elif s.endswith("m"):
        s, mult = s[:-1], 1_000_000
    try:
        return cast(float(s) * mult)
    except ValueError:
        return None


def _context(text: str) -> dict:
    if "FILE CONTEXT (JSON):" in text:
        try:
            return json.loads(text.split("FILE CONTEXT (JSON):", 1)[1].strip())
        except json.JSONDecodeError:
            return {}
    return {}


def _plan(question: str, tool_names: set[str]) -> list[tuple[str, dict]]:
    q = question.lower()
    ctx = _context(question)
    calls: list[tuple[str, dict]] = []
    M = r"\$?([\d,.]+[km]?)"
    if any(w in q for w in ("penalty", "break", "ird", "prepayment")):
        lender = next((b for b in ("rbc", "td", "scotia", "bmo", "cibc", "national") if re.search(rf"\b{b}", q)), None)
        bal = ctx.get("balance") or _num(rf"(?:balance|owe|of)\s*{M}", question)
        rate = ctx.get("contract_rate") or _num(r"(\d+(?:\.\d+)?)\s*%", question)
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", question)
        if lender and bal and rate and len(dates) >= 2:
            calls.append(("penalty_by_lender", {"lender": lender, "balance": bal, "contract_rate": rate,
                                                "term_start": dates[0], "maturity": dates[1],
                                                **({"payout_date": dates[2]} if len(dates) > 2 else {}),
                                                **({"original_posted_rate": op} if (op := _num(r"posted[^%]{0,30}?(\d+(?:\.\d+)?)\s*%", question)) else {})}))
        elif bal and rate:
            months = _num(r"(\d+)\s*months", question, int) or 24
            calls.append(("penalty_quick", {"balance": bal, "contract_rate": rate, "months_remaining": months,
                                            "comparison_rate": max(0.0, rate - 1.0)}))
    if any(w in q for w in ("qualif", "afford", "stress test", "pass", "approve", "gds", "tds")):
        f = {k: ctx[k] for k in ("price", "down_payment", "annual_income", "contract_rate", "property_tax_annual",
                                 "other_debt_monthly", "amort_years", "first_time_buyer", "new_build", "condo_fees_monthly",
                                 "heat_annual") if ctx.get(k) is not None}
        f.setdefault("price", _num(rf"(?:price|for|home)\s*{M}", question))
        f.setdefault("down_payment", _num(rf"{M}\s*down|down(?: payment)?\s*(?:of)?\s*{M}", question))
        f.setdefault("annual_income", _num(rf"(?:income|earn\w*|make)\s*(?:of)?\s*{M}", question))
        f.setdefault("contract_rate", _num(r"(\d+(?:\.\d+)?)\s*%", question))
        if all(f.get(k) for k in ("price", "down_payment", "annual_income", "contract_rate")):
            calls.append(("find_path_to_yes" if any(w in q for w in ("how", "fix", "path", "what would")) else "qualify_purchase", f))
    if any(w in q for w in ("market", "bank of canada", "policy rate", "prime", "bond", "spread")):
        calls.append(("market_snapshot", {}))
    if "web_research" in tool_names and any(w in q for w in ("latest", "recent", "news", "this week", "announce", "osfi", "fsra", "today")):
        calls.append(("web_research", {"query": question[:200], "scope": "official"}))
    if any(w in q for w in ("renewal shock", "payment shock", "renew")) and ctx.get("original_principal"):
        calls.append(("renewal_payment_shock", {k: ctx[k] for k in ("original_principal", "original_rate", "original_amort_years",
                                                                     "months_elapsed", "renewal_rate") if k in ctx}))
    # Mortgage OS module tools (the author's apps)
    price = ctx.get("price") or _num(rf"(?:\$|price of |home (?:for|at) |wants a )\$?([\d,.]+[km]?)\s*(?:home|house|condo|semi|purchase|property)", question) \
        or _num(rf"\$([\d,.]+[km]?)\s*(?:home|house|condo|semi)", question)
    if any(w in q for w in ("closing", "close on", "cash to close", "land transfer", "ltt")) and price:
        saved = ctx.get("savings") or _num(rf"\$?([\d,.]+[km]?)\s*(?:saved|in savings)", question) or 0
        ftb = "first-time" in q or "first time" in q
        calls.append(("cash_to_close_ontario", {"price": price, "savings": saved, "first_time": ftb, "toronto": "toronto" in q}))
        calls.append(("land_transfer_tax", {"price": price, "province": "ON", "first_time": ftb, "toronto": "toronto" in q}))
    if any(w in q for w in ("benchmark", "home value", "house price", "worth")):
        place = next((c.title() for c in ("oakville", "toronto", "mississauga", "brampton", "markham", "vaughan", "hamilton",
                                         "ottawa", "calgary", "edmonton", "vancouver") if c in q), None)
        if place:
            ptype = next((t for t in ("detached", "semi", "town", "condo") if t in q), "composite")
            calls.append(("benchmark_home_price", {"place": place, "property_type": ptype}))
    if "affordab" in q and "index" in q:
        calls.append(("housing_affordability_index", {}))
    if any(w in q for w in ("commercial", "dscr", "noi", "private credit")):
        loan = _num(r"\$([\d,.]+[km])\s*(?:on|loan)", question)
        value = _num(r"on a \$([\d,.]+[km])", question)
        noi = _num(r"\$([\d,.]+[km]?)\s*noi", question)
        rate = _num(r"(\d+(?:\.\d+)?)\s*%", question)
        if loan and value and noi and rate:
            calls.append(("private_credit_deal_screen", {"loan": loan, "value": value, "noi": noi, "rate": rate,
                                                         "amort": 0 if "interest-only" in q or "interest only" in q else 25}))
    if any(w in q for w in ("document", "paperwork", "checklist")):
        calls.append(("buyer_document_checklist", {"work": "self" if "self-employed" in q else "salaried",
                                                   "sources": ["savings"] + (["gift"] if "gift" in q else [])}))
    calls = [c for c in calls if c[0] in tool_names]
    if not calls and "market_snapshot" in tool_names:
        calls.append(("market_snapshot", {}))
    return calls


def _fmt(v: Any) -> str:
    if isinstance(v, float) and abs(v) >= 100:
        return f"${v:,.2f}"
    return str(v)


def _summarize(results: list[tuple[str, dict]]) -> str:
    lines = ["[offline scripted answer - no language model was called]"]
    for name, r in results:
        if "error" in r:
            lines.append(f"- {name}: could not compute ({r['error']}).")
            continue
        if name in ("qualify_purchase",):
            lines.append(f"- Stress test at {r['qualifying_rate']}%: GDS {r['gds']}%, TDS {r['tds']}%, "
                         f"{'passes' if r['passes'] else 'fails'}. Stressed payment {_fmt(r['stressed_payment'])}.")
        elif name == "find_path_to_yes":
            lines.append(f"- Passes now: {r['passes_now']}. " + "; ".join(r.get("reasons", [])))
            for o in r.get("options", []):
                if o.get("max_price"):
                    lines.append(f"  - Max price {_fmt(o['max_price'])}")
                if o.get("min_down_payment"):
                    lines.append(f"  - Min down payment {_fmt(o['min_down_payment'])}")
                if o.get("min_annual_income"):
                    lines.append(f"  - Min income {_fmt(o['min_annual_income'])}")
        elif name == "penalty_quick":
            p = r["penalty"]
            lines.append(f"- Penalty estimate {_fmt(p['penalty'])} ({p['method']}).")
        elif name == "penalty_by_lender":
            e = r.get("estimate") or {}
            lines.append(f"- {r.get('lender_code', '').upper()} method penalty estimate: {e.get('total_estimate')} "
                         f"(controlling: {e.get('controlling_method')}).")
        elif name == "market_snapshot":
            lines.append(f"- BoC policy rate {r['policy_rate']['rate']}% ({r['policy_rate']['date']}), "
                         f"prime {r['prime']['rate']}%, GoC 5-year {r['goc_curve']['60']['rate']}%.")
        elif name == "renewal_payment_shock":
            lines.append(f"- Payment {_fmt(r['payment_before'])} -> {_fmt(r['payment_after'])} ({r['pct_change']}%).")
        elif name == "cash_to_close_ontario":
            lines.append(f"- Cash to Close: {_fmt(float(r['cashToClose']))} needed on closing day "
                         f"({_fmt(float(r['down']))} down payment); gap vs savings {_fmt(float(r.get('gap', 0)))}.")
        elif name == "land_transfer_tax":
            lines.append(f"- Land transfer tax (Canadian Mortgage Suite): {_fmt(float(r['total']))} after rebates.")
        elif name == "benchmark_home_price":
            lines.append(f"- Benchmark Home Value: {r['city']} {r['property_type']} benchmark {_fmt(float(r['benchmark_price']))} "
                         f"({r['yoy_change_pct']}% over 12 months).")
        elif name == "housing_affordability_index":
            lines.append(f"- BoC affordability index {r['affordability_index_pct']}% ({r['quarter']}) vs a "
                         f"{r['long_run_average_pct']}% long-run average.")
        elif name == "private_credit_deal_screen":
            m = r.get("metrics", {})
            lines.append(f"- Private Credit Screener: grade {r['grade']}, LTV {m.get('ltv')}%, DSCR {round(m.get('dscr', 0), 2)}.")
        elif name == "buyer_document_checklist":
            lines.append("- Doc Quest checklist, slowest first: " + ", ".join(d["title"] for d in r.get("documents", [])[:6]) + ".")
        elif name == "web_research":
            for s in r.get("sources", [])[:3]:
                lines.append(f"- Source: {s['title']} <{s['url']}>")
        else:
            lines.append(f"- {name}: done.")
    lines.append("Next: confirm inputs with the client and verify with the lender.")
    return "\n".join(lines)


def _memo(user: str) -> str:
    from ..ladder.runner import template_memo
    try:
        payload = json.loads(user.split("LADDER RESULTS (JSON):", 1)[1])
        rungs = payload["ladder"]
        for r in rungs:
            r.setdefault("evidence", {"options": r.get("options", [])})
        return "[offline template memo - no language model was called]\n" + template_memo(rungs)
    except Exception:  # pragma: no cover - defensive
        return "[offline template memo]"


class OfflineTransport:
    def __init__(self):
        self.requests: list[dict] = []

    def __call__(self, path: str, payload: dict | None, method: str = "POST") -> dict:
        self.requests.append({"path": path, "payload": payload})
        if path == "models":
            return {"data": [{"id": OFFLINE_MODEL}]}
        msgs = payload["messages"]
        system = next((m["content"] for m in msgs if m["role"] == "system"), "")
        last = msgs[-1]
        usage = {"prompt_tokens": sum(len(str(m.get("content", ""))) // 4 for m in msgs), "completion_tokens": 60}
        if "You route questions" in system:
            from ..agent.router import offline_route_reply
            return self._msg(offline_route_reply(last["content"]), usage)
        if "underwriting documents" in system:
            from ..intake.documents import read
            r = read(last["content"])
            fields = {k: {"value": v, "quote": r["quotes"].get(k, "")} for k, v in r["extracted"].items()
                      if not isinstance(v, (list, bool))}
            return self._msg(json.dumps({"type": r["type"], "fields": fields}), usage)
        if payload.get("response_format") or "JSON" in system and "fields" in system:
            from ..intake.extract import pattern_extract
            text = last["content"]
            return self._msg(json.dumps({"fields": pattern_extract(text)}), usage)
        if "decision memo" in system:
            return self._msg(_memo(last["content"]), usage)
        if "message from a Canadian mortgage broker" in system:
            facts = re.search(r'"first_name":\s*"([^"]+)"', last["content"])
            name = facts.group(1) if facts else "there"
            return self._msg(f"Hi {name}, thanks for sending your details. We've reviewed your file and would like to "
                             "walk you through it. Reply with a good time for a 15-minute call. [offline draft]", usage)
        tools = {t["function"]["name"] for t in payload.get("tools") or []}
        if last["role"] == "user" and tools:
            calls = _plan(last["content"], tools)
            tc = [{"id": f"call_{i}", "type": "function",
                   "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]
            return {"model": OFFLINE_MODEL, "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": tc},
                                                         "finish_reason": "tool_calls"}], "usage": usage}
        if last["role"] == "tool" or (last["role"] == "user" and not tools):
            results = []
            names = {c["id"]: c["function"]["name"] for m in msgs if m["role"] == "assistant"
                     for c in m.get("tool_calls") or []}
            for m in msgs:
                if m["role"] == "tool":
                    name = m.get("name") or names.get(m.get("tool_call_id"), "")
                    try:
                        results.append((name, json.loads(m["content"])))
                    except json.JSONDecodeError:
                        results.append((name, {"error": "unreadable"}))
            return self._msg(_summarize(results), usage)
        return self._msg("[offline] No answer.", usage)

    @staticmethod
    def _msg(content: str, usage: dict) -> dict:
        return {"model": OFFLINE_MODEL, "choices": [{"message": {"role": "assistant", "content": content},
                                                     "finish_reason": "stop"}], "usage": usage}


def offline_client():
    from .client import NemotronClient
    return NemotronClient(OfflineTransport(), reasoner="offline/nemotron-super-stand-in",
                          fast="offline/nemotron-nano-stand-in", ultra="offline/nemotron-ultra-stand-in", offline=True)
