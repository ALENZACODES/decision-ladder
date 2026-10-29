"""Per-address legal descriptions for the no-server page, from cities that publish them.

  Calgary (short legal: plan;block;lot), Edmonton (legal description), Vancouver (lot/block/plan/district lot + PID),
  Township of Langley (legal description + PID), Victoria (PID).
Output: static/data/legal/<first 2 postal chars>.json  {FSA: {"UNIT|CIVIC|CORE|DIR": "legal text"}}
        static/data/legal/index.json  list of available 2-character prefixes
"""
import json, pathlib, re, sqlite3, sys
from collections import defaultdict
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from addrkey import key3, split_nar_civic        # noqa: E402

RAW = ROOT / "data" / "raw"; OUT = ROOT / "static" / "data" / "legal"; OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.json"):
    f.unlink()
num = lambda s: pd.to_numeric(s, errors="coerce")
rows = []   # (prov, key, legal)

if (RAW / "calgary_legal.parquet").exists():
    c = pd.read_parquet(RAW / "calgary_legal.parquet")
    parts = c["address"].fillna("").str.extract(r"^(?:(?P<u>\w+)\s+(?=\d+\w?\s))?(?P<c>\d+\w?)\s+(?P<s>.+)$")
    for u, cv, st, lg in zip(parts.u.fillna(""), parts.c.fillna(""), parts.s.fillna(""), c.short_legal.fillna("")):
        if lg:
            p = lg.split(";")
            text = "Plan " + p[0] + (f", Block {p[1]}" if len(p) > 1 and p[1] else "") + (f", Lot {p[2]}" if len(p) > 2 and p[2] else "")
            rows.append(("AB", key3(u, cv, st), text))
if (RAW / "edmonton_legal.parquet").exists():
    e = pd.read_parquet(RAW / "edmonton_legal.parquet")
    base = pd.read_parquet(RAW / "edmonton.parquet")[["account_number", "suite"]] if "suite" in pd.read_parquet(RAW / "edmonton.parquet").columns else None
    if base is not None:
        e = e.merge(base, on="account_number", how="left")
    for u, h, st, lg in zip(e.get("suite", pd.Series("", index=e.index)).fillna(""), e.house_number.fillna(""), e.street_name.fillna(""),
                            e.legal_description.fillna("")):
        if lg:
            rows.append(("AB", key3(str(u).strip(), h, st), re.sub(r"\s+", " ", lg).strip()))
v = pd.read_parquet(RAW / "vancouver.parquet")
for u, cv, st, lot, blk, plan, dl, pid, lt in zip(v.from_civic_number.fillna(""), v.to_civic_number.fillna(""), v.street_name.fillna(""),
                                                  v.lot.fillna(""), v.block.fillna(""), v.plan.fillna(""), v.district_lot.fillna(""),
                                                  v.pid.fillna(""), v.legal_type.fillna("")):
    bits = [f"Lot {lot}" if lot else "", f"Block {blk}" if blk else "", f"Plan {plan}" if plan else "", f"District Lot {dl}" if dl else "",
            f"PID {pid}" if pid else ""]
    text = ", ".join(b for b in bits if b)
    if text:
        rows.append(("BC", key3(u if lt == "STRATA" else "", cv, st), text))
l = pd.read_parquet(RAW / "langley_twp.parquet")
for u, h, st, lg, pid in zip(l.Unit.fillna(""), l.House.fillna("").astype(str), l.Street.fillna(""), l.Legal_Description.fillna(""), l.PID.fillna("")):
    text = ", ".join(x for x in [str(lg).strip(), f"PID {pid}" if pid else ""] if x)
    if text:
        rows.append(("BC", key3(str(u), h, st), text))
vi = pd.read_parquet(RAW / "victoria.parquet")
for u, h, st, pid, lt in zip(vi.UNIT.fillna(""), num(vi.HOUSE).astype("Int64").astype(str).replace("<NA>", ""), vi.STREET.fillna(""),
                             vi.PID.fillna(""), vi.LEGAL_TYPE.fillna("")):
    if pid:
        rows.append(("BC", key3(str(u) if lt == "STRATA" else "", h, st), f"PID {pid}"))
print(len(rows), "legal descriptions")

# postal area of each record, via the National Address Register
db = sqlite3.connect(ROOT / "data" / "addresses.db")
post = {}
for prov in ("AB", "BC"):
    for civic, street, pc in db.execute("SELECT civic, street, replace(postal,' ','') FROM addr WHERE prov=?", (prov,)):
        if pc:
            u, c = split_nar_civic(civic)
            post.setdefault((prov, key3(u, c, street)), pc[:3])
out = defaultdict(lambda: defaultdict(dict)); hit = 0
for prov, k, text in rows:
    f = post.get((prov, k))
    if f:
        out[f[:2]][f][k] = text; hit += 1
for pre, d in out.items():
    (OUT / f"{pre}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(OUT / "index.json").write_text(json.dumps(sorted(out)))
sizes = sum(p.stat().st_size for p in OUT.glob("*.json"))
print(hit, "matched to addresses;", len(out), "files;", round(sizes / 1e6, 1), "MB")
