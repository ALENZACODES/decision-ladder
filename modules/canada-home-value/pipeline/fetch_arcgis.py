"""Download ArcGIS FeatureServer assessment layers (Victoria, Langley Township, Strathcona County)."""
import pathlib, sys, time
import pandas as pd, requests

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
LAYERS = {
    "victoria": "https://services.arcgis.com/EHSKalEvBxdO9ljW/arcgis/rest/services/Property_Assessment_Report_2026/FeatureServer/0",
    "langley_twp": "https://services5.arcgis.com/frpHL0Fv8koQRVWY/arcgis/rest/services/Assessments_2026/FeatureServer/0",
    "strathcona": "https://services.arcgis.com/B7ZrK1Hv4P1dsm9R/arcgis/rest/services/Property_Tax_Assessment_2024/FeatureServer/0",
}


def pull(name, url, page=2000):
    rows, off = [], 0
    while True:
        params = {"where": "1=1", "outFields": "*", "f": "json", "returnGeometry": "true", "outSR": "4326",
                  "resultOffset": off, "resultRecordCount": page, "orderByFields": "ObjectId" if name.startswith("victoria") else "OBJECTID"}
        for a in range(5):
            try:
                d = requests.get(url + "/query", params=params, timeout=120).json(); break
            except Exception as e:
                print(name, "retry", e); time.sleep(5 * (a + 1))
        feats = d.get("features", [])
        for f in feats:
            r = dict(f["attributes"]); g = f.get("geometry") or {}
            if "x" in g:
                r["_lon"], r["_lat"] = g["x"], g["y"]
            elif "rings" in g:
                ring = g["rings"][0]; r["_lon"] = sum(p[0] for p in ring) / len(ring); r["_lat"] = sum(p[1] for p in ring) / len(ring)
            rows.append(r)
        off += len(feats); print(name, off, flush=True)
        if not feats or not d.get("exceededTransferLimit", len(feats) == page):
            break
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / f"{name}.parquet"); return df


if __name__ == "__main__":
    for n in sys.argv[1:] or LAYERS:
        pull(n, LAYERS[n])
