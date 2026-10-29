"""static/data/town_muni.json: "FSA|MAIL TOWN" -> municipality (StatCan CSD) from the National Address Register.

A mailing town (Pefferlaw) and its postal area (L0E) don't name the municipality (Georgina); several municipalities share
one rural postal area, so the page looks the municipality up here instead of guessing the largest one.
"""
import json, pathlib, sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
db = sqlite3.connect(ROOT / "data" / "addresses.db")
best, exact = {}, {}
for pc, city, csd, n in db.execute("""SELECT replace(postal,' ',''), city, csd, count(*) FROM addr
                                      WHERE length(replace(postal,' ',''))=6 AND csd!='' GROUP BY 1,2,3"""):
    k = pc[:3] + "|" + city
    best[k] = best.get(k, {}); best[k][csd] = best[k].get(csd, 0) + n
    e = pc + "|" + city
    if e not in exact or n > exact[e][1]:
        exact[e] = (csd, n)
town = {k: max(v, key=v.get) for k, v in best.items()}
# full postal codes whose municipality differs from their town's usual one (reserves, towns inside a county, boundary streets)
pcx = {k.split("|")[0]: v[0] for k, v in exact.items() if town.get(k[:3] + "|" + k.split("|")[1]) != v[0]}
(ROOT / "static" / "data" / "town_muni.json").write_text(json.dumps({"t": town, "p": pcx}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(town), "postal-area towns;", len(pcx), "postal-code exceptions")
