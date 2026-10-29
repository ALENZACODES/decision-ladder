"""Download current-year residential property assessments from Calgary and Edmonton open data (Socrata)."""
import json, pathlib, time
import pandas as pd, requests

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
PAGE = 50000


def pull(base, select, where, name):
    rows, off = [], 0
    while True:
        params = {"$select": select, "$where": where, "$limit": PAGE, "$offset": off, "$order": ":id"}
        for attempt in range(5):
            try:
                r = requests.get(base, params=params, timeout=120); r.raise_for_status(); break
            except Exception as e:
                print(name, "retry", attempt, e); time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"{name}: gave up at offset {off}")
        batch = r.json()
        rows += batch; off += PAGE
        print(name, len(rows), flush=True)
        if len(batch) < PAGE:
            break
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / f"{name}.parquet")
    return df


def centroid(mp):
    try:
        ring = mp["coordinates"][0][0]
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    except Exception:
        return None, None


if __name__ == "__main__":
    cal = pull("https://data.calgary.ca/resource/4bsw-nn7w.json",
               "roll_number,address,assessed_value,comm_name,year_of_construction,land_use_designation,property_type,land_size_sf,sub_property_use,multipolygon",
               "assessment_class='RE'", "calgary")
    if "multipolygon" in cal:
        xy = cal["multipolygon"].map(centroid)
        cal["lon"] = [a for a, _ in xy]; cal["lat"] = [b for _, b in xy]
        cal.drop(columns="multipolygon").to_parquet(OUT / "calgary.parquet")
    pull("https://data.edmonton.ca/resource/q7d6-ambg.json",
         "account_number,suite,house_number,street_name,neighbourhood,assessed_value,garage,latitude,longitude",
         "tax_class='Residential'", "edmonton")
