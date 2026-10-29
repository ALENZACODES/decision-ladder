"""Neighbourhood-block (dissemination area) values for the no-server page, checked against real assessments.

value(block, type) = Census 2021 block median × regional index to Sep 2026 × local type ratio (CHSP, by municipality)
                      × calibration (records where they exist; published MLS HPI benchmarks otherwise)
Outputs:
  static/data/da_<PR>.json   per province code: DAUID -> [today all-types $, municipality key]
  static/data/csd_types.json municipality -> type ratios
  static/data/da_accuracy.json  holdout check where assessment records exist
"""
import json, pathlib, sqlite3, sys
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key, split_nar_civic        # noqa: E402
from calibrate import PUBLISHED                 # noqa: E402

OUT = ROOT / "static" / "data"
db = sqlite3.connect(ROOT / "data" / "addresses.db")
da = pd.read_parquet(ROOT / "data" / "da_values.parquet").dropna(subset=["today"]).set_index("da")
types = json.loads((ROOT / "data" / "csd_types.json").read_text())

# municipality of each block (most addresses), as "PROV|NAME"
csd = pd.read_sql("SELECT da, prov, upper(csd) csd, count(*) n FROM addr WHERE da IS NOT NULL GROUP BY 1,2,3", db)
csd = csd.sort_values("n").groupby("da").tail(1).set_index("da")
da["mkey"] = (csd.prov + "|" + csd.csd).reindex(da.index)
da["n"] = csd.n.reindex(da.index)
CLS_T = {"house": "detached", "semi": "semi", "town": "town", "condotown": "town", "condo": "condo",
         "duplex": "multiplex", "multiplex": "multiplex", "mobile": "mobile"}


def ratio(mkey, t):
    r = types.get(mkey or "", {})
    return r.get(t) or {"detached": 1.15, "semi": .92, "town": .8, "condo": .65, "multiplex": 1.4, "mobile": .4}.get(t, 1.0)


# 1. Check against real assessments (Québec, Alberta, Winnipeg, BC cities): block of each record via its address
p = pd.read_parquet(ROOT / "data" / "parcels_postal.parquet") if (ROOT / "data" / "parcels_postal.parquet").exists() else None
acc = {}
calib_region = {}
if p is not None:
    look = {}
    for prov in sorted(p.prov.unique()):
        for civic, street, d in db.execute("SELECT civic, street, da FROM addr WHERE prov=? AND da IS NOT NULL", (prov,)):
            u, c = split_nar_civic(civic)
            look.setdefault((prov, key(u, c, street)), d)
            look.setdefault((prov, "|" + key("", c, street).split("|", 1)[1]), d)
    p["da"] = [look.get((pr, k)) or look.get((pr, "|" + k.split("|", 1)[1])) for pr, k in zip(p.prov, p.key)]
    p = p[p.da.isin(da.index) & p.cls.isin(CLS_T)]
    p["t"] = p.cls.map(CLS_T)
    p["pred"] = [da.at[d, "today"] * ratio(da.at[d, "mkey"], t) for d, t in zip(p.da, p.t)]
    p["reg"] = da.reg.reindex(p.da).values
    raw_err = (p.pred / p.today - 1).abs()
    # calibration per region from half the records, tested on the other half
    rng = np.random.default_rng(3); fit = rng.random(len(p)) < .5
    # learn corrections only where that region really has local records (min 2,000), and keep them sensible
    REC_REG = {"CGY", "EDM", "ABO", "PRA", "VAN", "BCO", "MTL", "QCO"}
    g = (p[fit].today / p[fit].pred).groupby(p[fit].reg)
    calib_region = {r: float(min(1.6, max(0.6, v))) for r, v in g.median().items() if r in REC_REG and g.size()[r] >= 2000}
    adj = p.pred * p.reg.map(calib_region).fillna(1)
    err = (adj / p.today - 1).abs()[~fit]
    acc = {"records": int((~fit).sum()), "median_abs_pct_err_raw": round(float(raw_err.median()), 4),
           "median_abs_pct_err": round(float(err.median()), 4), "within_10pct": round(float((err < .1).mean()), 3),
           "within_20pct": round(float((err < .2).mean()), 3),
           "by_region": {r: round(float(err[(p.reg == r)[~fit].values].median()), 4) for r in p.reg[~fit].dropna().unique()},
           "by_type": {t: round(float(err[(p.t == t)[~fit].values].median()), 4) for t in p.t.unique()},
           "calibration": {k: round(v, 3) for k, v in calib_region.items()}}
    print("accuracy", acc)

# 2. Calibrate regions without records (Ontario etc.) to published Sep 2026 MLS HPI composites, per municipality
calib_muni = {}
for name, pub in PUBLISHED.items():
    for prov in ("ON", "AB", "BC"):
        rows = da[da.mkey == f"{prov}|{name.upper()}"]
        if len(rows) > 20:
            w = rows.n.fillna(1)
            calib_muni[f"{prov}|{name.upper()}"] = min(1.6, max(0.6, pub / float(np.average(rows.today, weights=w))))
on_reg = {}
for k, v in calib_muni.items():
    if k.startswith("ON|"):
        r = da[da.mkey == k].reg.mode()
        if len(r):
            on_reg.setdefault(r.iat[0], []).append(v)
for r, vs in on_reg.items():
    calib_region.setdefault(r, float(min(1.6, max(0.6, np.median(vs)))))
print("municipal calibration", {k: round(v, 3) for k, v in calib_muni.items()})
print("region calibration", {k: round(v, 3) for k, v in calib_region.items()})


def final(d):
    m = calib_muni.get(da.at[d, "mkey"]) if da.at[d, "mkey"] in calib_muni and da.at[d, "reg"] not in (acc.get("calibration") or {}) else None
    return da.at[d, "today"] * (m or calib_region.get(da.at[d, "reg"], 1.0))


da["final"] = [final(d) for d in da.index]
for pr, g in da.groupby(da.index.str[:2]):
    (OUT / f"da_{pr}.json").write_text(json.dumps({d: [int(round(v, -3)), mk] for d, v, mk in zip(g.index, g.final, g.mkey.fillna(""))},
                                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(OUT / "csd_types.json").write_text(json.dumps(types, separators=(",", ":")), encoding="utf-8")
(OUT / "da_accuracy.json").write_text(json.dumps(acc))
print("wrote", len(da), "blocks")
