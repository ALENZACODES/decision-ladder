import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const csv = readFileSync(new URL("../data.csv", import.meta.url), "utf8").trim().split(/\r?\n/);
const header = csv[0].split(",");
const rows = csv.slice(1).map((line) => {
  const cells = line.split(",");
  const row = {};
  header.forEach((h, i) => {
    row[h] = h === "m" ? cells[i] : cells[i] === "" ? null : Number(cells[i]);
  });
  return row;
});

const js = readFileSync(new URL("../src/data.js", import.meta.url), "utf8");
const embedded = JSON.parse(js.slice(js.indexOf("["), js.lastIndexOf("]") + 1));

test("data.csv has the expected columns", () => {
  assert.deepEqual(header, ["m", "policy", "cpi", "inflation", "mortgage", "usdcad"]);
});

test("one row per month, no gaps, from January 2015", () => {
  assert.equal(rows[0].m, "2015-01");
  for (let i = 1; i < rows.length; i++) {
    const [y, m] = rows[i - 1].m.split("-").map(Number);
    const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
    assert.equal(rows[i].m, next);
  }
});

test("the page uses exactly the data in data.csv", () => {
  assert.deepEqual(embedded, rows);
});

test("inflation is the year-over-year change in CPI", () => {
  for (let i = 12; i < rows.length; i++) {
    const r = rows[i];
    if (r.inflation === null) continue;
    const expected = (r.cpi / rows[i - 12].cpi - 1) * 100;
    assert.ok(Math.abs(expected - r.inflation) < 0.01, `${r.m}: ${r.inflation} vs ${expected.toFixed(2)}`);
  }
});

test("values are in plausible ranges", () => {
  for (const r of rows) {
    if (r.policy !== null) assert.ok(r.policy >= 0 && r.policy <= 10, r.m);
    if (r.mortgage !== null) assert.ok(r.mortgage >= 2 && r.mortgage <= 10, r.m);
    if (r.usdcad !== null) assert.ok(r.usdcad >= 1 && r.usdcad <= 2, r.m);
  }
});

test("headline figures in the README match the data", () => {
  const at = (m) => rows.find((r) => r.m === m);
  assert.equal(Math.max(...rows.map((r) => r.inflation ?? -Infinity)), at("2022-06").inflation);
  assert.equal(at("2022-06").inflation.toFixed(1), "8.1");
  assert.equal(at("2022-03").policy, 0.5);
  assert.equal(at("2022-02").policy, 0.25);
  assert.equal(Math.max(...rows.map((r) => r.mortgage ?? -Infinity)), 7.04);
  assert.equal(at("2023-10").mortgage, 7.04);
  assert.equal(Math.max(...rows.map((r) => r.policy ?? -Infinity)), 5);
});
