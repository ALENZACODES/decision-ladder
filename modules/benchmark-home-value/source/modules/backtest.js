// Value backtest over every assessed address in data/detail/*.json, using the page's own price index.
//
// Walk-forward: from each assessment a home had, predict every later assessment it got, using only
// what was known at the start (that home's value then + the page's regional index), and compare.
//   index  : the page's method for a past value, value × index(then→later)        (what the page shows)
//   flat   : no change at all (the baseline any model has to beat)
//   local  : the postal area's own median growth over the same years             (what a local index would add)
// Cross-section: each home's latest assessment predicted from the median of the other homes on its street.
// Assessment roll year Y reflects market value on July 1 of Y-1 (Alberta and BC rules).
const fs = require("fs"), path = require("path");
const P = require("./pagecode.js");
const D = path.join(__dirname, "..", "data");
const fsaInfo = JSON.parse(fs.readFileSync(path.join(D, "fsa.json")));
const idxFiles = JSON.parse(fs.readFileSync(path.join(D, "detail", "index.json")));

const LETTER_REG = { T: "CGY", V: "VAN", R: "PRA" };
const G = { ON: .06, BC: .07, QC: .045 };
const PROV = { T: "AB", V: "BC", R: "MB" };
function cityOf(fsa) {
  const p2 = fsa.slice(0, 2);
  if (p2 === "T2" || p2 === "T3") return "Calgary";
  if (p2 === "T5" || p2 === "T6") return "Edmonton";
  if (p2 === "V5" || p2 === "V6") return "Vancouver";
  if (fsa[0] === "T") return "Other Alberta";
  if (fsa[0] === "V") return "Other BC";
  return "Manitoba";
}
function idxAt(reg, prov, y, m) {     // the page's own lookup, including its pre-2016 extension
  const idx = P.IDX[reg], i = P.mi(y, m), g = G[prov] || .035;
  return i >= 0 ? idx[Math.min(i, idx.length - 1)] : idx[0] / Math.pow(1 + g, -i / 12);
}
function decodeHistory(s) {
  if (!s) return [];
  const [head, vals] = s.split(":"), [yy, step] = head.split("/").map(Number);
  return vals.split(",").map((v, i) => v ? [2000 + yy + i * step, parseInt(v, 36) * 1000] : null).filter(Boolean);
}
const med = a => { if (!a.length) return NaN; const s = Float64Array.from(a).sort(), k = s.length >> 1; return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2; };

// ---------- load every record ----------
const homes = [];                      // {fsa, city, reg, prov, key, unit, zone, h:[[y,v]...]}
let total = 0, noHist = 0;
for (const file of Object.keys(idxFiles)) {
  const d = JSON.parse(fs.readFileSync(path.join(D, "detail", file + ".json")));
  for (const [fsa, recs] of Object.entries(d)) {
    const reg = (fsaInfo[fsa] && fsaInfo[fsa].r) || LETTER_REG[fsa[0]], prov = PROV[fsa[0]];
    for (const [k, v] of Object.entries(recs)) {
      total++;
      const h = decodeHistory(v[1]);
      const [unit, civic, core, dir, ty] = k.split("|");
      if (!h.length) { noHist++; continue; }
      homes.push({ fsa, city: cityOf(fsa), reg, prov, street: `${core}|${dir}|${ty || ""}`, civic, unit, zone: v[2] || "", h });
    }
  }
}

// keep homes, not office towers, parking stalls or vacant scraps: a value inside 2x of its street's typical and within a sane band
const byStreet = new Map();
for (const o of homes) {
  const last = o.h[o.h.length - 1][1], key = o.fsa + "|" + o.street + "|" + (o.unit ? "u" : "h");
  o.sk = key; if (!byStreet.has(key)) byStreet.set(key, []); byStreet.get(key).push(last);
}
const streetMed = new Map(); for (const [k, a] of byStreet) streetMed.set(k, med(a));
const keep = homes.filter(o => {
  const last = o.h[o.h.length - 1][1], m = streetMed.get(o.sk);
  return last >= 75000 && last <= 12e6 && (!(byStreet.get(o.sk).length >= 3) || (last <= m * 3 && last >= m / 3));
});

// ---------- local (postal-area) growth: median of v(t1)/v(t0) across homes with both rolls ----------
const localG = new Map();              // fsa|y0|y1 -> median growth
{
  const acc = new Map();
  for (const o of keep) for (let i = 0; i < o.h.length; i++) for (let j = i + 1; j < o.h.length; j++) {
    const k = `${o.fsa}|${o.h[i][0]}|${o.h[j][0]}`; if (!acc.has(k)) acc.set(k, []); acc.get(k).push(o.h[j][1] / o.h[i][1]);
  }
  for (const [k, a] of acc) if (a.length >= 20) localG.set(k, med(a));
}

// ---------- walk-forward pairs ----------
const pairs = [];                      // compact: [cityIdx, y0, y1, errIdx, errFlat, errLocal|NaN, unit, pred, actual]
const CITIES = ["Calgary", "Edmonton", "Other Alberta", "Vancouver", "Other BC", "Manitoba"];
const growthAct = new Map();           // city|y0|y1 -> [ratios]
for (const o of keep) {
  const ci = CITIES.indexOf(o.city);
  for (let i = 0; i < o.h.length; i++) for (let j = i + 1; j < o.h.length; j++) {
    const [y0, v0] = o.h[i], [y1, v1] = o.h[j];
    if (v0 < 20000) continue;
    const gi = idxAt(o.reg, o.prov, y1 - 1, 6) / idxAt(o.reg, o.prov, y0 - 1, 6);
    const lg = localG.get(`${o.fsa}|${y0}|${y1}`);
    const pi = v0 * gi;
    pairs.push([ci, y0, y1, pi / v1 - 1, v0 / v1 - 1, lg ? v0 * lg / v1 - 1 : NaN, o.unit ? 1 : 0, pi, v1]);
    if (j === i + 1) { const k = `${o.city}|${y0}|${y1}`; if (!growthAct.has(k)) growthAct.set(k, { a: [], reg: o.reg, prov: o.prov }); growthAct.get(k).a.push(v1 / v0); }
  }
}

// ---------- cross-section: street median of the other homes (leave one out) ----------
const xs = [];                         // [cityIdx, err, unit]
{
  const groups = new Map();
  for (const o of keep) {
    const [y, v] = o.h[o.h.length - 1]; if (y < 2025) continue;
    const k = o.sk + "|" + o.zone + "|" + y; if (!groups.has(k)) groups.set(k, []); groups.get(k).push([v, o]);
  }
  for (const a of groups.values()) {
    if (a.length < 4) continue;
    const vals = a.map(x => x[0]).sort((p, q) => p - q);
    for (const [v, o] of a) {      // median of the others: drop one copy of this value
      const others = vals.slice(); others.splice(others.indexOf(v), 1);
      xs.push([CITIES.indexOf(o.city), med(others) / v - 1, o.unit ? 1 : 0]);
    }
  }
}

// ---------- summaries ----------
function stats(errs) {
  const a = errs.filter(Number.isFinite), n = a.length; if (!n) return null;
  const abs = a.map(Math.abs);
  const w = t => +(abs.filter(x => x <= t).length / n).toFixed(4);
  return { n, mdape: +med(abs).toFixed(4), bias: +med(a).toFixed(4), w5: w(.05), w10: w(.10), w20: w(.20),
    p90: +Float64Array.from(abs).sort()[Math.floor(n * .9)].toFixed(4) };
}
const col = (rows, c) => rows.map(r => r[c]);
const out = { generated: new Date().toISOString().slice(0, 10), records: total, with_history: homes.length, tested_homes: keep.length,
  homes_by_city: {}, pairs: pairs.length, groups: {}, calib: [], scatter: [], fsa: [] };
for (const o of keep) out.homes_by_city[o.city] = (out.homes_by_city[o.city] || 0) + 1;
function hist(rows, c) {   // -50%..+50% in 2.5-point bins, share of predictions
  const bins = new Array(41).fill(0); let lo = 0, hi = 0, n = 0;
  for (const r of rows) { const e = r[c]; if (!Number.isFinite(e)) continue; n++; const b = Math.round(e * 100 / 2.5);
    if (b < -20) lo++; else if (b > 20) hi++; else bins[b + 20]++; }
  return { bins: bins.map(x => +(x / n).toFixed(5)), under: +(lo / n).toFixed(4), over: +(hi / n).toFixed(4) };
}
function group(rows, xsRows) {
  const g = { methods: {}, horizon: {}, kind: {}, hist: {}, xs: null };
  for (const [m, c] of [["index", 3], ["flat", 4], ["local", 5]]) { g.methods[m] = stats(col(rows, c)); g.hist[m] = hist(rows, c); }
  const hz = new Map(); for (const r of rows) { const h = r[2] - r[1]; if (!hz.has(h)) hz.set(h, []); hz.get(h).push(r); }
  for (const [h, rr] of [...hz].sort((a, b) => a[0] - b[0])) if (rr.length >= 300)
    g.horizon[h] = { index: stats(col(rr, 3)), flat: stats(col(rr, 4)), local: stats(col(rr, 5)) };
  g.kind = { house: stats(rows.filter(r => !r[6]).map(r => r[3])), condo: stats(rows.filter(r => r[6]).map(r => r[3])) };
  g.xs = { all: stats(xsRows.map(r => r[1])), house: stats(xsRows.filter(r => !r[2]).map(r => r[1])), condo: stats(xsRows.filter(r => r[2]).map(r => r[1])) };
  return g;
}
out.groups.All = group(pairs, xs);
for (let ci = 0; ci < CITIES.length; ci++) { const rows = pairs.filter(r => r[0] === ci); if (rows.length) out.groups[CITIES[ci]] = group(rows, xs.filter(r => r[0] === ci)); }
// index vs reality, one row per city and roll-to-roll period
for (const [k, g] of growthAct) {
  const [city, y0, y1] = k.split("|"); if (g.a.length < 300) continue;
  const act = med(g.a) - 1, ix = idxAt(g.reg, g.prov, +y1 - 1, 6) / idxAt(g.reg, g.prov, +y0 - 1, 6) - 1;
  out.calib.push({ city, from: +y0, to: +y1, actual: +act.toFixed(4), index: +ix.toFixed(4), n: g.a.length });
}
out.calib.sort((a, b) => a.city.localeCompare(b.city) || a.from - b.from);
// predicted vs actual, an even sample of 2,400 latest-roll pairs
{ const latest = pairs.filter(r => r[2] >= 2025); const step = Math.max(1, Math.floor(latest.length / 2400));
  for (let i = 0; i < latest.length; i += step) out.scatter.push([latest[i][0], Math.round(latest[i][7] / 1000), Math.round(latest[i][8] / 1000), latest[i][6]]); }
// every postal area: index error and local error
{ const byF = new Map();
  for (const o of keep) for (let i = 0; i < o.h.length - 1; i++) {
    const [y0, v0] = o.h[i], [y1, v1] = o.h[o.h.length - 1]; if (y1 < 2025 || v0 < 20000) continue;
    const e = v0 * idxAt(o.reg, o.prov, y1 - 1, 6) / idxAt(o.reg, o.prov, y0 - 1, 6) / v1 - 1;
    if (!byF.has(o.fsa)) byF.set(o.fsa, { city: o.city, e: [] }); byF.get(o.fsa).e.push(e);
  }
  for (const [f, g] of byF) if (g.e.length >= 100) { const s = stats(g.e); out.fsa.push([f, g.city, s.n, s.mdape, s.bias, s.w10]); }
  out.fsa.sort((a, b) => a[0].localeCompare(b[0])); }
out.cities = CITIES;
fs.writeFileSync(path.join(__dirname, "backtest_values.json"), JSON.stringify(out));
console.log(JSON.stringify({ records: total, noHist, with_history: homes.length, kept: keep.length, pairs: pairs.length }, null, 1));
console.log(Object.entries(out.groups).map(([c, v]) => `${c}: index ${v.methods.index.mdape} flat ${v.methods.flat.mdape} local ${v.methods.local && v.methods.local.mdape} xs ${v.xs.all && v.xs.all.mdape} n=${v.methods.index.n}`).join("\n"));
console.log(out.calib.map(r => `${r.city} ${r.from}->${r.to} actual ${(r.actual * 100).toFixed(1)}% index ${(r.index * 100).toFixed(1)}%`).join("\n"));
