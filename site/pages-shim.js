// GitHub Pages build of Decision Ladder: answers the UI's /api/* calls without a server.
// GET endpoints are snapshots written at build time by the same Python code (api/*.json).
// POST endpoints run the real Python package in the browser (Pyodide) in offline mode, and the
// JavaScript apps' calculators run through pages-bridge.js. Nothing is sent to any model or API.
(function () {
  const PREFIX = "__PREFIX__";
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v__PYV__/full/";
  const RR_LIVE = "__RR_LIVE__";
  const origFetch = window.fetch.bind(window);
  let pyReady = null;

  function note(msg) {
    let n = document.getElementById("pagesNote");
    if (!n) {
      n = document.createElement("div");
      n.id = "pagesNote";
      n.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:9999;max-width:420px;padding:10px 14px;border-radius:10px;" +
        "background:#10233f;color:#fff;font:13px/1.4 system-ui,sans-serif;box-shadow:0 4px 18px rgba(0,0,0,.25)";
      document.body.appendChild(n);
    }
    n.textContent = msg;
    n.hidden = !msg;
  }

  function loadScript(src) {
    return new Promise((ok, bad) => {
      const s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = () => bad(new Error("could not load " + src));
      document.head.appendChild(s);
    });
  }

  function rewrite(text) {
    return text.split('"/apps/renewal-radar/').join('"' + RR_LIVE)
               .split('"/apps/').join('"' + PREFIX + "/apps/");
  }

  async function ensurePy() {
    if (pyReady) return pyReady;
    pyReady = (async () => {
      note("Loading the Python engine in your browser (first run only, about 10-20 seconds)…");
      await loadScript(PREFIX + "/static/pages-bridge.js");
      await window.dlBridgeReady;
      await loadScript(PYODIDE + "pyodide.js");
      const py = await loadPyodide({ indexURL: PYODIDE });
      const zip = await (await origFetch(PREFIX + "/py/bundle.zip")).arrayBuffer();
      py.unpackArchive(zip, "zip", { extractDir: "/home/pyodide/app" });
      py.runPython("import sys; sys.path.insert(0, '/home/pyodide/app')");
      py.runPython("import pyapi");
      note("");
      return py.pyimport("pyapi");
    })();
    pyReady.catch((e) => { note("Could not start the in-browser engine: " + e.message); pyReady = null; });
    return pyReady;
  }
  window.dlEnsurePy = ensurePy;

  window.fetch = async function (input, init) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin === location.origin && url.pathname.startsWith("/api/")) {
      const name = url.pathname.slice(5);
      const method = ((init && init.method) || "GET").toUpperCase();
      if (method === "GET") {
        const r = await origFetch(PREFIX + "/api/" + name + ".json");
        return new Response(rewrite(await r.text()), { status: r.status, headers: { "Content-Type": "application/json" } });
      }
      const api = await ensurePy();
      await new Promise((r) => setTimeout(r, 30)); // let the spinner paint before the synchronous run
      const out = JSON.parse(api.handle(url.pathname, (init && init.body) || "{}"));
      return new Response(rewrite(JSON.stringify(out.body)), { status: out.status, headers: { "Content-Type": "application/json" } });
    }
    return origFetch(input, init);
  };

  // Warm the engine in the background once the page is idle, so the first click is fast.
  window.addEventListener("load", () => setTimeout(() => ensurePy().catch(() => {}), 1500));
})();
