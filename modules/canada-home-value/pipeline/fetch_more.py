"""Download more open municipal property data: Winnipeg + Edmonton details (Socrata), Vancouver tax report, Montréal units."""
import io, pathlib, sys
import pandas as pd, requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_assessments import OUT, pull, centroid

if __name__ == "__main__":
    which = sys.argv[1:] or ["winnipeg", "edmonton_details", "vancouver", "montreal"]
    if "winnipeg" in which:
        w = pull("https://data.winnipeg.ca/resource/d4mq-wa44.json",
                 "roll_number,street_number,street_name,street_type,full_address,neighbourhood_area,total_living_area,building_type,"
                 "basement,basement_finish,year_built,rooms,air_conditioning,fire_place,attached_garage,detached_garage,pool,"
                 "property_use_code,assessed_land_area,zoning,total_assessed_value,assessment_date,geometry",
                 "property_class_1 like 'RESIDENTIAL%'", "winnipeg")
        xy = w["geometry"].map(centroid)
        w["lon"] = [a for a, _ in xy]; w["lat"] = [b for _, b in xy]
        w.drop(columns="geometry").to_parquet(OUT / "winnipeg.parquet")
    if "edmonton_details" in which:
        pull("https://data.edmonton.ca/resource/dkk9-cj3x.json",
             "account_number,house_number,street_name,zoning,lot_size,total_gross_area,year_built,garage,neighbourhood,latitude,longitude",
             "account_number IS NOT NULL", "edmonton_details")
    if "vancouver" in which:
        url = ("https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/property-tax-report/exports/csv"
               "?where=report_year%3D%222026%22&delimiter=%2C")
        r = requests.get(url, timeout=600); r.raise_for_status()
        v = pd.read_csv(io.BytesIO(r.content), dtype=str)
        v.to_parquet(OUT / "vancouver.parquet"); print("vancouver", len(v))
    if "montreal" in which:
        url = "https://donnees.montreal.ca/dataset/4ad6baea-4d2c-460f-a8bf-5d000db498f7/resource/2b9dfc3d-91d3-48de-b32c-a2a6d9417079/download/uniteevaluationfonciere.csv"
        r = requests.get(url, timeout=600); r.raise_for_status()
        m = pd.read_csv(io.BytesIO(r.content), dtype=str, encoding="utf-8")
        m.to_parquet(OUT / "montreal.parquet"); print("montreal", len(m), list(m.columns))
