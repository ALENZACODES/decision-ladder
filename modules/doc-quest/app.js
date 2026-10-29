(function () {
  const $ = id => document.getElementById(id);
  const KEY = "docquest.v1";
  const saved = JSON.parse(localStorage.getItem(KEY) || "null");
  const S = saved || { answers: null, done: {}, simple: false };
  const save = () => localStorage.setItem(KEY, JSON.stringify(S));
  const say = t => { $("live").textContent = ""; setTimeout(() => $("live").textContent = t, 50); };
  const mins = m => { if (m < 60) return `about ${m} min`; const h = Math.floor(m / 60), r = Math.round((m % 60) / 5) * 5; return `about ${h} h${r ? " " + r + " min" : ""}`; };

  // the "before" wall: every jargon line a lender might send
  $("wall").innerHTML = DOCS.map(d => `<li>${d.jargon}</li>`).join("");

  function readForm() {
    const f = $("qs");
    return {
      work: f.work.value,
      sources: [...f.querySelectorAll("input[name=src]:checked")].map(i => i.value),
      newcomer: f.newcomer.value === "y",
      ownOther: f.own.value === "y",
      partner: f.partner.value === "y"
    };
  }
  function fillForm(a) {
    const f = $("qs");
    f.querySelector(`input[name=work][value="${a.work}"]`).checked = true;
    f.querySelectorAll("input[name=src]").forEach(i => i.checked = a.sources.includes(i.value));
    f.querySelector(`input[name=newcomer][value="${a.newcomer ? "y" : "n"}"]`).checked = true;
    f.querySelector(`input[name=own][value="${a.ownOther ? "y" : "n"}"]`).checked = true;
    f.querySelector(`input[name=partner][value="${a.partner ? "y" : "n"}"]`).checked = true;
  }

  function text(d) { return S.simple ? d.simple : d.plain; }
  function card(d, i) {
    const slow = d.wait > 0;
    return `<li class="card ${slow ? "slow" : ""}">
      <div class="card-top"><span class="n" aria-hidden="true">${i + 1}</span>
        <h2 id="t-${d.id}">${d.title}</h2>
        ${slow ? `<span class="badge">Ask today. Takes ${d.wait === 1 ? "a day" : "a few days"}</span>` : `<span class="badge quick">${d.minutes} min</span>`}</div>
      <p>${text(d)}</p>
      <p class="where"><b>Where to get it:</b> ${d.where}</p>
      <p class="jargon">Your lender may call it: <i>${d.jargon}</i></p>
      <button type="button" class="btn tick" data-done="${d.id}" aria-describedby="t-${d.id}">I have this</button>
    </li>`;
  }
  function row(d, undo) {
    return `<li><span><b>${d.title}</b> <small>${d.group}${d.minutes ? " · " + d.minutes + " min" : ""}</small></span>
      ${undo ? `<button type="button" class="link" data-undo="${d.id}">Undo</button>` : ""}</li>`;
  }

  function render(focusHead) {
    const a = S.answers;
    $("ask").hidden = !!a; $("plan").hidden = !a;
    $("simple").checked = S.simple;
    document.body.classList.toggle("is-simple", S.simple);
    if (!a) return;
    const all = Logic.ordered(a), next = Logic.nextUp(a, S.done, 3);
    const nextIds = new Set(next.map(d => d.id));
    const rest = all.filter(d => !d.later && !S.done[d.id] && !nextIds.has(d.id));
    const offer = all.filter(d => d.later);
    const done = all.filter(d => !d.later && S.done[d.id]);
    const p = Logic.progress(a, S.done);

    $("prog").innerHTML = `<div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="${p.total}" aria-valuenow="${p.done}" aria-label="Papers gathered"><i style="width:${p.total ? p.done / p.total * 100 : 0}%"></i></div>
      <span>${p.done} of ${p.total} gathered${p.minutesLeft ? ` · ${mins(p.minutesLeft)} of work left` : ""}</span>`;
    $("plan-h").textContent = next.length ? (next.length === 1 ? "Your last one" : `Your next ${next.length === 2 ? "two" : "three"}`) : "All set";
    $("next").innerHTML = next.map(card).join("");
    $("doneAll").hidden = next.length > 0;
    $("rest").innerHTML = rest.map(d => row(d)).join("") || "<li>Nothing else. These are the last ones.</li>";
    $("laterCount").textContent = `(${rest.length})`;
    $("offer").innerHTML = offer.map(d => row(d)).join("");
    $("offerCount").textContent = `(${offer.length})`;
    $("doneList").innerHTML = done.map(d => row(d, true)).join("") || "<li>Nothing yet.</li>";
    $("doneCount").textContent = `(${done.length})`;
    $("partnerNote").hidden = !a.partner;
    $("partnerNote").textContent = "Applying with someone? They need their own copy of everything under You and Income. The down payment papers are shared.";
    save();
    if (focusHead) $("plan-h").focus();
  }

  $("qs").addEventListener("submit", e => {
    e.preventDefault(); S.answers = readForm(); render(true);
    const p = Logic.progress(S.answers, S.done);
    say(`Your list has ${p.total} papers. Showing the first three.`);
  });
  $("next").addEventListener("click", e => {
    const id = e.target.dataset && e.target.dataset.done; if (!id) return;
    const idx = [...$("next").querySelectorAll("[data-done]")].findIndex(b => b.dataset.done === id);
    S.done[id] = true; const d = DOCS.find(x => x.id === id);
    render();
    // keep the user in place: focus the card now sitting where the ticked one was
    const btns = $("next").querySelectorAll("[data-done]");
    const target = btns[Math.min(idx, btns.length - 1)];
    if (target) target.focus(); else $("plan-h").focus();
    const p = Logic.progress(S.answers, S.done);
    say(`${d.title} done. ${p.done} of ${p.total}.`);
  });
  $("doneList").addEventListener("click", e => {
    const id = e.target.dataset && e.target.dataset.undo; if (!id) return;
    delete S.done[id]; render(); say("Moved back to your list.");
  });
  $("simple").addEventListener("change", e => { S.simple = e.target.checked; render(); });
  $("edit").addEventListener("click", () => { fillForm(S.answers); S.answers = null; render(); $("ask-h").scrollIntoView(); $("qs").querySelector("input").focus(); });
  $("restart").addEventListener("click", () => { if (!confirm("Clear your answers and progress?")) return; S.answers = null; S.done = {}; save(); location.reload(); });
  $("print").addEventListener("click", () => { document.querySelectorAll("details.more").forEach(d => d.open = true); window.print(); });

  if (S.answers) fillForm(S.answers);
  render();
})();
