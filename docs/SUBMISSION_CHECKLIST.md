# Submission checklist: deadline Fri Oct 30, 2026, 1:00 PM EDT (10:00 AM PT)

Submissions lock at the deadline. Don't edit the repo, video or Devpost page after it.

## Ready now
- [x] Public repo, MIT license, README covering setup, Nemotron, Token Factory, Tavily and Nebius Serverless usage
- [x] 14 modules embedded; a 17-rung journey; cross-checks; Nano / Super / Ultra; Tavily Search and Extract
- [x] CI green (OS tests + each app's own tests); the container image is published to `ghcr.io/alenzacodes/decision-ladder`
- [x] Devpost text: `docs/DEVPOST_SUBMISSION.md`
- [x] Video script and automatic recorder: `docs/VIDEO_SCRIPT.md`, `scripts/record_demo.mjs`
- [ ] **Demo URL now, in offline mode** (Render, from `docs/DEPLOY.md`). It switches to live as soon as you add the key.
- [ ] Devpost draft #1269923: paste the text, choose **Best Apps and Agents**, add the repo link and screenshots from `docs/screenshots/`

## When the key arrives (about 45 minutes)
1. Double-click **Go Live.cmd**. Paste the key (hidden). It lists models, runs `smoke` and `eval`, then opens the app.
   - Every smoke check should pass. The models check reports whether Nemotron 3 Ultra is available to your key; if not, Super writes the memo, and that is stated in the app.
2. Add `NEBIUS_API_KEY` (and `TAVILY_API_KEY`) to the demo host, redeploy, and check that `/api/health` shows `"mode": "live"`.
3. Optional but strong: run `deploy/nebius/endpoint.sh` (Serverless endpoint) and `deploy/nebius/job.sh` (renewal-book job), and screenshot both in the Nebius console for the video or Devpost.
4. Record: `node scripts/record_demo.mjs http://localhost:8000`, then add the voice-over, then upload to YouTube as **Public**.
5. Put real numbers from `eval_report.json` and `smoke_report.json` into the Devpost text, and only numbers you actually got.
6. Write the feedback section from your own experience. It's a separate prize.
7. Submit, then check the video, repo, demo URL and track on the submission page.

## If the key is late
- Use the activation code **NEBIUS-DEVPOST-GLOBAL26** (Token Factory credit form linked in the Devpost "You're in!" email).
- Ask in the Nebius Discord for help with hackathon credits.
- Never submit the offline video as if it were live.
