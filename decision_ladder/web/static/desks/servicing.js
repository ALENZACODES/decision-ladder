"use strict";
const FREQS = "monthly|semi_monthly|biweekly|accelerated_biweekly|weekly|accelerated_weekly";
const LOAN = [["principal", "Principal / balance ($)", 500000, "n"], ["annual_rate", "Rate (%)", 4.79, "n"],
              ["amort_years", "Amortization (years)", 25, "n"], ["frequency", "Frequency", "monthly", "sel:" + FREQS],
              ["rate_type", "Rate type", "fixed", "sel:fixed|variable"], ["funding_date", "Funding date", today(), "d"]];
const PENALTY = [["lender", "Penalty profile", "generic", "sel:generic|rbc|rbc_pv|td|scotia|cibc|bmo|nbc"],
                 ["comparison_posted_rate", "Comparison rate (%)", "", "n"],
                 ["penalty_method", "IRD method (if profile has none)", "",
                  "sel:|simple_differential|posted_minus_discount|cibc_discount_addback|present_value"]];
const CURRENT = [["balance", "Balance ($)", 400000, "n"], ["current_rate", "Current rate (%)", 2.49, "n"],
                 ["remaining_term_months", "Months left on term", 24, "i"],
                 ["remaining_amort_years", "Amortization left (years)", 22, "n"], ["as_of", "As of", today(), "d"]];

const TABS = [
  {key: "schedule", title: "Schedule", tool: "servicing_schedule", rows: true,
   help: "Dated schedule. Variable with a held payment reports the trigger rate and trigger point.",
   fields: [...LOAN, ["term_months", "Term (months, blank = to payoff)", "", "i"],
            ["variable_payment", "Variable payment", "fixed", "sel:fixed|adjustable"],
            ["rate_changes", "Rate changes (JSON)", '[{"date": "2027-06-01", "rate": 5.25}]', "json"],
            ["trigger_point_pct", "Trigger point (% of original)", 100, "n"],
            ["on_trigger_point", "At trigger point", "flag", "sel:flag|reset"]]},
  {key: "freq", title: "Frequencies", tool: "servicing_frequency_compare",
   help: "All six frequencies funded the same day and run to payoff.",
   fields: LOAN.filter(f => f[0] !== "frequency")},
  {key: "trigger", title: "Trigger rate", tool: "variable_trigger_rate",
   help: "From a variable-rate statement: the rate at which the payment only covers interest.",
   fields: [["balance", "Balance ($)", 500000, "n"], ["payment", "Regular payment ($)", 2770, "n"],
            ["frequency", "Frequency", "monthly", "sel:" + FREQS], ["current_rate", "Current rate (%)", 5.2, "n"]]},
  {key: "prepay", title: "Prepayment", tool: "servicing_prepayment", rows: true,
   help: "Lump sums, payment increases and double-ups against the contract privileges; overages priced by the penalty engine.",
   fields: [...LOAN, ["term_months", "Term (months)", 60, "i"],
            ["lump_sums", "Lump sums (JSON)", '[{"date": "2027-06-01", "amount": 50000}]', "json"],
            ["payment_increases", "Payment increases (JSON)", '[{"date": "2028-01-01", "increase_pct": 10}]', "json"],
            ["double_ups", "Double-up dates (JSON)", "[]", "json"],
            ["lump_sum_pct", "Lump-sum privilege (% of original)", 15, "n"],
            ["payment_increase_pct", "Payment-increase privilege (%)", 15, "n"],
            ["double_up_allowed", "Double-ups allowed", true, "b"], ...PENALTY]},
  {key: "blend", title: "Blend vs break", tool: "blend_vs_break",
   help: "Blend-and-extend / blend-and-increase vs staying vs breaking, ranked by cost over a common horizon.",
   fields: [...CURRENT, ["new_rate", "New rate (%)", 4.29, "n"], ["new_term_months", "New term (months)", 60, "i"],
            ["new_funds", "New funds ($)", 0, "n"], ["renewal_rate", "Assumed renewal rate (%)", "", "n"],
            ["penalty", "Known penalty ($, optional)", "", "n"], ["refinance_costs", "Refinance costs ($)", 0, "n"],
            ["capitalize_penalty", "Add penalty to the loan", false, "b"], ["property_value", "Property value ($)", "", "n"],
            ...PENALTY]},
  {key: "port", title: "Port & increase", tool: "port_and_increase",
   help: "Port to a new home and add funds at a blended rate.",
   fields: [...CURRENT, ["new_funds", "New funds ($)", 150000, "n"], ["new_rate", "Rate on new funds (%)", 4.29, "n"],
            ["purchase_price", "Purchase price ($)", 900000, "n"], ["sale_closing", "Sale closing", "", "d"],
            ["purchase_closing", "Purchase closing", "", "d"], ["port_window_days", "Port window (days)", 30, "i"], ...PENALTY]},
  {key: "heloc", title: "HELOC room", tool: "heloc_room",
   help: "Readvanceable plan: revolving capped at 65% of value, whole plan at 80% (OSFI B-20).",
   fields: [["property_value", "Property value ($)", 1000000, "n"], ["heloc_balance", "HELOC balance ($)", 50000, "n"],
            ["heloc_rate", "HELOC rate (%)", 6.45, "n"],
            ["amortizing", "Amortizing segments (JSON)", '[{"label": "mortgage", "balance": 600000, "rate": 4.5, "amort_years": 25}]', "json"],
            ["authorized_limit", "Authorized limit ($, optional)", "", "n"], ["projection_years", "Projection (years)", 10, "i"],
            ["as_of", "As of", today(), "d"]]},
  {key: "defer", title: "Deferral", tool: "payment_deferral", rows: true,
   help: "Skip payments: capitalized interest and two ways back.",
   fields: [...LOAN, ["start", "First skipped payment on/after", today(), "d"], ["n_payments", "Payments skipped", 3, "i"]]},
  {key: "arrears", title: "Arrears", tool: "mortgage_arrears",
   help: "Amount to bring a mortgage current after missed payments.",
   fields: [["payment", "Regular payment ($)", 2900, "n"], ["annual_rate", "Rate (%)", 4.79, "n"], ["missed", "Missed payments", 2, "i"],
            ["frequency", "Frequency", "monthly", "sel:" + FREQS], ["rate_type", "Rate type", "fixed", "sel:fixed|variable"],
            ["fees_per_missed", "Fee per missed payment ($)", 0, "n"]]},
];

function today() { return new Date().toISOString().slice(0, 10); }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }
function label(k) { return k.replace(/_/g, " "); }
function fmt(v, key) {
  if (v === null || v === undefined) return "-";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") {
    const money = !/(rate|pct|ltv|years|months|share|days|year$|^n$|^payments$|payments_(made|skipped|per_year)|missed)/.test(key || "");
    return money ? v.toLocaleString("en-CA", {minimumFractionDigits: 2, maximumFractionDigits: 2})
                 : v.toLocaleString("en-CA", {maximumFractionDigits: 4});
  }
  return String(v);
}

let current = TABS[0];
const tabsEl = document.getElementById("tabs"), formEl = document.getElementById("form"), outEl = document.getElementById("out");

function renderTabs() {
  tabsEl.innerHTML = TABS.map(t => `<button role="tab" data-k="${t.key}" aria-selected="${t === current}">${esc(t.title)}</button>`).join("");
}
function renderForm() {
  const f = current.fields.map(([name, text, def, kind]) => {
    if (kind === "b") return `<label class="check"><input type="checkbox" name="${name}" ${def ? "checked" : ""}>${esc(text)}</label>`;
    if (kind.startsWith("sel:")) {
      const opts = kind.slice(4).split("|").map(o => `<option value="${o}" ${o === def ? "selected" : ""}>${o ? label(o) : "(none)"}</option>`);
      return `<label>${esc(text)}<select name="${name}">${opts.join("")}</select></label>`;
    }
    if (kind === "json") return `<label>${esc(text)}<textarea name="${name}">${esc(def)}</textarea></label>`;
    const type = kind === "d" ? "date" : kind === "s" ? "text" : "number";
    const step = kind === "i" ? "1" : "any";
    return `<label>${esc(text)}<input type="${type}" name="${name}" step="${step}" value="${esc(def)}"></label>`;
  });
  const rows = current.rows ? `<label class="check"><input type="checkbox" name="rows" checked>Show every payment</label>` : "";
  formEl.innerHTML = `<p class="help">${esc(current.help)}</p>${f.join("")}${rows}<button type="submit">Calculate</button>`;
}
function readArgs() {
  const args = {};
  for (const [name, , , kind] of current.fields) {
    const el = formEl.elements[name];
    if (kind === "b") { args[name] = el.checked; continue; }
    const v = el.value.trim();
    if (v === "") continue;
    if (kind === "n") args[name] = parseFloat(v);
    else if (kind === "i") args[name] = parseInt(v, 10);
    else if (kind === "json") args[name] = JSON.parse(v);
    else args[name] = v;
  }
  if (current.rows) args.rows = formEl.elements.rows.checked;
  return args;
}

// ------------------------------------------------------------------ result rendering
function isRowList(v) { return Array.isArray(v) && v.length && typeof v[0] === "object" && v[0] !== null && !Array.isArray(v[0]); }
function table(list) {
  const cols = Object.keys(list[0]).filter(c => list.every(r => typeof r[c] !== "object" || r[c] === null || Array.isArray(r[c])));
  const head = cols.map(c => `<th>${esc(label(c))}</th>`).join("");
  const body = list.map(r => "<tr>" + cols.map(c => `<td>${esc(Array.isArray(r[c]) ? r[c].join("; ") : fmt(r[c], c))}</td>`).join("") + "</tr>").join("");
  return `<div class="tablewrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function block(obj, depth) {
  const scalars = [], nested = [];
  for (const [k, v] of Object.entries(obj)) {
    if (k === "flags" || k === "rule_source") continue;
    if (isRowList(v)) nested.push(`<h3>${esc(label(k))}</h3>` + table(v));
    else if (Array.isArray(v)) scalars.push([k, v.length ? v.join("; ") : "none"]);
    else if (v && typeof v === "object") nested.push(depth < 3 ? `<h3>${esc(label(k))}</h3>` + block(v, depth + 1) : "");
    else scalars.push([k, v]);
  }
  const dl = scalars.length ? "<dl>" + scalars.map(([k, v]) => `<div><dt>${esc(label(k))}</dt><dd>${esc(fmt(v, k))}</dd></div>`).join("") + "</dl>" : "";
  return dl + nested.join("");
}
function collectFlags(obj, acc = []) {
  if (!obj || typeof obj !== "object") return acc;
  if (Array.isArray(obj.flags)) acc.push(...obj.flags.filter(f => typeof f === "string"));
  for (const v of Object.values(obj)) if (v && typeof v === "object" && !Array.isArray(v)) collectFlags(v, acc);
  return acc;
}
// first series worth charting: dated balances (rows), yearly end balances, or HELOC room
function chartSeries(res) {
  const sched = res.rows ? res : res.schedule || res.schedule_keep_payment;
  if (sched && sched.rows) return {title: "Balance after each payment", pts: sched.rows.map(r => [r.date, r.balance])};
  if (res.yearly) return {title: "Balance at year end", pts: res.yearly.map(r => [String(r.year), r.end_balance])};
  if (res.projection) return {title: "Available HELOC room", pts: res.projection.map(r => [r.date, r.available_room])};
  return null;
}
const G = {W: 760, H: 260, L: 70, R: 16, T: 12, B: 30};
function scales(pts) {
  const {W, H, L, R, T, B} = G, n = pts.length - 1, max = Math.max(...pts.map(p => p[1])) || 1;
  return {n, max, x: i => L + (W - L - R) * i / n, y: v => T + (H - T - B) * (1 - v / max)};
}
function chart(series) {
  const {W, H, L, R, T, B} = G, pts = series.pts;
  if (pts.length < 2) return "";
  const {n, max, x, y} = scales(pts);
  const ticks = [0, .25, .5, .75, 1].map(f => f * max);
  const grid = ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`).join("");
  const ylab = ticks.map(v => `<text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v / 1000).toLocaleString("en-CA")}k</text>`).join("");
  const step = Math.max(1, Math.ceil(n / 6));
  const xlab = pts.map((p, i) => i % step === 0 || i === n ? `<text x="${x(i)}" y="${H - 8}" text-anchor="${i === n ? "end" : i === 0 ? "start" : "middle"}">${esc(p[0].slice(0, 7))}</text>` : "").join("");
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  return `<div class="card"><h2>${esc(series.title)}</h2><div class="chart">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.title)}">
      <g class="grid">${grid}</g><g class="axis">${ylab}${xlab}</g>
      <path d="${d}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>
      <line class="cross" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="var(--ink-2)" stroke-dasharray="3 3" visibility="hidden"/>
      <circle class="dot" r="4" fill="var(--series-1)" stroke="var(--panel)" stroke-width="2" visibility="hidden"/>
      <rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>
    </svg><div class="tip"></div></div><p class="note">The table below lists every value shown.</p></div>`;
}
function wireChart(series) {
  const box = outEl.querySelector(".chart");
  if (!box) return;
  const svg = box.querySelector("svg"), tip = box.querySelector(".tip"), cross = svg.querySelector(".cross"), dot = svg.querySelector(".dot");
  const {W, H, L, R} = G, pts = series.pts, {n, x, y} = scales(pts);
  svg.addEventListener("mousemove", e => {
    const r = svg.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(n, Math.round((sx - L) / (W - L - R) * n)));
    const px = x(i), py = y(pts[i][1]);
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.setAttribute("visibility", "visible");
    tip.style.display = "block";
    tip.innerHTML = `${esc(pts[i][0])}<br><b>$${fmt(pts[i][1], "balance")}</b>`;
    const left = px * r.width / W;
    tip.style.left = (left > r.width - 140 ? left - 130 : left + 10) + "px";
    tip.style.top = (py * r.height / H) + "px";
  });
  svg.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); });
}
function render(res) {
  if (res.error) { outEl.innerHTML = `<div class="card error">${esc(res.error)}</div>`; return; }
  const flags = collectFlags(res);
  const series = chartSeries(res);
  const src = res.rule_source ? `<p class="note">Rule source: <a href="${esc(res.rule_source.url)}" target="_blank" rel="noopener">${esc(res.rule_source.title)}</a> (checked ${esc(res.rule_source.checked)})</p>` : "";
  outEl.innerHTML = (flags.length ? `<div class="card"><h2>Flags</h2><ul class="flags">${flags.map(f => `<li>${esc(f)}</li>`).join("")}</ul></div>` : "")
    + (series ? chart(series) : "")
    + `<div class="card"><h2>${esc(current.title)}</h2>${block(res, 0)}${src}</div>`;
  if (series) wireChart(series);
}

async function run(e) {
  e.preventDefault();
  let args;
  try { args = readArgs(); } catch (err) { render({error: "Check the JSON fields: " + err.message}); return; }
  outEl.innerHTML = `<div class="card note">Calculating...</div>`;
  try {
    const r = await fetch("/api/tool", {method: "POST", headers: {"Content-Type": "application/json"},
                                        body: JSON.stringify({name: current.tool, args})});
    render(await r.json());
  } catch (err) { render({error: "Request failed: " + err.message}); }
}

tabsEl.addEventListener("click", e => {
  const b = e.target.closest("button[data-k]");
  if (!b) return;
  current = TABS.find(t => t.key === b.dataset.k);
  renderTabs(); renderForm();
  outEl.innerHTML = `<div class="card note">Fill in the form and run the calculation.</div>`;
});
formEl.addEventListener("submit", run);
renderTabs(); renderForm();
