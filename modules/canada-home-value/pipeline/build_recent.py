"""Newer-than-Census stats (Statistics Canada, free; refreshed by the daily updater).

static/data/recent.json
  muni:  "Name|PROV" -> [pop 2021, pop latest, latest year, metro area or null]   (17-10-0155, July 1 estimates, 5,000+)
  jobs:  "Toronto" / "ON" -> [month, unemployment %, a year earlier %]            (14-10-0459, 3-month avg, seas. adj.)
Municipality -> metro area comes from the school database's CSD/CMA columns (ODEF), which covers every populated CSD.
"""
import io, json, pathlib, re, zipfile
import pandas as pd, requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "recent"; RAW.mkdir(parents=True, exist_ok=True)
PROV = {"Newfoundland and Labrador": "NL", "Prince Edward Island": "PE", "Nova Scotia": "NS", "New Brunswick": "NB", "Quebec": "QC",
        "Ontario": "ON", "Manitoba": "MB", "Saskatchewan": "SK", "Alberta": "AB", "British Columbia": "BC", "Yukon": "YT",
        "Northwest Territories": "NT", "Nunavut": "NU"}


def table(pid):
    z = RAW / f"{pid}.zip"
    z.write_bytes(requests.get(f"https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip", timeout=600).content)
    with zipfile.ZipFile(z) as zf:
        return pd.read_csv(io.BytesIO(zf.read(f"{pid}.csv")), low_memory=False)


def cma_of():
    zf = zipfile.ZipFile(ROOT / "data" / "raw" / "schools" / "odef.zip")
    d = pd.read_csv(io.BytesIO(zf.read(next(n for n in zf.namelist() if n.endswith("ODEF_v2_1.csv")))), encoding="latin-1", dtype=str)
    d = d[d.CMANAME.notna() & (d.CMANAME != "..")]
    return {(r.CSDNAME, r.Prov_Terr): r.CMANAME for r in d.itertuples()}


if __name__ == "__main__":
    pop = table("17100155")
    last = int(pop.REF_DATE.max())
    pop = pop[pop.REF_DATE.isin([2021, last])]
    cmas = cma_of()
    muni = {}
    for geo, g in pop.groupby("GEO"):
        m = re.match(r"^(.*) \([A-Z\-]+\), (.+)$", geo)
        if not m or m.group(2) not in PROV:
            continue
        name, prov = m.group(1), PROV[m.group(2)]
        v = dict(zip(g.REF_DATE, g.VALUE))
        if pd.notna(v.get(2021)) and pd.notna(v.get(last)):
            muni[f"{name}|{prov}"] = [int(v[2021]), int(v[last]), last, cmas.get((name, prov))]
    lf = table("14100459")
    lf = lf[(lf["Labour force characteristics"] == "Unemployment rate") & (lf["Statistics"] == "Estimate") & (lf["Data type"] == "Seasonally adjusted")]
    mon = lf.REF_DATE.max(); prev = f"{int(mon[:4]) - 1}{mon[4:]}"
    jobs = {}
    for geo, g in lf.groupby("GEO"):
        v = dict(zip(g.REF_DATE, g.VALUE))
        if mon not in v:
            continue
        key = PROV.get(geo) or geo.split(",")[0]
        jobs[key] = [mon, v[mon], v.get(prev)]
    (ROOT / "static" / "data" / "recent.json").write_text(json.dumps({"muni": muni, "jobs": jobs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(muni), "municipalities to", last, ";", len(jobs), "job areas to", mon)
