// Every address in the National Address Register packs: which evidence would the page use for it?
//   own   : the home's own assessment record (and history)        best
//   street: real assessment medians for its street
//   block : its 2021 Census block's value, moved to today
//   postal: its postal area's Census value, moved to today
//   region: regional benchmark only                                worst
const fs = require("fs"), path = require("path");
const P = require("./pagecode.js");
const D = path.join(__dirname, "..", "data");
const J = f => { try { return JSON.parse(fs.readFileSync(path.join(D, f))); } catch (e) { return null; } };
const fsaInfo = J("fsa.json"), detIdx = J("detail/index.json");
const fileOf = {}; for (const [k, fs_] of Object.entries(detIdx)) for (const f of fs_) fileOf[f] = k;
const det = {}, streets = {}, da = {};
for (const f of fs.readdirSync(D)) { const m = f.match(/^da_(\d+)\.json$/); if (m) Object.assign(da, J(f)); }
const skCache = new Map(), sk = s => { let v = skCache.get(s); if (v === undefined) { v = P.streetKey(s); skCache.set(s, v); } return v; };
const tyCache = new Map(), ty = s => { let v = tyCache.get(s); if (v === undefined) { v = P.stype(s); tyCache.set(s, v); } return v; };
const PROVL = { A: "NL", B: "NS", C: "PE", E: "NB", G: "QC", H: "QC", J: "QC", K: "ON", L: "ON", M: "ON", N: "ON", P: "ON", R: "MB", S: "SK", T: "AB", V: "BC", X: "NT", Y: "YT" };
const tot = { own: 0, street: 0, block: 0, postal: 0, region: 0 }, byProv = {}, byCityL = {};
let n = 0;
const packs = fs.readdirSync(path.join(D, "addr")).filter(f => /^p\d+\.json$/.test(f));
for (const pf of packs) {
  const pk = J("addr/" + pf);
  for (const [fsa, rows] of Object.entries(pk)) {
    if (fsa === "_c") continue;
    const prov = /^X0[ABC]/.test(fsa) ? "NU" : PROVL[fsa[0]];
    const file = fileOf[fsa]; if (file && !det[file]) det[file] = J("detail/" + file + ".json") || {};
    const d = file ? (det[file][fsa] || {}) : null;
    const L = fsa[0]; if (!(L in streets)) streets[L] = J("streets_" + L + ".json") || {};
    const sf = streets[L][fsa] || null, fi = fsaInfo[fsa];
    for (const [street, ci, data] of rows) {
      const key = sk(street), t = ty(street), hasStreet = !!(sf && sf[key]);
      for (const seg of data.split(";")) {
        const [tag, civs] = seg.split(":"); const daCode = tag.split("@")[1];
        const hasBlock = !!(daCode && da[daCode]);
        for (const tok of civs.split(" ")) {
          if (!tok) continue; n++;
          const [u, c] = tok.includes("/") ? tok.split("/") : ["", tok];
          let tier;
          if (d && (d[`${P.normNum(u)}|${P.normNum(c)}|${key}|${t}`] || (!u && d[`|${P.normNum(c)}|${key}|${t}`]))) tier = "own";
          else if (hasStreet) tier = "street";
          else if (hasBlock) tier = "block";
          else if (fi && fi.c) tier = "postal";
          else tier = "region";
          tot[tier]++;
          (byProv[prov] = byProv[prov] || { own: 0, street: 0, block: 0, postal: 0, region: 0 })[tier]++;
        }
      }
    }
  }
  process.stdout.write(".");
}
const out = { addresses: n, tiers: tot, by_prov: byProv };
fs.writeFileSync(path.join(__dirname, "coverage.json"), JSON.stringify(out));
console.log("\n" + JSON.stringify(out, null, 1));
