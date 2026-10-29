"""House prices / home value modules: values checked against the vendored data files and the published READMEs."""
import json

import pytest

from decision_ladder.agent import tools as T
from decision_ladder.modules import MODULES, load_all
from decision_ladder.modules import homevalue as H

load_all()

TOOLS = ("benchmark_home_price", "postal_area_home_value", "index_purchase_to_today", "housing_affordability_index",
         "affordability_rate_sensitivity", "valuation_accuracy")


def test_modules_and_tools_registered():
    for k in ("benchmark-home-value", "canada-home-value", "canada-housing-affordability-index-1980-2026"):
        assert k in MODULES and MODULES[k].path.is_dir()
    for t in TOOLS:
        assert t in T.TOOLS
        spec = T.TOOLS[t].spec()["function"]
        assert spec["parameters"]["type"] == "object"
        for r in spec["parameters"].get("required", []):
            assert r in spec["parameters"]["properties"]


def test_ui_entries_exist_and_core_data_is_local():
    for k in ("benchmark-home-value", "canada-home-value"):
        m = MODULES[k]
        assert (m.web_path / m.entry).is_file()
    d = H.BHV / "data"
    for f in ("fsa.json", "munis.json", "accuracy.json", "backtest.json", "updated.json", "rents.json", "recent.json"):
        assert (d / f).is_file(), f
    assert not (d / "addr").exists() and not (d / "detail").exists()   # bulk files intentionally remote


def test_page_constants_parsed_from_index_html():
    p = H.page()
    assert set(p["ANCH"]) >= {"GTA", "OTT", "CGY", "VAN", "MTL", "ATL"}
    assert p["ANCH"]["GTA"][-1] == [2026, 8, 146]
    assert p["TYPE"]["GTA"]["detached"] == 1.42
    oak = next(c for c in p["M"] if c["name"] == "Oakville")
    assert oak["bench"] == 1128800 and "L6J" in oak["fsa"]
    assert p["G_PRE"] == {"ON": 0.06, "BC": 0.07, "QC": 0.045}


def test_index_series_matches_anchors():
    s = H.index_series("GTA")
    assert len(s) == H.N_MONTHS == 129
    # anchors are exact before the +/-1.2% seasonal factor; Jan 2016 has month 0 -> sin(-1/12*2pi)
    import math
    assert s[0] == pytest.approx(100 * (1 + 0.012 * math.sin(-1 / 12 * 2 * math.pi)), rel=1e-9)


def test_benchmark_price_oakville_matches_page_table():
    r = T.run("benchmark_home_price", {"place": "Oakville"})
    assert r["benchmark_price"] == 1129000          # round(1,128,800 / 1000) * 1000, as seriesFor does
    assert r["by_type"]["detached"] == round(1128800 * 1.42 / 1000) * 1000
    assert r["as_of"] == "2026-09" and r["source"]["module"] == "benchmark-home-value"
    assert r["source"]["prices_as_of"]
    # postal prefix resolves to the same city; accents are tolerated
    assert T.run("benchmark_home_price", {"place": "L6J 3K2"})["city"] == "Oakville"
    assert T.run("benchmark_home_price", {"place": "Montreal"})["city"] == "Montréal"


def test_benchmark_price_unknown_place_is_tool_error():
    assert "error" in T.run("benchmark_home_price", {"place": "Atlantis"})


def test_postal_area_value_from_fsa_json():
    raw = json.loads((H.BHV / "data" / "fsa.json").read_text())["T2P"]
    r = T.run("postal_area_home_value", {"fsa": "t2p", "property_type": "condo"})
    assert r["census_2021_median_value"] == raw["c21"] and r["estimated_value_today"] == raw["c"]
    assert r["typical_value_for_type"] == raw["t"]["condo"][0]


def test_index_purchase_is_price_times_index_ratio():
    r = T.run("index_purchase_to_today", {"purchase_price": 780000, "purchase_year": 2021, "purchase_month": 11,
                                         "place": "Markham"})
    idx = H.index_series("GTA")
    assert r["value_today"] == pytest.approx(780000 * idx[-1] / idx[H.mi(2021, 10)], abs=0.01)
    pre = T.run("index_purchase_to_today", {"purchase_price": 400000, "purchase_year": 2010, "purchase_month": 6,
                                           "place": "Toronto", "renovation_spend": 50000})
    assert pre["pre_2016_extension"] and pre["value_today_with_renovations"] > pre["value_today"]
    assert "error" in T.run("index_purchase_to_today", {"purchase_price": 1, "purchase_year": 2027, "purchase_month": 1,
                                                       "place": "Toronto"})


def test_affordability_matches_published_readme_figures():
    # README results, run of 2026-10-18
    r = T.run("housing_affordability_index", {})
    assert r["quarter"] == "2026 Q2" and r["affordability_index_pct"] == 41.3
    assert r["long_run_average_pct"] == 37.4
    assert round(r["share_of_quarters_more_affordable_pct"]) == 77
    assert r["all_time_high"] == {"quarter": "1981 Q3", "pct": 64.7, "posted_5y_rate": 20.7}
    assert r["all_time_low"]["quarter"] == "2002 Q1" and r["all_time_low"]["pct"] == 27.5
    assert r["posted_5y_rate_avg_that_quarter"] == 6.09 and r["nhpi_yoy_pct"] == -2.3
    q = T.run("housing_affordability_index", {"quarter": "2023 Q3"})
    assert q["affordability_index_pct"] == 54.5 and q["posted_5y_rate_avg_that_quarter"] == 6.72


def test_affordability_rate_sensitivity_matches_readme():
    r = T.run("affordability_rate_sensitivity", {"rate_change_pts": -1})
    assert r["yearly_change_correlation"] == 0.85
    assert round(r["index_points_per_1pt_rate_move"], 1) == 3.1
    assert r["level_correlation"] == 0.57
    assert r["implied_index_change_pts"] == pytest.approx(-r["index_points_per_1pt_rate_move"])


def test_valuation_accuracy_reports_and_admits_avm_not_callable():
    r = T.run("valuation_accuracy", {"city": "Calgary"})
    assert r["benchmark_home_value"]["tested_homes"] == 974500
    assert r["benchmark_home_value"]["median_abs_pct_error_by_group_and_method"]["All"]["index"] == 0.0625
    assert r["canada_home_value_avm"]["callable_here"] is False
    assert r["canada_home_value_avm"]["city_median_abs_pct_err"] == 0.0555
    assert "avm_estimate" not in T.TOOLS
