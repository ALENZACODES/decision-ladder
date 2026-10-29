"""Canada Home Value API: address autocomplete (National Address Register), municipal property records
(Calgary, Edmonton, Winnipeg, Vancouver, Montréal) and an AI valuation model trained on assessed values."""
import json, math, pathlib, re, sqlite3, statistics, sys
import numpy as np, pandas as pd, lightgbm as lgb
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key, split_nar_civic                      # noqa: E402
from server.fsa_values import load as load_fsa, index_at, region as fsa_region   # noqa: E402

DATA, MOD = ROOT / "data", ROOT / "models"
app = FastAPI(title="Canada Home Value")
FSA = load_fsa()
PROV_MEDIAN = {}
for v in FSA.values():
    PROV_MEDIAN.setdefault(v["fsa"][0], []).append(v["median_today"])
PROV_MEDIAN = {k: statistics.median(x) for k, x in PROV_MEDIAN.items()}
PROV_LETTER = {"NL": "A", "NS": "B", "PE": "C", "NB": "E", "QC": "H", "ON": "M", "MB": "R", "SK": "S", "AB": "T", "BC": "V", "NT": "X", "NU": "X", "YT": "Y"}

# Assessment valuation date -> today (Sep 2026), from the regional index (same rule the model was trained with)
from train_model import region_of                                                    # noqa: E402


def time_adj(city, value_date, lat=None, lon=None):
    reg = region_of(city, lat, lon)
    if not reg or not value_date:
        return None
    return index_at(reg, 2026, 8) / index_at(reg, int(value_date[:4]), int(value_date[5:7]) - 1)


db = sqlite3.connect(DATA / "addresses.db", check_same_thread=False) if (DATA / "addresses.db").exists() else None
model = lgb.Booster(model_file=str(MOD / "avm.txt")) if (MOD / "avm.txt").exists() else None
meta = json.loads((MOD / "avm_meta.json").read_text()) if (MOD / "avm_meta.json").exists() else {}
parcels = pd.read_parquet(DATA / "parcels.parquet") if (DATA / "parcels.parquet").exists() else None
if parcels is not None:
    parcels = parcels.reset_index(drop=True)
    KEYIDX = {}
    for i, (prov, k) in enumerate(zip(parcels["prov"].values, parcels["key"].values)):
        KEYIDX.setdefault((prov, k), i)
        KEYIDX.setdefault((prov, "|" + k.split("|", 1)[1]), i)     # building-level fallback for units
    has = parcels[parcels.lat.notna() & (parcels["unit"].fillna("") == "")]
    cell = (has.lat * 200).round().astype(int).astype(str) + ":" + (has.lon * 200).round().astype(int).astype(str)
    GRID = {k: g.index.values for k, g in has.groupby(cell)}

SOURCE = {"Strathcona County": "Strathcona County", "Langley Township": "Township of Langley"}


def source_name(city):
    return "Québec" if str(city).startswith("QC-") else SOURCE.get(city, city)


TYPE_FROM_CLS = {"house": "detached", "semi": "semi", "duplex": "duplex", "multiplex": "multiplex", "town": "town",
                 "condotown": "condotown", "condo": "condo", "mobile": "mobile"}
CLS_LABEL = {"house": "Detached house", "semi": "Semi-detached", "duplex": "Duplex", "multiplex": "Triplex / fourplex",
             "town": "Townhouse", "condotown": "Condo townhouse", "condo": "Condo apartment", "mobile": "Mobile home", "other": "Other"}


@app.get("/api/health")
def health():
    return {"addresses": bool(db), "model": bool(model), "parcels": 0 if parcels is None else len(parcels),
            "postal_areas": len(FSA),
            "model_accuracy": {k: meta.get(k) for k in ("median_abs_pct_err", "within_5pct", "within_10pct", "by_city", "by_class")}}


@app.get("/api/fsa/{code}")
def fsa(code: str):
    v = FSA.get(code.upper().replace(" ", "")[:3])
    if not v:
        raise HTTPException(404, "No census value for that postal area")
    return v


_SYN_GROUPS = [("RD", "ROAD"), ("TWP", "TOWNSHIP"), ("RGE", "RANGE"), ("RR", "RANGE"), ("HWY", "HIGHWAY"), ("ST", "STREET", "SAINT"),
               ("STE", "SAINTE"), ("AVE", "AV", "AVENUE"), ("DR", "DRIVE"), ("BLVD", "BOUL", "BOULEVARD"), ("CRES", "CR", "CRESCENT"),
               ("CT", "CRT", "COURT"), ("PL", "PLACE"), ("LN", "LANE"), ("MT", "MOUNT"), ("PKY", "PKWY", "PARKWAY"), ("TRL", "TR", "TRAIL"),
               ("CIR", "CIRCLE"), ("SQ", "SQUARE"), ("TERR", "TERRACE"), ("HTS", "HEIGHTS"), ("PT", "POINT"), ("CH", "CHEMIN"),
               ("N", "NORTH"), ("S", "SOUTH"), ("E", "EAST", "EST"), ("W", "WEST", "OUEST", "O")]
SYN = {}
for g in _SYN_GROUPS:
    for t in g:
        SYN.setdefault(t, set()).update(g)


@app.get("/api/suggest")
def suggest(q: str, limit: int = 8):
    if not db:
        raise HTTPException(503, "Address index not built yet")
    toks = [t for t in re.findall(r"[\w']+", q.upper()) if t]
    if not toks:
        return []
    def term(t):
        alts = [t] + [x for x in SYN.get(t, ()) if x != t]
        return "(" + " OR ".join(f'"{x}"*' for x in alts) + ")" if len(alts) > 1 else f'"{t}"*'

    def run(ts):
        return db.execute("""SELECT a.id,a.civic,a.street,a.city,a.prov,a.postal FROM addr_fts f JOIN addr a ON a.id=f.rowid
                             WHERE addr_fts MATCH ? LIMIT 400""", (" AND ".join(term(t) for t in ts[:7]),)).fetchall()
    rows = run(toks)
    if not rows and len(toks) > 1 and toks[0].isdigit():   # house number not on that street: show the street's addresses
        rows = run(toks[1:])
    words = set(toks)

    def score(r):  # exact house number first, whole-word matches next, then no unit, then shortest
        unit, civic = split_nar_civic(r[1])
        hay = set(re.findall(r"[\w']+", f"{r[2]} {r[3]} {r[4]}".upper()))
        return (civic not in words, -len(words & hay), bool(unit) and unit not in words, len(r[2]))
    rows = sorted(rows, key=score)[:limit]
    return [{"id": r[0], "label": f"{r[1]} {r[2]}, {r[3]} {r[4]} {r[5]}".strip(), "city": r[3], "prov": r[4]} for r in rows]


def find_parcel(prov, unit, civic, street, lat, lon):
    if parcels is None:
        return None, None
    i = KEYIDX.get((prov, key(unit, civic, street)))
    if i is not None:
        return parcels.loc[i], "address"
    if unit:   # unit not in the records: fall back to the building, flagged as such
        i = KEYIDX.get((prov, "|" + key("", civic, street).split("|", 1)[1]))
        if i is not None:
            return parcels.loc[i], "building"
        return None, None
    best, bd = None, 1e9
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            idx = GRID.get(f"{round(lat*200)+di}:{round(lon*200)+dj}")
            if idx is None:
                continue
            g = parcels.loc[idx]
            d = (g.lat - lat) ** 2 + ((g.lon - lon) * math.cos(math.radians(lat))) ** 2
            j = d.idxmin()
            if d[j] < bd:
                bd, best = d[j], parcels.loc[j]
    if best is None or math.sqrt(bd) * 111_000 > 30:
        return None, None
    return best, "nearest"


def predict(row):
    X = pd.DataFrame([{f: row.get(f, np.nan) for f in meta["feats"]}])
    X["is_unit"] = float(bool(row.get("unit") or ""))
    X["hood"] = f'{row.get("city")}:{row.get("hood") if pd.notna(row.get("hood")) else "NA"}'
    for c, levels in meta["cats"].items():
        X[c] = pd.Categorical(X[c].astype(str), categories=levels)
    return float(np.exp(model.predict(X)[0]))


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return None
    return v.item() if hasattr(v, "item") else v


def floor_from_unit(unit):
    u = unit.upper()
    if u.startswith("PH"):
        return None, "penthouse"
    if u in ("BSMT", "BASEMENT", "LOWER", "MAIN", "UPPER", "REAR", "A", "B", "C"):
        return None, None
    n = re.match(r"^(\d+)", u)
    if not n:
        return None, "condo"
    n = int(n.group(1))
    return (n // 100 if n >= 100 else 1), "condo"


@app.get("/api/property/{pid}")
def property_detail(pid: int):
    if not db:
        raise HTTPException(503, "Address index not built yet")
    r = db.execute("SELECT civic,street,city,prov,postal,lat,lon,use,csd FROM addr WHERE id=?", (pid,)).fetchone()
    if not r:
        raise HTTPException(404, "Address not found")
    civic_full, street, city, prov, postal, lat, lon, use, csd = r
    unit, civic = split_nar_civic(civic_full)
    fz = FSA.get((postal or "").replace(" ", "")[:3])
    reg = fz["region"] if fz else fsa_region((postal or PROV_LETTER.get(prov, "M") + "0")[:3] if postal else PROV_LETTER.get(prov, "M") + "0")
    bench = fz["median_today"] if fz else PROV_MEDIAN.get(PROV_LETTER.get(prov, "M"), 500000)
    out = {"address": f"{civic_full} {street}", "unit": unit, "city": city, "prov": prov, "postal": postal, "lat": lat, "lon": lon,
           "municipality": csd, "facts": {}, "record": None, "ai": None, "fsa": fz, "floor": None, "suggest_type": None,
           "area": {"name": " ".join(w[:1].upper() + w[1:].lower() for w in (csd or city or prov).split()), "prov": prov, "region": reg, "bench": bench}}
    if unit:
        out["floor"], out["suggest_type"] = floor_from_unit(unit)

    p, how = find_parcel(prov, unit, civic, street, lat, lon)
    display = [["Municipality", csd or city], ["Postal code", postal or "—"]]
    if p is not None:
        f = {k: clean(p.get(k)) for k in ("city", "hood", "lot_sf", "living_sf", "year", "rooms", "storeys", "units", "cls", "garage", "zoning", "value", "value_date")}
        out["facts"] = f
        out["record"] = {"source": f'{source_name(f["city"])} property records', "match": how}
        if f["cls"] in TYPE_FROM_CLS and how == "address":
            out["suggest_type"] = TYPE_FROM_CLS[f["cls"]] if not (out["suggest_type"] == "penthouse") else "penthouse"
        hood = str(f["hood"] or "")
        if hood and not hood.isdigit() and not hood.startswith(("VAN-", "REM")) and hood.lower() not in (str(f["city"]).lower(), "no_data", "strathcona"):
            display.append(["Neighbourhood", hood.title()])
        if f["cls"]: display.append(["Property type", CLS_LABEL.get(f["cls"], f["cls"])])
        if f["year"]: display.append(["Year built", int(f["year"])])
        if f["living_sf"]: display.append(["Living area", f'{int(round(f["living_sf"], -1)):,} sq ft'])
        if f["lot_sf"] and f["cls"] not in ("condo",): display.append(["Lot size", f'{int(round(f["lot_sf"], -1)):,} sq ft'])
        if f["storeys"]: display.append(["Storeys", f["storeys"]])
        if f["units"] and f["units"] > 1: display.append(["Units in building", int(f["units"])])
        if f["rooms"]: display.append(["Rooms", int(f["rooms"])])
        if f["garage"] is not None: display.append(["Garage", "Yes" if f["garage"] else "No"])
        if f["zoning"]: display.append(["Zoning", f["zoning"]])
        if f["value"]:
            display.append([f'Assessed value ({f["value_date"][:4]})', f'${int(f["value"]):,}'])
        adj = time_adj(f["city"], f["value_date"], p.get("lat"), p.get("lon"))
        if model is not None and f["value"] and adj and how in ("address", "nearest"):
            ai = predict(p.to_dict())               # model is trained in Sep-2026 dollars
            city_err = meta.get("by_city", {}).get(f["city"])
            err = city_err or meta.get("median_abs_pct_err", .08)
            w = 0.6 if err <= 0.07 else 0.75 if err <= 0.12 else 0.9   # trust the assessment more where the model is weaker
            est = w * f["value"] * adj + (1 - w) * ai
            out["ai"] = {"estimate": round(est, -3), "low": round(est * (1 - 1.5 * err), -3), "high": round(est * (1 + 1.5 * err), -3),
                         "model_value": round(ai, -3), "assessment_today": round(f["value"] * adj, -3),
                         "method": f'{source_name(f["city"])} assessment (valued {f["value_date"]}) blended with the AI model, moved to Sep 2026',
                         "model_median_error": err}
    if fz:
        display.append([f'Postal area {fz["fsa"]} median', f'${int(fz["median_today"]):,} today'])
    out["display"] = display
    return out


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
