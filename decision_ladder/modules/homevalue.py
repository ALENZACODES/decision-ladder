"""House prices and home value: Benchmark Home Value, Canada Home Value and the Canada Housing Affordability
Index, wired into the Mortgage OS.

Single source of truth: the regional price index, city benchmarks and type multipliers are read at import
time straight out of ``modules/benchmark-home-value/index.html`` (the JS literals ``ANCH``, ``TYPE``, ``M``,
``REGION_NAME``, ``G_PRE``) and the series builder (``interp`` / ``seasonal`` / ``sanitize``) is a line-by-line
port of the same file. Postal-area values come from the app's own ``data/fsa.json``; accuracy from its
``data/backtest.json`` / ``data/accuracy.json``; the AVM test figures from canada-home-value's
``models/avm_meta.json``; affordability from the notebook's ``data/*.csv`` snapshot (Bank of Canada Valet).

What is local vs remote (module notes, also shown in the OS):
* benchmark-home-value: everything except ``data/addr/`` (146 MB address-autocomplete packs) and
  ``data/detail/`` (90 MB per-parcel assessment history) is vendored (about 22 MB). The app already
  degrades without them (its loaders ``.catch`` to empty): search falls back to street, postal-area and
  municipality level. Full address search and per-home assessment history live on the public site
  https://alenzacodes.github.io/benchmark-home-value/.
* canada-home-value: the FastAPI server needs pandas, numpy, lightgbm, a SQLite address index and the
  LightGBM model file ``models/avm.txt``; none of the data or the model file is in the repository, so the
  AVM is NOT callable here and no AVM tool is registered. Its published test results (avm_meta.json) are.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
import unicodedata
from functools import lru_cache

from ..agent.tools import I, N, S, Tool, _obj
from .registry import MODULES_DIR, AppModule, add_module, add_tool

BHV = MODULES_DIR / "benchmark-home-value"
CHV = MODULES_DIR / "canada-home-value"
AFF = MODULES_DIR / "canada-housing-affordability-index-1980-2026"
LIVE_SITE = "https://alenzacodes.github.io/benchmark-home-value/"
TYPES = ("detached", "semi", "town", "condo")


# ------------------------------------------------------------------ reading the JS literals
def _js_literal(src: str, name: str) -> str:
    """Return the text of ``const NAME=<{...} or [...]>`` with balanced brackets."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*([\[{])", src)
    if not m:
        raise ValueError(f"{name} not found in index.html")
    open_ch = m.group(1)
    close_ch = "}" if open_ch == "{" else "]"
    i, depth, in_str = m.start(1), 0, None
    while i < len(src):
        c = src[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return src[m.start(1):i + 1]
        i += 1
    raise ValueError(f"unbalanced literal for {name}")


def _to_json(js: str):
    js = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', js)  # quote bare keys
    js = re.sub(r"(\d)\.(?=[,\]}])", r"\1", js)
    js = re.sub(r"([:\[,]\s*)\.(\d)", r"\g<1>0.\2", js)                      # .06 -> 0.06
    return json.loads(js)


@lru_cache(maxsize=1)
def page() -> dict:
    """Constants from modules/benchmark-home-value/index.html."""
    src = (BHV / "index.html").read_text(encoding="utf-8")
    anch = _to_json(_js_literal(src, "ANCH"))
    typ = _to_json(_js_literal(src, "TYPE"))
    names = _to_json(_js_literal(src, "REGION_NAME"))
    gpre = _to_json(_js_literal(src, "G_PRE"))
    rows = _to_json(_js_literal(src, "M"))
    cities = [{"name": n, "prov": p, "reg": r, "bench": float(b), "fsa": f.split()} for n, p, r, b, f in rows
              if f != "" or n != "Welland Canal Region"]   # same filter as the page
    sqft = _to_json(_js_literal(src, "SQFT"))
    return {"ANCH": anch, "TYPE": typ, "REGION_NAME": names, "G_PRE": gpre, "M": cities, "SQFT": sqft}


# ------------------------------------------------------------------ the page's series builder (ported)
START = (2016, 0)
END = (2026, 8)   # new Date(2026,8,1) = Sep 2026
N_MONTHS = (END[0] - START[0]) * 12 + END[1] + 1


def mi(y: int, m: int) -> int:
    """index.html ``mi``: months since Jan 2016 (m is 0-based)."""
    return (y - 2016) * 12 + m


def _interp(anchors: list) -> list[float]:
    out = [math.nan] * N_MONTHS
    for (ay, am, av), (by, bm, bv) in zip(anchors, anchors[1:]):
        i0, i1 = mi(ay, am), mi(by, bm)
        for i in range(i0, min(i1, N_MONTHS - 1) + 1):
            t = (i - i0) / (i1 - i0)
            s = (1 - math.cos(math.pi * t)) / 2
            out[i] = av + (bv - av) * s
    return out


def _seasonal(arr: list[float]) -> list[float]:
    # JS: v*(1+0.012*sin((month-1)/12*2*pi)), month = MONTHS[i].getMonth() (0-based)
    return [v * (1 + 0.012 * math.sin(((i % 12) - 1) / 12 * 2 * math.pi)) for i, v in enumerate(arr)]


def _sanitize(arr: list[float], lo: float, hi: float) -> list[float]:
    a = list(arr)
    last = -1
    for i in range(len(a)):
        if not math.isfinite(a[i]):
            continue
        if a[i] < lo or a[i] > hi:
            a[i] = min(hi, max(lo, a[i]))
        if last >= 0 and i - last > 1:
            for j in range(last + 1, i):
                a[j] = a[last] + (a[i] - a[last]) * (j - last) / (i - last)
        elif last < 0 and i > 0:
            for j in range(i):
                a[j] = a[i]
        last = i
    if last < 0:
        return [lo] * len(a)
    for j in range(last + 1, len(a)):
        a[j] = a[last]
    return a


@lru_cache(maxsize=None)
def index_series(reg: str) -> tuple[float, ...]:
    anch = page()["ANCH"]
    if reg not in anch:
        reg = "GTA"   # IDXA falls back to GTA
    return tuple(_sanitize(_seasonal(_interp(anch[reg])), 20, 500))


def idx_at(reg: str, prov: str, y: int, m0: int) -> float:
    """index.html ``idxAtPage``: index level at (year, 0-based month), extended before 2016 at G_PRE."""
    idx = index_series(reg)
    i = mi(y, m0)
    g = page()["G_PRE"].get(prov, 0.035)
    return idx[min(i, len(idx) - 1)] if i >= 0 else idx[0] / (1 + g) ** (-i / 12)


def series_for(city: dict, typ: str) -> list[float]:
    """index.html ``seriesFor``: monthly $ series for a city and type (composite if typ is None)."""
    idx = index_series(city["reg"])
    now = idx[-1]
    mult = 1.0 if typ in (None, "composite") else page()["TYPE"][city["reg"]][typ]
    return _sanitize([round(city["bench"] * mult * v / now / 1000) * 1000 for v in idx], 20000, 20000000)


def month_label(i: int) -> str:
    y, m = divmod(i, 12)
    return f"{2016 + y}-{m + 1:02d}"


# ------------------------------------------------------------------ data files
@lru_cache(maxsize=1)
def fsa_table() -> dict:
    return json.loads((BHV / "data" / "fsa.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def data_updated() -> dict:
    p = BHV / "data" / "updated.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _plain(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()


def find_city(place: str) -> dict | None:
    q = _plain(place)
    cities = page()["M"]
    for c in cities:
        if _plain(c["name"]) == q:
            return c
    fsa = re.sub(r"\s", "", place or "").upper()[:3]
    if re.fullmatch(r"[A-Z]\d[A-Z]", fsa):
        for c in cities:
            if fsa in c["fsa"]:
                return c
    for c in cities:
        if q and q in _plain(c["name"]):
            return c
    return None


def _source(extra: str = "") -> dict:
    u = data_updated()
    return {"module": "benchmark-home-value", "file": "modules/benchmark-home-value/index.html" + extra,
            "prices_as_of": u.get("prices", "Sep 2026"), "data_checked": u.get("date"),
            "method": "regional price index (Jan 2016 = 100, shaped on public CREA/board HPI history) x city benchmark",
            "disclaimer": "Indicative only. Not an appraisal."}


# ------------------------------------------------------------------ tools
def t_benchmark_price(a: dict) -> dict:
    c = find_city(a["place"])
    if c is None:
        raise ValueError(f"no benchmark city matches {a['place']!r}; try a city name or a 3-character postal prefix")
    typ = (a.get("property_type") or "composite").lower()
    if typ not in TYPES + ("composite",):
        raise ValueError(f"property_type must be one of {('composite',) + TYPES}")
    s = series_for(c, typ)
    now, yr, five = s[-1], s[-13], s[-61]
    out = {"city": c["name"], "province": c["prov"], "region": c["reg"],
           "region_name": page()["REGION_NAME"][c["reg"]], "property_type": typ, "as_of": month_label(N_MONTHS - 1),
           "benchmark_price": now, "price_12m_ago": yr, "yoy_change_pct": round((now / yr - 1) * 100, 2),
           "price_5y_ago": five, "change_5y_pct": round((now / five - 1) * 100, 2),
           "peak_price": max(s), "peak_month": month_label(s.index(max(s))),
           "typical_size_sqft": page()["SQFT"].get(typ), "source": _source(" (M, TYPE, ANCH)")}
    if typ == "composite":
        out["by_type"] = {t: series_for(c, t)[-1] for t in TYPES}
    return out


def t_postal_value(a: dict) -> dict:
    fsa = re.sub(r"\s", "", a["fsa"]).upper()[:3]
    f = fsa_table().get(fsa)
    if not f:
        raise ValueError(f"postal area {fsa} is not in the Benchmark Home Value data")
    by_type = {t: {"typical_value": v[0], "assessment_records": v[1], "typical_sqft": v[2], "typical_year_built": v[3]}
               for t, v in (f.get("t") or {}).items()}
    out = {"fsa": fsa, "region": f["r"], "region_name": page()["REGION_NAME"].get(f["r"]),
           "census_2021_median_value": f.get("c21"), "regional_index_factor_since_2021": f.get("x"),
           "estimated_value_today": f.get("c"), "by_type_from_assessments": by_type,
           "street_level_data_available": bool(f.get("s")),
           "source": {**_source("; data/fsa.json"),
                      "method": "2021 Census median dwelling value moved to today with the regional price index; "
                                "type medians from municipal assessment records where published"}}
    want = (a.get("property_type") or "").lower()
    if want and want in by_type:
        out["typical_value_for_type"] = by_type[want]["typical_value"]
    return out


def t_index_purchase(a: dict) -> dict:
    """Port of index.html ``calcPaid``: value today = price x (index now / index when bought)."""
    c = find_city(a["place"])
    if c is None:
        raise ValueError(f"no benchmark city matches {a['place']!r}")
    price, y, mo = float(a["purchase_price"]), int(a["purchase_year"]), int(a["purchase_month"])
    if price <= 0 or not 1 <= mo <= 12 or y < 1990 or mi(y, mo - 1) > N_MONTHS - 1:
        raise ValueError("purchase_price must be positive, month 1-12, date between 1990-01 and 2026-09")
    idx = index_series(c["reg"])
    now, then = idx[-1], idx_at(c["reg"], c["prov"], y, mo - 1)
    val = price * now / then
    yrs = max(1 / 12, (N_MONTHS - 1 - mi(y, mo - 1)) / 12)
    out = {"city": c["name"], "region_name": page()["REGION_NAME"][c["reg"]], "purchase_price": price,
           "purchased": f"{y}-{mo:02d}", "value_today": round(val, 2), "value_today_rounded": round(val / 5000) * 5000,
           "change": round(val - price, 2), "change_pct": round((val / price - 1) * 100, 2),
           "per_year_pct": round(((val / price) ** (1 / yrs) - 1) * 100, 2),
           "index_then": round(then, 3), "index_now": round(now, 3), "as_of": month_label(N_MONTHS - 1),
           "pre_2016_extension": mi(y, mo - 1) < 0,
           "source": {**_source(" (calcPaid, idxAtPage)"),
                      "method": "repeat-sale indexing, the FHFA calculator method; before 2016 extended at "
                                f"{page()['G_PRE'].get(c['prov'], 0.035) * 100:.1f}%/yr"}}
    reno = float(a.get("renovation_spend") or 0)
    if reno:
        # index.html repeat-sale block: renovation value 0.6 x spend, depreciated 3%/yr over half the holding period
        out["renovation_value_added"] = round(reno * 0.6 * 0.97 ** (yrs / 2), 2)
        out["value_today_with_renovations"] = round(val + out["renovation_value_added"], 2)
    return out


@lru_cache(maxsize=1)
def afford_rows() -> tuple[list[dict], list[tuple[str, float]]]:
    q = []
    with open(AFF / "data" / "quarterly_afford_nhpi.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["INDINF_AFFORD_Q"]:
                q.append({"date": r["date"], "afford": float(r["INDINF_AFFORD_Q"]),
                          "nhpi_yoy": float(r["INDINF_NHPI_Q"]) if r["INDINF_NHPI_Q"] else None})
    with open(AFF / "data" / "weekly_posted_5yr.csv", encoding="utf-8") as f:
        w = [(r["date"], float(r["V80691335"])) for r in csv.DictReader(f) if r["V80691335"]]
    return q, w


def _quarter(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    return f"{y} Q{(m - 1) // 3 + 1}"


def _qrate(qdate: str, weekly: list[tuple[str, float]]) -> float | None:
    y, m = int(qdate[:4]), int(qdate[5:7])
    end_m = m + 3
    end = f"{y + (end_m - 1) // 12}-{(end_m - 1) % 12 + 1:02d}-01"
    v = [r for d, r in weekly if qdate <= d < end]
    return round(sum(v) / len(v), 2) if v else None


def _pick_quarter(q: list[dict], when: str | None) -> dict:
    if not when:
        return q[-1]
    m = re.fullmatch(r"\s*(\d{4})\s*[- ]?\s*Q([1-4])\s*", when, re.I)
    if m:
        d = f"{m.group(1)}-{(int(m.group(2)) - 1) * 3 + 1:02d}-01"
    else:
        d = when.strip()[:10]
    cands = [r for r in q if r["date"] <= d]
    if not cands:
        raise ValueError(f"no affordability data on or before {when}")
    return cands[-1]


def t_affordability(a: dict) -> dict:
    q, w = afford_rows()
    row = _pick_quarter(q, a.get("quarter"))
    vals = [r["afford"] for r in q]
    hi = max(q, key=lambda r: r["afford"])
    lo = min(q, key=lambda r: r["afford"])
    more_affordable = sum(1 for v in vals if v < row["afford"]) / len(vals)
    return {"quarter": _quarter(row["date"]), "affordability_index_pct": round(row["afford"] * 100, 1),
            "meaning": "share of average disposable income needed to carry an average priced home",
            "long_run_average_pct": round(statistics.fmean(vals) * 100, 1),
            "share_of_quarters_more_affordable_pct": round(more_affordable * 100, 1),
            "posted_5y_rate_avg_that_quarter": _qrate(row["date"], w), "nhpi_yoy_pct": row["nhpi_yoy"],
            "all_time_high": {"quarter": _quarter(hi["date"]), "pct": round(hi["afford"] * 100, 1),
                              "posted_5y_rate": _qrate(hi["date"], w)},
            "all_time_low": {"quarter": _quarter(lo["date"]), "pct": round(lo["afford"] * 100, 1)},
            "series_range": [_quarter(q[0]["date"]), _quarter(q[-1]["date"])],
            "source": {"module": "canada-housing-affordability-index-1980-2026",
                       "file": "modules/canada-housing-affordability-index-1980-2026/data/quarterly_afford_nhpi.csv",
                       "series": "Bank of Canada Valet INDINF_AFFORD_Q, INDINF_NHPI_Q (StatCan 18-10-0205-01), V80691335",
                       "snapshot": "notebook run of 2026-10-18"}}


def _corr(x: list[float], y: list[float]) -> float:
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def t_affordability_vs_rates(a: dict) -> dict:
    """How the affordability index moves with the posted 5-year rate (the notebook's finding 3)."""
    q, w = afford_rows()
    pts = [(r["afford"] * 100, _qrate(r["date"], w)) for r in q]
    pts = [(af, rt) for af, rt in pts if rt is not None]
    lv_corr = _corr([p[0] for p in pts], [p[1] for p in pts])
    d_af = [pts[i][0] - pts[i - 4][0] for i in range(4, len(pts))]
    d_rt = [pts[i][1] - pts[i - 4][1] for i in range(4, len(pts))]
    c = _corr(d_rt, d_af)
    mx, my = statistics.fmean(d_rt), statistics.fmean(d_af)
    slope = sum((x - mx) * (y - my) for x, y in zip(d_rt, d_af)) / sum((x - mx) ** 2 for x in d_rt)
    out = {"yearly_change_correlation": round(c, 2), "index_points_per_1pt_rate_move": round(slope, 2),
           "level_correlation": round(lv_corr, 2), "quarters": len(pts),
           "source": {"module": "canada-housing-affordability-index-1980-2026",
                      "method": "4-quarter changes of the index vs the quarterly average posted 5-year rate (V80691335)"}}
    if a.get("rate_change_pts") is not None:
        out["implied_index_change_pts"] = round(slope * float(a["rate_change_pts"]), 2)
    return out


def t_accuracy(a: dict) -> dict:
    bt = json.loads((BHV / "data" / "backtest.json").read_text(encoding="utf-8"))
    acc = json.loads((BHV / "data" / "accuracy.json").read_text(encoding="utf-8"))
    groups = {g: {k: v.get("mdape") for k, v in d["methods"].items()} for g, d in bt["groups"].items()}
    avm = json.loads((CHV / "models" / "avm_meta.json").read_text(encoding="utf-8"))
    city = a.get("city")
    out = {"benchmark_home_value": {"backtest_generated": bt.get("generated"), "tested_homes": bt.get("tested_homes"),
                                    "median_abs_pct_error_by_group_and_method": groups,
                                    "street_model_test": {k: acc[k] for k in ("test_records", "median_abs_pct_err", "within_10pct", "within_20pct")}},
           "canada_home_value_avm": {"model": "LightGBM on open municipal assessment rolls", "train_rows": avm["rows"],
                                     "test_rows": avm["test_rows"], "median_abs_pct_err": round(avm["median_abs_pct_err"], 4),
                                     "within_10pct": round(avm["within_10pct"], 4), "by_class": avm["by_class"],
                                     "callable_here": False,
                                     "why_not_callable": "models/avm.txt and the parcel database are not in the repository"},
           "source": {"files": ["modules/benchmark-home-value/data/backtest.json", "modules/benchmark-home-value/data/accuracy.json",
                                "modules/canada-home-value/models/avm_meta.json"]}}
    if city:
        out["canada_home_value_avm"]["city_median_abs_pct_err"] = avm["by_city"].get(city)
    return out


# ------------------------------------------------------------------ registration
NOTES_BHV = ("Vendored with about 22 MB of its data. Not vendored: data/addr (146 MB address autocomplete) and "
             "data/detail (90 MB per-parcel assessment history); the app falls back to street, postal-area and "
             f"municipality level without them. Full address search: {LIVE_SITE}")

add_module(AppModule(
    key="benchmark-home-value", name="Benchmark Home Value", stages=["property", "prequal"], kind="static",
    description="Free home value estimator for every Canadian address: regional price index, city and postal-area "
                "benchmarks, assessment-based street values, rents, forecasts, backtest of 974,500 homes.",
    directory="benchmark-home-value", entry="index.html", repo="ALENZACODES/benchmark-home-value",
    live_url=LIVE_SITE, notes=NOTES_BHV))
add_module(AppModule(
    key="canada-home-value", name="Canada Home Value", stages=["property"], kind="static",
    description="Home value estimator with an AI (LightGBM) valuation model for Calgary and Edmonton parcels and an "
                "area benchmark everywhere else. Embedded here: the self-contained estimator page.",
    directory="canada-home-value", entry="home-value-estimator.html", repo="ALENZACODES/canada-home-value",
    notes="The FastAPI server (server/app.py) needs pandas, lightgbm, the address SQLite index and models/avm.txt, "
          "none of which are in the repo, so the OS embeds the standalone estimator page and exposes the AVM's "
          "published test results (models/avm_meta.json), not live AVM predictions."))
add_module(AppModule(
    key="canada-housing-affordability-index-1980-2026", name="Canada Housing Affordability Index 1980-2026",
    stages=["market", "prequal"], kind="data",
    description="45 years of the Bank of Canada housing affordability index with posted 5-year rates and the New "
                "Housing Price Index (Kaggle notebook + data snapshot).",
    directory="canada-housing-affordability-index-1980-2026", entry="README.md",
    repo="ALENZACODES/canada-housing-affordability-index-1980-2026",
    live_url="https://www.kaggle.com/code/johnnykhan1/canada-housing-affordability-index-1980-to-2026"))

_P = {"place": {"type": "string", "description": "city name (e.g. Oakville) or 3-character postal prefix (e.g. L6J)"},
      "property_type": {"type": "string", "enum": ["composite", "detached", "semi", "town", "condo"]}}

for _tool, _mod in (
    (Tool("benchmark_home_price",
          "Benchmark home price for a Canadian city or postal prefix (composite or by type) with 12-month and 5-year "
          "change and peak, from Benchmark Home Value's regional index. Indicative, not an appraisal.",
          _obj(_P, ["place"]), t_benchmark_price, "property"), "benchmark-home-value"),
    (Tool("postal_area_home_value",
          "Typical home value in a postal area (FSA, e.g. M5V): 2021 Census median moved to today, plus medians by "
          "property type from municipal assessment records where available.",
          _obj({"fsa": S, "property_type": S}, ["fsa"]), t_postal_value, "property"), "benchmark-home-value"),
    (Tool("index_purchase_to_today",
          "Value today of a home bought at a known price and month, moved through the regional price index "
          "(repeat-sale / FHFA method), with optional renovation spend.",
          _obj({"purchase_price": N, "purchase_year": I, "purchase_month": I, "place": S, "renovation_spend": N},
               ["purchase_price", "purchase_year", "purchase_month", "place"]), t_index_purchase, "property"),
     "benchmark-home-value"),
    (Tool("housing_affordability_index",
          "Bank of Canada housing affordability index (share of disposable income to carry an average home) for a "
          "quarter (e.g. '2023 Q3', default latest), vs its 1980-2026 history, with that quarter's posted 5-year rate.",
          _obj({"quarter": S}), t_affordability, "market"), "canada-housing-affordability-index-1980-2026"),
    (Tool("affordability_rate_sensitivity",
          "How much the affordability index moves per 1-point change in the posted 5-year rate (1980-2026), "
          "optionally applied to a rate change you give.",
          _obj({"rate_change_pts": N}), t_affordability_vs_rates, "market"), "canada-housing-affordability-index-1980-2026"),
    (Tool("valuation_accuracy",
          "Published accuracy of the home value models: Benchmark Home Value backtest by city and method, and the "
          "Canada Home Value LightGBM AVM test (optionally for one city).",
          _obj({"city": S}), t_accuracy, "property"), "canada-home-value"),
):
    add_tool(_tool, _mod)

__all__ = ["page", "index_series", "series_for", "find_city", "t_benchmark_price", "t_postal_value",
           "t_index_purchase", "t_affordability", "t_affordability_vs_rates", "t_accuracy"]
