"""E4: tax morale components from Afrobarometer Round 8 Tanzania: reproduce from the raw file, no composite, disclosure rule held."""
import csv
import json
import os
import sys

import numpy as np
import pyreadstat
import pytest
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))["afrobarometer"]
RAW = os.path.join(ROOT, "data", "raw", "afrobarometer", "afrobarometer_release-data_tan_r8_en_2021-06-10.sav")


def _res(project):
    with open(os.path.join(project, "data", "processed", "afrobarometer_morale.json"), encoding="utf-8") as f:
        return json.load(f)


def _raw():
    cols = ["URBRUR", "Q1", CFG["weight"]] + sorted({i["variable"] for i in CFG["indicators"]})
    df, _ = pyreadstat.read_sav(RAW, usecols=cols, apply_value_formats=False)
    return df


def test_components_reproduce_from_the_raw_file(pipeline_run):
    res = _res(pipeline_run)
    df = _raw()
    assert len(df) == 2398 and res["source"]["n_respondents"] == 2398
    w = df[CFG["weight"]].to_numpy(float)
    nat = {e["indicator"]: e for e in res["estimates"] if e["level"] == "All adults 18+"}
    assert set(nat) == {i["id"] for i in CFG["indicators"]}
    for ind in CFG["indicators"]:
        x = df[ind["variable"]].to_numpy(float)
        asked = x != -1
        want = float(np.sum(w[asked & np.isin(x, ind["codes"])]) / np.sum(w[asked]) * 100)
        e = nat[ind["id"]]
        assert e["pct"] == pytest.approx(want, abs=1e-6), ind["id"]
        assert e["n_unweighted_base"] == int(asked.sum())
        assert e["ci95_low_pct"] < e["pct"] < e["ci95_high_pct"]
        valid = asked & ~np.isin(x, (8, 9, 98, 99))
        assert e["pct_of_valid"] == pytest.approx(float(np.sum(w[valid & np.isin(x, ind["codes"])]) / np.sum(w[valid]) * 100), abs=1e-6)
    # urban and rural levels reproduce as well
    for level, code in (("Urban", 1), ("Rural", 2)):
        ind = CFG["indicators"][2]
        x = df[ind["variable"]].to_numpy(float)
        m = (df["URBRUR"] == code).to_numpy() & (x != -1)
        want = float(np.sum(w[m & np.isin(x, ind["codes"])]) / np.sum(w[m]) * 100)
        got = next(e for e in res["estimates"] if e["indicator"] == ind["id"] and e["level"] == level)
        assert got["pct"] == pytest.approx(want, abs=1e-6)


def test_every_indicator_names_its_variable_wording_and_codes(pipeline_run):
    res = _res(pipeline_run)
    for ind in res["indicators"]:
        assert ind["variable"] and ind["question"] and ind["code_labels"] and ind["meaning"]
    variables = {i["variable"] for i in res["indicators"]}
    assert {"Q76E_TAN", "Q39A", "Q41J", "Q80D_TAN", "Q47D", "Q47C", "Q38A", "Q38B"} <= variables
    assert res["estimation"]["weight"] == "withinwt_hh"
    assert "INFERRED" in res["estimation"]["psu"]
    assert res["source"]["fieldwork"]["from"] == "2021-02-23"


def test_no_composite_is_published(pipeline_run):
    res = _res(pipeline_run)
    assert res["composite"]["published"] is False
    text = json.dumps(res).lower()
    for banned in ("59.8", "61.8", "composite_score", "morale_index", "weights_assumed"):
        assert banned not in text.replace("the 59.8% composite", "").replace("the wvs 61.8%", ""), banned
    with open(os.path.join(pipeline_run, "outputs", "tables", "tax_morale_components.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and all("composite" not in r["indicator"] and "composite" not in r["group"] for r in rows)
    assert {r["group"] for r in rows} <= {"civic_duty", "trust_in_tax_authority", "acceptability_of_not_paying", "perceived_avoidance", "reciprocity", "fiscal_exchange"}
    gap = res["civic_duty_minus_reciprocity_gap"]
    assert gap["recomputed"] and all(g["ci95_percentage_points"][0] < g["gap_percentage_points"] < g["ci95_percentage_points"][1] for g in gap["recomputed"])
    for g in gap["recomputed"]:
        assert g["gap_percentage_points"] == pytest.approx(g["civic_duty_pct"] - g["reciprocity_pct"], abs=1e-6)


def test_disclosure_rule_holds_in_the_published_rows(pipeline_run):
    res = _res(pipeline_run)
    for e in res["estimates"]:
        if e.get("suppressed"):
            assert e["pct"] is None and e["n_unweighted_base"] is None
        else:
            assert e["n_unweighted_base"] >= 10
            if e["n_unweighted_numerator"] is not None:
                assert e["n_unweighted_numerator"] >= 10
            else:
                assert e.get("low_precision") is True
    with open(os.path.join(pipeline_run, "outputs", "tables", "tax_morale_components.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["n_unweighted_base"]:
                assert int(float(r["n_unweighted_base"])) >= 10
            if r["n_unweighted_numerator"]:
                assert int(float(r["n_unweighted_numerator"])) >= 10


def test_mapped_baselines_are_data_and_the_rest_stay_assumptions(pipeline_run):
    res = _res(pipeline_run)
    scores = res["baseline_scores"]
    for key in ("trust", "social_norm", "fairness", "simplicity"):
        e = assumptions.entry("tax_morale.baseline." + key)
        assert e["basis"] == "DATA" and "value" not in e and e["data_path"] == "baseline_scores.%s.value" % key
        assert scores[key]["mapped"] and scores[key]["variable"] and 0 < scores[key]["value"] < 1
        lo, hi = scores[key]["ci95"]
        assert lo < scores[key]["value"] < hi
    for key in ("enforcement",):
        e = assumptions.entry("tax_morale.baseline." + key)
        assert e["basis"] == "ASSUMPTION" and "value" in e
        assert not scores[key]["mapped"] and "NOT MAPPED" in scores[key]["rationale"].upper()
    # the model reads the data values (the real project's processed file; the test run uses the same data and code)
    real = json.load(open(paths.AFROBAROMETER_MORALE, encoding="utf-8"))["baseline_scores"]["trust"]["value"]
    assert assumptions.A("tax_morale.baseline.trust") == pytest.approx(real)
