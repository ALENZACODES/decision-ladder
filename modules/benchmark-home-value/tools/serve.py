"""Local server for Benchmark Home Value: serves the app folder to this computer only (127.0.0.1) and relays
requests to a fixed list of free public data services that browsers can't call directly (no CORS) or that are
often busy (OpenStreetMap). Nothing else is reachable through it.
Usage: python serve.py [port]"""
import http.server, json, os, socketserver, sys, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
UA = {"User-Agent": "BenchmarkHomeValue/1.0 (local app)"}
# name -> list of upstream base URLs, tried in order
RELAYS = {
    "ckan": ["https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"],
    "tps": ["https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/Neighbourhood_Crime_Rates_Open_Data/FeatureServer/0/query"],
    "overpass": ["https://overpass.openstreetmap.fr/api/interpreter", "https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
                 "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"],
    "boc": ["https://www.bankofcanada.ca/valet/observations"],
}
def good(name, body):
    try:
        j = json.loads(body)
    except Exception:
        return False
    if name == "overpass": return isinstance(j.get("elements"), list)
    if name == "ckan": return bool(j.get("success"))
    return True
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache"); super().end_headers()
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        if not self.path.startswith("/proxy/"): return super().do_GET()
        head, _, tail = self.path[len("/proxy/"):].partition("?")   # e.g. "boc/V39079/json", "recent=1"
        name, _, sub = head.partition("/")
        extra = "/" + sub if sub else ""
        if ".." in extra: return self.send_error(400, "bad path")
        if name not in RELAYS: return self.send_error(404, "unknown relay")
        last = "no upstream answered"
        for base in RELAYS[name]:
            url = base + extra + ("?" + tail if tail else "")
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15 if name == "overpass" else 25) as r:
                    body = r.read()
                if good(name, body):
                    self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body))); self.send_header("X-Relay-Source", base.split("/")[2])
                    self.end_headers(); self.wfile.write(body); return
                last = "upstream answered with unusable data"
            except Exception as e:
                last = str(e)
        try: self.send_error(502, last[:200])
        except OSError: pass
class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True
    def handle_error(self, request, client_address):
        # the page gave up waiting and closed the connection: nothing to report
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, TimeoutError)): return
        super().handle_error(request, client_address)
if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as s:
        print(f"Benchmark Home Value is running at http://localhost:{PORT}/  (close this window to stop)")
        s.serve_forever()
