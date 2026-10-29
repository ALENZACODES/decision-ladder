const MONEY = /(loan|cost|rent|payment|fee|interest|noi|value|balance|premium|equity|income|expense|vacancy|advance|draw|cap_by|holdback_|retained|released|cash|gap|in_place|market|reserve|debt_service|^hard|^soft|land|shortfall|proceeds|amount|lender$|broker$|other$|exit$)/;
const PLAIN = /(pct|years|^months?$|_months?$|points|units|^leases|weighting|year$|tier|area|count|_market$)/;
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const label = k => k.replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/\bltv\b/i, "LTV").replace(/\bltc\b/i, "LTC")
  .replace(/\bdscr\b/i, "DSCR").replace(/\bdcr\b/i, "DCR").replace(/\bnoi\b/i, "NOI").replace(/\bwalt\b/i, "WALT");

function fmt(k, v) {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v !== "number") return esc(v);
  if (/pct/.test(k)) return v.toLocaleString("en-CA", {maximumFractionDigits: 2}) + "%";
  if (/^(dscr|dcr)(_|$)/.test(k)) return v.toFixed(2) + "x";
  if (/(^|_)rate$/.test(k)) return v.toLocaleString("en-CA", {maximumFractionDigits: 3}) + "%";
  if (/psf/.test(k)) return "$" + v.toFixed(2);
  if (MONEY.test(k) && !PLAIN.test(k)) return "$" + v.toLocaleString("en-CA", {minimumFractionDigits: 0, maximumFractionDigits: 0});
  return v.toLocaleString("en-CA", {maximumFractionDigits: 3});
}

function table(rows) {
  const cols = [...new Set(rows.flatMap(Object.keys))].filter(c => c !== "flag");
  const body = rows.map(r => `<tr class="${r.flag ? "flag" : ""}">` +
    cols.map(c => `<td>${typeof r[c] === "object" && r[c] !== null ? esc(JSON.stringify(r[c])) : fmt(c, r[c])}</td>`).join("") + "</tr>").join("");
  return `<div class="scroll"><table><thead><tr>${cols.map(c => `<th>${esc(label(c))}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// constraint caps are loan amounts even though their keys are "ltv", "dscr", "debt_yield"
function kv(obj, parent) {
  return `<table class="kv"><tbody>${Object.entries(obj).map(([k, v]) =>
    `<tr><td>${esc(label(k))}</td><td>${fmt(parent === "constraints" ? "loan" : k, v)}</td></tr>`).join("")}</tbody></table>`;
}

function render(obj, parent) {
  const flat = {}, parts = [];
  for (const [k, v] of Object.entries(obj)) {
    if (k === "engine" || k === "cash_flows") continue;
    if (Array.isArray(v) && v.length && typeof v[0] === "object") parts.push(`<h3>${esc(label(k))}</h3>` + table(v));
    else if (Array.isArray(v)) { if (v.length) parts.push(`<h3>${esc(label(k))}</h3><ul class="notes">${v.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`); }
    else if (v && typeof v === "object") {
      if (k === "sources") parts.push(`<h3>Sources</h3><ul class="notes">${Object.entries(v).map(([n, u]) =>
        /^https?:/.test(u) ? `<li>${esc(label(n))}: <a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>` : `<li>${esc(label(n))}: ${esc(u)}</li>`).join("")}</ul>`);
      else parts.push(`<h3>${esc(label(k))}</h3>` + render(v, k));
    } else flat[k] = v;
  }
  return (Object.keys(flat).length ? kv(flat, parent) : "") + parts.join("");
}

const HEADLINE = {
  commercial_underwrite: r => { const s = r.sizing; const fits = s.requested_fits;
    return [fits === false ? "bad" : "ok", `Max loan ${fmt("loan", s.max_loan)}, bound by ${s.binding_constraint.toUpperCase()}` +
      (fits === undefined ? "" : fits ? " (request fits)" : `; request short by ${fmt("loan", s.shortfall)}`)]; },
  cmhc_mli_size: r => ["ok", `${r.best}: base loan ${fmt("loan", (r.select && r.best !== "MLI Standard" ? r.select : r.standard).base_loan)}` +
      ` · ${r.score.total_points} Select points`],
  construction_draw_schedule: r => [r.ltc_ok ? "ok" : "bad", `Loan ${fmt("loan", r.loan_amount)} at ${r.ltc_pct}% LTC` +
      (r.ltc_ok ? "" : `; add ${fmt("equity", r.equity_shortfall)} equity to reach ${r.max_ltc_pct}%`)],
  private_bridge_cost: r => [r.criminal_rate_flag ? "bad" : r.early_exits_over_limit.length ? "warn" : "ok",
    `Net advance ${fmt("advance", r.net_advance)} · true cost ${r.effective_annual_cost_pct.toFixed(2)}% effective` +
    (r.criminal_rate_flag ? " · over the criminal-rate screen" : r.early_exits_over_limit.length ? " · early exit can breach the criminal-rate screen" : "")],
  rent_roll_analysis: r => [r.flags.length ? "warn" : "ok", `WALT ${r.walt_years_by_rent} yrs by rent · ${r.physical_occupancy_pct}% occupied` +
    (r.flags.length ? ` · ${r.flags.length} concentration flag(s)` : "")],
};

const yes = s => /^(y|yes|true|1)$/i.test((s || "").trim());
const num = s => (s || "").trim() === "" ? undefined : Number(String(s).replace(/[$,\s]/g, ""));
const rows = t => t.split("\n").map(l => l.trim()).filter(Boolean);
// the name may contain commas, so the n numeric / flag fields are taken from the right
const fields = (l, n) => { const p = l.split(",").map(x => x.trim()); return [p.slice(0, Math.max(1, p.length - n)).join(", "), ...p.slice(-n)]; };
const PARSE = {
  kv: t => { const o = {}; for (const l of rows(t)) { const m = l.match(/^(.*?)\s*[,:]\s*\$?([\d,.]+)$/); if (m) o[m[1]] = num(m[2]); }
             return Object.keys(o).length ? o : undefined; },
  budget: t => rows(t).map(l => { const [item, cost, s, e, hard] = fields(l, 4);
    return {item, cost: num(cost), start_month: num(s), end_month: num(e) ?? num(s), hard: hard === undefined || hard === "" ? true : yes(hard)}; }),
  leases: t => rows(t).map(l => { const [tenant, area, rent, market, expiry, vacant] = fields(l, 5);
    const r = {tenant, area: num(area), rent: num(rent) ?? 0, market_rent: num(market), vacant: yes(vacant)};
    if (expiry) r.expiry = expiry;
    return r; }),
};

function collect(form) {
  const args = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    let v;
    if (el.type === "checkbox") v = el.checked;
    else if (el.dataset.parse) v = el.value.trim() ? PARSE[el.dataset.parse](el.value) : undefined;
    else if (el.type === "number") v = num(el.value);
    else v = el.value || undefined;
    if (v !== undefined && !(typeof v === "number" && isNaN(v))) args[el.name] = v;
  }
  return args;
}

async function run(form) {
  const out = form.nextElementSibling, btn = form.querySelector("button.run"), name = form.dataset.tool;
  const args = collect(form);
  btn.disabled = true;
  try {
    const res = await fetch("/api/tool", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify({name, args})});
    const r = await res.json();
    if (r.error) { out.innerHTML = `<p class="err">${esc(r.error)}</p>`; return; }
    const [cls, text] = HEADLINE[name](r);
    out.innerHTML = `<div class="banner ${cls}">${esc(text)}</div>` + render(r);
  } catch (e) {
    out.innerHTML = `<p class="err">Request failed: ${esc(e.message)}</p>`;
  } finally { btn.disabled = false; }
}

document.querySelectorAll("form[data-tool]").forEach(f => f.addEventListener("submit", e => { e.preventDefault(); run(f); }));
document.querySelectorAll("nav button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("nav button").forEach(x => x.setAttribute("aria-selected", x === b));
  document.querySelectorAll("section.desk").forEach(s => s.classList.toggle("on", s.id === b.dataset.desk));
}));
