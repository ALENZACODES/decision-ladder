"""Deep links: open each embedded app pre-filled with the client's own numbers.

Most of the author's apps already keep their state in the URL (hash or query string) so a page can be
shared. The OS uses that: a rung computed by Cash to Close links to Cash to Close showing *this* client's
price, savings and down payment, not the app's defaults. Only parameters each app's own code reads are set.
"""
from __future__ import annotations

from urllib.parse import quote, urlencode


def _n(x) -> str:
    v = float(x)
    return str(int(v)) if v.is_integer() else f"{v:g}"


def deep_link(module: str, entry: str, f: dict, stage: str = "") -> str:
    base = f"/apps/{module}/{entry}"
    try:
        if module == "cash-to-close" and f.get("price") and f.get("down_payment") is not None:
            price, down = float(f["price"]), float(f["down_payment"])
            return base + "#" + urlencode({
                "price": _n(price), "savings": _n(f.get("savings") or down), "city": "to" if f.get("toronto") else "on",
                "ftb": "y" if f.get("first_time_buyer") else "n", "dp": f"{down / price * 100:.2f}",
                "am": "30" if int(f.get("amort_years", 25)) > 25 else "25"})
        if module == "canadian-mortgage-suite":
            tab = {"prequal": "afford", "closing": "closing", "underwriting": "stress", "servicing": "renew"}.get(stage)
            return base + (f"#{tab}" if tab else "")
        if module == "private-credit-screener" and f.get("loan"):
            keys = ("loan", "value", "noi", "rate", "amort", "termYrs", "capRate", "exitCapShift", "noiGrowth", "fees", "sponsorScore")
            return base + "#" + urlencode({k: _n(f[k]) for k in keys if f.get(k) is not None})
        if module == "renewal-shock-radar" and f.get("price") and f.get("contract_rate"):
            loan = float(f["price"]) - float(f.get("down_payment") or 0)
            rate = float(f["contract_rate"])
            return base + "#" + urlencode({"loan": _n(round(loan)), "origRate": _n(rate), "newRate": _n(round(rate + 1, 2)),
                                           "amort": _n(f.get("amort_years", 25)), "term": _n(f.get("term_years", 5)),
                                           "income": _n(f.get("annual_income") or 0)})
        if module == "renewal-check" and f.get("balance") and (f.get("renewal_rate") or f.get("new_rate")):
            return base + "?" + urlencode({"b": _n(f["balance"]), "y": _n(f.get("remaining_amort_years", 20)),
                                           "c": _n(f["contract_rate"]), "o": _n(f.get("renewal_rate") or f.get("new_rate"))})
        if module == "benchmark-home-value" and (f.get("postal_code") or f.get("city")):
            return base + "?a=" + quote(str(f.get("postal_code") or f.get("city")))
    except (TypeError, ValueError):
        pass
    return base
