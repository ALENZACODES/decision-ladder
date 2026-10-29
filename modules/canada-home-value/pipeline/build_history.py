"""Per-address assessment history for the no-server page.

Inputs: data/raw/hist_*.parquet (fetch_history.py) plus the current roll from data/raw (2026).
Output: static/data/history/<first 2 postal chars>.json  {FSA: {"UNIT|CIVIC|CORE|DIR": "2014:450 2015:462 ... 2026:520"}}
        values in thousands of dollars, roll years. static/data/history/index.json lists available prefixes.
"""
import json, pathlib, re, sqlite3, sys
from collections import defaultdict
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key3, split_nar_civic        # noqa: E402

RAW = ROOT / "data" / "raw"; OUT = ROOT / "static" / "data" / "history"; OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.json"):
    f.unlink()
num = lambda s: pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "", regex=False), errors="coerce")
hist = defaultdict(dict)        # (prov, key) -> {year: value}


def add(prov, keys, years, values):
    for k, y, v in zip(keys, years, values):
        if k and pd.notna(v) and 20_000 <= v <= 30_000_000:
            hist[(prov, k)][int(y)] = int(round(v / 1000))


def cal_keys(addr):
    p = addr.fillna("").str.extract(r"^(?:(?P<u>\w+)\s+(?=\d+\w?\s))?(?P<c>\d+\w?)\s+(?P<s>.+)$")
    return [key3(u, c, s) for u, c, s in zip(p.u.fillna(""), p.c.fillna(""), p.s.fillna(""))]


if (RAW / "hist_calgary.parquet").exists():
    h = pd.read_parquet(RAW / "hist_calgary.parquet"); add("AB", cal_keys(h.address), h.roll_year, num(h.assessed_value))
cur = pd.read_parquet(RAW / "calgary.parquet"); add("AB", cal_keys(cur.address), [2026] * len(cur), num(cur.assessed_value))

e_now = pd.read_parquet(RAW / "edmonton.parquet")
suite = e_now["suite"].fillna("").astype(str).str.strip() if "suite" in e_now else pd.Series("", index=e_now.index)
acct_key = {a: key3(s, h, st) for a, s, h, st in zip(e_now.account_number, suite, e_now.house_number.fillna(""), e_now.street_name.fillna(""))}
add("AB", list(acct_key.values()), [2026] * len(acct_key), num(e_now.assessed_value))
if (RAW / "hist_edmonton.parquet").exists():
    h = pd.read_parquet(RAW / "hist_edmonton.parquet")
    ks = [acct_key.get(a) or key3("", hn, st) for a, hn, st in zip(h.account_number, h.house_number.fillna(""), h.street_name.fillna(""))]
    add("AB", ks, h.assessment_year, num(h.assessed_value))


def van_add(d, year_col):
    strata = d.legal_type.eq("STRATA")
    ks = [key3(u if s else "", c, st) for u, c, st, s in zip(d.from_civic_number.fillna(""), d.to_civic_number.fillna(""), d.street_name.fillna(""), strata)]
    add("BC", ks, d[year_col], num(d.current_land_value).fillna(0) + num(d.current_improvement_value).fillna(0))


v = pd.read_parquet(RAW / "vancouver.parquet"); v["y"] = 2026; van_add(v, "y")
if (RAW / "hist_vancouver.parquet").exists():
    h = pd.read_parquet(RAW / "hist_vancouver.parquet"); van_add(h, "year")


def lang_add(d, years):
    strata = d.Legal_Type.eq("STRATA")
    ks = [key3(str(u) if s and u not in ("None", "nan") else "", str(h).split(".")[0], st) for u, h, st, s in zip(d.Unit.fillna(""), d.House.fillna(""), d.Street.fillna(""), strata)]
    add("BC", ks, years, num(d.Residential_Buildings).fillna(0) + num(d.Residential_Land).fillna(0))


l = pd.read_parquet(RAW / "langley_twp.parquet"); lang_add(l, [2026] * len(l))
if (RAW / "hist_langley.parquet").exists():
    h = pd.read_parquet(RAW / "hist_langley.parquet")
    if {"Residential_Buildings", "Residential_Land"} <= set(h.columns):
        lang_add(h, h.year)


def vic_add(d, years):
    strata = d.LEGAL_TYPE.eq("STRATA")
    ks = [key3(str(u) if s and u not in ("None", "nan") else "", str(h).split(".")[0], st) for u, h, st, s in zip(d.UNIT.fillna(""), d.HOUSE.fillna(""), d.STREET.fillna(""), strata)]
    add("BC", ks, years, num(d.impr_gross).fillna(0) + num(d.land_gross).fillna(0))


vi = pd.read_parquet(RAW / "victoria.parquet"); vic_add(vi, [2026] * len(vi))
if (RAW / "hist_victoria.parquet").exists():
    vic_add(pd.read_parquet(RAW / "hist_victoria.parquet"), [2024] * len(pd.read_parquet(RAW / "hist_victoria.parquet")))

hist = {k: v for k, v in hist.items() if len(v) >= 2}          # history needs at least two years
print(len(hist), "addresses with history")
db = sqlite3.connect(ROOT / "data" / "addresses.db")
post = {}
for prov in ("AB", "BC"):
    for civic, street, pc in db.execute("SELECT civic, street, replace(postal,' ','') FROM addr WHERE prov=?", (prov,)):
        if pc:
            u, c = split_nar_civic(civic)
            post.setdefault((prov, key3(u, c, street)), pc[:3])
out = defaultdict(lambda: defaultdict(dict)); hit = 0
for (prov, k), yv in hist.items():
    f = post.get((prov, k))
    if f:
        out[f[:2]][f][k] = " ".join(f"{y}:{yv[y]}" for y in sorted(yv)); hit += 1
for pre, d in out.items():
    (OUT / f"{pre}.json").write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
(OUT / "index.json").write_text(json.dumps(sorted(out)))
print(hit, "matched;", len(out), "files;", round(sum(p.stat().st_size for p in OUT.glob("*.json")) / 1e6, 1), "MB;",
      "largest", round(max(p.stat().st_size for p in OUT.glob("*.json")) / 1e6, 1), "MB")
