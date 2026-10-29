"""Renewal Radar module: tools call the vendored Renewal Radar engines in-process (no network)."""
import importlib.util
from pathlib import Path

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.modules import MODULES, load_all
from decision_ladder.modules import rr_service

ROOT = Path(__file__).resolve().parent.parent
RR = ROOT / "modules" / "renewal-radar"
pytestmark = pytest.mark.skipif(not (RR / "backend" / "renewal").is_dir() or importlib.util.find_spec("pydantic") is None,
                                reason="Renewal Radar sources or pydantic not available")

load_all()

TD = dict(lender="TD", balance=640000, contract_rate=5.29, term_months=60, start="2023-08-01",
          posted_at_origination=6.84, payout="2026-10-28", amort_months=276,
          current_posted={"6": 5.74, "12": 5.69, "24": 5.39, "36": 6.04, "48": 5.99, "60": 6.09, "72": 6.29, "84": 6.4, "120": 6.8})


def letter_pages():
    from pypdf import PdfReader
    return [p.extract_text() for p in PdfReader(str(RR / "fixtures" / "fictional-renewal-letter.pdf")).pages]


def test_module_registered_with_tools():
    m = MODULES["renewal-radar"]
    assert m.kind == "service" and m.live_url and "servicing" in m.stages
    assert {"rr_letter_xray", "rr_bank_penalty", "rr_penalty_helper", "rr_broker_book_review"} <= set(m.tools)
    assert m.lines_of_code > 20000


def test_letter_xray_reads_sample_letter():
    pytest.importorskip("pypdf")
    out = T.run("rr_letter_xray", {"pages": letter_pages()})
    assert "error" not in out, out
    f = {k: v["value"] for k, v in out["fields"].items()}
    assert f["balance"] == 480000 and f["offered_rate"] == 5.49 and f["current_rate"] == 4.19
    assert f["term_months"] == 36 and f["maturity_date"] == "2027-03-01" and f["amortization_months"] == 228
    assert out["missing_required"] == [] and out["tasks"]


def test_letter_xray_requires_text():
    assert "error" in T.run("rr_letter_xray", {"text": "   "})


def test_td_exact_penalty_with_supplied_table():
    out = T.run("rr_bank_penalty", TD)
    assert "error" not in out, out
    assert out["status"] == "exact-method" and out["lender_policy"] == "TD" and out["rates_source"] == "supplied by caller"
    assert out["discount"] == pytest.approx(1.55) and out["compare_term"] == 24
    assert out["penalty"] == max(out["three_month"], out["ird"]) and out["method"] == "IRD"


def test_penalty_uses_rate_book_when_no_table():
    args = {k: v for k, v in TD.items() if k != "current_posted"}
    out = T.run("rr_bank_penalty", args)
    assert "error" not in out, out
    assert out["rates_source"].startswith("rate book (TD")


def test_unknown_lender_without_table_is_an_error_not_a_crash():
    args = {**{k: v for k, v in TD.items() if k != "current_posted"}, "lender": "Some Credit Union"}
    assert "error" in T.run("rr_bank_penalty", args)


@pytest.mark.parametrize("helper", ["break-even", "cheapest-day", "blend", "lump-sum", "sensitivity", "port-vs-break",
                                    "countdown", "stress-test", "net-switch", "reverse-rate", "heatmap", "summary"])
def test_every_penalty_helper(helper):
    out = T.run("rr_penalty_helper", {**TD, "helper": helper, "new_rate": 4.39, "quoted_penalty": 15000})
    assert "error" not in out, out
    assert out["helper"] == helper and out["result"] is not None


def test_helper_validation():
    assert "new_rate is required" in T.run("rr_penalty_helper", {**TD, "helper": "net-switch"})["error"]
    assert "error" in T.run("rr_penalty_helper", {**TD, "helper": "nope"})


def test_sensitivity_moves_penalty_the_right_way():
    rows = T.run("rr_penalty_helper", {**TD, "helper": "sensitivity"})["result"]
    by = {r["posted_move"]: r["penalty"] for r in rows}
    assert by[-0.5] > by[0.0] > by[0.5]  # higher posted rates -> lower IRD


def test_forecast_has_transitions():
    out = T.run("rr_penalty_forecast", TD)
    assert "error" not in out and out["weeks"] > 50 and out["transitions"]


def test_switch_pathway_straight_switch_and_refinance():
    s = T.run("rr_switch_pathway", {"balance": 480000, "offered_rate": 5.49, "maturity_date": "2027-03-01"})
    assert s["status"] == "potentially-exempt" and s["sources"]
    r = T.run("rr_switch_pathway", {"balance": 480000, "offered_rate": 5.49, "maturity_date": "2027-03-01", "cash_out": 50000})
    assert r["status"] == "new-underwriting" and r["qualifying_rate"] == 7.49


def test_negotiation_script():
    out = T.run("rr_negotiation_script", {"balance": 480000, "offered_rate": 5.49, "maturity_date": "2027-03-01",
                                          "amortization_months": 228, "term_months": 36, "competing_rate": 4.49})
    assert "error" not in out, out
    assert len(out["call_script"]) >= 5 and out["modelled_payment_difference"] > 0 and not out["offer_verified"]


def test_wait_economics():
    out = T.run("rr_wait_economics", {"balance": 480000, "old_rate": 5.49, "new_rate": 4.49, "amort_months": 228,
                                      "horizon_months": 36, "wait_months": 6, "later_penalty": 3000})
    assert "error" not in out and out["net_benefit"] == pytest.approx(out["interest_saved"] - 3000, abs=0.01)


def test_lead_score_bands():
    hot = T.run("rr_lead_score", {"renewal_date": "2027-01-15", "balance": 480000, "current_rate": 5.49,
                                  "market_rate": 4.49, "has_statement": True, "today": "2026-10-28"})
    assert hot["band"] == "hot" and hot["score"] == 85
    cold = T.run("rr_lead_score", {"today": "2026-10-28"})
    assert cold["band"] == "nurture"


def test_renewal_plan_dates():
    out = T.run("rr_renewal_plan", {"maturity_date": "2027-03-01"})
    assert out["steps"][0]["due"] == "2026-11-01" and out["steps"][-1]["due"] == "2027-03-01"


def test_broker_book_review_on_sample_book():
    csv_text = (RR / "fixtures" / "broker-book-sample.csv").read_text()
    out = T.run("rr_broker_book_review", {"csv": csv_text, "target_rate": 4.39, "as_of": "2026-10-20"})
    assert "error" not in out, out
    assert out["deals_reviewed"] == 8 and sum(out["summary"].values()) == 8
    assert all(r["status"] for r in out["results"])


def test_penalty_accuracy_report():
    out = T.run("rr_penalty_accuracy", {})
    assert out["report"]["td_oracle"]["exact_to_the_cent"] == 2000
    assert {"RBC", "TD", "Scotiabank", "BMO", "CIBC", "National Bank"} <= set(out["verified_lender_methods"])


def test_service_status_is_honest():
    st = rr_service.status()
    assert st["url"].endswith(":8100") or st["url"]
    assert "uvicorn" in st["command"] and "renewal.main:app" in st["command"]
    if st["missing_dependencies"]:
        assert not rr_service.start(wait=1)["ok"]
