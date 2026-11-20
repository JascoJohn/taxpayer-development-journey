"""Dashboard v1.1, A: the Scenario lab's pure-NumPy simulator (dashboard/tdj_lib/scenario_lab.py, reading only outputs/stats/scenario_lab_inputs.json) reproduces the pipeline's
outputs/stats/stage_economics.json, stage by stage and for the portfolio, with the pipeline's own seed and number of draws. Tolerance: math.isclose with rel_tol = abs_tol = 1e-9 (ROI values near zero, such as an ROI p10 of 5e-16, differ in the last digits between Windows and Linux; the same operations in the same
order give the same bits; the tolerance only guards against the order of float sums).

These tests read the tracked outputs of the repository (no raw data needed)."""
import json
import math
import os
import sys
import time

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
from tdj_lib import scenario_lab as sl  # noqa: E402

TOL = 1e-9


@pytest.fixture(scope="module")
def inputs():
    return sl.load_inputs(os.path.join(ROOT, "outputs", "stats", "scenario_lab_inputs.json"))


@pytest.fixture(scope="module")
def report():
    with open(os.path.join(ROOT, "outputs", "stats", "stage_economics.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def lab(inputs):
    return sl.Lab(inputs)                                   # the pipeline's own number of draws (10,000) and seed


def close(a, b):
    assert math.isclose(a, b, rel_tol=TOL, abs_tol=TOL), (a, b)


def test_inputs_carry_the_pipeline_seed_and_draws(inputs, report):
    assert inputs["shared"]["seed"] == report["seed"] and inputs["shared"]["n_draws"] == report["n_draws"]


def test_default_stages_reproduce_stage_economics(lab, report):
    res = lab.run()
    for s, st in report["stages"].items():
        mc = st["monte_carlo_at_10pct"]
        for key in ("registrants", "revenue_pv", "cost", "npv", "roi"):
            if key not in mc:
                assert key not in res["stages"][s], (s, key)
                continue
            for stat in ("median", "p10", "p90", "mean"):
                close(res["stages"][s][key][stat], mc[key][stat])
        for key, v in st["central_at_10pct"].items():
            close(res["central_stages"][s][key], v)
        if report["income_bases"]["central"]["stages"][s].get("p_roi_ge_1") is not None:
            close(res["stages"][s]["p_roi_ge_1"], report["income_bases"]["central"]["stages"][s]["p_roi_ge_1"])


def test_default_portfolio_reproduces_stage_economics(lab, report):
    res = lab.run()
    pf = report["portfolio"]
    for key, d in pf["monte_carlo_at_10pct"].items():
        for stat in ("median", "p10", "p90", "mean"):
            close(res["portfolio"][key][stat], d[stat])
    for key, v in pf["central_at_10pct"].items():
        close(res["central_portfolio"][key], v)
    close(res["portfolio"]["p_roi_ge_1"], report["income_bases"]["central"]["portfolio_excluding_asset"]["p_roi_ge_1"])


@pytest.mark.parametrize("basis", ["low", "high"])
def test_income_bases_reproduce_the_bracket(lab, report, basis):
    res = lab.run({"basis": basis})
    blk = report["income_bases"][basis]
    for s in ("entry", "active", "enterprise", "legacy"):
        for stat in ("median", "p10", "p90"):
            close(res["stages"][s]["roi"][stat], blk["stages"][s]["roi_10y"][stat])
    for stat in ("median", "p10", "p90"):
        close(res["portfolio"]["roi"][stat], blk["portfolio_excluding_asset"]["roi_10y"][stat])


def test_20_year_aged_variant_reproduces(lab, report):
    res = lab.run({"horizon": 20})
    for s in ("entry", "active", "enterprise", "legacy"):
        v = report["stages"][s]["variants"]["horizon_20_aged"]["0.1"]
        for stat in ("median", "p10", "p90"):
            close(res["stages"][s]["roi"][stat], v["roi"][stat])
    v = report["portfolio"]["variants"]["horizon_20_aged"]["0.1"]
    for stat in ("median", "p10", "p90"):
        close(res["portfolio"]["roi"][stat], v["roi"][stat])
    b = report["stages"]["asset"]["break_even_cost"]["by_variant_and_rate_tzs"]["horizon_20_aged"]["0.1"]
    for stat in ("median", "p10", "p90"):
        close(res["stages"]["asset"]["revenue_pv"][stat], b[stat])


@pytest.mark.parametrize("rate", [0.05, 0.12])
def test_discount_sensitivities_reproduce(lab, report, rate):
    res = lab.run({"rate": rate})
    v = report["portfolio"]["variants"]["horizon_10_flat"]["%g" % rate]
    for stat in ("median", "p10", "p90"):
        close(res["portfolio"]["roi"][stat], v["roi"][stat])


@pytest.mark.parametrize("pv", [0.75, 0.90, 0.95])
def test_fixed_persistence_reproduces(lab, report, pv):
    res = lab.run({"persistence": pv})
    v = report["portfolio"]["variants"]["horizon_10_flat_persistence_%.2f" % pv]["0.1"]
    for stat in ("median", "p10", "p90"):
        close(res["portfolio"]["roi"][stat], v["roi"][stat])


def test_controls_move_results_in_the_expected_direction(inputs):
    lab = sl.Lab(inputs, n_draws=1000)
    base = lab.run()
    assert lab.run({"reach_mult": 2.0})["portfolio"]["revenue_pv"]["median"] > base["portfolio"]["revenue_pv"]["median"]
    assert lab.run({"uptake_mult": 0.0})["portfolio"]["revenue_pv"]["median"] < 1.0                # no uplift: only floating-point noise is left
    assert lab.run({"persistence": 0.95})["portfolio"]["revenue_pv"]["median"] > lab.run({"persistence": 0.5})["portfolio"]["revenue_pv"]["median"]
    off = lab.run({"stages_on": dict(sl.default_controls(inputs)["stages_on"], seed=False)})
    assert off["portfolio"]["cost"]["median"] < base["portfolio"]["cost"]["median"]
    none = lab.run({"stages_on": {s: False for s in inputs["shared"]["stage_order"]}})
    assert none["portfolio"] is None


def test_live_run_is_fast_enough(inputs):
    lab = sl.Lab(inputs, n_draws=1000)
    lab.run({"basis": "central"})                          # draws once
    t = time.perf_counter()
    for i in range(5):
        lab.run({"reach_mult": 1.0 + 0.1 * i, "horizon": 20 if i % 2 else 10})
    assert (time.perf_counter() - t) / 5 < 1.0
