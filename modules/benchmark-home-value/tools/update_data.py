"""Refresh the live inputs for Benchmark Home Value on this computer (all free, no keys):
  - Bank of Canada Valet API: policy rate, prime rate, posted 5-year mortgage rate  -> data/rates.json
  - Chart.js 4.5.1 (local copy, so charts draw even when the CDN is blocked)          -> vendor/chart.umd.min.js
  - data/updated.json "checked" date (shown as the page's Live tag)
Each step is independent: if one source fails, the files from the last good run are kept."""
import json, os, sys, urllib.request, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "BenchmarkHomeValue/1.0"}
def get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()
def write_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f: f.write(data)
    os.replace(tmp, path)
ok = 0
# 1) Bank of Canada rates (each series fetched separately; dates differ)
SERIES = {"policy": "V39079", "prime": "V80691311", "posted": "V80691335"}
rates, dates = {}, []
for key, code in SERIES.items():
    for url in (f"https://www.bankofcanada.ca/valet/observations/{code}/json?recent=1",
                f"https://www.banqueducanada.ca/valet/observations/{code}/json?recent=1"):
        try:
            obs = json.loads(get(url))["observations"][-1]
            rates[key] = float(obs[code]["v"]); dates.append(obs["d"]); break
        except Exception as e:
            last = e
    else:
        print(f"  ! Bank of Canada {key} rate: not reachable ({last}); keeping the saved value")
if rates:
    path = os.path.join(ROOT, "data", "rates.json")
    old = {}
    try: old = json.load(open(path, encoding="utf-8-sig"))
    except Exception: pass
    old.update(rates); old["d"] = max(dates); old["source"] = "Bank of Canada Valet API"
    write_atomic(path, json.dumps(old).encode()); ok += 1
    print("  + Bank of Canada:", ", ".join(f"{k} {v}%" for k, v in rates.items()), "as of", old["d"])
# 2) Chart.js local copy (cdnjs, then jsDelivr, then unpkg)
dest = os.path.join(ROOT, "vendor", "chart.umd.min.js"); os.makedirs(os.path.dirname(dest), exist_ok=True)
for url in ("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js",
            "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js",
            "https://unpkg.com/chart.js@4.5.1/dist/chart.umd.min.js"):
    try:
        js = get(url, 30)
        if len(js) > 100000 and b"Chart" in js[:5000]:
            write_atomic(dest, js); ok += 1; print("  + Chart library saved for offline use"); break
    except Exception as e:
        last = e
else:
    print("  ! Chart library: not reachable; charts will use the built-in renderer")
# 3) Toronto Police neighbourhood crime rates with boundaries (used when the live feed can't be reached)
TPS = "https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Neighbourhood_Crime_Rates_Open_Data/FeatureServer/0/query"
CATS = ["ASSAULT","BREAKENTER","AUTOTHEFT","ROBBERY","THEFTFROMMV","THEFTOVER","SHOOTING","HOMICIDE"]
def build_toronto(j):
    rows, geo = [], {}
    for f in j.get("features", []):
        a = f["attributes"]; years = sorted({int(k.rsplit("_",1)[1]) for k in a if k.startswith("ASSAULT_") and k.rsplit("_",1)[1].isdigit()})
        r = {"name": a["AREA_NAME"], "id": a["HOOD_ID"], "pop": a.get("POPULATION_" + str(years[-1])) or a.get("POPULATION_2025"), "c": {}, "rt": {}}
        for k in CATS:
            r["c"][k] = [a.get(f"{k}_{y}") or 0 for y in years]; r["rt"][k] = [round(a.get(f"{k}_RATE_{y}") or 0, 1) for y in years]
        rows.append(r)
        g = f.get("geometry") or {}
        if g.get("rings"): geo[a["HOOD_ID"]] = [[[round(x, 5), round(y, 5)] for x, y in ring] for ring in g["rings"]]
    return rows, geo, years
try:
    j = json.loads(get(TPS + "?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&geometryPrecision=5&maxAllowableOffset=0.0001&f=json", 60))
    rows, geo, years = build_toronto(j)
    if len(rows) >= 100 and len(geo) >= 100:
        out = {"d": datetime.date.today().isoformat(), "years": years, "rows": rows, "geo": geo, "source": "Toronto Police Service Public Safety Data Portal"}
        write_atomic(os.path.join(ROOT, "data", "crime_toronto.json"), json.dumps(out, separators=(",", ":")).encode()); ok += 1
        print(f"  + Toronto Police neighbourhood crime: {len(rows)} neighbourhoods, {years[0]}-{years[-1]}")
    else:
        print("  ! Toronto Police data looked incomplete; keeping the saved copy")
except Exception as e:
    print("  ! Toronto Police data: not reachable; keeping the saved copy")
# 4) Live tag (only when something was actually refreshed)
if ok:
  try:
    up = os.path.join(ROOT, "data", "updated.json"); u = json.load(open(up, encoding="utf-8-sig"))
    now = datetime.datetime.now()
    u["date"] = now.strftime("%Y-%m-%d"); u["checked"] = now.strftime("%Y-%m-%dT%H:%M")
    write_atomic(up, json.dumps(u).encode())
  except Exception as e:
    print("  ! Couldn't update the Live date:", e)
print("\n  Done." if ok else "\n  Nothing could be updated (offline?). The app still works with the data it has.")
