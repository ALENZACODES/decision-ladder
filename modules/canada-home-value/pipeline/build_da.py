"""Assign every address to its 2021 Census dissemination area (neighbourhood block, ~400-700 homes) and
store block-level home values.

  data/raw/da/da_bounds.json   block polygons from StatCan's boundary map service (WGS84, generalised)
  data/raw/da/da_value.csv     2021 Census median dwelling value per block (SDMX DF_DA, characteristic 1474)
  data/addresses.db            gains column `da` on table addr
  data/da_values.parquet       da -> median 2021, region, today's value (regional index + calibration)
"""
import json, pathlib, sqlite3, sys, time
import numpy as np, pandas as pd, requests
import shapely
from shapely.geometry import shape

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server.fsa_values import index_at, region as fsa_region, CALIB   # noqa: E402

RAW = ROOT / "data" / "raw" / "da"
LAYER = "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/12/query"


def fetch_missing(feats):
    """Fetch blocks that are not in the cached file yet, by province code, in small pages."""
    have = {f["da"] for f in feats}
    v = pd.read_csv(RAW / "da_value.csv", dtype={"ALT_GEO_CODE": str})
    need = sorted(set(v.ALT_GEO_CODE) - have)
    for i in range(0, len(need), 200):
        ids = need[i:i + 200]
        p = {"where": "DAUID IN (" + ",".join(f"'{d}'" for d in ids) + ")", "outFields": "DAUID", "outSR": "4326",
             "f": "geojson", "returnGeometry": "true", "maxAllowableOffset": "0.0005"}
        for a in range(5):
            try:
                d = requests.post(LAYER, data=p, timeout=300, headers={"User-Agent": "Mozilla/5.0"}).json(); break
            except Exception as e:
                print("retry", e); time.sleep(5 * (a + 1))
        else:
            continue
        feats += [{"da": x["properties"]["DAUID"], "g": x["geometry"]} for x in d.get("features", []) if x.get("geometry")]
        print("filled", i + len(ids), "of", len(need), flush=True)
    uniq = {f["da"]: f for f in feats}
    return list(uniq.values())


def fetch_bounds():
    out = RAW / "da_bounds.json"
    if out.exists():
        feats = fetch_missing(json.loads(out.read_text()))
        out.write_text(json.dumps(feats))
        return feats
    feats, off = [], 0
    while True:
        p = {"where": "1=1", "outFields": "DAUID", "outSR": "4326", "f": "geojson", "returnGeometry": "true",
             "maxAllowableOffset": "0.0002", "resultOffset": off, "resultRecordCount": 4000, "orderByFields": "DAUID"}
        for a in range(5):
            try:
                d = requests.get(LAYER, params=p, timeout=300, headers={"User-Agent": "Mozilla/5.0"}).json(); break
            except Exception as e:
                print("retry", e); time.sleep(5 * (a + 1))
        f = d.get("features", [])
        feats += [{"da": x["properties"]["DAUID"], "g": x["geometry"]} for x in f if x.get("geometry")]
        off += len(f); print("blocks", off, flush=True)
        if len(f) < 4000:
            break
    out.write_text(json.dumps(feats))
    return feats


def assign(feats, provs=None):
    geoms = [shape(f["g"]) for f in feats]; ids = np.array([f["da"] for f in feats])
    tree = shapely.STRtree(geoms)
    db = sqlite3.connect(ROOT / "data" / "addresses.db")
    cols = [r[1] for r in db.execute("PRAGMA table_info(addr)")]
    if "da" not in cols:
        db.execute("ALTER TABLE addr ADD COLUMN da TEXT")
    n = db.execute("SELECT max(id) FROM addr").fetchone()[0]; step = 500_000; done = 0
    for lo in range(0, n + 1, step):
        q = "SELECT id, lon, lat FROM addr WHERE id BETWEEN ? AND ?" + (f" AND prov IN ({','.join('?'*len(provs))})" if provs else "")
        rows = db.execute(q, [lo, lo + step - 1] + list(provs or [])).fetchall()
        if not rows:
            continue
        a = np.array(rows); pts = shapely.points(a[:, 1], a[:, 2])
        pi, gi = tree.query(pts, predicate="within")
        da = np.full(len(rows), None, dtype=object); da[pi] = ids[gi]
        miss = np.where(da == None)[0]                                      # noqa: E711  edge points: nearest block
        if len(miss):
            ni, dist = tree.query_nearest(pts[miss], return_distance=True, all_matches=False)
            near = dist < 0.01                                           # ~1 km; farther means no block known here
            da[miss[ni[0][near]]] = ids[ni[1][near]]
        db.executemany("UPDATE addr SET da=? WHERE id=?", list(zip(da.tolist(), a[:, 0].astype(int).tolist())))
        db.commit(); done += len(rows); print("assigned", done, flush=True)
    db.execute("CREATE INDEX IF NOT EXISTS addr_da ON addr(da)"); db.commit()


def values():
    v = pd.read_csv(RAW / "da_value.csv", dtype={"ALT_GEO_CODE": str})
    v = v[pd.to_numeric(v.OBS_VALUE, errors="coerce").notna()]
    db = sqlite3.connect(ROOT / "data" / "addresses.db")
    fsa = pd.read_sql("SELECT da, substr(replace(postal,' ',''),1,3) fsa, count(*) n FROM addr WHERE da IS NOT NULL GROUP BY 1,2", db)
    fsa = fsa.sort_values("n").groupby("da").tail(1).set_index("da").fsa           # main postal area of each block
    out = pd.DataFrame({"da": v.ALT_GEO_CODE, "m21": v.OBS_VALUE.astype(float),
                        "lo21": pd.to_numeric(v.CI_LOW, errors="coerce"), "hi21": pd.to_numeric(v.CI_HIGH, errors="coerce")})
    out["fsa"] = out.da.map(fsa)
    out["reg"] = [fsa_region(f) if isinstance(f, str) and len(f) == 3 else None for f in out.fsa]
    # blocks with no postal code (mostly the North and rural areas): use the province's default region
    PR_REG = {"10": "ATL", "11": "ATL", "12": "ATL", "13": "ATL", "24": "QCO", "35": "EON", "46": "PRA", "47": "PRA",
              "48": "ABO", "59": "BCO", "60": "TER", "61": "TER", "62": "TER"}
    out["reg"] = [r if isinstance(r, str) else PR_REG.get(d[:2]) for r, d in zip(out.reg, out.da)]
    cache = {}
    def fac(r):
        if r not in cache:
            cache[r] = index_at(r, 2026, 8) / index_at(r, 2021, 4) * CALIB.get(r, 1.0)
        return cache[r]
    out["today"] = [m * fac(r) if isinstance(r, str) else np.nan for m, r in zip(out.m21, out.reg)]
    out.to_parquet(ROOT / "data" / "da_values.parquet")
    print("blocks with values", len(out), "with region", int(out.reg.notna().sum()))


if __name__ == "__main__":
    feats = fetch_bounds(); print(len(feats), "block polygons")
    if "--skip-assign" not in sys.argv:
        provs = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--provs=")), None)
        assign(feats, provs)
    values()
