
  window.dlBridgeCall = function (mod, fn, raw) {
    const key = mod + "." + fn;
    if (!FUNCS[key]) return JSON.stringify({ ok: false, error: "unknown function " + key });
    try {
      const result = FUNCS[key](raw ? JSON.parse(raw) : {});
      return JSON.stringify({ ok: true, result }, (k, v) => (typeof v === "number" && !isFinite(v) ? null : v));
    } catch (e) {
      return JSON.stringify({ ok: false, error: e.name + ": " + e.message });
    }
  };
  window.dlBridgeReady = Promise.all(ESM_FILES.map(async (f) => { ESM[f] = await import(MODS + "/" + f); }));
})();
