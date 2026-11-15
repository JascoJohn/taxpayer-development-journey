"""E5 - agent trust, morale and income from data (aggregate calibration only).

Replaces the simulated inputs of the agent-based and tier-migration simulations:
  trust, morale  EMPIRICAL weighted distributions per cell (age band x urban/rural) on Afrobarometer Round 8 Tanzania respondents:
                 trust = Q41J (trust in the tax/revenue office, rescaled 0-1, four levels); morale = Q76e-tan (good citizens should
                 pay the taxes they owe: never 0, only if they choose 0.5, always 1, three levels). One item each, no composite, no
                 weights. The method-of-moments Beta fit is published beside it as a check and is NOT used: both items are ordinal with
                 three or four levels, a Beta fits them poorly (morale shapes below 0.3, U-shaped, with the middle level lost), so agents
                 draw a level with the weighted cell shares.
  income         percentile distributions of annual EARNINGS per age band, ILFS 2024 (persons 16+): cash earnings of employees +
                 net income from self-employment + net income from agriculture, converted to TZS per year, with the share of persons
                 with no earnings (they stay in the population with zero income). A national distribution (all persons 16+) gives
                 each agent's income RANK, which replaces the former saturating income scale.

Only AGGREGATE cell distributions are combined across the two surveys (agents take the age band and urban/rural residence of a FinScope cell
and draw from the cell distributions published here). No respondent is linked across surveys (data terms, clause 4); no respondent-level row
is written. The disclosure rule applies (cells with fewer than min_base respondents are not published).

ILFS has no urban/rural variable (the file carries region and enumeration area only), so income varies by age band, not by residence.

Outputs: data/processed/agent_trust_morale.json, data/processed/agent_income.json
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pyreadstat
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
import afrobarometer_morale as afro

CFG = paths.CFG["agent_inputs"]
LABEL = "aggregate cell distributions from survey data; no respondent-level rows; no record linkage across surveys"


def weighted_quantiles(x, w, probs):
    order = np.argsort(x)
    xs, ws = x[order], w[order]
    cum = (np.cumsum(ws) - 0.5 * ws) / ws.sum()
    return np.interp(probs, cum, xs)


def beta_moments(x, w):
    """Weighted mean and variance and the method-of-moments Beta shape parameters."""
    m = float(np.average(x, weights=w))
    v = float(np.average((x - m) ** 2, weights=w))
    k = m * (1 - m) / v - 1.0 if v > 0 else float("inf")
    return m, v, k * m, k * (1 - m)


# ------------------------------------------------------------------ trust and morale
def trust_morale(sav_path=None):
    df, _ = afro.load(sav_path)
    w = df[afro.CFG["weight"]].to_numpy(float)
    urban = (df["URBRUR"] == 1).to_numpy()
    items = CFG["trust_morale"]
    cells = []
    for name, band_mask in afro.age_band_masks(df):
        lo = int(name.split("-")[0].rstrip("+"))
        for is_urban in (True, False):
            m = band_mask & (urban == is_urban)
            cell = {"age_band": name, "band_index": [n for n, _ in afro.age_band_masks(df)].index(name), "age_from": lo, "urban": bool(is_urban), "n_unweighted": int(m.sum())}
            if disclosure.is_suppressed(int(m.sum())):
                cells.append(disclosure.suppress(cell, []))
                continue
            for key, spec in items.items():
                x = df[spec["variable"]].to_numpy(float)
                valid = m & (x >= spec["valid_min"]) & (x <= spec["valid_max"])
                score = (x[valid] - spec["valid_min"]) / (spec["valid_max"] - spec["valid_min"])
                mean, var, a, b = beta_moments(score, w[valid])
                levels = sorted(set(np.round(score, 6)))
                shares = [float(np.average(np.isclose(score, lv), weights=w[valid])) for lv in levels]
                # fit check: empirical weighted CDF at the midpoints between the discrete levels against the Beta CDF there
                mids = [(levels[i] + levels[i + 1]) / 2 for i in range(len(levels) - 1)]
                emp = [float(np.average(score <= t, weights=w[valid])) for t in mids]
                fit = [float(stats.beta.cdf(t, a, b)) for t in mids]
                cell[key] = {"variable": spec["variable"], "n_unweighted_valid": int(valid.sum()), "mean": mean, "variance": var, "beta_a": a, "beta_b": b,
                             "levels": [float(l) for l in levels], "weighted_shares_by_level": shares,
                             "fit_check_max_abs_cdf_difference": float(max(abs(e - f) for e, f in zip(emp, fit))) if mids else 0.0}
            cells.append(cell)
    return {"label": LABEL, "type": "COMPUTED (survey data), aggregates only",
            "source": "Afrobarometer Round 8 Tanzania 2021 (%s), weight %s; see data/processed/afrobarometer_morale.json" % (os.path.basename(sav_path or paths.AFROBAROMETER_SAV), afro.CFG["weight"]),
            "method": "EMPIRICAL cell distribution (weighted shares of each answer level, used by the simulations); a method-of-moments Beta (beta_a, beta_b from the weighted mean and variance) is published as a check with its maximum CDF difference and is not used",
            "items": {k: {"variable": v["variable"], "rescale": v["rescale"], "meaning": v["meaning"]} for k, v in items.items()},
            "age_band_note": "the 16-24 agent band is calibrated on respondents aged 18-24 (Afrobarometer interviews adults 18+)",
            "no_linkage": "cells only; no respondent is linked to a FinScope or ILFS record (data terms, clause 4)", "cells": cells}


# ------------------------------------------------------------------ income
def income(sav_path=None):
    c = CFG["income"]
    cols = [c["age"], c["weight"], c["employee_cash"], c["self_net"], c["self_period"], c["agri_net"], c["agri_period"]]
    df, meta = pyreadstat.read_sav(sav_path or paths.ILFS_SAV, usecols=cols, apply_value_formats=False)
    labels = dict(zip(meta.column_names, meta.column_labels))
    age = df[c["age"]].to_numpy(float)
    ok = (age >= 16) & (age <= 97)
    df = df[ok].reset_index(drop=True)
    age = df[c["age"]].to_numpy(float)
    w = df[c["weight"]].to_numpy(float)

    def monthly(col, period_col):
        v = df[col].fillna(0).to_numpy(float)
        v = np.where(v > 0, v, 0.0)
        per = df[period_col].to_numpy(float)
        factor = np.where(per == 1, 52.0 / 12.0, 1.0)         # week -> month (52/12); month stays
        return v * factor
    cash = np.where(df[c["employee_cash"]].fillna(0).to_numpy(float) > 0, df[c["employee_cash"]].fillna(0).to_numpy(float), 0.0)
    self_ = monthly(c["self_net"], c["self_period"])
    agri = monthly(c["agri_net"], c["agri_period"])
    annual = (cash + self_ + agri) * 12.0
    earner = annual > 0
    probs = np.arange(1, 100) / 100.0
    bands = []
    cfg_bands = paths.CFG["targeting"]["agent_age_bands"]
    for i, (lo, hi) in enumerate(cfg_bands):
        m = (age >= lo) & ((age <= hi) if i < len(cfg_bands) - 1 else np.ones(len(age), bool))
        e = m & earner
        cell = {"band_index": i, "age_from": lo, "age_to": hi, "n_unweighted_persons": int(m.sum()), "n_unweighted_earners": int(e.sum())}
        if disclosure.is_suppressed(int(m.sum())) or disclosure.is_suppressed(int(e.sum())):
            bands.append(disclosure.suppress(cell, ["n_unweighted_persons", "n_unweighted_earners"]))
            continue
        cell["share_without_earnings_pct"] = float((1 - np.average(earner[m], weights=w[m])) * 100)
        cell["share_with_employee_cash_pct_of_earners"] = float(np.average(cash[e] > 0, weights=w[e]) * 100)
        cell["share_with_self_employment_income_pct_of_earners"] = float(np.average(self_[e] > 0, weights=w[e]) * 100)
        cell["share_with_agricultural_income_pct_of_earners"] = float(np.average(agri[e] > 0, weights=w[e]) * 100)
        cell["mean_annual_earnings_tzs_among_earners"] = float(np.average(annual[e], weights=w[e]))
        cell["annual_earnings_tzs_percentiles_among_earners"] = [float(x) for x in weighted_quantiles(annual[e], w[e], probs)]
        bands.append(cell)
    nat_all = [float(x) for x in weighted_quantiles(annual, w, probs)]
    nat = {"n_unweighted_persons": int(len(age)), "n_unweighted_earners": int(earner.sum()), "share_without_earnings_pct": float((1 - np.average(earner, weights=w)) * 100),
           "annual_earnings_tzs_percentiles_all_persons_16plus": nat_all, "percentile_grid": [int(p * 100) for p in probs]}
    return {"label": LABEL, "type": "COMPUTED (survey data), aggregates only",
            "source": "ILFS 2024 (NBS) anonymised microdata, weight %s, persons aged 16-97" % c["weight"],
            "variables": {"employees_cash_earnings": {"variable": c["employee_cash"], "label_in_file": labels[c["employee_cash"]],
                                                       "reference_period": "per month: the file's label is cut off after 'during the last'; the values (mean TZS 433,694, median 250,000 among those above zero) match the monthly income of paid employees in the ILFS 2020/21 report (mean TZS 390,992, median 300,000), so the period is taken to be the month (inferred, not stated)"},
                          "self_employment_net_income": {"variable": c["self_net"], "period_variable": c["self_period"], "label_in_file": labels[c["self_net"]],
                                                          "reference_period": "week or month as recorded in the period variable (1 = week, 2 = month); weekly amounts are converted with 52/12", "kind": "net of the expenses of the earned income (Q87C)"},
                          "agricultural_net_income": {"variable": c["agri_net"], "period_variable": c["agri_period"], "label_in_file": labels[c["agri_net"]],
                                                       "reference_period": "week or month (period variable); weekly amounts converted with 52/12", "kind": "net of expenses (Q88C)"}},
            "definition": "annual earnings = 12 x (cash earnings from paid employment + net self-employment income + net agricultural income), each converted to a month; a person with none of the three has zero earnings. Payments in kind (Q86BIN_KIND) are excluded (not cash).",
            "self_employment_exists": True,
            "non_earners": "persons aged 16+ with no earnings (students, home-makers, the unemployed, unpaid helpers) are part of the population with zero income; their share is published per cell and agents draw zero with that probability. This is an assumption about how non-earners enter the simulation (they cannot generate income-tax revenue), recorded as an ASSUMPTION in the register.",
            "no_urban_rural": "the ILFS file has no urban/rural variable, so cells are age bands only",
            "percentile_use": "agents draw a percentile uniformly in 1-99 and interpolate between published percentiles; values below the 1st and above the 99th percentile are not represented (the mean of the draws is slightly below the published mean)",
            "age_bands": bands, "national": nat}


def run_agent_inputs(sav_afro=None, sav_ilfs=None, trust_path=None, income_path=None):
    trust_path = trust_path or paths.AGENT_TRUST_MORALE
    income_path = income_path or paths.AGENT_INCOME
    tm, inc = trust_morale(sav_afro), income(sav_ilfs)
    for p, obj in ((trust_path, tm), (income_path, inc)):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
    c0 = tm["cells"][0]
    print("  agent inputs: %d trust/morale cells (e.g. %s urban=%s trust mean %.2f, morale mean %.2f); income: %d age bands, %.1f%% of persons 16+ without earnings" % (
        len(tm["cells"]), c0["age_band"], c0["urban"], c0["trust"]["mean"], c0["morale"]["mean"], len(inc["age_bands"]), inc["national"]["share_without_earnings_pct"]))
    return tm, inc


if __name__ == "__main__":
    run_agent_inputs()
