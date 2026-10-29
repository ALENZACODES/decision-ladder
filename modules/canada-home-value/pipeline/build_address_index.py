"""Build a SQLite full-text address index from the StatCan National Address Register zip.

Usage: python pipeline/build_address_index.py data/nar/202512.zip
Produces data/addresses.db with table `addr` and FTS5 table `addr_fts` (prefix search for autocomplete).
"""
import csv, io, pathlib, sqlite3, sys, zipfile
from pyproj import Transformer

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "addresses.db"
to_wgs = Transformer.from_crs("EPSG:3347", "EPSG:4326", always_xy=True)


def label(r):
    unit = (r.get("APT_NO_LABEL") or "").strip()
    civic = f'{r.get("CIVIC_NO","").strip()}{(r.get("CIVIC_NO_SUFFIX") or "").strip()}'
    street = " ".join(x for x in [r.get("MAIL_STREET_NAME") or r.get("OFFICIAL_STREET_NAME"),
                                   r.get("MAIL_STREET_TYPE") or r.get("OFFICIAL_STREET_TYPE"),
                                   r.get("MAIL_STREET_DIR") or r.get("OFFICIAL_STREET_DIR")] if x and x.strip())
    city = (r.get("MAIL_MUN_NAME") or r.get("CSD_ENG_NAME") or "").strip()
    prov = (r.get("MAIL_PROV_ABVN") or "").strip()
    pc = (r.get("MAIL_POSTAL_CODE") or "").strip()
    pc = f"{pc[:3]} {pc[3:]}" if len(pc) == 6 else pc
    head = f"{unit}-{civic}" if unit else civic
    return head, street, city, prov, pc


def main(zpath):
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript("""
      PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE addr(id INTEGER PRIMARY KEY, civic TEXT, street TEXT, city TEXT, prov TEXT, postal TEXT,
                        lat REAL, lon REAL, use INTEGER, csd TEXT);
    """)
    n = 0
    with zipfile.ZipFile(zpath) as z:
        files = [f for f in z.namelist() if f.lower().endswith(".csv") and "address" in f.lower()]
        print(len(files), "address files")
        for f in files:
            with z.open(f) as fh:
                rd = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
                batch = []
                for r in rd:
                    # building point, else the building-footprint point (many newer homes only have the second one)
                    try:
                        x, y = float(r["BG_X"]), float(r["BG_Y"])
                    except (TypeError, ValueError, KeyError):
                        try:
                            x, y = float(r["BF_REPPOINT_X"]), float(r["BF_REPPOINT_Y"])
                        except (TypeError, ValueError, KeyError):
                            continue
                    lon, lat = to_wgs.transform(x, y)
                    civic, street, city, prov, pc = label(r)
                    if not civic or not street:
                        continue
                    batch.append((civic, street, city, prov, pc, round(lat, 6), round(lon, 6),
                                  int(r.get("BU_USE") or 0) if (r.get("BU_USE") or "").isdigit() else 0,
                                  r.get("CSD_ENG_NAME", "")))
                    if len(batch) >= 100000:
                        con.executemany("INSERT INTO addr(civic,street,city,prov,postal,lat,lon,use,csd) VALUES(?,?,?,?,?,?,?,?,?)", batch)
                        n += len(batch); batch = []; print(f, n, flush=True)
                con.executemany("INSERT INTO addr(civic,street,city,prov,postal,lat,lon,use,csd) VALUES(?,?,?,?,?,?,?,?,?)", batch)
                n += len(batch); con.commit()
    print("rows", n, "- building search index")
    con.executescript("""
      CREATE VIRTUAL TABLE addr_fts USING fts5(txt, content='', prefix='2 3 4', tokenize='unicode61 remove_diacritics 2');
      INSERT INTO addr_fts(rowid, txt) SELECT id, civic||' '||street||' '||city||' '||prov||' '||replace(postal,' ','') FROM addr;
      CREATE INDEX addr_geo ON addr(lat, lon);
    """)
    con.commit(); con.close(); print("done", DB)


if __name__ == "__main__":
    main(sys.argv[1])
