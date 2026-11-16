"""E1-E3: TRA-feasible variants, leakage review and refits, calibration of predicted levels by age band."""
import csv
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401


def _load(project, rel="outputs/stats/targeting_model.json"):
    with open(os.path.join(project, rel), encoding="utf-8") as f:
        return json.load(f)


def _cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_variants_use_only_their_listed_features_and_say_why_tra_can_obtain_them(pipeline_run):
    res = _load(pipeline_run)
    spec = _cfg()["targeting"]["variants"]
    assert spec["core"]["features"] == ["c8c", "c9", "reg_name", "clustertype"]                   # age, sex, region, urban/rural
    assert set(spec["extended"]["features"]) == set(spec["core"]["features"]) | {"MM", "BusO", "IncomeMain"}
    for key in ("core", "extended"):
        v = res["variants"][key]
        assert v["features"] == spec[key]["features"]
        assert set(v["encoded_from_columns"]) <= set(spec[key]["features"])
        assert v["n_encoded_features"] < 100                                                      # nothing beyond the listed columns was encoded
        assert set(v["obtainability"]) == set(spec[key]["features"])
        assert all(len(o["obtainable_by_tra"]) > 20 for o in v["obtainability"].values())
    assert res["variants"]["core"]["n_encoded_features"] < res["variants"]["extended"]["n_encoded_features"] < res["variants"]["survey_model_block_d"]["n_encoded_features"]


def test_variant_metrics_sit_next_to_the_survey_model_and_are_ordered(pipeline_run):
    res = _load(pipeline_run)
    with open(os.path.join(pipeline_run, "outputs", "tables", "targeting_variants.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5
    names = [r["model"] for r in rows]
    assert names[0].startswith("PRIMARY") and any(n.startswith("SURVEY") for n in names) and any(n.startswith("CORE") for n in names) and any(n.startswith("EXTENDED") for n in names)
    for r in rows:
        for k in ("roc_auc_weighted", "roc_auc_unweighted", "pr_auc_weighted", "brier_weighted", "brier_unweighted", "entry_multiplier_top_decile"):
            assert r[k] != "" and float(r[k]) > 0, (r["model"], k)
    auc = {r["model"].split(":")[0].split(" ")[0]: float(r["roc_auc_weighted"]) for r in rows}
    assert auc["PRIMARY"] > auc["EXTENDED"] > auc["CORE"] > 0.7 and abs(auc["PRIMARY"] - auc["SURVEY"]) < 0.01
    v = res["variants"]
    for key in ("primary", "survey_model_block_d", "core", "extended"):
        t = v[key]["held_out_test"]["logistic_regression"]
        assert 0.5 < t["roc_auc_weighted"] < 1 and 0.5 < t["roc_auc_unweighted"] < 1
        lo, hi = v[key]["entry_multiplier"]["ci95"]
        assert lo < v[key]["entry_multiplier"]["top_decile"] < hi


def test_feature_review_covers_the_financial_topics_and_keeps_paye_employment(pipeline_run):
    audit = _load(pipeline_run)["leakage_audit"]
    review = audit["feature_review"]
    rows = review["rows"]
    assert review["n_features_reviewed"] == len(rows) > 200
    for r in rows:
        assert r["class"] in ("REQUIRES_TIN", "NO_REQUIREMENT", "UNCERTAIN") and r["basis"] and r["label"] is not None, r["feature"]
        if r["class"] != "NO_REQUIREMENT" or r["family"] != "other topic-matched item":
            assert r["source_url"].startswith("http") or r["basis"].startswith("Attitude") or r["basis"].startswith("Matched"), r["feature"]
    by = {r["feature"]: r for r in rows}
    for banking in ("BANKED", "OVERALL_FORMAL", "ins2", "pens1", "cred3_1__1", "D6_3a__4"):
        assert banking in by, banking
    for emp in ("D2_1__1", "D3_1", "IncomeMain"):
        assert by[emp]["class"] == "NO_REQUIREMENT" and "KEPT" in by[emp]["decision"] and "PAYE" in by[emp]["basis"]
    assert by["D6_3a__4"]["class"] == "REQUIRES_TIN"
    assert "formal employment registered for paye" in review["formal_employment_note"].lower()
    with open(os.path.join(pipeline_run, "outputs", "tables", "targeting_leakage_review.csv"), encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == len(rows)


def test_requires_tin_features_are_absent_from_the_refit(pipeline_run):
    res = _load(pipeline_run)
    audit = res["leakage_audit"]
    requires = {r["feature"] for r in audit["feature_review"]["rows"] if r["class"] == "REQUIRES_TIN"}
    uncertain = {r["feature"] for r in audit["feature_review"]["rows"] if r["class"] == "UNCERTAIN"}
    assert requires and uncertain
    import targeting_model as tm
    df = tm.load_frame()
    X, _ = tm.build_features(df)
    single = {a["variable"] for a in audit["excluded"] if a["reason_class"] == "single_feature_leakage"}
    X = X.drop(columns=[c for c in X.columns if c in single])
    src = X.columns.map(tm.source_column)
    kept1 = [c for c, s in zip(X.columns, src) if s not in requires]
    kept2 = [c for c, s in zip(X.columns, src) if s not in requires and s not in uncertain]
    assert not ({tm.source_column(c) for c in kept1} & requires)
    assert not ({tm.source_column(c) for c in kept2} & (requires | uncertain))
    r1, r2 = audit["refits"]["without_requires_tin"], audit["refits"]["without_requires_tin_and_uncertain"]
    assert r1["n_encoded_features_kept"] == len(kept1) and r2["n_encoded_features_kept"] == len(kept2)
    assert r1["n_encoded_features_kept"] > r2["n_encoded_features_kept"]
    base = audit["refits"]["survey_model_block_d"]["held_out_test_logistic"]["roc_auc_weighted"]
    assert abs(r1["held_out_test"]["logistic_regression"]["roc_auc_weighted"] - base) < 0.02


def test_calibrated_band_means_equal_the_observed_rates(pipeline_run):
    res = _load(pipeline_run)
    df = pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), usecols=["c8c", "c27__13", "population_wt"], low_memory=False)
    age = df["c8c"].to_numpy(float)
    tin = df["c27__13"].astype(str).str.strip().str.lower().eq("yes").to_numpy()
    w = df["population_wt"].to_numpy(float)
    bands = [tuple(b) for b in _cfg()["targeting"]["agent_age_bands"]]
    rows = res["calibration_by_age_band"]["bands"]
    assert len(rows) == len(bands)
    for i, ((lo, hi), r) in enumerate(zip(bands, rows)):
        m = (age >= lo) & ((age <= hi) if i < len(bands) - 1 else np.ones(len(age), bool))
        want = float(np.average(tin[m], weights=w[m]) * 100)
        assert r["observed_tin_rate_pct"] == pytest.approx(want, abs=1e-6)
        assert r["mean_predicted_after_pct"] == pytest.approx(want, abs=1e-6)                  # the calibrated mean equals the observed rate
    entry = rows[0]
    assert (entry["age_from"], entry["age_to"]) == (16, 24) and entry["observed_tin_rate_pct"] == pytest.approx(0.77, abs=0.01)
    # the Entry deciles use the calibrated levels: their weighted mean is the observed Entry rate; the ranking (deciles) is untouched
    dec = res["entry_segment"]["deciles"]
    wt = np.array([d["weighted_population"] for d in dec], float)
    mean_pred = np.array([d["mean_predicted_pct"] for d in dec], float)
    assert float(np.average(mean_pred, weights=wt)) == pytest.approx(entry["observed_tin_rate_pct"], abs=1e-4)
    assert all(d["mean_predicted_uncalibrated_pct"] > 0 for d in dec)
    m = res["entry_segment"]["targeting_multiplier"]
    assert m["entry_calibration"]["mean_predicted_tin_rate_pct"] == pytest.approx(m["entry_calibration"]["observed_tin_rate_pct"], abs=1e-4)
    assert abs(m["modelled_top_decile"] / m["modelled_top_decile_uncalibrated"] - 1) < 0.15      # essentially unchanged
    for s in m["by_share_reached"]:
        assert s["targeted_tin_holders_per_10000_reached"] > s["random_tin_holders_per_10000_reached"] > 0


def test_agent_cells_carry_the_calibrated_propensity(pipeline_run):
    with open(os.path.join(pipeline_run, "data", "processed", "agent_cells.json"), encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    res = _load(pipeline_run)
    for band in res["calibration_by_age_band"]["bands"]:
        c = [x for x in cells if x["age_from"] == band["age_from"]]
        w = np.array([x["weighted_population"] for x in c])
        p = np.array([x["mean_propensity"] for x in c])
        # cells cover ages 16-90 (the last band is 65-90), calibration uses everyone aged 65+: a few respondents above 90 explain the small gap in the last band
        assert float(np.average(p, weights=w) * 100) == pytest.approx(band["observed_tin_rate_pct"], rel=0.10)
        assert all("mean_propensity_uncalibrated" in x for x in c)
