"""Assessment history where cities publish past rolls.

Calgary 2014+ (4ur7-wsgc), Edmonton 2014+ (qi6a-xuwt), Vancouver 2020-2025 tax reports, Township of Langley 2020-2025,
Victoria 2024. Saved to data/raw/hist_*.parquet.
"""
import io, pathlib, sys
import pandas as pd, requests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_assessments import OUT, pull
from fetch_arcgis import pull as arc

FIRST = "2014"
if __name__ == "__main__":
    which = sys.argv[1:] or ["calgary", "edmonton", "vancouver", "langley", "victoria"]
    if "calgary" in which:
        pull("https://data.calgary.ca/resource/4ur7-wsgc.json", "address,roll_year,assessed_value",
             f"roll_year >= '{FIRST}' AND roll_year < '2026'", "hist_calgary")
    if "edmonton" in which:
        pull("https://data.edmonton.ca/resource/qi6a-xuwt.json", "account_number,assessment_year,assessed_value,house_number,street_name",
             f"assessment_year >= '{FIRST}' AND assessment_year < '2026'", "hist_edmonton")
    if "vancouver" in which:
        parts = []
        for y in range(2020, 2026):
            url = ("https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/property-tax-report/exports/csv"
                   f"?where=report_year%3D%22{y}%22&select=from_civic_number,to_civic_number,street_name,legal_type,current_land_value,current_improvement_value,tax_assessment_year&delimiter=%2C")
            r = requests.get(url, timeout=600); r.raise_for_status()
            d = pd.read_csv(io.BytesIO(r.content), dtype=str); d["year"] = str(y); parts.append(d); print("vancouver", y, len(d), flush=True)
        pd.concat(parts).to_parquet(OUT / "hist_vancouver.parquet")
    if "langley" in which:
        layers = {2025: "Assessment_2025/FeatureServer/0", 2024: "Assessments_2024/FeatureServer/0", 2023: "Assessments_2023/FeatureServer/4",
                  2022: "Assessments_2022/FeatureServer/4", 2021: "Assessments_2021/FeatureServer/4", 2020: "Assessments_2020/FeatureServer/0"}
        parts = []
        for y, lay in layers.items():
            try:
                d = arc(f"langley_{y}", "https://services5.arcgis.com/frpHL0Fv8koQRVWY/arcgis/rest/services/" + lay)
                d["year"] = str(y); parts.append(d)
            except Exception as e:
                print("langley", y, "skipped:", e)
        pd.concat(parts, ignore_index=True).astype(str).to_parquet(OUT / "hist_langley.parquet")
    if "victoria" in which:
        d = arc("victoria_2024", "https://services.arcgis.com/EHSKalEvBxdO9ljW/arcgis/rest/services/Property_Assessment_Report_2024/FeatureServer/0")
        d["year"] = "2024"; d.astype(str).to_parquet(OUT / "hist_victoria.parquet")
