const L = D.map((r) => r.m);
const f = document.getElementById("from"),
  t = document.getElementById("to");
L.forEach((m) => {
  f.add(new Option(m, m));
  t.add(new Option(m, m));
});
f.value = "2015-01";
t.value = L.filter((m, i) => D[i].policy != null).pop();
const phone = window.matchMedia("(max-width: 600px)").matches;
const opt = (y) => ({
  responsive: true,
  aspectRatio: phone ? 1.1 : 2,
  animation: false,
  interaction: { mode: "index", intersect: false },
  plugins: { legend: { position: "bottom" } },
  scales: { x: { ticks: { maxTicksLimit: phone ? 4 : 12 } }, y: { title: { display: true, text: y } } },
  elements: { point: { radius: 0 } },
});
const ds = (l, k, c, x = {}) =>
  Object.assign(
    {
      label: l,
      data: [],
      borderColor: c,
      backgroundColor: c,
      borderWidth: 2,
      spanGaps: true,
    },
    x,
  );
const C1 = new Chart(c1, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      ds("Policy rate (%)", "policy", "#011f5b", { stepped: true }),
      ds("CPI inflation, y/y (%)", "inflation", "#990000"),
      ds("Inflation target 2%", null, "#8a8578", {
        borderDash: [5, 5],
        borderWidth: 1,
      }),
    ],
  },
  options: opt("Percent"),
});
const C2 = new Chart(c2, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      ds("Policy rate (%)", "policy", "#011f5b", { stepped: true }),
      ds("5-year conventional mortgage (%)", "mortgage", "#b08d2c"),
    ],
  },
  options: opt("Percent"),
});
const C3 = new Chart(c3, {
  type: "bar",
  data: {
    labels: [],
    datasets: [ds("Real policy rate (pts)", "real", "#1b6b3a")],
  },
  options: opt("Percentage points"),
});
const C4 = new Chart(c4, {
  type: "line",
  data: {
    labels: [],
    datasets: [ds("USD/CAD, monthly average", "usdcad", "#4a62a8")],
  },
  options: opt("CAD per USD"),
});
function upd() {
  let a = L.indexOf(f.value),
    b = L.indexOf(t.value);
  if (a > b) [a, b] = [b, a];
  const S = D.slice(a, b + 1),
    lab = S.map((r) => r.m);
  const col = (k) => S.map((r) => r[k]);
  const real = S.map((r) =>
    r.policy != null && r.inflation != null
      ? +(r.policy - r.inflation).toFixed(2)
      : null,
  );
  C1.data.labels = lab;
  C1.data.datasets[0].data = col("policy");
  C1.data.datasets[1].data = col("inflation");
  C1.data.datasets[2].data = S.map(() => 2);
  C2.data.labels = lab;
  C2.data.datasets[0].data = col("policy");
  C2.data.datasets[1].data = col("mortgage");
  C3.data.labels = lab;
  C3.data.datasets[0].data = real;
  C3.data.datasets[0].backgroundColor = real.map((v) =>
    v < 0 ? "#990000" : "#1b6b3a",
  );
  C4.data.labels = lab;
  C4.data.datasets[0].data = col("usdcad");
  [C1, C2, C3, C4].forEach((c) => c.update());
  const mx = (k) => {
    let r = S.filter((x) => x[k] != null);
    return r.length ? r.reduce((p, c) => (c[k] > p[k] ? c : p)) : null;
  };
  const last = (k) => S.filter((x) => x[k] != null).pop();
  const i = mx("inflation"),
    p = mx("policy"),
    m = mx("mortgage"),
    lp = last("policy"),
    li = last("inflation");
  kpis.innerHTML = [
    [i ? i.inflation + "%" : "n/a", "Peak inflation (" + (i ? i.m : "") + ")"],
    [p ? p.policy + "%" : "n/a", "Peak policy rate (" + (p ? p.m : "") + ")"],
    [
      m ? m.mortgage + "%" : "n/a",
      "Peak 5-year mortgage (" + (m ? m.m : "") + ")",
    ],
    [
      lp ? lp.policy + "% / " + (li ? li.inflation + "%" : "") : "",
      "Policy rate / inflation at end of window",
    ],
  ]
    .map(
      (x) =>
        '<div class="k"><b>' + x[0] + "</b><span>" + x[1] + "</span></div>",
    )
    .join("");
}
f.onchange = t.onchange = upd;
reset.onclick = () => {
  f.value = L[0];
  t.value = L[L.length - 1];
  upd();
};
upd();
