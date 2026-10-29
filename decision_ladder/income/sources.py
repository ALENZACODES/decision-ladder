"""Qualifying income by source, the way Canadian lenders typically underwrite each type.

Every source returns the annual qualifying figure, the method that produced it, the documents a lender will
ask for, and flags an underwriter would raise. Histories are listed oldest first; the two most recent years
are used. A declining trend qualifies on the lower, most recent year rather than the average.
"""
from __future__ import annotations

from . import params as P

DOCS = {
    "salary": ["employment letter (title, start date, salary, permanent/probation status)", "pay stub within 30 days",
               "most recent T4 or NOA"],
    "hourly": ["employment letter stating guaranteed hours and hourly rate", "pay stub within 30 days", "most recent T4"],
    "variable": ["T4s and NOAs for the two most recent years", "employment letter confirming the income is ongoing",
                 "year-to-date pay stub"],
    "self_employed": ["T1 Generals with T2125 for two years", "NOAs for two years (no taxes owing)",
                      "business licence or articles of incorporation", "business bank statements"],
    "pension": ["pension statement or T4A", "bank statement showing deposits"],
    "government": ["T4A(P) / T4A(OAS) or benefit statement", "bank statement showing deposits"],
    "support": ["court order or separation agreement", "proof of receipt (bank statements, 3-12 months)"],
    "ccb": ["CCB notice from CRA", "children's birth certificates", "bank statement showing deposits"],
    "contract": ["current contract with end date", "T4s or T1/T2125 for two years of contract history"],
}
VARIABLE = {"overtime", "bonus", "commission"}
TYPES = {"salary", "hourly", "self_employed", "pension", "cpp", "oas", "child_support", "spousal_support", "ccb",
         "contract", *VARIABLE}
NONTAXABLE = {"child_support", "ccb"}


def two_year(history: list[float], min_years: int) -> tuple[float, str, list[str]]:
    """Two-year average, or the most recent year when it is lower (declining trend)."""
    flags = []
    hist = [float(x) for x in history]
    if len(hist) < min_years:
        return 0.0, f"not used: {len(hist)} year(s) of history, {min_years} required", \
            [f"less than {min_years} years of history"]
    if len(hist) == 1:
        return max(0.0, hist[0]), "most recent year (one year required by policy)", flags
    prior, latest = hist[-2], hist[-1]
    avg = (prior + latest) / 2
    if latest < prior:
        drop = (prior - latest) / prior * 100 if prior > 0 else 0.0
        flags.append(f"declining: {latest:,.0f} vs {prior:,.0f} ({drop:.1f}% lower); qualified on the lower year")
        return max(0.0, latest), "most recent year (declining trend, lower than the 2-year average)", flags
    return max(0.0, avg), f"2-year average of {prior:,.0f} and {latest:,.0f}", flags


def _self_employed(src: dict, pol: dict) -> tuple[float, str, list[str]]:
    years = src.get("years") or []
    if not years:
        raise ValueError("self_employed needs years: [{net_income, cca, business_use_of_home, other_add_backs}]")
    method = src.get("income_method", "add_backs")
    if method == "add_backs":
        adj = [float(y["net_income"]) + float(y.get("cca", 0)) + float(y.get("business_use_of_home", 0))
               + float(y.get("other_add_backs", 0)) for y in years]
        amount, how, flags = two_year(adj, pol["variable_min_years"])
        how = f"T2125/line 15000 net income plus CCA, business-use-of-home and other add-backs; {how}"
    elif method == "gross_up":
        g = float(src.get("gross_up_pct", P.VERIFIED["self_employed_gross_up_pct"]["value"]))
        base, how, flags = two_year([float(y["net_income"]) for y in years], pol["variable_min_years"])
        amount = base * (1 + g / 100)
        how = f"line 15000 net income grossed up {g:g}%; {how}"
        if g > P.VERIFIED["self_employed_gross_up_pct"]["value"]:
            flags.append(f"gross-up {g:g}% exceeds CMHC's 15%: lender-specific (Alt-A / BFS stated income)")
    else:
        raise ValueError("income_method must be 'add_backs' or 'gross_up'")
    months = src.get("months_in_business")
    if months is not None and months < P.VERIFIED["self_employed_months_recommended"]["value"]:
        flags.append(f"{months} months in business: under the 24 months CMHC recommends; "
                     "needs same-industry experience or an Alt-A/BFS lender")
    return amount, how, flags


def qualify_source(src: dict, pol: dict | None = None) -> dict:
    """Qualifying annual income for one source: ``{type, label, qualifying_annual, method, documents, flags}``."""
    pol = pol or P.policy()
    kind = src.get("type")
    if kind not in TYPES:
        raise ValueError(f"unknown income type {kind!r}; one of {sorted(TYPES)}")
    amt = float(src.get("annual_amount", 0) or 0)
    flags: list[str] = []
    docs_key = kind
    if kind == "salary":
        amount, how = amt, "base salary"
    elif kind == "hourly":
        rate, hours = float(src["hourly_rate"]), float(src.get("guaranteed_hours_per_week", 0))
        if hours <= 0:
            raise ValueError("hourly income needs guaranteed_hours_per_week; non-guaranteed hours use 'overtime'")
        amount, how = rate * hours * 52, f"{rate:g}/h x {hours:g} guaranteed h/week x 52"
    elif kind in VARIABLE or kind == "contract":
        hist = src.get("history") or ([amt] if amt else [])
        amount, how, flags = two_year(hist, pol["variable_min_years"])
        docs_key = "contract" if kind == "contract" else "variable"
    elif kind == "self_employed":
        amount, how, flags = _self_employed(src, pol)
    elif kind == "pension":
        amount, how = amt, "pension as paid"
    elif kind in ("cpp", "oas"):
        amount, how, docs_key = amt, f"{kind.upper()} benefit as paid", "government"
    elif kind in ("child_support", "spousal_support"):
        docs_key = "support"
        if pol["support_requires_order"] and not src.get("court_order"):
            amount, how = 0.0, "not used: no court order or separation agreement"
            flags.append("support without a court order or separation agreement is not counted by this lender")
        else:
            amount, how = amt, "support per court order / separation agreement"
    else:  # ccb
        if pol["include_ccb"]:
            amount, how = amt, "Canada Child Benefit as paid"
        else:
            amount, how = 0.0, "not used: lender excludes Canada Child Benefit"
    if kind in ("child_support", "spousal_support", "ccb") and amount > 0:
        left = src.get("years_remaining")
        if left is not None and left < pol["continuity_years"]:
            amount, how = 0.0, f"not used: only {left:g} year(s) remaining"
            flags.append(f"income ends within {pol['continuity_years']} years")
    if amount > 0 and (kind in NONTAXABLE or src.get("nontaxable")) and pol["nontaxable_gross_up_pct"]:
        amount *= 1 + pol["nontaxable_gross_up_pct"] / 100
        how += f", non-taxable grossed up {pol['nontaxable_gross_up_pct']:g}%"
    if src.get("probation"):
        flags.append("on probation: many lenders decline until it ends unless the borrower stays in the same industry")
    if kind == "contract" and src.get("months_remaining") is not None and src["months_remaining"] < 6:
        flags.append(f"contract ends in {src['months_remaining']} months: lender will want renewal evidence")
    return {"type": kind, "label": src.get("label") or kind.replace("_", " "), "qualifying_annual": round(amount, 2),
            "method": how, "documents": DOCS[docs_key], "flags": flags}


POLICY_KEYS = ("variable_min_years", "support_requires_order", "include_ccb", "continuity_years",
               "nontaxable_gross_up_pct")


def qualifying_income(sources: list[dict], policy: dict | None = None) -> dict:
    """Qualifying income across all sources, with the method and support for each."""
    if not sources:
        raise ValueError("at least one income source is required")
    pol = P.policy(policy)
    rows = [qualify_source(s, pol) for s in sources]
    total = round(sum(r["qualifying_annual"] for r in rows), 2)
    stated = sum(float(s.get("annual_amount", 0) or 0) for s in sources)
    return {"engine": "income.sources.qualifying_income", "method": "lender treatment per source (see each source)",
            "total_qualifying_annual": total,
            "total_qualifying_monthly": round(total / 12, 2), "sources": rows,
            "flags": [f"{r['label']}: {f}" for r in rows for f in r["flags"]],
            "excluded_or_reduced": [r["label"] for r, s in zip(rows, sources)
                                    if s.get("annual_amount") and r["qualifying_annual"] < float(s["annual_amount"])],
            "stated_annual_amounts": round(stated, 2),
            "assumptions": P.assumptions(pol, POLICY_KEYS),
            "source": P.sources("self_employed_gross_up_pct", "self_employed_months_recommended")}
