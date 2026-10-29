// Automated demo recording: drives the running app through docs/VIDEO_SCRIPT.md with on-screen captions,
// records the browser, and writes demo/decision-ladder-demo.mp4 plus demo/narration.srt and demo/narration.txt
// (the voice-over lines with timings, ready for your own voice or an ElevenLabs clone of it).
//
//   1. start the app:     python -m decision_ladder serve 8000          (live: NEBIUS_API_KEY set)
//   2. one-time setup:    npm i playwright && npx playwright install chromium   (ffmpeg on PATH for mp4)
//   3. record:            node scripts/record_demo.mjs [http://localhost:8000]
//
// The captions are part of the video, so it reads well even without a voice-over. Live model calls take
// a few seconds; each scene waits for its result before moving on, then holds for the caption time.
import { createRequire } from "module";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8000";
const OUT = path.resolve("demo");
fs.mkdirSync(OUT, { recursive: true });

const W = 1440, H = 900;
const scenes = [];  // {start, end, text}
let t0 = 0;
const now = () => (Date.now() - t0) / 1000;

async function caption(page, text) {
  await page.evaluate((txt) => {
    let el = document.getElementById("__cap");
    if (!el) {
      el = document.createElement("div");
      el.id = "__cap";
      Object.assign(el.style, {
        position: "fixed", left: "50%", bottom: "28px", transform: "translateX(-50%)", zIndex: 99999,
        maxWidth: "1100px", padding: "14px 22px", borderRadius: "12px", background: "rgba(10,18,36,.92)",
        color: "#fff", font: "600 22px/1.35 system-ui,-apple-system,Segoe UI,Roboto,sans-serif",
        boxShadow: "0 8px 30px rgba(0,0,0,.35)", borderLeft: "6px solid #76b900", textAlign: "left",
      });
      document.body.appendChild(el);
    }
    el.textContent = txt;
  }, text);
}

// A scene shows its caption, runs its action, then holds: at least `seconds` in total and at least
// HOLD seconds after the action finished, so a slow live model call never cuts the result off screen.
const HOLD = 4;
async function scene(page, text, seconds, action) {
  const start = now();
  await caption(page, text);
  if (action) await action();
  const left = Math.max(seconds - (now() - start), HOLD);
  await page.waitForTimeout(left * 1000);
  scenes.push({ start, end: now(), text });
}

async function tab(page, name) {
  await page.click(`button.tab[data-tab="${name}"]`);
  await page.waitForTimeout(400);
}

// A click starts a request: wait until the button shows it is busy (disabled), then until it is idle again.
async function waitIdle(page, selector, timeout = 120000) {
  await page.waitForFunction((sel) => document.querySelector(sel)?.disabled, selector, { timeout: 1500 }).catch(() => {});
  await page.waitForFunction((sel) => {
    const b = document.querySelector(sel);
    return b && !b.disabled;
  }, selector, { timeout }).catch(() => {});
  await page.waitForTimeout(600);
}

const smoothScroll = (page, y) => page.evaluate((yy) => window.scrollTo({ top: yy, behavior: "smooth" }), y);

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: OUT, size: { width: W, height: H } } });
  const page = await context.newPage();
  t0 = Date.now();
  await page.goto(BASE);
  await page.waitForTimeout(1200);
  const mode = await page.textContent("#modeBadge");
  console.log("mode badge:", mode);

  const rung = async (title) => {
    const b = page.locator("button.rung", { hasText: title }).first();
    await b.scrollIntoViewIfNeeded().catch(() => {});
    await b.click().catch(() => {});
    await page.waitForTimeout(700);
  };

  await scene(page, "Decision Ladder Mortgage OS: fourteen of my own mortgage apps in one system, driven by NVIDIA Nemotron on Nebius Token Factory.", 10);
  await scene(page, "Every stage of a Canadian mortgage, from first email to renewal and commercial deals. Each card is one of my apps, running inside the OS.", 9,
    () => smoothScroll(page, 420));

  await scene(page, "A client emails her broker. Nemotron Nano extracts the file and reads her pay stub and T4; every value must quote its source.", 14, async () => {
    await tab(page, "intake");
    for (const t of ["+ Pay stub", "+ T4 slip"]) await page.click(`text=${t}`).catch(() => {});
    await page.click("#btnExtractRun");
    await waitIdle(page, "#btnExtractRun");
    await smoothScroll(page, 260);
  });

  await scene(page, "Her file climbs a 17-rung ladder. Each rung is computed by one of my apps: Doc Quest, the Mortgage Suite, the Pre-Underwriting Check, Benchmark Home Value, Cash to Close.", 15, async () => {
    await tab(page, "os");
    await smoothScroll(page, 0);
    await page.click("#osRunPriya");
    await waitIdle(page, "#runLadder");
  });
  await scene(page, "The B-20 stress test fails. The ladder computes a path to yes, re-checking every option against the same test.", 10,
    () => rung("B-20 stress test"));
  await scene(page, "Cash to Close finds she is $19,875 short on closing day, and finds the down payment that keeps cash for closing costs.", 11,
    () => rung("Cash to close"));
  await scene(page, "Five independent engines, in Python and JavaScript, compute the same quantities. They agree to the cent; differences are labelled, never hidden.", 12,
    () => rung("Cross-check"));
  await scene(page, "Every number opens in the app that computed it: here, Cash to Close, embedded in the OS.", 10, async () => {
    await rung("Cash to close");
    const link = page.locator(".eng.link", { hasText: "Cash to Close" }).first();
    await link.click().catch(() => {});
    await page.waitForTimeout(1500);
  });
  await scene(page, "Nemotron 3 Ultra writes the credit decision; a provenance verifier traces every figure back to a calculator.", 10, async () => {
    await tab(page, "ladder");
    const memo = page.locator("text=Broker decision memo").first();
    await memo.scrollIntoViewIfNeeded().catch(() => {});
  });

  await scene(page, "As a copilot, Nemotron Nano routes each question to the right apps, and Nemotron Super calls their tools.", 14, async () => {
    await tab(page, "copilot");
    await page.fill("#chatInput", "A first-time buyer in Ontario has $60,000 saved and wants a $700,000 home. How much cash do they need on closing day, and what is the land transfer tax?");
    await page.click("#chatSend").catch(() => {});
    await waitIdle(page, "#chatSend");
    await smoothScroll(page, 600);
  });

  await scene(page, "Five years later, renewal: Renewal Radar reads the letter, checks the switch pathway, drafts the negotiation script and computes the lender-exact penalty.", 13, async () => {
    await tab(page, "ladder");
    await page.selectOption("#samplePick", "pandemic_renewal_rbc").catch(() => {});
    await page.click("#runLadder");
    await waitIdle(page, "#runLadder");
    await rung("Exit cost");
  });

  await scene(page, "Commercial deals go through the Private Credit Deal Screener: DSCR, debt yield, grade, and which assumption moves it.", 10, async () => {
    await page.selectOption("#samplePick", "hamilton_commercial").catch(() => {});
    await page.click("#runLadder");
    await waitIdle(page, "#runLadder");
    await rung("Commercial");
  });

  await scene(page, "Overnight, the whole book runs as a Nebius Serverless job: a ranked renewal queue with lender-exact penalties and guardrailed outreach.", 11, async () => {
    await tab(page, "book");
    await page.click("#btnBook");
    await waitIdle(page, "#btnBook");
    await smoothScroll(page, 450);
  });

  await scene(page, "Open source, MIT. Nemotron Nano, Super and Ultra on Token Factory, Tavily for live sources, and every number from tested code.", 8,
    () => tab(page, "how"));

  await page.close();
  const webm = await page.video().path();
  await context.close();
  await browser.close();

  const pad = (n, w = 2) => String(n).padStart(w, "0");
  const ts = (s) => `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(Math.floor(s % 60))},${pad(Math.round((s % 1) * 1000), 3)}`;
  fs.writeFileSync(path.join(OUT, "narration.srt"), scenes.map((s, i) => `${i + 1}\n${ts(s.start)} --> ${ts(s.end)}\n${s.text}\n`).join("\n"));
  fs.writeFileSync(path.join(OUT, "narration.txt"), scenes.map((s) => `[${s.start.toFixed(1)}s] ${s.text}`).join("\n\n") + "\n");
  const total = scenes.length ? scenes[scenes.length - 1].end : 0;
  console.log(`recorded ${total.toFixed(1)} s (limit 180 s) -> ${webm}`);
  const mp4 = path.join(OUT, "decision-ladder-demo.mp4");
  try {
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", webm, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]);
    console.log("wrote", mp4);
  } catch (e) {
    console.log("ffmpeg not available; upload the .webm directly or convert it:", webm);
  }
  if (total > 175) console.log("WARNING: longer than 2:55; shorten scene times before uploading.");
})();
