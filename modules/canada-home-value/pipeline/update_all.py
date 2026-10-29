"""Check every source for new data and rebuild whatever changed. Safe to run on a schedule (e.g. weekly).

  python pipeline/update_all.py            # check + rebuild what changed
  python pipeline/update_all.py --force    # rebuild everything

Sources and how often they change:
  National Address Register (StatCan)   ~twice a year   new YYYYMM.zip release
  Calgary / Edmonton / Winnipeg          continuously    open-data APIs (new parcels, sales-driven roll updates)
  Vancouver / Victoria / Langley         yearly          new assessment year
  Québec roll (MAMH)                     quarterly       ROLE<year> package
State is kept in data/state.json. Output: rebuilt static/ (ready to upload) and a git commit.
"""
import datetime as dt, json, pathlib, subprocess, sys, zipfile
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
STATE = ROOT / "data" / "state.json"
LOG = ROOT / "data" / "update.log"


def log(*a):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M} " + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(*args):
    log("run", *args)
    subprocess.run([PY, *args], cwd=ROOT, check=True)


def head(url):
    try:
        r = requests.head(url, timeout=30, allow_redirects=True)
        # Outage/maintenance pages come back 200 text/html for any URL; not a real file
        if r.headers.get("Content-Type", "").startswith("text/html"):
            return 404, None
        return r.status_code, r.headers.get("Last-Modified") or r.headers.get("Content-Length")
    except Exception as e:
        return None, str(e)


def newest_nar(after):
    """Probe StatCan for NAR releases newer than `after` (YYYYMM)."""
    today = dt.date.today(); found = None
    y, m = int(after[:4]), int(after[4:])
    while (y, m) < (today.year, today.month):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        tag = f"{y}{m:02d}"
        code, _ = head(f"https://www150.statcan.gc.ca/n1/pub/46-26-0002/2022001/{tag}.zip")
        if code == 200:
            found = tag
    return found


def socrata_count(base, where):
    try:
        return requests.get(base, params={"$select": "count(*)", "$where": where}, timeout=60).json()[0]["count"]
    except Exception:
        return None


def chsp_release():
    """Release time of StatCan table 46-10-0027 (municipal assessment medians by property type)."""
    try:
        r = requests.post("https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata", json=[{"productId": 46100027}], timeout=60)
        return r.json()[0]["object"]["releaseTime"]
    except Exception:
        return None


def rent_release():
    """Release time of StatCan table 34-10-0133 (CMHC average rents)."""
    try:
        r = requests.post("https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata", json=[{"productId": 34100133}], timeout=60)
        return r.json()[0]["object"]["releaseTime"]
    except Exception:
        return None


def refresh_rents():
    url = requests.get("https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/34100133/en", timeout=60).json()["object"]
    z = ROOT / "data" / "raw" / "rent" / "34100133.zip"; z.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(z, "wb") as f:
            for c in r.iter_content(1 << 20):
                f.write(c)
    zipfile.ZipFile(z).extractall(z.parent)


def refresh_chsp():
    url = requests.get("https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/46100027/en", timeout=60).json()["object"]
    z = ROOT / "data" / "raw" / "chsp" / "46100027.zip"; z.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(z, "wb") as f:
            for c in r.iter_content(1 << 20):
                f.write(c)
    zipfile.ZipFile(z).extractall(z.parent)
    run("pipeline/build_chsp.py")


def main(force=False):
    state = json.loads(STATE.read_text()) if STATE.exists() else {"nar": "202512"}
    changed = {"addresses": force, "records": force}

    # 1. National Address Register
    rel = newest_nar(state.get("nar", "202512"))
    if rel:
        log("new address register release", rel)
        zpath = ROOT / "data" / "nar" / f"{rel}.zip"
        with requests.get(f"https://www150.statcan.gc.ca/n1/pub/46-26-0002/2022001/{rel}.zip", stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        zipfile.ZipFile(zpath).testzip()
        run("pipeline/build_address_index.py", str(zpath))
        state["nar"] = rel; changed["addresses"] = True
    else:
        log("address register: no new release after", state.get("nar"))

    # 2. Municipal records: refetch when the source row count or file date moved
    checks = {
        "calgary": socrata_count("https://data.calgary.ca/resource/4bsw-nn7w.json", "assessment_class='RE'"),
        "edmonton": socrata_count("https://data.edmonton.ca/resource/q7d6-ambg.json", "tax_class='Residential'"),
        "winnipeg": socrata_count("https://data.winnipeg.ca/resource/d4mq-wa44.json", "property_class_1 like 'RESIDENTIAL%'"),
        "chsp": chsp_release(),
        "rents": rent_release(),
        "quebec": head(f"https://donneesouvertes.affmunqc.net/role/ROLE{dt.date.today().year}_GEOPACKAGE.zip")[1],
    }
    for name, sig in checks.items():
        if sig and state.get(name) != sig:
            log("source changed:", name, state.get(name), "->", sig)
            state[name] = sig; changed["records"] = True
            if name == "calgary" or name == "edmonton":
                run("pipeline/fetch_assessments.py")
            elif name == "winnipeg":
                run("pipeline/fetch_more.py", "winnipeg", "edmonton_details")
            elif name == "rents":
                refresh_rents()
            elif name == "chsp":
                refresh_chsp()
            elif name == "quebec":
                log("Québec roll changed: download ROLE<year>_GEOPACKAGE.zip into data/raw/qc and unzip (see README)")
    if changed["records"] or changed["addresses"]:
        run("pipeline/build_parcels.py")
        if changed["records"]:
            run("pipeline/train_model.py")
        run("pipeline/build_static.py")
        if changed["addresses"]:
            run("pipeline/build_da.py")                # place new addresses in Census neighbourhood blocks
        run("pipeline/build_da_static.py")
        run("pipeline/check_block_accuracy.py")
        run("pipeline/build_addresses.py")
        run("pipeline/build_csd_lookup.py")             # mailing town -> municipality
        if changed["records"]:
            run("pipeline/fetch_legal.py"); run("pipeline/build_legal.py")
            run("pipeline/fetch_history.py"); run("pipeline/build_history.py")
        run("pipeline/build_extras.py")                # rents, zoning, non-residential flags
        run("pipeline/build_details.py")
        run("pipeline/make_static_page.py")
        STATE.write_text(json.dumps(state, indent=1))
        subprocess.run(["git", "add", "-A"], cwd=ROOT)
        subprocess.run(["git", "commit", "-q", "-m", f"Data update {dt.date.today()}: "
                        + ", ".join(k for k, v in changed.items() if v)], cwd=ROOT)
        run("pipeline/export_site.py")                 # refresh Downloads\canada-home-value-site (+ .zip)
        log("rebuilt; static/ and Downloads site export are ready")
    else:
        STATE.write_text(json.dumps(state, indent=1))
        log("nothing new")


def stamp():
    """data/updated.json: the date of the last successful check, shown on the page as "Live · Updated <date>"."""
    st = {"date": dt.date.today().isoformat(), "checked": dt.datetime.now().isoformat(timespec="minutes"), "prices": "Sep 2026"}
    for d in (ROOT / "static" / "data", pathlib.Path.home() / "Downloads" / "canada-home-value-site" / "data"):
        if d.exists():
            (d / "updated.json").write_text(json.dumps(st), encoding="utf-8")
    log("stamped", st["date"])


if __name__ == "__main__":
    main(force="--force" in sys.argv)
    for extra in ("pipeline/build_schools.py", "pipeline/build_recent.py"):   # new school year / StatCan release, cheap to re-check daily
        try:
            run(extra)
        except Exception as e:
            log("failed", extra, e)
    subprocess.run([PY, str(ROOT / "pipeline" / "make_static_page.py")], cwd=ROOT)
    stamp()
