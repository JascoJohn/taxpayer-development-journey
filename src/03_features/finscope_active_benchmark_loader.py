"""
FinScope Tanzania 2023 region x business-activity benchmark loader,
for the Active stage's Mzani wa Kodi tool.

Extends finscope_region_activity_loader.py's region x IncomeMain
cross-tab (same four business-activity categories, same regions) with
two more real, respondent-level fields per cell:

  - fasx: FinScope's own financial access strand -- Banked / Other
    formal non-bank / Informal only / Excluded. This is FinScope's
    flagship, internationally standard measure of financial/economic
    engagement -- the closest real, respondent-level proxy this
    dataset has for "how economically active is this business," in
    the total absence of any income or turnover variable.
  - D6_4a: business registration status (Yes/No; a small number of
    blank responses exist and are excluded from the registered-rate
    denominator rather than silently counted as "No").

Investigated before writing (not assumed):
  - Confirmed FinScope 2023 has no income-AMOUNT or turnover variable
    anywhere (see finscope_region_activity_loader.py's own
    investigation notes) -- which is exactly why this loader outputs a
    strand *distribution* and a registration *rate* per cell, never a
    shilling figure. Turning either of those into a presumptive-tax
    category is an illustrative interpretive step, done downstream in
    tdj_lib/benchmark_adapters.py (clearly tagged as such there), not
    a claim made by this file.
  - Per-cell sample sizes are small: median respondent_count across
    the 124 region x activity cells is 14, and 42 of 124 cells have
    fewer than 10 respondents. This loader does not hide that --
    respondent_count is written to every row so the dashboard can
    (and does) refuse an estimate when a cell is too thin, rather than
    presenting a confident-looking number built on a handful of people.
"""

import os
import json

import pandas as pd

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import run_meta
import disclosure
from finscope_segments import HOUSEHOLD_WEIGHT_VAR
CSV_PATH = paths.FINSCOPE_CSV
OUTPUT_PATH = paths.FINSCOPE_ACTIVE_BENCHMARK

# Same four categories as finscope_region_activity_loader.py -- the
# IncomeMain values that represent an actual own-account economic
# activity a presumptive-tax tool would apply to.
BUSINESS_ACTIVITY_CATEGORIES = [
    "Traders - non-agricultural",
    "Traders - agricultural products",
    "Service providers",
    "Farmers and fishers",
]

STRAND_CATEGORIES = ["Banked", "Other formal non-bank", "Informal only", "Excluded"]


def _cell_row(df, cell_df, cell_mask, ident):
    """One benchmark cell (region, zone or national) for the given respondents, with the disclosure rule applied.
    Returns None when the cell has no weight."""
    cell_weight = cell_df[HOUSEHOLD_WEIGHT_VAR].sum()
    if cell_weight <= 0:
        return None

    strand_pct = {}
    for strand in STRAND_CATEGORIES:
        strand_mask = cell_df["fasx"].astype(str).str.strip() == strand
        strand_weight = cell_df.loc[strand_mask, HOUSEHOLD_WEIGHT_VAR].sum()
        strand_pct[strand] = round(float(strand_weight / cell_weight * 100), 1)

    # D6_4a has a small number of blank/whitespace responses in
    # the raw data (not just Yes/No) -- excluded from the
    # denominator rather than folded into "not registered".
    reg_valid = cell_df[cell_df["D6_4a"].astype(str).str.strip().isin(["Yes", "No"])]
    reg_valid_weight = reg_valid[HOUSEHOLD_WEIGHT_VAR].sum()
    registered_weight = reg_valid.loc[
        reg_valid["D6_4a"].astype(str).str.strip() == "Yes", HOUSEHOLD_WEIGHT_VAR
    ].sum()
    registered_pct = (
        round(float(registered_weight / reg_valid_weight * 100), 1)
        if reg_valid_weight > 0 else None
    )

    row = dict(ident)
    row.update({
        "respondent_count": int(len(cell_df)),
        "weighted_population": float(cell_weight),
        "strand_distribution_pct": strand_pct,
        "registered_pct": registered_pct,
        "registered_respondent_count": int(len(reg_valid)),
    })
    # ---- disclosure rule (config.yaml disclosure) ----
    if disclosure.is_suppressed(row["respondent_count"]):
        disclosure.suppress(row, ["respondent_count", "weighted_population", "strand_distribution_pct",
                                  "registered_pct", "registered_respondent_count"])
        return row
    low, ci = [], {}
    fasx = df["fasx"].astype(str).str.strip()
    for strand in STRAND_CATEGORIES:
        numerator = int((cell_df["fasx"].astype(str).str.strip() == strand).sum())
        if disclosure.is_low_precision(row["respondent_count"], numerator):
            low.append("strand_distribution_pct:" + strand)
            ci["strand_distribution_pct:" + strand] = disclosure.ci95_domain_pct(df, HOUSEHOLD_WEIGHT_VAR, cell_mask, fasx == strand)
    reg_status = df["D6_4a"].astype(str).str.strip()
    if disclosure.is_suppressed(len(reg_valid)):
        disclosure.suppress_fields(row, ["registered_pct", "registered_respondent_count"])
    else:
        yes = int((reg_valid["D6_4a"].astype(str).str.strip() == "Yes").sum())
        if disclosure.is_low_precision(len(reg_valid), yes):
            low.append("registered_pct")
            ci["registered_pct"] = disclosure.ci95_domain_pct(df, HOUSEHOLD_WEIGHT_VAR, cell_mask & reg_status.isin(["Yes", "No"]), reg_status == "Yes")
    if low:
        disclosure.flag_low_precision(row, low, ci)
    return row


def build_finscope_active_benchmark_data(csv_path=CSV_PATH, output_path=OUTPUT_PATH):
    """
    Computes a Household_weight-weighted region x business-activity
    benchmark table -- sample size, weighted population, financial
    access strand distribution, and registration rate per cell -- from
    FinScope 2023 microdata, and writes it to output_path as JSON.
    Returns the same dict it wrote.
    """
    print("\n  Building FinScope Active-stage benchmark cells...")
    if not os.path.exists(csv_path):
        print(f"  ERROR: {csv_path} not found")
        return None

    df = pd.read_csv(
        csv_path,
        usecols=["reg_name", "IncomeMain", HOUSEHOLD_WEIGHT_VAR, "fasx", "D6_4a",
                 "reg_code", "dist_code", "ward_code1", "ea_code", "clustertype"],   # design columns: confidence intervals
        low_memory=False,
    )
    zone_of = {r: z for z, regs in paths.CFG["zones"]["regions"].items() for r in regs}
    df["zone"] = df["reg_name"].map(zone_of)
    biz = df[df["IncomeMain"].isin(BUSINESS_ACTIVITY_CATEGORIES)].copy()
    if biz.empty:
        print("  ERROR: no business-activity respondents found -- check IncomeMain values")
        return None
    unmapped = sorted(set(df["reg_name"]) - set(zone_of))
    if unmapped:
        raise SystemExit("regions without a zone in config.yaml zones.regions: %s" % unmapped)

    rows = []
    for region, region_df in biz.groupby("reg_name"):
        for activity, cell_df in region_df.groupby("IncomeMain"):
            row = _cell_row(df, cell_df, (df["reg_name"] == region) & (df["IncomeMain"] == activity), {"region": region, "activity": activity})
            if row is not None:
                rows.append(row)
    # E6: the same cells one level up, for the dashboard's fallback when a region cell is suppressed (zone first, then national)
    zone_rows = []
    for zone, zone_df in biz.groupby("zone"):
        for activity, cell_df in zone_df.groupby("IncomeMain"):
            row = _cell_row(df, cell_df, (df["zone"] == zone) & (df["IncomeMain"] == activity), {"zone": zone, "activity": activity})
            if row is not None:
                zone_rows.append(row)
    national_rows = []
    for activity, cell_df in biz.groupby("IncomeMain"):
        row = _cell_row(df, cell_df, (df["IncomeMain"] == activity), {"level": "national", "activity": activity})
        if row is not None:
            national_rows.append(row)

    out = {
        "source": "FinScope Tanzania 2023 (n=9,915, weighted by Household_weight)",
        "methodology": (
            "For each region x business-activity (IncomeMain) cell: real "
            "respondent count and weighted population (same cells as "
            "finscope_region_activity.json), the weighted distribution across "
            "FinScope's own financial access strand (fasx: Banked / Other "
            "formal non-bank / Informal only / Excluded), and the weighted "
            "business-registration rate (D6_4a). No income, turnover, or "
            "revenue amount is estimated anywhere in this file -- FinScope "
            "2023 has no such variable. Any mapping from these real cell "
            "characteristics to a presumptive-tax category is an illustrative "
            "interpretive step performed downstream by the dashboard, not a "
            "claim made by this loader."
        ),
        "strand_categories": STRAND_CATEGORIES,
        "disclosure_rule": ("cells (region, zone and national) with fewer than %d unweighted respondents are suppressed (all estimates and counts null); registration rates with fewer than %d "
                            "valid answers are suppressed; estimates whose unweighted numerator is below %d are kept and flagged low_precision with a 95%% CI "
                            "(reconstructed design)") % (disclosure.MIN_BASE, disclosure.MIN_BASE, disclosure.LOW_PRECISION_NUMERATOR),
        "rows": rows,
        "zone_rows": zone_rows,
        "national_rows": national_rows,
        "zones": {"source": paths.CFG["zones"]["source"], "url": paths.CFG["zones"]["url"],
                  "note": "the dashboard shows the zone cell when a region cell is suppressed (fewer than %d respondents), and the national cell when the zone cell is suppressed too" % disclosure.MIN_BASE},
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    n_supp = sum(1 for r in rows if r.get("suppressed"))
    n_low = sum(1 for r in rows if r.get("low_precision"))
    print(f"  OK: {len(rows)} region x activity benchmark cells written to {output_path} "
          f"({n_supp} suppressed, {n_low} flagged low precision)")
    print(f"      zone x activity: {len(zone_rows)} cells ({sum(1 for r in zone_rows if r.get('suppressed'))} suppressed); "
          f"national x activity: {len(national_rows)} cells ({sum(1 for r in national_rows if r.get('suppressed'))} suppressed)")
    return out


if __name__ == "__main__":
    build_finscope_active_benchmark_data()
