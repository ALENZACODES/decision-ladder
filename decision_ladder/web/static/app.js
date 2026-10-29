/* Decision Ladder web UI. Vanilla JS; every server string is inserted as text, never as HTML. */
(function () {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /** h("div", {class: "x", onclick: fn}, child, "text", [children]) - text children become text nodes. */
  function h(tag, attrs, ...kids) {
    const el = document.createElementNS(SVG_TAGS.has(tag) ? SVGNS : HTMLNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "class") el.setAttribute("class", v);
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    append(el, kids);
    return el;
  }
  function append(el, kids) {
    for (const k of kids.flat(Infinity)) {
      if (k === null || k === undefined || k === false) continue;
      el.appendChild(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return el;
  }
  const HTMLNS = "http://www.w3.org/1999/xhtml";
  const SVGNS = "http://www.w3.org/2000/svg";
  const SVG_TAGS = new Set(["svg", "g", "path", "line", "rect", "circle", "text", "title", "polyline", "defs", "marker", "polygon"]);

  const fmtMoney = (v) => (v === null || v === undefined || v === "" || isNaN(+v)) ? "—" :
    "$" + (+v).toLocaleString("en-CA", { maximumFractionDigits: Math.abs(+v) >= 1000 ? 0 : 2 });
  const fmtNum = (v, d = 2) => (v === null || v === undefined || isNaN(+v)) ? "—" : (+v).toLocaleString("en-CA", { maximumFractionDigits: d });
  const fmtPct = (v) => (v === null || v === undefined || isNaN(+v)) ? "—" : (+v).toFixed(2) + "%";
  const label = (k) => String(k).replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/^\w/, (c) => c.toUpperCase());

  function fmtVal(k, v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (typeof v === "object") return JSON.stringify(v);
    if (typeof v === "number") {
      const key = String(k).toLowerCase();
      if (/(rate|gds|tds|ltv|pct|gap|policy|prime|goc|reference|change_pct)/.test(key) && Math.abs(v) < 100) return fmtNum(v, 2) + (/(points|score|priority)/.test(key) ? "" : "%");
      if (/(payment|price|premium|balance|value|loan|penalty|saving|income|debt|total|cost|cashback|fees|basis)/.test(key)) return fmtMoney(v);
      return fmtNum(v, 2);
    }
    return String(v);
  }

  let toastTimer = null;
  function toast(msg, kind) {
    const t = $("#toast");
    t.textContent = msg;
    t.className = "toast show" + (kind === "info" ? " info" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.className = "toast"), 4500);
  }

  async function api(path, body) {
    const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const r = await fetch(path, opt);
    let data;
    try { data = await r.json(); } catch (e) { throw new Error(`HTTP ${r.status}: not JSON`); }
    if (!r.ok || (data && data.error && Object.keys(data).length <= 2)) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  }

  /** Run fn with the button in a loading state. */
  async function busy(btn, fn) {
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "";
    append(btn, [h("span", { class: "spin" }), "Working…"]);
    try { return await fn(); }
    catch (e) { toast(e.message || String(e)); }
    finally { btn.disabled = false; btn.textContent = orig; }
  }

  function jsonBlock(obj, title) {
    return h("details", {}, h("summary", {}, title || "Raw JSON"), h("pre", { class: "json" }, JSON.stringify(obj, null, 2)));
  }

  function kvList(obj, skip) {
    const dl = h("dl", { class: "kv" });
    for (const [k, v] of Object.entries(obj || {})) {
      if (skip && skip.includes(k)) continue;
      if (v && typeof v === "object" && !Array.isArray(v)) {
        if (!Object.keys(v).length) continue;
        append(dl, [h("dt", {}, label(k)), h("dd", {}, Object.entries(v).map(([a, b]) => `${a}: ${fmtVal(a, b)}`).join(" · "))]);
      } else if (Array.isArray(v)) {
        append(dl, [h("dt", {}, label(k)), h("dd", {}, v.length ? v.map((x) => typeof x === "object" ? JSON.stringify(x) : x).join(", ") : "none")]);
      } else {
        append(dl, [h("dt", {}, label(k)), h("dd", {}, fmtVal(k, v))]);
      }
    }
    return dl;
  }

  /** Text with "[unverified]" tokens highlighted; everything else stays plain text. */
  function richText(text, cls) {
    const el = h("div", { class: cls || "memo" });
    String(text || "").split(/(\[unverified\])/).forEach((part) => {
      if (part === "[unverified]") el.appendChild(h("span", { class: "unv" }, part));
      else if (part) el.appendChild(document.createTextNode(part));
    });
    return el;
  }

  function verifBadge(v) {
    if (!v || v.checked === undefined) return null;
    if (v.ok) return h("span", { class: "verif ok" }, `✓ ${v.supported}/${v.checked} figures traced to calculators`);
    return h("span", { class: "verif bad" },
      `✗ ${v.unsupported.length} figure(s) not traced: ${v.unsupported.map((u) => u.text).join(", ")}`);
  }

  function usageStrip(usage, timings, model) {
    const s = h("div", { class: "strip" });
    if (timings) for (const [k, v] of Object.entries(timings)) append(s, [h("span", {}, `${k} `, h("b", {}, `${fmtNum(v, 1)} ms`))]);
    if (usage && usage.calls !== undefined) {
      append(s, [h("span", {}, "model calls ", h("b", {}, usage.calls)),
        h("span", {}, "tokens ", h("b", {}, `${fmtNum(usage.prompt_tokens, 0)} in / ${fmtNum(usage.completion_tokens, 0)} out`)),
        h("span", {}, "approx cost ", h("b", {}, `$${(+usage.approx_cost_usd || 0).toFixed(4)}`))]);
      for (const [m, u] of Object.entries(usage.by_model || {})) append(s, [h("span", {}, h("b", {}, m), ` ×${u.calls}`)]);
    }
    if (model && model.offline) append(s, [h("span", { class: "pill warm" }, "offline stand-in: no model was called")]);
    return s;
  }

  // ------------------------------------------------------------------ state
  const state = { samples: null, health: null, lastFile: null, chat: [], marketLoaded: false };

  // ------------------------------------------------------------------ tabs
  function showTab(name) {
    $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
    if (name === "market" && !state.marketLoaded) loadMarket();
    if (history.replaceState) history.replaceState(null, "", "#" + name);
  }
  $$(".tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

  // ------------------------------------------------------------------ health
  async function loadHealth() {
    try {
      const hl = await api("/api/health");
      state.health = hl;
      const mb = $("#modeBadge"), rb = $("#researchBadge");
      if (hl.mode === "live") {
        mb.className = "badge live";
        mb.textContent = `LIVE · NVIDIA ${prettyModel(hl.models.reasoner)} on ${hl.provider}`;
      } else {
        mb.className = "badge off";
        mb.textContent = "OFFLINE DEMO · scripted stand-in, no model";
      }
      mb.title = `reasoner: ${hl.models.reasoner}\nfast: ${hl.models.fast}`;
      rb.className = "badge " + (hl.research === "tavily-live" ? "live" : "muted");
      rb.textContent = hl.research === "tavily-live" ? "Tavily research: live" : "Tavily research: offline fixtures";
      $("#footVer").textContent = `v${hl.version} · ${hl.tools} tools`;
    } catch (e) {
      $("#modeBadge").textContent = "server unreachable";
    }
  }
  function prettyModel(id) {
    const s = String(id || "").split("/").pop();
    if (/super/i.test(s)) return "Nemotron 3 Super";
    if (/nano/i.test(s)) return "Nemotron 3 Nano";
    return s;
  }

  // ------------------------------------------------------------------ samples
  async function loadSamples() {
    const s = await api("/api/samples");
    state.samples = s;
    const pick = $("#samplePick");
    for (const [k, f] of Object.entries(s.files)) pick.appendChild(h("option", { value: k }, f.label || k));
    const setFile = () => {
      const f = Object.assign({}, s.files[pick.value]);
      delete f.label;
      $("#fileJson").value = JSON.stringify(f, null, 2);
    };
    pick.addEventListener("change", setFile);
    setFile();
    $("#intakeText").value = s.email;
    $("#bookCsv").value = s.book_csv.trim();
  }

  // ------------------------------------------------------------------ ladder rendering
  const STATUS_TEXT = { PASS: "PASS", REFER: "REFER", FAIL: "FAIL", SKIP: "SKIP" };

  function renderLadder(run, target) {
    target.textContent = "";
    const rungs = run.rungs || [];
    const decision = rungs.find((r) => r.key === "decision") || { status: "REFER", summary: run.verdict };
    const counts = {};
    rungs.forEach((r) => { if (r.key !== "decision") counts[r.status] = (counts[r.status] || 0) + 1; });

    const head = h("div", { class: "card" },
      h("div", { class: "verdict-wrap" },
        h("div", { class: "verdict " + decision.status }, run.verdict || decision.summary),
        h("div", { class: "counts" }, Object.entries(counts).map(([s, n]) => h("span", { class: "pill " + s }, `${n} ${s}`))),
      ),
      h("div", { class: "hint" }, `${(run.file && run.file.borrower_name) || "File"} · ${(run.file && run.file.purpose) || "purchase"} · ${(run.file && run.file.province) || ""}`));
    target.appendChild(head);

    // ladder (bottom-to-top) + detail
    const ladder = h("div", { class: "ladder", role: "list" });
    const detail = h("div", { class: "card detail" }, h("div", { class: "hint" }, "Select a rung to see its figures and evidence."));
    const btns = [];
    [...rungs].reverse().forEach((r, iRev) => {
      const idx = rungs.length - iRev;
      const b = h("button", { class: `rung ${r.status}`, role: "listitem", type: "button" },
        h("span", { class: "num" }, idx),
        h("span", { class: "t" }, r.title, h("span", { class: "s" }, r.summary)),
        h("span", { class: "pill " + r.status }, STATUS_TEXT[r.status] || r.status));
      b.addEventListener("click", () => {
        btns.forEach((x) => x.classList.remove("sel"));
        b.classList.add("sel");
        renderRungDetail(r, detail);
      });
      btns.push(b);
      ladder.appendChild(b);
    });
    target.appendChild(h("div", { class: "ladder-grid" }, h("div", { class: "card" }, h("h2", {}, "The ladder"), ladder), detail));
    const firstBad = rungs.find((r) => r.status === "FAIL") || rungs.find((r) => r.status === "REFER" && r.key !== "decision");
    if (firstBad) btns[rungs.length - 1 - rungs.indexOf(firstBad)].click();

    // memo
    if (run.memo) {
      target.appendChild(h("div", { class: "card" },
        h("div", { class: "row between" }, h("h2", {}, "Broker decision memo"),
          memoSourcePill(run)),
        richText(run.memo), verifBadge(run.memo_verification)));
    }
    // path to yes
    const opts = (decision.evidence && decision.evidence.options) || [];
    const qual = rungs.find((r) => r.key === "qualification");
    const pty = qual && qual.evidence && qual.evidence.path_to_yes;
    if (opts.length || pty) {
      const cards = h("div", { class: "options" });
      if (pty && pty.options) {
        pty.options.forEach((o) => {
          const lines = [];
          if (o.max_price) lines.push(`Max price ${fmtMoney(o.max_price)}`);
          if (o.min_down_payment) lines.push(`Down payment ${fmtMoney(o.min_down_payment)} (+${fmtMoney(o.additional_needed)})`);
          if (o.max_other_debt_monthly !== undefined && o.max_other_debt_monthly !== null) lines.push(`Max other debt ${fmtMoney(o.max_other_debt_monthly)}/mo`);
          if (o.min_annual_income) lines.push(`Income ${fmtMoney(o.min_annual_income)}/yr (+${fmtMoney(o.shortfall)})`);
          if (o.lever === "30_year_amortization") lines.push(o.passes ? "Passes at 30 years" : "Does not pass at 30 years");
          if (!lines.length && o.reason) lines.push(o.reason);
          const q = o.qualification;
          cards.appendChild(h("div", { class: "opt" }, h("b", {}, label(o.lever)), lines.join(" · "),
            q ? h("div", { class: "hint" }, `GDS ${fmtNum(q.gds)}% · TDS ${fmtNum(q.tds)}% · ${q.passes ? "passes" : "fails"}`) : null));
        });
      } else {
        opts.forEach((o) => cards.appendChild(h("div", { class: "opt" }, o)));
      }
      target.appendChild(h("div", { class: "card" }, h("h2", {}, "Path to yes"),
        h("p", { class: "hint" }, "Each option was re-run through the same stress test that failed the file."), cards));
    }
    // message
    if (run.message) {
      const m = run.message;
      const c = h("div", { class: "card" }, h("h2", {}, "Borrower message (draft)"));
      if (m.error) c.appendChild(h("div", { class: "unv" }, m.error));
      else {
        c.appendChild(h("div", { class: "msg" }, m.draft));
        c.appendChild(h("div", { class: "row" },
          h("span", { class: "pill " + (m.blocked ? "FAIL" : "PASS") }, m.blocked ? "Blocked by guardrail" : "Guardrail: clean"),
          m.blocked ? h("span", { class: "hint" }, `Violations: ${(m.guardrail.violations || []).join(", ")}. Safe text will be sent instead.`) : null));
      }
      target.appendChild(c);
    }
    // research
    if (run.research && run.research.length) {
      const ul = h("ul", { class: "sources" });
      run.research.forEach((r) => {
        if (r.error) ul.appendChild(h("li", {}, `${r.query}: `, h("span", { class: "unv" }, r.error)));
        (r.sources || []).forEach((s) => ul.appendChild(h("li", {},
          h("a", { href: safeUrl(s.url), target: "_blank", rel: "noopener noreferrer" }, s.title || s.url),
          h("div", { class: "meta" }, `${hostOf(s.url)}${s.published ? " · " + s.published : ""} · query: ${r.query}`))));
      });
      target.appendChild(h("div", { class: "card" }, h("h2", {}, "Live research (Tavily)"), ul));
    }
    target.appendChild(h("div", { class: "card" }, usageStrip(run.usage, run.timings_ms, run.model)));
  }

  function memoSourcePill(run) {
    const offline = run.model && run.model.offline;
    const src = String(run.memo_source || "");
    if (offline) return h("span", { class: "pill warm" }, "offline stand-in (no model)");
    if (src.startsWith("nemotron")) return h("span", { class: "pill nv" }, `written by ${prettyModel(run.model && run.model.reasoner)}`);
    return h("span", { class: "pill grey" }, src || "template");
  }

  function renderRungDetail(r, box) {
    box.textContent = "";
    append(box, [
      h("div", { class: "row between" }, h("h3", {}, r.title), h("span", { class: "pill " + r.status }, r.status)),
      h("p", {}, r.summary),
      r.metrics && Object.keys(r.metrics).length ? kvList(r.metrics) : null,
      r.findings && r.findings.length ? h("ul", { class: "find" }, r.findings.map((f) => h("li", {}, f))) : null,
      r.ms !== undefined ? h("div", { class: "hint" }, `Computed in ${fmtNum(r.ms, 2)} ms, no model involved.`) : null,
      r.evidence && Object.keys(r.evidence).length ? jsonBlock(r.evidence, "Evidence") : null,
    ]);
  }

  function safeUrl(u) {
    try { const x = new URL(u); return (x.protocol === "https:" || x.protocol === "http:") ? x.href : "#"; } catch (e) { return "#"; }
  }
  function hostOf(u) { try { return new URL(u).hostname; } catch (e) { return ""; } }

  // ------------------------------------------------------------------ ladder tab
  $("#runLadder").addEventListener("click", (ev) => busy(ev.currentTarget, async () => {
    let file;
    try { file = JSON.parse($("#fileJson").value); } catch (e) { throw new Error("File JSON is not valid: " + e.message); }
    state.lastFile = file;
    const run = await api("/api/ladder", { file, research: $("#optResearch").checked, memo: true, message: true });
    renderLadder(run, $("#ladderOut"));
  }));

  // ------------------------------------------------------------------ intake tab
  async function doIntake(btn, runIt) {
    return busy(btn, async () => {
      const text = $("#intakeText").value;
      const out = await api("/api/intake", { text, run: runIt });
      renderIntake(out);
      const lad = $("#intakeLadder");
      lad.textContent = "";
      if (out.ladder) {
        state.lastFile = out.ladder.file;
        renderLadder(out.ladder, lad);
      }
    });
  }
  $("#btnExtract").addEventListener("click", (e) => doIntake(e.currentTarget, false));
  $("#btnExtractRun").addEventListener("click", (e) => doIntake(e.currentTarget, true));

  function renderIntake(out) {
    const box = $("#intakeOut");
    box.textContent = "";
    const conflicts = new Set((out.conflicts || []).map((c) => c.field));
    const tb = h("tbody");
    for (const [name, f] of Object.entries(out.fields || {})) {
      const src = f.source || "";
      tb.appendChild(h("tr", { class: conflicts.has(name) ? "conf" : null },
        h("td", {}, label(name)), h("td", {}, fmtVal(name, f.value)),
        h("td", {}, h("span", { class: "pill " + (src === "both" ? "PASS" : src.startsWith("model") ? "nv" : "grey") }, src)),
        h("td", { class: "quote" }, f.quote || "")));
    }
    const ex = out.extractors || {};
    const c = h("div", { class: "card" },
      h("div", { class: "row between" }, h("h2", {}, "Extracted file"),
        h("span", { class: "hint" }, `patterns: ${ex.pattern || 0} · model: ${ex.model || 0}`)),
      ex.model_error ? h("div", { class: "unv" }, "Model error: " + ex.model_error) : null,
      h("div", { class: "tbl-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Field", "Value", "Source", "Quoted from text"].map((t) => h("th", {}, t)))), tb)));
    box.appendChild(c);
    if ((out.conflicts || []).length) {
      box.appendChild(h("div", { class: "card" }, h("h2", {}, "Conflicts (broker to confirm)"),
        h("ul", { class: "find" }, out.conflicts.map((x) => h("li", {},
          `${label(x.field)}: pattern says ${fmtVal(x.field, x.pattern)} ("${x.pattern_quote}"), model says ${fmtVal(x.field, x.model)} ("${x.model_quote}")`)))));
    }
    if ((out.dropped || []).length) {
      box.appendChild(h("div", { class: "card" }, h("h2", {}, "Dropped model values (no evidence in text)"),
        h("ul", { class: "find" }, out.dropped.map((x) => h("li", { class: "unv" }, `${label(x.field)} = ${fmtVal(x.field, x.value)}: ${x.reason}`)))));
    }
    if (out.usage) box.appendChild(h("div", { class: "card" }, usageStrip(out.usage)));
  }

  // ------------------------------------------------------------------ copilot tab
  const SUGGEST = [
    "What is the penalty to break a TD mortgage: balance 640000 at 5.29%, term 2023-08-01 to 2028-08-01, posted rate at funding 6.84%, payout 2026-10-28?",
    "How could this file pass the stress test?",
    "What did the Bank of Canada do most recently and what does it mean for 5-year fixed rates?",
    "Compare renewal at 4.84% vs switching at 4.29% on 512400 over 20 years for a 5 year term",
    "Show me today's market snapshot: policy rate, prime and the GoC 5-year.",
  ];
  SUGGEST.forEach((q) => $("#chips").appendChild(h("button", { class: "chip", type: "button", onclick: () => {
    $("#chatInput").value = q;
    if (/this file/i.test(q)) $("#useCtx").checked = true;
    $("#chatInput").focus();
  } }, q)));

  $("#chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#chatForm").requestSubmit(); }
  });
  $("#chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#chatInput").value.trim();
    if (!q) return;
    const log = $("#chatLog");
    log.appendChild(h("div", { class: "bubble user" }, q));
    $("#chatInput").value = "";
    let ctx = null;
    if ($("#useCtx").checked) {
      try { ctx = state.lastFile || JSON.parse($("#fileJson").value); } catch (err) { ctx = null; }
    }
    const pending = h("div", { class: "bubble bot" }, h("span", { class: "spin" }), "Nemotron is planning tool calls…");
    log.appendChild(pending);
    log.scrollTop = log.scrollHeight;
    busy($("#chatSend"), async () => {
      try {
        const res = await api("/api/ask", { question: q, context: ctx, history: state.chat.slice(-6) });
        state.chat.push({ role: "user", content: q }, { role: "assistant", content: res.answer });
        pending.replaceWith(renderAnswer(res));
      } catch (err) {
        pending.replaceWith(h("div", { class: "bubble bot" }, h("span", { class: "unv" }, "Error: " + err.message)));
      }
      log.scrollTop = log.scrollHeight;
    });
  });

  function renderAnswer(res) {
    const b = h("div", { class: "bubble bot" });
    b.appendChild(richText(res.answer, ""));
    const steps = (res.steps || []).filter((s) => s.kind !== "answer");
    const meta = h("div", { class: "meta" },
      verifBadge(res.verification), res.repaired ? h("span", { class: "pill warm" }, " repaired once ") : null,
      h("span", {}, ` · ${steps.length} tool call(s) · ${res.model}`));
    b.appendChild(meta);
    if (steps.length) {
      const d = h("details", {}, h("summary", {}, "Trace: tool calls and results"));
      steps.forEach((s) => d.appendChild(h("div", { class: "step" },
        h("span", { class: "nm" }, s.name), " ", h("span", { class: "pill " + (s.kind === "repair" ? "warm" : s.kind === "research" ? "nv" : "grey") }, s.kind),
        h("span", { class: "hint" }, ` ${fmtNum(s.ms, 1)} ms`),
        jsonBlock(s.args, "Arguments"), jsonBlock(s.result, "Result"))));
      b.appendChild(d);
    }
    b.appendChild(usageStrip(res.usage));
    return b;
  }

  // ------------------------------------------------------------------ book tab
  $("#btnBook").addEventListener("click", (ev) => busy(ev.currentTarget, async () => {
    const res = await api("/api/book", { csv: $("#bookCsv").value, as_of: $("#bookAsOf").value || null, drafts: +$("#bookDrafts").value || 0 });
    renderBook(res);
  }));

  function renderBook(res) {
    const box = $("#bookOut");
    box.textContent = "";
    const s = res.summary || {};
    box.appendChild(h("div", { class: "tiles" },
      tile("Loans", fmtNum(s.loans, 0), `as of ${res.as_of}`, true),
      tile("Total balance", fmtMoney(s.balance_total), "book under review"),
      tile("Call this week", fmtNum(s.call_this_week, 0), `${fmtNum(s.call_this_month, 0)} more this month`),
      tile("Avg payment change", fmtPct(s.avg_payment_change_pct), "at renewal rate")));
    if ((res.errors || []).length) box.appendChild(h("div", { class: "card" }, h("h2", {}, "Rows skipped"),
      h("ul", { class: "find" }, res.errors.map((e) => h("li", { class: "unv" }, e)))));
    const tb = h("tbody");
    (res.queue || []).forEach((r) => {
      const sh = r.shock;
      tb.appendChild(h("tr", {},
        h("td", {}, h("span", { class: "bar" }, h("i", { style: { width: Math.min(100, r.priority) + "%" } })), fmtNum(r.priority, 1)),
        h("td", {}, h("span", { class: "pill " + (r.tier === "call this week" ? "FAIL" : r.tier === "call this month" ? "REFER" : "SKIP") }, r.tier)),
        h("td", {}, r.borrower), h("td", {}, r.lender), h("td", { class: "n" }, fmtMoney(r.balance)),
        h("td", { class: "nowrap" }, r.maturity), h("td", { class: "n" }, r.months_to_maturity),
        h("td", { class: "n" }, sh ? `${fmtMoney(sh.payment_before)} → ${fmtMoney(sh.payment_after)} (${sh.pct_change > 0 ? "+" : ""}${fmtNum(sh.pct_change, 1)}%)` : "—"),
        h("td", { class: "n" }, r.penalty_today === null || r.penalty_today === undefined ? (r.penalty_floor ? h("span", { class: "hint", title: "Three months' interest is the minimum; the IRD for this lender's method needs the payout statement" }, "≥ " + fmtMoney(r.penalty_floor)) : h("span", { class: "hint", title: r.penalty_status || "" }, "needs discount")) : fmtMoney(r.penalty_today)),
        h("td", {}, r.why)));
    });
    box.appendChild(h("div", { class: "card" }, h("h2", {}, "Renewal queue"),
      h("div", { class: "tbl-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Priority", "Tier", "Borrower", "Lender", "Balance", "Maturity", "Months", "Payment at renewal", "Penalty today", "Why"]
          .map((t, i) => h("th", { class: [4, 6, 7, 8].includes(i) ? "n" : null }, t)))), tb))));
    const drafts = (res.queue || []).filter((r) => r.outreach);
    if (drafts.length) {
      const c = h("div", { class: "card" }, h("h2", {}, "Outreach drafts (Nemotron Nano + guardrail)"));
      drafts.forEach((r) => {
        const o = r.outreach;
        c.appendChild(h("details", { open: true }, h("summary", {}, `${r.borrower} · ${r.tier}`),
          o.error ? h("div", { class: "unv" }, o.error) : [
            h("div", { class: "msg" }, o.draft),
            h("div", { class: "row" }, h("span", { class: "pill " + (o.blocked ? "FAIL" : "PASS") }, o.blocked ? "Blocked: " + o.guardrail.violations.join(", ") : "Guardrail: clean")),
          ]));
      });
      box.appendChild(c);
    }
  }

  function tile(k, v, d, accent) {
    return h("div", { class: "tile" + (accent ? " accent" : "") }, h("div", { class: "k" }, k), h("div", { class: "v" }, v), h("div", { class: "d" }, d || ""));
  }

  // ------------------------------------------------------------------ market tab
  async function loadMarket() {
    state.marketLoaded = true;
    try {
      const [m, hist] = await Promise.all([api("/api/market"), api("/api/history")]);
      const tiles = $("#marketTiles");
      tiles.textContent = "";
      const t = (k, o, accent) => o ? tile(k, fmtPct(o.rate), `${o.date} · ${o.source}`, accent) : tile(k, "—", "no data");
      const curve = m.goc_curve || {};
      const eff = (m.effective_new_lending || {}).actual_rate_new_uninsured || {};
      append(tiles, [
        t("BoC policy rate", m.policy_rate, true), t("Prime", m.prime),
        t("GoC 2-year", curve["24"]), t("GoC 5-year", curve["60"]), t("GoC 10-year", curve["120"]),
        t("Big-6 posted 5y", m.big6_typical_posted_5y), t("New uninsured 5y+ (effective)", eff["60"]),
        m.fixed_mortgage_spread ? tile("5y mortgage spread", fmtNum(m.fixed_mortgage_spread.value_pct_points) + " pts",
          m.fixed_mortgage_spread.definition) : null,
      ]);
      drawChart($("#marketChart"), [
        { name: "BoC policy rate", color: "#76b900", pts: hist.policy_rate },
        { name: "GoC 5-year yield", color: "#1d5fa8", pts: hist.goc_5y },
        { name: "Big-6 typical posted 5y", color: "#e07a2f", pts: hist.posted_5y },
        { name: "New uninsured 5y+ (effective)", color: "#c0392b", pts: hist.new_uninsured_5y },
      ]);
    } catch (e) {
      state.marketLoaded = false;
      toast("Market data: " + e.message);
    }
  }

  function drawChart(box, series) {
    box.textContent = "";
    const W = 900, H = 340, L = 46, R = 16, T = 14, B = 34;
    const all = series.flatMap((s) => (s.pts || []).map((p) => ({ t: Date.parse(p.date), v: +p.rate }))).filter((p) => !isNaN(p.t));
    if (!all.length) { box.appendChild(h("div", { class: "empty" }, "No history.")); return; }
    const t0 = Math.min(...all.map((p) => p.t)), t1 = Math.max(...all.map((p) => p.t));
    const vMax = Math.ceil(Math.max(...all.map((p) => p.v)) + 0.5), vMin = 0;
    const x = (t) => L + (t - t0) / (t1 - t0 || 1) * (W - L - R);
    const y = (v) => T + (1 - (v - vMin) / (vMax - vMin || 1)) * (H - T - B);
    const svg = h("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Canadian rates since 2021" });
    for (let v = vMin; v <= vMax; v += 1) {
      append(svg, [h("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "#e5e9ef" }),
        h("text", { x: L - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: "#5f6b7a" }, v + "%")]);
    }
    const y0 = new Date(t0).getFullYear(), y1 = new Date(t1).getFullYear();
    for (let yr = y0; yr <= y1 + 1; yr++) {
      const t = Date.UTC(yr, 0, 1);
      if (t < t0 || t > t1) continue;
      append(svg, [h("line", { x1: x(t), x2: x(t), y1: T, y2: H - B, stroke: "#eef1f4" }),
        h("text", { x: x(t), y: H - B + 18, "text-anchor": "middle", "font-size": 11, fill: "#5f6b7a" }, yr)]);
    }
    series.forEach((s) => {
      const pts = (s.pts || []).map((p) => [Date.parse(p.date), +p.rate, p.date]).filter((p) => !isNaN(p[0]));
      if (!pts.length) return;
      svg.appendChild(h("polyline", { points: pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" "),
        fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round" }));
      const step = Math.max(1, Math.floor(pts.length / 40));
      pts.forEach((p, i) => {
        if (i % step && i !== pts.length - 1) return;
        svg.appendChild(h("circle", { cx: x(p[0]), cy: y(p[1]), r: 3.5, fill: s.color, "fill-opacity": 0.01, stroke: "none" },
          h("title", {}, `${s.name}\n${p[2]}: ${p[1].toFixed(2)}%`)));
      });
    });
    box.appendChild(svg);
    box.appendChild(h("div", { class: "legend" }, series.map((s) => h("span", { style: { "--c": s.color } }, s.name))));
    $$(".legend span", box).forEach((el, i) => el.style.setProperty("--c", series[i].color));
  }

  // ------------------------------------------------------------------ architecture diagram
  function drawArch() {
    const W = 900, H = 300;
    const svg = h("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Decision Ladder architecture" });
    const defs = h("defs", {}, h("marker", { id: "ar", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto" },
      h("path", { d: "M0,0 L10,5 L0,10 z", fill: "#5f6b7a" })));
    svg.appendChild(defs);
    const box = (x, y, w, hh, title, sub, fill, stroke) => h("g", {},
      h("rect", { x, y, width: w, height: hh, rx: 9, fill, stroke: stroke || "#c9d2dd" }),
      h("text", { x: x + w / 2, y: y + 22, "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: "#16243a" }, title),
      h("text", { x: x + w / 2, y: y + 40, "text-anchor": "middle", "font-size": 11, fill: "#5f6b7a" }, sub));
    const arrow = (x1, y1, x2, y2) => h("line", { x1, y1, x2, y2, stroke: "#5f6b7a", "stroke-width": 1.5, "marker-end": "url(#ar)" });
    append(svg, [
      box(10, 30, 160, 56, "Client email / docs", "free text, PDFs", "#fff"),
      box(10, 120, 160, 56, "Mortgage file", "JSON, CSV book", "#fff"),
      box(220, 30, 200, 56, "Nemotron 3 Nano", "intake JSON · drafts", "#eef7df", "#76b900"),
      box(220, 120, 200, 146, "Decision Ladder", "11 deterministic rungs", "#f3f6fa", "#23354f"),
      box(470, 30, 200, 56, "Nemotron 3 Super", "tool planning · memo", "#eef7df", "#76b900"),
      box(470, 120, 200, 56, "Provenance verifier", "every figure traced", "#fff7ec", "#e07a2f"),
      box(470, 210, 200, 56, "Tavily research", "BoC · OSFI · FSRA · CMHC", "#fff"),
      box(720, 30, 170, 56, "Nebius Token Factory", "OpenAI-compatible API", "#0d1726", "#76b900"),
      box(720, 120, 170, 56, "Broker memo", "verdict · path to yes", "#fff"),
      box(720, 210, 170, 56, "Borrower message", "guardrail checked", "#fff"),
      arrow(170, 58, 218, 58), arrow(320, 86, 320, 118), arrow(170, 148, 218, 148),
      arrow(420, 160, 468, 148), arrow(420, 58, 468, 58), arrow(570, 86, 570, 118), arrow(670, 58, 718, 58),
      arrow(670, 148, 718, 148), arrow(570, 210, 570, 178), arrow(670, 238, 718, 238),
    ]);
    // ladder glyph inside the ladder box
    for (let i = 0; i < 5; i++) svg.appendChild(h("rect", { x: 270, y: 178 + i * 16, width: 100, height: 6, rx: 2,
      fill: ["#2f8f46", "#2f8f46", "#b7791f", "#c0392b", "#2f8f46"][i] }));
    // dark box text fix
    $$("text", svg).forEach((t) => { if (t.textContent === "Nebius Token Factory" || t.textContent === "OpenAI-compatible API") t.setAttribute("fill", "#e6edf5"); });
    $("#archSvg").appendChild(svg);
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    drawArch();
    loadHealth();
    try { await loadSamples(); } catch (e) { toast("Could not load samples: " + e.message); }
    const hash = (location.hash || "").slice(1);
    if (hash && $("#tab-" + hash)) showTab(hash);
  }
  boot();
})();
