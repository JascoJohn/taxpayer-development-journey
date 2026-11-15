"""W10 - tax morale from Afrobarometer Round 8, Tanzania (components only; no composite).

Source: Afrobarometer Round 8 Tanzania respondent-level file (n = 2,398 adults 18+, interviews 23 Feb - 25 Mar 2021), SPSS format, read with
pyreadstat; the raw file is not published (data/raw/ is git-ignored). Provenance, terms and citation: data/raw/SOURCES.csv.

What is published: weighted percentages with 95% confidence intervals for each COMPONENT behind the report's composite, one row per
indicator, for all adults, urban and rural, and age bands. The report's 59.8% composite (assumed weights 30/35/20/15) is retired and is
not recomputed; the WVS 61.8% stays removed. No respondent-level row is ever written.

Estimation
  weights    withinwt_hh (Afrobarometer's within-country weight that includes household size and the number of adults), config afrobarometer.weight
  design     the file carries no PSU or strata variable. STRATA = region x urban/rural (REGION, URBRUR). PSUs are INFERRED: respondents in one region
             and urban/rural area with identical values on all 20 EA_* items (the fieldworker's observations of the enumeration area) form one
             cluster; this gives 285 clusters of 8 (13 of 16, one of 24, one of 6), against the 300 EAs of the Tanzania sample. It is an inference, not a
             documented design: intervals are Taylor-linearised on it (logit scale, Student-t) and may be slightly narrower than the true design allows.
  base       "pct" = share of respondents ASKED (code -1 'missing / not asked' excluded; 'refused' and "don't know" stay in the base).
             "pct_of_valid" = share among respondents who gave a substantive answer (refused / don't know excluded).
  disclosure the project rule (config disclosure): base < min_base suppressed; numerator < low_precision_numerator withheld and flagged.

Also computed here: the baseline SCORES (weighted mean of an item rescaled to 0-1, don't know / refused excluded) used to map three of the five
tax_morale.baseline.* constants to data, and the civic-duty minus reciprocity gap recomputed from the components with its own CI.

Outputs: data/processed/afrobarometer_morale.json (aggregates), outputs/tables/tax_morale_components.csv
"""

import csv
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pyreadstat
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
from survey_design import ci95, linearised_ratio

CFG = paths.CFG["afrobarometer"]
LABEL = "weighted survey estimates, Afrobarometer Round 8 Tanzania 2021; components only, no composite"
NO_ANSWER = (8, 9, 98, 99)


# ------------------------------------------------------------------ data
def load(sav_path=None):
    cols = ["RESPNO", "REGION", "URBRUR", "Q1", "DATEINTR", CFG["weight"]] + [c for c in _ea_columns(sav_path)] + sorted({i["variable"] for i in CFG["indicators"]})
    df, meta = pyreadstat.read_sav(sav_path or paths.AFROBAROMETER_SAV, usecols=list(dict.fromkeys(cols)), apply_value_formats=False)
    return df, meta


def _ea_columns(sav_path=None):
    _, meta = pyreadstat.read_sav(sav_path or paths.AFROBAROMETER_SAV, metadataonly=True)
    return [c for c in meta.column_names if c.startswith("EA_")]


def design(df):
    ea = [c for c in df.columns if c.startswith("EA_")]
    strata = df["REGION"].astype(int).astype(str) + "|" + df["URBRUR"].astype(int).astype(str)
    psu = strata + "|" + df[ea].astype(str).agg("|".join, axis=1)
    return strata.to_numpy(), psu.to_numpy()


def age_band_masks(df):
    bands = paths.CFG["targeting"]["agent_age_bands"]
    age = df["Q1"].to_numpy(float)
    out = []
    for i, (lo, hi) in enumerate(bands):
        lo_eff = max(lo, 18)                               # Afrobarometer interviews adults 18+
        m = (age >= lo_eff) & ((age <= hi) if i < len(bands) - 1 else np.ones(len(age), bool))
        out.append(("%d-%d" % (lo_eff, hi) if i < len(bands) - 1 else "%d+" % lo_eff, m))
    return out


# ------------------------------------------------------------------ estimation
def _influence(num, den, w, strata, psu):
    """Linearised influence values of the ratio sum(w*num)/sum(w*den) aggregated to PSUs: (ratio, frame of PSU totals)."""
    num, den, w = np.asarray(num, float), np.asarray(den, float), np.asarray(w, float)
    d_total = float((w * den).sum())
    if d_total <= 0:
        return float("nan"), None
    ratio = float((w * num).sum()) / d_total
    z = w * (num - ratio * den) / d_total
    f = pd.DataFrame({"z": z, "h": strata, "c": psu})
    return ratio, f.groupby(["h", "c"], sort=False)["z"].sum().reset_index()


def _variance(tot):
    var = 0.0
    for _, g in tot.groupby("h", sort=False):
        n_h = len(g)
        if n_h >= 2:
            var += n_h / (n_h - 1.0) * float(((g["z"] - g["z"].mean()) ** 2).sum())
    return var


def _t(tot):
    return float(stats.t.ppf(0.975, max(tot["c"].shape[0] - tot["h"].nunique(), 1)))


def share(num, base, w, strata, psu):
    """Weighted share (per cent) of `num` within `base` (both boolean) with a logit 95% CI. Returns (pct, lo, hi)."""
    r, se, n_psu, n_str, _ = linearised_ratio(num.astype(float), base.astype(float), w, strata, psu)
    if not (r == r):
        return None, None, None
    lo, hi = ci95(r, se, n_psu, n_str)
    return r * 100, lo * 100, hi * 100


def mean_score(score, base, w, strata, psu):
    """Weighted mean of a 0-1 score within `base`, with a Student-t interval on the linearised standard error."""
    r, tot = _influence(np.where(base, score, 0.0), base.astype(float), w, strata, psu)
    if tot is None:
        return None, None, None
    se = math.sqrt(_variance(tot))
    t = _t(tot)
    return r, max(r - t * se, 0.0), min(r + t * se, 1.0)


def difference(num1, base1, num2, base2, w, strata, psu):
    """Difference in percentage points between two weighted shares on the same respondents, with a CI from the joint linearisation."""
    r1, t1 = _influence(num1.astype(float), base1.astype(float), w, strata, psu)
    r2, t2 = _influence(num2.astype(float), base2.astype(float), w, strata, psu)
    m = t1.merge(t2, on=["h", "c"], suffixes=("1", "2"))
    m["z"] = m["z1"] - m["z2"]
    se = math.sqrt(_variance(m[["h", "c", "z"]]))
    t = _t(m[["h", "c", "z"]])
    d = (r1 - r2) * 100
    return d, d - t * se * 100, d + t * se * 100


def _codes(series, codes):
    return series.isin(codes).to_numpy()


def indicator_row(ind, level, mask, df, w, strata, psu):
    x = df[ind["variable"]].to_numpy(float)
    asked = mask & (x != -1) & ~np.isnan(x)
    valid = asked & ~np.isin(x, NO_ANSWER)
    num = asked & np.isin(x, ind["codes"])
    row = {"group": ind["group"], "indicator": ind["id"], "variable": ind["variable"], "answer_codes": ind["codes"], "level": level,
           "n_unweighted_base": int(asked.sum()), "n_unweighted_numerator": int(num.sum())}
    p, lo, hi = share(num, asked, w, strata, psu)
    pv, lov, hiv = share(num & valid, valid, w, strata, psu) if valid.sum() else (None, None, None)
    row.update({"pct": p, "ci95_low_pct": lo, "ci95_high_pct": hi, "pct_of_valid": pv, "ci95_low_pct_of_valid": lov, "ci95_high_pct_of_valid": hiv,
                "n_unweighted_valid": int(valid.sum()),
                "pct_dont_know_or_refused": float(np.average(np.isin(x, NO_ANSWER)[asked], weights=w[asked]) * 100) if asked.sum() else None})
    keys = ["pct", "ci95_low_pct", "ci95_high_pct", "pct_of_valid", "ci95_low_pct_of_valid", "ci95_high_pct_of_valid", "pct_dont_know_or_refused", "n_unweighted_valid"]
    return disclosure.apply_to_row(row, "n_unweighted_base", "n_unweighted_numerator", keys)


def baseline_scores(df, w, strata, psu):
    out = {}
    for key, spec in CFG["baseline_mapping"].items():
        if not spec.get("variable"):
            out[key] = {"mapped": False, "candidate_variable": spec.get("candidate_variable"), "rationale": spec["rationale"]}
            continue
        x = df[spec["variable"]].to_numpy(float)
        valid = (x >= spec["valid_min"]) & (x <= spec["valid_max"])
        s = (x - spec["valid_min"]) / (spec["valid_max"] - spec["valid_min"])
        if spec["direction"] == "reverse":
            s = 1.0 - s
        s = np.where(valid, s, 0.0)
        m, lo, hi = mean_score(s, valid, w, strata, psu)
        out[key] = {"mapped": True, "variable": spec["variable"], "label": spec.get("label"), "score": "weighted mean of the item rescaled to 0-1 (%s), don't know / refused excluded" % spec["rescale"],
                    "value": m, "ci95": [lo, hi], "n_unweighted_base": int(valid.sum()), "previous_typed_value": spec["previous_typed_value"],
                    "mapping_rationale": spec["rationale"]}
    return out


def run_afrobarometer_morale(sav_path=None, json_path=None, csv_path=None):
    json_path = json_path or paths.AFROBAROMETER_MORALE
    csv_path = csv_path or paths.TAX_MORALE_COMPONENTS_CSV
    df, meta = load(sav_path)
    w = df[CFG["weight"]].to_numpy(float)
    strata, psu = design(df)
    levels = [("All adults 18+", np.ones(len(df), bool)), ("Urban", (df["URBRUR"] == 1).to_numpy()), ("Rural", (df["URBRUR"] == 2).to_numpy())]
    levels += [("Age " + name, m) for name, m in age_band_masks(df)]
    rows = []
    for ind in CFG["indicators"]:
        for name, m in levels:
            rows.append(indicator_row(ind, name, m, df, w, strata, psu))

    # the reciprocity gap the report quotes (71% civic duty minus 43% "government listens"), recomputed from the components
    gaps = []
    for g in CFG["gap_definitions"]:
        a = next(i for i in CFG["indicators"] if i["id"] == g["civic_duty"]); b = next(i for i in CFG["indicators"] if i["id"] == g["reciprocity"])
        xa, xb = df[a["variable"]].to_numpy(float), df[b["variable"]].to_numpy(float)
        ba, bb = (xa != -1) & ~np.isnan(xa), (xb != -1) & ~np.isnan(xb)
        d, lo, hi = difference(ba & np.isin(xa, a["codes"]), ba, bb & np.isin(xb, b["codes"]), bb, w, strata, psu)
        pa = next(r for r in rows if r["indicator"] == a["id"] and r["level"] == "All adults 18+")
        pb = next(r for r in rows if r["indicator"] == b["id"] and r["level"] == "All adults 18+")
        gaps.append({"civic_duty_indicator": a["id"], "civic_duty_variable": a["variable"], "civic_duty_pct": pa["pct"],
                     "reciprocity_indicator": b["id"], "reciprocity_variable": b["variable"], "reciprocity_pct": pb["pct"],
                     "gap_percentage_points": d, "ci95_percentage_points": [lo, hi]})

    result = {
        "label": LABEL, "type": "COMPUTED (survey data)",
        "source": {"dataset": "Afrobarometer Round 8, Tanzania, respondent-level data", "file": os.path.basename(sav_path or paths.AFROBAROMETER_SAV),
                   "n_respondents": int(len(df)), "fieldwork": {"from": str(df["DATEINTR"].min()), "to": str(df["DATEINTR"].max()), "from_variable": "DATEINTR"},
                   "citation": CFG["citation"], "provenance": "data/raw/SOURCES.csv"},
        "estimation": {"weight": CFG["weight"], "weight_note": CFG["weight_note"], "strata": "REGION x URBRUR (%d strata)" % len(set(strata)),
                       "psu": "INFERRED from identical region, urban/rural and EA_* items: %d clusters (not a documented design)" % len(set(psu)),
                       "interval": "95%, logit scale, Student-t, Taylor-linearised on the inferred design",
                       "bases": "pct: respondents asked (don't know and refused stay in the base); pct_of_valid: substantive answers only"},
        "disclosure_rule": "base < %d suppressed; numerator < %d withheld and the row flagged low_precision" % (disclosure.MIN_BASE, disclosure.LOW_PRECISION_NUMERATOR),
        "composite": {"published": False, "note": "the 59.8% composite (assumed weights 30/35/20/15) is retired; the WVS 61.8% stays removed; only components are published"},
        "indicators": [{"id": i["id"], "group": i["group"], "variable": i["variable"], "question": i["question"], "answer_codes_counted": i["codes"],
                        "code_labels": i["code_labels"], "meaning": i["meaning"]} for i in CFG["indicators"]],
        "estimates": rows,
        "civic_duty_minus_reciprocity_gap": {"report_value": "28 pp (71% civic duty minus 43% 'government listens'; hand-typed from published figures, not reproducible from the file)", "recomputed": gaps},
        "baseline_scores": baseline_scores(df, w, strata, psu),
    }
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    cols = ["group", "indicator", "variable", "answer_codes", "level", "n_unweighted_base", "n_unweighted_numerator", "pct", "ci95_low_pct", "ci95_high_pct",
            "pct_of_valid", "ci95_low_pct_of_valid", "ci95_high_pct_of_valid", "pct_dont_know_or_refused", "low_precision", "suppressed"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in rows:
            wr.writerow([("" if r.get(c) is None else ("%.2f" % r[c] if isinstance(r.get(c), float) else (";".join(map(str, r[c])) if isinstance(r.get(c), list) else r.get(c, False if c in ("low_precision", "suppressed") else "")))) for c in cols])
    nat = {r["indicator"]: r for r in rows if r["level"] == "All adults 18+"}
    print("  afrobarometer: %d respondents; civic duty (Q76e always) %.1f%%, trust in tax office (a lot) %.1f%%, councillors listen (often/always) %.1f%%" % (
        len(df), nat["civic_duty_always_pay"]["pct"], nat["trust_tax_office_a_lot"]["pct"], nat["listen_councillors_often_always"]["pct"]))
    return result


if __name__ == "__main__":
    run_afrobarometer_morale()
