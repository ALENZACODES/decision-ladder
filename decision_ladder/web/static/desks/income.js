// Field spec: [name, label, type, default, extra]. Dotted names nest (policy.offset_pct -> {policy:{offset_pct}}).
// type: n number, i integer, s text, b checkbox, sel select (extra = options),
//       props property lines, srcs income-source lines.
const PROP_COLS = ["name", "value", "balance", "rate", "amort_years", "rent_monthly", "taxes_annual", "heat_annual",
                   "condo_fees_monthly", "other_expenses_annual", "owner_occupied", "new_mortgage"];
const PROPS_HINT = "One per line: " + PROP_COLS.join(",") + " (owner/new: y or n; blanks allowed)";
const SRC_HINT = "One per line, type: key=value; ... e.g. salary: amount=95000 | hourly: rate=31.5; hours=37.5 | " +
  "bonus: history=8000/6500 | self_employed: net=61000/72000; cca=4000/3500; home=2400/2400 | " +
  "child_support: amount=9600; court_order=yes";
const DEMO_PROPS = "home,900000,520000,4.49,22,0,6200,1800,0,0,y,n\ncondo,610000,430000,5.09,25,2650,3700,0,560,1500,n,n\n" +
                   "duplex,820000,410000,2.99,19,4300,5600,2400,0,4000,n,n";
const DEMO_SRCS = "salary: amount=104000\nbonus: history=14000/9500\nself_employed: net=28000/34000; cca=2500/3000; home=1200/1400";
const INCOME = [["annual_income","Qualifying income ($/yr) if no sources below","n",null],
  ["income_sources","Income sources (optional)","srcs",""],["other_debt_monthly","Other debt payments ($/month)","n",450]];
const POLICY = [["policy.addback_pct","Add-back % of rent (lender policy)","n",50],
  ["policy.offset_pct","Offset % of rent (lender policy)","n",80]];

const DESKS = [
  { tool: "income_qualifying", title: "Qualifying income",
    blurb: "Qualifying income per source with the method lenders use, the supporting documents and underwriting flags.",
    fields: [["income_sources","Income sources","srcs",DEMO_SRCS + "\nchild_support: amount=7200; court_order=yes\nccb: amount=6400"],
      ["policy.variable_min_years","Years of variable income required (lender policy)","i",2],
      ["policy.include_ccb","Lender counts Canada Child Benefit","b",false],
      ["policy.support_requires_order","Support needs a court order","b",true],
      ["policy.nontaxable_gross_up_pct","Non-taxable gross-up % (lender policy)","n",0]] },
  { tool: "rental_method_compare", title: "Rental method comparison",
    blurb: "GDS and TDS for the same borrower and properties under add-back, offset and net-rental, at the B-20 qualifying rate.",
    fields: [...INCOME, ["properties","Properties","props",DEMO_PROPS], ...POLICY,
      ["policy.offset_surplus_to_income","Offset surplus added to income","b",false],
      ["policy.addback_excludes_tax_heat","Add-back excludes rental taxes and heat","b",false],
      ["policy.net_rental_add_back_interest","Net rental adds back mortgage interest","b",true]] },
  { tool: "rental_portfolio", title: "Investor portfolio",
    blurb: "LTV, NOI, DSCR and cash flow per property, total debt service, and which properties drag TDS.",
    fields: [...INCOME, ["method","Rental method for TDS drag","sel","offset",["offset","add_back","net_rental"]],
      ["properties","Properties","props",DEMO_PROPS], ...POLICY,
      ["policy.vacancy_pct","Vacancy allowance % (lender policy)","n",0],["policy.min_dscr","Minimum DSCR (lender policy)","n",1.0]] },
  { tool: "income_max_purchase", title: "Maximum purchase price",
    blurb: "Highest price with a fixed down payment, counting the subject's rent and existing rentals under each method.",
    fields: [...INCOME, ["down_payment","Down payment ($)","n",150000],["contract_rate","Contract rate (%)","n",4.39],
      ["amort_years","Amortization (years)","i",25],["method","Rental method","sel","all",["all","add_back","offset","net_rental"]],
      ["owner_occupied","Borrower will live in the subject","b",true],["rent_monthly","Subject rent ($/month)","n",1500],
      ["property_tax_rate_pct","Property tax (% of price per year)","n",0.75],["heat_annual","Heat ($/yr, blank = default)","n",null],
      ["condo_fees_monthly","Condo fees ($/month)","n",0],["other_expenses_annual","Subject other expenses ($/yr)","n",0],
      ["first_time_buyer","First-time buyer","b",false],["new_build","New build","b",false],
      ["properties","Existing properties (optional)","props",""], ...POLICY] },
  { tool: "rental_rent_needed", title: "Rent needed to qualify",
    blurb: "Lowest monthly rent a property needs for the whole file to pass GDS and TDS, under each method.",
    fields: [...INCOME, ["target","Property to solve for (name)","s","condo"],
      ["properties","Properties","props",DEMO_PROPS], ...POLICY] },
  { tool: "income_policy_reference", title: "Rules & sources",
    blurb: "The regulatory figures this desk uses with source and check date, and the lender-policy defaults.", fields: [] },
];

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fid = name => "f_" + name.replace(/\./g, "_");
let current = 0;

function fieldHtml([name, label, type, def, extra]) {
  const id = fid(name);
  if (type === "b") return `<div class="check"><label><input type="checkbox" id="${id}" ${def ? "checked" : ""}>${esc(label)}</label></div>`;
  let input;
  if (type === "sel") input = `<select id="${id}">${extra.map(o => `<option ${o === def ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  else if (type === "props" || type === "srcs")
    input = `<textarea id="${id}" rows="4">${esc(def || "")}</textarea><p class="hint">${esc(type === "props" ? PROPS_HINT : SRC_HINT)}</p>`;
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

const yes = v => /^(y|yes|true|1)$/i.test(v.trim());

function parseProps(text) {
  return text.split("\n").map(l => l.trim()).filter(Boolean).map(line => {
    const p = {};
    line.split(",").forEach((raw, j) => {
      const k = PROP_COLS[j], v = raw.trim();
      if (!k || v === "") return;
      p[k] = k === "name" ? v : (k === "owner_occupied" || k === "new_mortgage") ? yes(v) : Number(v);
    });
    return p;
  });
}

const SRC_KEYS = {amount: "annual_amount", rate: "hourly_rate", hours: "guaranteed_hours_per_week", months: "months_in_business",
                  court_order: "court_order", probation: "probation", years_remaining: "years_remaining", label: "label",
                  history: "history", gross_up: "gross_up_pct", contract_months_left: "months_remaining"};
const SE_KEYS = {net: "net_income", cca: "cca", home: "business_use_of_home", other: "other_add_backs"};

function parseSources(text) {
  return text.split("\n").map(l => l.trim()).filter(Boolean).map(line => {
    const [type, rest = ""] = line.split(":");
    const s = {type: type.trim()}, years = [];
    rest.split(";").map(x => x.trim()).filter(Boolean).forEach(kv => {
      const [k, v = ""] = kv.split("=").map(x => x.trim());
      if (SE_KEYS[k]) v.split("/").forEach((n, j) => { (years[j] ??= {})[SE_KEYS[k]] = Number(n); });
      else if (!SRC_KEYS[k]) throw new Error(`unknown key "${k}" in: ${line}`);
      else if (k === "history") s.history = v.split("/").map(Number);
      else if (k === "court_order" || k === "probation") s[SRC_KEYS[k]] = yes(v);
      else s[SRC_KEYS[k]] = k === "label" ? v : Number(v);
    });
    if (years.length) s.years = years;
    if (s.gross_up_pct != null) s.income_method = "gross_up";
    return s;
  });
}

function setPath(obj, path, v) {
  const keys = path.split(".");
  let o = obj;
  keys.slice(0, -1).forEach(k => (o = o[k] ??= {}));
  o[keys.at(-1)] = v;
}

function collect(d) {
  const args = {};
  for (const [name, , type] of d.fields) {
    const el = $("#" + fid(name));
    if (type === "b") { setPath(args, name, el.checked); continue; }
    const raw = el.value.trim();
    if (raw === "") continue;
    const v = type === "props" ? parseProps(raw) : type === "srcs" ? parseSources(raw)
            : (type === "s" || type === "sel") ? raw : Number(raw);
    setPath(args, name, v);
  }
  if (args.income_sources) delete args.annual_income;
  return args;
}

const fmt = v => v === null || v === undefined ? "—" : typeof v === "boolean" ? (v ? "yes" : "no")
  : typeof v === "number" ? v.toLocaleString("en-CA", {maximumFractionDigits: 3}) : Array.isArray(v) ? v.join("; ") : v;
const label = k => k.replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/\bgds\b/, "GDS").replace(/\btds\b/, "TDS")
                    .replace(/\bdscr\b/, "DSCR").replace(/\bltv\b/, "LTV").replace(/\bnoi\b/, "NOI");

function table(obj) {
  const rows = Object.entries(obj).filter(([, v]) => v === null || typeof v !== "object" || (Array.isArray(v) && typeof v[0] !== "object"));
  return rows.length ? `<table>${rows.map(([k, v]) => `<tr><td>${esc(label(k))}</td><td class="num">${esc(fmt(v))}</td></tr>`).join("")}</table>` : "";
}

function listTable(rows, best) {
  const cols = [...new Set(rows.flatMap(r => Object.keys(r)))].filter(c => !rows.some(r => r[c] && typeof r[c] === "object" && !Array.isArray(r[c])));
  return `<table><tr>${cols.map(c => `<th>${esc(label(c))}</th>`).join("")}</tr>${rows.map(r =>
    `<tr${best && (r.method === best || r.name === best) ? ' class="best"' : ""}>${cols.map(c =>
      `<td class="${typeof r[c] === "number" ? "num" : ""}">${esc(fmt(r[c]))}</td>`).join("")}</tr>`).join("")}</table>`;
}

function headline(r) {
  const out = [];
  if (r.total_qualifying_annual != null) out.push(`<div class="flag ok">Qualifying income $${fmt(r.total_qualifying_annual)} / year</div>`);
  if (r.best_method && r.qualifies_under) out.push(`<div class="flag ${r.qualifies_under.length ? "ok" : "bad"}">${r.qualifies_under.length
      ? `Qualifies under: ${esc(r.qualifies_under.join(", "))}. Most room: ${esc(r.best_method)}` : "Does not qualify under any method"}</div>`);
  if (r.max_price !== undefined) out.push(`<div class="flag ${r.max_price ? "ok" : "bad"}">${r.max_price
      ? `Maximum price $${fmt(r.max_price)} (${esc(r.best_method)})` : "No price passes with these inputs"}</div>`);
  if (r.most_forgiving_method !== undefined) out.push(`<div class="flag ${r.most_forgiving_method ? "ok" : "bad"}">${r.most_forgiving_method
      ? `Lowest rent needed under ${esc(r.most_forgiving_method)}` : "No rent up to the cap makes the file pass"}</div>`);
  if (r.drags_tds?.length) out.push(`<div class="flag warn">Drags TDS: ${esc(r.drags_tds.join(", "))}</div>`);
  if (r.below_min_dscr?.length) out.push(`<div class="flag warn">Below minimum DSCR: ${esc(r.below_min_dscr.join(", "))}</div>`);
  (r.flags || []).forEach(f => out.push(`<div class="flag warn">${esc(f)}</div>`));
  return out.join("");
}

const asRows = obj => Object.entries(obj).map(([method, v]) => ({method, ...v}));

function sections(r) {
  let html = "";
  if (r.sources && r.sources[0]?.qualifying_annual !== undefined)
    html += `<h3>By source</h3>` + listTable(r.sources.map(s => ({label: s.label, qualifying_annual: s.qualifying_annual,
      method: s.method, documents: s.documents})));
  if (r.summary) html += `<h3>By method</h3>` + listTable(r.summary, r.best_method);
  if (r.results && !r.summary) html += `<h3>By method</h3>` + listTable(asRows(r.results), r.best_method || r.most_forgiving_method);
  if (r.results?.[r.best_method]?.properties)
    html += `<h3>Properties under ${esc(r.best_method)}</h3>` + listTable(r.results[r.best_method].properties);
  if (r.portfolio) html += `<h3>Portfolio</h3>` + table(r.portfolio) + `<h3>Properties</h3>` + listTable(r.properties);
  if (r.ratios) html += `<h3>Ratios (${esc(r.method)})</h3>` + table(r.ratios);
  if (r.tds_drag) html += `<h3>TDS drag (leave one out)</h3>` + listTable(r.tds_drag);
  if (r.income) html += `<h3>Income used</h3>` + listTable(r.income.sources.map(s => ({label: s.label, qualifying_annual: s.qualifying_annual, method: s.method})));
  if (r.lender_policy_defaults) html += `<h3>Lender policy defaults (vary by lender)</h3>` +
    listTable(Object.entries(r.lender_policy_defaults).map(([k, v]) => ({parameter: k, default: v.default, description: v.description})));
  return html;
}

function sources(r) {
  const s = (r.source || []).filter(x => x.url);
  return (s.length ? `<p class="src"><b>Verified.</b> ${s.map(x => `${esc(x.note)}: <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.url)}</a> (checked ${esc(x.checked)})`).join("<br>")}</p>` : "")
    + (r.assumptions ? `<p class="src"><b>Assumptions.</b> ${Object.entries(r.assumptions).map(([k, v]) => `${esc(label(k))}: ${esc(v)}`).join("<br>")}</p>` : "");
}

function render(r) {
  if (r.error) return `<p class="err">${esc(r.error)}</p>`;
  return headline(r) + sections(r) + sources(r) + `<details><summary>Raw result</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>`;
}

async function run() {
  const d = DESKS[current], out = $("#result");
  let args;
  try { args = collect(d); } catch (e) { out.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  out.innerHTML = `<p class="blurb">Calculating…</p>`;
  try {
    const res = await fetch("/api/tool", {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify({name: d.tool, args})});
    out.innerHTML = `<h2>${esc(d.title)}</h2>` + render(await res.json());
  } catch (e) {
    out.innerHTML = `<p class="err">Request failed: ${esc(e.message)}</p>`;
  }
}

DESKS.forEach((d, i) => {
  const b = document.createElement("button");
  b.textContent = d.title; b.setAttribute("role", "tab"); b.addEventListener("click", () => showForm(i));
  $("#tabs").appendChild(b);
});
showForm(0);
