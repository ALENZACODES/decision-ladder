(function () {
  const $ = id => document.getElementById(id);
  const fmt = n => (n < 0 ? "-$" : "$") + Math.round(Math.abs(n)).toLocaleString("en-CA");
  const pct = n => (Math.round(n * 1000) / 10).toLocaleString("en-CA") + "%";
  const num = v => +String(v).replace(/[^0-9.]/g, "") || 0;
  const T = RATES.typical;

  const STAGES = [
    { name: "Before you offer", when: "Days or weeks ahead" },
    { name: "Offer accepted", when: "Within about 24 hours" },
    { name: "Lawyer collects funds", when: "1 to 2 days before closing" },
    { name: "Closing day", when: "Keys" },
    { name: "Moving day", when: "First week" }
  ];

  const state = {
    price: 700000, savings: 60000, city: "to", ftb: "y", dp: "min", am: "25",
    depositPct: T.depositPct * 100, inspection: T.inspection, legal: T.legal, title: T.titleInsurance,
    adjustments: T.adjustments, moving: T.moving, hbp: 0, gift: 0, stage: 2, open: ""
  };

  // ---------- URL hash ----------
  const KEYS = ["price","savings","city","ftb","dp","am","depositPct","inspection","legal","title","adjustments","moving","hbp","gift"];
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const TEXT = ["city", "ftb", "dp", "am"];
    KEYS.forEach(k => { if (!h.has(k)) return; const v = h.get(k); state[k] = TEXT.includes(k) ? v : (num(v) || 0); });
  }
  function writeHash() {
    const h = new URLSearchParams();
    KEYS.forEach(k => h.set(k, state[k]));
    history.replaceState(null, "", "#" + h.toString());
  }

  // ---------- compute ----------
  function downFor(price) {
    const min = Calc.minDown(price);
    if (state.dp === "min") return Math.ceil(min);
    return Math.max(Math.ceil(min), Math.round(price * (+state.dp) / 100));
  }
  function compute(priceOverride, extraCash) {
    const price = priceOverride == null ? state.price : priceOverride;
    const down = downFor(price);
    return Calc.plan({
      price, savings: state.savings + (extraCash || 0), down,
      toronto: state.city === "to", firstTime: state.ftb === "y", amort30: state.am === "30",
      deposit: Math.round(price * state.depositPct / 100),
      inspection: state.inspection, legal: state.legal, title: state.title,
      adjustments: state.adjustments, moving: state.moving
    });
  }

  // highest price (to the nearest $1,000) where cash to close fits the savings
  function maxPrice(extra) {
    let lo = 0, hi = 5000000;
    if (compute(hi, extra).gap >= 0) return hi;
    while (hi - lo > 1000) { const mid = Math.floor((lo + hi) / 2); if (compute(mid, extra).gap >= 0) lo = mid; else hi = mid; }
    return Math.floor(lo / 1000) * 1000;
  }

  // ---------- explanations ----------
  function why(it, p) {
    const ftb = state.ftb === "y";
    switch (it.id) {
      case "inspection": return "Many buyers in busy markets inspect before they offer so the offer can be firm. Either way, you pay the inspector before you know the house is yours.";
      case "deposit": return `Due within about 24 hours of acceptance, usually as a bank draft to the listing brokerage's trust account. It counts toward your down payment, but it has to be ready weeks before the rest. ${state.depositPct}% is common in the GTA. Your offer sets the real number.`;
      case "retainer": return "Legal fees, disbursements, HST and title insurance. Quotes vary a lot from firm to firm, so get two.";
      case "balance": return "Your down payment minus the deposit you already paid. Your lawyer needs it as a wire or certified funds a day or two before closing.";
      case "ltt": return ftb
        ? `Ontario charges this on every purchase: ${fmt(it.gross)} on this price. First-time buyers get up to $4,000 back, usually right at registration, so you pay ${fmt(it.amount)}.`
        : `Ontario charges this on every purchase: ${fmt(it.gross)} on this price. The $4,000 refund is only for people who have never owned a home anywhere in the world.`;
      case "mltt": return ftb
        ? `Toronto charges its own land transfer tax on top of Ontario's, at the same rates up to $3 million: ${fmt(it.gross)} here. First-time buyers get up to $4,475 back, so you pay ${fmt(it.amount)}. Buy outside Toronto and this line disappears.`
        : `Toronto charges its own land transfer tax on top of Ontario's, at the same rates up to $3 million: ${fmt(it.gross)} here. The $4,475 rebate is only for first-time buyers. Buy outside Toronto and this line disappears.`;
      case "pst": return `This is the one people miss. The mortgage insurance premium is added to your mortgage, but Ontario charges 8% sales tax on it, and the tax can't go on the loan. You pay ${fmt(it.amount)} in cash through your lawyer.`;
      case "adjust": return "If the seller already paid this year's property tax or this month's condo fees, you pay back the part that covers the days after closing.";
      case "moving": return "Movers or a truck, utility hookups, and the first trip to the hardware store.";
      case "premium": return `Required when you put down less than 20%. It protects the lender, not you. It's ${pct(p.rate)} of your loan${p.amort30 ? ", including 0.20 points for a 30-year amortization" : ""}. It goes on the mortgage, so it doesn't come out of savings, but you pay interest on it for years.`;
    }
    return "";
  }
  const EDIT = { inspection: ["inspection"], retainer: ["legal", "title"], adjust: ["adjustments"], moving: ["moving"], deposit: ["depositPct"] };
  const EDIT_LABEL = { inspection: "Inspection", legal: "Legal fees", title: "Title insurance", adjustments: "Adjustments", moving: "Moving", depositPct: "Deposit, % of price" };
  const TAG = { cash: ["Cash", "tag-cash"], loan: ["Added to your loan", "tag-loan"], down: ["Down payment", "tag-down"] };

  // ---------- render ----------
  function render(announce) {
    const p = compute();

    // verdict
    const short = p.gap < 0;
    $("verdict").className = "verdict " + (short ? "is-short" : "is-ok");
    $("verdict").innerHTML =
      `<p class="big">You need <strong>${fmt(p.cashToClose)}</strong> on closing, not ${fmt(p.down)}.</p>` +
      `<p class="small">${short ? `<span class="icon" aria-hidden="true">&#9888;</span> You're <strong>${fmt(-p.gap)} short</strong> of that with ${fmt(p.savings)} saved.`
                                : `<span class="icon" aria-hidden="true">&#10003;</span> You're covered, with <strong>${fmt(p.gap)}</strong> to spare.`}</p>` +
      (p.belowMin ? `<p class="warn">The minimum down payment at this price is ${fmt(p.minDown)}.</p>` : "") +
      (p.price >= RATES.minDown.insuredCap ? `<p class="warn">At $1.5 million or more, mortgage insurance isn't available, so you need at least 20% down.</p>` : "");

    // bar
    const scale = Math.max(p.cashToClose, p.savings, 1) * 1.06;
    const extra = Math.max(0, p.extras);
    $("bar").innerHTML =
      `<div class="seg-down" style="width:${p.down / scale * 100}%"><span>${fmt(p.down)}</span></div>` +
      `<div class="seg-extra" style="width:${extra / scale * 100}%"><span>+${fmt(extra)}</span></div>`;
    $("bar").setAttribute("aria-label", `Down payment ${fmt(p.down)} plus ${fmt(extra)} of other cash costs, against savings of ${fmt(p.savings)}.`);
    $("savingsLine").style.left = (p.savings / scale * 100) + "%";
    const sp = p.savings / scale; $("savingsLine").className = "savings-line" + (sp > 0.82 ? " edge" : sp < 0.12 ? " start" : "");
    $("savingsLabel").textContent = "Saved " + fmt(p.savings);

    // meter
    const mp = Math.min(1, p.extrasPct / 0.6);
    $("meter").innerHTML =
      `<div class="meter-head"><span>Surprise meter</span><strong>${pct(p.extrasPct)}</strong></div>` +
      `<div class="meter-track"><div class="meter-fill" style="width:${mp * 100}%"></div></div>` +
      `<p>On top of your down payment, closing costs you another ${pct(p.extrasPct)} of it in cash${p.premium ? `, and ${fmt(p.premium)} of insurance gets added to your mortgage` : ""}.</p>`;

    // amortization availability
    const can30 = state.ftb === "y" && p.insured;
    $("am-30").disabled = !can30;
    if (!can30 && state.am === "30") { state.am = "25"; $("am-25").checked = true; return render(announce); }
    $("amort-note").textContent = can30 ? "30 years lowers the payment but adds 0.20 points to the insurance premium."
      : (state.ftb !== "y" ? "30 years on an insured resale mortgage is for first-time buyers." : "With 20% down there's no insurance, so the 30-year surcharge doesn't apply. Ask your lender.");

    // timeline
    const visible = p.items.filter(i => !i.hidden);
    let bal = p.savings;
    const balances = STAGES.map((s, k) => {
      const out = visible.filter(i => i.when === k && i.kind === "cash").reduce((a, i) => a + i.amount, 0);
      bal -= out; return { out, bal };
    });
    $("stages").innerHTML = STAGES.map((s, k) => {
      const b = balances[k], neg = b.bal < 0;
      return `<button role="tab" id="tab-${k}" aria-controls="stagePanel" aria-selected="${k === state.stage}" tabindex="${k === state.stage ? 0 : -1}" class="stage ${neg ? "neg" : ""}" data-k="${k}">
        <span class="dot" aria-hidden="true">${k + 1}</span><span class="st-name">${s.name}</span>
        <span class="st-out">${b.out ? "-" + fmt(b.out) : "No cash out"}</span>
        <span class="st-bal">${neg ? "Short " + fmt(-b.bal) : "Left " + fmt(b.bal)}</span></button>`;
    }).join("");
    const st = STAGES[state.stage], here = visible.filter(i => i.when === state.stage);
    $("stagePanel").setAttribute("aria-labelledby", "tab-" + state.stage);
    $("stagePanel").innerHTML = `<h3>${st.name} <small>${st.when}</small></h3>` +
      (here.length ? `<ul>${here.map(i => `<li><span>${i.label}</span><strong>${i.kind === "loan" ? "added to loan" : fmt(i.amount)}</strong></li>`).join("")}</ul>` : "<p>Nothing due.</p>") +
      `<p class="bal">${balances[state.stage].bal < 0 ? `By here you've run out, ${fmt(-balances[state.stage].bal)} short.` : `Savings left after this stage: ${fmt(balances[state.stage].bal)}`}</p>`;

    // items
    $("items").innerHTML = visible.map(i => {
      const tag = TAG[i.down ? "down" : i.kind];
      const edits = (EDIT[i.id] || []).map(k => `<label class="edit">${EDIT_LABEL[k]} <input type="number" min="0" step="${k === "depositPct" ? 0.5 : 50}" data-k="${k}" value="${state[k]}"></label>`).join("");
      return `<li class="item"><details data-id="${i.id}" ${state.open === i.id ? "open" : ""}>
        <summary><span class="lbl">${i.label}${i.approx ? ' <em>approx.</em>' : ""}</span>
          <span class="tag ${tag[1]}">${tag[0]}</span><span class="amt">${fmt(i.amount)}</span></summary>
        <div class="why"><p>${why(i, p)}</p>${edits ? `<div class="edits">${edits}</div>` : ""}</div></details></li>`;
    }).join("") +
      `<li class="total"><span>Cash you need on closing</span><strong>${fmt(p.cashToClose)}</strong></li>`;

    // close the gap
    const mx = maxPrice(0);
    $("maxPrice").textContent = fmt(mx);
    $("maxPriceNote").textContent = mx >= state.price
      ? `is the most your ${fmt(p.savings)} covers with these settings. You have room.`
      : `is the most your ${fmt(p.savings)} covers with these settings, ${fmt(state.price - mx)} less than this home.`;
    $("useMax").hidden = mx >= state.price || mx === 0;
    const add = state.hbp + state.gift;
    if (add > 0) {
      const q = compute(null, add);
      $("leverResult").className = "gap-result" + (q.gap < 0 ? " short" : "");
      $("leverResult").textContent = q.gap < 0
        ? `With ${fmt(add)} more you'd still be ${fmt(-q.gap)} short. The most you could pay: ${fmt(maxPrice(add))}.`
        : `With ${fmt(add)} more you're covered, with ${fmt(q.gap)} to spare. The most you could pay: ${fmt(maxPrice(add))}.`;
    } else {
      $("leverResult").className = "gap-result";
      $("leverResult").textContent = short ? `You need ${fmt(-p.gap)} more for this home.` : "You're already covered at this price.";
    }
    $("hbp").closest(".lever").querySelector("small").textContent = state.hbp > 60000 ? "The limit is $60,000 per person. Two buyers can each use it." : "up to $60,000 each, tax-free, repaid over 15 years";

    writeHash();
    clearTimeout(render.t);
    if (announce) render.t = setTimeout(() => {
      $("announce").textContent = `You need ${fmt(p.cashToClose)} on closing. ` + (short ? `You're ${fmt(-p.gap)} short.` : `You're covered with ${fmt(p.gap)} to spare.`);
    }, 700);
  }

  // ---------- events ----------
  function bindMoney(id) {
    const el = $(id);
    el.addEventListener("input", () => { state[id] = num(el.value); render(true); });
    el.addEventListener("blur", () => { el.value = state[id].toLocaleString("en-CA"); });
  }
  bindMoney("price"); bindMoney("savings"); bindMoney("hbp"); bindMoney("gift");
  $("useMax").addEventListener("click", () => { state.price = maxPrice(0); $("price").value = state.price.toLocaleString("en-CA"); render(true); $("price").focus(); });
  [["city", "city"], ["ftb", "ftb"], ["dp", "dp"], ["am", "am"]].forEach(([name, key]) => {
    document.querySelectorAll(`input[name=${name}]`).forEach(r => r.addEventListener("change", () => { state[key] = r.value; render(true); }));
  });
  $("stages").addEventListener("click", e => { const b = e.target.closest(".stage"); if (!b) return; state.stage = +b.dataset.k; render(); $("tab-" + state.stage).focus(); });
  $("stages").addEventListener("keydown", e => {
    const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (e.key === "Home") state.stage = 0; else if (e.key === "End") state.stage = STAGES.length - 1;
    else if (d) state.stage = (state.stage + d + STAGES.length) % STAGES.length; else return;
    e.preventDefault(); render(); $("tab-" + state.stage).focus();
  });
  $("items").addEventListener("toggle", e => { if (e.target.open) state.open = e.target.dataset.id; else if (state.open === e.target.dataset.id) state.open = ""; }, true);
  $("items").addEventListener("change", e => {
    const k = e.target.dataset && e.target.dataset.k; if (!k) return;
    state[k] = Math.max(0, +e.target.value || 0); render(true);
    const again = document.querySelector(`#items input[data-k="${k}"]`); if (again) again.focus();
  });
  $("copyLink").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); $("copied").textContent = "Link copied"; }
    catch (e) { $("copied").textContent = "Copy the address bar to share"; }
    setTimeout(() => $("copied").textContent = "", 2500);
  });
  $("print").addEventListener("click", () => { document.querySelectorAll("#items details").forEach(d => d.open = true); window.print(); });

  // sources
  const S = [["Minimum down payment", RATES.minDown.source], ["CMHC premiums and 30-year surcharge", RATES.cmhc.source],
    ["Ontario sales tax on insurance premiums", RATES.ontarioPstOnPremium.source], ["Ontario land transfer tax", RATES.ontarioLtt.source],
    ["Ontario first-time buyer refund", "https://www.ontario.ca/document/land-transfer-tax/land-transfer-tax-refunds-first-time-homebuyers"],
    ["Toronto land transfer tax", RATES.torontoMltt.source],
    ["Toronto first-time buyer rebate", "https://www.toronto.ca/services-payments/property-taxes-utilities/municipal-land-transfer-tax-mltt/municipal-land-transfer-tax-mltt-rebate-opportunities/"]];
  $("sources").innerHTML = S.map(([t, u]) => `<li><a href="${u}" rel="noopener">${t}</a></li>`).join("");
  $("checked").textContent = new Date(RATES.checked + "T12:00:00").toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });

  // init
  readHash();
  $("price").value = (+state.price).toLocaleString("en-CA");
  $("savings").value = (+state.savings).toLocaleString("en-CA");
  $("hbp").value = (+state.hbp).toLocaleString("en-CA"); $("gift").value = (+state.gift).toLocaleString("en-CA");
  [["city", state.city], ["ftb", state.ftb], ["dp", state.dp], ["am", state.am]].forEach(([n, v]) => { const r = document.querySelector(`input[name=${n}][value="${v}"]`); if (r) r.checked = true; });
  render();
})();
