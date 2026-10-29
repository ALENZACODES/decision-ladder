/* Pure functions, no DOM. Tested in test.js. */
(function (root) {
  const R = (typeof module !== "undefined") ? require("./rates.js") : RATES; // RATES is a global const from rates.js

  function bracketTax(price, brackets) {
    let tax = 0, lower = 0;
    for (const [upper, rate] of brackets) {
      if (price > lower) tax += (Math.min(price, upper) - lower) * rate;
      lower = upper;
    }
    return Math.round(tax * 100) / 100;
  }

  function minDown(price) {
    const m = R.minDown;
    if (price >= m.insuredCap) return price * m.uninsuredPct;
    if (price <= m.firstTier) return price * m.firstPct;
    return m.firstTier * m.firstPct + (price - m.firstTier) * m.secondPct;
  }

  function cmhcRate(ltv, amort30) {
    if (ltv <= 0.80) return 0;
    const t = R.cmhc.tiers.find(t => ltv <= t.maxLtv + 1e-9);
    if (!t) return null; // over 95%: not insurable
    return t.pct + (amort30 ? R.cmhc.surcharge30 : 0);
  }

  // s: { price, savings, down, toronto, firstTime, amort30, deposit, inspection, legal, title, adjustments, moving }
  function plan(s) {
    const price = Math.max(0, +s.price || 0);
    const need = minDown(price);
    const down = Math.max(0, +s.down || 0);
    const loan = Math.max(0, price - down);
    const ltv = price ? loan / price : 0;
    const insured = price < R.minDown.insuredCap && ltv > 0.80;
    const amort30 = !!s.amort30 && !!s.firstTime && insured;
    const rate = insured ? cmhcRate(ltv, amort30) : 0;
    const premium = rate ? Math.round(loan * rate) : 0;
    const pst = Math.round(premium * R.ontarioPstOnPremium.pct * 100) / 100;

    const lttGross = bracketTax(price, R.ontarioLtt.brackets);
    const lttRefund = s.firstTime ? Math.min(lttGross, R.ontarioLtt.firstTimeRefundMax) : 0;
    const mlttGross = s.toronto ? bracketTax(price, R.torontoMltt.brackets) : 0;
    const mlttRebate = s.toronto && s.firstTime ? Math.min(mlttGross, R.torontoMltt.firstTimeRebateMax) : 0;

    const deposit = Math.min(down, Math.max(0, +s.deposit || 0));
    const items = [
      { id: "inspection", label: "Home inspection", when: 0, amount: +s.inspection || 0, kind: "cash", approx: true },
      { id: "deposit", label: "Deposit (part of your down payment)", when: 1, amount: deposit, kind: "cash", down: true },
      { id: "retainer", label: "Lawyer and title insurance", when: 2, amount: (+s.legal || 0) + (+s.title || 0), kind: "cash", approx: true },
      { id: "balance", label: "Rest of your down payment", when: 2, amount: down - deposit, kind: "cash", down: true },
      { id: "ltt", label: "Ontario land transfer tax", when: 2, amount: lttGross - lttRefund, gross: lttGross, credit: lttRefund, kind: "cash" },
      { id: "mltt", label: "Toronto land transfer tax", when: 2, amount: mlttGross - mlttRebate, gross: mlttGross, credit: mlttRebate, kind: "cash", hidden: !s.toronto },
      { id: "pst", label: "Sales tax on mortgage insurance", when: 2, amount: pst, kind: "cash", hidden: !premium },
      { id: "adjust", label: "Adjustments to the seller", when: 2, amount: +s.adjustments || 0, kind: "cash", approx: true },
      { id: "moving", label: "Moving day", when: 4, amount: +s.moving || 0, kind: "cash", approx: true },
      { id: "premium", label: "Mortgage insurance premium", when: 3, amount: premium, kind: "loan", hidden: !premium }
    ];
    const cashItems = items.filter(i => i.kind === "cash" && !i.hidden);
    const cashToClose = Math.round(cashItems.reduce((a, i) => a + i.amount, 0) * 100) / 100;
    const extras = Math.round((cashToClose - down) * 100) / 100;
    const savings = Math.max(0, +s.savings || 0);
    return {
      price, minDown: need, down, belowMin: down + 0.5 < need, loan, ltv, insured, notInsurable: insured && rate === null,
      tooPricey: price >= R.minDown.insuredCap && ltv > 0.80,
      amort30, rate, premium, pst, lttGross, lttRefund, mlttGross, mlttRebate,
      items, cashToClose, extras, savings, gap: Math.round((savings - cashToClose) * 100) / 100,
      extrasPct: down ? extras / down : 0
    };
  }

  const api = { bracketTax, minDown, cmhcRate, plan };
  if (typeof module !== "undefined") module.exports = api; else root.Calc = api;
})(this);
