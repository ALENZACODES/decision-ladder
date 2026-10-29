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

async function scene(page, text, seconds, action) {
  const start = now();
  await caption(page, text);
  if (action) await action();
  const left = seconds - (now() - start);
  if (left > 0) await page.waitForTimeout(left * 1000);
  scenes.push({ start, end: now(), text });
}

async function tab(page, name) {
  await page.click(`button.tab[data-tab="${name}"]`);
  await page.waitForTimeout(400);
}

// A click starts a request: wait until the button shows it is busy (disabled), then until it is idle again.
async function waitIdle(page, selector, timeout = 120000) {
  await page.waitForFunction((sel) => document.querySelector(sel)?.disabled, selector, { timeout: 3000 }).catch(() => {});
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

  await scene(page, "Decision Ladder: Canadian mortgage decisions, top down. NVIDIA Nemotron on Nebius Token Factory reasons; tested calculators decide.", 9);

  await scene(page, "A client emails their broker. Nemotron Nano extracts the file. Every value must quote the sentence it came from, or it is dropped.", 14, async () => {
    await tab(page, "intake");
    await page.click("#btnExtractRun");
    await waitIdle(page, "#btnExtractRun");
    await smoothScroll(page, 300);
  });

  await scene(page, "The file climbs eleven rungs. Every rung is deterministic, tested code: screening, insurance, the OSFI B-20 stress test, lender fit, market, exit cost.", 14, async () => {
    await tab(page, "ladder");
    await page.selectOption("#samplePick", { index: 0 }).catch(() => {});
    await page.click("#runLadder");
    await waitIdle(page, "#runLadder");
  });
  await scene(page, "This purchase fails the stress test. Instead of stopping at no, the ladder computes the path to yes, and re-checks every option against the same test.", 12, async () => {
    const r = await page.$("text=B-20 stress test");
    if (r) await r.click().catch(() => {});
    await page.waitForTimeout(800);
    await smoothScroll(page, 1350);
  });
  await scene(page, "Nemotron 3 Super writes the broker memo. A provenance verifier traces every figure back to a calculator; anything it cannot trace is flagged on screen.", 12, async () => {
    await smoothScroll(page, 950);
  });

  await scene(page, "As a copilot, Nemotron chooses among 19 tools. Here: TD's own penalty method, with TD's posted rates from the rate book.", 16, async () => {
    await tab(page, "copilot");
    const chip = await page.$("text=What is the penalty to break a TD");
    if (chip) await chip.click();
    await page.click("#chatSend").catch(() => {});
    await waitIdle(page, "#chatSend");
    await smoothScroll(page, 500);
  });
  await scene(page, "For anything newer than the rate book, Tavily searches only official Canadian sources: Bank of Canada, OSFI, FSRA, CMHC. Every source is cited.", 16, async () => {
    const chip = await page.$("text=What did the Bank of Canada do most recently");
    if (chip) await chip.click();
    await page.click("#chatSend").catch(() => {});
    await waitIdle(page, "#chatSend");
    await smoothScroll(page, 2000);
  });

  await scene(page, "For a whole book: a ranked renewal queue with payment shock, today's penalty by lender method, and outreach drafts that pass a compliance guardrail.", 14, async () => {
    await tab(page, "book");
    await page.click("#btnBook");
    await waitIdle(page, "#btnBook");
    await smoothScroll(page, 450);
  });

  await scene(page, "Every number carries its date and source: Bank of Canada Valet series and the Big-6 banks' own posted rates.", 9,
    () => tab(page, "market"));

  await scene(page, "Open source, MIT, zero dependencies, 240+ tests. Nemotron reasons; calculators decide.", 8,
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
