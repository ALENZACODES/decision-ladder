// Load the page's own price-index and address-normalising code into Node, so the backtest
// uses exactly the functions the page runs (no re-implementation drift).
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const script = html.slice(html.indexOf('"use strict";'), html.lastIndexOf("</script>"));
function slice(from, to) {
  const a = script.indexOf(from), b = script.indexOf(to, a);
  if (a < 0 || b < 0) throw new Error("marker not found: " + from + " / " + to);
  return script.slice(a, b);
}
const src = [
  slice("const ANCH=", "/* ---------- Five-year fixed rate history"),
  slice("const RATE=", "function seriesFor("),
  // address normalisation helpers
  slice("const TYPEWORDS=", "const title="),
  slice("const normNum=", "let DETIDX=null;"),
  slice("const STYPE=", "async function detailFor("),
].join("\n");
const api = new Function(src + `
  ;return {ANCH,REGION_NAME,MONTHS,IDX,mi,plain,streetKey,normNum,stype,TYPEWORDS,DIRS};`)();
module.exports = api;
if (require.main === module) {
  console.log(Object.keys(api.IDX), api.MONTHS.length, api.streetKey("134 ST NW"), api.stype("MAIN ST"), api.normNum("0012"));
}
