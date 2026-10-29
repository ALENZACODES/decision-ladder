"""Per-municipality property-type ratios from StatCan's Canadian Housing Statistics Program (table 46-10-0027).

For each census subdivision (latest year available) we take the median assessment value of each property type and
divide by the all-types median, so a neighbourhood's all-dwelling Census value can be split by type with local,
assessment-based ratios. Output: data/csd_types.json  {"PROV|NAME": {"detached": 1.31, "condo": 0.62, ...}, ...}
"""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROV = {"10": "NL", "11": "PE", "12": "NS", "13": "NB", "24": "QC", "35": "ON", "46": "MB", "47": "SK", "48": "AB",
        "59": "BC", "60": "YT", "61": "NT", "62": "NU"}
TYPE = {"Single-detached house": "detached", "Semi-detached house": "semi", "Row house": "town",
        "Condominium apartment": "condo", "Mobile home": "mobile", "Property with multiple residential units": "multiplex"}

d = pd.read_csv(ROOT / "data" / "raw" / "chsp" / "46100027.csv",
                usecols=["REF_DATE", "GEO", "DGUID", "Property type", "Period of construction", "Residency participation",
                         "Estimates", "VALUE"], dtype=str)
d = d[d["Period of construction"].str.startswith("Total") & d["Residency participation"].str.startswith("Total")
      & d.DGUID.str[4:9].eq("A0005") & d.Estimates.isin(["Median assessment value", "Number"])]
d["VALUE"] = pd.to_numeric(d.VALUE, errors="coerce")
d = d[d.VALUE.notna()]
d["prov"] = d.DGUID.str[9:11].map(PROV)
d["name"] = d.GEO.str.split(",").str[0].str.strip()
d = d.sort_values("REF_DATE").groupby(["DGUID", "Property type", "Estimates"]).tail(1)   # latest year per CSD/type
out = {}
for (dg, prov, name), g in d.groupby(["DGUID", "prov", "name"]):
    med = g[g.Estimates == "Median assessment value"].set_index("Property type").VALUE
    num = g[g.Estimates == "Number"].set_index("Property type").VALUE
    tot = med.get("Total, all property types")
    if not tot or pd.isna(tot):
        continue
    r = {"_n": int(num.get("Total, all property types", 0) or 0)}
    for k, t in TYPE.items():
        if k in med and num.get(k, 0) >= 30:          # need enough properties for a stable median
            r[t] = round(float(med[k] / tot), 3)
    # small places have unstable medians (vacant land, cottages): skip them, and keep ratios realistic
    BOUNDS = {"detached": (0.8, 1.8), "semi": (0.6, 1.4), "town": (0.5, 1.3), "condo": (0.3, 1.2), "mobile": (0.15, 0.9), "multiplex": (0.8, 3.0)}
    if r["_n"] >= 500:
        for t, (lo, hi) in BOUNDS.items():
            if t in r:
                r[t] = round(min(hi, max(lo, r[t])), 3)
        if len(r) > 1:
            out[f"{prov}|{name.upper()}"] = r
(ROOT / "data" / "csd_types.json").write_text(json.dumps(out))
print(len(out), "municipalities with type ratios")
for k in ("ON|MISSISSAUGA", "ON|TORONTO", "ON|OTTAWA", "NS|HALIFAX", "SK|SASKATOON", "NB|MONCTON"):
    print(k, out.get(k))
