"""
FinScope Tanzania 2023 region x business-activity prevalence loader
(standalone copy for this project -- the original lives in a separate
project and has the full investigation notes on why this is a prevalence table, not a turnover
calculator).

Differs from the original only in HOW it persists: the original writes
to that project's shared evidence_store.db via evidence_db.py's
helpers (appropriate there, since that database is the shared home for
every survey this project loads). This standalone copy has no such
database -- it exists purely to serve this one dashboard -- so it writes
directly to JSON instead of round-tripping through SQLite. Same
computation, same real FinScope data, simpler plumbing.

Investigated before writing (not assumed):
  - D5 (the codebook's only variable with an explicit "business
    activity" value list) is answered by only 496 of 9,915 respondents
    -- a narrow services-only sub-question, too sparse for a real
    regional cross-tab.
  - IncomeMain is populated for the full sample and already
    distinguishes trading/farming/service livelihood categories -- the
    real, usable "activity" dimension.
  - No turnover or income-AMOUNT variable exists anywhere in FinScope
    2023 (checked every codebook label and raw column name).
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
OUTPUT_PATH = paths.FINSCOPE_REGION_ACTIVITY

# The four IncomeMain categories that represent an actual own-account
# economic activity a presumptive-tax calculator would apply to.
BUSINESS_ACTIVITY_CATEGORIES = [
    "Traders - non-agricultural",
    "Traders - agricultural products",
    "Service providers",
    "Farmers and fishers",
]


def build_finscope_region_activity_data(csv_path=CSV_PATH, output_path=OUTPUT_PATH):
    """
    Computes a Household_weight-weighted region x business-activity
    prevalence table from FinScope 2023 microdata and writes it to
    output_path as JSON. Returns the same dict it wrote.
    """
    print("\n  Building FinScope region x activity prevalence...")
    if not os.path.exists(csv_path):
        print(f"  ✗ {csv_path} not found")
        return None

    df = pd.read_csv(
        csv_path, usecols=["reg_name", "IncomeMain", HOUSEHOLD_WEIGHT_VAR],
        low_memory=False,
    )
    biz = df[df["IncomeMain"].isin(BUSINESS_ACTIVITY_CATEGORIES)].copy()
    if biz.empty:
        print("  ✗ no business-activity respondents found -- check IncomeMain values")
        return None

    rows = []
    for region, region_df in biz.groupby("reg_name"):
        region_total_weight = region_df[HOUSEHOLD_WEIGHT_VAR].sum()
        for activity, activity_df in region_df.groupby("IncomeMain"):
            weighted_pop = activity_df[HOUSEHOLD_WEIGHT_VAR].sum()
            pct = (weighted_pop / region_total_weight * 100) if region_total_weight else 0.0
            row = {
                "region": region,
                "activity": activity,
                "weighted_population": float(weighted_pop),
                "pct_of_region_business_activity": round(float(pct), 2),
                "respondent_count": int(len(activity_df)),
            }
            # disclosure rule (config.yaml disclosure): fewer than min_base respondents -> estimate and count withheld
            if disclosure.is_suppressed(row["respondent_count"]):
                disclosure.suppress(row, ["weighted_population", "pct_of_region_business_activity", "respondent_count"])
            rows.append(row)

    # E6: the same prevalence one level up (zone, national), for the dashboard's fallback when a region cell is suppressed
    zone_of = {r: z for z, regs in paths.CFG["zones"]["regions"].items() for r in regs}
    biz["zone"] = biz["reg_name"].map(zone_of)
    zone_rows, national_rows = [], []
    for zone, zone_df in biz.groupby("zone"):
        zone_total = zone_df[HOUSEHOLD_WEIGHT_VAR].sum()
        for activity, activity_df in zone_df.groupby("IncomeMain"):
            row = {"zone": zone, "activity": activity, "weighted_population": float(activity_df[HOUSEHOLD_WEIGHT_VAR].sum()),
                   "pct_of_zone_business_activity": round(float(activity_df[HOUSEHOLD_WEIGHT_VAR].sum() / zone_total * 100), 2), "respondent_count": int(len(activity_df))}
            if disclosure.is_suppressed(row["respondent_count"]):
                disclosure.suppress(row, ["weighted_population", "pct_of_zone_business_activity", "respondent_count"])
            zone_rows.append(row)
    nat_total = biz[HOUSEHOLD_WEIGHT_VAR].sum()
    for activity, activity_df in biz.groupby("IncomeMain"):
        row = {"level": "national", "activity": activity, "weighted_population": float(activity_df[HOUSEHOLD_WEIGHT_VAR].sum()),
               "pct_of_national_business_activity": round(float(activity_df[HOUSEHOLD_WEIGHT_VAR].sum() / nat_total * 100), 2), "respondent_count": int(len(activity_df))}
        if disclosure.is_suppressed(row["respondent_count"]):
            disclosure.suppress(row, ["weighted_population", "pct_of_national_business_activity", "respondent_count"])
        national_rows.append(row)

    out = {
        "source": "FinScope Tanzania 2023 (n=9,915, weighted by Household_weight)",
        "methodology": (
            "Weighted prevalence of four business-activity IncomeMain categories "
            "(Traders - non-agricultural, Traders - agricultural products, Service "
            "providers, Farmers and fishers) within each region. This is a "
            "population-share table, not a turnover/income-amount distribution -- "
            "FinScope 2023 contains no turnover or income-amount variable, checked "
            "exhaustively against the codebook and raw columns."
        ),
        "disclosure_rule": "cells with fewer than %d unweighted respondents are suppressed (estimate and count null, suppressed: true)" % disclosure.MIN_BASE,
        "rows": rows,
        "zone_rows": zone_rows,
        "national_rows": national_rows,
        "zones": {"source": paths.CFG["zones"]["source"], "url": paths.CFG["zones"]["url"]},
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    n_supp = sum(1 for r in rows if r.get("suppressed"))
    print(f"  ✓ {len(rows)} region x activity rows written to {output_path} "
          f"({biz['reg_name'].nunique()} regions x {len(BUSINESS_ACTIVITY_CATEGORIES)} activities; {n_supp} suppressed)")
    return out


if __name__ == "__main__":
    build_finscope_region_activity_data()
