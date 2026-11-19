"""Pass 6B-1 H4: the digital twin is retired and replaced by the reach scenarios of the four stage tools (Figure 5.2), scale-checked against the TRA FY2024/25 collections."""
import csv
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import reach_scenarios as rs  # noqa: E402
import tra_collections as tc  # noqa: E402


def _res():
    with open(paths.REACH_SCENARIOS, encoding="utf-8") as f:
        return json.load(f)


def test_the_twin_is_retired_and_not_in_the_pipeline():
    assert os.path.exists(os.path.join(ROOT, "src", "retired", "digital_twin_v0.py"))
    readme = open(os.path.join(ROOT, "src", "retired", "README.md"), encoding="utf-8").read()
    for cite in ("PASS6A D2", "PASS6C E1", "PASS6D F4"):
        assert cite in readme, cite
    assert "F5" in readme
    run_all = open(os.path.join(ROOT, "run_all.py"), encoding="utf-8").read()
    assert "digital_twin" not in run_all and "run_digital_twin" not in run_all and "reach_scenarios" in run_all
    em = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    assert "def run_digital_twin" not in em and "twin_baseline" not in em
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        assert "digital_twin_baseline" not in json.load(f)
    for ext in ("png", "svg"):                                                      # the stale outputs are deleted
        assert not os.path.exists(os.path.join(ROOT, "outputs", "figures", "fig_5_2_digital_twin." + ext))
    assert not os.path.exists(os.path.join(ROOT, "src", "06_figures", "fig_5_2_digital_twin.py"))
    for k in ("twin.ussd.conversion", "twin.msme.tin_rate", "twin.presumptive.uplift_factor"):
        assert k in paths.CFG["retired_assumptions"] and paths.CFG["retired_assumptions"][k]["retired_in"] == "Pass 6B-1"


def test_four_levers_and_the_secondary_set_at_four_reach_settings():
    d = _res()
    assert set(d["sets"]) == {"four_levers", "entry_active"} and d["sets"]["entry_active"] == ["entry", "active"] and d["sets"]["four_levers"] == ["entry", "active", "enterprise", "legacy"]
    assert set(d["reach_scenarios"]) == {"table5_1_reach", "reach_10pct", "reach_25pct", "reach_50pct"}
    assert d["income_basis"] == "hbs_receipts_owners" and d["stage_mapping"] == "B" and "MODELLED" in d["label"]
    y = {(r["set"], r["scenario"]): r for r in d["year10"]}
    rev = [y[("four_levers", s)]["incremental_revenue_tzs"] for s in ("reach_10pct", "reach_25pct", "reach_50pct")]
    assert rev[0] < rev[1] < rev[2]
    assert rev[2] == pytest.approx(rev[0] * 5, rel=0.02)                          # revenue is linear in a flat reach
    for k in ("table5_1_reach", "reach_10pct", "reach_25pct", "reach_50pct"):
        assert y[("entry_active", k)]["incremental_revenue_tzs"] < y[("four_levers", k)]["incremental_revenue_tzs"]
        r = y[("four_levers", k)]
        assert r["revenue_p10"] <= r["incremental_revenue_tzs"] <= r["revenue_p90"] and r["payers_p10"] <= r["active_payers_owing_tax"] <= r["payers_p90"]
        assert r["active_payers_owing_tax"] <= r["alive_registrants"] <= r["registrants_cum"]
    assert len([r for r in d["by_year"] if r["set"] == "four_levers" and r["scenario"] == "reach_10pct"]) == 10


def test_the_registration_trend_is_its_own_component():
    d = _res()
    by = [r for r in d["by_year"] if r["set"] == "four_levers" and r["scenario"] == "reach_50pct"]
    assert all(r["trend_revenue_tzs_median"] > r["incremental_revenue_tzs_median"] for r in by)        # drawn as its own line, never added to the tools
    assert "its own component" in d["trend_component"]["label"] and d["trend_component"]["new_registrants_per_year"] > 0


def test_the_scale_check_against_tra_fy2024_25_and_the_retired_twin():
    d = _res()
    sc = d["scale_check_tra_fy2024_25"]
    assert sc["tra_fy2024_25_tzs"]["individuals_income_tax"] == pytest.approx(305.95e9, rel=1e-3)
    assert sc["tra_fy2024_25_tzs"]["total_gross"] == pytest.approx(31.594e12, rel=1e-3)
    for nm, v in sc["year10_increment_tzs"].items():
        assert v < 0.05 * sc["tra_fy2024_25_tzs"]["individuals_income_tax"] * 100 and v < 6.15e12 / 100, nm          # nowhere near the retired twin's 6.15 trillion
    assert sc["pct_of"]["four_levers_reach_50pct"]["individuals_income_tax"] < 5
    with open(paths.TRA_COLLECTIONS_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["type"] == "CITED" and raw["fiscal_year"] == "2024/25" and raw["tzs"]["individuals_income_tax"] == sc["tra_fy2024_25_tzs"]["individuals_income_tax"]


def test_the_full_reach_implication_of_figure_5_1_is_stored():
    f = _res()["figure_5_1_full_reach_implication"]
    assert round(f["extra_tin_holders_best_single_at_full_reach"]) == 592707 and round(f["extra_tin_holders_combined_at_full_reach"]) == 2166125
    assert "NO reach factor" in f["reading"] and f["table5_1_new_registrants_median_four_levers"] < f["extra_tin_holders_best_single_at_full_reach"] / 50


def test_the_tables_and_the_figure_exist_with_the_evidence_type():
    for p in (paths.REACH_YEAR10_CSV, paths.REACH_BY_YEAR_CSV):
        df = pd.read_csv(p)
        assert (df["evidence_type"] == "MODELLED (scenario)").all()
    assert len(pd.read_csv(paths.REACH_YEAR10_CSV)) == 8 and len(pd.read_csv(paths.REACH_BY_YEAR_CSV)) == 80
    assert os.path.exists(os.path.join(ROOT, "outputs", "figures", "fig_5_2_reach_scenarios.png"))


def test_cohort_arithmetic():
    draws, ramp = 4, 5
    spec = {"population": 1000.0}
    inp = {"reach": np.full(draws, 0.5), "persist": np.full(draws, 0.5), "p": np.full(draws, 0.1), "lnor": np.full(draws, np.log(2.0)), "tax": np.full(draws, 100.0)}
    delta = 1 / (1 + np.exp(-(np.log(0.1 / 0.9) + np.log(2.0)))) - 0.1
    c = rs.cohort(spec, inp, 0.5, None, draws, ramp)
    new = 1000 * 0.5 * delta
    assert c["cum"][0, 0] == pytest.approx(new / 5) and c["cum"][4, 0] == pytest.approx(new) and c["cum"][9, 0] == pytest.approx(new)
    assert c["alive"][0, 0] == pytest.approx(new / 5)
    assert c["alive"][1, 0] == pytest.approx(new / 5 * (1 + 0.5))                      # the first cohort persists at 0.5, the second enters
    assert c["payers"][3, 0] == pytest.approx(0.5 * c["alive"][3, 0]) and c["rev"][3, 0] == pytest.approx(100.0 * c["alive"][3, 0])
    zero = rs.cohort(spec, inp, 0.5, 0.0, draws, ramp)
    assert zero["cum"].sum() == 0 and zero["rev"].sum() == 0
    full = rs.cohort(spec, inp, 0.5, 20.0, draws, ramp)                                  # cannot register more than the stage's unregistered adults
    assert full["cum"][-1, 0] == pytest.approx(1000 * 0.9)


def test_the_tra_workbook_reader_needs_four_quarters():
    d = pd.DataFrame([["x", 1.0, 2.0, 3.0, 4.0], ["y", 1.0, 0.0, 0.0, 0.0]])
    assert tc._annual(d, 0, [1, 2, 3, 4]) == 10.0
    with pytest.raises(ValueError):
        tc._annual(d, 1, [1, 2, 3, 4])
