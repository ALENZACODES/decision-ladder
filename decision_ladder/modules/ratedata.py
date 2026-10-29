"""The author's Bank of Canada rate notebooks and his Quiet Charges, Shoebox and pitch-deck projects as OS modules.

* Three Kaggle notebooks (policy rate vs 5-year bond vs mortgage rates; real interest rates; the 2020-2021
  renewal wave) plus his Kaggle Bank of Canada dataset notebooks. Their committed data files feed one tool,
  ``rate_spreads``, which reads the CSVs as committed (no network, no re-fitting).
* Quiet Charges (recurring charges in a bank statement) and Shoebox (bank transactions to CRA Form T2125 lines)
  run their own JavaScript through ``bridge.mjs``.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..agent.tools import Tool, _obj
from .jsapps import _tool
from .registry import MODULES_DIR, AppModule, add_module, add_tool

PR = MODULES_DIR / "canada-policy-rate-bond-yield-mortgage-rate" / "data"
RI = MODULES_DIR / "canada-real-interest-rates-cpi-vs-policy-rate" / "data"
NOW = MODULES_DIR / "kaggle-boc-notebooks" / "data" / "canada-mortgage-rate-nowcast-output" / "nowcast_latest.csv"

S = {"type": "string"}
N = {"type": "number"}

MODS = [
    AppModule(key="canada-policy-rate-bond-yield-mortgage-rate", name="Who Sets Canada's 5 Year Mortgage Rate?",
              stages=["market"], kind="data", entry="README.md",
              description="Kaggle notebook: Bank of Canada policy rate vs 5-year GoC bond yield vs posted and actual (effective) "
                          "5-year mortgage rates, with the committed Bank of Canada data.",
              directory="canada-policy-rate-bond-yield-mortgage-rate",
              repo="ALENZACODES/canada-policy-rate-bond-yield-mortgage-rate"),
    AppModule(key="canada-real-interest-rates-cpi-vs-policy-rate", name="Real Interest Rates in Canada Since 2009",
              stages=["market"], kind="data", entry="README.md",
              description="Kaggle notebook: real policy rate and real 5-year bond yield using CPI and core inflation (trim, median).",
              directory="canada-real-interest-rates-cpi-vs-policy-rate",
              repo="ALENZACODES/canada-real-interest-rates-cpi-vs-policy-rate"),
    AppModule(key="canada-renewal-shock-2020-2021-five-year-fixed", name="Canada's Renewal Wave: 2020 and 2021 Fixed Rates",
              stages=["market", "servicing"], kind="data", entry="README.md",
              description="Kaggle notebook: payment shock at renewal for every 2020 and 2021 five-year fixed cohort, from Bank of "
                          "Canada effective lending rates.",
              directory="canada-renewal-shock-2020-2021-five-year-fixed",
              repo="ALENZACODES/canada-renewal-shock-2020-2021-five-year-fixed"),
    AppModule(key="kaggle-boc-notebooks", name="Bank of Canada Kaggle dataset notebooks",
              stages=["market"], kind="data", entry="LICENSE",
              description="Two of the author's Kaggle notebooks with their data: the daily Bank of Canada policy rate explorer and "
                          "the Canada Mortgage Rate Nowcaster output explorer (ridge and gradient-boosting nowcasts).",
              directory="kaggle-boc-notebooks", repo="ALENZACODES/kaggle-datasets-notebooks",
              notes="Only the two Bank of Canada notebooks are vendored; the repo's two non-mortgage notebooks are left out."),
    AppModule(key="quiet-charges", name="Quiet Charges", stages=["documents", "underwriting"], web_root="",
              description="Finds recurring charges in a bank statement CSV (weekly to annual), flags price increases and stale "
                          "subscriptions, and totals the monthly cost. In the OS: recurring obligations a lender reading 90 days "
                          "of statements will see.",
              directory="quiet-charges", repo="ALENZACODES/quiet-charges", live_url="https://alenzacodes.github.io/quiet-charges/"),
    AppModule(key="shoebox", name="Shoebox", stages=["documents", "underwriting"],
              description="Sorts bank transactions into CRA Form T2125 expense lines in the browser with an open-weight embedding "
                          "model (MiniLM). In the OS: a first look at a self-employed borrower's business expenses.",
              directory="shoebox", repo="ALENZACODES/shoebox", live_url="https://alenzacodes.github.io/shoebox/"),
    AppModule(key="renewal-check-pitch", name="RenewalCheck pitch deck", stages=["lead", "servicing"],
              description="Ten-slide pitch for RenewalCheck, a free Canadian mortgage renewal checker; every figure links to a "
                          "Bank of Canada or CMHC source.",
              directory="renewal-check-pitch", repo="ALENZACODES/renewal-check-pitch",
              live_url="https://alenzacodes.github.io/renewal-check-pitch/"),
]
for _m in MODS:
    add_module(_m)


def _read(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _last(rows: list[dict], col: str, upto: str | None = None) -> tuple[str, float] | None:
    for r in reversed(rows):
        if upto and r["date"] > upto:
            continue
        v = (r.get(col) or "").strip()
        if v:
            return r["date"], float(v)
    return None


def _yoy(rows: list[dict], col: str, upto: str | None) -> tuple[str, float] | None:
    idx = {r["date"]: r for r in rows if (r.get(col) or "").strip()}
    last = _last(rows, col, upto)
    if not last:
        return None
    d, v = last
    prev = idx.get(f"{int(d[:4]) - 1}{d[4:]}")
    return (d, round((v / float(prev[col]) - 1) * 100, 2)) if prev else None


def rate_spreads(a: dict) -> dict:
    """Latest (or as-of) rate stack from the committed Bank of Canada files in the author's notebooks."""
    upto = a.get("as_of") or None
    try:
        daily, posted, eff, cpi = (_read(PR / "daily_policy_bond.csv"), _read(PR / "weekly_posted_5yr.csv"),
                                   _read(PR / "monthly_effective_5yr_uninsured.csv"), _read(RI / "monthly_cpi.csv"))
    except OSError as e:
        return {"error": f"rate data missing: {e}"}
    pol, bond = _last(daily, "V39079", upto), _last(daily, "BD.CDN.5YR.DQ.YLD", upto)
    post, ef = _last(posted, "V80691335", upto), _last(eff, "V122667786", upto)
    infl = _yoy(cpi, "V41690973", upto)
    trim, med = _last(cpi, "CPI_TRIM", upto), _last(cpi, "CPI_MEDIAN", upto)
    out: dict = {"as_of": upto or "latest in files",
                 "policy_rate": pol and {"date": pol[0], "pct": pol[1]},
                 "goc_5yr_yield": bond and {"date": bond[0], "pct": bond[1]},
                 "posted_5yr_fixed": post and {"date": post[0], "pct": post[1]},
                 "effective_5yr_uninsured": ef and {"date": ef[0], "pct": ef[1]},
                 "cpi_yoy": infl and {"date": infl[0], "pct": infl[1]},
                 "cpi_trim": trim and {"date": trim[0], "pct": trim[1]},
                 "cpi_median": med and {"date": med[0], "pct": med[1]}}
    sp = {}
    if ef and bond:
        sp["effective_minus_goc5_pts"] = round(ef[1] - bond[1], 2)
    if post and ef:
        sp["posted_minus_effective_pts"] = round(post[1] - ef[1], 2)
    if pol and infl:
        sp["real_policy_rate_pts"] = round(pol[1] - infl[1], 2)
    if bond and infl:
        sp["real_goc5_pts"] = round(bond[1] - infl[1], 2)
    out["spreads"] = sp
    if NOW.exists() and not upto:
        out["nowcast_5yr_effective"] = [{k: r[k] for k in ("month", "horizon", "last_published", "nowcast_rate")}
                                        for r in _read(NOW)]
    out["note"] = ("Values are the committed Bank of Canada series in the author's notebooks (dates shown per series); "
                   "the posted rate is the big-six posted 5-year, not an offer. Nowcast is the author's model output, not a forecast "
                   "from the Bank.")
    out["source"] = {"module": "canada-policy-rate-bond-yield-mortgage-rate + canada-real-interest-rates-cpi-vs-policy-rate"
                               " + kaggle-boc-notebooks", "series": ["V39079", "BD.CDN.5YR.DQ.YLD", "V80691335", "V122667786",
                                                                     "V41690973", "CPI_TRIM", "CPI_MEDIAN"]}
    out["engine"] = "Bank of Canada rate notebooks (committed data)"
    return out


add_tool(Tool("rate_spreads",
              "Rate stack from the Bank of Canada data in the author's notebooks: policy rate, 5-year GoC yield, posted 5-year "
              "fixed, effective 5-year uninsured (what borrowers actually got), CPI y/y and core trim/median, with spreads "
              "(effective minus bond, posted minus effective, real policy rate, real 5-year yield) and the author's mortgage-rate "
              "nowcast. as_of=YYYY-MM-DD for a past date.",
              _obj({"as_of": S}, []), rate_spreads, "market"), "canada-policy-rate-bond-yield-mortgage-rate")

for _t, _key in [
    (_tool("recurring_charges_scan",
           "Quiet Charges: find recurring charges in a bank statement CSV (Date, Description, Amount; negatives are spending). "
           "Returns active recurring count, monthly and annual total, price increases, and each recurring item with cadence and "
           "confidence. Omit csv to run the app's fictional sample. Use for obligations a lender will see on 90 days of statements.",
           {"csv": S, "today": {"type": "string", "description": "YYYY-MM-DD used to decide which charges are still active"}},
           [], "quiet-charges", "scan", "underwriting"), "quiet-charges"),
    (_tool("self_employed_expense_lines",
           "Shoebox: sort a bank statement CSV into CRA Form T2125 expense lines (keyword baseline server-side), with money in, "
           "claimable totals (meals at 50%), and lines that need a business-use percentage (pct: {line_id: percent}). Omit csv for "
           "the app's fictional sample. A first look at a self-employed borrower's expenses, not a tax return.",
           {"csv": S, "pct": {"type": "object", "additionalProperties": N}}, [], "shoebox", "lines", "underwriting"), "shoebox"),
]:
    add_tool(_t, _key)
