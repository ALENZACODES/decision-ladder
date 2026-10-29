"""Train the LightGBM valuation model on every municipal record that has an assessed value (data/parcels.parquet).

Target: log(assessed value). Writes models/avm.txt and models/avm_meta.json with holdout accuracy by city and by class.
"""
import json, pathlib
import sys
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from server.fsa_values import index_at

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = ROOT / "models"; MOD.mkdir(exist_ok=True)

FEATS = ["lat", "lon", "lot_sf", "living_sf", "year", "rooms", "storeys", "garage", "is_unit", "cls", "city", "hood"]
CATS = ["cls", "city", "hood"]


CITY_REGION = {"Calgary": "CGY", "Edmonton": "EDM", "Strathcona County": "EDM", "Winnipeg": "PRA", "Vancouver": "VAN",
               "Langley Township": "VAN", "Victoria": "BCO"}


def region_of(city, lat, lon):
    if city in CITY_REGION:
        return CITY_REGION[city]
    if str(city).startswith("QC-"):
        return "MTL" if (45.35 <= (lat or 0) <= 45.75 and -74.15 <= (lon or 0) <= -73.3) else "QCO"
    return None


def to_today(df):
    """Factor that moves each assessment from its valuation date to Sep 2026 with the regional index."""
    regs = [region_of(c, a, b) for c, a, b in zip(df["city"], df["lat"], df["lon"])]
    cache = {}
    out = []
    for r, d in zip(regs, df["value_date"].astype(str)):
        if r is None or len(d) < 7:
            out.append(np.nan); continue
        k = (r, d[:7])
        if k not in cache:
            cache[k] = index_at(r, 2026, 8) / index_at(r, int(d[:4]), int(d[5:7]) - 1)
        out.append(cache[k])
    return np.array(out)


def prep(df):
    df = df.copy()
    df["is_unit"] = (df["unit"].fillna("") != "").astype(float)
    df["hood"] = df["city"].astype(str) + ":" + df["hood"].fillna("NA").astype(str)
    return df


if __name__ == "__main__":
    p = pd.read_parquet(ROOT / "data" / "parcels.parquet")
    p = p[p.value.notna() & (p.cls != "other") & (p.value_date.astype(str) >= "2022")]
    p = p.assign(adj=to_today(p)); p = p[p.adj.notna()]
    p["value"] = p["value"] * p["adj"]            # train on Sep-2026 dollars
    df = prep(p)
    print("rows", len(df), df.city.value_counts().to_dict())
    for c in CATS:
        df[c] = df[c].astype(str).astype("category")
    rng = np.random.default_rng(42); test = rng.random(len(df)) < 0.12
    X, y = df[FEATS], np.log(df["value"])
    params = dict(objective="regression_l1", learning_rate=0.06, num_leaves=511, min_data_in_leaf=25, max_cat_to_onehot=8,
                  feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1, cat_smooth=15, cat_l2=5, verbose=-1)
    dtr = lgb.Dataset(X[~test], y[~test], categorical_feature=CATS)
    dte = lgb.Dataset(X[test], y[test], reference=dtr)
    m = lgb.train(params, dtr, 3000, valid_sets=[dte], callbacks=[lgb.early_stopping(150), lgb.log_evaluation(500)])
    pred = np.exp(m.predict(X[test], num_iteration=m.best_iteration))
    err = np.abs(pred / df["value"][test].values - 1)
    t = df[test]
    by = lambda col: {str(k): round(float(np.median(err[(t[col] == k).values])), 4) for k in t[col].unique() if (t[col] == k).sum() > 200}
    meta = {"rows": int(len(df)), "test_rows": int(test.sum()), "median_abs_pct_err": float(np.median(err)),
            "within_5pct": float((err < .05).mean()), "within_10pct": float((err < .10).mean()),
            "by_city": by("city"), "by_class": by("cls"),
            "feats": FEATS, "cats": {c: list(df[c].cat.categories) for c in CATS}, "best_iteration": m.best_iteration}
    m.save_model(str(MOD / "avm.txt"), num_iteration=m.best_iteration)
    (MOD / "avm_meta.json").write_text(json.dumps(meta))
    print({k: v for k, v in meta.items() if k not in ("cats", "feats")})
