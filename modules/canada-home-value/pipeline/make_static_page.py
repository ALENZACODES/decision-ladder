"""Build static/index.html (no server) from web/index.html: swap the API script for static-data.js and drop the map."""
import pathlib, re
R = pathlib.Path(__file__).resolve().parent.parent
s = (R / "web" / "index.html").read_text(encoding="utf-8")
a = s.index("/* ---- Live address autocomplete"); b = s.index("</script></body></html>")
s = s[:a] + (R / "static" / "static-data.js").read_text(encoding="utf-8") + "\n" + (R / "static" / "address-search.js").read_text(encoding="utf-8") + "\n" + (R / "static" / "report.js").read_text(encoding="utf-8") + "\n" + (R / "static" / "insights.js").read_text(encoding="utf-8") + "\n" + (R / "static" / "i18n.js").read_text(encoding="utf-8") + s[b:]
# artifact pages are wrapped in their own document skeleton and only allow Google Fonts stylesheets
s = re.sub(r"^<!doctype html>\s*<html[^>]*><head>.*?\n", "", s, count=1, flags=re.S)
s = s.replace("</style></head><body>", "</style>").replace("</script></body></html>", "</script>")
s = re.sub(r'<link rel="stylesheet" href="https://unpkg.com/leaflet[^>]*>\s*<script src="https://unpkg.com/leaflet[^>]*></script>\s*', "", s)
# the map stays; static-data.js only loads it where the host allows map images
s = s.replace("Indicative only. Values are modelled from public regional benchmark levels, not from sold listings for this property.",
              "Indicative only. Values come from public municipal assessment records, the 2021 Census and published regional benchmarks, not from sold listings.")
s = '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + s
(R / "static" / "index.html").write_text(s, encoding="utf-8")
print("static/index.html", len(s) // 1024, "KB")
