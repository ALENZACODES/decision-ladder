"""Modules added from the author's rate notebooks, Quiet Charges and Shoebox."""
import shutil

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.modules import MODULES, load_all
from decision_ladder.modules.registry import MODULES_DIR, notebook_code_lines

load_all()
node = pytest.mark.skipif(not (shutil.which("node") or shutil.which("nodejs")), reason="needs Node")


def test_modules_registered():
    for k in ("canada-policy-rate-bond-yield-mortgage-rate", "canada-real-interest-rates-cpi-vs-policy-rate",
              "canada-renewal-shock-2020-2021-five-year-fixed", "kaggle-boc-notebooks", "quiet-charges", "shoebox",
              "renewal-check-pitch"):
        assert k in MODULES and MODULES[k].path.is_dir()


def test_rate_spreads_latest_and_as_of():
    r = T.run("rate_spreads", {})
    assert r["policy_rate"]["pct"] == 2.25 and r["goc_5yr_yield"]["pct"] == 3.53
    assert r["spreads"]["posted_minus_effective_pts"] == round(6.19 - 4.49, 2)
    past = T.run("rate_spreads", {"as_of": "2023-07-15"})
    assert past["policy_rate"]["date"] <= "2023-07-15" and "nowcast_5yr_effective" not in past


def test_notebook_lines_count_code_cells_only():
    nb = MODULES_DIR / "canada-policy-rate-bond-yield-mortgage-rate" / "canada-policy-rate-bond-yield-mortgage-rate.ipynb"
    n = notebook_code_lines(nb)
    assert 0 < n < sum(1 for _ in nb.open(encoding="utf-8"))


@node
def test_quiet_charges_sample():
    r = T.run("recurring_charges_scan", {"today": "2026-10-29"})
    assert r["sample"] and r["active_recurring"] == 6 and r["monthly"] == 171.21


@node
def test_quiet_charges_custom_csv():
    rows = ["Date,Description,Amount"] + [f"2026-{m:02d}-05,ACME LEASE #12,-410.00" for m in range(1, 10)]
    r = T.run("recurring_charges_scan", {"csv": "\n".join(rows), "today": "2026-10-01"})
    assert r["active_recurring"] == 1 and r["recurring"][0]["cadence"] == "monthly" and r["monthly"] == 410


@node
def test_shoebox_sample_lines():
    r = T.run("self_employed_expense_lines", {})
    assert r["deductible"] > 0 and "9220" in r["needs_business_use_pct"]
    meals = next(x for x in r["by_line"] if x["line"] == "8523")
    assert meals["claim"] == round(meals["spent"] * 0.5, 2)
