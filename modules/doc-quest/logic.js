(function (root) {
  const LIB = (typeof module !== "undefined") ? require("./docs.js") : DOCS; // global const from docs.js
  // answers: { work: salaried|hourly|commission|self, sources: [savings,fhsa,rrsp,gift], newcomer: bool, ownOther: bool, partner: bool }
  function listFor(a) {
    return LIB.filter(d => d.when(a));
  }
  // Slow ones first (things you have to ask someone for), then by section; papers for after the offer go last.
  function ordered(a) {
    const groups = ["You", "Income", "Debts", "Down payment", "The home"];
    return listFor(a).slice().sort((x, y) =>
      (x.later ? 1 : 0) - (y.later ? 1 : 0) ||
      (y.wait > 0 ? 1 : 0) - (x.wait > 0 ? 1 : 0) ||
      groups.indexOf(x.group) - groups.indexOf(y.group));
  }
  function nextUp(a, done, n) {
    return ordered(a).filter(d => !d.later && !done[d.id]).slice(0, n || 3);
  }
  function progress(a, done) {
    const now = listFor(a).filter(d => !d.later);
    const left = now.filter(d => !done[d.id]);
    return { total: now.length, done: now.length - left.length, minutesLeft: left.reduce((s, d) => s + d.minutes, 0) };
  }
  const api = { listFor, ordered, nextUp, progress };
  if (typeof module !== "undefined") module.exports = api; else root.Logic = api;
})(this);
