# Devpost submission text (Nebius × NVIDIA Global AI Hackathon)

**Project name:** Decision Ladder
**Tagline:** Canadian mortgage decisions, top down. Nemotron reasons; calculators decide.
**Track:** Best Apps and Agents
**Built with:** NVIDIA Nemotron 3 Super, NVIDIA Nemotron 3 Nano, Nebius Token Factory, Tavily, Python (standard library), vanilla JS
**Repo:** https://github.com/ALENZACODES/decision-ladder
**Demo:** (add your deployed URL)
**Video:** (add your YouTube URL)

---

## Inspiration

I'm a licensed mortgage broker in Ontario, and I'm also a data scientist. The Bank of Canada says the last of the five-year fixed mortgages taken out during the pandemic renew over the next 12 months. That group is about 12% of all mortgages, and on average their payments rise about 15%. Every one of those files gets the same treatment: someone re-keys the client's email, runs a stress test in one tool and a penalty in another, checks rates on a bank website, and writes a note. When the answer is "no", nobody has time to work out what would turn it into "yes".

General-purpose chatbots are fluent here, but they invent numbers. In mortgages, one made-up penalty or stressed payment can cost a client thousands of dollars or a broker their licence. So I built a system where the model does what language models are good at (reading, planning, choosing tools, explaining) and never does the arithmetic.

## What it does

A mortgage file climbs **eleven rungs**: intake, screening, documents, collateral, insurance, B-20 qualification, lender fit, market, exit cost, compliance and decision. Each rung returns PASS, REFER, FAIL or SKIP from tested, deterministic engines. The verdict is GO, GO WITH CONDITIONS, RESTRUCTURE or DECLINE AS STRUCTURED.

When the stress test fails, the ladder works out a **path to yes**: the highest price that passes, the smallest down payment that passes, the debt payoff needed, the income or co-borrower needed, and whether a 30-year amortization helps. Each option is re-run through the same stress test that failed the file.

**NVIDIA Nemotron on Nebius Token Factory** does the language and agent work:

- **Nemotron 3 Super** is the broker copilot. It plans multi-step tool calls across 19 mortgage tools plus Tavily web research, and it writes the broker's decision memo.
- **Nemotron 3 Nano** turns a client's email into a structured file in JSON mode. Every value has to quote the exact sentence it came from, or it's dropped. Nano also drafts client messages (file status, renewal outreach).

**Tavily** searches only official Canadian sources (Bank of Canada, OSFI, FSRA, CMHC, Canada.ca) for anything newer than the rate book, and every source is cited.

A **provenance verifier** checks every number in the model's text against the tool results. Any number with no source gets one repair round, and if it still can't be traced it is marked **[unverified]** on screen. An **outbound guardrail** blocks rate quotes, approval promises, pressure language and requests for a client's SIN, passwords or card numbers.

The **Renewal Book** tab scans a broker's whole book from a CSV. It ranks clients by urgency, payment shock and balance, shows today's penalty under each lender's own method, and drafts guardrailed outreach for the top clients.

## How we built it

- One client module talks to Token Factory's OpenAI-compatible API using only the Python standard library. It handles tool calling, JSON mode with a fallback, stripping `<think>` blocks, retries with backoff, and per-model token and cost accounting.
- The deterministic engines include the B-20 stress test, the default-insurance premium schedule, Dec 2024 insured rules, Canadian semi-annual compounding, renewal shock, the Nov 2024 OSFI straight-switch rule, and a Decimal penalty engine with lender-specific IRD methods. The penalty engine reports how far the comparison-term rule alone moves the penalty.
- A rate book of more than 13,900 dated observations: Bank of Canada Valet series plus each Big-6 bank's own captured posted and special rates. Every figure carries its date and source.
- A web app, a CLI, an eval harness, a live smoke test, Docker and Render deployment, and over 230 tests that run without any network or keys.
- Built on my own earlier October 2026 projects (Renewal Radar and MortgageLoanOps). The README says exactly what was reused and what is new.

## Challenges we ran into

- **Stopping the model from doing arithmetic.** Asking nicely wasn't enough. The fix was structural: tools for every number, a verifier that matches figures with display rounding ($3,343 for 3,343.27, $25.1K for 25,110), and a repair turn.
- **Grounding extraction.** Model extraction is fluent but can paraphrase into numbers that aren't in the email. Requiring an exact supporting quote, and comparing against a deterministic pattern extractor, turned silent errors into visible flags.
- **Penalties.** Lenders compute the interest rate differential differently. The term-rule sensitivity shows when a "penalty" is really a range.

## Accomplishments that we're proud of

- A path to yes that can never contradict the decline, because each option is re-run through the same stress test.
- Every figure the model writes is either traced to a calculation or visibly flagged.
- Zero dependencies: it runs anywhere Python 3.10+ runs, and offline mode needs no keys for review.

## What we learned

The system works best when the model handles intent and language and the code handles numbers. Nemotron is good at choosing the right tool and turning eleven rung results into a memo a broker can act on. The deterministic layer is what makes it safe to put in front of a client.

## What's next for Decision Ladder

Connecting a licensed screening provider and lender policy feeds; OCR for renewal letters and pay stubs, using Renewal Radar's document pipeline; a dedicated Nemotron endpoint for book-scale overnight runs; and a pilot with my brokerage.

---

## Feedback on Nebius and NVIDIA tools (fill in from your own experience; specific beats generic)

- Getting a key and first call: how long did it take? Anything unclear?
- Model catalogue: were the Nemotron IDs easy to find? Did `/v1/models` list them?
- Tool calling with Nemotron 3 Super: how reliable were the tool choices and argument JSON across the eval cases (`eval_report.json`)?
- JSON mode with Nemotron 3 Nano: was `response_format` honoured?
- Latency and cost per ladder run (from `smoke_report.json`).
- What you'd want next (e.g. per-key usage dashboards, a structured-output guarantee).
