"""W9: the targeting model is trained on the real FinScope respondents; only aggregates are published."""
import copy
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import ROOT, requires_raw

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401


def _load(project, rel):
    with open(os.path.join(project, rel), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- published outputs
def test_no_respondent_level_rows_in_any_output(pipeline_run):
    """No published file holds respondent-level rows: no array as long as the survey (or the Entry segment), no per-person scores."""
    n_resp = 9915
    big = []
    banned_keys = {"probabilities", "propensities", "respondent_id", "SN", "respondents", "individual_scores"}

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                assert k not in banned_keys, (path, k)
                walk(v, path + "/" + k)
        elif isinstance(x, list):
            if len(x) >= 1000:
                big.append((path, len(x)))
            for i, v in enumerate(x[:50]):
                walk(v, path + "[%d]" % i)
    for d in ("data/interim", "data/processed", "outputs/stats"):
        for root, _, files in os.walk(os.path.join(pipeline_run, d)):
            for f in files:
                if f.endswith(".json") and f != "run_meta.json":
                    p = os.path.join(root, f)
                    with open(p, encoding="utf-8") as fh:
                        walk(json.load(fh), os.path.relpath(p, pipeline_run))
    assert big == [], big
    assert n_resp > 1000
    assert not os.path.exists(os.path.join(pipeline_run, "outputs", "stats", "finscope_targeting_population.json"))
    for rel in ("outputs/tables/targeting_deciles.csv",):
        n_lines = sum(1 for _ in open(os.path.join(pipeline_run, rel), encoding="utf-8"))
        assert n_lines <= 11                                                        # header + ten deciles


def test_published_cells_follow_the_disclosure_rule(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/targeting_model.json")
    for d in res["entry_segment"]["deciles"]:
        if d.get("suppressed"):
            assert d["mean_predicted_pct"] is None and d["n_unweighted"] is None
        else:
            assert d["n_unweighted"] >= 10
            if d.get("n_tin_unweighted") is not None:
                assert d["n_tin_unweighted"] >= 10
            else:
                assert d.get("low_precision") is True
    cells = _load(pipeline_run, "data/processed/agent_cells.json")["cells"]
    assert cells and all(c["n_unweighted"] >= 10 for c in cells)
    assert res["entry_segment"]["targeting_multiplier"]["definition"]


def test_metrics_are_reported_for_both_models_weighted_and_unweighted(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/targeting_model.json")
    for model in ("logistic_regression", "gradient_boosting"):
        m = res["held_out_test"][model]
        for k in ("roc_auc_weighted", "roc_auc_unweighted", "pr_auc_weighted", "pr_auc_unweighted", "brier_weighted", "brier_unweighted"):
            assert 0 <= m[k] <= 1, (model, k)
        assert m["roc_auc_weighted"] > 0.7                  # far above chance, far below 1 (no leakage of the outcome)
        assert m["roc_auc_weighted"] < 0.99
    assert res["split"]["stratified"] is True and abs(res["split"]["test_size"] - 0.2) < 1e-9
    assert res["cross_validation"]["folds"] == 5
    assert res["calibration_test_set"]["logistic_regression"]
    assert "observational" in res["label"]


def test_leakage_audit_lists_every_excluded_variable_with_a_reason(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/targeting_model.json")
    audit = res["leakage_audit"]["excluded"]
    names = {a["variable"] for a in audit}
    assert all(a["reason"] for a in audit)
    assert "c27__13" in names                                                      # the outcome
    assert {n for n in names if re.match(r"c27__\d+$", n)} >= {"c27__13", "c27__4", "c27__7", "c27__15"}
    assert {"c24_2a", "gov_2__7", "D6_4a", "D6_4b"} <= names
    assert any(re.match(r"D6_4c__", n) for n in names)
    assert res["leakage_audit"]["data_map_label_search"]["status"] == "searched"


# ---------------------------------------------------------------- reproducibility (in-process, light settings)
@pytest.fixture(scope="module")
def tm():
    import importlib
    return importlib.import_module("targeting_model")


def _light(tm, monkeypatch):
    cfg = copy.deepcopy(tm.CFG)
    cfg["cv_repeats"] = 1
    cfg["logistic"]["c_grid"] = [0.003, 0.03]
    cfg["gradient_boosting"]["max_iter"] = 30
    cfg["bootstrap_replicates"] = 20
    cfg["permutation_candidates"] = 5
    cfg["permutation_repeats"] = 1
    monkeypatch.setattr(tm, "CFG", cfg)


@requires_raw
def test_excluded_variables_are_absent_from_the_features(tm):
    df = pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), low_memory=False)
    X, audit = tm.build_features(df)
    sources = {c.split("=")[0] for c in X.columns}
    for bad in ("c27__13", "c24_2a", "gov_2__7", "D6_4a", "D6_4b", "population_wt", "Household_weight", "SN", "dist_name", "ward_name", "ea_code"):
        assert bad not in sources, bad
    assert not any(re.match(r"c27__\d+$", s) or re.match(r"D6_4c", s) for s in sources)
    assert {a["variable"] for a in audit} >= {"c27__13", "c24_2a"}
    assert X.shape[1] > 300                                                        # broad: far beyond the former six features


@requires_raw
def test_two_runs_give_identical_cv_and_stable_heldout_auc(tm, monkeypatch, tmp_path):
    _light(tm, monkeypatch)
    out = []
    for i in range(2):
        out.append(tm.run_targeting_model(json_path=str(tmp_path / ("a%d.json" % i)), deciles_path=str(tmp_path / ("d%d.csv" % i)),
                                          cells_path=str(tmp_path / ("c%d.json" % i)), quick=True,
                                          variants_path=str(tmp_path / ("v%d.csv" % i)), review_path=str(tmp_path / ("r%d.csv" % i))))      # Pass 4: the quick run must not overwrite the published variants and leakage tables
    a, b = out
    assert a["cross_validation"]["results"] == b["cross_validation"]["results"]                       # seeded CV reproduces exactly
    for m in ("logistic_regression", "gradient_boosting"):
        assert abs(a["held_out_test"][m]["roc_auc_weighted"] - b["held_out_test"][m]["roc_auc_weighted"]) < 1e-9
    assert open(tmp_path / "d0.csv", "rb").read() == open(tmp_path / "d1.csv", "rb").read()
    assert open(tmp_path / "c0.json", "rb").read() == open(tmp_path / "c1.json", "rb").read()
