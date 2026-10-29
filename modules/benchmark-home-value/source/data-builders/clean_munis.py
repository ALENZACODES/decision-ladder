"""Drop stray postal areas from municipality lists.

A few register addresses carry the wrong municipality code (a Manitoulin Island P0P address
coded to Toronto, say), so Toronto's postal list held P0P, L3R and L4L, and a search "in
Toronto" could return a home on Manitoulin Island or in Markham. Each address's 2021 Census
block (dissemination area) names its real municipality, so count every municipality's
addresses per postal area by block, and drop a postal area from a municipality only when
none of that postal area's blocks belong to it."""
import json, glob, re, sys, collections, unicodedata
D = sys.argv[1] if len(sys.argv) > 1 else "data"
munis = json.load(open(f"{D}/munis.json"))
def plain(s):
    s = unicodedata.normalize("NFKD", str(s or "")); s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"\(.*?\)", " ", s); s = re.sub(r"[^A-Z0-9 ]", " ", s); return re.sub(r"\s+", " ", s).strip()
da = {}
for f in glob.glob(f"{D}/da_*.json"): da.update(json.load(open(f)))
cnt = collections.Counter(); fsa_tot = collections.Counter(); fsa_da = collections.Counter()
for f in glob.glob(f"{D}/addr/p[0-9]*.json"):
    pk = json.load(open(f))
    for fsa, rows in pk.items():
        if fsa == "_c": continue
        for street, ci, data in rows:
            for seg in data.split(";"):
                tag, civs = seg.split(":", 1); parts = tag.split("@"); n = len([t for t in civs.split(" ") if t])
                fsa_tot[fsa] += n
                d = da.get(parts[1]) if len(parts) > 1 and parts[1] else None
                if d: cnt[(d[1], fsa)] += n; fsa_da[fsa] += n
removed = []; seen_m = set(k[0] for k in cnt)
for m in munis:
    mk = f"{m['prov']}|{plain(m['name'])}"
    if mk not in seen_m or len(m["fsa"]) < 2: continue          # no blocks name this municipality: leave it alone
    keep = [f for f in m["fsa"] if cnt.get((mk, f), 0) > 0 or fsa_da.get(f, 0) < 0.5 * fsa_tot.get(f, 1)]
    if not keep: continue
    gone = [f for f in m["fsa"] if f not in keep]
    if gone: removed.append((m["name"], m["prov"], gone)); m["fsa"] = keep
json.dump(munis, open(f"{D}/munis.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(removed), "municipalities lost stray postal areas")
for r in removed:
    if r[0] in ("Toronto", "Vancouver", "Ottawa", "Montréal", "Calgary", "Edmonton", "Winnipeg", "Mississauga"): print(" ", r)
