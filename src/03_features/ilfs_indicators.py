"""W1 - ILFS 2024 informality, status in employment and enterprise registration (COMPUTED from the microdata).

Reads data/raw/ilfs/ILFS2024-URT-FINAL - Anonymized.sav (NBS, public-use file) with pyreadstat.
Weight: WEIGHT (sums to the file's population total, 65,257,621.66 persons; 61,588 person records).

POPULATION AND BASE (decisions fixed in the Block B brief, plus the one choice documented here)
  * employed persons aged 15+, MAIN JOB only (Q25, Q27A, Q33, Q34, Q37, Q38A all refer to the main job);
    agriculture is INCLUDED.
  * "Employed" = ILO_LFS19 == 1 (employed under the 19th ICLS), the variable NBS uses for its published
    employment-to-population ratio (computed here: 68.65% against NBS's published 68.7%). The 13th-ICLS flag
    (ILO_LFS == 1, which also counts own-use farmers and gives an employment ratio of 83.2%) is reported as a
    sensitivity case. Persons aged 98/99 (= don't know / not stated) are excluded from the 15+ base.

INFORMAL EMPLOYMENT, ICLS-17 (17th International Conference of Labour Statisticians, 2003 guidelines
on informal employment; operational rules follow the ILO/NBS practice for a household survey with these items)
  Status in the main job is Q25 (1 paid employee; 2 self-employed non-agricultural; 3 self-employed agricultural;
  4 unpaid helper in non-agricultural household activities; 5 unpaid helper in agricultural household activities;
  6 on-the-job trainee; 7 unpaid helper of a family member working for someone else).
    contributing family workers  Q25 in {4, 5, 7}   -> always informal (the ICLS-17 rule for this status)
    employees and trainees       Q25 in {1, 6}      -> informal when Q34 != 1, i.e. no social-security contribution
                                                       is paid (Q34: 1 yes, 2 no, 3 don't know; 'don't know' counts as not
                                                       paid). Social-security coverage is the ILO's primary criterion.
    employers and own-account    Q25 in {2, 3}      -> informal when the enterprise is not registered: Q38A == 6
                                                       (Q38A 1-5 = registered with BRELA/BPRA, TRA/ZRB or another
                                                       authority, with or without licence). A missing Q38A (under 1% of
                                                       these workers) is treated as not registered.
  Sensitivity: (b) an employee is informal only if none of social security (Q34), paid annual leave (Q30) and paid sick
  leave (Q31A) applies; (c) 13th-ICLS employed base; (d) non-agricultural workers only (ISIC section A excluded,
  Q22B_MAIN_ISIC != 1).

STATUS IN EMPLOYMENT (ICSE-93 style, from Q25 and Q27A 'paid employees on a regular basis')
  employees = Q25 1; employers = Q25 2 or 3 with Q27A == 1; own-account workers = Q25 2 or 3 with Q27A != 1;
  contributing family workers = Q25 4, 5 or 7; other = Q25 6 (on-the-job trainees). Self-employment is reported with
  and without contributing family workers.
  NOTE: NBS's report uses ICSE-18 categories (dependent contractors, independent workers, ...) that cannot be rebuilt
  one-to-one from Q25; the comparison with its published shares is in ilfs_summary.json.

REGISTRATION SHARE (Q38A != 6 among those whose Q38A is answered; main job)
  headline base: non-agricultural self-employed (Q25 == 2); also all workers with Q38A answered, and
  non-agricultural private-business owners (Q37 == 6). 'Registered' = any registration with any authority, Q38A in 1-5;
  also reported: with a business licence (Q38A in 1, 3) and with TRA/ZRB (Q38A == 2).

SURVEY DESIGN. The file has no variable called strata or PSU. Its geography columns (region, district, council,
constituency, division, ward/shehia, village, enumeration area) identify exactly 593 enumeration areas
(24 households each), the 593 first-stage EAs NBS reports. PSU = that composite EA key. Strata are RECONSTRUCTED as
region (31): NBS's published sampling domains (rural, other urban, Dar es Salaam; 7 domains in Zanzibar) are
not identifiable in the file (there is no urban/rural variable for the current residence). Design-based
(Taylor-linearised) 95% confidence intervals use survey_design.py, labelled "reconstructed design".

Outputs: data/processed/ilfs_indicators.json (aggregates only), outputs/tables/ilfs_informality.csv,
outputs/stats/ilfs_summary.json.
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
from survey_design import ci95, design_df, linearised_ratio

COLUMNS = ["ILO_LFS", "ILO_LFS19", "REGION", "DISTRICT", "COUNCIL", "CONSTITUENCY", "DIVISION", "WARD_SHEHIA", "VILLAGE",
           "EA", "Q06B_MEM_AGE", "Q25", "Q27A", "Q30", "Q31A", "Q34", "Q37", "Q38A", "Q38C", "Q22B_MAIN_ISIC", "WEIGHT"]
GEO = ["REGION", "DISTRICT", "COUNCIL", "CONSTITUENCY", "DIVISION", "WARD_SHEHIA", "VILLAGE", "EA"]

# published figures (CITED, never computed here): NBS, "The Labour Market: Key Findings from the ILFS 2024", Nov 2025
CITATION = {
    "title": "The Labour Market: Key Findings from the ILFS 2024",
    "publisher": "National Bureau of Statistics (NBS), United Republic of Tanzania, with OCGS Zanzibar",
    "published": "07 November 2025",
    "url": "https://www.nbs.go.tz/uploads/statistics/documents/en-1762517636-THE%20LABOUR%20MARKET%20KEY%20FINDINGS%20FROM%20THE%20ILFS%202024.pdf",
    "figures": {
        "informal_employment_2024_pct": {"value": 94.6, "where": "Figure 3.3 (the key message calls it Figure 2.3), printed p. 20; Executive Summary p. 1"},
        "informal_employment_2020_21_pct": {"value": 92.5, "where": "same Figure 3.3, 2020/21 bars (URT total); Executive Summary p. 1; Annex A summary of findings"},
        "dependent_contractors_pct": {"value": 74.8, "where": "Table 3.3 (the key message calls it Table 2.3), printed p. 16, URT total"},
        "contributing_family_workers_pct": {"value": 16.9, "where": "Table 3.3, printed p. 16, URT total"},
        "employees_paid_employment_pct": {"value": 7.7, "where": "Table 3.3, printed p. 16, URT total"},
        "employment_to_population_ratio_pct": {"value": 68.7, "where": "Table 3.2 key message, printed p. 16 (65.8% in 2020/21)"},
    },
}


# --------------------------------------------------------------------------------------------- classification
def classify(df):
    """Adds boolean/category columns used by the indicators. Pure function of the survey columns."""
    q25 = df["Q25"]
    q38 = df["Q38A"]
    out = pd.DataFrame(index=df.index)
    out["status"] = np.select(
        [q25.isna(), q25 == 1, q25.isin([2, 3]) & (df["Q27A"] == 1), q25.isin([2, 3]), q25.isin([4, 5, 7]), q25 == 6],
        ["not stated", "employee", "employer", "own-account", "contributing family worker", "other (trainee)"],
        default="not stated")
    out["is_employee"] = q25.isin([1, 6])
    out["is_selfemp"] = q25.isin([2, 3])
    out["is_cfw"] = q25.isin([4, 5, 7])
    out["registered"] = q38.isin([1, 2, 3, 4, 5])
    out["q38_answered"] = q38.notna()
    out["licensed"] = q38.isin([1, 3])
    out["tra_registered"] = q38 == 2
    ss = df["Q34"] == 1
    out["informal"] = np.where(out["is_cfw"], True,
                        np.where(out["is_employee"], ~ss,
                        np.where(out["is_selfemp"], ~out["registered"], np.nan)))
    leave = (df["Q30"] == 1) | (df["Q31A"] == 1)
    out["informal_leave_test"] = np.where(out["is_cfw"], True,
                        np.where(out["is_employee"], ~(ss | leave),
                        np.where(out["is_selfemp"], ~out["registered"], np.nan)))
    # Sensitivity "NBS-consistent" rule: formal = employees with social security, plus self-employed whose business is registered
    # as a company/legal entity (Q38C == 1); everyone else is informal. It reproduces NBS's published 94.6% to within 0.1 pp.
    formal_nbs_like = (out["is_employee"] & ss) | (out["is_selfemp"] & (df["Q38C"] == 1))
    out["informal_nbs_like"] = ~formal_nbs_like
    out["agriculture"] = df["Q22B_MAIN_ISIC"] == 1
    return out


def _design(df):
    psu = df[GEO].astype(int).astype(str).agg("|".join, axis=1)
    strata = df["REGION"].astype(int).astype(str)
    return strata.to_numpy(), psu.to_numpy()


def estimate(label, base, num, w, strata, psu, definition, group="", note=""):
    """Weighted share of `num` within `base` (boolean arrays) with a linearised 95% CI. Returns a dict (per cent)."""
    base = np.asarray(base, dtype=bool)
    num = np.asarray(num, dtype=float) * base
    r, se, n_psu, n_str, lonely = linearised_ratio(num, base.astype(float), w, strata, psu)
    lo, hi = ci95(r, se, n_psu, n_str)
    row = {"group": group, "indicator": label, "base_definition": definition, "n_unweighted_base": int(base.sum()),
           "n_unweighted_numerator": int((np.asarray(num) > 0).sum()),
           "base_weighted_persons": float((w * base).sum()),
           "estimate_pct": r * 100.0, "se_pct": se * 100.0, "ci95_low_pct": lo * 100.0, "ci95_high_pct": hi * 100.0,
           "note": note}
    # disclosure rule (config.yaml disclosure): applied to every published row
    return disclosure.apply_to_row(row, "n_unweighted_base", "n_unweighted_numerator",
                                   ["estimate_pct", "se_pct", "ci95_low_pct", "ci95_high_pct"], ["base_weighted_persons"])


def compute(df):
    """Returns (rows, summary) for an ILFS data frame (columns as in COLUMNS)."""
    w = df["WEIGHT"].to_numpy(dtype=float)
    strata, psu = _design(df)
    age = df["Q06B_MEM_AGE"]
    age_ok = age.between(15, 97)
    c = classify(df)
    emp19 = (df["ILO_LFS19"] == 1) & age_ok
    emp13 = (df["ILO_LFS"] == 1) & age_ok
    stat_ok = c["status"] != "not stated"

    rows = []
    B19 = "employed 15+ (ILO_LFS19 = 1), main job, agriculture included"
    B13 = "employed 15+ (ILO_LFS = 1, 13th ICLS), main job, agriculture included, status stated"
    base19 = emp19 & stat_ok
    base13 = emp13 & stat_ok
    nonag19 = base19 & ~c["agriculture"]

    inf = c["informal"].astype(float).fillna(0).to_numpy() == 1
    inf_leave = c["informal_leave_test"].astype(float).fillna(0).to_numpy() == 1
    # A. informality
    rows.append(estimate("Informal employment rate, ICLS-17 (headline)", base19, inf, w, strata, psu, B19, "informality",
                         "contributing family workers; employees without social security (Q34 != 1); self-employed in unregistered enterprises (Q38A = 6)"))
    rows.append(estimate("Informal employment, employees' leave test", base19, inf_leave, w, strata, psu, B19, "informality",
                         "employee informal only if no social security, no paid annual leave and no paid sick leave"))
    rows.append(estimate("Informal employment, NBS-consistent rule", base19, c["informal_nbs_like"].to_numpy(), w, strata, psu, B19, "informality",
                         "formal = employees with social security + self-employed with a legal-entity registration (Q38C = 1); all others informal"))
    rows.append(estimate("Informal employment, 13th-ICLS employed base", base13, inf, w, strata, psu, B13, "informality", "sensitivity: includes own-use farmers"))
    rows.append(estimate("Informal employment, non-agricultural workers", nonag19, inf, w, strata, psu,
                         B19 + ", excluding ISIC section A", "informality"))
    for name, m in (("employees", c["is_employee"]), ("employers and own-account workers", c["is_selfemp"]), ("contributing family workers", c["is_cfw"])):
        sub = base19 & m
        rows.append(estimate("Informal employment among %s" % name, sub, inf, w, strata, psu, B19 + ", status = " + name, "informality_by_status"))
    # B. status in employment
    for cat in ("employee", "employer", "own-account", "contributing family worker", "other (trainee)"):
        rows.append(estimate("Share of employed: " + cat, base19, (c["status"] == cat).to_numpy(), w, strata, psu, B19, "status"))
    selfemp = c["status"].isin(["employer", "own-account"]).to_numpy()
    rows.append(estimate("Self-employed (employers + own-account), without contributing family workers", base19, selfemp, w, strata, psu, B19, "status"))
    rows.append(estimate("Self-employed incl. contributing family workers", base19, selfemp | (c["status"] == "contributing family worker").to_numpy(),
                         w, strata, psu, B19, "status", "the 'self-employed' reading that includes unpaid family helpers"))
    rows.append(estimate("Share of employed: status as in 13th-ICLS base, employees", base13, (c["status"] == "employee").to_numpy(), w, strata, psu, B13, "status"))
    # C. registration
    reg = c["registered"].to_numpy()
    def reg_rows(base, base_name, head):
        r = []
        r.append(estimate("Registered (any authority) - " + base_name, base, reg, w, strata, psu, base_name, "registration", head))
        r.append(estimate("With a business licence - " + base_name, base, c["licensed"].to_numpy(), w, strata, psu, base_name, "registration"))
        r.append(estimate("Registered with TRA/ZRB - " + base_name, base, c["tra_registered"].to_numpy(), w, strata, psu, base_name, "registration"))
        return r
    ans = c["q38_answered"].to_numpy()
    rows += reg_rows(base19 & (df["Q25"] == 2).to_numpy() & ans, "non-agricultural self-employed (Q25 = 2), Q38A answered [HEADLINE BASE]", "headline")
    rows += reg_rows(base19 & ans, "all workers with Q38A answered", "")
    rows += reg_rows(base19 & (df["Q37"] == 6).to_numpy() & ans, "non-agricultural private-business owners/workers (Q37 = 6), Q38A answered", "")
    # D. context
    rows.append(estimate("Employment-to-population ratio, 15+ (19th ICLS)", age_ok.to_numpy(), emp19.to_numpy(), w, strata, psu, "all persons 15-97", "context",
                         "NBS publishes 68.7%"))
    rows.append(estimate("Employment-to-population ratio, 15+ (13th ICLS)", age_ok.to_numpy(), emp13.to_numpy(), w, strata, psu, "all persons 15-97", "context"))

    est = {r["indicator"]: r for r in rows}
    n_psu = len(set(psu))
    n_str = len(set(strata))
    lonely = int(pd.Series(psu).groupby(pd.Series(strata)).nunique().eq(1).sum())
    summary = {
        "records": int(len(df)),
        "weight_sum_persons": float(w.sum()),
        "design": {"description": "RECONSTRUCTED: PSU = enumeration area (composite of the 8 geography columns), strata = region; "
                                  "linearised variance, logit CI, Student-t",
                   "n_psu": n_psu, "n_strata": n_str, "strata_with_one_psu": lonely, "degrees_of_freedom": design_df(n_psu, n_str),
                   "published_first_stage_EAs": 593},
        "base": {"employed_15plus_19th_icls_unweighted": int(emp19.sum()), "employed_15plus_19th_icls_weighted": float(w[emp19.to_numpy()].sum()),
                 "base_with_status_unweighted": int(base19.sum()), "status_not_stated_in_base_unweighted": int((emp19 & ~stat_ok).sum()),
                 "persons_15plus_weighted": float(w[age_ok.to_numpy()].sum()),
                 "q38a_missing_among_self_employed_unweighted": int((base19 & c["is_selfemp"] & ~c["q38_answered"]).sum()),
                 "employed_13th_icls_15plus_unweighted": int(emp13.sum())},
        "headline": {
            "informal_employment_pct": est["Informal employment rate, ICLS-17 (headline)"]["estimate_pct"],
            "registration_share_pct_headline_nonag_self_employed": est["Registered (any authority) - non-agricultural self-employed (Q25 = 2), Q38A answered [HEADLINE BASE]"]["estimate_pct"],
        },
    }
    return rows, summary


# --------------------------------------------------------------------------------------------- outputs
def _fmt(v):
    return "%.4f" % v if isinstance(v, float) else v


def write_outputs(rows, summary, csv_path, json_path, summary_path):
    for p in (csv_path, json_path, summary_path):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    cols = ["group", "indicator", "base_definition", "n_unweighted_base", "n_unweighted_numerator", "base_weighted_persons",
            "estimate_pct", "se_pct", "ci95_low_pct", "ci95_high_pct", "note"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in rows:
            wr.writerow([_fmt(r[c]) if c != "base_weighted_persons" or r[c] is None else "%.0f" % r[c] for c in cols])
    est = {r["indicator"]: r for r in rows}
    indicators = {r["indicator"]: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("indicator",)} for r in rows}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "ILFS 2024 anonymized microdata (NBS), WEIGHT", "type": "COMPUTED", "aggregates_only": True,
                   "design": summary["design"], "base": summary["base"], "indicators": indicators}, f, indent=2, ensure_ascii=False)

    def g(label):
        return est[label]["estimate_pct"]
    pub = CITATION["figures"]
    comp = {
        "informal_employment_2024": {"computed_pct": g("Informal employment rate, ICLS-17 (headline)"), "published_pct": pub["informal_employment_2024_pct"]["value"],
                                     "gap_pp": g("Informal employment rate, ICLS-17 (headline)") - pub["informal_employment_2024_pct"]["value"],
                                     "nbs_consistent_rule_pct": g("Informal employment, NBS-consistent rule"),
                                     "nbs_consistent_rule_gap_pp": g("Informal employment, NBS-consistent rule") - pub["informal_employment_2024_pct"]["value"],
                                     "explanation": "NBS does not state its operational definition. The headline applies the ICLS-17 rules to the items in the file "
                                                    "(self-employed are formal if their enterprise is registered with any authority, Q38A 1-5). NBS's 94.6% is "
                                                    "reproduced to within 0.1 pp by a stricter rule: only employees with social-security contributions and "
                                                    "self-employed with a legal-entity registration (Q38C = 1) are formal. The gap is therefore a definition "
                                                    "difference (what counts as a registered enterprise), not rounding or a base difference."},
        "employment_to_population_ratio": {"computed_pct": g("Employment-to-population ratio, 15+ (19th ICLS)"), "published_pct": pub["employment_to_population_ratio_pct"]["value"],
                                           "note": "agreement shows the 19th-ICLS employed flag is the base NBS uses"},
        "employees_vs_nbs_paid_employment": {"computed_q25_paid_employee_pct": g("Share of employed: employee"), "published_pct": pub["employees_paid_employment_pct"]["value"],
                                             "explanation": "Q25 'paid employee' is wider than NBS's 'wage and salaried' class (ICSE-18); wage/salary earners (Q28A = 1) are about 7.1% of the employed (checked, not reported as a headline)."},
        "contributing_family_workers": {"computed_pct": g("Share of employed: contributing family worker"), "published_pct": pub["contributing_family_workers_pct"]["value"],
                                        "explanation": "Q25 4, 5 and 7 (incl. unpaid helpers in agriculture) vs NBS's ICSE-18 class; different category boundaries."},
        "self_employed_vs_dependent_contractors": {"computed_self_employed_without_cfw_pct": g("Self-employed (employers + own-account), without contributing family workers"),
                                                   "computed_self_employed_with_cfw_pct": g("Self-employed incl. contributing family workers"),
                                                   "published_dependent_contractors_pct": pub["dependent_contractors_pct"]["value"],
                                                   "explanation": "The report's '74.8% self-employed' is NBS's 'dependent contractors' share (ICSE-18), not a self-employed total; "
                                                                  "NBS publishes no 'self-employed' figure and its six classes do not map onto Q25."},
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"type": "COMPUTED (2024 values) / CITED (2020/21 and NBS comparison figures)",
                   "headline": summary["headline"],
                   "registration_bases": {k: round(r["estimate_pct"], 4) for k, r in est.items() if r["group"] == "registration"},
                   "status_shares_pct": {k: round(r["estimate_pct"], 4) for k, r in est.items() if r["group"] == "status"},
                   "informality_pct": {k: round(r["estimate_pct"], 4) for k, r in est.items() if r["group"] in ("informality", "informality_by_status")},
                   "design": summary["design"], "base": summary["base"],
                   "published_cross_check": comp, "cited_source": CITATION,
                   "informality_2020_21_cited_pct": 92.5,
                   "informality_2020_21_note": "CITED from the 2024 report (NBS 2025); the 2020/21 microdata are not held and the 2020/21 Analytical Report (NBS 2022) "
                                               "does not itself state 92.5% (it gives the informal SECTOR share, 29.0% of employment, Table 6.1)."},
                  f, indent=2, ensure_ascii=False)


def run_ilfs_indicators(sav_path=None, csv_path=None, json_path=None, summary_path=None):
    import pyreadstat
    sav_path = sav_path or paths.ILFS_SAV
    df, _ = pyreadstat.read_sav(sav_path, usecols=COLUMNS)
    rows, summary = compute(df)
    write_outputs(rows, summary, csv_path or paths.ILFS_INFORMALITY_CSV, json_path or paths.ILFS_INDICATORS, summary_path or paths.ILFS_SUMMARY)
    h = summary["headline"]
    print("  employed 15+ (19th ICLS): %s records; informal employment %.2f%%; registered (non-agri self-employed) %.2f%%" % (
        format(summary["base"]["base_with_status_unweighted"], ","), h["informal_employment_pct"], h["registration_share_pct_headline_nonag_self_employed"]))
    return rows, summary


if __name__ == "__main__":
    run_ilfs_indicators()
