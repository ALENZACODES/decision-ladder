# Devpost submission text (Nebius × NVIDIA Global AI Hackathon)

**Project name:** Decision Ladder: Mortgage OS
**Tagline:** Every stage of a Canadian mortgage, one system. Nemotron reasons; calculators decide.
**Track:** Best Apps and Agents
**Built with:** NVIDIA Nemotron 3 Nano, Super and Ultra; Nebius Token Factory; Tavily (Search and Extract); Nebius Serverless AI endpoint and job definitions (scripts in the repo, not yet deployed); Python; Node.js; vanilla JS
**Repo:** https://github.com/ALENZACODES/decision-ladder
**Demo:** (your deployed URL)
**Video:** (your YouTube URL)

---

## For each judging team

**NVIDIA (Nemotron).** Every tier does the job it is best at, measured live on Token Factory: Nano 30B-A3B routes each question to the right apps (Super then sees 24 to 37 of 92 tools) and extracts client emails in JSON mode; Super 120B-A12B calls the tools (right tool in 15 to 16 of 17 eval cases across two runs); Ultra 550B-A55B writes the one decision that has to be right, and all five Ultra memos traced every figure to a calculator in both runs. The model never does arithmetic, and a provenance verifier gives it one repair turn before any untraced figure is marked `[unverified]` on screen.

**Nebius Token Factory.** One OpenAI-compatible client, models resolved from `/v1/models` at start-up, `chat_template_kwargs.enable_thinking` per tier, retries, and a live workflow that anyone with a key can rerun: `gh workflow run live.yml` produces the smoke test, the 17-case eval and the five Ultra memos (raw reports on the `live-results` branch). A full live run cost about $0.20. The feedback section below is from those runs, not from memory.

**Tavily.** Search is restricted to official Canadian sources (Bank of Canada, OSFI, CMHC, FSRA), and Extract reads each lender's own rate page to check whether a quoted rate is still current before the memo relies on it. Live run 40909847212: Search returned the Bank of Canada's Oct 28, 2026 rate announcement and OSFI's 2026-2027 risk outlook, and Extract read RBC's and TD's own rate pages and flagged that neither page showed the posted 5-year rate in the OS's Oct 15 rate book (TD 6.14, RBC 6.19), so the broker confirms the rate before a penalty is quoted. The smoke test passed 9/9 with Tavily on.

**Nebius Serverless and AI Cloud.** The same container runs locally, on any host, or as a Nebius Serverless endpoint; the overnight renewal-book scan is written as a stateless job with input and output files so it can run as a Serverless job. The scripts are in the repo; I have not deployed them yet.

**Everyone.** It is built by a licensed Ontario mortgage broker for real broker work, on 20 of my own repositories plus five desks written for this hackathon (556+ tests). Rules are checked against official sources and cited in every result; anything that is an assumption says so.

## Inspiration

I'm a licensed mortgage broker in Ontario and a data scientist. Over the past year I built separate tools for each part of my job: a land transfer tax and closing-cost suite, a cash-to-close planner, a document checklist, a pre-underwriting checker, a home-value estimator, a renewal-penalty engine checked against the banks' own calculators, a renewal-shock model, a private-credit screener, and more.

A real client doesn't arrive one tool at a time. One email leads to affordability, documents, the stress test, the property, closing costs, and a renewal five years later. Meanwhile, the last of the pandemic-era five-year fixed mortgages are renewing: the Bank of Canada says that's about 12% of all mortgages, with payments up about 15% on average.

So I put all of my apps inside one system and gave it an agent. The rule is the same as in my practice: the model can read, plan, choose and explain, but it never does the arithmetic.

## What it does

**One client, start to finish.** Priya emails: a $1.1M semi in Oakville, $220K saved, a 4.19% offer.
- **Lead and documents.** Nemotron Nano extracts her file; every value must quote her email. It reads her pay stub and T4. **Doc Quest** builds her checklist.
- **Underwriting.**
  - The **Canadian Mortgage Suite** says her income supports $1,064,600.
  - The **Pre-Underwriting Check** scores her file 20/100.
  - **MortgageLoanOps** fails the B-20 stress test (GDS 39.9%, TDS 45.4%).
  - The ladder then works out a path to yes, re-checking each option against the same test.
- **Property.** **Benchmark Home Value** puts her price 7.2% below the Oakville semi benchmark.
- **Closing.** **Cash to Close** finds she'd be **$19,875 short on closing day**, and finds the down payment that keeps cash for closing costs. One click opens Cash to Close with her numbers, showing the same $19,875.
- **Servicing.** **Renewal Shock Radar** shows what a rate one point higher would do to her payment at renewal.
- **Decision.** **Nemotron 3 Ultra** writes the credit decision. A verifier checks that every figure came from a calculator.

**Five years later,** **Renewal Radar** reads her renewal letter and checks whether a straight switch avoids the stress test. It drafts a retention script and computes the penalty with the lender's exact method.

**Commercial deals** go through the **Private Credit Deal Screener**: DSCR, debt yield, a letter grade, and the assumption that moves the grade most.

**Overnight,** a batch job (packaged to run as a Nebius Serverless job) scans the whole renewal book and ranks who to call, with lender-exact penalties and outreach drafts that pass a compliance guardrail.

## How we built it

- **21 modules from 20 of my repositories: 79,503 lines of their own code** Five new desks (commercial, business lending, income and rental, servicing, disclosure) add 8,710 lines; the repository totals 100,180 lines of code. Each app runs its own screen inside the OS. The JavaScript apps' calculators run through a small Node bridge that loads each app's real `calc.js`, so the agent, the ladder and the app's screen always agree. Renewal Radar's Python engines are imported in-process, and its FastAPI app is proxied.
- **A 17-rung ladder covers the lifecycle:** lead, documents, pre-qualification, underwriting, property, closing, market, servicing, commercial, compliance, decision. Each rung is computed by one of the apps and returns PASS, REFER, FAIL or SKIP.
- **Three Nemotron tiers on Token Factory, as the brief recommends:**
  - **Nano** routes each question to the right lifecycle stages; Super then sees about 8 to 15 of the 92 tools instead of all of them. Nano also does the JSON extraction and drafts.
  - **Super** runs the tool calls.
  - **Ultra** writes the credit decision, falling back to Super if Ultra isn't available.
- **A standard-library Token Factory client.** It handles tool calling, JSON mode with a fallback, retries, `<think>` stripping, recovery of inline tool calls (Qwen3-Coder XML and `<TOOLCALL>` formats), model auto-resolution against `/v1/models`, and token and cost accounting.
- **Tavily.**
  - Search runs on official Canadian domains only (Bank of Canada, OSFI, FSRA, CMHC, Canada.ca), and every source is cited.
  - Extract reads each Big-6 bank's own rate page and confirms whether the rate book's posted 5-year rate is still current.
- **Nebius Serverless AI (ready, not yet deployed).** A GitHub Action publishes the container image; `deploy/nebius/endpoint.sh` serves the OS as a CPU endpoint and `deploy/nebius/job.sh` runs the renewal-book scan as a job billed only while it runs. I have not run either on Nebius during the submission period.
- **Tests.** Over 350 OS tests and every JavaScript app's own test suite run in CI.

## Cross-checks: my apps check each other

Several of my calculators were built separately, in Python and JavaScript. Where they overlap, the OS runs all of them on the same inputs, and **every overlapping quantity agrees to the cent**:
- land transfer tax and first-time-buyer refunds
- CMHC premium
- qualifying rate and payment
- payment at renewal
- the IRD penalty: three engines, all at $17,013.33

Differences are labelled, not hidden. TD's own calculator method, reproduced in Renewal Radar, counts the time left day-exact and gives $16,363.73; the OS uses that lender-exact figure.

The cross-check also **caught a real bug** while I was integrating: my MortgageLoanOps stress test qualified insured files without the CMHC premium in the loan. It's fixed and tested.

## Challenges we ran into

- **Keeping the model away from arithmetic, with 92 tools across 21 modules and 5 desks.** Nano routing kept tool choice focused, and the provenance verifier, with one repair turn, kept the answers honest.
- **Making separately built apps agree.** Aligning their inputs for the cross-checks was most of the work. It turned up one real bug and one real method difference.
- **Grounding extraction.** A value from an email or a pay stub is kept only if its quoted words appear in the source.

## Accomplishments that we're proud of

- A single client journey that runs through my real apps, with every number traceable to the app that computed it, and each app opens with the client's own numbers.
- A path to yes that can't contradict the decline: for the stress test and for cash to close.
- Every overlapping calculation in my apps agrees, and the OS proves it on every file.
- Live on Token Factory: up to 9/9 smoke checks (with Tavily), the right tool in 15 to 16 of 17 eval cases across three runs, and 14 of 15 Nemotron 3 Ultra memos fully traced to calculators (the one exception was visibly marked).

## What we learned

Nemotron is very good at the parts of mortgage work that are language: reading, routing, planning and explaining. Its value multiplies when its tools are trusted. The three tiers matter in practice: Nano for the many cheap calls, Super for tool use, Ultra for the one decision that has to be right.

## What's next for Decision Ladder

- A licensed screening provider and live lender policy feeds.
- OCR in front of document reading.
- A dedicated Nemotron endpoint for book-scale overnight runs.
- A pilot in my brokerage.

---

## What was significantly updated during the submission period

The submission period ran from Aug 26 to Oct 30, 2026. All 21 module projects are my own, created in October 2026.

The Mortgage OS itself was built for this hackathon:
- the module system and embedded apps
- the staged ladder
- the cross-checks
- the three-tier Nemotron design
- the Token Factory client
- the verifier
- grounded intake and document reading
- Tavily Search and Extract
- the Serverless job and endpoint definitions (container, scripts; not yet deployed)
- the UI, evals and CI
- five new desks: commercial lending, business lending, income and rental qualification, servicing, disclosure and compliance

## Feedback on Nebius and NVIDIA tools

From two live runs on 2026-10-29 (reports on the repo's `live-results` branch):

- **Getting started.** The AI Builder Program email gives a Token Factory promo code, not a key, and Token Factory asks for full billing details with a card before a key can be created. A hackathon path that issues a key with the credit already applied would remove the biggest blocker I hit.
- **`/v1/models`.** 29 models were listed, 5 of them Nemotron. The IDs follow three different naming styles (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/Nemotron-3-Ultra-550b-a55b`), so I resolve models from the list at start-up instead of hard-coding them. Consistent IDs, or documented aliases, would help.
- **Nemotron 3 Super tool calling** was strong: the right tool in 15 to 16 of 17 eval cases across three runs, with 24 to 37 tools offered per question (out of 92). Two rough edges: once it returned no content and no tool calls (`finish_reason=stop`) after long tool results, and once it called a misspelled tool name (`pennalty_by_lender`) before correcting itself. A retry with a short nudge fixed the empty reply every time.
- **Formatting.** Super sometimes writes thousands with a narrow no-break space ("$710 000"). Anyone parsing model output for numbers should normalise that.
- **Nemotron 3 Nano JSON mode** (`response_format`) was honoured and fast. It extracted 15 fields from a client email, but sometimes paraphrases when asked to quote the source text, so quote-grounded extraction drops a few fields.
- **`chat_template_kwargs.enable_thinking`** was accepted on all three models. I ran with thinking off for latency.
- **Nemotron 3 Ultra** wrote all five decision memos well: structured, cited each app, and after a verifier fix on my side every figure in all five traced to a calculator. Once it computed a new figure itself despite the instruction not to, which the verifier caught.
- **Latency and cost.** The 17-case eval cost about $0.18 (55 calls, 581k prompt tokens, almost all of it tool schemas and tool results). Median latency per question was 6.3 s, 14.0 s, 4.1 s and 6.5 s in four runs the same day, so I'd welcome published latency targets per model.
- **Serverless.** The endpoint and job scripts are in `deploy/nebius/`; I did not deploy them during the submission period, so I have no feedback on them yet.
- **Tavily.** The Nebius Builder credit was applied without a card. Search with an official-domain allow-list returned current Bank of Canada and OSFI pages on the first try. Extract on two big-bank rate pages worked, but those pages mix posted, special and other-term rates, so turning "the page" into "the posted 5-year rate" still needs the label matching I wrote; a structured-table option in Extract would help.
