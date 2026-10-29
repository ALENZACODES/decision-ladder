"""Combine the value backtest, address coverage and address round-trip results into data/backtest.json."""
import json, glob, re, collections, os
B = os.environ.get("BHV_BUILD", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # folder holding build/ and data/
out = json.load(open(f"{B}/build/backtest_values.json"))
out["coverage"] = json.load(open(f"{B}/build/coverage.json"))
PROV = {"A":"NL","B":"NS","C":"PE","E":"NB","G":"QC","H":"QC","J":"QC","K":"ON","L":"ON","M":"ON","N":"ON","P":"ON","R":"MB","S":"SK","T":"AB","V":"BC","X":"NT","Y":"YT"}
def prov(f): return "NU" if re.match(r"X0[ABC]", f) else PROV[f[0]]
def summarise(files):
    tot = collections.Counter(); bp = collections.defaultdict(collections.Counter)
    for fn in files:
        for line in open(fn):
            try: r = json.loads(line)
            except Exception: continue
            if "e" in r: k = "ask_missing"
            elif r["auto"] == 1: k = "correct"
            elif r["auto"] == 0: k = "wrong"
            elif r["inList"] == 1: k = "ask_listed"
            else: k = "ask_missing"
            p = prov(r["fsa"]); tot[k] += 1; tot["n"] += 1; bp[p][k] += 1; bp[p]["n"] += 1
    return tot, bp
import sys
NEW = sys.argv[1] if len(sys.argv) > 1 else "rt_new_*.jsonl"; OLD = sys.argv[2] if len(sys.argv) > 2 else "rt_old_*.jsonl"
new_files = sorted(glob.glob(f"{B}/tests/out/{NEW}"))
tot, bp = summarise(new_files)
if tot["n"]:
    L = {k: tot[k] for k in ("n", "correct", "wrong", "ask_listed", "ask_missing")}
    L["by_prov"] = {p: {k: c[k] for k in ("n", "correct", "wrong", "ask_listed", "ask_missing")} for p, c in bp.items()}
    old_files = sorted(glob.glob(f"{B}/tests/out/{OLD}"))
    if old_files:
        ot, _ = summarise(old_files)
        L["before"] = {"n": ot["n"], "correct": ot["correct"], "wrong": ot["wrong"]}
    out["lookup"] = L
json.dump(out, open(f"{B}/data/backtest.json", "w"), separators=(",", ":"))
print("backtest.json", os.path.getsize(f"{B}/data/backtest.json"), "bytes; lookup", out.get("lookup", {}).get("n"), {k: out.get("lookup", {}).get(k) for k in ("correct", "wrong", "ask_listed", "ask_missing")}, "before", out.get("lookup", {}).get("before"))
