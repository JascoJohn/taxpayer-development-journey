"""W1: ILFS 2024 indicators - weights sum to the file total, shares sum to 100%, definitions behave as documented."""
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
import ilfs_indicators as il  # noqa: E402


@pytest.fixture(scope="module")
def data():
    import pyreadstat
    df, _ = pyreadstat.read_sav(paths.ILFS_SAV, usecols=il.COLUMNS)
    rows, summary = il.compute(df)
    return df, {r["indicator"]: r for r in rows}, summary


def test_weights_sum_to_the_file_total(data):
    df, est, summary = data
    assert len(df) == 61_588
    assert df["WEIGHT"].sum() == pytest.approx(65_257_621.66, abs=0.01)
    assert summary["weight_sum_persons"] == pytest.approx(df["WEIGHT"].sum())
    # the employment ratio uses the 19th-ICLS flag NBS uses (published: 68.7%)
    assert est["Employment-to-population ratio, 15+ (19th ICLS)"]["estimate_pct"] == pytest.approx(68.7, abs=0.1)


def test_status_shares_sum_to_100(data):
    _, est, _ = data
    parts = ["employee", "employer", "own-account", "contributing family worker", "other (trainee)"]
    total = sum(est["Share of employed: " + p]["estimate_pct"] for p in parts)
    assert total == pytest.approx(100.0, abs=1e-9)
    se = est["Self-employed (employers + own-account), without contributing family workers"]["estimate_pct"]
    assert se == pytest.approx(est["Share of employed: employer"]["estimate_pct"] + est["Share of employed: own-account"]["estimate_pct"])
    assert est["Self-employed incl. contributing family workers"]["estimate_pct"] == pytest.approx(
        se + est["Share of employed: contributing family worker"]["estimate_pct"])


def test_informality_definition_pieces_are_consistent(data):
    _, est, _ = data
    by_status = ["Informal employment among employees", "Informal employment among employers and own-account workers",
                 "Informal employment among contributing family workers"]
    shares = {"Informal employment among employees": est["Share of employed: employee"]["estimate_pct"] + est["Share of employed: other (trainee)"]["estimate_pct"],
              "Informal employment among employers and own-account workers": est["Self-employed (employers + own-account), without contributing family workers"]["estimate_pct"],
              "Informal employment among contributing family workers": est["Share of employed: contributing family worker"]["estimate_pct"]}
    overall = sum(shares[k] / 100 * est[k]["estimate_pct"] for k in by_status)
    assert overall == pytest.approx(est["Informal employment rate, ICLS-17 (headline)"]["estimate_pct"], abs=1e-6)
    assert est["Informal employment among contributing family workers"]["estimate_pct"] == 100.0
    head = est["Informal employment rate, ICLS-17 (headline)"]
    assert head["ci95_low_pct"] < head["estimate_pct"] < head["ci95_high_pct"]
    assert est["Informal employment, NBS-consistent rule"]["estimate_pct"] == pytest.approx(94.6, abs=0.2)


def test_registration_bases_are_stated_and_ordered(data):
    _, est, _ = data
    keys = [k for k in est if k.startswith("Registered (any authority)")]
    assert len(keys) == 3
    head = [k for k in keys if "HEADLINE" in k]
    assert len(head) == 1 and "non-agricultural self-employed" in head[0]
    for k in keys:
        assert 0 < est[k]["estimate_pct"] < 100
    assert not any(abs(est[k]["estimate_pct"] - 46.9) < 5 for k in keys)          # no base reproduces the report's 46.9%


def test_design_matches_the_published_first_stage_sample(data):
    _, _, summary = data
    assert summary["design"]["n_psu"] == summary["design"]["published_first_stage_EAs"] == 593
    assert summary["design"]["strata_with_one_psu"] == 0 and "RECONSTRUCTED" in summary["design"]["description"]


def test_written_files_match_the_computation(data):
    _, est, summary = data
    if not os.path.exists(paths.ILFS_SUMMARY):
        pytest.skip("run run_all.py first")
    with open(paths.ILFS_SUMMARY, encoding="utf-8") as f:
        stored = json.load(f)
    assert stored["headline"]["informal_employment_pct"] == pytest.approx(est["Informal employment rate, ICLS-17 (headline)"]["estimate_pct"], abs=1e-9)
    assert stored["informality_2020_21_cited_pct"] == 92.5
    with open(paths.ILFS_INDICATORS, encoding="utf-8") as f:
        agg = json.load(f)
    assert agg["aggregates_only"] is True and "WEIGHT" in agg["source"]
    table = pd.read_csv(paths.ILFS_INFORMALITY_CSV)
    assert len(table) == len(est)


def test_classification_on_a_toy_frame():
    df = pd.DataFrame({"Q25": [1, 1, 2, 2, 3, 4, 6, 7], "Q27A": [np.nan, np.nan, 1, 2, 2, np.nan, np.nan, np.nan],
                       "Q34": [1, 2, np.nan, np.nan, np.nan, np.nan, 2, np.nan], "Q30": [np.nan] * 8, "Q31A": [np.nan] * 8,
                       "Q38A": [np.nan, np.nan, 1, 6, 6, np.nan, np.nan, np.nan], "Q38C": [np.nan] * 8, "Q22B_MAIN_ISIC": [3, 3, 7, 7, 1, 1, 3, 3]})
    c = il.classify(df)
    assert list(c["informal"]) == [0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    assert list(c["status"]) == ["employee", "employee", "employer", "own-account", "own-account", "contributing family worker",
                                 "other (trainee)", "contributing family worker"]
