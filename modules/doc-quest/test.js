const assert = require("assert"); const L = require("./logic.js"); const DOCS = require("./docs.js");
const base = { work: "salaried", sources: ["savings"], newcomer: false, ownOther: false, partner: false };
const ids = a => L.listFor(a).map(d => d.id);
assert.deepStrictEqual(ids(base).sort(), ["aps","bank90","debts","deposit","id","joblet","pad","paystub"].sort());
assert.ok(ids({ ...base, work: "self" }).includes("t1") && !ids({ ...base, work: "self" }).includes("joblet"));
assert.ok(ids({ ...base, work: "hourly" }).includes("t4") && ids({ ...base, work: "hourly" }).includes("noa"));
assert.ok(ids({ ...base, sources: ["gift", "fhsa", "rrsp"] }).includes("gift"));
assert.ok(ids({ ...base, newcomer: true }).includes("status"));
// slow items come first; after-offer items never appear in "next up"
const nx = L.nextUp({ ...base, newcomer: true, sources: ["gift"] }, {});
assert.ok(nx[0].wait > 0 && nx.every(d => !d.later));
const p = L.progress(base, { id: true, paystub: true });
assert.strictEqual(p.total, 5); assert.strictEqual(p.done, 2);
// try every combination of answers: nobody is handed the whole pre-offer list
const pre = DOCS.filter(d => !d.later).length; let most = 0;
for (const work of ["salaried","hourly","commission","self"]) for (let m = 0; m < 16; m++) for (const newcomer of [true,false]) for (const ownOther of [true,false]) {
  const sources = ["savings","fhsa","rrsp","gift"].filter((_, i) => m & (1 << i));
  most = Math.max(most, L.listFor({ work, sources, newcomer, ownOther, partner: false }).filter(d => !d.later).length);
}
assert.ok(most < pre, "someone gets every item");
// every doc has the fields the UI needs
DOCS.forEach(d => ["id","jargon","title","plain","simple","where","group"].forEach(k => assert.ok(d[k], d.id + " missing " + k)));
console.log(`all tests pass (largest list: ${most} of ${pre} pre-offer papers)`);
