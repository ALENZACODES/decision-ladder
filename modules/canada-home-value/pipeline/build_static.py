"""Pre-compute real-data files for the no-server (static) version of the estimator.

Outputs to static/data/:
  munis.json            every municipality (CSD) in Canada -> province, region, postal areas, address count
  fsa.json              every postal area -> census median today + record-based medians by property type (Sep-2026 $)
  streets/<FSA>.json    per postal area: street -> [median today $, records, most common type, median sq ft, median year]
  accuracy.json         holdout check of the street / postal-area estimate against real assessments
"""
import json, pathlib, sqlite3, sys
from collections import defaultdict
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key, split_nar_civic, street_core          # noqa: E402
from train_model import to_today                                  # noqa: E402
from server.fsa_values import load as load_fsa, region as fsa_region  # noqa: E402

OUT = ROOT / "static" / "data"; (OUT / "streets").mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(ROOT / "data" / "addresses.db")

# 1. Municipalities and postal areas from the National Address Register
print("municipalities…")
mun = defaultdict(lambda: {"n": 0, "fsa": defaultdict(int)})
for csd, prov, postal, n in db.execute("SELECT csd, prov, substr(replace(postal,' ',''),1,3), count(*) FROM addr GROUP BY 1,2,3"):
    if not csd or not prov:
        continue
    m = mun[(csd, prov)]; m["n"] += n
    if postal and len(postal) == 3:
        m["fsa"][postal] += n
munis = []
for (csd, prov), m in mun.items():
    fsas = sorted(m["fsa"], key=lambda f: -m["fsa"][f])
    reg = fsa_region(fsas[0]) if fsas else None
    munis.append({"name": csd, "prov": prov, "reg": reg, "n": m["n"], "fsa": fsas})
munis.sort(key=lambda x: (x["prov"], -x["n"]))
(OUT / "munis.json").write_text(json.dumps(munis, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(munis), "municipalities")

# 2. Postal code for each property record via its address key (unit first, then building)
print("postal codes for records…")
p = pd.read_parquet(ROOT / "data" / "parcels.parquet")
p = p[p.value.notna() & (p.value_date.astype(str) >= "2022") & (p.cls != "other")].copy()
p["adj"] = to_today(p); p = p[p.adj.notna()]; p["today"] = p.value * p.adj
post = {}
for prov in sorted(p.prov.unique()):
    for civic, street, pc in db.execute("SELECT civic, street, replace(postal,' ','') FROM addr WHERE prov=?", (prov,)):
        if not pc:
            continue
        u, c = split_nar_civic(civic)
        post.setdefault((prov, key(u, c, street)), pc)
        post.setdefault((prov, "|" + key("", c, street).split("|", 1)[1]), pc)
p["postal"] = [post.get((pr, k)) or post.get((pr, "|" + k.split("|", 1)[1])) for pr, k in zip(p.prov, p.key)]
p = p[p.postal.notna()]
p["fsa"] = p.postal.str[:3]
p["street"] = p.key.str.split("|").str[2] + "|" + p.key.str.split("|").str[3]
print(len(p), "records with postal code")
p.drop(columns=[c for c in ("geometry",) if c in p]).to_parquet(ROOT / "data" / "parcels_postal.parquet")

TYPE = {"house": "detached", "semi": "semi", "duplex": "duplex", "multiplex": "multiplex", "town": "town",
        "condotown": "condotown", "condo": "condo", "mobile": "mobile"}
p["t"] = p.cls.map(TYPE)

# 3. Holdout accuracy of exactly what the page does: same-type street median (>=2 records), else postal-area median,
#    scaled by (home sq ft / typical sq ft) ** 0.5 when both are known
SIZE_EXP = 0.5
rng = np.random.default_rng(7); test = rng.random(len(p)) < 0.1
tr, te = p[~test], p[test]
g = tr.groupby(["fsa", "street", "t"]).agg(v=("today", "median"), n=("today", "size"), sf=("living_sf", "median"))
f = tr.groupby(["fsa", "t"]).agg(v_f=("today", "median"), sf_f=("living_sf", "median"))
te = te.join(g, on=["fsa", "street", "t"]).join(f, on=["fsa", "t"])
use_s = (te.n >= 2).values
base = np.where(use_s, te.v, te.v_f); bsf = np.where(use_s, te.sf, te.sf_f)
ratio = np.where(np.isfinite(te.living_sf) & np.isfinite(bsf) & (bsf > 0), np.clip(te.living_sf / bsf, .4, 3) ** SIZE_EXP, 1)
err = np.abs(base * ratio / te.today - 1); ok = np.isfinite(err)
te, err, use_s = te[ok], err[ok], use_s[ok]
acc = {"test_records": int(len(te)), "median_abs_pct_err": round(float(np.median(err)), 4),
       "within_10pct": round(float((err < .1).mean()), 3), "within_20pct": round(float((err < .2).mean()), 3),
       "by_level": {"street": round(float(np.median(err[use_s])), 4), "postal": round(float(np.median(err[~use_s])), 4)},
       "by_type": {t: round(float(np.median(err[(te.t == t).values])), 4) for t in te.t.dropna().unique()},
       "size_exponent": SIZE_EXP}
(OUT / "accuracy.json").write_text(json.dumps(acc))
print("accuracy", acc)

# 4. Postal-area file: census + record medians by type
census = load_fsa()
fsa_out = {}
g = p.groupby(["fsa", "t"]).agg(v=("today", "median"), n=("today", "size"), sf=("living_sf", "median"), yr=("year", "median"))
for f, c in census.items():
    fsa_out[f] = {"r": c["region"], "c": c["median_today"], "c21": c["median_2021"], "x": c["factor"], "t": {}}
for (f, t), row in g.iterrows():
    if row.n < 5:
        continue
    d = fsa_out.setdefault(f, {"r": fsa_region(f), "c": None, "c21": None, "x": None, "t": {}})
    d["t"][t] = [int(round(row.v, -3)), int(row.n), None if pd.isna(row.sf) else int(row.sf), None if pd.isna(row.yr) else int(row.yr)]
(OUT / "fsa.json").write_text(json.dumps(fsa_out, separators=(",", ":")), encoding="utf-8")
print(len(fsa_out), "postal areas;", sum(1 for v in fsa_out.values() if v["t"]), "with record medians")

# 5. Street files per postal area: street -> {type: [median today $, records, median sq ft, median year]}
sg = p.groupby(["fsa", "street", "t"]).agg(v=("today", "median"), n=("today", "size"), sf=("living_sf", "median"), yr=("year", "median"))
p["civn"] = pd.to_numeric(p.key.str.split("|").str[1].str.extract(r"^(\d+)")[0], errors="coerce")
rng_ = p.groupby(["fsa", "street"]).civn.agg(["min", "max"])
files = 0
for fsa_code, grp in sg.groupby(level=0):
    d = {}
    for (_, s_, t), row in grp.iterrows():
        if row.n < 2:
            continue
        d.setdefault(s_, {})[t] = [int(round(row.v, -3)), int(row.n), None if pd.isna(row.sf) else int(row.sf), None if pd.isna(row.yr) else int(row.yr)]
    for s_ in d:
        lo, hi = rng_.loc[(fsa_code, s_)] if (fsa_code, s_) in rng_.index else (np.nan, np.nan)
        if pd.notna(lo):
            d[s_]["_r"] = [int(lo), int(hi)]
    if d:
        (OUT / "streets" / f"{fsa_code}.json").write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8"); files += 1
        fsa_out.setdefault(fsa_code, {"r": fsa_region(fsa_code), "c": None, "c21": None, "x": None, "t": {}})["s"] = 1
(OUT / "fsa.json").write_text(json.dumps(fsa_out, separators=(",", ":")), encoding="utf-8")
print(files, "street files")

# 6. Bundle street files by first postal-code letter for publishing
bundles = {}
for f in sorted((OUT / "streets").iterdir()):
    bundles.setdefault(f.name[0], {})[f.name[:3]] = json.loads(f.read_text(encoding="utf-8"))
for k, v in bundles.items():
    (OUT / f"streets_{k}.json").write_text(json.dumps(v, separators=(",", ":")), encoding="utf-8")
print(len(bundles), "street bundles")
