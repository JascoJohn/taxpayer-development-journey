"""E5: agent trust, morale and income come from aggregate cell distributions of Afrobarometer and ILFS; nothing is linked per person."""
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

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))


def _j(project, name):
    with open(os.path.join(project, "data", "processed", name), encoding="utf-8") as f:
        return json.load(f)


def _arrays(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _arrays(v, path + "/" + str(k))
    elif isinstance(x, list):
        yield path, x
        for i, v in enumerate(x):
            yield from _arrays(v, path + "[%d]" % i)


def test_the_files_are_aggregates_with_no_respondent_rows(pipeline_run):
    for name in ("agent_trust_morale.json", "agent_income.json", "afrobarometer_morale.json"):
        res = _j(pipeline_run, name)
        for path, arr in _arrays(res):
            assert len(arr) <= 200, (name, path, len(arr))                      # no array comes near a respondent-level table (<= 99 percentiles, <= 190 estimate rows)
        text = json.dumps(res)
        for banned in ("RESPNO", "HHNUMBER", "INTERV_NUMBER", "Q01_PERSONNO", "population_wt", "respondent_id"):
            assert banned not in text, (name, banned)
    tm = _j(pipeline_run, "agent_trust_morale.json")
    assert len(tm["cells"]) == 12 and tm["no_linkage"]
    for c in tm["cells"]:
        assert c["n_unweighted"] >= 10
        for key in ("trust", "morale"):
            assert sum(c[key]["weighted_shares_by_level"]) == pytest.approx(1.0, abs=1e-9)
            assert c[key]["beta_a"] > 0 and c[key]["beta_b"] > 0 and 0 <= c[key]["mean"] <= 1
    inc = _j(pipeline_run, "agent_income.json")
    assert len(inc["age_bands"]) == 6 and inc["self_employment_exists"] is True
    for b in inc["age_bands"]:
        p = np.array(b["annual_earnings_tzs_percentiles_among_earners"])
        assert len(p) == 99 and np.all(np.diff(p) >= 0) and p[0] > 0
        assert 0 <= b["share_without_earnings_pct"] <= 100 and b["n_unweighted_earners"] >= 10
    nat = np.array(inc["national"]["annual_earnings_tzs_percentiles_all_persons_16plus"])
    assert len(nat) == 99 and np.all(np.diff(nat) >= 0)


def test_the_income_cells_reproduce_from_ilfs(pipeline_run):
    inc = _j(pipeline_run, "agent_income.json")
    c = CFG["agent_inputs"]["income"]
    df, _ = pyreadstat.read_sav(paths.ILFS_SAV, usecols=[c["age"], c["weight"], c["employee_cash"], c["self_net"], c["self_period"], c["agri_net"], c["agri_period"]], apply_value_formats=False)
    df = df[(df[c["age"]] >= 16) & (df[c["age"]] <= 97)]
    w = df[c["weight"]].to_numpy(float)

    def monthly(col, per):
        v = np.where(df[col].fillna(0).to_numpy(float) > 0, df[col].fillna(0).to_numpy(float), 0.0)
        return v * np.where(df[per].to_numpy(float) == 1, 52.0 / 12.0, 1.0)
    cash = np.where(df[c["employee_cash"]].fillna(0).to_numpy(float) > 0, df[c["employee_cash"]].fillna(0).to_numpy(float), 0.0)
    annual = (cash + monthly(c["self_net"], c["self_period"]) + monthly(c["agri_net"], c["agri_period"])) * 12
    age = df[c["age"]].to_numpy(float)
    b = inc["age_bands"][1]                                                      # 25-34
    m = (age >= b["age_from"]) & (age <= b["age_to"])
    assert b["n_unweighted_persons"] == int(m.sum())
    assert b["share_without_earnings_pct"] == pytest.approx(float((1 - np.average(annual[m] > 0, weights=w[m])) * 100), abs=1e-6)
    e = m & (annual > 0)
    assert b["mean_annual_earnings_tzs_among_earners"] == pytest.approx(float(np.average(annual[e], weights=w[e])), rel=1e-9)
    assert inc["variables"]["employees_cash_earnings"]["variable"] == "Q86B_CASH" and "inferred" in inc["variables"]["employees_cash_earnings"]["reference_period"]


def test_the_simulation_reads_the_aggregate_files_and_the_constants_are_data(pipeline_run):
    import economic_model as em
    for key in ("agents.trust_beta_a", "agents.trust_beta_b", "agents.morale_beta_a", "agents.morale_beta_b", "agents.income_lognormal_sigma", "agents.income_scale_tzs"):
        e = assumptions.entry(key)
        assert e["basis"] == "DATA" and "value" not in e and e["from"].startswith("data/processed/"), key
    assert assumptions.entry("agents.non_earners_zero_income")["basis"] == "ASSUMPTION"
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    for gone in ('A("agents.trust_beta', 'A("agents.morale_beta', 'A("agents.income_lognormal_sigma")', 'A("agents.income_scale_tzs")', "rng.beta("):
        assert gone not in code, gone
    rng = np.random.default_rng(1)
    n = 60_000
    ages = rng.integers(16, 80, n)
    urban = rng.random(n) < 0.4
    income, trust, morale, rank = em.draw_agent_inputs(ages, urban, rng)
    tm = json.load(open(paths.AGENT_TRUST_MORALE, encoding="utf-8"))["cells"]
    cell = next(c for c in tm if c["band_index"] == 1 and c["urban"])
    sel = (ages >= 25) & (ages <= 34) & urban
    assert trust[sel].mean() == pytest.approx(cell["trust"]["mean"], abs=0.02)
    assert morale[sel].mean() == pytest.approx(cell["morale"]["mean"], abs=0.02)
    inc = json.load(open(paths.AGENT_INCOME, encoding="utf-8"))["age_bands"][1]
    sel2 = (ages >= 25) & (ages <= 34)
    assert (income[sel2] == 0).mean() == pytest.approx(inc["share_without_earnings_pct"] / 100, abs=0.02)
    assert np.median(income[sel2 & (income > 0)]) == pytest.approx(inc["annual_earnings_tzs_percentiles_among_earners"][49], rel=0.05)
    assert rank.min() >= 0 and rank.max() <= 1 and np.corrcoef(income, rank)[0, 1] > 0.5
    assert set(np.round(np.unique(trust), 5)) <= {0.0, 0.33333, 0.66667, 1.0}                  # the four answer levels of Q41J (published rounded to 6 decimals)


def test_the_data_terms_state_the_no_linkage_rule_for_agent_inputs():
    text = open(os.path.join(ROOT, "docs", "data_terms.md"), encoding="utf-8").read()
    assert "clause 4" in text.lower() and "agent_income.json" in text and "agent_trust_morale.json" in text and "no record linkage" in text.lower()
