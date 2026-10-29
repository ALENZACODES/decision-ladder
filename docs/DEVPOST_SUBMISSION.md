# Devpost submission text (Nebius × NVIDIA Global AI Hackathon)

**Project name:** Decision Ladder: Mortgage OS
**Tagline:** Every stage of a Canadian mortgage, one system. Nemotron reasons; calculators decide.
**Track:** Best Apps and Agents
**Built with:** NVIDIA Nemotron 3 Nano, Super and Ultra; Nebius Token Factory; Nebius Serverless AI (endpoints and jobs); Tavily (Search and Extract); Python; Node.js; vanilla JS
**Repo:** https://github.com/ALENZACODES/decision-ladder
**Demo:** (your deployed URL)
**Video:** (your YouTube URL)

---

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

**Overnight,** a Nebius Serverless job scans the whole renewal book and ranks who to call, with lender-exact penalties and outreach drafts that pass a compliance guardrail.

## How we built it

- **14 of my projects run as modules: 76,319 lines of their own code.** Each app runs its own screen inside the OS. The JavaScript apps' calculators run through a small Node bridge that loads each app's real `calc.js`, so the agent, the ladder and the app's screen always agree. Renewal Radar's Python engines are imported in-process, and its FastAPI app is proxied.
- **A 17-rung ladder covers the lifecycle:** lead, documents, pre-qualification, underwriting, property, closing, market, servicing, commercial, compliance, decision. Each rung is computed by one of the apps and returns PASS, REFER, FAIL or SKIP.
- **Three Nemotron tiers on Token Factory, as the brief recommends:**
  - **Nano** routes each question to the right lifecycle stages; Super then sees about 8 to 15 of the 52 tools instead of all of them. Nano also does the JSON extraction and drafts.
  - **Super** runs the tool calls.
  - **Ultra** writes the credit decision, falling back to Super if Ultra isn't available.
- **A standard-library Token Factory client.** It handles tool calling, JSON mode with a fallback, retries, `<think>` stripping, recovery of inline tool calls (Qwen3-Coder XML and `<TOOLCALL>` formats), model auto-resolution against `/v1/models`, and token and cost accounting.
- **Tavily.**
  - Search runs on official Canadian domains only (Bank of Canada, OSFI, FSRA, CMHC, Canada.ca), and every source is cited.
  - Extract reads each Big-6 bank's own rate page and confirms whether the rate book's posted 5-year rate is still current.
- **Nebius Serverless AI.** The OS deploys as a CPU endpoint (a GitHub Action publishes the image), and the renewal-book scan runs as a job billed only while it runs.
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

- **Keeping the model away from arithmetic, with 50+ tools across 14 apps.** Nano routing kept tool choice focused, and the provenance verifier, with one repair turn, kept the answers honest.
- **Making 14 separately built apps agree.** Aligning their inputs for the cross-checks was most of the work. It turned up one real bug and one real method difference.
- **Grounding extraction.** A value from an email or a pay stub is kept only if its quoted words appear in the source.

## Accomplishments that we're proud of

- A single client journey that runs through 14 real apps, with every number traceable to the app that computed it, and each app opens with the client's own numbers.
- A path to yes that can't contradict the decline: for the stress test and for cash to close.
- Every overlapping calculation in my apps agrees, and the OS proves it on every file.

## What we learned

Nemotron is very good at the parts of mortgage work that are language: reading, routing, planning and explaining. Its value multiplies when its tools are trusted. The three tiers matter in practice: Nano for the many cheap calls, Super for tool use, Ultra for the one decision that has to be right.

## What's next for Decision Ladder

- A licensed screening provider and live lender policy feeds.
- OCR in front of document reading.
- A dedicated Nemotron endpoint for book-scale overnight runs.
- A pilot in my brokerage.

---

## What was significantly updated during the submission period

The submission period ran from Aug 26 to Oct 30, 2026. All 14 module projects are my own, created in October 2026.

The Mortgage OS itself was built for this hackathon:
- the module system and embedded apps
- the staged ladder
- the cross-checks
- the three-tier Nemotron design
- the Token Factory client
- the verifier
- grounded intake and document reading
- Tavily Search and Extract
- the Serverless job and endpoint
- the UI, evals and CI

## Feedback on Nebius and NVIDIA tools (fill in from your own experience; specific beats generic)

- Getting a key and first call: how long did it take, and was anything unclear?
- `/v1/models`: were Nemotron Nano, Super and Ultra all listed, and were the IDs easy to find?
- Tool calling with Nemotron 3 Super across 50+ tools: how reliable were tool choice and argument JSON (see `eval_report.json`)?
- JSON mode with Nemotron 3 Nano: was `response_format` honoured? Did `chat_template_kwargs.enable_thinking` work?
- Nemotron 3 Ultra: latency and quality on the decision memo.
- Serverless endpoint and job setup: CLI experience, cold start, logs.
- Latency and cost per ladder run (`smoke_report.json`).
