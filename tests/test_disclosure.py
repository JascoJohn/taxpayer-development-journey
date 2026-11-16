"""D1: one disclosure rule for every published output (config.yaml disclosure:).

  base < min_base                  -> estimate and count are null, "suppressed": true, "reason": "base < 10"
  base >= min_base, numerator < 10 -> estimate kept, "low_precision": true, numerator withheld
"""
import csv
import importlib
import json
import os
import re
import sys

import pandas as pd
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401

MIN_BASE, LOW_NUM = 10, 10
ID_KEYS = {"decile", "group", "age_from", "age_to", "decile_from", "decile_to", "reason", "region", "activity", "model", "term", "section"}
BASE_KEYS = {"respondent_count", "registered_respondent_count", "n_unweighted", "n_unweighted_base", "n_unweighted_cell", "base"}
NUMERATOR_KEYS = {"n_unweighted_numerator", "n_tin_unweighted", "tin_holders_unweighted", "unweighted_numerator"}


def _cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _published_json(project):
    for d in ("data/interim", "data/processed", "outputs/stats"):
        for root, _, files in os.walk(os.path.join(project, d)):
            for f in sorted(files):
                if f.endswith(".json") and f != "run_meta.json":
                    p = os.path.join(root, f)
                    with open(p, encoding="utf-8") as fh:
                        yield os.path.relpath(p, project).replace(os.sep, "/"), json.load(fh)


def _walk(x, path):
    if isinstance(x, dict):
        yield path, x
        for k, v in x.items():
            yield from _walk(v, path + "/" + str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _walk(v, path + "[%d]" % i)


def test_thresholds_come_from_config_and_the_dashboard_uses_them():
    d = _cfg()["disclosure"]
    assert d == {"min_base": MIN_BASE, "low_precision_numerator": LOW_NUM}
    import disclosure
    assert disclosure.MIN_BASE == d["min_base"] and disclosure.LOW_PRECISION_NUMERATOR == d["low_precision_numerator"]
    dash = os.path.join(ROOT, "dashboard")
    sys.path.insert(0, dash)
    try:
        adapters = importlib.import_module("tdj_lib.benchmark_adapters")
    finally:
        sys.path.remove(dash)
    assert adapters.MIN_N_FOR_ANY_ESTIMATE == d["min_base"]
    src = open(os.path.join(dash, "tdj_lib", "benchmark_adapters.py"), encoding="utf-8").read()
    assert not re.search(r"MIN_N_FOR_ANY_ESTIMATE\s*=\s*\d", src)           # no typed copy of the threshold


def test_no_published_cell_with_a_small_base_carries_an_estimate(pipeline_run):
    problems = []
    n_suppressed = n_flagged = 0
    for rel, doc in _published_json(pipeline_run):
        for path, cell in _walk(doc, ""):
            if cell.get("suppressed") is True:
                n_suppressed += 1
                if cell.get("reason") != "base < %d" % MIN_BASE:
                    problems.append((rel, path, "reason"))
                for k, v in cell.items():
                    if k not in ID_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                        problems.append((rel, path, k, v))
            for k in BASE_KEYS & set(cell):
                v = cell[k]
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v < MIN_BASE:
                    problems.append((rel, path, k, v))
            for k in NUMERATOR_KEYS & set(cell):
                v = cell[k]
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v < LOW_NUM:
                    problems.append((rel, path, k, v))
            if cell.get("low_precision") is True:
                n_flagged += 1
                if not cell.get("low_precision_fields") and "value" not in cell:         # a flagged cell names its fields (or is a flagged leaf)
                    problems.append((rel, path, "low_precision without fields"))
    assert problems == [], problems[:10]
    assert n_suppressed > 0 and n_flagged > 0                                 # the rule is actually being applied


def test_published_tables_follow_the_rule(pipeline_run):
    for name in ("tin_by_segment.csv", "ilfs_informality.csv", "tin_mobile_money.csv", "targeting_deciles.csv"):
        with open(os.path.join(pipeline_run, "outputs", "tables", name), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            for k in BASE_KEYS | NUMERATOR_KEYS | {"tin_holders_unweighted"}:
                if k in r and r[k] not in ("", None):
                    thr = MIN_BASE if k in BASE_KEYS else LOW_NUM
                    assert float(r[k]) >= thr, (name, k, r[k])
            if str(r.get("suppressed", "")).lower() == "true":
                est = [c for c in ("estimate", "estimate_pct", "tin_rate_pct", "mean_predicted_pct", "observed_tin_rate_pct") if c in r]
                assert all(r[c] == "" for c in est), (name, r)


def test_region_activity_and_benchmark_cells_match_the_raw_counts(pipeline_run):
    """Bases are recomputed from the raw FinScope file: suppressed exactly when the unweighted base is below 10; registration
    numerators below 10 are flagged."""
    df = pd.read_csv(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), usecols=["reg_name", "IncomeMain", "D6_4a"], low_memory=False)
    df["reg_name"] = df["reg_name"].astype(str).str.strip()
    df["IncomeMain"] = df["IncomeMain"].astype(str).str.strip()
    base = pd.crosstab(df["reg_name"], df["IncomeMain"])
    yes = pd.crosstab(df.loc[df["D6_4a"].astype(str).str.strip().str.lower() == "yes", "reg_name"], df.loc[df["D6_4a"].astype(str).str.strip().str.lower() == "yes", "IncomeMain"])
    with open(os.path.join(pipeline_run, "data", "processed", "finscope_region_activity.json"), encoding="utf-8") as f:
        ra = json.load(f)["rows"]
    with open(os.path.join(pipeline_run, "data", "processed", "finscope_active_benchmark.json"), encoding="utf-8") as f:
        ab = json.load(f)["rows"]
    for name, rows in (("region_activity", ra), ("benchmark", ab)):
        for r in rows:
            n = int(base.loc[r["region"]].get(r["activity"], 0))
            assert bool(r.get("suppressed")) == (n < MIN_BASE), (name, r["region"], r["activity"], n)
            if not r.get("suppressed"):
                assert r["respondent_count"] == n
    for r in ab:
        if r.get("suppressed"):
            continue
        k = int(yes.loc[r["region"]].get(r["activity"], 0)) if r["region"] in yes.index else 0
        reg_fields = {"registered_pct", "registered_respondent_count"}
        if r.get("registered_pct") is None:
            assert reg_fields <= set(r.get("suppressed_fields", [])), r
        elif k < LOW_NUM:
            assert "registered_pct" in r.get("low_precision_fields", []), (r["region"], r["activity"], k)
        else:
            assert "registered_pct" not in r.get("low_precision_fields", []), (r["region"], r["activity"], k)


def test_region_tin_rates_and_summary_counts(pipeline_run):
    with open(os.path.join(pipeline_run, "data", "interim", "finscope_summary.json"), encoding="utf-8") as f:
        s = json.load(f)
    flagged = [k for k, v in s["geography"]["by_region"].items() if v.get("low_precision")]
    assert flagged                                                              # thin regions are flagged, not hidden
    for k, v in s["geography"]["by_region"].items():
        assert v["tin_rate_pct"] is not None, k                                  # base >= 10 for every region: estimate kept
    for k, v in s["registration_barriers"].items():
        if isinstance(v, dict) and v.get("suppressed"):
            assert v["count"] is None and v["pct"] is None
