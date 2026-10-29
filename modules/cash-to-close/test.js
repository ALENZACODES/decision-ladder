const assert = require("assert");
const C = require("./calc.js");
const near = (a, b, m) => assert.ok(Math.abs(a - b) < 0.01, `${m}: ${a} vs ${b}`);
// Ontario LTT on $368,000 equals the $4,000 refund (ontario.ca rounds this to "the first $368,000")
near(C.bracketTax(368000, require("./rates.js").ontarioLtt.brackets), 3995, "LTT 368k"); near(C.bracketTax(368333.33, require("./rates.js").ontarioLtt.brackets), 4000, "LTT refund cap point");
// Toronto MLTT full rebate up to $400,000 ($4,475)
near(C.bracketTax(400000, require("./rates.js").torontoMltt.brackets), 4475, "MLTT 400k");
// $850,000: 275 + 1,950 + 2,250 + 9,000 = 13,475
near(C.bracketTax(850000, require("./rates.js").ontarioLtt.brackets), 13475, "LTT 850k");
// Toronto $3.5M: 2M part = 36,475 ; +1M*2.5% = 25,000 ; +0.5M*4.4% = 22,000
near(C.bracketTax(3500000, require("./rates.js").torontoMltt.brackets), 36475 + 25000 + 22000, "MLTT 3.5M");
// min down
near(C.minDown(400000), 20000, "min 400k"); near(C.minDown(700000), 45000, "min 700k"); near(C.minDown(1500000), 300000, "min 1.5M");
// CMHC tiers
near(C.cmhcRate(0.95, false), 0.04, "95"); near(C.cmhcRate(0.90, false), 0.031, "90"); near(C.cmhcRate(0.85, true), 0.030, "85+30");
assert.strictEqual(C.cmhcRate(0.80, false), 0);
// Full plan: $700k Toronto first-time, minimum down $45k, 25 yr
const p = C.plan({ price: 700000, savings: 60000, down: 45000, toronto: true, firstTime: true, amort30: false,
  deposit: 35000, inspection: 500, legal: 2000, title: 400, adjustments: 1000, moving: 1500 });
near(p.loan, 655000, "loan"); near(p.premium, 26200, "premium 4% of 655k"); near(p.pst, 2096, "pst 8%");
near(p.lttGross, 10475, "ltt 700k"); near(p.lttRefund, 4000, "refund"); near(p.mlttRebate, 4475, "rebate");
near(p.cashToClose, 45000 + 500 + 2400 + 6475 + 6000 + 2096 + 1000 + 1500, "cash to close");
assert.ok(p.gap < 0, "short");
// 20% down: no premium, no PST
const q = C.plan({ price: 700000, savings: 200000, down: 140000, toronto: false, firstTime: false, deposit: 35000 });
assert.strictEqual(q.premium, 0); assert.strictEqual(q.pst, 0); assert.strictEqual(q.mlttGross, 0);
// 30-year only for first-time insured buyers
const r = C.plan({ price: 500000, down: 25000, firstTime: false, amort30: true });
assert.strictEqual(r.amort30, false); near(r.rate, 0.04, "repeat buyer no surcharge");
console.log("all tests pass");
