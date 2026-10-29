"""Back-test sample: one real address and one postal-code query per distinct postal area (FSA) in Canada, plus addresses
with an official assessment (the value check). Ground truth comes from StatCan's National Address Register (municipality,
postal code) and the municipal assessment rolls. Writes static/backtest.json for pipeline/backtest.js run in the page.
"""
import json, pathlib, random, sqlite3, sys
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import street_core, street_dir, split_nar_civic   # noqa: E402

random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
db = sqlite3.connect(ROOT / "data" / "addresses.db")
# one pass over a random 6% of the register, then one address + one postal code per postal area
byf = {}
for row in db.execute("""SELECT civic, street, city, prov, replace(postal,' ',''), csd FROM addr
                         WHERE abs(random()) % 16 = 0 AND length(replace(postal,' ',''))=6 AND use IN (0,1,2) AND csd!=''"""):
    l = byf.setdefault(row[4][:3], [])
    if len(l) < 6:
        l.append(row)
addr, postal = [], []
for f, rows in byf.items():
    random.shuffle(rows)
    c, s, city, prov, pc, csd = rows[0]
    u, n = split_nar_civic(c)
    fmt = random.choice(["{n} {s}, {city}", "{n} {s} {city}", "{n} {s}, {city} {prov}"])
    addr.append({"q": fmt.format(n=(f"{u}-{n}" if u else n), s=s.title(), city=city.title(), prov=prov), "civic": n, "unit": u,
                 "street": s, "postal": pc, "city": city, "csd": csd, "prov": prov})
    c2, s2, city2, prov2, pc2, csd2 = rows[-1]
    postal.append({"q": f"{pc2[:3]} {pc2[3:]}", "postal": pc2, "csd": csd2, "prov": prov2})
# value check: addresses with an official assessment (largest record cities), matched to the register by civic + street
p = pd.read_parquet(ROOT / "data" / "parcels.parquet", columns=["city", "prov", "key", "unit", "value", "value_date", "cls"])
p = p[(p.unit == "") & p.value.between(100_000, 5_000_000) & p.cls.isin(["house", "semi", "town"])]
val = []
for city, g in p.groupby("city"):
    for r in g.sample(min(40, len(g)), random_state=1).itertuples():
        _, civ, core, d = r.key.split("|")[:4]
        rows = db.execute("SELECT civic, street, city, replace(postal,' ',''), csd FROM addr WHERE prov=? AND civic=? AND street LIKE ? LIMIT 20",
                          (r.prov, civ, core.split(" ")[0] + "%")).fetchall()
        rows = [x for x in rows if street_core(x[1]) == core and (street_dir(x[1]) or "") == (d or "")]
        if len(rows) != 1:
            continue
        c, s, town, pc, csd = rows[0]
        val.append({"q": f"{c} {s.title()}, {town.title()}", "civic": c, "street": s, "postal": pc, "csd": csd, "prov": r.prov,
                    "assessed": r.value, "date": r.value_date, "cls": r.cls, "roll": city})
(ROOT / "static" / "backtest.json").write_text(json.dumps({"addr": addr, "postal": postal, "value": val}, ensure_ascii=False), encoding="utf-8")
print(len(addr), "addresses,", len(postal), "postal codes,", len(val), "assessed homes")
