"""Rent roll analysis: occupancy, WALT, lease rollover concentration and mark-to-market.

Each lease is a dict:

* ``tenant`` - name or unit number
* ``area`` - rentable square feet (optional; when every lease omits it, each unit weighs 1)
* ``rent`` - in-place annual base rent, dollars (0 for a vacant unit)
* ``market_rent`` - annual market rent for the same space, dollars (optional)
* ``expiry`` - lease expiry YYYY-MM-DD (omit for month-to-month / periodic tenancies)
* ``vacant`` - true for a vacant unit

WALT is the weighted average of years remaining to expiry, weighted by in-place rent (the lender's usual
view) and by area. Expired and month-to-month leases count as zero years remaining.
"""
from __future__ import annotations

from datetime import date

from .common import pct, r2

ROLLOVER_FLAG_PCT = 25.0  # assumption: a single year rolling over more than this share of rent is flagged


def _d(s) -> date:
    return date.fromisoformat(str(s)[:10])


def _years_left(expiry: date | None, as_of: date) -> float:
    if expiry is None or expiry <= as_of:
        return 0.0
    return (expiry - as_of).days / 365.25


def analyze(leases: list[dict], as_of: str, rollover_flag_pct: float = ROLLOVER_FLAG_PCT) -> dict:
    if not leases:
        raise ValueError("rent roll is empty")
    today = _d(as_of)
    use_area = any(float(l.get("area") or 0) > 0 for l in leases)
    rows, by_year = [], {}
    tot = {"area": 0.0, "occ_area": 0.0, "rent": 0.0, "market_occ": 0.0, "market_vac": 0.0, "units": 0, "vacant": 0,
           "walt_rent": 0.0, "walt_area": 0.0}
    for i, l in enumerate(leases):
        name = str(l.get("tenant") or f"unit {i + 1}")
        area = float(l.get("area") or 0) if use_area else 1.0
        if area < 0:
            raise ValueError(f"{name}: area must not be negative")
        vacant = bool(l.get("vacant")) or float(l.get("rent") or 0) == 0
        rent = 0.0 if vacant else float(l.get("rent") or 0)
        market = l.get("market_rent")
        market = None if market in (None, "") else float(market)
        expiry = _d(l["expiry"]) if l.get("expiry") and not vacant else None
        yrs = _years_left(expiry, today)
        tot["units"] += 1
        tot["area"] += area
        if vacant:
            tot["vacant"] += 1
            tot["market_vac"] += market or 0.0
            rows.append({"tenant": name, "status": "vacant", "area": area if use_area else None,
                         "market_rent": market, "mtm_gap": None})
            continue
        tot["occ_area"] += area
        tot["rent"] += rent
        tot["walt_rent"] += rent * yrs
        tot["walt_area"] += area * yrs
        bucket = "month-to-month / expired" if yrs == 0 else str(expiry.year)
        b = by_year.setdefault(bucket, {"rent": 0.0, "area": 0.0, "leases": 0})
        b["rent"] += rent
        b["area"] += area
        b["leases"] += 1
        gap = None
        if market is not None:
            tot["market_occ"] += market
            gap = market - rent
        rows.append({"tenant": name, "status": "occupied", "area": area if use_area else None, "rent": r2(rent),
                     "rent_psf": r2(rent / area) if use_area and area else None, "expiry": expiry and expiry.isoformat(),
                     "years_left": round(yrs, 2), "market_rent": market, "mtm_gap": None if gap is None else r2(gap),
                     "mtm_gap_pct": None if gap is None or not rent else pct(gap / rent)})

    rent, area = tot["rent"], tot["area"]
    rollover = []
    for k in sorted(by_year, key=lambda k: (k[0].isdigit(), k)):
        b = by_year[k]
        share = b["rent"] / rent * 100 if rent else 0.0
        rollover.append({"year": k, "leases": b["leases"], "rent": r2(b["rent"]), "pct_of_rent": round(share, 2),
                         "area": b["area"] if use_area else None, "flag": share > rollover_flag_pct})
    occupied = [r for r in rows if r["status"] == "occupied"]
    top = max(occupied, key=lambda r: r["rent"], default=None)
    priced = [r for r in occupied if r["mtm_gap"] is not None]
    in_place_priced = sum(r["rent"] for r in priced)
    gap_total = sum(r["mtm_gap"] for r in priced)
    flags = [f"{r['year']}: {r['pct_of_rent']}% of rent rolls over" for r in rollover if r["flag"]]
    if top and rent and top["rent"] / rent * 100 > rollover_flag_pct:
        flags.append(f"largest tenant {top['tenant']} pays {pct(top['rent'] / rent)}% of rent")
    return {
        "as_of": today.isoformat(),
        "weighting": "area (sf)" if use_area else "units",
        "units": tot["units"], "vacant_units": tot["vacant"],
        "physical_occupancy_pct": round(tot["occ_area"] / area * 100, 2) if area else 0.0,
        "economic_occupancy_pct": round(rent / (rent + tot["market_vac"]) * 100, 2) if rent + tot["market_vac"] else 0.0,
        "in_place_rent": r2(rent),
        "vacant_market_rent": r2(tot["market_vac"]),
        "gross_potential_rent": r2(rent + tot["market_vac"]),
        "walt_years_by_rent": round(tot["walt_rent"] / rent, 2) if rent else 0.0,
        "walt_years_by_area": round(tot["walt_area"] / tot["occ_area"], 2) if tot["occ_area"] else 0.0,
        "rollover": rollover,
        "largest_tenant": top and {"tenant": top["tenant"], "rent": top["rent"], "pct_of_rent": pct(top["rent"] / rent) if rent else 0.0},
        "mark_to_market": {"leases_priced": len(priced), "in_place": r2(in_place_priced), "market": r2(in_place_priced + gap_total),
                           "gap": r2(gap_total), "gap_pct": pct(gap_total / in_place_priced) if in_place_priced else None,
                           "below_market": sum(1 for r in priced if r["mtm_gap"] > 0),
                           "above_market": sum(1 for r in priced if r["mtm_gap"] < 0)},
        "leases": rows,
        "flags": flags,
        "assumptions": [f"rollover flag threshold {rollover_flag_pct:g}% of in-place rent (assumption, not a lender rule)",
                        "month-to-month and expired leases count as 0 years remaining",
                        "economic occupancy = in-place rent / (in-place rent + market rent of vacant units)"],
        "engine": "commercial.rentroll",
    }
