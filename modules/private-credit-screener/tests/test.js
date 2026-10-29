const C = require("../calc.js"),
  assert = require("assert");
let n = 0;
const near = (a, b, t = 1e-6) => {
  assert(Math.abs(a - b) <= t, a + " vs " + b);
  n++;
};
near(C.annualDebtService(1e6, 10, 0), 100000);
near(C.annualDebtService(120000, 0.000001, 10), 12000, 0.1);
const d = {
  loan: 6e6,
  value: 10e6,
  noi: 700000,
  rate: 10,
  amort: 0,
  termYrs: 2,
  capRate: 7,
  exitCapShift: 0,
  noiGrowth: 0,
  fees: 2,
  sponsorScore: 4,
};
const m = C.metrics(d);
near(m.ltv, 60);
near(m.ds, 600000);
near(m.dscr, 700000 / 600000);
near(m.debtYield, (700000 / 6e6) * 100);
near(m.balloon, 6e6);
near(m.exitValue, 10e6, 1e-3);
near(m.exitLtv, 60, 1e-6);
near(m.breakevenValueDrop, 40, 1e-6);
near(m.allInYield, 11);
const am = C.metrics({ ...d, amort: 25 });
assert(am.balloon < 6e6 && am.ds > 600000);
n++;
const s = C.score(d);
assert(s.total >= 0 && s.total <= 100);
n++;
const worse = C.score({ ...d, loan: 8.5e6 });
assert(worse.total < s.total);
n++;
assert(C.score({ ...d, exitCapShift: 1 }).total <= s.total);
n++;
const t = C.tornado(d);
assert.equal(t.length, 7);
n++;
for (let i = 1; i < t.length; i++) assert(t[i - 1].swing >= t[i].swing);
n++;
assert(["A", "B", "C", "D"].includes(s.grade));
n++;
console.log("private-credit-screener: " + n + " assertions passed");
