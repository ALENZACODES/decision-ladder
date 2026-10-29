"""Head-to-head on real assessments: Census block value vs Census postal-area value (the only options in Ontario)."""
import json, pathlib, sqlite3, sys
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key, split_nar_civic
from server.fsa_values import load as load_fsa

db = sqlite3.connect(ROOT / "data" / "addresses.db")
da = {k: v for f in (ROOT / "static" / "data").glob("da_[0-9]*.json") for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
types = json.loads((ROOT / "data" / "csd_types.json").read_text())
fsa = load_fsa()
p = pd.read_parquet(ROOT / "data" / "parcels_postal.parquet").sample(400_000, random_state=1)
look = {}
for prov in sorted(p.prov.unique()):
    for civic, street, d in db.execute("SELECT civic, street, da FROM addr WHERE prov=?", (prov,)):
        u, c = split_nar_civic(civic); look.setdefault((prov, key(u, c, street)), d); look.setdefault((prov, "|" + key("", c, street).split("|", 1)[1]), d)
p["da"] = [look.get((pr, k)) or look.get((pr, "|" + k.split("|", 1)[1])) for pr, k in zip(p.prov, p.key)]
CLS = {"house": "detached", "semi": "semi", "town": "town", "condotown": "town", "condo": "condo", "duplex": "multiplex", "multiplex": "multiplex", "mobile": "mobile"}
DEF = {"detached": 1.15, "semi": .92, "town": .8, "condo": .65, "multiplex": 1.4, "mobile": .4}
p = p[p.cls.isin(CLS) & p.da.isin(da.keys()) & p.postal.str[:3].isin(fsa.keys())]
p["t"] = p.cls.map(CLS)
r = [(types.get(da[d][1], {}).get(t) or DEF[t]) for d, t in zip(p.da, p.t)]
blk = np.array([da[d][0] for d in p.da]) * r
fs = np.array([fsa[f[:3]]["median_today"] for f in p.postal]) * r
for name, pred in (("block", blk), ("postal area", fs), ("blend 70/30", .7 * blk + .3 * fs), ("geometric", np.sqrt(blk * fs))):
    e = np.abs(pred / p.today.values - 1)
    print(f"{name:12s} median err {np.median(e):.3f}  within10 {np.mean(e<.1):.3f}  within20 {np.mean(e<.2):.3f}")

# add the owner's floor area (records that have it), relative to the typical size for that type
typ = p.groupby("t").living_sf.median()
geo = np.sqrt(blk * fs)
has = p.living_sf.notna().values
for a in (0, .3, .45, .6):
    adj = np.where(has, np.clip(p.living_sf.values / p.t.map(typ).values, .4, 3) ** a, 1)
    e = np.abs(geo * adj / p.today.values - 1)[has]
    print(f"size exponent {a}: median err {np.median(e):.3f} within10 {np.mean(e<.1):.3f} within20 {np.mean(e<.2):.3f} (n={has.sum()})")
print("typical sq ft by type", typ.round(-1).to_dict())

# record the method the page uses for homes without records: sqrt(block x postal area) x local type ratio x size^0.4
adj = np.where(has, np.clip(p.living_sf.values / p.t.map(typ).values, .4, 3) ** .4, 1)
e_all = np.abs(geo / p.today.values - 1); e_sz = np.abs(geo * adj / p.today.values - 1)[has]
out = json.loads((ROOT / "static" / "data" / "da_accuracy.json").read_text() or "{}")
out.update({"method": "sqrt(block x postal area) x local type ratio x (sq ft / typical)^0.4",
            "median_abs_pct_err": round(float(np.median(e_all)), 4), "with_size_median_abs_pct_err": round(float(np.median(e_sz)), 4),
            "with_size_within_10pct": round(float(np.mean(e_sz < .1)), 3), "with_size_within_20pct": round(float(np.mean(e_sz < .2)), 3),
            "tested_on": int(len(p))})
(ROOT / "static" / "data" / "da_accuracy.json").write_text(json.dumps(out))
print("saved", {k: out[k] for k in ("median_abs_pct_err", "with_size_median_abs_pct_err")})
