"""The author's JavaScript apps as Mortgage OS modules.

Nine browser apps (vendored under ``modules/``) are served inside the OS at ``/apps/<key>/`` and their
calculator code is exposed to Nemotron as tools. Tools run the apps' *own* JavaScript through
``bridge.mjs`` (Node), so the agent, the OS and each app's screen always give the same number.
If Node is not installed the tools return an explicit error; the apps' screens still work.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..agent.tools import Tool, _obj
from .registry import AppModule, add_module, add_tool

BRIDGE = Path(__file__).resolve().parent / "bridge.mjs"
TIMEOUT_S = 10

N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}
S = {"type": "string"}


def node_path() -> str | None:
    return shutil.which("node") or shutil.which("nodejs")


def call(module: str, fn: str, args: dict) -> dict:
    """Run one bridged function. Always returns a dict (errors as {"error": ...})."""
    node = node_path()
    if not node:
        return {"error": "node not installed: these tools run the app's own JavaScript; install Node.js 18+"}
    try:
        p = subprocess.run([node, str(BRIDGE), module, fn, json.dumps(args)], capture_output=True, text=True,
                           timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"error": f"{module}.{fn} timed out after {TIMEOUT_S}s"}
    try:
        out = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": f"bridge returned non-JSON (exit {p.returncode}): {(p.stderr or p.stdout)[:300]}"}
    if not out.get("ok"):
        return {"error": out.get("error") or f"bridge failed: {(p.stderr or '')[:300]}"}
    res = out["result"]
    if isinstance(res, dict):
        res.setdefault("engine", f"{module} ({fn})")
    return res


def _tool(name: str, desc: str, props: dict, required: list[str], module: str, fn: str, rung: str,
          transform=None) -> Tool:
    def run(a: dict) -> dict:
        args = transform(a) if transform else a
        return call(module, fn, args)
    return Tool(name, desc, _obj(props, required), run, rung)


# ------------------------------------------------------------------------------------- modules
APPS = [
    AppModule(key="canadian-mortgage-suite", name="Canadian Mortgage Calculator Suite", stages=["prequal", "closing", "servicing"],
              description="Fourteen Canadian mortgage and home-buying calculators on 2026 OSFI, CMHC and land transfer tax rules "
                          "(all provinces), with cited sources: payment, affordability, CMHC, LTT, closing costs, penalty, renewal, "
                          "refinance, rent vs buy, FHSA/HBP.",
              directory="canadian-mortgage-suite", repo="ALENZACODES/canadian-mortgage-suite",
              live_url="https://alenzacodes.github.io/canadian-mortgage-suite/"),
    AppModule(key="cash-to-close", name="Cash to Close", stages=["closing"],
              description="Ontario cash-to-close planner: down payment plus land transfer tax (twice in Toronto), PST on mortgage "
                          "insurance, lawyer, title insurance, adjustments and moving, against the buyer's savings.",
              directory="cash-to-close", repo="ALENZACODES/cash-to-close", live_url="https://alenzacodes.github.io/cash-to-close/"),
    AppModule(key="mortgage-decision-lab", name="Mortgage Decision Lab", stages=["prequal", "servicing"],
              description="Six calculators on one page: payment and debt service, down payment, rate sensitivity, renewal, "
                          "rent vs buy and prepayment, plus a Canada vs US compounding comparison.",
              directory="mortgage-decision-lab", repo="ALENZACODES/mortgage-decision-lab",
              live_url="https://alenzacodes.github.io/mortgage-decision-lab/"),
    AppModule(key="pre-underwriting-copilot", name="Loan File Pre-Underwriting Check", stages=["underwriting", "documents"],
              description="Reads a plain-text loan file and checks it before lender submission: LTV, GDS/TDS at the qualifying rate, "
                          "minimum down payment, missing or stale documents, name mismatches, and a readiness score with a broker memo.",
              directory="pre-underwriting-copilot", repo="ALENZACODES/pre-underwriting-copilot",
              live_url="https://alenzacodes.github.io/pre-underwriting-copilot/"),
    AppModule(key="private-credit-screener", name="Private Credit Deal Screener", stages=["commercial"],
              description="Scores a senior real estate loan on LTV, DSCR, debt yield, exit LTV and sponsor; letter grade, "
                          "sensitivity (tornado) of the grade to each assumption, and credit-memo inputs.",
              directory="private-credit-screener", repo="ALENZACODES/private-credit-screener",
              live_url="https://alenzacodes.github.io/private-credit-screener/"),
    AppModule(key="renewal-check", name="Renewal Check", stages=["servicing"],
              description="New payment at renewal from four statement numbers and the offered rate, what happens if the client "
                          "keeps paying the old amount, nearby-rate scenarios, and a prepayment penalty estimate.",
              directory="renewal-check", repo="ALENZACODES/renewal-check", live_url="https://alenzacodes.github.io/renewal-check/"),
    AppModule(key="renewal-shock-radar", name="Renewal Shock Radar", stages=["servicing", "market"],
              description="How much a Canadian mortgage payment can rise at renewal, using Bank of Canada and CMHC figures, with a "
                          "shock band, share of income and the amortization needed to keep the old payment.",
              directory="renewal-shock-radar", repo="ALENZACODES/renewal-shock-radar",
              live_url="https://alenzacodes.github.io/renewal-shock-radar/"),
    AppModule(key="canada-rate-cycle-dashboard", name="Canada's Rate Cycle 2015-2026", stages=["market"],
              description="Interactive dashboard of the Bank of Canada policy rate, CPI inflation, the 5-year conventional mortgage "
                          "rate and USD/CAD, monthly 2015 to 2026 (Bank of Canada Valet).",
              directory="canada-rate-cycle-dashboard", repo="ALENZACODES/canada-rate-cycle-dashboard",
              live_url="https://alenzacodes.github.io/canada-rate-cycle-dashboard/"),
    AppModule(key="doc-quest", name="Doc Quest", stages=["documents", "lead"],
              description="Plain-language mortgage document checklist for first-time and newcomer buyers, ordered so slow items "
                          "(things you must ask someone for) come first, three steps at a time.",
              directory="doc-quest", repo="ALENZACODES/doc-quest", live_url="https://alenzacodes.github.io/doc-quest/"),
]
for _m in APPS:
    add_module(_m)


# ------------------------------------------------------------------------------------- tools
def _cms_ltt(a: dict) -> dict:
    a = dict(a)
    a["province"] = str(a.get("province", "ON")).upper()
    for k in ("first_time", "new_build"):
        if k in a:
            a["firstTime" if k == "first_time" else "newBuild"] = a.pop(k)
    return a


def _cms_afford(a: dict) -> dict:
    m = {"annual_income": "income", "contract_rate": "rate", "down_payment": "down", "amort_years": "years",
         "property_tax_annual": "propertyTax", "heat_monthly": "heat", "condo_fees_monthly": "condoFees",
         "other_debt_monthly": "debts", "first_time": "firstTime", "new_build": "newBuild"}
    out = {m.get(k, k): v for k, v in a.items()}
    out["province"] = str(out.get("province", "ON")).upper()
    return out


TOOLS = [
    (_tool("cash_to_close_ontario",
           "Cash a buyer needs on closing day in Ontario (Cash to Close app): down payment (minimum if not given), Ontario land "
           "transfer tax with first-time refund, Toronto municipal LTT with rebate when toronto=true, 8% PST on CMHC premium, "
           "deposit, lawyer, title insurance, inspection, adjustments and moving. Returns cashToClose, extras over the down "
           "payment, gap vs savings (negative = short), and each line item.",
           {"price": N, "savings": N, "down": {"type": "number", "description": "down payment; omit for the legal minimum"},
            "toronto": B, "first_time": B, "amort30": B, "deposit": N, "inspection": N, "legal": N, "title": N,
            "adjustments": N, "moving": N}, ["price", "savings"], "cash-to-close", "plan", "closing"), "cash-to-close"),
    (_tool("land_transfer_tax",
           "Land transfer tax / land titles fees for any province or territory (Canadian Mortgage Suite): provincial, municipal "
           "(Toronto MLTT when toronto=true, Montreal when montreal=true), first-time-buyer and new-build rebates, net total. "
           "province is a two-letter code (ON, BC, QC, AB, MB, SK, NS, NB, PE, NL, YT, NT, NU).",
           {"price": N, "province": S, "toronto": B, "montreal": B, "first_time": B, "new_build": B,
            "loan": {"type": "number", "description": "mortgage amount (Alberta registration fee)"}},
           ["price", "province"], "canadian-mortgage-suite", "landTransferTax", "closing", _cms_ltt), "canadian-mortgage-suite"),
    (_tool("closing_costs_estimate",
           "All closing costs for a purchase (Canadian Mortgage Suite): net land transfer tax plus legal, inspection, appraisal, "
           "title insurance, adjustments, moving, PST on mortgage insurance, and GST/levies for new builds. Defaults are typical "
           "amounts; override any.",
           {"price": N, "province": S, "toronto": B, "first_time": B, "new_build": B, "insurancePst": N, "legal": N,
            "inspection": N, "appraisal": N, "title": N, "adjustments": N, "moving": N, "gstNet": N, "levies": N},
           ["price", "province"], "canadian-mortgage-suite", "closingCosts", "closing", _cms_ltt), "canadian-mortgage-suite"),
    (_tool("affordability_by_income",
           "Highest purchase price a household qualifies for at the B-20 qualifying rate (Canadian Mortgage Suite), including the "
           "CMHC premium when under 20% down and the insured-mortgage rules. Returns maxPrice, limiting ratio (GDS or TDS), max "
           "payment, loan and contract payment. heat_monthly is dollars per month.",
           {"annual_income": N, "contract_rate": N, "down_payment": N, "amort_years": I, "property_tax_annual": N,
            "heat_monthly": N, "condo_fees_monthly": N, "other_debt_monthly": N, "province": S, "first_time": B, "new_build": B},
           ["annual_income", "contract_rate", "down_payment"], "canadian-mortgage-suite", "affordability", "prequal",
           _cms_afford), "canadian-mortgage-suite"),
    (_tool("refinance_cash_out",
           "Refinance / equity take-out (Canadian Mortgage Suite): maximum loan at 80% of value, cash out after penalty and fees, "
           "new vs old payment, monthly saving including consolidated debt payments, and break-even months.",
           {"homeValue": N, "balance": N, "newLoan": N, "currentRate": N, "newRate": N, "remainingYears": N, "years": N,
            "penalty": N, "fees": N, "consolidatedPayments": N},
           ["homeValue", "balance", "newLoan", "currentRate", "newRate", "remainingYears", "years"],
           "canadian-mortgage-suite", "refinance", "servicing"), "canadian-mortgage-suite"),
    (_tool("down_payment_savings_plan",
           "First-home down payment plan (Canadian Mortgage Suite): FHSA contributions with growth and tax saved, RRSP Home Buyers' "
           "Plan withdrawal (cap applied), cash, for one buyer or a couple.",
           {"years": I, "fhsaAnnual": N, "returnPct": N, "marginalRate": N, "rrsp": N, "couple": B, "cash": N},
           ["years", "fhsaAnnual"], "canadian-mortgage-suite", "downPaymentPlan", "prequal"), "canadian-mortgage-suite"),
    (_tool("rent_vs_buy",
           "Rent vs buy net worth year by year (Mortgage Decision Lab). Rates in percent; taxPct and maintPct are percent of home "
           "value per year; closingPct and sellPct percent of price. Returns per-year buy vs rent net worth, the final year, "
           "the winner and the gap.",
           {"price": N, "down": N, "rate": N, "amort": I, "years": I, "rent": N, "rentGrowth": N, "appreciation": N,
            "investReturn": N, "taxPct": N, "maintPct": N, "closingPct": N, "sellPct": N},
           ["price", "down", "rate", "amort", "years", "rent", "rentGrowth", "appreciation", "investReturn", "taxPct",
            "maintPct", "closingPct", "sellPct"], "mortgage-decision-lab", "rentVsBuy", "prequal"), "mortgage-decision-lab"),
    (_tool("prepayment_savings",
           "Interest and months saved by prepaying (Mortgage Decision Lab): extra is added to every monthly payment, lump is an "
           "annual lump sum. Canadian semi-annual compounding.",
           {"balance": N, "rate": N, "amort": I, "extra": N, "lump": N}, ["balance", "rate", "amort", "extra", "lump"],
           "mortgage-decision-lab", "prepay", "servicing"), "mortgage-decision-lab"),
    (_tool("pre_underwrite_loan_file",
           "Pre-underwriting review of a plain-text loan file (Loan File Pre-Underwriting Check). The text uses 'Field: value' lines "
           "(Borrower, Province, Application date, Employment, Annual income, Credit score, Purchase price, Down payment, Gift, "
           "Contract rate, Amortization, Property tax, Heating, Condo fees, Monthly debts) and a 'Documents:' list of "
           "'- type | YYYY-MM-DD | name' lines. Fictional files must contain [EXAMPLE]. Or pass sample='clean'|'messy'. Returns "
           "status, readiness score, ratios, flags (high/medium/low), document checks and a broker memo.",
           {"text": S, "sample": {"type": "string", "enum": ["clean", "messy"]}}, [], "pre-underwriting-copilot", "review",
           "underwriting"), "pre-underwriting-copilot"),
    (_tool("private_credit_deal_screen",
           "Screen a private / commercial senior real estate loan (Private Credit Deal Screener): LTV, debt service, DSCR, debt "
           "yield, balloon, exit value and exit LTV, all-in yield, 0-100 score, letter grade A-D and which assumptions move the "
           "grade most. Rates in percent; amort 0 = interest-only; capRate defaults to NOI/value; sponsorScore 1-5.",
           {"loan": N, "value": N, "noi": N, "rate": N, "amort": N, "termYrs": N, "capRate": N, "exitCapShift": N,
            "noiGrowth": N, "fees": N, "sponsorScore": N}, ["loan", "value", "noi", "rate"],
           "private-credit-screener", "screen", "commercial"), "private-credit-screener"),
    (_tool("renewal_offer_check",
           "Renewal Check: from the balance, years left on the amortization, current rate and offered renewal rate, the new "
           "payment and monthly change, how long the mortgage takes if the client keeps paying the old payment (or whether it no "
           "longer covers interest), and payments at nearby rates (-0.5, +1, +2 points).",
           {"balance": N, "years": N, "currentRate": N, "offerRate": N}, ["balance", "years", "currentRate", "offerRate"],
           "renewal-check", "check", "renewal"), "renewal-check"),
    (_tool("renewal_shock_band",
           "Renewal Shock Radar: payment rise at renewal for a loan taken out earlier (loan, original rate, amortization years, "
           "term years elapsed, new rate), balance at renewal, share of income before and after, shock band (low/moderate/high/"
           "severe), years of amortization needed to keep the old payment, and a rate curve around the new rate.",
           {"loan": N, "origRate": N, "amort": N, "term": N, "newRate": N, "income": N,
            "curveRates": {"type": "array", "items": N}}, ["loan", "origRate", "amort", "term", "newRate"],
           "renewal-shock-radar", "shock", "renewal"), "renewal-shock-radar"),
    (_tool("buyer_document_checklist",
           "Doc Quest: the mortgage document checklist for a buyer profile, slow items first, with plain-language explanations "
           "and where to get each. work: salaried|hourly|commission|self; sources: any of savings, fhsa, rrsp, gift; newcomer, "
           "ownOther (owns another property), partner. done: ids already collected. Returns documents, next_up and progress.",
           {"work": {"type": "string", "enum": ["salaried", "hourly", "commission", "self"]},
            "sources": {"type": "array", "items": {"type": "string", "enum": ["savings", "fhsa", "rrsp", "gift"]}},
            "newcomer": B, "ownOther": B, "partner": B, "done": {"type": "array", "items": S}, "n": I}, [],
           "doc-quest", "checklist", "documents"), "doc-quest"),
    (_tool("rate_cycle_history",
           "Canada's rate cycle 2015-2026 (Bank of Canada Valet, monthly): for a window from/to (YYYY-MM), the start, end, max and "
           "min of the policy rate, CPI inflation, 5-year conventional mortgage rate and USD/CAD, with the month of each extreme. "
           "rows=true also returns the monthly rows.",
           {"from": S, "to": S, "rows": B}, [], "canada-rate-cycle-dashboard", "series", "market"), "canada-rate-cycle-dashboard"),
]
for _t, _key in TOOLS:
    add_tool(_t, _key)
