"""W6: the TIN / mobile-money evidence is an observational association estimated on the real FinScope respondents."""
import csv
import json
import os
import re

import numpy as np
import pandas as pd

from conftest import ROOT

LABEL_PARTS = ("observational", "not a causal estimate")


def _load(project, rel):
    with open(os.path.join(project, rel), encoding="utf-8") as f:
        return json.load(f)


def _raw():
    return pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), usecols=["c27__13", "MM", "population_wt"], low_memory=False)


def test_descriptives_reproduce_from_the_raw_data(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/tin_mobile_money.json")
    df = _raw()
    tin = df["c27__13"].astype(str).str.strip().str.lower().eq("yes").to_numpy()
    mm = df["MM"].astype(str).str.strip().eq("MM").to_numpy()
    w = pd.to_numeric(df["population_wt"]).to_numpy(float)
    assert len(df) == 9915
    rows = {r["group"]: r for r in res["descriptives"]["tin_rate_by_group"]}
    assert rows["All adults (16+)"]["n_unweighted_base"] == 9915
    for name, m in (("All adults (16+)", np.ones(len(df), bool)), ("Mobile-money users", mm), ("Non-users of mobile money", ~mm)):
        r = rows[name]
        want = w[m & tin].sum() / w[m].sum() * 100
        assert abs(r["tin_rate_pct"] - want) < 1e-6, name
        assert r["n_unweighted_base"] == int(m.sum())
        num = int((m & tin).sum())
        if num < 10:                                    # disclosure rule: numerator withheld, estimate flagged
            assert r.get("low_precision") is True and r["n_unweighted_numerator"] is None, name
        else:
            assert r["n_unweighted_numerator"] == num, name
    share = res["descriptives"]["share_of_tin_holders_using_mobile_money"]
    assert abs(share["share_of_tin_holders_using_mm_pct"] - w[tin & mm].sum() / w[tin].sum() * 100) < 1e-6
    assert share["n_unweighted_base"] == int(tin.sum())


def test_model_converges_and_the_marginal_effect_is_reported_with_a_ci(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/tin_mobile_money.json")
    diag = res["model_diagnostics"]
    assert diag["primary_firth"]["converged"] is True
    assert diag["primary_firth"]["max_abs_coefficient"] < 15                     # no separation blow-up under the Firth penalty
    ame = res["average_marginal_effect_of_mobile_money"]
    lo, hi = ame["ci95_percentage_points"]
    assert lo < ame["percentage_points"] < hi
    assert ame["percentage_points"] > 0 and lo > 0
    assert res["odds_ratio_mobile_money"]["primary"] > 1
    assert res["headline_model"] in ("primary", "with region")


def test_everything_is_labelled_observational(pipeline_run):
    res = _load(pipeline_run, "outputs/stats/tin_mobile_money.json")
    for part in LABEL_PARTS:
        assert part in res["label"]
        assert part in res["average_marginal_effect_of_mobile_money"]["label"]
    with open(os.path.join(pipeline_run, "outputs", "tables", "tin_mobile_money.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(all(p in r["label"] for p in LABEL_PARTS) for r in rows)
    # disclosure: no numerator below 10 is published
    for r in rows:
        if r["n_unweighted_numerator"]:
            assert int(float(r["n_unweighted_numerator"])) >= 10, r


def test_the_simulated_causal_estimates_are_gone(pipeline_run):
    model = _load(pipeline_run, "outputs/stats/economic_model.json")
    for retired in ("causal_inference", "ml_segmentation"):
        assert retired not in model
    code = ""
    for root, _, files in os.walk(os.path.join(ROOT, "src")):
        if "imported" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                code += open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
    for pattern in (r"def run_causal_inference_analysis", r"run_causal_inference_analysis\(", r"A\(\"psm\.", r"A\(\"did\.", r"A\(\"sc\.",
                    r"true_mm_effect\s*=", r"def build_segmentation_model"):
        assert not re.search(pattern, code), pattern
