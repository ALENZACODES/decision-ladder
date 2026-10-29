"""Neighbourhood profile for every Census block (2021 Census, StatCan SDMX, free).

static/data/prof_<PR>.json  DAUID -> [pop21, growth%, median age, median household income, owner%, single-detached%,
                                      apartment 5+ storeys%, built<=1960%, built 2016-21%, owner monthly cost, renter monthly cost,
                                      bachelor+%, unemployment%, transit commute%, low income%]
static/data/prof_ca.json    national medians of each field, for "higher than X% of neighbourhoods" comparisons
"""
import io, json, pathlib, time
import numpy as np, pandas as pd, requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "da"; OUT = ROOT / "static" / "data"
CODES = [1, 2, 3, 40, 41, 42, 47, 56, 229, 331, 1400, 1401, 1426, 1427, 1434, 1472, 1480, 1998, 2008, 2230, 2603, 2607]
URL = "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data/STC_CP,DF_DA/A5..1.{c}.1"


def fetch():
    f = RAW / "da_profile.parquet"
    if f.exists():
        return pd.read_parquet(f)
    parts = []
    for i in range(0, len(CODES), 4):
        grp = "+".join(str(c) for c in CODES[i:i + 4])
        for a in range(5):
            try:
                r = requests.get(URL.format(c=grp), headers={"Accept": "application/vnd.sdmx.data+csv", "User-Agent": "Mozilla/5.0"}, timeout=900)
                r.raise_for_status(); break
            except Exception as e:
                print("retry", e); time.sleep(10 * (a + 1))
        d = pd.read_csv(io.BytesIO(r.content), usecols=["ALT_GEO_CODE", "CHARACTERISTIC", "OBS_VALUE"], dtype={"ALT_GEO_CODE": str})
        parts.append(d); print("codes", grp, len(d), flush=True)
    d = pd.concat(parts)
    d.to_parquet(f)
    return d


if __name__ == "__main__":
    d = fetch()
    w = d.pivot_table(index="ALT_GEO_CODE", columns="CHARACTERISTIC", values="OBS_VALUE", aggfunc="first")
    g = lambda c: pd.to_numeric(w.get(c), errors="coerce")
    pct = lambda a, b: (g(a) / g(b) * 100).where(g(b) > 0)
    prof = pd.DataFrame({
        "pop": g(1), "growth": pd.Series(np.where(np.asarray(g(2)) >= 50, (np.asarray(g(1)) / np.asarray(g(2)) - 1) * 100, np.nan), index=w.index).round(1), "age": g(40), "inc": g(229), "own": pct(1401, 1400), "sfd": pct(42, 41), "apt": pct(47, 41),
        "old": pct(1427, 1426), "new": pct(1434, 1426), "ocost": g(1472), "rcost": g(1480), "bach": pct(2008, 1998),
        "unemp": g(2230), "transit": pct(2607, 2603), "lowinc": g(331)})
    cols = list(prof.columns)
    med = {c: (None if np.isnan(m := float(np.nanmedian(prof[c]))) else m) for c in cols}
    # percentile rank of each block vs all of Canada, 0-100, so the page can say "higher than 78% of neighbourhoods"
    rank = prof.rank(pct=True) * 100
    # national percentiles (every 5%) so the page can rank a block without storing ranks per block
    pcts = {c: [None if np.isnan(x) else round(float(x), 1) for x in np.nanpercentile(prof[c], list(range(0, 101, 5)))] if prof[c].notna().any() else None for c in cols}
    (OUT / "prof_ca.json").write_text(json.dumps({"fields": cols, "median": med, "pct": pcts}))
    n = 0
    for pr, grp in prof.groupby(prof.index.str[:2]):
        out = {}
        for da, row in grp.iterrows():
            vals = [None if pd.isna(v) else (round(v, 1) if abs(v) < 1000 else int(round(v))) for v in row.values]
            out[da] = vals
        (OUT / f"prof_{pr}.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8"); n += len(out)
    print(n, "blocks profiled;", round(sum(f.stat().st_size for f in OUT.glob("prof_*.json")) / 1e6, 1), "MB; medians", {k: (round(v) if v is not None else None) for k, v in med.items()})
