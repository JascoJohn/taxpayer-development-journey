"""W5 - TIN holding by lifecycle stage, from ONE stratification and ONE weight.

Reads FinScope Tanzania 2023 (data/raw/finscope/FinScope.csv) and computes, overall and for each of the five
adult stages (Entry, Active, Enterprise, Asset, Legacy):

  * the weighted TIN rate (c27__13 = 'Yes', weight population_wt),
  * the unweighted n and the unweighted number of TIN holders,
  * the weighted population and TIN holders,
  * design-based (Taylor-linearised) 95% confidence intervals (see survey_design.py).

The stage assignment, the weight and the TIN mask are the single definitions in finscope_segments.py.
The five stages are mutually exclusive and exhaustive for respondents aged 16+, so the population-weighted
average of the stage rates equals the overall rate by construction; this script checks it in code and
raises ReconciliationError if it does not hold.

Survey design: FinScope.csv has no variable called strata, psu or cluster. It does carry the sampling-frame
geography: region (reg_code), urban/rural cluster type (clustertype), district, ward and enumeration-area codes.
Enumeration-area codes are only unique within a ward, so the primary sampling unit is rebuilt as the composite
reg_code | dist_code | ward_code1 | ea_code (666 EAs, 15 respondents each in all but a few), and strata as
region x cluster type (61 strata, 2-35 PSUs each). This is a RECONSTRUCTED design (FSDT does not document it in the
files held), so the confidence intervals are labelled "reconstructed design" wherever they are shown.

Outputs: outputs/tables/tin_by_segment.csv, outputs/stats/tin_reconciliation.json.
"""

import csv
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
from finscope_segments import (ADULT_STAGES, SEED_AGE_MAX, SEED_AGE_MIN, WEIGHT_VAR, lifecycle_stage,
                               survey_weights, tin_holder_mask)
from survey_design import ci95, design_df, linearised_ratio

STAGE_LABELS = {"entry": "Entry", "active": "Active", "enterprise": "Enterprise", "asset": "Asset", "legacy": "Legacy"}
STAGE_DEFINITIONS = {
    "entry": "age %d-24" % (SEED_AGE_MAX + 1),
    "active": "age 25-44, not a business owner (BusO != 'Business owners')",
    "enterprise": "age 25-64, business owner (BusO == 'Business owners')",
    "asset": "age 45-64, not a business owner",
    "legacy": "age 65+",
}
TOLERANCE = 1e-9          # the identity is exact up to floating-point error
DESIGN_COLUMNS = ["reg_code", "dist_code", "ward_code1", "ea_code", "clustertype"]

# values quoted in the submitted report (rounded, per cent) - compared in the reconciliation file
REPORT_VALUES_PCT = {"overall": 3.8, "active": 4.6, "enterprise": 9.7}


class ReconciliationError(RuntimeError):
    """The population-weighted average of the stage TIN rates differs from the overall rate."""


def reconstruct_design(df):
    """(strata, psu, description) from the sampling-frame columns; (None, None, text) if they are missing."""
    missing = [c for c in DESIGN_COLUMNS if c not in df.columns]
    if missing:
        return None, None, "design variables missing (%s): weighted rates and unweighted n only" % ", ".join(missing)
    psu = df[["reg_code", "dist_code", "ward_code1", "ea_code"]].astype(str).agg("|".join, axis=1)
    strata = df["reg_code"].astype(str) + "|" + df["clustertype"].astype(str)
    return strata, psu, ("RECONSTRUCTED design: PSU = enumeration area (reg_code|dist_code|ward_code1|ea_code), "
                         "strata = region x urban/rural cluster type (reg_code|clustertype); "
                         "linearised variance, logit CI, Student-t")


def _row(name, label, definition, mask, tin, w, n_total_w, strata, psu):
    n = int(mask.sum())
    n_tin = int((mask & tin).sum())
    pop = float(w[mask].sum())
    tin_w = float(w[mask & tin].sum())
    rate = tin_w / pop if pop > 0 else float("nan")
    row = {"segment": name, "label": label, "definition": definition, "n_unweighted": n,
           "tin_holders_unweighted": n_tin, "population_weighted": pop,
           "population_share_pct": pop / n_total_w * 100.0, "tin_holders_weighted": tin_w,
           "tin_rate_pct": rate * 100.0, "se_pct": None, "ci95_low_pct": None, "ci95_high_pct": None}
    if strata is not None:
        num = (mask & tin).to_numpy(dtype=float)
        den = mask.to_numpy(dtype=float)
        r, se, n_psu, n_str, lonely = linearised_ratio(num, den, w.to_numpy(), strata.to_numpy(), psu.to_numpy())
        lo, hi = ci95(r, se, n_psu, n_str)
        row.update(se_pct=se * 100.0, ci95_low_pct=lo * 100.0, ci95_high_pct=hi * 100.0)
        row["_design"] = (n_psu, n_str, lonely)
    return row


def compute(df):
    """Returns (rows, reconciliation dict) for a FinScope data frame."""
    w = survey_weights(df)
    tin = tin_holder_mask(df)
    stage = pd.Series(lifecycle_stage(df), index=df.index)
    total_w = float(w.sum())
    strata, psu, design_text = reconstruct_design(df)

    rows = [_row("overall", "All adults (16+)", "every respondent", pd.Series(True, index=df.index), tin, w, total_w, strata, psu)]
    for s in ADULT_STAGES:
        rows.append(_row(s, STAGE_LABELS[s], STAGE_DEFINITIONS[s], stage == s, tin, w, total_w, strata, psu))
    unassigned = ~stage.isin(ADULT_STAGES)
    if unassigned.any():
        rows.append(_row("unassigned", "Not in an adult stage", "age outside the adult stages", unassigned, tin, w, total_w, strata, psu))

    stage_rows = [r for r in rows if r["segment"] != "overall"]
    overall = rows[0]
    avg = sum(r["population_weighted"] / total_w * r["tin_rate_pct"] for r in stage_rows if r["population_weighted"] > 0)
    diff = avg - overall["tin_rate_pct"]
    rec = {
        "identity": "sum over stages of (stage population / total population) x stage TIN rate = overall TIN rate",
        "weight_variable": WEIGHT_VAR,
        "tin_variable": "c27__13 == 'Yes'",
        "stage_assignment": "finscope_segments.lifecycle_stage (single definition); seed band %d-%d (config.yaml seed_age_band)" % (SEED_AGE_MIN, SEED_AGE_MAX),
        "n_respondents": int(len(df)),
        "weighted_population": total_w,
        "overall_tin_rate_pct": overall["tin_rate_pct"],
        "population_weighted_average_of_stage_rates_pct": avg,
        "difference_pct_points": diff,
        "tolerance_pct_points": TOLERANCE,
        "identity_holds": bool(abs(diff) <= TOLERANCE),
        "unassigned_respondents": int(unassigned.sum()),
        "weights_sum_equal_across_stages": bool(abs(sum(r["population_weighted"] for r in stage_rows) - total_w) < 1e-6),
        "stage_rates_pct": {r["segment"]: r["tin_rate_pct"] for r in stage_rows},
        "stage_population_share_pct": {r["segment"]: r["population_share_pct"] for r in stage_rows},
        "design": design_text,
    }
    if strata is not None:
        n_psu, n_str, lonely = overall["_design"]
        rec["design_summary"] = {"n_psu": n_psu, "n_strata": n_str, "strata_with_one_psu": lonely,
                                 "degrees_of_freedom": design_df(n_psu, n_str)}
    else:
        rec["design_summary"] = None
    if not rec["identity_holds"] or rec["unassigned_respondents"] or not rec["weights_sum_equal_across_stages"]:
        raise ReconciliationError(
            "TIN reconciliation failed: weighted average of stage rates %.12f%% vs overall %.12f%% (difference %.3e); "
            "unassigned respondents: %d" % (avg, overall["tin_rate_pct"], diff, rec["unassigned_respondents"]))
    rec["report_values_pct"] = {
        k: {"report": v, "computed_rounded_1dp": round((overall if k == "overall" else next(r for r in rows if r["segment"] == k))["tin_rate_pct"], 1)}
        for k, v in REPORT_VALUES_PCT.items()}
    return rows, rec


def write_outputs(rows, rec, table_path, json_path):
    os.makedirs(os.path.dirname(table_path), exist_ok=True)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    cols = ["segment", "label", "definition", "n_unweighted", "tin_holders_unweighted", "population_weighted",
            "population_share_pct", "tin_holders_weighted", "tin_rate_pct", "se_pct", "ci95_low_pct", "ci95_high_pct", "low_precision", "suppressed"]
    # disclosure rule (config.yaml disclosure): base = unweighted n of the stage, numerator = unweighted TIN holders
    rows = [disclosure.apply_to_row(dict(r), "n_unweighted", "tin_holders_unweighted", ["tin_rate_pct", "se_pct", "ci95_low_pct", "ci95_high_pct"],
                                    ["population_weighted", "population_share_pct", "tin_holders_weighted"]) for r in rows]
    with open(table_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in rows:
            out = []
            for c in cols:
                v = r.get(c, False if c in ("low_precision", "suppressed") else None)
                if isinstance(v, float):
                    v = "%.4f" % v if c.endswith("_pct") else "%.2f" % v
                out.append("" if v is None else v)
            wr.writerow(out)
    rec = dict(rec)
    rec["table"] = paths.CFG["files"]["tin_by_segment_csv"]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)


def run_tin_by_segment(csv_path=None, table_path=None, json_path=None):
    csv_path = csv_path or paths.FINSCOPE_CSV
    table_path = table_path or paths.TIN_BY_SEGMENT_CSV
    json_path = json_path or paths.TIN_RECONCILIATION
    df = pd.read_csv(csv_path, low_memory=False)
    rows, rec = compute(df)
    write_outputs(rows, rec, table_path, json_path)
    print("  overall TIN rate %.3f%%; identity holds (difference %.2e pp)" % (rec["overall_tin_rate_pct"], rec["difference_pct_points"]))
    for r in rows:
        ci = "" if r["ci95_low_pct"] is None else "  95%% CI %.2f-%.2f" % (r["ci95_low_pct"], r["ci95_high_pct"])
        print("  %-10s n=%5d  TIN holders=%4d  rate %.3f%%%s" % (r["segment"], r["n_unweighted"], r["tin_holders_unweighted"], r["tin_rate_pct"], ci))
    return rec


if __name__ == "__main__":
    run_tin_by_segment()
