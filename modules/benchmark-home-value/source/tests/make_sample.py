"""One random address from every street in the National Address Register packs (seeded), as a person would type it."""
import os
APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the app folder
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUTDIR, exist_ok=True)
import json, glob, re, random, sys
random.seed(7)
D = os.path.join(APP, "data")
out = []
def title(s): return re.sub(r"(^|[\s\-'])(\w)", lambda m: m.group(1) + m.group(2).upper(), s.lower())
for f in sorted(glob.glob(f"{D}/addr/p[0-9]*.json"), key=lambda x: int(re.findall(r"p(\d+)", x)[0])):
    pk = json.load(open(f)); C = pk.get("_c", [])
    for fsa, rows in pk.items():
        if fsa == "_c": continue
        for street, ci, data in rows:
            addrs = []
            for seg in data.split(";"):
                tag, civs = seg.split(":", 1); ldu = tag.split("@")[0]
                addrs += [(t, ldu) for t in civs.split(" ") if t]
            addrs = [a for a in addrs if a[0].count("/") <= 1] or addrs
            t, ldu = random.choice(addrs)
            if t.count("/") > 1: continue
            u, n = t.split("/") if "/" in t else ("", t)
            city = C[ci]
            q = f"{u + '-' if u else ''}{n} {title(street)}, {title(city)}"
            out.append([q, fsa, street, n, u, city, ldu])
random.shuffle(out)
json.dump(out, open(OUTDIR + "/sample_all.json", "w"))
print(len(out), out[:3])
