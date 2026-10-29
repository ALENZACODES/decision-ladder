// Field spec: [name, label, type, default, extra]. Dotted names nest (request.equipment -> {request:{equipment}}).
// type: n number, i integer, s text, b checkbox, sel select (extra = options), rows textarea "a,b" lines (extra = keys)
const DESKS = [
  { tool: "csbfp_assess", title: "CSBFP eligibility & limits",
    blurb: "Revenue-cap screen and eligible amounts by asset class under the Canada Small Business Financing Program.",
    fields: [["gross_annual_revenue","Gross annual revenue ($)","n",3500000],["farming","Farming business","b",false],
      ["request.real_property","Real property ($)","n",400000],["request.equipment","Equipment ($)","n",350000],
      ["request.leasehold_improvements","Leasehold improvements ($)","n",250000],["request.intangible_assets","Intangible assets ($)","n",0],
      ["request.working_capital","Working capital ($)","n",100000],["request.line_of_credit","Line of credit ($)","n",150000],
      ["existing_term_outstanding","Existing CSBFP term loans ($)","n",0]] },
  { tool: "csbfp_term_loan", title: "CSBFP term loan cost",
    blurb: "Payment, 2% registration fee, all-in APR and the program's maximum rate.",
    fields: [["amount","Loan amount ($)","n",300000],["annual_rate_pct","Contract rate (%)","n",7.45],["years","Term (years, max 15)","n",10],
      ["rate_kind","Rate type","sel","floating",["floating","fixed"]],["prime_pct","Lender prime (%)","n",4.45],
      ["residential_rate_pct","Lender residential rate for term (%, fixed)","n",null],
      ["finance_registration_fee","Finance the registration fee","b",true],["other_fees","Other fees at funding ($)","n",0]] },
  { tool: "csbfp_line_of_credit", title: "CSBFP line of credit",
    blurb: "Up to $150,000 for up to 5 years: maximum rate check (prime + 5) and annual cost with the 2% registration fee.",
    fields: [["authorized","Authorized amount ($)","n",150000],["average_drawn","Average drawn ($)","n",60000],
      ["annual_rate_pct","Rate (%)","n",9.45],["prime_pct","Lender prime (%)","n",4.45],["years","Registration period (years)","n",5],
      ["standby_fee_pct","Standby fee on undrawn (%)","n",0]] },
  { tool: "invoice_factoring", title: "Invoice factoring",
    blurb: "Advance, discount fee, reserve release and effective annual cost from the cash timing. Fill the ledger box to cost a batch.",
    fields: [["face","Invoice face ($)","n",25000],["days_to_collect","Expected days to collect","n",45],
      ["advance_rate_pct","Advance rate (%)","n",85],["fee_type","Fee type","sel","per_period",["per_period","flat","tiered"]],
      ["fee_pct","Fee (%) per period / flat / per extra period","n",2],["period_days","Days per period","i",30],
      ["prorate","Pro-rate fee by day","b",false],["fee_basis","Fee charged on","sel","face",["face","advance"]],
      ["tiers","Tiers: up_to_days,fee_pct per line","rows","",["up_to_days","fee_pct"]],
      ["recourse","Recourse","b",true],["recourse_days","Recourse after (days)","i",90],
      ["non_recourse_premium_pct","Non-recourse premium (% of face)","n",0],["upfront_fees","Upfront fee per invoice ($)","n",0],
      ["invoices","Ledger: face,days_to_collect per line (optional)","rows","",["face","days_to_collect"]]] },
  { tool: "unsecured_term_loan", title: "Unsecured term loan",
    blurb: "Level payment, total cost and APR with fees in the rate; criminal-rate check.",
    fields: [["principal","Principal ($)","n",75000],["annual_rate_pct","Contract rate (%)","n",16.5],["years","Term (years)","n",3],
      ["payments_per_year","Payments per year","i",12],["upfront_fees","Fees deducted from advance ($)","n",2250],
      ["financed_fees","Fees added to loan ($)","n",0],["borrower_is_natural_person","Borrower is an individual / sole proprietor","b",false],
      ["business_purpose","Business purpose","b",true]] },
  { tool: "business_line_of_credit", title: "Business line of credit",
    blurb: "Annual cost on the average drawn balance, including standby and fixed fees.",
    fields: [["limit","Limit ($)","n",100000],["average_drawn","Average drawn ($)","n",40000],["annual_rate_pct","Rate (%)","n",9.95],
      ["standby_fee_pct","Standby fee on undrawn (%)","n",0.5],["annual_fee","Annual fee ($)","n",500],["setup_fee","Setup fee ($)","n",0],
      ["expected_years","Expected life (years)","n",1],["borrower_is_natural_person","Borrower is an individual","b",false]] },
  { tool: "merchant_cash_advance", title: "Merchant cash advance",
    blurb: "Implied APR of a factor-rate advance repaid by daily remittances. Give expected days, or holdback with daily sales.",
    fields: [["advance","Advance ($)","n",50000],["factor_rate","Factor rate","n",1.35],["expected_remittance_days","Expected remittance days","i",120],
      ["holdback_pct","Holdback (%) (if no days)","n",null],["expected_daily_sales","Expected daily sales ($)","n",null],
      ["fees","Fees deducted ($)","n",0],["days_per_week","Remittance days per week","i",5],
      ["sensitivity_days","Sensitivity: remittance days, comma separated","s","60,90,120,180"],
      ["borrower_is_natural_person","Borrower is an individual","b",false]] },
  { tool: "criminal_rate_check", title: "Criminal rate check",
    blurb: "Compare an all-in APR with the s.347 ceiling that applies (35%; 48% commercial band; none over $500k).",
    fields: [["apr_pct","All-in APR (%)","n",42],["credit_advanced","Credit advanced, net of fees ($)","n",60000],
      ["borrower_is_natural_person","Borrower is an individual","b",false],["business_purpose","Business purpose","b",true]] },
  { tool: "business_dscr", title: "DSCR & borrowing capacity",
    blurb: "Normalized EBITDA, cash available for debt service, business and global DSCR, and the largest new loan at the target.",
    fields: [["net_income","Net income ($/yr)","n",280000],["interest_expense","Interest expense","n",45000],["income_taxes","Income taxes","n",55000],
      ["depreciation_amortization","Depreciation & amortization","n",70000],["add_backs","Add-backs: label,amount per line","rows","",["label","amount"]],
      ["owner_compensation_paid","Owner pay in expenses","n",null],["market_compensation","Market salary for role","n",null],
      ["unfunded_capex","Unfunded capex","n",20000],["distributions","Distributions / draws","n",0],
      ["existing_business_debt_service","Existing business debt service ($/yr)","n",120000],
      ["target_dscr","Target DSCR","n",1.25],["new_loan_rate_pct","New loan rate (%)","n",7.5],["new_loan_amort_years","New loan amortization (yrs)","n",10],
      ["proposed_loan.amount","Proposed loan ($, optional)","n",null],["proposed_loan.annual_rate_pct","Proposed rate (%)","n",null],
      ["proposed_loan.amort_years","Proposed amortization (yrs)","n",null],
      ["owner.personal_income","Owner personal income ($/yr, optional)","n",null],["owner.personal_taxes","Owner personal taxes","n",null],
      ["owner.living_expenses","Owner living expenses","n",null],["owner.personal_debt_service","Owner personal debt service","n",null]] },
  { tool: "equipment_lease_vs_buy", title: "Equipment lease vs buy",
    blurb: "After-tax NPV with CCA; positive net advantage to leasing means lease.",
    fields: [["cost","Equipment cost ($)","n",120000],["lease_payment","Lease payment ($/period)","n",2350],["lease_term_years","Lease term (years)","i",5],
      ["lease_payments_per_year","Lease payments per year","i",12],["lease_in_advance","Payments in advance","b",true],
      ["borrow_rate_pct","Pre-tax loan rate (%)","n",7.5],["tax_rate_pct","Tax rate (%)","n",26.5],["cca_rate_pct","CCA class rate (%)","n",30],
      ["salvage_value","Salvage at end ($)","n",20000],["buy_annual_operating_cost","Owner-paid costs the lease includes ($/yr)","n",0],
      ["acquired","Acquired (YYYY-MM-DD)","s","2026-11-15"],["available_for_use","Available for use (YYYY-MM-DD)","s","2026-12-01"],
      ["first_year_factor_override","First-year factor override (0.5/1/1.5)","n",null]] },
];

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let current = 0;

function fieldHtml([name, label, type, def, extra]) {
  const id = "f_" + name.replace(/\./g, "_");
  if (type === "b") return `<div class="check"><label><input type="checkbox" id="${id}" ${def ? "checked" : ""}>${esc(label)}</label></div>`;
  let input;
  if (type === "sel") input = `<select id="${id}">${extra.map(o => `<option ${o === def ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  else if (type === "rows") input = `<textarea id="${id}" placeholder="${extra.join(",")}">${esc(def || "")}</textarea>`;
  else input = `<input id="${id}" ${type === "s" ? "" : 'type="number" step="any"'} value="${def ?? ""}">`;
  return `<label for="${id}">${esc(label)}</label>${input}`;
}

function showForm(i) {
  current = i;
  const d = DESKS[i];
  [...$("#tabs").children].forEach((b, k) => b.setAttribute("aria-selected", k === i));
  $("#form-card").innerHTML = `<h2>${esc(d.title)}</h2><p class="blurb">${esc(d.blurb)}</p>
    <form id="calc">${d.fields.map(fieldHtml).join("")}<button class="run" type="submit">Calculate</button></form>`;
  $("#calc").addEventListener("submit", e => { e.preventDefault(); run(); });
}

function setPath(obj, path, v) {
  const keys = path.split(".");
  let o = obj;
  keys.slice(0, -1).forEach(k => (o = o[k] ??= {}));
  o[keys.at(-1)] = v;
}

function collect(d) {
  const args = {};
  for (const [name, , type, , extra] of d.fields) {
    const el = $("#f_" + name.replace(/\./g, "_"));
    let v;
    if (type === "b") v = el.checked;
    else if (type === "rows") {
      const lines = el.value.split("\n").map(l => l.trim()).filter(Boolean);
      if (!lines.length) continue;
      v = lines.map(l => { const p = l.split(","), o = {};
        extra.forEach((k, j) => { const x = (p[j] ?? "").trim(); o[k] = k === "label" ? x : Number(x); }); return o; });
    } else {
      if (el.value.trim() === "") continue;
      v = type === "s" ? el.value.trim() : Number(el.value);
      if (name === "sensitivity_days") v = el.value.split(",").map(Number).filter(n => n > 0);
    }
    setPath(args, name, v);
  }
  return args;
}

const money = v => typeof v === "number" ? v.toLocaleString("en-CA", {maximumFractionDigits: 2}) : v;
const label = k => k.replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/\bapr\b/, "APR").replace(/\bear\b/, "EAR")
                    .replace(/\bdscr\b/, "DSCR").replace(/\bcads\b/, "CADS");

function table(obj) {
  const rows = Object.entries(obj).filter(([k, v]) => v !== null && typeof v !== "object" && k !== "engine");
  return rows.length ? `<table>${rows.map(([k, v]) =>
    `<tr><td>${esc(label(k))}</td><td class="num">${esc(typeof v === "boolean" ? (v ? "yes" : "no") : money(v))}</td></tr>`).join("")}</table>` : "";
}

function listTable(rows) {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]);
  return `<table><tr>${cols.map(c => `<th>${esc(label(c))}</th>`).join("")}</tr>${rows.map(r =>
    `<tr>${cols.map(c => `<td class="num">${esc(money(r[c]))}</td>`).join("")}</tr>`).join("")}</table>`;
}

function flags(r) {
  const out = [], cr = r.criminal_rate || (r.engine === "business.usury.check" ? r : null);
  if (cr) {
    const cls = cr.exceeds_criminal_rate ? "bad" : cr.flag ? "warn" : "ok";
    out.push(`<div class="flag ${cls}">${esc(cr.flag || `Within the criminal rate: ${cr.regime}`)}
      ${cr.cap_apr_pct != null ? ` (cap ${cr.cap_apr_pct}% APR, this ${cr.apr_pct}%)` : " (no ceiling)"}</div>`);
    if (cr.characterization) out.push(`<p class="src">${esc(cr.characterization)}</p>`);
  }
  if (r.within_max_rate === false) out.push(`<div class="flag bad">Contract rate is above the CSBFP maximum of ${r.max_rate_pct}%</div>`);
  if (r.passes_target === false) out.push(`<div class="flag warn">Pro forma DSCR is below the ${r.target_dscr} target</div>`);
  if (r.decision) out.push(`<div class="flag ok">Decision: ${esc(r.decision)} (net advantage to leasing $${money(r.net_advantage_to_leasing)})</div>`);
  if (r.eligibility) out.push(`<div class="flag ${r.eligibility.eligible ? "ok" : "bad"}">${r.eligibility.eligible ? "Eligible for CSBFP"
      : "Not eligible: " + esc(r.eligibility.reasons.join("; "))}</div>`);
  return out.join("");
}

function sources(r) {
  const s = [].concat(r.source || [], r.criminal_rate?.source || []);
  const urls = [...new Map(s.filter(x => x && x.url).map(x => [x.url, x])).values()];
  const asm = Object.assign({}, r.assumptions || {}, r.criminal_rate?.assumptions || {});
  return (urls.length ? `<p class="src">Sources: ${urls.map(u => `<a href="${esc(u.url)}" target="_blank" rel="noopener">${esc(u.url)}</a> (checked ${esc(u.checked)})`).join("; ")}</p>` : "")
    + (typeof r.source === "string" ? `<p class="src">Source: ${esc(r.source)}</p>` : "")
    + (Object.keys(asm).length ? `<p class="src"><b>Assumptions.</b> ${Object.values(asm).map(esc).join(" ")}</p>` : "");
}

function render(r) {
  if (r.error) return `<p class="err">${esc(r.error)}</p>`;
  let html = flags(r) + table(r);
  for (const [k, v] of Object.entries(r)) {
    if (["criminal_rate", "source", "assumptions", "eligibility"].includes(k) || v === null || typeof v !== "object") continue;
    if (Array.isArray(v) && v.length && typeof v[0] === "object") html += `<h3>${esc(label(k))}</h3>` + listTable(v);
    else if (!Array.isArray(v)) {
      html += `<h3>${esc(label(k))}</h3>` + table(v);
      for (const [k2, v2] of Object.entries(v)) if (v2 && typeof v2 === "object" && !Array.isArray(v2)) html += `<h4>${esc(label(k2))}</h4>` + table(v2);
    }
  }
  return html + sources(r) + `<details><summary>Raw result</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>`;
}

async function run() {
  const d = DESKS[current], out = $("#result");
  out.innerHTML = `<p class="blurb">Calculating…</p>`;
  try {
    const res = await fetch("/api/tool", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify({name: d.tool, args: collect(d)})});
    out.innerHTML = `<h2>${esc(d.title)}</h2>` + render(await res.json());
  } catch (e) {
    out.innerHTML = `<p class="err">Request failed: ${esc(e.message)}</p>`;
  }
}

DESKS.forEach((d, i) => {
  const b = document.createElement("button");
  b.textContent = d.title; b.setAttribute("role", "tab"); b.onclick = () => showForm(i);
  $("#tabs").appendChild(b);
});
showForm(0);
