"""The author's JavaScript apps as OS modules: every tool runs the app's own code through the Node bridge.

Expected values come from each repo's own test suite or README (cited per test), not from new math.
"""
import json
import subprocess

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.modules import MODULES, load_all
from decision_ladder.modules import jsapps

load_all()
NODE = jsapps.node_path()
needs_node = pytest.mark.skipif(NODE is None, reason="node not installed")

JS_MODULES = ["canadian-mortgage-suite", "cash-to-close", "mortgage-decision-lab", "pre-underwriting-copilot",
              "private-credit-screener", "renewal-check", "renewal-shock-radar", "canada-rate-cycle-dashboard", "doc-quest"]


def run(name, args):
    out = T.run(name, args)
    assert "error" not in out, out
    return out


def near(a, b, tol=0.01):
    assert abs(a - b) <= tol, f"{a} vs {b}"


# ------------------------------------------------------------------ registry
@pytest.mark.parametrize("key", JS_MODULES)
def test_module_registered_with_ui_and_tools(key):
    m = MODULES[key]
    assert m.kind == "static" and (m.path / m.entry).is_file()
    assert m.tools and all(t in T.TOOLS for t in m.tools)
    assert m.live_url.startswith("https://alenzacodes.github.io/") and m.lines_of_code > 100


def test_tool_names_unique_and_specs_valid():
    for m in JS_MODULES:
        for t in MODULES[m].tools:
            fn = T.TOOLS[t].spec()["function"]
            for r in fn["parameters"]["required"]:
                assert r in fn["parameters"]["properties"]


def test_missing_node_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(jsapps, "node_path", lambda: None)
    assert "node not installed" in T.run("land_transfer_tax", {"price": 1, "province": "ON"})["error"]


@needs_node
def test_bridge_lists_functions_and_reports_unknown():
    out = json.loads(subprocess.run([NODE, str(jsapps.BRIDGE), "--list"], capture_output=True, text=True).stdout)
    assert "cash-to-close.plan" in out
    assert "unknown function" in jsapps.call("cash-to-close", "nope", {})["error"]


# ------------------------------------------------------------------ cash-to-close
@needs_node
def test_cash_to_close_readme_example():
    # README screenshot: "$700,000 price and $60,000 saved: $64,971 due on closing" (Toronto, first-time, app defaults)
    r = run("cash_to_close_ontario", {"price": 700000, "savings": 60000, "toronto": True, "first_time": True})
    near(r["cashToClose"], 64971)
    near(r["premium"], 26200)
    near(r["pst"], 2096)
    near(r["gap"], -4971)
    assert r["engine"].startswith("cash-to-close")


@needs_node
def test_cash_to_close_twenty_percent_down_has_no_premium():
    # repo test.js: 20% down -> no premium, no PST, no Toronto tax outside Toronto
    r = run("cash_to_close_ontario", {"price": 700000, "savings": 200000, "down": 140000, "deposit": 35000})
    assert r["premium"] == 0 and r["pst"] == 0 and r["mlttGross"] == 0


# ------------------------------------------------------------------ canadian-mortgage-suite
@needs_node
@pytest.mark.parametrize("args,total", [
    ({"province": "ON", "price": 500000}, 6475),                                         # ontario.ca example
    ({"province": "ON", "price": 400000, "toronto": True, "first_time": True}, 475),     # MLTT fully rebated
    ({"province": "BC", "price": 500000}, 8000),
    ({"province": "on", "price": 2500000}, 36475 + 12500),
])
def test_land_transfer_tax_repo_examples(args, total):
    near(run("land_transfer_tax", args)["total"], total)


@needs_node
def test_closing_costs_repo_example():
    r = run("closing_costs_estimate", {"province": "ON", "price": 500000, "insurancePst": 1000})
    near(r["total"], 6475 + 2000 + 500 + 350 + 350 + 1000 + 1500 + 1000)


@needs_node
def test_affordability_repo_example():
    r = run("affordability_by_income", {"annual_income": 120000, "contract_rate": 4.5, "down_payment": 100000,
                                        "amort_years": 25, "property_tax_annual": 4000, "heat_monthly": 100})
    assert 500000 < r["maxPrice"] < 700000 and r["qualifyingRate"] == 6.5
    r2 = run("affordability_by_income", {"annual_income": 120000, "contract_rate": 4.5, "down_payment": 100000,
                                         "amort_years": 25, "other_debt_monthly": 2000})
    assert r2["limiting"] == "TDS"


@needs_node
def test_refinance_and_down_payment_plan_repo_examples():
    r = run("refinance_cash_out", {"homeValue": 1000000, "balance": 500000, "newLoan": 900000, "currentRate": 5,
                                   "newRate": 4, "remainingYears": 20, "years": 25, "penalty": 5000, "fees": 1000})
    near(r["maxLoan"], 800000)
    near(r["cashOut"], 294000)
    p = run("down_payment_savings_plan", {"years": 5, "fhsaAnnual": 8000, "returnPct": 0, "rrsp": 60000, "couple": True, "cash": 0})
    near(p["total"], 200000)


# ------------------------------------------------------------------ mortgage-decision-lab
@needs_node
def test_prepayment_repo_examples():
    near(run("prepayment_savings", {"balance": 400000, "rate": 5, "amort": 25, "extra": 0, "lump": 0})["interestSaved"], 0, 1)
    r = run("prepayment_savings", {"balance": 400000, "rate": 5, "amort": 25, "extra": 300, "lump": 0})
    assert r["monthsSaved"] > 0 and r["interestSaved"] > 0


@needs_node
def test_rent_vs_buy_one_row_per_year():
    r = run("rent_vs_buy", {"price": 700000, "down": 140000, "rate": 4.5, "amort": 25, "years": 10, "rent": 2800,
                            "rentGrowth": 3, "appreciation": 3, "investReturn": 5, "taxPct": 0.7, "maintPct": 1,
                            "closingPct": 1.5, "sellPct": 5})
    assert len(r["years"]) == 10 and r["winner"] in ("Buy", "Rent")
    near(r["gap"], r["final"]["buyNW"] - r["final"]["rentNW"], 1e-6)


# ------------------------------------------------------------------ pre-underwriting-copilot
@needs_node
def test_pre_underwriting_samples_match_repo_tests():
    a = run("pre_underwrite_loan_file", {"sample": "clean"})
    assert a["status"] == "Ready for lender review"
    near(a["ratios"]["loan"], 551000, 1e-9)
    assert not a["ratios"]["insured"] and "GDS" in a["memo"]
    b = run("pre_underwrite_loan_file", {"sample": "messy"})
    assert b["status"] == "Not ready" and b["flags"][0]["level"] == "high"
    near(b["ratios"]["minDown"], 25000 + 220000 * 0.1, 1e-9)
    msgs = " ".join(f["msg"] for f in b["flags"])
    for needle in ("below the federal minimum", "does not match", "ID expired", "gift letter", "business financials"):
        assert needle in msgs


@needs_node
def test_pre_underwriting_free_text_and_missing_input():
    r = run("pre_underwrite_loan_file", {"text": "Borrower: X"})
    assert any("not marked" in f["msg"] for f in r["flags"])
    assert "required" in T.run("pre_underwrite_loan_file", {})["error"]


# ------------------------------------------------------------------ private-credit-screener
@needs_node
def test_private_credit_repo_example():
    d = {"loan": 6e6, "value": 10e6, "noi": 700000, "rate": 10, "amort": 0, "termYrs": 2, "capRate": 7,
         "exitCapShift": 0, "noiGrowth": 0, "fees": 2, "sponsorScore": 4}
    r = run("private_credit_deal_screen", d)
    m = r["metrics"]
    near(m["ltv"], 60, 1e-6)
    near(m["ds"], 600000, 1e-6)
    near(m["dscr"], 700000 / 600000, 1e-6)
    near(m["exitLtv"], 60, 1e-6)
    near(m["allInYield"], 11, 1e-6)
    assert r["grade"] in "ABCD" and len(r["sensitivity"]) == 7
    worse = run("private_credit_deal_screen", {**d, "loan": 8.5e6})
    assert worse["total"] < r["total"]


# ------------------------------------------------------------------ renewal-check / renewal-shock-radar
@needs_node
def test_renewal_check_repo_example():
    r = run("renewal_offer_check", {"balance": 400000, "years": 20, "currentRate": 2.29, "offerRate": 4.49})
    assert r["change"] > 0 and r["keep"]["covers"] and r["keep"]["extraMonths"] > 0 and len(r["scenarios"]) == 4
    assert r["posted_as_of"] and r["posted_latest"]
    bad = run("renewal_offer_check", {"balance": 0, "years": 50, "currentRate": -1, "offerRate": 30})
    assert set(bad["errors"]) >= {"balance", "years"}


@needs_node
def test_renewal_shock_repo_examples():
    same = run("renewal_shock_band", {"loan": 500000, "origRate": 5, "amort": 25, "term": 5, "newRate": 5})
    near(same["change"], 0)
    assert same["band"] == "low"
    s = run("renewal_shock_band", {"loan": 500000, "origRate": 2, "amort": 25, "term": 5, "newRate": 4.5, "income": 150000})
    assert s["newPmt"] > s["oldPmt"] and s["keepPaymentYears"] > 20
    near(s["shareOld"], s["oldPmt"] / 12500 * 100, 1e-9)
    pcts = [c["pct"] for c in s["curve"]]
    assert pcts == sorted(pcts)


# ------------------------------------------------------------------ doc-quest
@needs_node
def test_doc_quest_repo_examples():
    base = run("buyer_document_checklist", {"work": "salaried", "sources": ["savings"]})
    ids = sorted(d["id"] for d in base["documents"])
    assert ids == sorted(["aps", "bank90", "debts", "deposit", "id", "joblet", "pad", "paystub"])
    self_emp = [d["id"] for d in run("buyer_document_checklist", {"work": "self"})["documents"]]
    assert "t1" in self_emp and "joblet" not in self_emp
    nx = run("buyer_document_checklist", {"sources": ["gift"], "newcomer": True})["next_up"]
    assert nx[0]["wait"] > 0 and all(not d.get("later") for d in nx)
    p = run("buyer_document_checklist", {"done": ["id", "paystub"]})["progress"]
    assert p["total"] == 5 and p["done"] == 2


# ------------------------------------------------------------------ rate-cycle dashboard
@needs_node
def test_rate_cycle_readme_headlines():
    # repo's data.test.js: inflation peak 8.1% in 2022-06; mortgage peak 7.04% in 2023-10; policy max 5%
    s = run("rate_cycle_history", {})["summary"]
    assert s["inflation"]["max"]["month"] == "2022-06" and round(s["inflation"]["max"]["value"], 1) == 8.1
    assert s["mortgage"]["max"] == {"month": "2023-10", "value": 7.04}
    assert s["policy"]["max"]["value"] == 5
    w = run("rate_cycle_history", {"from": "2022-01", "to": "2022-12", "rows": True})
    assert w["months"] == 12 and len(w["rows"]) == 12
