# Submission checklist: deadline Fri Oct 30, 2026, 10:00 AM PT (1:00 PM Toronto)

Submissions lock at the deadline. Don't edit the repo, video or Devpost page after it.

## Ready now (no key needed)
- [x] Public repo with MIT LICENSE and a README with setup and run instructions
- [x] App, CLI, tests (CI on GitHub Actions), offline demo mode
- [x] Devpost text: `docs/DEVPOST_SUBMISSION.md`
- [x] Video script: `docs/VIDEO_SCRIPT.md`; automated recorder: `scripts/record_demo.mjs`
- [ ] Deploy the demo URL now in offline mode (`docs/DEPLOY.md`, Render option A). The URL then exists before the key does.
- [ ] Devpost draft #1269923: paste the text, choose **Best Apps and Agents**, add the repo link and screenshots from `docs/screenshots/`

## The moment the key arrives (about 30 minutes total)
1. Double-click **Go Live.cmd** (Windows). It asks for the key (hidden), lists models, runs `smoke`, runs `eval`, then opens the app.
   - All smoke checks should PASS. If a model-ID check fails, the note at the end gives the `DL_MODEL_*` values to set.
2. Add `NEBIUS_API_KEY` to the Render service and redeploy. Confirm `/api/health` shows `"mode": "live"`.
3. Record: start the app (live), then run `node scripts/record_demo.mjs`. Watch `demo/decision-ladder-demo.mp4`, which must be under 3:00 and show the green LIVE badge and Nemotron model names.
   - Optional voice-over: read `demo/narration.txt`, or generate it with your voice clone, and lay it over the video in CapCut using `narration.srt` for timing.
4. Upload to YouTube as **Public** (not unlisted) early, because uploads are slow.
5. Paste real numbers from `eval_report.json` and `smoke_report.json` into the Devpost "Challenges" or "Accomplishments" sections. Only use numbers you actually got.
6. Write the Nebius/NVIDIA feedback section from your own experience. It's a separate prize.
7. Submit. Then check that the submission page shows the video, repo link, demo URL and track.

## If the key does NOT arrive in time
- Claim the activation code **NEBIUS-DEVPOST-GLOBAL26** (Token Factory credit form linked in the "You're in!" Devpost email). That may be faster than the Builder Program review.
- Ask in the Nebius Discord (linked in the Devpost emails) for help getting hackathon credits.
- Never submit the offline video as if it were live. The rules require the project to run on Token Factory with an NVIDIA model.
