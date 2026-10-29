const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const money = v => typeof v === "number" ? v.toLocaleString("en-CA", {style: "currency", currency: "CAD"}) : esc(v);
const pill = (ok, t) => `<span class="pill ${ok === null ? "na" : ok ? "ok" : "bad"}">${esc(t)}</span>`;
const CHARGE_TYPES = ["admin", "brokerage_fee", "lender_lawyer", "appraisal_required", "insurance", "brokerage_reimbursed",
  "default_insurance_pst", "registration", "borrower_lawyer", "title_insurance", "default_insurance", "discharge",
  "optional_insurance", "tax_account", "appraisal_report_to_borrower", "prepayment_penalty", "overdraft", "default_charges"];
const TRIGGERS = {ON: ["conflicts", "relationships", "incentives", "reverse_mortgage"],
                  AB: ["conflicts", "referral_fee", "licensee_interest", "borrower_fee_charged"]};
const KYC = ["employment", "income", "property", "financial_knowledge", "objectives", "risk_tolerance", "housing_plan",
             "vulnerability", "credit_history"];

async function tool(name, args) {
  const r = await fetch("/api/tool", {method: "POST", headers: {"Content-Type": "application/json"},
                                      body: JSON.stringify({name, args})});
  return r.json();
}
function formArgs(form) {
  const a = {};
  for (const el of form.elements) {
    if (!el.name || el.name === "json") continue;
    if (el.type === "checkbox") { if (el.checked) a[el.name] = true; continue; }
    if (el.value === "") continue;
    a[el.name] = el.type === "number" ? Number(el.value) : el.value;
  }
  return a;
}
function cites(r) {
  const c = (r.citations || []).map(x => `<li>${esc(x.title)} ${esc(x.section)} &mdash; <a href="${esc(x.url)}">${esc(x.url)}</a> (checked ${esc(x.checked)})</li>`).join("");
  return `<div class="cites"><p class="note">${esc(r.note)}</p><ul>${c}</ul><div>engine: ${esc(r.engine)}</div></div>`;
}
function fail(out, r) { out.innerHTML = `<p class="err">${esc(r.error || "request failed")}</p>`; return !r.error; }
function bind(id, name, build, render) {
  const form = $("#f-" + id), out = $("#o-" + id);
  form.addEventListener("submit", async e => {
    e.preventDefault();
    let args;
    try { args = build(form); } catch (err) { out.innerHTML = `<p class="err">${esc(err.message)}</p>`; return; }
    out.innerHTML = '<p class="note">Working&hellip;</p>';
    const r = await tool(name, args);
    if (fail(out, r)) out.innerHTML = render(r) + cites(r);
  });
}

// tabs
$("#tabs").addEventListener("click", e => {
  const t = e.target.dataset.t; if (!t) return;
  document.querySelectorAll("nav button, section.tab").forEach(el => el.classList.toggle("on", el.dataset.t === t || el.id === t));
});

// statement
function addCharge(type = "brokerage_fee", amount = "") {
  const d = document.createElement("div"); d.className = "row";
  d.innerHTML = `<select data-c="type">${CHARGE_TYPES.map(t => `<option ${t === type ? "selected" : ""}>${t}</option>`).join("")}</select>
    <input data-c="amount" type="number" step="0.01" placeholder="amount" value="${amount}"><input data-c="label" placeholder="label (optional)">
    <button type="button" class="alt">Remove</button>`;
  d.querySelector("button").onclick = () => d.remove();
  $("#charges").appendChild(d);
}
$("#add-charge").onclick = () => addCharge();
bind("stmt", "disclosure_statement", form => {
  const a = formArgs(form);
  a.charges = [...document.querySelectorAll("#charges .row")].map(r => ({
    type: r.querySelector('[data-c="type"]').value, amount: Number(r.querySelector('[data-c="amount"]').value || 0),
    label: r.querySelector('[data-c="label"]').value || undefined})).filter(c => c.amount > 0);
  return a;
}, r => {
  const c = r.cost, fed = c.federal_comparison;
  const rows = r.items.map(i => `<tr><td>${esc(i.item)}</td><td>${esc(i.label)}</td><td>${fmt(i.value)}</td>
    <td>${pill(i.status === "provided" ? true : i.status === "missing" ? false : null, i.status)}</td></tr>`).join("");
  const sched = r.schedule.map(s => `<tr><td>${s.n}</td><td class="num">${money(s.opening)}</td><td class="num">${money(s.interest)}</td>
    <td class="num">${money(s.principal)}</td><td class="num">${money(s.payment)}</td><td class="num">${money(s.closing)}</td></tr>`).join("");
  const timing = r.timing ? `<p>Delivery timing: ${pill(r.timing.ok, r.timing.ok ? "on time" : r.timing.ok === null ? "not checked" : "late")} ${esc(r.timing.finding)}</p>` : "";
  return `<h2>${esc(r.title)}</h2>
    <p>${["borrower", "lender", "brokerage", "statement_date"].filter(k => r[k]).map(k => `<b>${k.replace("_", " ")}:</b> ${esc(r[k])}`).join(" &middot; ")}</p>
    <div class="kpi"><div><span>Payment</span><b>${money(c.payment)}</b></div><div><span>Cost of borrowing (term)</span><b>${money(c.cost_of_borrowing)}</b></div>
    <div><span>APR</span><b>${c.apr_pct.toFixed(3)}%</b></div><div><span>Balance at maturity</span><b>${money(c.balance_at_maturity)}</b></div>
    <div><span>Federal formula APR</span><b>${fed.apr_pct.toFixed(3)}%</b></div></div>
    <p class="note">${esc(c.apr_basis)}. Assumptions: ${esc(c.assumptions.join("; "))}.</p>
    ${timing}${r.missing.length ? `<p class="err">Missing before delivery: ${esc(r.missing.join("; "))}</p>` : ""}
    <table><thead><tr><th>#</th><th>Item (s. 8(1))</th><th>Disclosure</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>
    <details><summary>Amortization schedule for the term (${r.schedule.length} payments)</summary>
    <table><thead><tr><th>#</th><th>Opening</th><th>Interest</th><th>Principal</th><th>Payment</th><th>Closing</th></tr></thead><tbody>${sched}</tbody></table></details>`;
});
function fmt(v) {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "number") return money(v);
  if (Array.isArray(v)) return v.map(fmt).join("<br>") || "none";
  if (typeof v === "object") {
    if (v.due_dates) return `${money(v.amount)} ${esc(v.frequency)}, ${v.count} payments, ${esc(v.due_dates[0])} to ${esc(v.due_dates.at(-1))}`;
    if (v.label) return `${esc(v.label)} ${money(v.amount)} <span class="note">(${esc(v.basis)})</span>`;
    if (v.date) return `${money(v.amount)} on ${esc(v.date)}`;
    return esc(JSON.stringify(v));
  }
  return esc(v);
}

// Interest Act
bind("ia", "interest_act_check", form => {
  const a = formArgs(form); a.blended_payments = !!a.blended_payments; return a;
}, r => {
  const prov = r.provisions.map(p => `<tr><td>${esc(p.section)}</td><td>${pill(p.applies ? true : null, p.applies ? "applies" : "n/a")}</td><td>${esc(p.why)}</td></tr>`).join("");
  const flags = r.red_flags.map(f => `<tr><td>${esc(f.section)}</td><td>${esc(f.issue)}</td><td>${esc(f.consequence)}</td></tr>`).join("");
  const comp = Object.entries(r.computed).map(([k, v]) => `<div><span>${esc(k.replace(/_/g, " "))}</span><b>${typeof v === "number" ? (k.includes("pct") ? v.toFixed(4) + "%" : money(v)) : esc(v)}</b></div>`).join("");
  return `<p>${pill(r.clean, r.clean ? "no red flags" : r.red_flags.length + " red flag(s)")}</p><div class="kpi">${comp}</div>
    <table><thead><tr><th>Section</th><th></th><th>Why</th></tr></thead><tbody>${prov}</tbody></table>
    ${flags ? `<h3>Red flags</h3><table><thead><tr><th>Section</th><th>Issue</th><th>Consequence</th></tr></thead><tbody>${flags}</tbody></table>` : ""}`;
});

// renewal
bind("ren", "renewal_disclosure_timing", formArgs, r => {
  if (r.applies === false) return `<p>${pill(null, "not applicable")} ${esc(r.finding)}</p>`;
  const t = r.timing;
  return `<p>${pill(r.ok, r.ok ? "compliant" : "issue")} ${esc(r.kind)}: ${esc(r.finding)}</p>
    <div class="kpi"><div><span>Days counted</span><b>${t.days_counted} / ${t.required}</b></div>
    <div><span>Latest compliant date</span><b>${esc(t.latest_compliant_date)}</b></div>
    ${r.renewal_effective_no_earlier_than ? `<div><span>Renewal effective no earlier than</span><b>${esc(r.renewal_effective_no_earlier_than)}</b></div>` : ""}</div>
    ${(r.missing_content || []).length ? `<p class="err">Missing content: ${esc(r.missing_content.join("; "))}</p>` : ""}`;
});

// conduct checklist: build the field list from the rules table
async function loadRules() {
  const j = $("#jur").value, r = await tool("disclosure_rules", {jurisdiction: j});
  const fields = [...new Set((r.rules || []).flatMap(x => x.fields))];
  if (j === "ON") fields.push(...KYC.map(k => "kyc." + k));
  if (j === "AB") fields.push("funding_confirmation_accepted");
  $("#fields").innerHTML = fields.map(f => `<label class="chk"><input type="checkbox" data-f="${f}">${f.replace(/_/g, " ")}</label>`).join("");
  $("#triggers").innerHTML = TRIGGERS[j].map(t => `<label class="chk"><input type="checkbox" data-trig="${t}">${t.replace(/_/g, " ")}</label>`).join("")
    + (j === "AB" ? `<label>Initial disclosure date<input type="date" data-d="initial_disclosure_date"></label><label>Fee date<input type="date" data-d="fee_date"></label>` : "");
}
$("#jur").onchange = loadRules;
bind("conduct", "conduct_checklist", form => {
  const a = formArgs(form), file = {kyc: {}};
  for (const k of ["principal", "disclosure_date", "signing_date", "lender_type"]) if (a[k] !== undefined) file[k] = a[k];
  form.querySelectorAll("[data-f]").forEach(el => {
    if (!el.checked) return;
    const f = el.dataset.f; if (f.startsWith("kyc.")) file.kyc[f.slice(4)] = true; else file[f] = true;
  });
  form.querySelectorAll("[data-trig]").forEach(el => { if (el.checked) file[el.dataset.trig] = el.dataset.trig === "conflicts" ? ["disclosed in file"] : true; });
  form.querySelectorAll("[data-d]").forEach(el => { if (el.value) file[el.dataset.d] = el.value; });
  return {jurisdiction: a.jurisdiction, file};
}, r => {
  const rows = r.results.map(x => `<tr><td>${esc(x.id)}</td><td>${esc(x.requirement)}${x.detail ? `<br><span class="note">${esc(x.detail)}</span>` : ""}</td>
    <td>${esc(x.citation)}</td><td>${pill(x.status === "met" ? true : x.status === "missing" ? false : null, x.status)}</td>
    <td>${esc((x.missing || []).join(", "))}</td></tr>`).join("");
  return `<p>${pill(r.complete, r.complete ? "complete" : r.missing.length + " rule(s) with gaps")} met ${r.summary.met}, missing ${r.summary.missing}, n/a ${r.summary["n/a"]}</p>
    <table><thead><tr><th>Rule</th><th>Requirement</th><th>Citation</th><th>Status</th><th>Missing</th></tr></thead><tbody>${rows}</tbody></table>`;
});

// FINTRAC
$("#fin-json").value = JSON.stringify({
  record_date: new Date().toISOString().slice(0, 10),
  clients: [{name: "Borrower One", method: "photo_id", verified_date: "", address: "", dob: "", occupation: "",
             photo_id: {doc_type: "driver's licence", doc_number: "", jurisdiction: "ON", country: "CA", expiry_date: "",
                        authenticated: false, photo_matched: false},
             third_party_determined: false, pep_hio_determined: false}],
  transactions: [{date: "", amount: 0, cash: false, payer: "Borrower One", receipt_of_funds_record: false, payer_verified: false}],
  program: {compliance_officer: "", policies: false, risk_assessment: false, training: false, effectiveness_review_date: ""}
}, null, 2);
bind("fin", "fintrac_check", form => {
  const strip = o => Array.isArray(o) ? o.map(strip) : o && typeof o === "object"
    ? Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "").map(([k, v]) => [k, strip(v)])) : o;
  const a = strip(JSON.parse($("#fin-json").value));
  a.transactions = (a.transactions || []).filter(t => t.amount > 0 && t.date);
  return a;
}, r => {
  const cl = r.clients.map(c => `<tr><td>${esc(c.name)}</td><td>${esc(c.type)}</td><td>${pill(c.ok, c.ok ? "complete" : "gaps")}</td><td>${esc(c.missing.join("; "))}</td></tr>`).join("");
  const tx = r.transactions.map(t => `<tr><td>${esc(t.date)}</td><td class="num">${money(t.amount)}</td><td>${pill(t.ok, t.ok ? "ok" : "gaps")}</td><td>${esc(t.missing.join("; "))}</td></tr>`).join("");
  return `<p>${pill(r.complete, r.complete ? "complete" : r.missing.length + " gap(s)")}${r.retain_until ? ` Retain records until <b>${esc(r.retain_until)}</b>` : ""}</p>
    <table><thead><tr><th>Client</th><th>Type</th><th></th><th>Missing</th></tr></thead><tbody>${cl}</tbody></table>
    ${tx ? `<table><thead><tr><th>Received</th><th>Amount</th><th></th><th>Missing</th></tr></thead><tbody>${tx}</tbody></table>` : ""}
    ${r.program ? `<p>Compliance program: ${pill(r.program.ok, r.program.ok ? "ok" : "gaps")} ${esc(r.program.missing.join("; "))}</p>` : ""}`;
});

addCharge("brokerage_fee", 0);
loadRules();

document.getElementById("print-btn")?.addEventListener("click", () => window.print());
