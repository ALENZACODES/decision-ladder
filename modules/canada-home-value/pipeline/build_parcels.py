"""Merge municipal property records into one table keyed to National Address Register addresses.

Output: data/parcels.parquet with columns
  city, prov, key, unit, lat, lon, value, value_date, hood, lot_sf, living_sf, year, rooms, storeys, units,
  cls (house/semi/town/condo/duplex/multiplex/mobile/other), garage, zoning, use_label
"""
import pathlib, sqlite3, sys
import numpy as np, pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from addrkey import key, split_nar_civic

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, DATA = ROOT / "data" / "raw", ROOT / "data"
num = lambda s: pd.to_numeric(s, errors="coerce")
M2_TO_SF = 10.7639


def nar_coords(cities, prov):
    db = sqlite3.connect(DATA / "addresses.db")
    q = f"SELECT civic,street,lat,lon,postal FROM addr WHERE prov=? AND csd IN ({','.join('?'*len(cities))})"
    rows = db.execute(q, [prov] + list(cities)).fetchall()
    out = {}
    for civic, street, lat, lon, pc in rows:
        u, c = split_nar_civic(civic)
        out.setdefault(key(u, c, street), (lat, lon, pc))
        out.setdefault(key("", c, street), (lat, lon, pc))   # building-level fallback
    print(prov, cities, "NAR keys", len(out))
    return out


def calgary():
    c = pd.read_parquet(RAW / "calgary.parquet")
    addr = c["address"].fillna("")
    sub = c["sub_property_use"].fillna("")
    parts = addr.str.extract(r"^(?:(?P<u>\w+)\s+(?=\d+\w?\s))?(?P<c>\d+\w?)\s+(?P<s>.+)$")
    is_unit = parts["u"].notna() & sub.str.match(r"^(R2|R3|R402)")
    cls = np.select([sub.eq("R110"), sub.eq("R120"), sub.eq("R121"), sub.str.match(r"^R[23]"), sub.eq("R401"), sub.eq("R402")],
                    ["house", "semi", "duplex", "condo", "town", "condotown"], "other")
    return pd.DataFrame({"city": "Calgary", "prov": "AB",
        "key": [key(u if iu else "", cc, ss) for u, cc, ss, iu in zip(parts["u"].fillna(""), parts["c"].fillna(""), parts["s"].fillna(""), is_unit)],
        "unit": np.where(is_unit, parts["u"].fillna(""), ""), "lat": num(c["lat"]), "lon": num(c["lon"]),
        "value": num(c["assessed_value"]), "value_date": "2025-07-01", "hood": c["comm_name"],
        "lot_sf": num(c["land_size_sf"]), "living_sf": np.nan, "year": num(c["year_of_construction"]), "rooms": np.nan,
        "storeys": np.nan, "units": np.nan, "cls": cls, "garage": np.nan, "zoning": c["land_use_designation"], "use_label": sub})


def edmonton():
    e = pd.read_parquet(RAW / "edmonton.parquet")
    d = pd.read_parquet(RAW / "edmonton_details.parquet")[["account_number", "zoning", "lot_size", "total_gross_area", "year_built"]]
    e = e.merge(d, on="account_number", how="left")
    suite = e["suite"].fillna("").astype(str).str.strip() if "suite" in e else pd.Series("", index=e.index)
    zon = e["zoning"].fillna("")
    cls = np.where(suite != "", "condo", np.where(zon.str.match(r"^(RF[34]|RM|RA)"), "town", "house"))
    return pd.DataFrame({"city": "Edmonton", "prov": "AB",
        "key": [key(u, h, s) for u, h, s in zip(suite, e["house_number"].fillna(""), e["street_name"].fillna(""))],
        "unit": suite, "lat": num(e["latitude"]), "lon": num(e["longitude"]), "value": num(e["assessed_value"]),
        "value_date": "2025-07-01", "hood": e["neighbourhood"], "lot_sf": num(e["lot_size"]) * M2_TO_SF,
        "living_sf": num(e["total_gross_area"]) * M2_TO_SF, "year": num(e["year_built"]), "rooms": np.nan, "storeys": np.nan,
        "units": np.nan, "cls": cls, "garage": (e["garage"] == "Y").astype(float), "zoning": zon, "use_label": ""})


def winnipeg():
    w = pd.read_parquet(RAW / "winnipeg.parquet")
    use = w["property_use_code"].fillna("")
    cls = np.select([use.str.contains("CONDO"), use.str.contains("DUPLEX|DOUBLE"), use.str.contains("SEMI|SIDE BY SIDE"),
                     use.str.contains("ROW|TOWN"), use.str.contains("TRIPLEX|FOURPLEX|MULTI"), use.str.contains("MOBILE")],
                    ["condo", "duplex", "semi", "town", "multiplex", "mobile"], "house")
    full = w["full_address"].fillna("")
    unit = full.str.extract(r"^(?:UNIT\s+)?(\w+)\s*-\s*\d")[0].fillna("")
    return pd.DataFrame({"city": "Winnipeg", "prov": "MB",
        "key": [key(u, n, f"{s} {t}") for u, n, s, t in zip(unit, w["street_number"].fillna(""), w["street_name"].fillna(""), w["street_type"].fillna(""))],
        "unit": unit, "lat": num(w["lat"]), "lon": num(w["lon"]), "value": num(w["total_assessed_value"]),
        "value_date": "2025-04-01", "hood": w["neighbourhood_area"], "lot_sf": num(w["assessed_land_area"]),
        "living_sf": num(w["total_living_area"]), "year": num(w["year_built"]), "rooms": num(w["rooms"]),
        "storeys": w["building_type"].map({"ONE STOREY": 1, "TWO STOREY": 2, "ONE & 1/2 STOREY": 1.5, "BI-LEVEL": 1.5, "SPLIT LEVEL": 1.5}),
        "units": np.nan, "cls": cls,
        "garage": ((w["attached_garage"] == "Yes") | (w["detached_garage"] == "Yes")).astype(float),
        "zoning": w["zoning"], "use_label": use})


def vancouver():
    v = pd.read_parquet(RAW / "vancouver.parquet")
    v = v[v["zoning_classification"].fillna("").str.contains("Residential|Dwelling|Comprehensive|Multiple|Two-Family|One-Family|RT|RM|RS", regex=True)]
    unit = v["from_civic_number"].fillna("").astype(str)
    strata = v["legal_type"].eq("STRATA")
    cls = np.where(strata, np.where(v["zoning_classification"].str.contains("Two-Family|One-Family|RT|Residential Inclusive", na=False), "condotown", "condo"),
                   np.where(v["zoning_classification"].str.contains("Two-Family", na=False), "duplex", "house"))
    keys = [key(u if s else "", c, st) for u, c, st, s in zip(unit, v["to_civic_number"].fillna(""), v["street_name"].fillna(""), strata)]
    geo = nar_coords(["Vancouver"], "BC")
    ll = [geo.get(k) or geo.get(k.split("|", 1)[0] and "|" + k.split("|", 1)[1]) for k in keys]
    return pd.DataFrame({"city": "Vancouver", "prov": "BC", "key": keys, "unit": np.where(strata, unit, ""),
        "lat": [x[0] if x else np.nan for x in ll], "lon": [x[1] if x else np.nan for x in ll],
        "value": num(v["current_land_value"]).fillna(0) + num(v["current_improvement_value"]).fillna(0), "value_date": "2025-07-01",
        "hood": "VAN-" + v["neighbourhood_code"].fillna(""), "lot_sf": np.nan, "living_sf": np.nan, "year": num(v["year_built"]),
        "rooms": np.nan, "storeys": np.nan, "units": np.nan, "cls": cls, "garage": np.nan,
        "zoning": v["zoning_district"], "use_label": v["zoning_classification"]})


def montreal():
    m = pd.read_parquet(RAW / "montreal.parquet")
    m = m[m["LIBELLE_UTILISATION"].isin(["Logement", "Logements sociaux et abordables"])]
    unit = m["SUITE_DEBUT"].fillna("").str.strip()
    condo = m["CATEGORIE_UEF"].eq("Condominium")
    n = num(m["NOMBRE_LOGEMENT"])
    cls = np.where(condo, "condo", np.select([n == 1, n == 2, n.between(3, 4)], ["house", "duplex", "multiplex"], "other"))
    civ = m["CIVIQUE_DEBUT"].fillna("").str.strip()
    keys = [key(u, c, s) for u, c, s in zip(unit, civ, m["NOM_RUE"].fillna(""))]
    geo = nar_coords(["Montréal", "Montreal"], "QC")
    ll = [geo.get(k) or geo.get("|" + k.split("|", 1)[1]) for k in keys]
    return pd.DataFrame({"city": "Montréal", "prov": "QC", "key": keys, "unit": unit,
        "lat": [x[0] if x else np.nan for x in ll], "lon": [x[1] if x else np.nan for x in ll],
        "value": np.nan, "value_date": None, "hood": m["NO_ARROND_ILE_CUM"], "lot_sf": num(m["SUPERFICIE_TERRAIN"]) * M2_TO_SF,
        "living_sf": num(m["SUPERFICIE_BATIMENT"]) * M2_TO_SF, "year": num(m["ANNEE_CONSTRUCTION"]).where(lambda x: x > 1700),
        "rooms": np.nan, "storeys": num(m["ETAGE_HORS_SOL"]), "units": n, "cls": cls, "garage": np.nan,
        "zoning": "", "use_label": m["CATEGORIE_UEF"]})


if __name__ == "__main__":
    parts = []
    from parcels_more import LOADERS
    for f in (calgary, edmonton, winnipeg, vancouver, *LOADERS):   # montreal() superseded by the Québec roll
        d = f(); parts.append(d)
        print(f.__name__, len(d), "with coords", int(d.lat.notna().sum()), "with value", int(d.value.notna().sum()),
              d.cls.value_counts().to_dict())
    p = pd.concat(parts, ignore_index=True)
    p.loc[(p.value < 30_000) | (p.value > 25_000_000), "value"] = np.nan
    for c in ("hood", "zoning", "use_label", "unit", "value_date"):
        p[c] = p[c].astype("string")
    p.to_parquet(DATA / "parcels.parquet")
    print("total", len(p))
