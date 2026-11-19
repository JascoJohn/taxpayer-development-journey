"""
economic_model.py
═══════════════════════════════════════════════════════════════
Tanzania Policy Design Agent — Economic Model
═══════════════════════════════════════════════════════════════

This file transforms the pipeline from a revenue calculator
into a policy AI. It contains:

A. Core revenue calculations (fixed formulas, auditable)
B. Monte Carlo simulation (1,000 iterations, CI ranges)
C. Tax morale model (behavioral compliance layer)
D. Agent-based simulation (500,000 synthetic citizens)
E. (retired in Block F0: the intervention optimizer)
F. (retired in Pass 6B-1: the digital twin; see src/retired/)
G. Causal inference layer (true intervention effects)
H. Cost-benefit calculator (ROI per intervention)
I. Sensitivity analysis (assumption stress testing)
J. Compliance funnel model (FinScope-grounded)

Every number traces to a formula.
Every formula states its assumptions.
No LLM estimates anywhere in this file.

DEPENDENCIES
------------
pip install numpy scipy scikit-learn
"""

import os
import json
import math
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import numpy as np
from scipy import stats
from assumption_ledger import log_assumption

# ── sklearn imports with graceful fallback ───────────────────
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("  sklearn not available — ML model will be skipped")

# ============================================================
# CONFIGURATION
# ============================================================
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import run_meta
from assumptions import A
from finscope_segments import LIFECYCLE_STAGES, ML_SEGMENT_STAGES, SEED_AGE_MIN, SEED_AGE_MAX
from census_population import seed_population_from_processed
import statutory_tax as stat
FINSCOPE_SUMMARY_FILE = paths.FINSCOPE_SUMMARY
ECONOMIC_MODEL_OUTPUT = paths.ECONOMIC_MODEL
RANDOM_SEED           = paths.RANDOM_SEED
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# ============================================================
# BASE PARAMETERS
# Updated with real FinScope data where available
# ============================================================
def load_base_params():
    """
    Loads base parameters, preferring FinScope-measured
    values over estimates where available.
    """
    params = {
        # ── Economy ───────────────────────────────────────────
        # gdp_usd, tzs_per_usd, tax_to_gdp_current and tax_to_gdp_target come from outputs/stats/macro_inputs.json
        # (World Bank WDI snapshots; load_macro_params below). The typed 78.84B, 2,500, 0.128, 0.165 are gone.
        "gdp_growth_rate":      A("base.gdp_growth_rate"),
        "population":           A("base.population"),

        # ── Taxpayer base (TRA 2023) ─────────────────────────
        "registered_taxpayers": A("base.registered_taxpayers"),
        "working_age_population": A("base.working_age_population"),
        "informal_workers_pct": 0.92,
        "formal_workers_pct":   0.08,

        # ── Mobile money (FinScope 2023 adult users, Block E3.3; BoT's account count is a context figure only) ──
        "adult_population":     A("base.adult_population"),
        "mobile_money_users":   A("base.mobile_money_users"),
        "mobile_money_gdp_pct": A("base.mobile_money_gdp_pct"),

        # ── Lifecycle populations (FinScope 2023 defaults) ───
        # These are overwritten by load_finscope_params()
        # Seed (ages seed_age_band in config.yaml) is set by load_census_params() from the 2022 Census 10% sample
        "seed_stage_population":       None,
        "entry_stage_population":      10_605_005,
        "active_stage_population":      2_916_165,      # stage mapping B (Pass 6B-1): informal business owners 25-64
        "enterprise_stage_population":    572_735,      # stage mapping B: owners with a formal step, 25-64
        "workers_stage_population":    12_110_886,      # stage mapping B: non-owners 25-44, no revenue lever
        "asset_stage_population":       5_590_836,
        "legacy_stage_population":      2_338_624,

        # ── FinScope compliance metrics (defaults) ───────────
        "tin_rate_pct":         3.8,
        "mm_penetration_pct":   71.6,
        "mm_no_tin_count":      23_140_012,
        "tin_gap":              32_827_568,

        # ── Average incomes by segment (TZS/year) ────────────
        "informal_worker_avg_income_tzs": A("base.informal_worker_avg_income_tzs"),
        "msme_avg_revenue_tzs":          A("base.msme_avg_revenue_tzs"),
        "mobile_money_avg_transaction":     150_000,

        # ── Tax rates ────────────────────────────────────────
        # Block F1: the flat 15% and 3% rates are retired; the tax of a new taxpayer is the statutory schedule applied to the DISTRIBUTION of ILFS 2024 earnings (src/04_models/statutory_tax.py)
        "mean_tax_informal_tzs":    A("base.new_taxpayer_mean_tax_tzs"),
        "mean_tax_msme_tzs":        A("base.msme_mean_presumptive_tax_tzs"),
        "property_tax_rate":        0.001,
        "property_tax_target_rate": 0.005,

        # ── Property ─────────────────────────────────────────
        "urban_property_untaxed_pct":    0.60,
        "urban_property_value_tzs": 50_000_000_000_000,

        # ── Scenario capture rates ───────────────────────────
        "conservative_capture": 0.30,
        "moderate_capture":     0.60,
        "ambitious_capture":    0.90,

        # ── Behavioral uplift ────────────────────────────────
        # 1.35x = behavioral interventions produce 35% more
        # compliance than enforcement alone
        # Source: Rwanda RRA behavioral study,
        #         UK HMRC behavioral insights unit
        "behavioral_uplift": 1.35,

        # ── Tax morale baseline scores (0-1) ─────────────────
        "baseline_trust":       A("tax_morale.baseline.trust"),
        "baseline_simplicity":  A("tax_morale.baseline.simplicity"),
        "baseline_enforcement": A("tax_morale.baseline.enforcement"),
        "baseline_social_norm": A("tax_morale.baseline.social_norm"),
        "baseline_fairness":    A("tax_morale.baseline.fairness"),
    }

    # Load FinScope real values if available
    params = load_finscope_params(params)
    params = load_exemption_params(params)
    params = load_census_params(params)
    params = load_macro_params(params)
    return params


def load_macro_params(params):
    """
    GDP, tax-to-GDP, benchmark and exchange rate from outputs/stats/macro_inputs.json, written by
    src/03_features/macro_inputs.py from the World Bank WDI snapshots named in config.yaml (no typed fallback: a missing
    file stops the run). tax_to_gdp_current is Tanzania's latest ratio (2024); tax_to_gdp_target is the benchmark chosen by
    config.yaml macro.benchmark_source (default: the peer average in the latest year all five countries report).
    """
    if not os.path.exists(paths.MACRO_INPUTS):
        raise FileNotFoundError(
            "%s not found: run src/03_features/macro_inputs.py (run_all.py does it before the economic model)" % paths.MACRO_INPUTS)
    with open(paths.MACRO_INPUTS, "r", encoding="utf-8") as f:
        mi = json.load(f)
    tz, bm = mi["tanzania"], mi["benchmark"]
    params["gdp_usd"]            = tz["gdp_usd"]
    params["tzs_per_usd"]        = tz["fx_tzs_per_usd"]
    params["tax_to_gdp_current"] = tz["tax_to_gdp_pct"] / 100.0
    params["tax_to_gdp_target"]  = bm["benchmark_pct"] / 100.0
    params["macro"] = {
        "tanzania_year": tz["latest_year"],
        "tanzania_tax_revenue_tzs": tz["tax_revenue_tzs"],
        "tanzania_tax_revenue_usd": tz["tax_revenue_usd"],
        "benchmark_policy": bm["policy"],
        "benchmark_year": bm["year"],
        "tanzania_same_year_pct": bm["tanzania_same_year_pct"],
        "gap_pp": bm["gap_pp"],
        "revenue_gap_tzs": bm["revenue_gap_tzs"],
        "revenue_gap_usd": bm["revenue_gap_usd"],
        "target_tax_revenue_tzs": bm["target_tax_revenue_tzs"],
        "target_tax_revenue_usd": bm["target_tax_revenue_usd"],
    }
    return params


def load_census_params(params):
    """
    Seed-stage population for the configured age band (config.yaml seed_age_band, 6-15), COMPUTED from the 2022 Census
    10% sample by src/03_features/census_population.py (x10 expansion) and read from data/processed/census_age_counts.json.
    There is no typed fallback (it was 15,000,000): a missing file stops the run.
    """
    seed = seed_population_from_processed()
    if seed is None:
        raise FileNotFoundError(
            "%s not found: run src/03_features/census_population.py (run_all.py does it before the economic model)"
            % paths.CENSUS_AGE_COUNTS)
    params["seed_stage_population"] = seed
    params["seed_age_band"] = [SEED_AGE_MIN, SEED_AGE_MAX]
    return params


def load_finscope_params(params):
    """
    Overwrites estimated lifecycle populations with
    real FinScope 2023 survey-measured values.
    """
    if not os.path.exists(FINSCOPE_SUMMARY_FILE):
        return params

    with open(FINSCOPE_SUMMARY_FILE, "r",
              encoding="utf-8") as f:
        fs = json.load(f)

    by_stage = fs.get("by_stage", {})

    mapping = {s: s + "_stage_population" for s in LIFECYCLE_STAGES if s != "seed"}

    for stage_key, param_key in mapping.items():
        stage_data = by_stage.get(stage_key, {})
        pop = stage_data.get("population", 0)
        if pop > 0:
            params[param_key] = int(pop)

    # Core compliance metrics
    params["tin_rate_pct"]       = fs.get("tin_rate", 3.8)
    params["mm_penetration_pct"] = fs.get("mm_rate", 71.6)
    params["mm_no_tin_count"]    = fs.get("mm_no_tin", 23_140_012)
    params["tin_gap"]            = fs.get("tin_gap", 32_827_568)

    # Pension and insurance for legacy/asset stages
    pen_ins = fs.get("pension_insurance", {})
    params["pension_coverage_pct"]   = pen_ins.get(
        "pension_coverage_pct", 3.8
    )
    params["insurance_coverage_pct"] = pen_ins.get(
        "insurance_coverage_pct", 9.6
    )

    return params


def load_exemption_params(params):
    """
    Sets the tax exemption/relief rate for the compliance funnel's Payment stage.

    The rates are read from outputs/stats/tax_exemption_rate.json, written by
    src/03_features/tax_exemptions.py from the Ministry of Finance workbook
    (FY2023/24 Q1; ONE QUARTER, Jul-Sep 2023). The funnel uses the DOMESTIC
    reliefs rate (domestic taxes only: the funnel describes domestic filers);
    the TOTAL rate (domestic plus customs and excise, 8.77% when rounded) is
    kept as a sensitivity case. There is no typed fallback: a missing file
    stops the run, so that no number is ever silently replaced.
    """
    if not os.path.exists(paths.TAX_EXEMPTION_RATE):
        raise FileNotFoundError(
            "%s not found: run src/03_features/tax_exemptions.py (run_all.py does it before the economic model)"
            % paths.TAX_EXEMPTION_RATE)
    with open(paths.TAX_EXEMPTION_RATE, "r", encoding="utf-8") as f:
        ex = json.load(f)
    params["exemption_pct_of_collection"] = ex["funnel_rate_pct"]
    params["exemption_rate_basis"] = ex["funnel_rate"]
    params["exemption_pct_total_sensitivity"] = ex["sensitivity_rate_pct"]
    params["exemption_period"] = ex["period"]
    return params


# ============================================================
# A. CORE REVENUE CALCULATIONS
# ============================================================

def calculate_current_tax_base(params):
    """
    Tanzania's current tax base metrics.
    Starting point for all expansion calculations.

    Inputs come from macro_inputs.json (WDI). Current revenue = Tanzania's latest tax-to-GDP ratio x GDP in TZS of that year.
    The revenue gap = (benchmark - Tanzania, SAME year) x GDP in TZS of that year (no exchange-rate step); US$ figures
    use the official exchange rate of the same year.
    """
    m = params["macro"]
    current_rev_tzs = m["tanzania_tax_revenue_tzs"]
    current_rev_usd = m["tanzania_tax_revenue_usd"]
    target_rev_usd  = m["target_tax_revenue_usd"]
    gap_usd         = m["revenue_gap_usd"]
    gap_tzs         = m["revenue_gap_tzs"]

    return {
        "current_tax_revenue_usd":    round(current_rev_usd, 0),
        "current_tax_revenue_tzs":    round(current_rev_tzs, 0),
        "revenue_per_taxpayer_tzs":   round(
            current_rev_tzs / params["registered_taxpayers"], 0
        ),
        "revenue_per_working_age_tzs": round(
            current_rev_tzs / params["working_age_population"], 0
        ),
        "target_tax_revenue_usd":     round(target_rev_usd, 0),
        "revenue_gap_usd":            round(gap_usd, 0),
        "revenue_gap_tzs":            round(gap_tzs, 0),
        "revenue_gap_pct_gdp":        round(m["gap_pp"], 2),
        "benchmark_policy":           m["benchmark_policy"],
        "benchmark_year":             m["benchmark_year"],
        "assumptions": {
            "gdp_usd":              params["gdp_usd"],
            "tax_to_gdp_current":   params["tax_to_gdp_current"],
            "tax_to_gdp_target":    params["tax_to_gdp_target"],
            "tax_to_gdp_current_in_benchmark_year": m["tanzania_same_year_pct"] / 100.0,
            "registered_taxpayers": params["registered_taxpayers"],
            "source": "World Bank WDI snapshots via outputs/stats/macro_inputs.json (tax-to-GDP of Tanzania %d; benchmark %s, %d)" % (
                m["tanzania_year"], m["benchmark_policy"], m["benchmark_year"])
        }
    }


def calculate_lifecycle_stage_potential(
    stage_name, population, avg_income_tzs,
    tax_pp, capture_rate, params,
    years=10, with_behavioral=True
):
    """
    Revenue potential for one lifecycle stage.
    All parameters explicit and auditable.
    """
    capturable  = round(population * capture_rate)
    annual_rev  = capturable * tax_pp

    if with_behavioral:
        annual_rev *= params["behavioral_uplift"]

    annual_rev_usd = annual_rev / params["tzs_per_usd"]
    growth = params["gdp_growth_rate"]
    cumulative = sum(
        annual_rev * math.pow(1 + growth, yr)
        for yr in range(years)
    )
    gdp_tzs = params["gdp_usd"] * params["tzs_per_usd"]

    return {
        "stage":                     stage_name,
        "capturable_population":     capturable,
        "annual_tax_per_person_tzs": round(tax_pp, 0),
        "annual_revenue_tzs":        round(annual_rev, 0),
        "annual_revenue_usd":        round(annual_rev_usd, 0),
        "cumulative_10yr_tzs":       round(cumulative, 0),
        "tax_gdp_impact_pct":        round(
            annual_rev / gdp_tzs * 100, 3
        ),
        "behavioral_uplift_applied": with_behavioral,
        "assumptions": {
            "population":        population,
            "avg_income_tzs":    avg_income_tzs,
            "tax_per_person_tzs": tax_pp,
            "effective_tax_rate": (tax_pp / avg_income_tzs) if avg_income_tzs else None,
            "capture_rate":      capture_rate,
            "behavioral_uplift": params["behavioral_uplift"]
                                 if with_behavioral else 1.0,
            "growth_rate":       params["gdp_growth_rate"],
            "years":             years
        }
    }


def calculate_mobile_money_opportunity(params):
    """
    Revenue from formalizing mobile money taxation.
    Tanzania's single largest untapped opportunity.
    """
    mm_value_tzs = (
        params["gdp_usd"] * params["tzs_per_usd"] *
        params["mobile_money_gdp_pct"]
    )
    levy_rate     = 0.005   # Conservative 0.5% levy
    capture_pct   = 0.05    # Current capture rate
    current_tax   = mm_value_tzs * capture_pct * 0.01
    full_potential = mm_value_tzs * levy_rate
    additional    = full_potential - current_tax

    return {
        "mobile_money_value_tzs":          round(mm_value_tzs, 0),
        "current_tax_captured_tzs":        round(current_tax, 0),
        "full_potential_tzs":              round(full_potential, 0),
        "additional_revenue_tzs":          round(additional, 0),
        "additional_revenue_usd":          round(
            additional / params["tzs_per_usd"], 0
        ),
        "per_user_annual_contribution_tzs": round(
            additional / params["mobile_money_users"], 0
        ),
        "assumptions": {
            "levy_rate":           levy_rate,
            "current_capture_pct": capture_pct,
            "note": "Kenya charges 0.3% excise on MM transfers"
        }
    }


def calculate_property_tax_opportunity(params):
    """
    Revenue from property tax reform.
    Tanzania at 0.1% of GDP vs Africa average 0.5%.
    """
    gdp_tzs     = params["gdp_usd"] * params["tzs_per_usd"]
    current_pt  = gdp_tzs * 0.001
    target_pt   = gdp_tzs * 0.005
    additional  = target_pt - current_pt
    urban_opp   = (
        params["urban_property_value_tzs"] *
        params["urban_property_untaxed_pct"] *
        params["property_tax_target_rate"]
    )

    return {
        "current_property_tax_tzs":      round(current_pt, 0),
        "target_property_tax_tzs":       round(target_pt, 0),
        "additional_revenue_tzs":        round(additional, 0),
        "additional_revenue_usd":        round(
            additional / params["tzs_per_usd"], 0
        ),
        "urban_untaxed_opportunity_tzs": round(urban_opp, 0),
        "assumptions": {
            "current_rate_gdp": "0.1%",
            "target_rate_gdp":  "0.5% (Africa average)",
            "source": "OECD Revenue Statistics Africa 2023"
        }
    }


def run_scenario_analysis(params):
    """
    Three-scenario analysis: conservative, moderate, ambitious.
    Uses real FinScope lifecycle populations.
    """
    scale = params.get("income_scale", 1.0)                       # earnings scale of the sensitivity grid (1.0 in the published run)
    stages_config = [
        {
            "name": "Seed Stage",
            "population": params["seed_stage_population"],
            "avg_income": 0,
            "tax_pp": 0,
            "note": "Foundation — no direct revenue"
        },
        {
            "name": "Entry Stage",
            "population": params["entry_stage_population"],
            "avg_income": params["informal_worker_avg_income_tzs"] * 0.7 * scale,
            "tax_pp": stat.informal_mean_tax(0.7 * scale),
            "finscope_mm_pct": 60.2,
            "finscope_tin_pct": 0.8,
        },
        {
            "name": "Active Stage",
            "population": params["active_stage_population"],
            "avg_income": params["informal_worker_avg_income_tzs"] * scale,
            "tax_pp": stat.informal_mean_tax(scale),
            "finscope_mm_pct": None,   # the former mapping's 77.7 does not describe this group; not recomputed here (Pass 6B-1)
            "finscope_tin_pct": 6.4,   # mapping B, FinScope 2023 (outputs/tin_by_segment.csv)
        },
        {
            "name": "Enterprise Stage",
            "population": params["enterprise_stage_population"],
            "avg_income": params["msme_avg_revenue_tzs"] * scale,
            "tax_pp": stat.msme_mean_tax(scale),
            "finscope_mm_pct": None,   # former mapping's 91.7 retired
            "finscope_tin_pct": 26.5,  # mapping B, FinScope 2023
        },
        {
            "name": "Workers 25-44 (no revenue lever)",
            "population": params["workers_stage_population"],
            "avg_income": 0,
            "tax_pp": 0,
            "note": "no revenue lever (stage mapping B)",
            "finscope_mm_pct": None,
            "finscope_tin_pct": 4.6,
        },
        {
            "name": "Asset Stage",
            "population": params["asset_stage_population"],
            "avg_income": (
                params["urban_property_value_tzs"] /
                params["asset_stage_population"]
            ),
            "tax_pp": (params["urban_property_value_tzs"] / params["asset_stage_population"]) * params["property_tax_target_rate"],
            "finscope_mm_pct": 75.8,
            "finscope_tin_pct": 4.3,
        },
    ]

    scenarios = {}

    for scenario_name, capture_rate in [
        ("conservative", params["conservative_capture"]),
        ("moderate",     params["moderate_capture"]),
        ("ambitious",    params["ambitious_capture"]),
    ]:
        print(f"  Calculating {scenario_name} scenario "
              f"(capture rate: {capture_rate*100:.0f}%)...")

        stage_results      = []
        total_annual_tzs   = 0
        total_new_taxpayers = 0

        for stage in stages_config:
            if stage["avg_income"] == 0:
                stage_results.append({
                    "stage":             stage["name"],
                    "annual_revenue_tzs": 0,
                    "note":              stage.get("note", "")
                })
                continue

            result = calculate_lifecycle_stage_potential(
                stage_name=stage["name"],
                population=stage["population"],
                avg_income_tzs=stage["avg_income"],
                tax_pp=stage["tax_pp"],
                capture_rate=capture_rate,
                params=params,
                with_behavioral=True
            )
            stage_results.append(result)
            total_annual_tzs   += result["annual_revenue_tzs"]
            total_new_taxpayers += result["capturable_population"]

        mm   = calculate_mobile_money_opportunity(params)
        prop = calculate_property_tax_opportunity(params)
        mm_scaled   = mm["additional_revenue_tzs"]   * capture_rate
        prop_scaled = prop["additional_revenue_tzs"]  * capture_rate
        total_annual_tzs += mm_scaled + prop_scaled

        current  = calculate_current_tax_base(params)
        gdp_tzs  = params["gdp_usd"] * params["tzs_per_usd"]
        new_total = (
            current["current_tax_revenue_tzs"] + total_annual_tzs
        )
        new_gdp_ratio = new_total / gdp_tzs

        scenarios[scenario_name] = {
            "capture_rate":    capture_rate,
            "stage_results":   stage_results,
            "mobile_money_contribution_tzs":  round(mm_scaled, 0),
            "property_tax_contribution_tzs":  round(prop_scaled, 0),
            "total_additional_annual_revenue_tzs": round(
                total_annual_tzs, 0
            ),
            "total_additional_annual_revenue_usd": round(
                total_annual_tzs / params["tzs_per_usd"], 0
            ),
            "total_new_taxpayers":   total_new_taxpayers,
            "new_total_revenue_tzs": round(new_total, 0),
            "new_tax_to_gdp_pct":    round(new_gdp_ratio * 100, 2),
            "current_tax_to_gdp_pct": round(
                params["tax_to_gdp_current"] * 100, 2
            ),
            "improvement_pct_points": round(
                (new_gdp_ratio - params["tax_to_gdp_current"]) * 100,
                2
            ),
        }

        print(f"    Additional revenue: "
              f"TZS {total_annual_tzs:,.0f}")
        print(f"    New taxpayers: {total_new_taxpayers:,.0f}")
        print(f"    New tax-to-GDP: "
              f"{scenarios[scenario_name]['new_tax_to_gdp_pct']}%")

    return scenarios


def calculate_demographic_dividend(params):
    """
    Path A (informal default) vs Path B (behavioral lifecycle).
    Quantifies the cost of inaction over 10 years.
    """
    # cohort size per single year of age: the Seed population divided by the width of the configured age band (6-15: 10 years)
    seed_band_width  = SEED_AGE_MAX - SEED_AGE_MIN + 1
    new_per_year     = round(params["seed_stage_population"] / seed_band_width)
    total_10yr       = new_per_year * 10
    tax_pp           = params["mean_tax_informal_tzs"]                # statutory tax on the earnings distribution (Block F1)

    path_a_rev = total_10yr * 0.20 * tax_pp
    path_b_rev = (
        total_10yr * 0.80 * tax_pp *
        params["behavioral_uplift"]
    )
    diff = path_b_rev - path_a_rev

    return {
        "total_new_entrants_10yr": total_10yr,
        "path_a_capture_rate":     0.20,
        "path_a_revenue_tzs":      round(path_a_rev, 0),
        "path_b_capture_rate":     0.80,
        "path_b_revenue_tzs":      round(path_b_rev, 0),
        "difference_tzs":          round(diff, 0),
        "difference_usd":          round(
            diff / params["tzs_per_usd"], 0
        ),
        "assumptions": {
            "path_a": "Default informal trajectory (20% formalize)",
            "path_b": "Behavioral lifecycle from 2025 (80% formalize)",
            "behavioral_uplift": params["behavioral_uplift"],
            "source_uplift": "Rwanda RRA + UK HMRC behavioral studies"
        }
    }


# ============================================================
# B. MONTE CARLO SIMULATION
# ============================================================

def run_monte_carlo_simulation(params, n_iterations=1000):
    """
    Runs 1,000 Monte Carlo iterations with randomised
    assumptions to produce confidence intervals on revenue.

    Key uncertainties modelled:
    - Capture rate (±50% of point estimate)
    - Behavioral uplift (1.1 to 1.6)
    - Income levels (±30%)
    - GDP growth rate (±2pp)
    - Tax rate effectiveness (±20%)

    Returns confidence intervals for each scenario.
    """
    print(f"\n  Running Monte Carlo ({n_iterations} iterations)...")

    results = {
        "conservative": [],
        "moderate":     [],
        "ambitious":    [],
    }

    base_captures = {
        "conservative": params["conservative_capture"],
        "moderate":     params["moderate_capture"],
        "ambitious":    params["ambitious_capture"],
    }

    gdp_tzs = params["gdp_usd"] * params["tzs_per_usd"]

    for i in range(n_iterations):
        # Randomise key assumptions
        uplift      = np.random.uniform(1.10, 1.60)
        income_mult = np.random.uniform(0.70, 1.30)
        growth      = np.random.uniform(0.03, 0.08)
        tax_eff     = np.random.uniform(0.80, 1.20)

        for scenario, base_cap in base_captures.items():
            # Capture rate varies around base
            cap = np.clip(
                np.random.normal(base_cap, base_cap * 0.25),
                0.05, 0.95
            )

            # Entry + Active + Enterprise stages: the statutory tax on the earnings distribution scaled by income_mult (Block F1)
            populations = [
                params["entry_stage_population"],
                params["active_stage_population"],
                params["enterprise_stage_population"],
            ]
            taxes = [
                stat.informal_mean_tax(0.7 * income_mult) * tax_eff,
                stat.informal_mean_tax(income_mult) * tax_eff,
                stat.msme_mean_tax(income_mult) * tax_eff,
            ]

            total = 0
            for pop, tax_pp in zip(populations, taxes):
                total += pop * cap * tax_pp * uplift

            # Mobile money and property scaled
            mm_rev = (
                gdp_tzs * params["mobile_money_gdp_pct"] *
                0.005 * cap
            )
            prop_rev = gdp_tzs * 0.004 * cap
            total += mm_rev + prop_rev

            results[scenario].append(total)

    # Compute confidence intervals
    ci_results = {}
    for scenario, values in results.items():
        arr = np.array(values)
        ci_results[scenario] = {
            "mean_tzs":   round(float(np.mean(arr)), 0),
            "median_tzs": round(float(np.median(arr)), 0),
            "ci_80_low":  round(float(np.percentile(arr, 10)), 0),
            "ci_80_high": round(float(np.percentile(arr, 90)), 0),
            "ci_95_low":  round(float(np.percentile(arr, 2.5)), 0),
            "ci_95_high": round(float(np.percentile(arr, 97.5)), 0),
            "std_tzs":    round(float(np.std(arr)), 0),
            "prob_exceeds_africa_avg": round(float(
                np.mean(arr > gdp_tzs * 0.037)
            ) * 100, 1),
            "n_iterations": n_iterations,
        }
        print(f"    {scenario}: "
              f"TZS {ci_results[scenario]['median_tzs']/1e12:.1f}T "
              f"(80% CI: "
              f"{ci_results[scenario]['ci_80_low']/1e12:.1f}T – "
              f"{ci_results[scenario]['ci_80_high']/1e12:.1f}T)")

    return ci_results


# ============================================================
# C. TAX MORALE MODEL
# ============================================================

def agent_status():
    """Publication status of the agent and tier simulations (Block E2.0 / E2.4): flagged until the calibration to TRA's registered-taxpayer trend has succeeded."""
    try:
        with open(paths.AGENT_CALIBRATION, encoding="utf-8") as f:
            cal = json.load(f)
        if cal.get("status") == "fit ok":
            return "CALIBRATED (Blocks E2.4 / E3.1): the no-intervention scenario reproduces TRA's registered-taxpayer trend 2017/18-2023/24 (RMSE %.2f pp); intervention effects are the tax-morale model's odds ratios (ASSUMPTION uplifts)" % cal["fit"]["rmse_pp"]
    except FileNotFoundError:
        pass
    return "UN-RECALIBRATED - NOT FOR PUBLICATION"


def _logit(p):
    return math.log(p / (1.0 - p))


def observed_adult_tin_rate():
    """FinScope 2023 weighted adult (16+) TIN rate, as a proportion (outputs/tables/tin_by_segment.csv, row 'overall')."""
    import csv
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["segment"] == "overall":
                return float(r["tin_rate_pct"]) / 100.0
    raise SystemExit("outputs/tables/tin_by_segment.csv has no 'overall' row")


def build_tax_morale_model(params):
    """
    Models compliance probability as a function of
    behavioral drivers, not just income.

    compliance_probability =
        f(trust, simplicity, enforcement,
          social_norm, fairness, morale)

    Each driver scored 0-1. Weighted combination
    produces a compliance probability score.

    Calibrated against FinScope trust variables
    and registration barrier data.
    """
    print("\n  Building tax morale model...")

    # Baseline scores from FinScope gov_2 barrier data
    # These represent Tanzania's current state
    baseline = {
        "trust":        params["baseline_trust"],       # 0.35
        "simplicity":   params["baseline_simplicity"],  # 0.25
        "enforcement":  params["baseline_enforcement"], # 0.40
        "social_norm":  params["baseline_social_norm"], # 0.30
        "fairness":     params["baseline_fairness"],    # 0.30
    }

    # Weights from behavioral economics literature
    # (Luttmer & Singhal 2014, OECD Tax Morale 2019)
    weights = {
        "trust":       A("tax_morale.weight.trust"),  # Highest weight — Tanzania key driver
        "simplicity":  A("tax_morale.weight.simplicity"),  # FinScope barrier: 62.5% say "too small"
        "enforcement": A("tax_morale.weight.enforcement"),  # Lower weight — Tanzania enforcement weak
        "social_norm": A("tax_morale.weight.social_norm"),  # Community-based — high Tanzania relevance
        "fairness":    A("tax_morale.weight.fairness"),  # Perceived value for tax paid
    }

    def morale_index(scores):
        """Weighted index of the five driver scores, in [0, 1] (Block F0: the trust penalty of the original model never binds at the data baseline and was retired)."""
        weighted = sum(scores[k] * weights[k] for k in scores)
        return min(1.0, max(0.0, weighted))

    # Intervention effects on morale scores
    # Each intervention raises specific morale drivers
    interventions = {
        "USSD_registration_nudge": {
            "simplicity":  A("tax_morale.effect.USSD_registration_nudge.simplicity"),
            "trust":       A("tax_morale.effect.USSD_registration_nudge.trust"),
            "description": "Reduces friction — directly targets "
                          "complexity barrier"
        },
        "civic_tax_education": {
            "social_norm": A("tax_morale.effect.civic_tax_education.social_norm"),
            "fairness":    A("tax_morale.effect.civic_tax_education.fairness"),
            "description": "Builds tax identity and visible returns"
        },
        "mobile_money_TIN_bridge": {
            "simplicity":  A("tax_morale.effect.mobile_money_TIN_bridge.simplicity"),
            "trust":       A("tax_morale.effect.mobile_money_TIN_bridge.trust"),
            "description": "Eliminates registration friction entirely"
        },
        "community_compliance_norms": {
            "social_norm": A("tax_morale.effect.community_compliance_norms.social_norm"),
            "trust":       A("tax_morale.effect.community_compliance_norms.trust"),
            "description": "Social proof — everyone complies"
        },
        "visible_tax_returns": {
            "fairness":    A("tax_morale.effect.visible_tax_returns.fairness"),
            "trust":       A("tax_morale.effect.visible_tax_returns.trust"),
            "description": "Shows citizens what their tax builds"
        },
        "presumptive_tax_simplification": {
            "simplicity":  A("tax_morale.effect.presumptive_tax_simplification.simplicity"),
            "trust":       A("tax_morale.effect.presumptive_tax_simplification.trust"),
            "description": "One simple payment for small businesses"
        },
    }

    # ------------------------------------------------------------------------------------------------------------------
    # Block E2.3 recalibration.
    # What the model's "compliance probability" is: the original code computes a weighted index of five driver scores in [0, 1] and calls it a
    # probability; it defines no event. The report calls it "modeled compliance probability" of the portfolio (Fig 5.1) and the interventions it
    # evaluates (USSD TIN nudge, mobile-money TIN bridge, presumptive simplification, norms, education, visible returns) aim at TIN registration. It is
    # therefore read as the PROBABILITY THAT AN ADULT HOLDS A TIN, whose observed counterpart is the FinScope 2023 weighted adult TIN rate (3.83%).
    # Model: p = expit(alpha + beta * index(scores)).  alpha: fitted so that the baseline reproduces the observed rate EXACTLY (1 parameter, 1 target).
    # beta: the scale that converts the (unchanged, ASSUMPTION) driver deltas of each intervention to log-odds, fitted by least squares through the origin
    # to the log odds ratios that the ORIGINAL model implied for the six solo interventions at its old baseline (6 targets, 1 parameter).
    # ------------------------------------------------------------------------------------------------------------------
    observed_tin = observed_adult_tin_rate()
    old_scores = {k: float(paths.CFG["afrobarometer"]["baseline_mapping"][k]["previous_typed_value"]) for k in baseline}   # 0.35 / 0.25 / 0.40 / 0.30 / 0.30
    p_old0 = morale_index(old_scores)
    old_solo, ln_or_old = {}, {}
    for int_name, effects in interventions.items():
        sc = dict(old_scores)
        for driver, delta in effects.items():
            if driver != "description":
                sc[driver] = min(1.0, sc[driver] + delta)
        old_solo[int_name] = morale_index(sc)
        ln_or_old[int_name] = _logit(old_solo[int_name]) - _logit(p_old0)
    z0 = morale_index(baseline)
    dz = {}
    for int_name, effects in interventions.items():
        sc = dict(baseline)
        for driver, delta in effects.items():
            if driver != "description":
                sc[driver] = min(1.0, sc[driver] + delta)
        dz[int_name] = morale_index(sc) - z0
    beta = sum(dz[k] * ln_or_old[k] for k in dz) / sum(dz[k] ** 2 for k in dz)
    alpha = _logit(observed_tin) - beta * z0

    def compliance_probability(scores):
        return 1.0 / (1.0 + math.exp(-(alpha + beta * morale_index(scores))))

    current_cp = compliance_probability(baseline)

    def odds_ratio_of_set(names):
        """Odds ratio of a set of active interventions, by the model's own combination rule (Block E3.1).
        One intervention: its solo odds ratio. Two or more: the driver deltas of the active interventions are ADDED after multiplying each by
        tax_morale.combined_discount (the rule that produces the 'combined' effect below), capped at 1, passed through the same index and the fitted beta:
        OR = exp(beta x (index(combined drivers) - index(baseline)))."""
        names = list(names)
        if len(names) == 1:
            return math.exp(beta * dz[names[0]])
        sc = dict(baseline)
        for n in names:
            for driver, delta in interventions[n].items():
                if driver != "description":
                    sc[driver] = min(1.0, sc[driver] + delta * A("tax_morale.combined_discount"))
        return math.exp(beta * (morale_index(sc) - z0))

    import itertools
    odds_ratio_by_set = {}
    for r in (1, 2, len(interventions)):
        for combo in itertools.combinations(sorted(interventions), r):
            odds_ratio_by_set["+".join(combo)] = odds_ratio_of_set(combo)

    # Model each intervention's compliance uplift
    intervention_effects = {}
    naive_sum_of_uplifts = 0.0     # sum of the six solo uplifts from the UNROUNDED probabilities (Fig 5.1 "naive sum")
    for int_name, effects in interventions.items():
        new_scores = baseline.copy()
        for driver, delta in effects.items():
            if driver != "description":
                new_scores[driver] = min(1.0,
                    new_scores[driver] + delta
                )
        new_cp = compliance_probability(new_scores)
        uplift = new_cp - current_cp
        naive_sum_of_uplifts += uplift
        uplift_pct = (uplift / current_cp * 100
                      if current_cp > 0 else 0)

        intervention_effects[int_name] = {
            "baseline_compliance_prob":  round(current_cp, 6),
            "new_compliance_prob":       round(new_cp, 6),
            "absolute_uplift":           round(uplift, 6),
            "odds_ratio_implied":        round(math.exp(beta * dz[int_name]), 4),
            "odds_ratio_of_original_model_at_its_old_baseline": round(math.exp(ln_or_old[int_name]), 4),
            "relative_uplift_pct":       round(uplift_pct, 1),
            "description":               effects["description"],
            "new_scores":                {
                k: round(v, 3) for k, v in new_scores.items()
            }
        }

    # Combined effect of all interventions
    combined_scores = baseline.copy()
    for int_name, effects in interventions.items():
        for driver, delta in effects.items():
            if driver != "description" and driver in combined_scores:
                combined_scores[driver] = min(1.0,
                    combined_scores[driver] + delta * A("tax_morale.combined_discount")
                    # Diminishing returns on combined
                )
    combined_cp = compliance_probability(combined_scores)

    # By lifecycle stage — different morale profiles
    stage_morale = {}
    stage_adjustments = {
        "entry":      {"trust": -0.10, "simplicity": -0.05},
        "active":     {"social_norm": +0.05},
        "enterprise": {"enforcement": +0.10, "fairness": -0.05},
        "asset":      {"trust": +0.05, "fairness": +0.05},
        "legacy":     {"social_norm": +0.10, "trust": +0.10},
    }

    for stage, adj in stage_adjustments.items():
        stage_scores = baseline.copy()
        for driver, delta in adj.items():
            stage_scores[driver] = min(1.0, max(0.0,
                stage_scores[driver] + delta
            ))
        stage_morale[stage] = {
            "compliance_probability": round(
                compliance_probability(stage_scores), 6
            ),
            "scores": {k: round(v, 3) for k, v in stage_scores.items()}
        }

    result = {
        "status": "RECALIBRATED (Block E2.3) to the observed adult TIN rate; effect sizes are ASSUMPTION uplifts; the naive sum is not a meaningful probability",
        "definition": ("compliance probability = probability that an ADULT HOLDS A TIN (registration). The original code defines no event: it weights five driver scores (0-1) into an "
                       "index and calls it a probability; the report (Fig 5.1, 'modeled compliance probability under the project's tax morale model') evaluates interventions aimed "
                       "at TIN registration. Observed counterpart: FinScope 2023 weighted adult TIN rate."),
        "observed_anchor": {"value": observed_tin, "source": "FinScope Tanzania 2023, weighted adult (16+) TIN rate, outputs/tables/tin_by_segment.csv (361 of 9,915 respondents)"},
        "calibration": {"form": "p = expit(alpha + beta * index(driver scores))", "alpha": alpha, "beta": beta, "index_at_baseline": z0,
                        "alpha_target": "baseline probability equals the observed adult TIN rate exactly (1 parameter, 1 target)",
                        "beta_target": "least squares through the origin of beta x (index change of each intervention) on the log odds ratio the original linear model implied at its old baseline (6 solo interventions, 1 parameter)",
                        "old_baseline_scores": old_scores, "old_baseline_probability": p_old0,
                        "conversion": {k: {"old_solo_probability": old_solo[k], "old_log_odds_ratio": ln_or_old[k], "old_odds_ratio": math.exp(ln_or_old[k]), "index_change_new_baseline": dz[k],
                                           "fitted_log_odds_ratio": beta * dz[k], "fitted_odds_ratio": math.exp(beta * dz[k])} for k in dz},
                        "uplift_sizes": "the driver deltas (config tax_morale.effect.*) are unchanged ASSUMPTIONS; only their scale to log-odds is fitted"},
        "baseline_compliance_probability": round(current_cp, 6),
        "combined_intervention_probability": round(combined_cp, 6),
        "combined_uplift_pct": round(
            (combined_cp - current_cp) / current_cp * 100, 1
        ) if current_cp > 0 else 0,
        # baseline + the sum of the six solo uplifts, computed from unrounded values (the report's "naive sum of parts")
        "naive_sum_of_solo_effects_pct": round(
            (current_cp + naive_sum_of_uplifts) * 100, 3
        ),
        "odds_ratio_by_active_set": odds_ratio_by_set,
        "combination_rule": ("one active intervention: its solo odds ratio exp(beta x index change); two or more: the drivers' deltas are summed after multiplying each by "
                             "tax_morale.combined_discount (%s), capped at 1, then exp(beta x index change) (the rule that gives the combined effect of all six). Block E3.1: "
                             "the agent and tier simulations multiply each agent's yearly registration odds by the odds ratio of the set of interventions that reach the agent" % A("tax_morale.combined_discount")),
        "baseline_scores":        baseline,
        "weights":                weights,
        "intervention_effects":   intervention_effects,
        "by_lifecycle_stage":     stage_morale,
        "methodology": (
            "Weighted compliance probability model. "
            "Weights from Luttmer & Singhal (2014) and "
            "OECD Tax Morale report (2019). "
            "Baseline scores from FinScope Tanzania 2023 "
            "government trust and barrier variables."
        )
    }

    best_int = max(
        intervention_effects.items(),
        key=lambda x: x[1]["relative_uplift_pct"]
    )
    print(f"    Baseline compliance probability: {current_cp:.1%}")
    print(f"    Best single intervention: {best_int[0]} "
          f"(+{best_int[1]['relative_uplift_pct']}%)")
    print(f"    Combined effect: {combined_cp:.1%} "
          f"(+{result['combined_uplift_pct']}%)")

    return result


# ============================================================
# D.0 AGENT POPULATION FROM REAL FINSCOPE RESPONDENTS (Block D3)
# ============================================================

def load_agent_population(n_agents, rng):
    """Draw the simulated population as a weighted resample of REAL FinScope respondents' attributes.

    Source: data/processed/agent_cells.json (written by src/04_models/targeting_model.py): weighted cells of age band x mobile
    money x urban x propensity decile, each pooled to at least disclosure.min_base respondents, so no respondent is ever
    written out. An agent takes the age (uniform within the cell's age band), mobile-money status and urban residence of its
    cell, and starts with a TIN with probability equal to the cell's mean predicted propensity (out-of-fold predictions of the
    real-data targeting model; recalibrated within each age band to the observed weighted TIN rate, Block E1). Income, trust and morale
    come from other surveys' aggregate cell distributions: see draw_agent_inputs.
    """
    try:
        with open(paths.AGENT_CELLS, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
    except FileNotFoundError:
        raise SystemExit("%s is missing: run `python run_all.py --from-raw` (src/04_models/targeting_model.py writes it)" % paths.AGENT_CELLS)
    w = np.array([c["weighted_population"] for c in cells], float)
    pick = rng.choice(len(cells), size=n_agents, p=w / w.sum())
    lo = np.array([c["age_from"] for c in cells])[pick]
    hi = np.array([c["age_to"] for c in cells])[pick]
    ages = rng.integers(lo, hi + 1)
    has_mm = np.array([c["mobile_money"] for c in cells])[pick]
    urban = np.array([c["urban"] for c in cells])[pick]
    propensity = np.array([c["mean_propensity"] for c in cells])[pick]
    return ages, has_mm, urban, propensity


# ============================================================
# D. AGENT-BASED SIMULATION
# ============================================================

def draw_agent_inputs(ages, urban, rng):
    """Trust, morale and income of the agents, drawn from AGGREGATE survey cell distributions (Block E1, E5); no respondent is linked.

    trust, morale  weighted answer-level shares per cell (age band x urban/rural) of Afrobarometer Round 8 Tanzania (Q41J trust in the
                   tax/revenue office; Q76e-tan civic duty), data/processed/agent_trust_morale.json.
    income         annual earnings (TZS) per age band from ILFS 2024, data/processed/agent_income.json: with the published share of
                   persons without earnings the draw is zero; otherwise a percentile drawn uniformly in 1-99 and interpolated.
    income_rank    the agent's rank (0-1) in the national distribution of annual earnings of persons 16+, which replaces the former
                   saturating income scale in the compliance probability.
    """
    try:
        with open(paths.AGENT_TRUST_MORALE, encoding="utf-8") as f:
            tm = json.load(f)["cells"]
        with open(paths.AGENT_INCOME, encoding="utf-8") as f:
            inc = json.load(f)
    except FileNotFoundError as e:
        raise SystemExit("%s is missing: run `python run_all.py --from-raw` (src/03_features/agent_inputs.py writes it)" % e.filename)
    bands = paths.CFG["targeting"]["agent_age_bands"]
    band = np.zeros(len(ages), int)
    for i, (lo, hi) in enumerate(bands):
        band[(ages >= lo) & ((ages <= hi) if i < len(bands) - 1 else np.ones(len(ages), bool))] = i
    n = len(ages)
    trust, morale = np.zeros(n), np.zeros(n)
    for cell in tm:
        if cell.get("suppressed"):
            continue
        idx = np.where((band == cell["band_index"]) & (urban == cell["urban"]))[0]
        for arr, key in ((trust, "trust"), (morale, "morale")):
            d = cell[key]
            arr[idx] = rng.choice(d["levels"], size=len(idx), p=np.array(d["weighted_shares_by_level"]) / sum(d["weighted_shares_by_level"]))
    income = np.zeros(n)
    grid = np.arange(1, 100, dtype=float)
    for b in inc["age_bands"]:
        if b.get("suppressed"):
            continue
        idx = np.where(band == b["band_index"])[0]
        earner = rng.random(len(idx)) >= b["share_without_earnings_pct"] / 100.0
        if not A("agents.non_earners_zero_income"):        # ASSUMPTION: persons without earnings enter with zero income (True); False draws everyone from the earners' distribution
            earner = np.ones(len(idx), bool)
        u = rng.uniform(1.0, 99.0, size=len(idx))
        draw = np.interp(u, grid, b["annual_earnings_tzs_percentiles_among_earners"])
        income[idx] = np.where(earner, draw, 0.0)
    national = np.array(inc["national"]["annual_earnings_tzs_percentiles_all_persons_16plus"])
    income_rank = np.searchsorted(national, income, side="right") / float(len(national))
    return income, trust, morale, income_rank


def _registration_hazard(params, trust, morale, income_rank, has_mm, urban, ages, interventions, morale_model=None):
    """Yearly registration probability of each (non-registered) agent (Block E3.1) and the odds ratios applied.

    Without interventions: hazard = conversion_rate x clip(trust x w + morale x w + income_rank x w + mobile_money x w + intercept, 0, 1).
    With interventions the agent's registration ODDS are multiplied by the morale model's odds ratio of the interventions that reach the agent: the USSD TIN
    nudge reaches mobile-money users, civic tax education reaches urban agents aged agents.edu.min_age or more; an agent reached by both gets the odds ratio of the
    set by the morale model's own combination rule (tax_morale.combined_discount). The earlier trust / morale uplift path and the community-norm feedback are retired."""
    index = (trust * A("agents.p_comply.trust_weight") + morale * A("agents.p_comply.morale_weight") + income_rank * A("agents.p_comply.income_weight") +
             has_mm.astype(float) * A("agents.p_comply.mm_weight"))
    p_comply = np.clip(index + A("agents.p_comply.intercept"), 0.0, 1.0)
    hazard = p_comply * A("agents.conversion_rate")
    ors = {"ussd": 1.0, "edu": 1.0, "both": 1.0}
    if interventions:
        m = morale_model if morale_model is not None else build_tax_morale_model(params)
        sets = m["odds_ratio_by_active_set"]
        u, e = AGENT_INTERVENTIONS["ussd"], AGENT_INTERVENTIONS["edu"]
        ors = {"ussd": sets[u], "edu": sets[e], "both": sets["+".join(sorted((u, e)))]}
        reached_u = has_mm
        reached_e = urban & (ages >= A("agents.edu.min_age"))
        orv = np.where(reached_u & reached_e, ors["both"], np.where(reached_u, ors["ussd"], np.where(reached_e, ors["edu"], 1.0)))
        odds = hazard / np.maximum(1.0 - hazard, 1e-12) * orv
        hazard = np.where(orv != 1.0, odds / (1.0 + odds), hazard)               # agents that no intervention reaches keep exactly their own probability
    return hazard, ors, index


AGENT_INTERVENTIONS = {"ussd": "USSD_registration_nudge", "edu": "civic_tax_education"}


def run_agent_based_simulation(params, n_agents=paths.N_AGENTS,
                                 n_years=paths.N_YEARS, interventions=True, initial_rate=None, quiet=False, morale_model=None):
    """
    Simulates 500,000 synthetic Tanzanian citizens
    over 10 years. Each agent has individual attributes
    and makes compliance decisions based on their state.

    Agent attributes:
    - age, income, education, region
    - mobile_money (bool)
    - trust_score (0-1)
    - tax_morale_score (0-1)
    - compliance_status (none/registered/filing/compliant)

    Each year:
    1. Agents receive interventions based on their stage
    2. Trust and morale scores update
    3. Compliance decision made probabilistically
    4. Revenue accumulated
    """
    if not quiet:
        print(f"\n  Running agent-based simulation "
              f"({n_agents:,} agents, {n_years} years{'' if interventions else ', NO interventions'})...")

    rng = np.random.default_rng(RANDOM_SEED)

    # ── Initialise agent population ──────────────────────────
    # Age, mobile money, urban residence and the starting TIN probability come from real FinScope respondents (agent_cells.json)
    ages, has_mm, urban, propensity = load_agent_population(n_agents, rng)

    # Assign lifecycle stages
    stages = np.select(
        [
            ages < 25,
            ages < 45,
            ages < 65,
            ages >= 65
        ],
        ML_SEGMENT_STAGES,
        default=ML_SEGMENT_STAGES[0]
    )

    # Income (ILFS 2024 earnings by age band), trust (Afrobarometer Q41J) and morale (Afrobarometer Q76e-tan): aggregate cell distributions
    income, trust, morale, income_rank = draw_agent_inputs(ages, urban, rng)

    # Initial compliance: a TIN with the cell's predicted propensity (real-data targeting model; weighted mean about the FinScope TIN rate)
    if initial_rate is not None:                       # calibration: start from a given adult registration rate (propensities rescaled, ranking kept)
        propensity = np.clip(propensity * (float(initial_rate) / float(propensity.mean())), 0.0, 1.0)
    compliant = rng.random(n_agents) < propensity
    initial_rate = float(compliant.mean())

    # Accumulate results by year
    yearly_results = []
    annual_revenue = np.zeros(n_agents)

    hazard, odds_ratios, index = _registration_hazard(params, trust, morale, income_rank, has_mm, urban, ages, interventions, morale_model)
    start_non_registered = ~compliant                     # the agents that can still register at the start

    for year in range(n_years):

        # ── Registration decision (Block E3.1) ───────────────
        # Non-compliant agents register with the yearly probability `hazard` (static per agent: trust, morale, income and mobile money do not
        # evolve any more). Under the interventions the agent's yearly registration ODDS are multiplied by the morale model's odds ratio.
        newly_compliant = ~compliant & (rng.random(n_agents) < hazard)
        compliant = compliant | newly_compliant

        # ── Revenue calculation ──────────────────────────────
        yr_revenue = (
            compliant.astype(float) * stat.pit(income) *                      # Block F1: each agent pays the statutory resident schedule on its own earnings
            (1 + params["gdp_growth_rate"]) ** year
        )
        annual_revenue = yr_revenue

        # Scale to full population
        # (agents represent 500K of 34M adults)
        scale_factor = (
            params["entry_stage_population"] +
            params["active_stage_population"] +
            params["workers_stage_population"] +
            params["asset_stage_population"]
        ) / n_agents

        total_yr_revenue = annual_revenue.sum() * scale_factor

        yearly_results.append({
            "year":              year + 1,
            "compliance_rate":   round(float(compliant.mean()), 4),
            "compliance_rate_exact": float(compliant.mean()),
            "n_compliant":       int(compliant.sum()),
            "mean_trust":        round(float(trust.mean()), 3),
            "mean_morale":       round(float(morale.mean()), 3),
            "annual_revenue_tzs": round(total_yr_revenue, 0),
        })

        if (year + 1) % 2 == 0 and not quiet:
            print(f"    Year {year+1}: "
                  f"compliance={compliant.mean():.1%}  "
                  f"trust={trust.mean():.2f}  "
                  f"revenue=TZS "
                  f"{total_yr_revenue/1e12:.2f}T")

    # Summary
    final_rate = float(compliant.mean())
    total_rev  = sum(r["annual_revenue_tzs"] for r in yearly_results)

    result = {
        "n_agents":               n_agents,
        "n_years":                n_years,
        "scenario":               "interventions (USSD TIN nudge for mobile-money users, civic tax education for urban adults 18+) switched on: yearly registration odds x the morale model's odds ratios" if interventions else "no interventions",
        "odds_ratios_applied":    {"USSD_registration_nudge (mobile-money users)": odds_ratios["ussd"], "civic_tax_education (urban, age >= %s)" % A("agents.edu.min_age"): odds_ratios["edu"],
                                   "both (morale model's combination rule)": odds_ratios["both"]} if interventions else {},
        "status":                 agent_status(),
        "initial_compliance_rate": round(initial_rate, 4),
        "final_compliance_rate":  round(final_rate, 4),
        "compliance_improvement": round(final_rate - initial_rate, 4),
        "cumulative_revenue_tzs": round(total_rev, 0),
        "average_annual_revenue_tzs": round(
            total_rev / n_years, 0
        ),
        "mean_index_non_registered_at_start": float(index[start_non_registered].mean()),
        "mean_yearly_registration_probability_non_registered_at_start": float(hazard[start_non_registered].mean()),
        "yearly_results":         yearly_results,
        "methodology": (
            "Vectorised agent-based simulation. "
            f"{n_agents:,} synthetic agents, {n_years} years. "
            "Age, mobile money, urban residence and the starting TIN status are a weighted resample of real FinScope Tanzania 2023 "
            "respondents' attributes (aggregate cells, data/processed/agent_cells.json) with the real-data targeting model's predicted "
            "propensities; income (ILFS 2024 earnings by age band) and trust and morale (Afrobarometer Round 8 by age band and urban/rural) are drawn from aggregate survey cell distributions. "
            "Yearly registration probability of a non-registered agent = conversion_rate x clip(trust, morale, income-rank and mobile-money terms + intercept); "
            "trust and morale are the agent's survey-based values and do not evolve (Block E3.1). Interventions multiply the agent's yearly registration odds by "
            "the tax-morale model's odds ratios (the same mechanism as Fig 5.1). "
            "Random seed: 42 for reproducibility."
        )
    }

    if not quiet:
        print(f"  Final compliance: {final_rate:.1%} "
              f"(from {initial_rate:.1%})")
        print(f"  10-year revenue: TZS {total_rev/1e12:.1f}T")

    return result


# ============================================================
# D.2 TIER-MIGRATION SIMULATION (Enterprise / Ngazi dashboard)
# Built to fill a specific, disclosed gap in this project's
# submission's Enterprise-stage dashboard page, whose 5-tier
# progression chart (Entry/Bronze/Silver/Gold/Platinum) had no real
# simulation behind it -- run_agent_based_simulation() above only
# tracks a binary compliant/non-compliant state, not years-registered
# or filing consistency, which is what the tiers are actually defined
# by. Deliberately a fully separate function (own population init, own
# rng calls) rather than an extension of run_agent_based_simulation --
# shares no mutable state with it, so nothing about that already-
# verified simulation's output changes by this function existing.
# Not wired into run_economic_model()'s orchestration: that function
# reruns and overwrites the entire economic_model.json in one pass, and
# doing that just to add this one new key would risk re-deriving every
# other already-verified figure in the file. Call this standalone and
# merge its result into the existing file instead.
# ============================================================

def run_tier_migration_simulation(params, n_agents=paths.N_AGENTS, n_years=paths.N_YEARS, morale_model=None):
    """
    Simulates the same size population as run_agent_based_simulation(),
    but tracks two dimensions that one doesn't: years_registered
    (increments each year an agent stays compliant) and a persistent
    per-agent filing-reliability trait correlated with trust and
    morale. Classifies each compliant agent into one of the 5 Ngazi
    tiers every year using the exact thresholds already shown on the
    Enterprise dashboard page, so the dashboard's illustrative tier
    chart can be replaced with this real distribution.
    """
    print(f"\n  Running tier-migration simulation "
          f"({n_agents:,} agents, {n_years} years)...")
    rng = np.random.default_rng(RANDOM_SEED)

    ages, has_mm, urban, propensity = load_agent_population(n_agents, rng)
    income, trust, morale, income_rank = draw_agent_inputs(ages, urban, rng)
    compliant = rng.random(n_agents) < propensity

    # New state this simulation introduces, not present in
    # run_agent_based_simulation(): already-compliant agents start with
    # a plausible existing tenure (1-3 years) rather than 0, so year-1
    # tier distribution isn't artificially all-Entry-tier.
    years_registered = np.where(
        compliant, rng.integers(A("tier.initial_tenure_low"), A("tier.initial_tenure_high"), size=n_agents), 0
    ).astype(float)
    # Persistent per-agent filing reliability, set once from trust/morale
    # (a taxpayer who trusts the system and has higher morale is modeled
    # as more likely to file on time) plus individual noise -- not
    # redrawn every year, so an agent's tier trajectory is coherent
    # rather than a fresh random tier each year.
    filing_reliability = np.clip(
        A("tier.filing.base") + A("tier.filing.trust_coef") * trust + A("tier.filing.morale_coef") * morale + rng.normal(0, A("tier.filing.noise_sd"), size=n_agents),
        A("tier.filing.clip_low"), A("tier.filing.clip_high"),
    )

    yearly_tier_distribution = []
    # Block E3.1: the same registration mechanism as run_agent_based_simulation (static trust / morale; interventions multiply the yearly registration odds by the
    # tax-morale model's odds ratios); the filing-reliability trait above is still set once from the agent's trust and morale
    hazard, _odds_ratios, _index = _registration_hazard(params, trust, morale, income_rank, has_mm, urban, ages, True, morale_model)
    for year in range(n_years):
        newly_compliant = ~compliant & (rng.random(n_agents) < hazard)
        compliant = compliant | newly_compliant

        years_registered = np.where(compliant, years_registered + 1, 0)

        # This year's on-time filing rate: the persistent reliability
        # trait plus year-to-year noise (illness, cash-flow timing,
        # etc.), not a fresh redraw of the trait itself.
        on_time_pct = np.clip(
            filing_reliability * 100 + rng.normal(0, A("tier.on_time_noise_sd"), size=n_agents), 0, 100
        )

        tier = np.select(
            [
                compliant & (on_time_pct >= A("tier.threshold.platinum_on_time")) & (years_registered >= A("tier.threshold.platinum_years")),
                compliant & (on_time_pct >= A("tier.threshold.gold_on_time")) & (years_registered >= A("tier.threshold.gold_years")),
                compliant & (on_time_pct >= A("tier.threshold.silver_on_time")),
                compliant & (on_time_pct >= A("tier.threshold.bronze_on_time")),
                compliant,
            ],
            [5, 4, 3, 2, 1],
            default=0,  # not registered/compliant at all
        )

        tier_pct = {
            int(t): round(float((tier == t).sum()) / n_agents * 100, 2)
            for t in range(6)
        }
        yearly_tier_distribution.append({
            "year": year + 1,
            "not_registered_pct":  tier_pct[0],
            "level_1_entry_pct":   tier_pct[1],
            "level_2_bronze_pct":  tier_pct[2],
            "level_3_silver_pct":  tier_pct[3],
            "level_4_gold_pct":    tier_pct[4],
            "level_5_platinum_pct": tier_pct[5],
        })

        if (year + 1) % 2 == 0:
            print(f"    Year {year+1}: {yearly_tier_distribution[-1]}")

    result = {
        "n_agents": n_agents,
        "n_years": n_years,
        "status": agent_status(),
        "tier_thresholds": {
            "level_5_platinum": "on-time filing >= %s%% AND years registered >= %s" % (A("tier.threshold.platinum_on_time"), A("tier.threshold.platinum_years")),
            "level_4_gold":     "on-time filing >= %s%% AND years registered >= %s" % (A("tier.threshold.gold_on_time"), A("tier.threshold.gold_years")),
            "level_3_silver":   "on-time filing >= %s%%" % A("tier.threshold.silver_on_time"),
            "level_2_bronze":   "on-time filing >= %s%%" % A("tier.threshold.bronze_on_time"),
            "level_1_entry":    "compliant, below Bronze threshold",
        },
        "yearly_tier_distribution": yearly_tier_distribution,
        "methodology": (
            "Standalone simulation, separate from run_agent_based_simulation "
            "-- shares no mutable state with it. Same population-generation "
            "approach (weighted resample of real FinScope respondents' age, mobile money, urban "
            "residence and predicted TIN propensity, aggregate cells; income, trust and morale from ILFS / Afrobarometer aggregate cell distributions; "
            "random seed 42) plus two new per-agent "
            "dimensions: years_registered (increments while compliant) and "
            "a persistent filing-reliability trait correlated with trust "
            "and morale, redrawn with year-to-year noise rather than from "
            "scratch. Tier thresholds match exactly what the "
            "Enterprise-stage dashboard already displays."
        ),
    }
    print(f"  Final tier distribution (year {n_years}): "
          f"{yearly_tier_distribution[-1]}")
    return result


# ============================================================
# F. DIGITAL TWIN: RETIRED (Pass 6B-1). The twin's year-10 increment was about 6.15 trillion TZS (about 22 times the whole FY2023/24 individuals' income tax collection), driven by
# registrations and tax rates that no data fix; see PASS6A D2, PASS6C E1, PASS6D F4/F5. The code is kept for the record in src/retired/digital_twin_v0.py (not run, not tested); the
# scale-checked replacement is src/04_models/reach_scenarios.py (Figure 5.2).
# ============================================================


# ============================================================
# G. CAUSAL INFERENCE LAYER: RETIRED (Block D2)
# The difference-in-differences on three region means, the propensity-score matching on simulated data (the effect was planted in
# the simulation and recovered from it) and the synthetic control with typed series and weights were removed. Their constants
# are listed as RETIRED in docs/assumptions_register.csv. The evidence on mobile money and TIN holding is now the observational,
# survey-weighted association estimated on the real FinScope respondents in src/04_models/tin_mobile_money.py (not a causal estimate).
# ============================================================


# ============================================================
# I. SENSITIVITY ANALYSIS
# ============================================================

def run_sensitivity_analysis(params):
    """
    Systematically varies each key assumption and
    shows revenue impact. Identifies which assumptions
    matter most.
    """
    print("\n  Running sensitivity analysis...")

    # Base case revenue (moderate scenario)
    base_scenarios = run_scenario_analysis(params)
    base_rev = base_scenarios["moderate"][
        "total_additional_annual_revenue_tzs"
    ]

    # Parameters to test and their ranges
    tests = [
        ("behavioral_uplift",        [1.0, 1.1, 1.2, 1.35, 1.5, 1.7]),
        ("moderate_capture",         [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]),
        ("income_scale",             [0.5, 0.75, 1.0, 1.25, 1.5]),
        ("gdp_growth_rate",          [0.02, 0.035, 0.055, 0.07, 0.09]),
        ("mobile_money_gdp_pct",     [0.30, 0.40, 0.49, 0.60, 0.70]),
    ]

    sensitivity_results = {}

    for param_name, values in tests:
        param_results = []

        for val in values:
            test_params = params.copy()
            test_params[param_name] = val

            try:
                test_scenarios = run_scenario_analysis(test_params)
                test_rev = test_scenarios["moderate"][
                    "total_additional_annual_revenue_tzs"
                ]
                pct_change = (
                    (test_rev - base_rev) / base_rev * 100
                ) if base_rev > 0 else 0

                param_results.append({
                    "value":      val,
                    "revenue_tzs": round(test_rev, 0),
                    "pct_change": round(pct_change, 1),
                })
            except Exception:
                pass

        if param_results:
            rev_range = max(
                r["revenue_tzs"] for r in param_results
            ) - min(
                r["revenue_tzs"] for r in param_results
            )
            sensitivity_results[param_name] = {
                "values_tested": param_results,
                "revenue_range_tzs": round(rev_range, 0),
                "sensitivity_rank": 0,  # filled below
            }

    # Rank by revenue range (most sensitive first)
    ranked = sorted(
        sensitivity_results.items(),
        key=lambda x: x[1]["revenue_range_tzs"],
        reverse=True
    )
    for rank, (name, data) in enumerate(ranked, 1):
        sensitivity_results[name]["sensitivity_rank"] = rank
        print(f"    Rank {rank}: {name} "
              f"(range: TZS "
              f"{data['revenue_range_tzs']/1e12:.1f}T)")

    return {
        "base_revenue_tzs":     base_rev,
        "parameters_tested":    len(sensitivity_results),
        "most_sensitive":       ranked[0][0] if ranked else None,
        "least_sensitive":      ranked[-1][0] if ranked else None,
        "results":              sensitivity_results,
        "methodology": (
            "One-at-a-time sensitivity analysis. "
            "Each parameter varied while others held constant. "
            "Revenue range shows maximum impact of uncertainty "
            "in each parameter."
        )
    }


# ============================================================
# J. COMPLIANCE FUNNEL MODEL (FinScope-grounded)
# ============================================================

def build_compliance_funnel_model(params):
    """
    Models the compliance funnel using real FinScope data.
    Shows where citizens drop out and quantifies the gap
    at each stage.
    """
    print("\n  Building compliance funnel model...")

    total = (
        params["entry_stage_population"] +
        params["active_stage_population"] +
        params["enterprise_stage_population"] +
        params["workers_stage_population"] +
        params["asset_stage_population"] +
        params["legacy_stage_population"]
    )

    # Real FinScope numbers
    funnel_levels = [
        {
            "level":        "Total adults (16+)",
            "count":        34_134_251,
            "pct_of_total": 100.0,
            "source":       "FinScope Tanzania 2023",
            "dropout_from_previous": 0,
        },
        {
            "level":        "Has income source",
            "count":        34_134_251,
            "pct_of_total": 100.0,
            "source":       "FinScope Tanzania 2023",
            "dropout_from_previous": 0,
            "note":         "100% — income variable broad"
        },
        {
            "level":        "Uses mobile money",
            "count":        24_445_601,
            "pct_of_total": 71.6,
            "source":       "FinScope Tanzania 2023 (MM composite)",
            "dropout_from_previous": 9_688_650,
            "barrier":      "No phone / no need / too expensive"
        },
        {
            "level":        "Has National ID",
            "count":        17_978_049,
            "pct_of_total": 52.7,
            "source":       "FinScope Tanzania 2023 (c27__1)",
            "dropout_from_previous": 16_156_202,
            "barrier":      "Birth registration gap / distance"
        },
        {
            "level":        "Has TIN",
            "count":        1_306_683,
            "pct_of_total": 3.8,
            "source":       "FinScope Tanzania 2023 (c27__13)",
            "dropout_from_previous": 16_671_366,
            "barrier":      "Biggest gap — 62.5% say business too small"
        },
        {
            "level":        "Active filer (estimated)",
            "count":        round(1_306_683 * 0.65),
            "pct_of_total": round(1_306_683 * 0.65 / 34_134_251 * 100, 1),
            "source":       "TRA estimate (65% of registered file)",
            "dropout_from_previous": round(1_306_683 * 0.35),
            "barrier":      "Complexity / cost of compliance"
        },
    ]

    # ── Extension (task #28): Payment, Audit, Dispute, Long-term
    # Compliance stages, added after Filing. Unlike the FinScope-
    # sourced stages above (individual-level measured survey data),
    # real individual-level transition rates for these later stages do
    # not exist in any source loaded into this project (confirmed --
    # Historical Audit Findings, task #12, was explicitly checked and
    # found not publicly available). Rather than fabricate a plausible-
    # looking dropout percentage for stages with no real measurement,
    # each is handled on its own honest terms:
    #   - Payment: uses a REAL aggregate proxy (the exemption-as-%-of-
    #     collection rate from MoF's own FY2023/24 Q1 data, loaded by
    #     tax_exemptions_loader.py) as an illustrative leakage estimate,
    #     clearly labeled as an aggregate proxy, not an individual-level
    #     measurement like the stages above it.
    #   - Audit, Dispute, Long-term Compliance: no quantified
    #     dropout/count is invented. Each carries data_gap=True, a
    #     count/pct/dropout of None (the revenue-potential loop below
    #     skips these safely), and real qualitative grounding from the
    #     legal/dispute documents loaded this session, so the funnel
    #     stage exists and is correctly cited even though it can't be
    #     quantified yet.
    filer_count = funnel_levels[-1]["count"]
    exemption_pct = params.get("exemption_pct_of_collection")
    exemption_pct_total = params.get("exemption_pct_total_sensitivity")
    exemption_period = params.get("exemption_period", "2023/24 - Q1")
    if exemption_pct is not None:
        payment_dropout = round(filer_count * (exemption_pct / 100.0))
        payment_pct_of_total = round(
            (filer_count - payment_dropout) / 34_134_251 * 100, 2
        )
        funnel_levels.append({
            "level":        "Pays in full (net of exemptions/reliefs)",
            "count":        filer_count - payment_dropout,
            "pct_of_total": payment_pct_of_total,
            "source":       "MoF Tax Exemptions/Reliefs Report FY2023/24 Q1 "
                            "(DOMESTIC reliefs rate, a single quarter: "
                            f"{exemption_period}, applied as a proxy leakage estimate: "
                            f"{exemption_pct:.2f}% of domestic gross collection "
                            "exempted/relieved -- NOT an "
                            "individual-filer-level measurement like the "
                            "stages above; the total rate incl. customs and "
                            "excise is in payment_stage_sensitivity)",
            "dropout_from_previous": payment_dropout,
            "barrier":      "Exemptions/reliefs granted under VAT Act 2014 "
                            "and Income Tax Act -- see legal_documents table"
        })
    else:
        funnel_levels.append({
            "level":        "Pays in full",
            "count":        None,
            "pct_of_total": None,
            "source":       "No exemption-rate data available",
            "dropout_from_previous": None,
            "data_gap":     True,
            "barrier":      "Unknown -- run tax_exemptions_loader.py first"
        })

    funnel_levels.append({
        "level":        "Audited",
        "count":        None,
        "pct_of_total": None,
        "source":       "No audit coverage-rate data available (task #12, "
                        "Historical Audit Findings Database, confirmed not "
                        "publicly available -- only TRA's own institutional "
                        "financial audits are published, not taxpayer audit "
                        "outcomes)",
        "dropout_from_previous": None,
        "data_gap":     True,
        "barrier":      "Audit/assessment governed by the Tax Administration "
                        "Act (General) Regulations and the Best Judgment "
                        "Rule -- see legal_documents table -- but no "
                        "coverage-rate statistic exists to quantify this stage"
    })

    case_digest_note = (
        "Real historical dispute topics exist (Tax Revenue Appeals "
        "Tribunal case digests, e.g. Best Judgment Rule, Additional "
        "Assessment After an Audit, Advocate's Fees -- see "
        "dispute_documents table) but no aggregate dispute VOLUME or "
        "RATE statistic (e.g. what share of audits get disputed) is "
        "publicly available"
    )
    funnel_levels.append({
        "level":        "Disputes (if any)",
        "count":        None,
        "pct_of_total": None,
        "source":       case_digest_note,
        "dropout_from_previous": None,
        "data_gap":     True,
        "barrier":      "Process governed by the Tax Revenue Appeals Act "
                        "and Tribunal Rules 2018 -- see dispute_documents table"
    })

    funnel_levels.append({
        "level":        "Long-term compliance (repeat filing)",
        "count":        None,
        "pct_of_total": None,
        "source":       "No panel/longitudinal filing data available -- "
                        "this stage is a recommended M&E metric "
                        "(re-filing rate in year 2+), not yet measured",
        "dropout_from_previous": None,
        "data_gap":     True,
        "barrier":      "Unknown -- requires longitudinal TIN-registry "
                        "tracking, not a one-time survey"
    })

    # Revenue potential at each dropout point
    tax_pp      = params["mean_tax_informal_tzs"]
    uplift      = params["behavioral_uplift"]

    for level in funnel_levels:
        dropout = level["dropout_from_previous"]
        if dropout is not None and dropout > 0:
            rev_potential = (
                dropout * tax_pp * 0.30 * uplift
            )
            level["revenue_potential_tzs"] = round(
                rev_potential, 0
            )
        elif dropout is None:
            level["revenue_potential_tzs"] = None
        else:
            level["revenue_potential_tzs"] = 0

    # Sensitivity case: the TOTAL exemption rate (domestic + customs and excise) applied to the Payment stage
    payment_sensitivity = None
    if exemption_pct is not None and exemption_pct_total is not None:
        sens_dropout = round(filer_count * (exemption_pct_total / 100.0))
        payment_sensitivity = {
            "basis": "total exemption rate (domestic reliefs + customs and excise), "
                     f"{exemption_period} (a single quarter)",
            "exemption_pct_of_collection": exemption_pct_total,
            "level": "Pays in full (net of exemptions/reliefs)",
            "count": filer_count - sens_dropout,
            "pct_of_total": round((filer_count - sens_dropout) / 34_134_251 * 100, 2),
            "dropout_from_previous": sens_dropout,
            "revenue_potential_tzs": round(sens_dropout * tax_pp * 0.30 * uplift, 0),
            "primary_case": {"basis": params.get("exemption_rate_basis", "domestic"),
                             "exemption_pct_of_collection": exemption_pct},
        }

    # Biggest opportunity
    # Note: .get(key, 0) alone doesn't catch this -- the key exists on
    # every level (including the new data_gap stages), just with value
    # None, so the default is never triggered. `or 0` is needed to
    # actually treat None as 0 for the max() comparison.
    biggest = max(
        funnel_levels,
        key=lambda x: x.get("revenue_potential_tzs") or 0
    )

    result = {
        "funnel_levels":       funnel_levels,
        "total_adults":        34_134_251,
        "registered_taxpayers": 1_306_683,
        "compliance_gap":      32_827_568,
        "mm_no_tin_target":    23_140_012,
        "payment_stage_sensitivity": payment_sensitivity,
        "biggest_dropout_level": biggest["level"],
        "biggest_dropout_count": biggest["dropout_from_previous"],
        "biggest_revenue_potential_tzs": biggest[
            "revenue_potential_tzs"
        ],
        "source":              "FinScope Tanzania 2023",
        "methodology": (
            "Compliance funnel using FinScope Tanzania 2023 "
            "microdata (n=9,915, weighted to 34,134,251 adults) for "
            "the Registration/TIN/Filing stages. Variables: MM "
            "composite, c27__1 (National ID), c27__13 (TIN). Revenue "
            "potential at 30% capture rate with 1.35x behavioral "
            "uplift. Extended (task #28) to cover the full funnel -- "
            "Registration -> TIN -> Filing -> Payment -> Audit -> "
            "Dispute -> Long-term Compliance: the Payment stage uses "
            "a real but AGGREGATE proxy (MoF's DOMESTIC reliefs rate "
            "for Q1 2023/24, a single quarter; the total rate incl. "
            "customs and excise is kept as a sensitivity case; not an "
            "individual-filer measurement); "
            "Audit, Dispute, and Long-term Compliance stages carry "
            "data_gap=True with count/pct/dropout=None because no "
            "individual-level transition-rate data exists in any "
            "source loaded into this project (Historical Audit "
            "Findings, task #12, was explicitly confirmed not "
            "publicly available) -- these stages are still populated "
            "with real qualitative/legal grounding (specific Act "
            "sections, real tribunal case-law topics) rather than "
            "omitted, but their quantitative fields are honestly left "
            "unset rather than estimated."
        )
    }

    print(f"  Biggest dropout: {biggest['level']}")
    print(f"  Dropout count:   "
          f"{biggest['dropout_from_previous']:,}")
    print(f"  Revenue potential: "
          f"TZS {biggest['revenue_potential_tzs']/1e12:.1f}T")

    return result


# ============================================================
# ML SEGMENTATION MODEL: RETIRED (Block D3)
# The logistic regression trained on 50,000 SYNTHETIC records with typed coefficients was removed. The targeting model is now
# trained on the real FinScope respondents: src/04_models/targeting_model.py (outputs/stats/targeting_model.json).
# ============================================================


# ============================================================
# MASTER RUNNER
# ============================================================

def run_economic_model():
    """
    Runs the complete economic model.
    Produces economic_model.json for agent_v4.py.
    """
    print("\n" + "═" * 60)
    print("  ECONOMIC MODEL")
    print("  Python-based policy analytics")
    print("  Every number traceable to a formula")
    print("═" * 60 + "\n")

    params = load_base_params()

    print("STEP 1: CURRENT TAX BASE")
    print("-" * 40)
    current = calculate_current_tax_base(params)
    print(f"  Current revenue: "
          f"TZS {current['current_tax_revenue_tzs']:,.0f}")
    print(f"  Revenue gap: "
          f"TZS {current['revenue_gap_tzs']:,.0f}")
    print(f"  Gap as % of GDP: {current['revenue_gap_pct_gdp']}%")

    print("\nSTEP 2: SCENARIO ANALYSIS")
    print("-" * 40)
    print("  Running all economic calculations...")
    scenarios = run_scenario_analysis(params)

    print("\nSTEP 3: MONTE CARLO SIMULATION")
    print("-" * 40)
    monte_carlo = run_monte_carlo_simulation(params, 1000)

    print("\nSTEP 4: TAX MORALE MODEL")
    print("-" * 40)
    morale_model = build_tax_morale_model(params)

    print("\nSTEP 5: AGENT-BASED SIMULATION")
    print("-" * 40)
    agent_sim = run_agent_based_simulation(
        params, n_agents=paths.N_AGENTS, n_years=paths.N_YEARS, morale_model=morale_model
    )
    # Block E2.4: the same population WITHOUT the interventions (the scenario the calibration to TRA's registration trend is made on)
    agent_sim_baseline = run_agent_based_simulation(
        params, n_agents=paths.N_AGENTS, n_years=paths.N_YEARS, interventions=False, quiet=True
    )
    agent_sim["no_intervention_scenario"] = {k: agent_sim_baseline[k] for k in ("scenario", "initial_compliance_rate", "final_compliance_rate", "compliance_improvement",
                                                                                "cumulative_revenue_tzs", "average_annual_revenue_tzs", "yearly_results", "status")}
    agent_sim["intervention_effect_on_final_compliance_pp"] = round((agent_sim["final_compliance_rate"] - agent_sim_baseline["final_compliance_rate"]) * 100, 3)

    print("\nSTEP 7: DIGITAL TWIN: retired (Pass 6B-1); see src/retired/README.md and src/04_models/reach_scenarios.py")

    print("\nSTEP 8: CAUSAL INFERENCE: retired (Block D2); see src/04_models/tin_mobile_money.py")

    print("\nSTEP 10: SENSITIVITY ANALYSIS")
    print("-" * 40)
    sensitivity = run_sensitivity_analysis(params)

    print("\nSTEP 11: COMPLIANCE FUNNEL MODEL")
    print("-" * 40)
    funnel = build_compliance_funnel_model(params)

    print("\nSTEP 12: ML SEGMENTATION MODEL: retired (Block D3); see src/04_models/targeting_model.py")

    print("\nSTEP 13: DEMOGRAPHIC DIVIDEND")
    print("-" * 40)
    demographic = calculate_demographic_dividend(params)

    print("\nSTEP 14: MOBILE MONEY OPPORTUNITY")
    print("-" * 40)
    mobile_money = calculate_mobile_money_opportunity(params)

    print("\nSTEP 15: PROPERTY TAX OPPORTUNITY")
    print("-" * 40)
    property_tax = calculate_property_tax_opportunity(params)

    # ── Assemble full model ──────────────────────────────────
    run_meta.stamp("economic_model.json", "generated_at")
    full_model = {
        "data_sources": {
            "finscope": "FinScope Tanzania 2023 "
                       "(FSDT, NBS approval, n=9,915)",
            "world_bank": "World Bank API 2024",
            "oecd":       "OECD Revenue Statistics Africa 2023",
            "imf":        "IMF DataMapper",
            "tra":        "TRA Annual Report 2022/23",
        },
        "finscope_acknowledgement": (
            "The findings in this report are based on data "
            "collected by FinScope Tanzania 2023. The findings, "
            "interpretations, and conclusions expressed are "
            "entirely those of the authors and do not necessarily "
            "represent the views of FinScope Tanzania 2023."
        ),
        "base_parameters":         params,
        "current_tax_base":        current,
        "scenarios":               scenarios,
        "monte_carlo":             monte_carlo,
        "tax_morale_model":        morale_model,
        "agent_based_simulation":  agent_sim,
        "sensitivity_analysis":    sensitivity,
        "compliance_funnel":       funnel,
        "demographic_dividend":    demographic,
        "mobile_money_opportunity": mobile_money,
        "property_tax_opportunity": property_tax,
        "methodology_note": (
            "All figures calculated using Python formulas. "
            "No LLM estimates. Parameters from World Bank API, "
            "IMF DataMapper, OECD Revenue Statistics Africa, "
            "FinScope Tanzania 2023, and TRA Annual Reports. "
            "Behavioral uplift 1.35x from Rwanda RRA and "
            "UK HMRC behavioral tax studies. "
            "Monte Carlo: 1,000 iterations. "
            "Agent simulation: 500,000 synthetic citizens, "
            "10 years. Random seed: 42."
        )
    }

    with open(ECONOMIC_MODEL_OUTPUT, "w",
              encoding="utf-8") as f:
        json.dump(full_model, f, indent=2,
                  default=str)

    # assumption ledger: one stable-id entry per constant of config.yaml `assumptions:`
    from assumption_ledger import write_config_ledger
    write_config_ledger()

    print(f"\n  Economic model saved to "
          f"{ECONOMIC_MODEL_OUTPUT}")

    print("\n" + "═" * 60)
    print("  ECONOMIC MODEL COMPLETE")
    print("═" * 60)
    print(f"\n  Components built: 15")
    print(f"\n  Files produced:")
    print(f"  → {ECONOMIC_MODEL_OUTPUT}")
    print(f"\n  Next step: Run agent_v3c.py")
    print("═" * 60)

    return full_model


if __name__ == "__main__":
    run_economic_model()
    