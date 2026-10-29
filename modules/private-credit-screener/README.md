![Private Credit Deal Screener banner](docs/banner.png)

# Private Credit Deal Screener

**Scores a private credit deal on coverage, leverage and collateral, tests which assumptions move the grade, and drafts a short credit memo.**

[![Live demo](https://img.shields.io/badge/live_demo-open-011F5B?style=flat-square)](https://alenzacodes.github.io/private-credit-screener/) [![Licence: MIT](https://img.shields.io/badge/licence-MIT-990000?style=flat-square)](LICENSE) ![Built with JavaScript](https://img.shields.io/badge/built_with-JavaScript-4a4a4a?style=flat-square) [![tests](https://github.com/ALENZACODES/private-credit-screener/actions/workflows/tests.yml/badge.svg)](https://github.com/ALENZACODES/private-credit-screener/actions/workflows/tests.yml)

**Live:** https://alenzacodes.github.io/private-credit-screener/

![Screener with the stabilized example deal loaded](docs/screenshot-desktop.png)

A first pass on a senior real estate loan, the kind of check you'd do before spending a day on a full credit memo. Put in the loan, the property value and the income, and it gives the deal a letter grade, shows which inputs the grade is most sensitive to, and drafts a one-page investment committee memo you can export.

## How the grade works

| Metric | Formula | Weight |
|---|---|---|
| LTV | loan / appraised value | 25% |
| DSCR | NOI / annual debt service | 25% |
| Exit LTV | balloon balance / exit value, where exit value = NOI grown over the term / (going-in cap rate + exit cap shift) | 25% |
| Debt yield | NOI / loan | 15% |
| Sponsor | your 1 to 5 rating | 10% |

The sensitivity chart moves each input up and down and shows how far the score swings, so you can see straight away whether a deal hangs on NOI, the rate or the appraisal.

The thresholds are my own screening framework, not an industry standard. Lenders set their own.

## Quick start

Open `index.html` in a browser, or serve the folder with `python3 -m http.server 8000` and open http://localhost:8000/. No install. Example deals are in the dropdown at the top.

## Tests

    node tests/test.js

18 checks on debt service (amortizing and interest-only), the metrics, the scoring and the sensitivity ranges. They run on every push.

## Data and sources

There's no outside data feed. Every deal in the app is a made-up example built to show the method, and the formulas are standard commercial real estate lending definitions (LTV, DSCR, debt yield, cap rate valuation). Don't enter real borrower information.

On a phone:

<img src="docs/screenshot-mobile.png" alt="Mobile layout" width="300">

Educational only, not financial advice.

## Files

    index.html, style.css   the page
    app.js                  inputs, grade, sensitivity chart and memo
    calc.js                 debt service, metrics, scoring and sensitivity, usable in Node
    charts.js               small SVG charts, no libraries
    tests/test.js           unit tests

## Licence

MIT. Copyright 2026 John Khan.

---

More of my work is on my [GitHub profile](https://github.com/ALENZACODES).
