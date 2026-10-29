"""Schools near every address (free, open data).

static/data/schools_<PROV>.json   [[name, lat, lon, level, kind, board, grades, history], ...]
  level   E elementary · S secondary · B both
  history (Ontario only) {"2024-25": [score, rank], ...}  score = share of students at the provincial standard
          (EQAO: Grade 3 and 6 reading, writing, math for elementary; Grade 9 math and Grade 10 literacy for secondary),
          rank = percent of Ontario schools at the same level it beats that year (100 = top).
Sources:
  Ontario   data.ontario.ca "School information and student demographics", every school year published (new years are
            picked up automatically from the catalogue on each run)
  Others    Statistics Canada Open Database of Educational Facilities (ODEF v2.1)
"""
import io, json, pathlib, re, zipfile
import pandas as pd, requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "schools"; RAW.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "static" / "data"
CKAN = "https://data.ontario.ca/api/3/action/package_show?id=school-information-and-student-demographics"
ODEF = "https://www150.statcan.gc.ca/n1/en/pub/37-26-0001/2022001/ODEF_v2.1.zip"
ELEM = ["Grade 3 Students Achieving the Provincial Standard in Reading", "Grade 3 Students Achieving the Provincial Standard in Writing",
        "Grade 3 Students Achieving the Provincial Standard in Mathematics", "Grade 6 Students Achieving the Provincial Standard in Reading",
        "Grade 6 Students Achieving the Provincial Standard in Writing", "Grade 6 Students Achieving the Provincial Standard in Mathematics"]
SEC = ["Grade 9 Students Achieving the Provincial Standard in Mathematics", "Students That Passed the Grade 10 OSSLT on Their First Attempt"]


def ontario_years():
    """Download every English school-information table in the catalogue; returns {"2024-25": DataFrame}."""
    res = requests.get(CKAN, timeout=60).json()["result"]["resources"]
    out = {}
    for r in res:
        u = r["url"]
        m = re.search(r"(20\d\d)_?(?:20)?(\d\d)", u.rsplit("/", 1)[-1])
        if not m or not u.endswith(".xlsx") or re.search(r"_fr", u):
            continue
        y = f"{m.group(1)}-{m.group(2)[-2:]}"
        f = RAW / f"on_{y}.xlsx"
        if not f.exists():
            f.write_bytes(requests.get(u, timeout=300).content)
        out[y] = pd.read_excel(f, dtype=str)
    return dict(sorted(out.items()))


def pct(s):
    t = str(s).strip()
    try:
        v = float(t.rstrip("%"))
    except ValueError:
        return None
    return v * 100 if not t.endswith("%") and v <= 1 else v   # 2023-24 stores 0.59 instead of 59%


def ontario():
    years = ontario_years()
    hist = {}
    for y, d in years.items():
        cols = {c: c.replace("Percentage of ", "") for c in d.columns}
        d = d.rename(columns=cols)
        for level, keys in (("E", ELEM), ("S", SEC)):
            have = [k for k in keys if k in d.columns]
            sc = d[have].apply(lambda col: col.map(pct)).mean(axis=1, skipna=True)
            ok = sc.notna() & d["School Level"].str.contains("Elementary" if level == "E" else "Secondary", na=False)
            rank = sc[ok].rank(pct=True) * 100
            if y in ("2019-20", "2020-21"):
                continue   # EQAO paused during COVID; these tables repeat earlier results
            for i in rank.index:
                if not (sc[i] == sc[i] and rank[i] == rank[i]):
                    continue
                hist.setdefault(d.at[i, "School Number"], {}).setdefault(level, {})[y] = [round(sc[i]), round(rank[i])]
    last = list(years.values())[-1]
    rows = []
    for _, r in last.iterrows():
        try:
            la, lo = float(r["Latitude"]), float(r["Longitude"])
            assert la == la and lo == lo   # not NaN
        except (TypeError, ValueError, AssertionError):
            continue
        lvl = {"Elementary": "E", "Secondary": "S"}.get(r["School Level"], "B")
        h = hist.get(r["School Number"], {})
        h = h.get(lvl) or h.get("E") or h.get("S") or {}
        kind = ("Catholic " if "Catholic" in str(r["Board Type"]) or r["School Type"] == "Catholic" else "") + ("French" if r["School Language"] == "French" else "")
        kind = kind.strip() or ("Private" if r["School Type"] == "Private" else "Public")
        txt = lambda x: x if isinstance(x, str) else ""
        rows.append([txt(r["School Name"]), round(la, 5), round(lo, 5), lvl, kind, txt(r["Board Name"]), txt(r["Grade Range"]), h])
    return rows


def others():
    z = RAW / "odef.zip"
    if not z.exists():
        z.write_bytes(requests.get(ODEF, timeout=300).content)
    with zipfile.ZipFile(z) as zf:
        name = next(n for n in zf.namelist() if n.endswith("ODEF_v2_1.csv"))
        d = pd.read_csv(io.BytesIO(zf.read(name)), encoding="latin-1", dtype=str)
    by = {}
    for _, r in d.iterrows():
        if r["Prov_Terr"] == "ON":
            continue
        try:
            la, lo = float(r["Latitude"]), float(r["Longitude"])
            assert la == la and lo == lo   # not NaN
        except (TypeError, ValueError, AssertionError):
            continue
        e, m, s = (str(r.get(k)) == "1" for k in ("ISCED1", "ISCED2", "ISCED3"))
        lvl = "B" if (e and s) else "S" if (s or (m and not e)) else "E"
        kind = r["Facility_Type"] if isinstance(r["Facility_Type"], str) and r["Facility_Type"] not in ("..", "") else "Public"
        by.setdefault(r["Prov_Terr"], []).append([r["Facility_Name"], round(la, 5), round(lo, 5), lvl, kind, r["Authority_Name"] if isinstance(r["Authority_Name"], str) else "", "", {}])
    return by


if __name__ == "__main__":
    allp = others()
    allp["ON"] = ontario()
    n = 0
    for prov, rows in allp.items():
        (OUT / f"schools_{prov}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8"); n += len(rows)
    size = sum((OUT / f"schools_{p}.json").stat().st_size for p in allp) / 1e6
    print(n, "schools;", len(allp), "provinces;", round(size, 2), "MB")
