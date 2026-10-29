/* Back-test run inside the page (paste into the console or run via the test browser after the page loads).
   Uses the page's own search (suggest) and pick, so it tests exactly what a visitor gets.
   Results: window.BT = {addr:[...], postal:[...], value:[...], done:true} */
(async () => {
  window.print = () => {};
  const S = await (await fetch("backtest.json?" + Date.now())).json();
  const P = s => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  const num = t => +String(t || "").replace(/[^\d]/g, "") || 0;
  const BT = window.BT = { addr: [], postal: [], value: [], done: false, n: 0 };
  const A = $("addr");
  async function search(q) { A.value = q; await suggest(); return (typeof acItems !== "undefined" ? acItems : []) || []; }
  async function choose(it) { await pick(it); return { muni: st.muni, prov: st.prov, val: num($("rVal").textContent), fsaMed: (DB.fsa[it.fsa] || {}).c || null }; }
  for (const t of (window.BT_ONLY&&BT_ONLY!=="addr"?[]:S.addr)) {
    BT.n++;
    try {
      const items = await search(t.q), it = items[0];
      const hit = items.findIndex(o => o.postal && P(o.civic) === P(t.civic) && P(o.unit) === P(t.unit) && P(o.postal) === P(t.postal));
      const r = it ? await choose(it) : {};
      BT.addr.push({ q: t.q, found: hit === 0, inList: hit >= 0, first: it ? `${it.label} ${it.sub || ""}` : null,
        muniOk: P(r.muni) === P(t.csd), muni: r.muni || null, csd: t.csd, val: r.val || 0, fsaMed: r.fsaMed });
    } catch (e) { BT.addr.push({ q: t.q, err: String(e) }); }
  }
  for (const t of (window.BT_ONLY&&BT_ONLY!=="postal"?[]:S.postal)) {
    BT.n++;
    try {
      const items = await search(t.q), it = items[0];
      const ok = !!it && P(it.postal) === P(t.postal);
      const r = it ? await choose(it) : {};
      BT.postal.push({ q: t.q, found: ok, first: it ? `${it.label} ${it.sub || ""}` : null, muniOk: P(r.muni) === P(t.csd), muni: r.muni || null, csd: t.csd, val: r.val || 0 });
    } catch (e) { BT.postal.push({ q: t.q, err: String(e) }); }
  }
  for (const t of (window.BT_ONLY&&BT_ONLY!=="value"?[]:S.value)) {
    BT.n++;
    try {
      const items = await search(t.q), it = items.find(o => P(o.civic) === P(t.civic) && P(o.postal) === P(t.postal)) || items[0];
      const r = it ? await choose(it) : {};
      BT.value.push({ q: t.q, roll: t.roll, assessed: t.assessed, val: r.val || 0, err: r.val ? r.val / t.assessed - 1 : null, muniOk: P(r.muni) === P(t.csd) });
    } catch (e) { BT.value.push({ q: t.q, err2: String(e) }); }
  }
  BT.done = true;
})();
