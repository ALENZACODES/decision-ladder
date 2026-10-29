"""Pack all ~16M National Address Register addresses into static files for no-server autocomplete.

static/data/addr/packs.json          FSA -> pack id
static/data/addr/p<id>.json          {FSA: [[street display, city idx, "LDU:civ civ u/civ;LDU:..."], ...], "_c": [cities]}
static/data/addr/idx_<L>.json        street key "CORE|DIR" -> [display name, [FSA, ...]]   (one per postal letter)
Segments: "LDU@DAUID@lat,lon:civics" (neighbourhood block of that postal code). Civic tokens: "120" or "406/3470" (unit 406 at 3470). Packs target ~1.2 MB so a search loads little.
"""
import json, pathlib, sqlite3, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import street_core, street_dir, split_nar_civic   # noqa: E402

OUT = ROOT / "static" / "data" / "addr"; OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.json"):
    f.unlink()
db = sqlite3.connect(ROOT / "data" / "addresses.db")
TARGET = 1_200_000

fsas = [r[0] for r in db.execute("SELECT DISTINCT substr(replace(postal,' ',''),1,3) FROM addr WHERE length(replace(postal,' ',''))=6 ORDER BY 1")]
print(len(fsas), "postal areas")
packs, idx = {}, defaultdict(dict)
cur, cur_size, pid = {}, 0, 0
cities = []; city_id = {}


def flush():
    global cur, cur_size, pid, cities, city_id
    if not cur:
        return
    cur["_c"] = cities
    (OUT / f"p{pid}.json").write_text(json.dumps(cur, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    pid += 1; cur, cur_size, cities, city_id = {}, 0, [], {}


total = 0
for n, fsa in enumerate(fsas):
    rows = db.execute("""SELECT civic, street, city, substr(replace(postal,' ',''),4,3), da, lat, lon, csd FROM addr
                         WHERE substr(replace(postal,' ',''),1,3)=?""", (fsa,)).fetchall()
    streets = defaultdict(lambda: defaultdict(list))   # (street, city) -> (ldu, municipality) -> civics
    ldu_da = defaultdict(lambda: defaultdict(int))      # full postal code -> its most common neighbourhood block
    ldu_ll = defaultdict(lambda: [0.0, 0.0, 0])       # postal code centre, for street-view links
    # a postal code that straddles a municipal line (town inside a county, reserve) is split by municipality, so each
    # segment's neighbourhood block lies inside the address's own municipality (blocks never cross municipal lines)
    for civic, street, city, ldu, da, lat, lon, csd in rows:
        g = (ldu, csd or "")
        if da:
            ldu_da[g][da] += 1
        if lat is not None:
            c = ldu_ll[g]; c[0] += lat; c[1] += lon; c[2] += 1
        u, c = split_nar_civic(civic)
        streets[(street, city)][g].append(f"{u}/{c}" if u else c)
    out = []
    for (street, city), by_ldu in streets.items():
        if city not in city_id:
            city_id[city] = len(cities); cities.append(city)
        def sortkey(t):
            c = t.split("/")[-1]; d = "".join(ch for ch in c if ch.isdigit())
            return (int(d) if d else 0, t)
        def tag(g):
            d = ldu_da.get(g)
            c = ldu_ll.get(g)
            ll = f"@{c[0]/c[2]:.5f},{c[1]/c[2]:.5f}" if c and c[2] else "@"
            return f"{g[0]}@{max(d, key=d.get) if d else ''}{ll}"
        data = ";".join(f"{tag(g)}:" + " ".join(sorted(set(v), key=sortkey)) for g, v in sorted(by_ldu.items()))
        out.append([street, city_id[city], data])
        k = f"{street_core(street)}|{street_dir(street)}"
        ent = idx[fsa[0]].setdefault(k, [street, []])
        if fsa not in ent[1]:
            ent[1].append(fsa)
    cur[fsa] = out; packs[fsa] = pid; total += len(rows)
    cur_size += sum(len(s[0]) + len(s[2]) + 8 for s in out)
    if cur_size >= TARGET:
        flush()
    if n % 200 == 0:
        print(n, fsa, total, "pack", pid, flush=True)
flush()
(OUT / "packs.json").write_text(json.dumps(packs, separators=(",", ":")), encoding="utf-8")
for L, d in idx.items():
    (OUT / f"idx_{L}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
sizes = sorted((f.stat().st_size, f.name) for f in OUT.glob("*.json"))
print("addresses", total, "packs", pid, "files", len(sizes), "total MB", round(sum(s for s, _ in sizes) / 1e6, 1),
      "largest", sizes[-3:])
# neighbourhood block -> municipality (exact: Census blocks nest inside municipalities)
dc = {}
for da, csd, n in db.execute("SELECT da, csd, count(*) FROM addr WHERE da IS NOT NULL AND csd!='' GROUP BY 1,2"):
    if da not in dc or n > dc[da][1]:
        dc[da] = (csd, n)
names = sorted({v[0] for v in dc.values()}); ix = {n: i for i, n in enumerate(names)}
(ROOT / "static" / "data" / "da_muni.json").write_text(json.dumps({"n": names, "d": {k: ix[v[0]] for k, v in dc.items()}}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(dc), "blocks -> municipality")
