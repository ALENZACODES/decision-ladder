// Node bridge: lets the Python OS call the real calculator code of the author's JavaScript apps.
//
//   node bridge.mjs <module> <function> '<json args>'      -> prints {"ok": true, "result": ...}
//   node bridge.mjs --list                                 -> prints the callable functions
//
// Every function below loads the module's own source file from modules/<repo>/ and calls its exported
// function. The only logic here is argument plumbing (defaults the app's own UI uses, field selection).
// No mortgage math is re-implemented in this file.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import vm from "node:vm";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODS = path.resolve(HERE, "..", "..", "modules");
const req = createRequire(import.meta.url);
const load = (repo, file) => req(path.join(MODS, repo, file));            // UMD/CommonJS files
const loadEsm = (repo, file) => import(pathToFileURL(path.join(MODS, repo, file)).href);

// Browser-global script (e.g. window.SAMPLES = {...}) evaluated in a sandbox.
function loadGlobal(repo, file) {
  const window = {};
  const ctx = vm.createContext({ window, globalThis: {} });
  vm.runInContext(readFileSync(path.join(MODS, repo, file), "utf8"), ctx, { filename: file });
  return window;
}

const pick = (o, keys) => Object.fromEntries(keys.filter((k) => o[k] !== undefined).map((k) => [k, o[k]]));

const FUNCS = {
  // ---------------------------------------------------------------- cash-to-close (Ontario)
  "cash-to-close.plan": (a) => {
    const C = load("cash-to-close", "calc.js");
    const R = load("cash-to-close", "rates.js");
    const T = R.typical;
    const price = +a.price;
    // Same defaults as the app's own state (app.js): minimum down, 5% deposit, typical costs.
    const down = a.down != null ? +a.down : Math.ceil(C.minDown(price));
    const res = C.plan({
      price, savings: +a.savings || 0, down,
      toronto: !!a.toronto, firstTime: !!a.first_time, amort30: !!a.amort30,
      deposit: a.deposit != null ? +a.deposit : Math.round(price * T.depositPct),
      inspection: a.inspection ?? T.inspection, legal: a.legal ?? T.legal, title: a.title ?? T.titleInsurance,
      adjustments: a.adjustments ?? T.adjustments, moving: a.moving ?? T.moving,
    });
    res.items = res.items.filter((i) => !i.hidden).map((i) => pick(i, ["label", "amount", "kind", "gross", "credit", "approx"]));
    res.rates_checked = R.checked;
    return res;
  },

  // ---------------------------------------------------------------- canadian-mortgage-suite (14 calculators)
  "canadian-mortgage-suite.landTransferTax": (a) => load("canadian-mortgage-suite", "calc.js").landTransferTax(a),
  "canadian-mortgage-suite.closingCosts": (a) => load("canadian-mortgage-suite", "calc.js").closingCosts(a),
  "canadian-mortgage-suite.affordability": (a) => load("canadian-mortgage-suite", "calc.js").affordability(a),
  "canadian-mortgage-suite.insurancePremium": (a) => load("canadian-mortgage-suite", "calc.js").insurancePremium(a),
  "canadian-mortgage-suite.refinance": (a) => load("canadian-mortgage-suite", "calc.js").refinance(a),
  "canadian-mortgage-suite.downPaymentPlan": (a) => load("canadian-mortgage-suite", "calc.js").downPaymentPlan(a),
  "canadian-mortgage-suite.fthbGstRebate": (a) => ({ rebate: load("canadian-mortgage-suite", "calc.js").fthbGstRebate(+a.price) }),
  "canadian-mortgage-suite.rentVsBuy": (a) => load("canadian-mortgage-suite", "calc.js").rentVsBuy(a),

  // ---------------------------------------------------------------- mortgage-decision-lab
  "mortgage-decision-lab.rentVsBuy": (a) => {
    const rows = load("mortgage-decision-lab", "calc.js").rentVsBuy(a);
    const last = rows[rows.length - 1];
    return { years: rows, final: last, winner: last.buyNW >= last.rentNW ? "Buy" : "Rent", gap: last.buyNW - last.rentNW };
  },
  "mortgage-decision-lab.prepay": (a) => load("mortgage-decision-lab", "calc.js").prepay(a),
  "mortgage-decision-lab.canadaVsUS": (a) => load("mortgage-decision-lab", "calc.js").canadaVsUS(a),

  // ---------------------------------------------------------------- pre-underwriting-copilot
  "pre-underwriting-copilot.review": (a) => {
    const E = load("pre-underwriting-copilot", "engine.js");
    let text = a.text;
    if (!text && a.sample) text = loadGlobal("pre-underwriting-copilot", "samples.js").SAMPLES[a.sample];
    if (!text) throw new Error("text (or sample: clean|messy) is required");
    const res = E.review(text);
    res.memo = E.memo(res).join("\n");
    return res;
  },
  "pre-underwriting-copilot.samples": () => loadGlobal("pre-underwriting-copilot", "samples.js").SAMPLES,

  // ---------------------------------------------------------------- private-credit-screener
  "private-credit-screener.screen": (a) => {
    const C = load("private-credit-screener", "calc.js");
    const d = {
      loan: +a.loan, value: +a.value, noi: +a.noi, rate: +a.rate, amort: +(a.amort || 0), termYrs: +(a.termYrs || 2),
      capRate: +(a.capRate ?? (a.noi / a.value) * 100), exitCapShift: +(a.exitCapShift || 0),
      noiGrowth: +(a.noiGrowth || 0), fees: +(a.fees || 0), sponsorScore: +(a.sponsorScore || 3),
    };
    const s = C.score(d);
    return { inputs: d, grade: s.grade, total: s.total, parts: s.parts, metrics: s.metrics, sensitivity: C.tornado(d) };
  },

  // ---------------------------------------------------------------- renewal-check (ESM)
  "renewal-check.check": async (a) => {
    const M = await loadEsm("renewal-check", "src/mortgage.js");
    const args = { balance: +a.balance, years: +a.years, currentRate: +a.currentRate, offerRate: +a.offerRate };
    const errors = M.validate(args);
    if (Object.keys(errors).length) return { errors };
    const R = await loadEsm("renewal-check", "src/rates.js");
    return { ...M.check(args), posted_latest: R.LATEST, posted_as_of: R.ASOF };
  },
  "renewal-check.penalty": async (a) => (await loadEsm("renewal-check", "src/mortgage.js")).penalty(a),

  // ---------------------------------------------------------------- renewal-shock-radar
  "renewal-shock-radar.shock": (a) => {
    const C = load("renewal-shock-radar", "calc.js");
    const o = pick(a, ["loan", "origRate", "amort", "term", "newRate", "income"]);
    const r = C.shock(o);
    r.band = C.band(r.pct);
    const rates = a.curveRates || [o.newRate - 1, o.newRate - 0.5, o.newRate, o.newRate + 0.5, o.newRate + 1].map((x) => +x.toFixed(2));
    const pcts = C.curve(o, rates);
    r.curve = rates.map((x, i) => ({ rate: x, pct: pcts[i] }));
    return r;
  },

  // ---------------------------------------------------------------- doc-quest
  "doc-quest.checklist": (a) => {
    const L = load("doc-quest", "logic.js");
    const ans = { work: a.work || "salaried", sources: a.sources || ["savings"], newcomer: !!a.newcomer,
                  ownOther: !!a.ownOther, partner: !!a.partner };
    const done = Object.fromEntries((a.done || []).map((id) => [id, true]));
    const keep = ["id", "title", "jargon", "plain", "where", "minutes", "wait", "group", "later"];
    return {
      answers: ans,
      documents: L.ordered(ans).map((d) => pick(d, keep)),
      next_up: L.nextUp(ans, done, a.n || 3).map((d) => pick(d, keep)),
      progress: L.progress(ans, done),
    };
  },

  // ---------------------------------------------------------------- canada-rate-cycle-dashboard
  "canada-rate-cycle-dashboard.series": (a) => {
    // Same extraction the repo's own test uses on src/data.js (embedded Bank of Canada Valet series).
    const js = readFileSync(path.join(MODS, "canada-rate-cycle-dashboard", "src", "data.js"), "utf8");
    const rows = JSON.parse(js.slice(js.indexOf("["), js.lastIndexOf("]") + 1));
    const from = a.from || rows[0].m, to = a.to || rows[rows.length - 1].m;
    const win = rows.filter((r) => r.m >= from && r.m <= to);
    const ext = (k, f) => {
      const v = win.filter((r) => r[k] != null);
      if (!v.length) return null;
      const r = v.reduce((x, y) => (f(y[k], x[k]) ? y : x));
      return { month: r.m, value: r[k] };
    };
    const first = win[0], last = win[win.length - 1];
    const summary = {};
    for (const k of ["policy", "inflation", "mortgage", "usdcad"]) {
      summary[k] = { start: first?.[k] ?? null, end: last?.[k] ?? null, max: ext(k, (a, b) => a > b), min: ext(k, (a, b) => a < b) };
    }
    return { from, to, months: win.length, summary, rows: a.rows ? win : undefined,
             source: "Bank of Canada Valet (policy rate, CPI, 5-year conventional mortgage, USD/CAD), monthly" };
  },
  // ---------------------------------------------------------------- quiet-charges (bank statement recurring charges)
  "quiet-charges.scan": async (a) => {
    const Q = await loadEsm("quiet-charges", "src/engine.js");
    const text = a.csv ?? readFileSync(path.join(MODS, "quiet-charges", "src", "sample.csv"), "utf8");
    const txns = Q.toTransactions(Q.parseCSV(text));
    const today = a.today ? new Date(a.today) : new Date();
    const subs = Q.findRecurring(txns, { today });
    const s = Q.summarize(subs);
    const r2 = (x) => Math.round(x * 100) / 100;
    return {
      transactions: txns.length, sample: a.csv == null,
      active_recurring: s.count, monthly: r2(s.monthly), annual: r2(s.annual), raised: s.raised, raised_cost_per_year: r2(s.raisedCost),
      recurring: subs.map((x) => ({ name: x.name, cadence: x.cadence, count: x.count, last: x.last, monthly: r2(x.annual / 12),
        annual: r2(x.annual), active: x.active, price_increases: x.increases.length, confidence: x.confidence,
        last_date: x.lastDate.toISOString().slice(0, 10) })),
    };
  },

  // ---------------------------------------------------------------- shoebox (T2125 expense lines, keyword baseline)
  "shoebox.lines": (a) => {
    const L = load("shoebox", "logic.js");
    const LINES = load("shoebox", "lines.js");
    const text = a.csv ?? readFileSync(path.join(MODS, "shoebox", "sample.csv"), "utf8");
    const txs = L.parseCSV(text);
    let income = 0, unmatched = 0;
    for (const t of txs) {
      if (t.inflow) { if (L.isRefund(t.desc)) { t.refund = true; t.line = L.keyword(t.desc, LINES) || "8810"; } else { t.line = "income"; income += t.amount; } continue; }
      t.line = L.keyword(t.desc, LINES);
      if (!t.line) { t.line = "9270"; unmatched++; }
    }
    const tot = L.totals(txs, LINES, a.pct || {});
    return {
      transactions: txs.length, sample: a.csv == null, classifier: "keyword baseline (the app's in-browser MiniLM classifier is not run server-side)",
      income_in: Math.round(income * 100) / 100, unmatched_to_other: unmatched, deductible: tot.deductible, needs_business_use_pct: tot.missing,
      by_line: tot.byLine.filter((o) => o.n).map((o) => ({ line: o.id, name: o.name, spent: o.spent, claim: o.claim, n: o.n })),
    };
  },
};

async function main() {
  const [mod, fn, raw] = process.argv.slice(2);
  if (mod === "--list") {
    process.stdout.write(JSON.stringify(Object.keys(FUNCS)));
    return;
  }
  const key = `${mod}.${fn}`;
  if (!FUNCS[key]) {
    process.stdout.write(JSON.stringify({ ok: false, error: `unknown function ${key}`, available: Object.keys(FUNCS) }));
    return;
  }
  try {
    const args = raw ? JSON.parse(raw) : {};
    const result = await FUNCS[key](args);
    process.stdout.write(JSON.stringify({ ok: true, result }, (k, v) => (typeof v === "number" && !isFinite(v) ? null : v)));
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: `${e.name}: ${e.message}` }));
  }
}
main();
