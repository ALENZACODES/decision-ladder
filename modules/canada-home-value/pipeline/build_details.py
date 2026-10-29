"""Merge legal descriptions and assessment history into compact per-postal-area detail files.

static/data/detail/<prefix>.json   {FSA: {"UNIT|CIVIC|CORE|DIR": [legal or "", "YY/STEP:v,v,v"]}}
  history values are thousands of dollars in base 36, starting at roll year 20YY, every STEP years (missing years = "").
static/data/detail/index.json      {prefix: [FSA, ...]}; prefixes are 2 or 3 postal characters, files stay under ~10 MB.
  --step=1 keeps every year (own site); default --step=2 fits the claude.ai page's 256 MB limit.
"""
import json, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "static" / "data"
OUT = pathlib.Path(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), str(D / "detail"))); OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.json"):
    f.unlink()
STEP = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--step=")), 3)
b36 = lambda n: "0" if n == 0 else ("" if n < 0 else (b36(n // 36).lstrip("0") + "0123456789abcdefghijklmnopqrstuvwxyz"[n % 36]))

det = defaultdict(lambda: defaultdict(lambda: ["", "", ""]))
for f in (D / "legal").glob("*.json"):
    if f.name == "index.json":
        continue
    for fsa, d in json.loads(f.read_text(encoding="utf-8")).items():
        for k, v in d.items():
            det[fsa][k][0] = v.replace("Plan ", "Pl ").replace(", Block ", " Blk ").replace(", Lot ", " Lot ")
for f in (D / "history").glob("*.json"):
    if f.name == "index.json":
        continue
    for fsa, d in json.loads(f.read_text(encoding="utf-8")).items():
        for k, s in d.items():
            yv = {int(y): int(v) for y, v in (x.split(":") for x in s.split())}
            last = max(yv); start = min(y for y in yv if (last - y) % STEP == 0)
            years = list(range(start, last + 1, STEP))
            if sum(y in yv for y in years) >= 2:
                det[fsa][k][1] = f"{start % 100}/{STEP}:" + ",".join(b36(yv[y]) if y in yv else "" for y in years)

for f in (D / "zoning").glob("*.json"):            # zoning code as the third field
    if f.name == "index.json":
        continue
    for fsa, d in json.loads(f.read_text(encoding="utf-8")).items():
        for k, z in d.items():
            det[fsa][k][2] = z
for fsa in det:                                      # drop empty trailing fields to save space
    for k, v in det[fsa].items():
        while v and v[-1] == "":
            v.pop()
groups = defaultdict(list)
for fsa in det:
    groups[fsa[:2]].append(fsa)
index = {}
for pre, fsas in groups.items():
    blob = {f: {k: v for k, v in det[f].items()} for f in fsas}
    s = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
    if len(s) < 10_000_000:
        (OUT / f"{pre}.json").write_text(s, encoding="utf-8"); index[pre] = sorted(fsas)
    else:                                   # big prefix: one file per postal area
        for f in fsas:
            (OUT / f"{f}.json").write_text(json.dumps({f: blob[f]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"); index[f] = [f]
(OUT / "index.json").write_text(json.dumps(index, separators=(",", ":")))
sizes = [p.stat().st_size for p in OUT.glob("*.json")]
print(sum(len(v) for v in det.values()), "addresses;", len(sizes), "files;", round(sum(sizes) / 1e6, 1), "MB; largest", round(max(sizes) / 1e6, 1), "MB; step", STEP)
