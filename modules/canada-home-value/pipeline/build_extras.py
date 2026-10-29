"""Extra public data for the page: rents, zoning per address, non-residential addresses.

static/data/rents.json          {"PROV|CENTRE": [bachelor, 1br, 2br, 3br]} CMHC 2025 average rents (StatCan 34-10-0133), plus "PROV|*" medians
static/data/zoning/<pre>.json   {FSA: {"UNIT|CIVIC|CORE|DIR|TYPE": "zoning code"}}  Calgary, Edmonton, Vancouver, Langley Twp, Winnipeg
static/data/zoning/index.json   {prefix: [FSA...]}
static/data/nonres/<L>.json     {FSA: ["UNIT/CIVIC|CORE|DIR", ...]} addresses the National Address Register marks non-residential (use 3)
"""
import json, pathlib, re, sqlite3, sys
from collections import defaultdict
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key, key3, split_nar_civic, street_core, street_dir   # noqa: E402

RAW = ROOT / "data" / "raw"; OUT = ROOT / "static" / "data"
PROV = {"Newfoundland and Labrador": "NL", "Prince Edward Island": "PE", "Nova Scotia": "NS", "New Brunswick": "NB", "Quebec": "QC",
        "Ontario": "ON", "Manitoba": "MB", "Saskatchewan": "SK", "Alberta": "AB", "British Columbia": "BC", "Yukon": "YT",
        "Northwest Territories": "NT", "Nunavut": "NU"}

# 1. rents
r = pd.read_csv(RAW / "rent" / "34100133.csv", dtype=str)
r = r[(r.REF_DATE == r.REF_DATE.max()) & r["Type of structure"].str.startswith("Row and apartment")]
r["VALUE"] = pd.to_numeric(r.VALUE, errors="coerce")
r = r[r.VALUE > 0]
UNIT = {"Bachelor units": 0, "One bedroom units": 1, "Two bedroom units": 2, "Three bedroom units": 3}
rents = {}
for geo, g in r.groupby("GEO"):
    m = re.match(r"(.+?), (.+?)(?: part.*)?$", geo)
    if not m:
        continue
    name, prov = m.group(1), PROV.get(m.group(2).replace(" part", "").strip())
    if not prov:
        continue
    v = [None] * 4
    for _, row in g.iterrows():
        if row["Type of unit"] in UNIT:
            v[UNIT[row["Type of unit"]]] = int(row.VALUE)
    for part in re.split(r"[-–]", name):                     # "Ottawa-Gatineau" -> both names
        rents[f"{prov}|{part.strip().upper()}"] = v
by_prov = defaultdict(list)
for k, v in rents.items():
    by_prov[k.split("|")[0]].append(v)
for p, vs in by_prov.items():
    rents[f"{p}|*"] = [int(np.median([x[i] for x in vs if x[i]])) if any(x[i] for x in vs) else None for i in range(4)]
(OUT / "rents.json").write_text(json.dumps(rents, separators=(",", ":")))
print(len(rents), "rent centres; ON*", rents.get("ON|*"), "TORONTO", rents.get("ON|TORONTO"))

# 2. zoning per address
num = lambda s: pd.to_numeric(s, errors="coerce")
rows = []
c = pd.read_parquet(RAW / "calgary.parquet")
pc = c.address.fillna("").str.extract(r"^(?:(?P<u>\w+)\s+(?=\d+\w?\s))?(?P<c>\d+\w?)\s+(?P<s>.+)$")
rows += [("AB", key3(u, cv, st), z) for u, cv, st, z in zip(pc.u.fillna(""), pc.c.fillna(""), pc.s.fillna(""), c.land_use_designation.fillna("")) if z]
ed = pd.read_parquet(RAW / "edmonton_details.parquet")
rows += [("AB", key3("", h, st), z) for h, st, z in zip(ed.house_number.fillna(""), ed.street_name.fillna(""), ed.zoning.fillna("")) if z]
v = pd.read_parquet(RAW / "vancouver.parquet")
rows += [("BC", key3(u if lt == "STRATA" else "", cv, st), z) for u, cv, st, z, lt in
         zip(v.from_civic_number.fillna(""), v.to_civic_number.fillna(""), v.street_name.fillna(""), v.zoning_district.fillna(""), v.legal_type.fillna("")) if z]
l = pd.read_parquet(RAW / "langley_twp.parquet")
rows += [("BC", key3("", str(h), st), z) for h, st, z in zip(l.House.fillna(""), l.Street.fillna(""), l.Zoning.fillna("")) if z]
w = pd.read_parquet(RAW / "winnipeg.parquet")
rows += [("MB", key3("", n, f"{s} {t}"), z) for n, s, t, z in zip(w.street_number.fillna(""), w.street_name.fillna(""), w.street_type.fillna(""), w.zoning.fillna("")) if z]
db = sqlite3.connect(ROOT / "data" / "addresses.db")
post = {}
for prov in ("AB", "BC", "MB"):
    for civic, street, p in db.execute("SELECT civic, street, replace(postal,' ','') FROM addr WHERE prov=?", (prov,)):
        if p:
            u, cv = split_nar_civic(civic)
            post.setdefault((prov, key3(u, cv, street)), p[:3]); post.setdefault((prov, key3("", cv, street)), p[:3])
zo = defaultdict(lambda: defaultdict(dict))
for prov, k, z in rows:
    f = post.get((prov, k))
    if f:
        zo[f[:2]][f][k] = str(z).split(" - ")[0].strip()[:24]
ZD = OUT / "zoning"; ZD.mkdir(exist_ok=True)
for f in ZD.glob("*.json"):
    f.unlink()
idx = {}
for pre, d in zo.items():
    s = json.dumps(d, separators=(",", ":"))
    if len(s) < 8_000_000:
        (ZD / f"{pre}.json").write_text(s); idx[pre] = sorted(d)
    else:
        for fsa, dd in d.items():
            (ZD / f"{fsa}.json").write_text(json.dumps({fsa: dd}, separators=(",", ":"))); idx[fsa] = [fsa]
(ZD / "index.json").write_text(json.dumps(idx, separators=(",", ":")))
print(sum(len(x) for d in zo.values() for x in d.values()), "addresses with zoning;", round(sum(f.stat().st_size for f in ZD.glob("*.json")) / 1e6, 1), "MB")

# 3. non-residential addresses
NR = OUT / "nonres"; NR.mkdir(exist_ok=True)
for f in NR.glob("*.json"):
    f.unlink()
nr = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))      # letter -> FSA -> "CORE|DIR" -> ["unit/civic", ...]
for civic, street, p in db.execute("SELECT civic, street, replace(postal,' ','') FROM addr WHERE use=3 AND postal IS NOT NULL"):
    if p and len(p) == 6:
        u, cv = split_nar_civic(civic)
        nr[p[0]][p[:3]][f"{street_core(street)}|{street_dir(street)}"].append(f"{u}/{cv}" if u else cv)
nr = {L: {f: {k: " ".join(sorted(set(v))) for k, v in d.items()} for f, d in fs.items()} for L, fs in nr.items()}
for L, d in nr.items():
    (NR / f"{L}.json").write_text(json.dumps(d, separators=(",", ":")))
print(sum(len(x) for d in nr.values() for x in d.values()), "non-residential addresses;", round(sum(f.stat().st_size for f in NR.glob("*.json")) / 1e6, 1), "MB")
