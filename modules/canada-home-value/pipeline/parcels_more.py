"""Loaders for the second wave of open assessment data: Québec province-wide roll, Victoria, Langley Township,
Strathcona County and New Brunswick (2017, facts only). Each returns the same columns as build_parcels.py."""
import glob, pathlib, sqlite3, struct
import numpy as np, pandas as pd
from addrkey import key

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
num = lambda s: pd.to_numeric(s, errors="coerce")
M2_TO_SF = 10.7639


def geocode(df, prov, csds=None):
    """Fill lat/lon from the National Address Register by address key (unit, then building)."""
    from addrkey import split_nar_civic
    db = sqlite3.connect(ROOT / "data" / "addresses.db")
    q = "SELECT civic,street,lat,lon FROM addr WHERE prov=?" + (f" AND csd IN ({','.join('?'*len(csds))})" if csds else "")
    geo = {}
    for civic, street, lat, lon in db.execute(q, [prov] + list(csds or [])):
        u, c = split_nar_civic(civic)
        geo.setdefault(key(u, c, street), (lat, lon)); geo.setdefault(key("", c, street), (lat, lon))
    ll = [geo.get(k) or geo.get("|" + k.split("|", 1)[1]) for k in df["key"]]
    df["lat"] = [x[0] if x else np.nan for x in ll]; df["lon"] = [x[1] if x else np.nan for x in ll]
    print(prov, csds, "geocoded", int(df.lat.notna().sum()), "of", len(df))
    return df


def _frame(**cols):
    base = dict(city=None, prov=None, key=None, unit="", lat=np.nan, lon=np.nan, value=np.nan, value_date=None, hood=None,
                lot_sf=np.nan, living_sf=np.nan, year=np.nan, rooms=np.nan, storeys=np.nan, units=np.nan, cls="house",
                garage=np.nan, zoning=None, use_label=None)
    base.update(cols)
    return pd.DataFrame(base)


def quebec():
    f = glob.glob(str(RAW / "qc" / "Role2026_geopackage" / "*.gpkg"))[0]
    db = sqlite3.connect(f)
    u = pd.read_sql("""SELECT id_provinc, code_mun, rl0105a use, rl0302a land_m2, rl0306a storeys, rl0307a year, rl0308a floor_m2,
                              rl0309a lien, rl0311a units, rl0404a value, dat_cond_mrche vdate
                       FROM b05v_unite_evaln_2026 WHERE rl0105a LIKE '1%'""", db)          # CUBF 1xxx = residential
    a = pd.read_sql("""SELECT id_provinc, rl0101a civic, rl0101e stype, rl0101g sname, rl0101h sdir, rl0101i unit
                       FROM b05v_adr_unite_evaln_2026 WHERE no_seq_adr='1' OR no_seq_adr IS NULL""", db)
    a = a.drop_duplicates("id_provinc")
    g = pd.read_sql("SELECT id_provinc, geom FROM rol_unite_p_2026", db).drop_duplicates("id_provinc")

    def xy(b):  # GeoPackage blob: 8-byte header then envelope (minx, maxx, miny, maxy) for points
        try:
            minx, _, miny, _ = struct.unpack("<4d", b[8:40]); return minx, miny
        except Exception:
            return np.nan, np.nan
    pts = g["geom"].map(xy)
    g["lon"] = [p[0] for p in pts]; g["lat"] = [p[1] for p in pts]
    d = u.merge(a, on="id_provinc", how="left").merge(g[["id_provinc", "lat", "lon"]], on="id_provinc", how="left")
    n = num(d["units"]); unit = d["unit"].fillna("").astype(str)
    condo = (n == 1) & ((d["lien"] == "5") | (unit != ""))
    cls = np.select([condo, n == 2, n.between(3, 4), n > 4, d["lien"] == "2", d["lien"].isin(["3", "4"])],
                    ["condo", "duplex", "multiplex", "other", "semi", "town"], "house")
    # municipality name from the NAR (CSD) is applied later via the address match; keep code for grouping
    street = d["stype"].fillna("") + " " + d["sname"].fillna("") + " " + d["sdir"].fillna("")
    return _frame(city="QC-" + d["code_mun"].astype(str), prov="QC",
                  key=[key(un, cv, st) for un, cv, st in zip(unit, d["civic"].fillna(""), street)],
                  unit=np.where(cls == "condo", unit, ""), lat=d["lat"], lon=d["lon"], value=num(d["value"]),
                  value_date=d["vdate"].str[:10], hood=d["code_mun"], lot_sf=num(d["land_m2"]) * M2_TO_SF,
                  living_sf=num(d["floor_m2"]) * M2_TO_SF, year=num(d["year"]).where(lambda x: x > 1700),
                  storeys=num(d["storeys"]), units=n, cls=cls, use_label=d["use"])


def victoria():
    v = pd.read_parquet(RAW / "victoria.parquet")
    v = v[v["assess_abbreviation"].fillna("").str.contains("Residential")]
    unit = v["UNIT"].fillna("").astype(str)
    strata = v["LEGAL_TYPE"].eq("STRATA")
    return _frame(city="Victoria", prov="BC",
                  key=[key(u if s else "", h, st) for u, h, st, s in zip(unit, num(v["HOUSE"]).astype("Int64").astype(str).replace("<NA>", ""), v["STREET"].fillna(""), strata)],
                  unit=np.where(strata, unit, ""), lat=num(v.get("_lat")), lon=num(v.get("_lon")),
                  value=num(v["impr_gross"]).fillna(0) + num(v["land_gross"]).fillna(0), value_date="2025-07-01",
                  hood="Victoria", cls=np.where(strata, "condo", "house")).pipe(geocode, "BC", ["Victoria"])


def langley_twp():
    v = pd.read_parquet(RAW / "langley_twp.parquet")
    val = num(v["Residential_Buildings"]).fillna(0) + num(v["Residential_Land"]).fillna(0)
    v = v[val > 0]; val = val[val > 0]
    unit = v["Unit"].fillna("").astype(str)
    strata = v["Legal_Type"].eq("STRATA")
    lot = num(v["Lot_Size"]) * np.where(v["Lot_Desc"].fillna("").str.contains("ACRE"), 43560, 1)
    return _frame(city="Langley Township", prov="BC",
                  key=[key(u if s else "", h, st) for u, h, st, s in zip(unit, v["House"].fillna("").astype(str), v["Street"].fillna(""), strata)],
                  unit=np.where(strata, unit, ""), lat=num(v["Latitude"]), lon=num(v["Longitude"]), value=val,
                  value_date="2025-07-01", hood=v["Community"], lot_sf=np.where(strata, np.nan, lot),
                  cls=np.where(strata, "condo", "house"), zoning=v["Zoning"])


def strathcona():
    s = pd.read_parquet(RAW / "strathcona.parquet")
    parts = s["address"].fillna("").str.extract(r"^(?P<c>\d+\w?)\s+(?P<s>.+)$")
    bldg = s["bldg"].fillna("")
    cls = np.select([bldg.str.contains("Condo|Apartment", case=False), bldg.str.contains("Duplex|Semi", case=False),
                     bldg.str.contains("Row|Town", case=False), bldg.str.contains("Mobile|Manufactured", case=False)],
                    ["condo", "semi", "town", "mobile"], "house")
    lot = num(s["parcelarea"]) * np.where(s["measured_in"].eq("A"), 43560, 1)
    return _frame(city="Strathcona County", prov="AB", key=[key("", c, st) for c, st in zip(parts["c"].fillna(""), parts["s"].fillna(""))],
                  lat=num(s["latitude"]), lon=num(s["longitude"]), value=num(s["assess_2023"]), value_date="2023-07-01",
                  hood="Strathcona", lot_sf=lot, living_sf=num(s["feet"]), cls=cls,
                  garage=(s["garage"] == "Y").astype(float), use_label=bldg)


def new_brunswick():
    t = pd.read_csv(RAW / "nb" / "Tombstone.tsv", sep="\t", dtype=str, encoding="latin-1")
    t.columns = ["pan", "loc", "tacd", "desc", "yr", "val", "levy"]
    t = t[t["desc"].fillna("").str.contains("House|Dwelling|Condo|Mobile|Duplex", case=False)]
    parts = t["loc"].fillna("").str.upper().str.extract(r"^(?P<c>\d+\w?)\s+(?P<s>.+)$")
    d = t["desc"].fillna("")
    cls = np.select([d.str.contains("Condo", case=False), d.str.contains("Mobile", case=False), d.str.contains("Duplex", case=False)],
                    ["condo", "mobile", "duplex"], "house")
    return _frame(city="New Brunswick", prov="NB", key=[key("", c, st) for c, st in zip(parts["c"].fillna(""), parts["s"].fillna(""))],
                  value=num(t["val"]), value_date="2017-01-01", hood=t["tacd"], cls=cls, use_label=d).pipe(geocode, "NB")


LOADERS = [quebec, victoria, langley_twp, strathcona, new_brunswick]
