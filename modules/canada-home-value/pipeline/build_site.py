"""Build site/ : the complete no-server website for your own hosting (no 256 MB limit), with every year of history.

  python pipeline/build_site.py      then upload the site/ folder to any static host (Netlify, Cloudflare Pages, S3, nginx).
Set HVE_CONFIG.googleKey near the top of site/index.html to show Street View photos and pinned maps.
"""
import pathlib, shutil, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
if SITE.exists():
    shutil.rmtree(SITE)
(SITE / "data").mkdir(parents=True)
shutil.copy(ROOT / "static" / "index.html", SITE / "index.html")
for f in (ROOT / "static" / "data").glob("*.json"):
    shutil.copy(f, SITE / "data" / f.name)
for d in ("addr", "nonres"):          # zoning is merged into the detail files
    shutil.copytree(ROOT / "static" / "data" / d, SITE / "data" / d)
subprocess.run([sys.executable, str(ROOT / "pipeline" / "build_details.py"), "--step=1", f"--out={SITE / 'data' / 'detail'}"], check=True)
html = (SITE / "index.html").read_text(encoding="utf-8")
KEY_LINE = '<script>window.HVE_CONFIG={mapillaryToken:"", googleKey:""};  // optional: free Mapillary token (no card) for street photos; Google key optional</script>'
html = html.replace('<meta name="claude:viewport-fit-sides" content="cover">' + chr(10), "")   # preview-only setting
html = html.replace("<title>", KEY_LINE + chr(10) + "<title>", 1)
(SITE / "index.html").write_text(html, encoding="utf-8")
# hosting config: long cache for data files (rebuilt weekly with new names only when content changes is not needed —
# a 1-day cache keeps updates visible), page always fresh; works on Netlify and Cloudflare Pages
(SITE / "_headers").write_text("""/index.html
  Cache-Control: no-cache
/
  Cache-Control: no-cache
/data/*
  Cache-Control: public, max-age=86400
  Access-Control-Allow-Origin: *
""", encoding="utf-8")
(SITE / "netlify.toml").write_text("""[build]
  publish = "."
""", encoding="utf-8")
size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
print("site/ ready:", round(size / 1e6, 1), "MB,", sum(1 for f in SITE.rglob("*") if f.is_file()), "files")
