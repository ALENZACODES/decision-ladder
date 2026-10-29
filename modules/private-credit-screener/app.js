(function () {
  const $ = (s) => document.querySelector(s),
    C = window.Calc,
    m = (v) => "$" + Math.round(v).toLocaleString("en-CA");
  const F = [
    ["loan", "Loan amount", 1e5],
    ["value", "Appraised value", 1e5],
    ["noi", "Net operating income / yr", 1e4],
    ["rate", "Interest rate %", 0.25],
    ["amort", "Amortization yrs (0 = interest-only)", 1],
    ["termYrs", "Term yrs", 1],
    ["capRate", "Going-in cap rate %", 0.05],
    ["exitCapShift", "Exit cap shift (pts)", 0.05],
    ["noiGrowth", "NOI growth % / yr", 0.25],
    ["fees", "Lender fees % of loan", 0.25],
    ["sponsorScore", "Sponsor score (1 to 5)", 1],
  ];
  const P = {
    "[EXAMPLE] Stabilized industrial, Calgary": {
      loan: 6e6,
      value: 10e6,
      noi: 700000,
      rate: 9.5,
      amort: 0,
      termYrs: 2,
      capRate: 7,
      exitCapShift: 0.25,
      noiGrowth: 2,
      fees: 1.5,
      sponsorScore: 4,
    },
    "[EXAMPLE] Condo inventory loan, Toronto": {
      loan: 14e6,
      value: 18.5e6,
      noi: 900000,
      rate: 11.5,
      amort: 0,
      termYrs: 1,
      capRate: 5,
      exitCapShift: 0.75,
      noiGrowth: 0,
      fees: 2,
      sponsorScore: 3,
    },
    "[EXAMPLE] Mixed-use bridge, Ottawa": {
      loan: 4.2e6,
      value: 6e6,
      noi: 430000,
      rate: 10.25,
      amort: 25,
      termYrs: 3,
      capRate: 6.75,
      exitCapShift: 0.5,
      noiGrowth: 1,
      fees: 1.75,
      sponsorScore: 3,
    },
  };
  const names = Object.keys(P);
  $("#preset").innerHTML = names.map((n) => `<option>${n}</option>`).join("");
  const q = new URLSearchParams(location.hash.slice(1));
  let d = { ...P[names[0]] };
  F.forEach(([k]) => {
    if (q.has(k)) d[k] = +q.get(k);
  });
  function inputs() {
    $("#inputs").innerHTML = F.map(
      ([k, l, s]) => `<label for="f_${k}">${l}</label><input type="number" id="f_${k}" step="${s}" value="${d[k]}">`,
    ).join("");
    document.querySelectorAll("#inputs input").forEach(
      (e) =>
        (e.oninput = () => {
          d[e.id.slice(2)] = +e.value;
          run();
        }),
    );
  }
  function run() {
    const s = C.score(d),
      x = s.metrics;
    history.replaceState(null, "", "#" + new URLSearchParams(d));
    const k = [
      ["Grade", s.grade, s.total + "/100"],
      ["LTV", x.ltv.toFixed(1) + "%", "loan / value", x.ltv <= 70],
      ["DSCR", x.dscr.toFixed(2) + "x", "NOI / debt service", x.dscr >= 1.2],
      ["Debt yield", x.debtYield.toFixed(1) + "%", "NOI / loan", x.debtYield >= 9],
      ["Exit LTV", x.exitLtv.toFixed(1) + "%", "balloon " + m(x.balloon), x.exitLtv <= 75],
      ["Value cushion", x.breakevenValueDrop.toFixed(0) + "%", "drop before loss at exit", x.breakevenValueDrop >= 25],
    ];
    $("#kpis").innerHTML = k
      .map(
        ([l, v, t, ok], i) =>
          `<div class="kpi"><div class="l">${l}</div><div class="${i ? "v" : "grade"} ${ok === true ? "good" : ok === false ? "bad" : ""}">${v}</div><div class="s">${t}</div></div>`,
      )
      .join("");
    const lab = { ltv: "LTV", dscr: "DSCR", dy: "Debt yield", exit: "Exit risk", sponsor: "Sponsor" };
    $("#bars").innerHTML = Object.entries(s.parts)
      .map(
        ([p, v]) =>
          `<div><span>${lab[p]}</span><em><i style="width:${(v * 100).toFixed(0)}%"></i></em><span>${(v * 100).toFixed(0)}</span></div>`,
      )
      .join("");
    const t = C.tornado(d);
    Charts.tornado($("#tornado"), { rows: t, base: s.total, fmt: (v) => v.toFixed(0), title: "Score sensitivity" });
    const top = t[0],
      risks = [];
    if (x.ltv > 70) risks.push(`LTV of ${x.ltv.toFixed(1)}% leaves limited equity cushion.`);
    if (x.dscr < 1.2) risks.push(`DSCR of ${x.dscr.toFixed(2)}x means income barely covers debt service.`);
    if (x.exitLtv > 75) risks.push(`Exit LTV of ${x.exitLtv.toFixed(1)}% creates refinance risk at maturity.`);
    if (d.sponsorScore <= 2) risks.push("Sponsor track record is thin.");
    if (!risks.length) risks.push("No threshold breaches at base case.");
    const L = [
      `IC MEMO [EXAMPLE]: ${$("#preset").value.replace("[EXAMPLE] ", "")}`,
      "",
      `Recommendation: ${s.total >= 75 ? "Proceed to full diligence" : s.total >= 60 ? "Proceed with structural protections" : s.total >= 45 ? "Re-cut terms before proceeding" : "Decline at proposed terms"} (grade ${s.grade}, ${s.total}/100).`,
      "",
      "Terms",
      `  ${m(d.loan)} senior loan at ${d.rate}%, ${d.amort ? d.amort + "-yr amortization" : "interest-only"}, ${d.termYrs}-yr term, ${d.fees}% fees. All-in yield about ${x.allInYield.toFixed(2)}%.`,
      "",
      "Credit metrics",
      `  LTV ${x.ltv.toFixed(1)}%, DSCR ${x.dscr.toFixed(2)}x, debt yield ${x.debtYield.toFixed(1)}%.`,
      `  Exit value ${m(x.exitValue)} at a ${(d.capRate + d.exitCapShift).toFixed(2)}% cap; exit LTV ${x.exitLtv.toFixed(1)}%. Value can fall ${x.breakevenValueDrop.toFixed(0)}% before principal is at risk.`,
      "",
      "Key risks",
      ...risks.map((r) => "  - " + r),
      "",
      `Largest sensitivity: ${top.label}, moving the score between ${Math.min(top.low, top.high).toFixed(0)} and ${Math.max(top.low, top.high).toFixed(0)}.`,
      "",
      "Suggested protections",
      "  - Cash management trigger if DSCR falls below 1.10x.",
      "  - Interest reserve sized to at least 6 months.",
      "  - Independent appraisal and environmental review before funding.",
      "",
      "Fictional deal for education. Not an offer or recommendation.",
    ];
    const me = $("#memo");
    me.textContent = "";
    L.forEach((l) => {
      me.append(l);
      me.append(document.createElement("br"));
    });
  }
  $("#preset").onchange = () => {
    d = { ...P[$("#preset").value] };
    inputs();
    run();
  };
  $("#share").onclick = () => {
    navigator.clipboard && navigator.clipboard.writeText(location.href);
    $("#share").textContent = "Copied";
    setTimeout(() => ($("#share").textContent = "Copy link"), 1500);
  };
  $("#pdf").onclick = () => window.print();
  inputs();
  run();
})();
