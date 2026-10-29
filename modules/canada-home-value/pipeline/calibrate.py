"""Recalibrate built-in benchmark prices to published Sep 2026 MLS HPI composite benchmarks and report the error.

Sources: TRREB Market Watch Sep 2026 (MLS HPI table), CREB Sep 2026 release, GVR Sep 2026, OREB Sep 2026.
"""
import pathlib, re, sys

PUBLISHED = {  # composite benchmark, Sep 2026
 "Toronto": 908200, "Mississauga": 867500, "Brampton": 829200, "Oakville": 1128800, "Burlington": 840600,
 "Milton": 861600, "Caledon": 1059900, "Vaughan": 1119400, "Markham": 1052500, "Richmond Hill": 1157700,
 "Aurora": 1106800, "Newmarket": 959500, "Ajax": 846900, "Clarington": 738900, "Oshawa": 699700,
 "Pickering": 866800, "Whitby": 897200, "Calgary": 566700, "Airdrie": 505800, "Okotoks": 606800,
 "Chestermere": 690200, "Vancouver": 1075900, "Ottawa": 623500,
}
# Type ratios to composite, from the same tables (TRREB GTA avg, CREB, GVR)
TYPES = {
 "GTA": "{detached:1.42,semi:1.05,town:0.8,condo:0.58}",
 "CGY": "{detached:1.3,semi:1.2,town:0.73,condo:0.51}",
 "VAN": "{detached:1.66,semi:1.15,town:0.95,condo:0.63}",
}

ROOT = pathlib.Path(__file__).resolve().parent.parent
row = re.compile(r'\["([^"]+)","(\w\w)","(\w+)",(\d+),')

for f in [ROOT / "web" / "index.html", ROOT / "home-value-estimator.html"]:
    if not f.exists():
        continue
    s = f.read_text(encoding="utf-8")
    old = {m.group(1): (m.group(3), int(m.group(4))) for m in row.finditer(s)}
    # region-wide correction for municipalities without a published figure
    ratios = {}
    for name, pub in PUBLISHED.items():
        if name in old:
            ratios.setdefault(old[name][0], []).append(pub / old[name][1])
    reg_ratio = {r: sum(v) / len(v) for r, v in ratios.items()}
    if f.name == "index.html":
        print(f"{'Municipality':<16}{'Before':>12}{'Published':>12}{'Error':>8}")
        errs = []
        for name, pub in PUBLISHED.items():
            if name in old:
                e = old[name][1] / pub - 1; errs.append(abs(e))
                print(f"{name:<16}{old[name][1]:>12,}{pub:>12,}{e:>+8.1%}")
        print(f"Median abs error before: {sorted(errs)[len(errs)//2]:.1%}")
        print("Region corrections for unpublished municipalities:", {k: round(v, 3) for k, v in reg_ratio.items()})

    def fix(m):
        name, prov, reg, bench = m.group(1), m.group(2), m.group(3), int(m.group(4))
        new = PUBLISHED.get(name) or round(bench * reg_ratio.get(reg, 1) / 1000) * 1000
        return f'["{name}","{prov}","{reg}",{new},'
    s = row.sub(fix, s)
    for reg, t in TYPES.items():
        s = re.sub(rf"{reg}:\{{detached:[^}}]+\}}", f"{reg}:{t}", s, count=1)
    f.write_text(s, encoding="utf-8")
print("updated")
