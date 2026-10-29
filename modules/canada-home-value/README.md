# Canada Home Value

Home value estimator for every Canadian province and territory, with address autocomplete and an AI valuation model.

## What's inside

| Part | Source | Notes |
|---|---|---|
| Address autocomplete | StatCan National Address Register (Dec 2025, ~16M addresses, Open Licence) | `data/addresses.db`, SQLite FTS5 prefix search |
| AI valuation model | Calgary + Edmonton open assessment data (2026 roll, valued Jul 1 2025) | LightGBM, `models/avm.txt` |
| Market trends + fallback estimate | Regional benchmark index curves built into `web/index.html` | Used where no parcel data exists |

The AI estimate is only available for Calgary and Edmonton parcels. Everywhere else the page uses the area benchmark model plus the owner's purchase price indexed to today.

No MLS or sold-listing data is used. Assessments are the city's mass-appraisal value, not sale prices.

## Rebuild from scratch

```bash
python -m venv .venv
.venv/Scripts/pip install pandas pyarrow lightgbm scikit-learn fastapi uvicorn requests pyproj
.venv/Scripts/python pipeline/fetch_assessments.py
curl -L -o data/nar/202512.zip https://www150.statcan.gc.ca/n1/pub/46-26-0002/2022001/202512.zip
.venv/Scripts/python pipeline/build_address_index.py data/nar/202512.zip
.venv/Scripts/python pipeline/train_model.py
```

## Run

```bash
.venv/Scripts/uvicorn server.app:app --port 8000
```

Then open http://localhost:8000.

## API

- `GET /api/suggest?q=15 deermeade` — address suggestions
- `GET /api/property/{id}` — address details, public-record facts, AI estimate (Calgary, Edmonton, Winnipeg, Vancouver), facts (+ Montréal), postal-area value everywhere
- `GET /api/health` — what's loaded and model accuracy

## Property records

`pipeline/fetch_assessments.py`, `fetch_more.py`, `fetch_arcgis.py` and the Québec / New Brunswick downloads feed
`pipeline/build_parcels.py` (+ `parcels_more.py`), which merges everything into `data/parcels.parquet` (4.57M records):

| Source | Records | Value date | Notes |
|---|---|---|---|
| Québec province-wide roll (MAMH, CC-BY 4.0) | 2.90M | Jul 2022–2024 | every municipality; floor area, year, storeys, units, attached type |
| Calgary | 580k | Jul 1 2025 | condo units, townhouses, lot size, year |
| Edmonton | 412k | Jul 1 2025 | condo suites, lot, floor area, year |
| Winnipeg | 232k | Apr 1 2025 | living area, rooms, garage, basement |
| Vancouver | 201k | Jul 1 2025 | every strata unit; land + improvement |
| Victoria | 61k | Jul 1 2025 | strata units |
| Langley Township | 53k | Jul 1 2025 | lot size, coordinates |
| Strathcona County | 37k | Jul 1 2023 | floor area, garage, basement |
| New Brunswick (GeoNB) | 93k | 2017 | facts only, too old to train on |

Not openly published: Ontario (MPAC), Saskatchewan cities, Halifax (only capped tax-bill values), most other BC cities (BC Assessment).
Download commands: `curl -L -o data/raw/qc/role2026.gpkg.zip https://donneesouvertes.affmunqc.net/role/ROLE2026_GEOPACKAGE.zip`
and `curl -L -o data/raw/nb/evan.zip https://geonb.snb.ca/downloads/evan/geonb_evan_tsv.zip` (unzip in place).

Every assessment is moved to Sep-2026 dollars with the regional index before training (`pipeline/train_model.py`).
Everywhere else the estimate is anchored to the 2021 Census postal-area median moved to today.

## No-server version (`static/`)

`static/index.html` plus `static/data/` is a complete site: any static host (S3, Netlify, Cloudflare Pages, nginx) can serve it.
No API, no database. Rebuild with:

```bash
.venv/Scripts/python pipeline/build_static.py      # values: municipalities, postal areas, streets
.venv/Scripts/python pipeline/build_addresses.py   # all ~16M addresses for autocomplete
.venv/Scripts/python pipeline/make_static_page.py  # page = web/index.html + static/static-data.js + static/address-search.js
```

| File | Contents |
|---|---|
| `data/munis.json` | every municipality: name, province, region, postal areas |
| `data/fsa.json` | every postal area: Census median today, record medians by type `[value, count, sq ft, year]`, `s:1` if street data exists |
| `data/streets_<L>.json` | per postal letter: `FSA -> "CORE|DIR" -> {type: [value, count, sq ft, year], _r: [min civic, max civic]}` |
| `data/accuracy.json` | holdout error of the page's own method |
| `data/addr/packs.json` | `FSA -> pack id` |
| `data/addr/idx_<L>.json` | per postal letter: `"CORE|DIR" -> [street name, [FSA...]]` |
| `data/addr/p<id>.json` | `FSA -> [[street, city index, "LDU:civic unit/civic …;LDU:…"]]`, `_c` = city names |

Street keys (`CORE|DIR`) come from `pipeline/addrkey.py`; `static/static-data.js` has the same rule in JavaScript.
Search loads one street index and only the packs for matching postal areas, so a lookup downloads a few MB at most.

## Neighbourhood blocks (Ontario, Saskatchewan, Atlantic, North and anywhere without records)

`pipeline/build_da.py` places every address in its 2021 Census dissemination area (57,936 blocks, boundaries from
StatCan's map service) and stores each block's Census median home value. `pipeline/build_chsp.py` turns StatCan's
Canadian Housing Statistics Program (table 46-10-0027, MPAC/BC Assessment/etc. medians) into per-municipality
property-type ratios for 2,275 municipalities. `pipeline/build_da_static.py` writes `static/data/da_<PR>.json` and
`csd_types.json`, calibrated to records where they exist and to published Sep 2026 MLS HPI benchmarks elsewhere.

For homes without assessment records the page uses sqrt(block × postal area) × local type ratio × (sq ft / typical)^0.4.
Tested on 400,000 real assessments (`pipeline/check_block_accuracy.py`): 20.7% median error, 18.3% with floor area,
versus 22.7% for postal-area values alone. Owner-entered purchase price narrows it further.

## Photos, maps, legal descriptions, history and printable report

- Photo and map links (Street View, Google Maps, satellite, Bing Streetside) open at each postal code's centre
  (`LDU@DAUID@lat,lon` in the address packs). An OpenStreetMap pin appears wherever the host allows map images.
- Set `HVE_CONFIG.googleKey` (Google Maps Platform key with Street View Static + Maps Static) on your own site to show
  the Street View photo and a pinned map in the page and in the report.
- Legal descriptions (`static/data/legal/`, 1.0M addresses): Calgary, Edmonton, Vancouver, Township of Langley, Victoria.
  Québec removes cadastre numbers from its open roll; Ontario's are not open.
- Assessment history (`static/data/history/`): Calgary and Edmonton 2014–2026, Vancouver 2020–2026, Langley 2020–2026,
  Victoria 2024/2026. Sold history is not openly published.
- "Print / Save as PDF" builds a one-page report (value, range, method, adjustments, facts, legal, history chart,
  location, equity). Printing works on your own site; the claude.ai preview blocks printing by design.

## Your own website

`python pipeline/build_site.py` writes `site/` (about 236 MB): the page plus every data file, with yearly assessment
history (2014–2026). Upload the folder to any static host. Paste a Google Maps Platform key into
`window.HVE_CONFIG={googleKey:"..."}` at the top of `site/index.html` for Street View photos and pinned maps; without it
the page shows an OpenStreetMap pin and photo links. Print / Save as PDF works there.

## Insights (all free public data)

- **What can I build here?** Units allowed on the lot from provincial law (Ontario Bill 23, BC Bill 44, Québec Bill 31) and
  municipal reforms (Toronto, Ottawa, Mississauga, Hamilton, London, Kitchener, Calgary R-CG, Edmonton RS, Winnipeg,
  Saskatoon, Regina, Halifax, Moncton, Fredericton, Vancouver, Victoria), adjusted by the lot's actual zoning where published.
  Rent income from CMHC 2025 average rents (StatCan 34-10-0133, `pipeline/build_extras.py`), income value at a 5% cap
  rate, typical build costs, and the financing programs that fit (Secondary Suite Refinance Program, MLI Select).
- **Zoning** for 1.0M addresses (Calgary, Edmonton, Vancouver, Langley Twp, Winnipeg), merged into the detail files.
- **Commercial / non-residential flag** from the National Address Register building-use code (490k addresses).
- **Neighbourhood profile** for 57,758 Census blocks (`pipeline/build_profile.py`): income, owners, age, education,
  transit, housing type and age, shelter costs, ranked against all of Canada.
- **Google Map** embedded with Google's free keyless embed on your own site (blocked inside the claude.ai preview).
