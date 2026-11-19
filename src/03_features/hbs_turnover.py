"""W-HBS (Pass 6B-1) - turnover of non-farm household-business owners from the Household Budget Survey 2017/18, as AGGREGATES (no respondent-level rows are written).

Promoted from the Pass 6C/6D diagnostics (_archive/diagnostics/pass6c|6d/scripts/hbs_prep.py, e2_*, e3_mzani.py). It feeds three consumers:
  * stage_economics.py: revenue per registrant of the Active and Enterprise stages (central = owners WITH receipts in the reference month; low = all owners, zeros kept);
  * the taxable-capacity output (share and number of adults above TZS 4M and 11M);
  * the Mzani wa Kodi tool: zone x activity and region x activity turnover bands with the presumptive tax at P25, median and P75.

Definitions (all labelled in docs/assumptions_register.csv, sign-off PENDING):
  persons        HBS 2017/18 Individual file, aged 16+; person weight = household weight (`weight`) of the Consumption Aggregate file (popweight is household weight x size and is never summed over persons)
  owner          a person with a record in the household-business section S10 (non-farm) whose ownership is a sole proprietorship or a partnership (proxy for FinScope BusO; farm businesses are not in S10)
  turnover       last-month receipts from sources 1-4 (sales of products, resale goods, construction, services; rents, interest and gifts excluded) x months operated in the last 12 (S10_06), uprated to 2024 with
                 World Bank WDI FP.CPI.TOTL (mean of 2017 and 2018 to 2024). Owners with no receipts in the reference month have turnover 0 (the "all owners" basis); the central basis uses owners WITH receipts
  formal step    BRELA registration (S10_15) or paying income tax or VAT (S10_16a)
  tax owed       the project's presumptive schedule (statutory_tax.presumptive; Finance Act 2026) up to the TZS 200M ceiling; turnover above the ceiling is flagged and excluded
  new business   started in the 12 months before the interview (for the 12-month nil period sensitivity)
Stage mapping B (finscope_segments.py): Active = owner, no formal step, 25-64; Enterprise = owner with a formal step, 25-64; Entry 16-24 and Legacy 65+ whoever they are; Workers 25-44 = non-owners; Asset = non-owners 45-64.
HBS is Mainland only, 2017/18; wage and salary income is not recorded: non-owners have no taxable turnover here.
Disclosure (config.yaml disclosure): cells with fewer than min_base respondents are suppressed; numerators below the threshold are flagged low precision.

Outputs: data/processed/hbs_turnover.json (aggregates), outputs/tables/taxable_capacity.csv, outputs/tables/taxable_capacity_by_zone.csv, outputs/stats/mzani_turnover.json, outputs/tables/mzani_turnover_zone_activity.csv
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
from assumptions import A
from statutory_tax import presumptive

CFG = paths.CFG["hbs"]
LABEL = "COMPUTED from HBS 2017/18 microdata (Mainland); CPI-uprated to 2024; last-month receipts annualised by months operated; not a forecast"
STAGES = ["entry", "active", "enterprise", "workers", "asset", "legacy"]
ACTIVITY_GROUPS = {"Agricultural products": "Traders - agricultural products (fishers cannot be separated)", "Non-agricultural goods and trade": "Traders - non-agricultural", "Services": "Service providers"}
CPC_TO_GROUP = {0: "Agricultural products", 1: "Non-agricultural goods and trade", 2: "Non-agricultural goods and trade", 3: "Non-agricultural goods and trade", 4: "Non-agricultural goods and trade",
                6: "Non-agricultural goods and trade", 5: "Services", 7: "Services", 8: "Services", 9: "Services"}


assert A("hbs.receipts_annualisation") == "last_month_receipts_x_months_operated" and A("hbs.cpi_uprating") == "wdi_fp_cpi_totl_mean_of_survey_years_to_target_year", "assumption differs from the implementation"
assert A("hbs.owners_with_receipts_central") is True


def cpi_factor():
    """CPI(target year) / CPI(survey): mean of the survey years (HBS fieldwork Dec 2017 - Dec 2018), from the WDI FP.CPI.TOTL snapshot."""
    with open(paths.WB_SNAPSHOTS[CFG["cpi_indicator"]], encoding="utf-8") as f:
        rows = json.load(f)[1]
    cpi = {int(r["date"]): r["value"] for r in rows if r["value"] is not None}
    survey = float(np.mean([cpi[int(y)] for y in CFG["cpi_survey_years"]]))
    return cpi[int(CFG["cpi_target_year"])] / survey, survey, cpi[int(CFG["cpi_target_year"])]


def load_frame():
    """Person frame (adults 16+ with a weight) with turnover, tax, flags and the stage of mapping B. Microdata are read here only."""
    import pyreadstat
    ind_cols = ["interview__id", "TUS__id", "REGION", "calc_age", "S1_4", "S10_02_1c", "S10_03_1", "S10_03_2", "S10_05", "S10_06", "S10_15", "S10_16a__1", "S10_16a__3"]
    ind, mi = pyreadstat.read_dta(paths.HBS_INDIVIDUAL, usecols=ind_cols)
    con, _ = pyreadstat.read_dta(paths.HBS_CONSUMPTION, usecols=["interview__id", "weight"])
    rec, mr = pyreadstat.read_dta(paths.HBS_S10C)
    reg_labels = mi.variable_value_labels.get("REGION", {})
    ind["region"] = ind["REGION"].map(reg_labels).fillna(ind["REGION"].astype(str))
    ind["age"] = ind["calc_age"].where(ind["calc_age"].between(0, 120), ind["S1_4"].where(ind["S1_4"].between(0, 120)))
    d = ind.merge(con, on="interview__id", how="left")
    rec = rec[rec["S10C__id"].isin(CFG["receipt_sources"])]
    rc = rec.groupby(["interview__id", "TUS__id"], as_index=False)["S10_10B"].sum().rename(columns={"S10_10B": "monthly_receipts"})
    d = d.merge(rc, on=["interview__id", "TUS__id"], how="left")
    d["monthly_receipts"] = d["monthly_receipts"].fillna(0.0)
    d["has_business"] = d["S10_06"].notna()
    d["reported"] = (d["monthly_receipts"] > 0) & d["has_business"]
    factor, _, _ = cpi_factor()
    months = d["S10_06"].clip(0, 12).fillna(0)
    d["turnover"] = np.where(d["has_business"], d["monthly_receipts"] * months, 0.0) * factor
    d["owner"] = d["has_business"] & d["S10_05"].isin([1, 2])
    d["formal"] = (d["S10_15"] == 1) | (d["S10_16a__3"] == 1) | (d["S10_16a__1"] == 1)
    d["new_business"] = d["has_business"] & ((d["S10_03_1"] >= 2018) | ((d["S10_03_1"] == 2017) & (d["S10_03_2"] >= 7)))
    d = d[(d["age"] >= 16) & d["weight"].notna()].copy()
    d["w"] = d["weight"]
    ceiling = A("tax.presumptive_schedule")["threshold_turnover"]
    d["over_ceiling"] = d["turnover"] > ceiling
    tax = np.where(d["over_ceiling"], 0.0, presumptive(d["turnover"].to_numpy()))
    d["tax"] = np.where(d["owner"], tax, 0.0)
    d["tax_first_year"] = np.where(d["new_business"], 0.0, d["tax"])
    a, o, f = d["age"], d["owner"], d["formal"]
    d["stage"] = np.select([(a <= 24), (a >= 65), o & ~f & (a >= 25) & (a <= 64), o & f & (a >= 25) & (a <= 64), (a >= 25) & (a <= 44) & ~o, (a >= 45) & (a <= 64) & ~o],
                           ["entry", "legacy", "active", "enterprise", "workers", "asset"], default="other")
    d["cpc_group"] = d["S10_02_1c"].map(CPC_TO_GROUP)
    zones = paths.CFG["zones"]["regions"]
    reg2zone = {r.lower(): z for z, rs in zones.items() for r in rs}
    d["zone"] = d["region"].str.lower().map(reg2zone)
    return d, reg_labels


def _wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    return float(np.average(x, weights=w)) if len(w) and w.sum() > 0 else float("nan")


def _wse(x, w):
    """Ratio-estimator standard error of the weighted mean, ignoring clustering (documented)."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    m = float(np.average(x, weights=w))
    return m, float(np.sqrt(np.sum((w * (x - m)) ** 2)) / np.sum(w))


def _wq(x, w, q):
    x, w = np.asarray(x, float), np.asarray(w, float)
    o = np.argsort(x)
    cw = np.cumsum(w[o]) / w.sum()
    return float(x[o][min(int(np.searchsorted(cw, q)), len(x) - 1)])


def group_stats(d, mask, reporters_only):
    """Mean tax per owner of a group (mapping B) and the figures stage_economics and the report need."""
    m = mask.to_numpy() if hasattr(mask, "to_numpy") else mask
    if reporters_only:
        m = m & d["reported"].to_numpy()
    g = d[m]
    w = g["w"].to_numpy()
    mean, se = _wse(g["tax"], w)
    out = {"n_unweighted": int(len(g)), "weighted": float(w.sum()), "tax_mean_tzs": mean, "tax_se_tzs": se, "share_owing_tax_pct": _wmean(g["tax"] > 0, w) * 100,
           "tax_first_year_mean_tzs": _wmean(g["tax_first_year"], w), "new_business_share_pct": _wmean(g["new_business"], w) * 100,
           "share_above_4m_pct": _wmean(g["turnover"] > 4e6, w) * 100, "share_above_11m_pct": _wmean(g["turnover"] > 11e6, w) * 100, "share_over_ceiling_pct": _wmean(g["over_ceiling"], w) * 100,
           "median_turnover_tzs": _wq(g["turnover"], w, 0.5), "mean_turnover_tzs": _wmean(g["turnover"], w)}
    assert not disclosure.is_suppressed(out["n_unweighted"]), "group too small to publish"
    return out


def taxable_capacity(d, fs_pop):
    """Shares (and numbers at FinScope scale) of adults above TZS 4M and 11M: all adults, by stage, owners, owners with receipts; by zone."""
    rows = []
    groups = [("all adults", np.ones(len(d), bool), sum(fs_pop.values()))] + [(s, (d["stage"] == s).to_numpy(), fs_pop.get(s)) for s in STAGES]
    groups += [("business owners", d["owner"].to_numpy(), None), ("owners with receipts in the reference month", (d["owner"] & d["reported"]).to_numpy(), None)]
    for name, m, pop in groups:
        g = d[m]
        w = g["w"].to_numpy()
        for thr in (4e6, 11e6):
            above = (g["turnover"] > thr).to_numpy()
            row = {"group": name, "threshold_tzs": thr, "n_unweighted": int(len(g)), "n_above_unweighted": int(above.sum()), "share_pct": _wmean(above, w) * 100,
                   "adults_above_hbs_weighted_2017_18": float(w[above].sum()), "adults_above_at_finscope_scale": (_wmean(above, w) * pop) if pop else None}
            row = disclosure.apply_to_row(row, "n_unweighted", "n_above_unweighted", ["share_pct"], ["adults_above_hbs_weighted_2017_18", "adults_above_at_finscope_scale"])
            rows.append(row)
    zrows = []
    for z in sorted(d["zone"].dropna().unique()):
        g = d[d["zone"] == z]
        w = g["w"].to_numpy()
        for thr in (4e6, 11e6):
            above = (g["turnover"] > thr).to_numpy()
            row = {"zone": z, "threshold_tzs": thr, "n_unweighted": int(len(g)), "n_above_unweighted": int(above.sum()), "share_pct": _wmean(above, w) * 100}
            zrows.append(disclosure.apply_to_row(row, "n_unweighted", "n_above_unweighted", ["share_pct"], []))
    return rows, zrows


MZANI_LABEL = "HBS 2017/18, CPI-uprated to 2024, last-month receipts annualised by months operated; owners with receipts"
MZANI_COVERAGE = ["Farmers and fishers are not covered: farm businesses are outside section 10 of the HBS questionnaire, and fishers cannot be separated from traders in agricultural products",
                  "Zanzibar is not covered: the HBS 2017/18 is a Mainland survey",
                  "The bands are for owners with receipts in the reference month (about 42% of non-farm business owners); owners with no receipts that month are not in them",
                  "Turnover is a survey estimate for the average business of the cell, not an assessment of any one business; the presumptive tax is the schedule in force applied to the band's turnover"]


def mzani_tables(d):
    """Zone x activity and region x activity turnover bands of owners WITH receipts, plus the national figure; the presumptive tax at P25, median and P75.
    Fallback order for a user: region cell (only with at least `mzani_min_region_cell` businesses with receipts) -> zone cell (disclosure minimum) -> national cell."""
    b = d[d["owner"] & d["cpc_group"].notna()].copy()
    ceiling = A("tax.presumptive_schedule")["threshold_turnover"]
    min_region = int(CFG["mzani_min_region_cell"])

    def tax_at(x):
        return None if x > ceiling else float(presumptive(np.array([x]))[0])          # above the ceiling the presumptive regime does not apply (the ordinary schedule does)

    def cells(df, keys, min_n):
        out = []
        for key, g in df.groupby(keys):
            rep = g[g["reported"]]
            rec = dict(zip(keys, key if isinstance(key, tuple) else (key,)))
            if disclosure.is_suppressed(len(rep)):                      # disclosure rule: a suppressed cell carries no counts and no estimate
                rec.update({"suppressed": True, "reason": "base < %d" % disclosure.MIN_BASE})
                out.append(rec)
                continue
            rec.update({"n_businesses": int(len(g)), "n_with_receipts": int(len(rep))})
            if len(rep) < min_n:                                        # enough to publish under the disclosure rule, not enough for a region band: withheld
                rec.update({"suppressed": False, "withheld": True, "withheld_reason": "fewer than %d businesses with receipts (region cells need %d)" % (min_n, min_n)})
            else:
                w, t_ = rep["w"].to_numpy(), rep["turnover"].to_numpy()
                q = [_wq(t_, w, p) for p in (0.25, 0.5, 0.75)]
                rec.update({"p25_tzs": q[0], "median_tzs": q[1], "p75_tzs": q[2], "tax_at_p25_tzs": tax_at(q[0]), "tax_at_median_tzs": tax_at(q[1]), "tax_at_p75_tzs": tax_at(q[2]),
                            "share_below_4m_pct": _wmean(t_ <= 4e6, w) * 100, "share_4m_to_11m_pct": _wmean((t_ > 4e6) & (t_ <= 11e6), w) * 100, "share_above_11m_pct": _wmean(t_ > 11e6, w) * 100,
                            "suppressed": False})
                if len(rep) < min_region:                                    # flagged cells name their fields (the disclosure convention); an unflagged cell carries no flag
                    rec.update({"low_precision": True, "low_precision_fields": ["p25_tzs", "median_tzs", "p75_tzs"]})
            out.append(rec)
        return out
    zone = cells(b.dropna(subset=["zone"]), ["zone", "cpc_group"], 10)
    region = cells(b, ["region", "cpc_group"], min_region)
    national = cells(b, ["cpc_group"], 10)
    for lst in (zone, region, national):
        for r in lst:
            r["activity"] = ACTIVITY_GROUPS[r.pop("cpc_group")]
    return {"zone_activity": zone, "region_activity": region, "national_activity": national}


def _write_csv(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols + ["evidence_type"])
        for r in rows:
            wr.writerow([("" if r.get(c) is None else (("%.6g" % r[c]) if isinstance(r[c], float) else r[c])) for c in cols] + ["COMPUTED"])


def write_outputs(result):
    """The Mzani wa Kodi file read by the dashboard, the Mzani cell tables and the taxable-capacity tables (aggregates only; every cell under the disclosure minimum is suppressed)."""
    mz = result["mzani"]
    doc = {"label": MZANI_LABEL, "type": "COMPUTED (survey data)", "coverage": MZANI_COVERAGE, "min_businesses_with_receipts_region_cell": int(CFG["mzani_min_region_cell"]),
           "fallback": "region cell (at least %d businesses with receipts) -> zone cell (at least %d) -> national cell" % (int(CFG["mzani_min_region_cell"]), disclosure.MIN_BASE),
           "presumptive_schedule": "config.yaml assumptions tax.presumptive_schedule (Finance Act 2026); above the TZS 200M ceiling the presumptive regime does not apply", "cpi": result["cpi"], **mz}
    os.makedirs(os.path.dirname(paths.MZANI_TURNOVER), exist_ok=True)
    with open(paths.MZANI_TURNOVER, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    cols = ["n_businesses", "n_with_receipts", "suppressed", "withheld", "p25_tzs", "median_tzs", "p75_tzs", "tax_at_p25_tzs", "tax_at_median_tzs", "tax_at_p75_tzs", "share_below_4m_pct", "share_4m_to_11m_pct", "share_above_11m_pct"]
    _write_csv(paths.MZANI_ZONE_CSV, mz["zone_activity"], ["zone", "activity"] + cols)
    _write_csv(paths.MZANI_REGION_CSV, mz["region_activity"], ["region", "activity"] + cols)
    cap, zcap = result["taxable_capacity"], result["taxable_capacity_by_zone"]
    ccols = ["group", "threshold_tzs", "n_unweighted", "n_above_unweighted", "share_pct", "adults_above_hbs_weighted_2017_18", "adults_above_at_finscope_scale", "low_precision", "suppressed"]
    _write_csv(paths.TAXABLE_CAPACITY_CSV, cap, ccols)
    _write_csv(paths.TAXABLE_CAPACITY_ZONE_CSV, zcap, ["zone", "threshold_tzs", "n_unweighted", "n_above_unweighted", "share_pct", "low_precision", "suppressed"])
    pick = lambda g, thr: next(r for r in cap if r["group"] == g and r["threshold_tzs"] == thr)
    summ = {"label": "COMPUTED from HBS 2017/18 microdata (Mainland); CPI-uprated to 2024; share of persons whose annual turnover from a household business exceeds the threshold", "type": "COMPUTED (survey data)",
            "thresholds_tzs": {"presumptive_start": 4e6, "top_rate_start": 11e6},
            "all_adults": {"share_above_4m_pct": pick("all adults", 4e6)["share_pct"], "share_above_11m_pct": pick("all adults", 11e6)["share_pct"],
                           "adults_above_4m_at_finscope_scale": pick("all adults", 4e6)["adults_above_at_finscope_scale"], "adults_above_11m_at_finscope_scale": pick("all adults", 11e6)["adults_above_at_finscope_scale"]},
            "business_owners": {"share_above_4m_pct": pick("business owners", 4e6)["share_pct"], "share_above_11m_pct": pick("business owners", 11e6)["share_pct"]},
            "owners_with_receipts_in_the_reference_month": {"share_above_4m_pct": pick("owners with receipts in the reference month", 4e6)["share_pct"], "share_above_11m_pct": pick("owners with receipts in the reference month", 11e6)["share_pct"]},
            "by_stage": {s: {"share_above_4m_pct": pick(s, 4e6).get("share_pct"), "share_above_11m_pct": pick(s, 11e6).get("share_pct"), "low_precision_4m": bool(pick(s, 4e6).get("low_precision")), "low_precision_11m": bool(pick(s, 11e6).get("low_precision"))} for s in STAGES},
            "by_zone": zcap, "notes": ["wage and salary income is not recorded in HBS 2017/18: the share of ADULTS above the thresholds counts business turnover only and understates taxable capacity from employment",
                                      "Mainland only; Zanzibar is not covered; farm businesses are outside section 10", "turnover is a survey estimate; a cell with fewer than %d respondents is suppressed and a numerator under %d is flagged low precision" % (disclosure.MIN_BASE, disclosure.MIN_BASE)]}
    with open(paths.TAXABLE_CAPACITY_JSON, "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=1, ensure_ascii=False)


def run_hbs_turnover(from_processed=False, json_path=None):
    json_path = json_path or paths.HBS_TURNOVER
    if from_processed:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    d, _ = load_frame()
    factor, cpi_s, cpi_t = cpi_factor()
    fs = {}
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            fs[r["segment"]] = float(r["population_weighted"])
    fs_pop = {s: fs[s] for s in STAGES if s in fs}
    stage_masks = {"active": (d["stage"] == "active"), "enterprise": (d["stage"] == "enterprise")}
    groups = {s: {"central_owners_with_receipts": group_stats(d, m, True), "low_all_owners": group_stats(d, m, False)} for s, m in stage_masks.items()}
    cap, zcap = taxable_capacity(d, fs_pop)
    mz = mzani_tables(d)
    stage_check = {s: {"hbs_weighted_adults_2017_18": float(d.loc[d["stage"] == s, "w"].sum()), "finscope_adults_2023": fs_pop.get(s), "n_unweighted": int((d["stage"] == s).sum())} for s in STAGES}
    result = {"label": LABEL, "type": "COMPUTED (survey data)", "source": "HBS 2017/18 (NBS), Individual file, Consumption Aggregate (weights), Form I S10C1; WDI FP.CPI.TOTL",
              "cpi": {"factor": factor, "cpi_survey_mean": cpi_s, "cpi_target": cpi_t, "survey_years": CFG["cpi_survey_years"], "target_year": CFG["cpi_target_year"]},
              "groups_mapping_B": groups, "taxable_capacity": cap, "taxable_capacity_by_zone": zcap, "stage_population_check": stage_check, "mzani": mz,
              "owners": {"n_unweighted": int(d["owner"].sum()), "weighted": float(d.loc[d["owner"], "w"].sum()), "share_with_receipts_pct": _wmean(d.loc[d["owner"], "reported"], d.loc[d["owner"], "w"]) * 100},
              "notes": ["wage and salary income is not recorded in HBS 2017/18: non-owners have no taxable turnover here", "Mainland only; Zanzibar is not covered", "farmers and fishers have no counterpart (farm businesses are outside section 10)",
                        "58% of owners had no receipts in the reference month: the 'all owners' basis keeps them at zero (low case); the central case uses owners with receipts"]}
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    write_outputs(result)
    return result


if __name__ == "__main__":
    run_hbs_turnover()
