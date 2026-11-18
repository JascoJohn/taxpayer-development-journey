"""W5: one stratification, one weight; the population-weighted average of the stage TIN rates equals the overall rate."""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import requires_raw

pytestmark = requires_raw          # needs the restricted microdata: skipped with a message when they are absent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import survey_design  # noqa: E402
import tin_by_segment as tin  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), low_memory=False)


@pytest.fixture(scope="module")
def result(df):
    return tin.compute(df)


def test_identity_holds_exactly(result):
    rows, rec = result
    assert rec["identity_holds"] is True
    assert abs(rec["difference_pct_points"]) <= 1e-9
    assert rec["unassigned_respondents"] == 0
    stage_rows = [r for r in rows if r["segment"] != "overall"]
    assert [r["segment"] for r in stage_rows] == ["entry", "active", "enterprise", "workers", "asset", "legacy"]
    avg = sum(r["population_weighted"] / rec["weighted_population"] * r["tin_rate_pct"] for r in stage_rows)
    assert avg == pytest.approx(rows[0]["tin_rate_pct"], abs=1e-9)
    assert sum(r["n_unweighted"] for r in stage_rows) == 9915
    assert sum(r["tin_holders_unweighted"] for r in stage_rows) == rows[0]["tin_holders_unweighted"] == 361


def test_rounded_rates_match_the_report(result):
    rows, rec = result
    by = {r["segment"]: r for r in rows}
    assert round(by["overall"]["tin_rate_pct"], 1) == 3.8
    # stage mapping B (Pass 6B-1): the Active and Enterprise rates of the submitted report (4.6, 9.7) belong to the former mapping and are no longer asserted as report values
    assert round(by["active"]["tin_rate_pct"], 1) == 6.4
    assert round(by["enterprise"]["tin_rate_pct"], 1) == 26.5
    assert round(by["workers"]["tin_rate_pct"], 1) == 4.6
    assert round(by["asset"]["tin_rate_pct"], 1) == 4.3
    assert round(rec["weighted_population"]) == 34134251
    assert round(rows[0]["tin_holders_weighted"]) == 1306683
    for k, v in rec["report_values_pct"].items():
        assert v["report"] == v["computed_rounded_1dp"], k


def test_json_and_table_match_the_computation(result):
    """The files written by run_all.py hold the same numbers as a fresh computation."""
    rows, rec = result
    if not (os.path.exists(paths.TIN_RECONCILIATION) and os.path.exists(paths.TIN_BY_SEGMENT_CSV)):
        pytest.skip("run run_all.py first")
    with open(paths.TIN_RECONCILIATION, encoding="utf-8") as f:
        stored = json.load(f)
    for k, v in stored["stage_rates_pct"].items():
        assert v == pytest.approx(rec["stage_rates_pct"][k], abs=1e-9)
    assert stored["overall_tin_rate_pct"] == pytest.approx(rec["overall_tin_rate_pct"], abs=1e-9)
    assert stored["identity_holds"] is True
    table = pd.read_csv(paths.TIN_BY_SEGMENT_CSV).set_index("segment")
    for r in rows:
        assert table.loc[r["segment"], "tin_rate_pct"] == pytest.approx(r["tin_rate_pct"], abs=1e-4)
        assert table.loc[r["segment"], "n_unweighted"] == r["n_unweighted"]


def test_fails_loudly_when_a_respondent_is_outside_the_adult_stages(df):
    broken = df.copy()
    broken.loc[broken.index[0], "c8c"] = 10          # a Seed-age respondent: not in any adult stage
    with pytest.raises(tin.ReconciliationError):
        tin.compute(broken)


def test_design_is_reconstructed_and_complete(result):
    rows, rec = result
    d = rec["design_summary"]
    assert d["n_psu"] == 666 and d["n_strata"] == 61 and d["strata_with_one_psu"] == 0
    for r in rows:
        assert r["ci95_low_pct"] <= r["tin_rate_pct"] <= r["ci95_high_pct"]
    assert "RECONSTRUCTED" in rec["design"]


def test_linearised_ratio_matches_a_hand_calculation():
    # one stratum, two PSUs of one unit each, equal weights: R = mean(y); Var(R) = (y1 - y2)^2 / 4
    r, se, n_psu, n_str, lonely = survey_design.linearised_ratio([1, 0], [1, 1], [1.0, 1.0], ["h", "h"], ["a", "b"])
    assert r == pytest.approx(0.5) and se == pytest.approx(0.5) and (n_psu, n_str, lonely) == (2, 1, 0)
    # a stratum with a single PSU is counted, not silently used
    _, _, _, _, lonely = survey_design.linearised_ratio([1, 0], [1, 1], [1.0, 1.0], ["h", "g"], ["a", "b"])
    assert lonely == 2
    lo, hi = survey_design.ci95(0.05, 0.01, 600, 60)
    assert 0 < lo < 0.05 < hi < 1
