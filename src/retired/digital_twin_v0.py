"""RETIRED (Pass 6B-1): the system-dynamics digital twin of the tax ecosystem, kept for the record. NOT imported by run_all.py, NOT tested, NOT in the dashboard.

Why it was retired: PASS6A D2 (the twin's year-10 increment of about TZS 6.15 trillion, about 22 times the whole FY2023/24 individuals' income tax collection, rests on registration and tax-rate
assumptions that no data fix), PASS6C E1 (the arithmetic behind it) and PASS6D F4 / F5 (the rescued, scale-checked version). The replacement is src/04_models/reach_scenarios.py (Figure 5.2).

To run it you would need the `twin.*` assumptions, which are listed in config.yaml under `retired_assumptions:` (restore them to `assumptions:` first) and the helpers of economic_model.py
(`from economic_model import load_base_params`). It is a snapshot of the code at the end of Pass 6A-6D, with the same names."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
from assumptions import A


# ============================================================
# DIGITAL TWIN OF TANZANIA'S TAX ECOSYSTEM (retired)
# ============================================================

def _bot_accounts_context():
    """Bank of Tanzania active mobile-money accounts (a context figure; data/processed/twin_inputs.json)."""
    try:
        with open(paths.TWIN_INPUTS, encoding="utf-8") as f:
            return json.load(f)["bot_active_mobile_money_accounts_context"]
    except (FileNotFoundError, KeyError):
        return {"value": None}


def run_digital_twin(params, n_years=10,
                      policy_changes=None):
    """
    A computational model of Tanzania's tax ecosystem
    as interacting systems:

    - Households (lifecycle stage populations)
    - MSMEs (enterprise stage)
    - Mobile money (transaction flows)
    - Banks (formal financial system)
    - TRA (revenue authority)
    - Local governments (service delivery)

    Simulates how policy changes propagate through
    the system and produce revenue outcomes.

    policy_changes: dict of parameter overrides
    Example:
        {"ussd_nudge_scale": 0.8,
         "trust_improvement_annual": 0.03}
    """
    print("\n  Running digital twin simulation...")

    # Default policy scenario (status quo)
    policy = {
        "ussd_nudge_scale":           0.0,    # Not deployed
        "trust_improvement_annual":   A("twin.default.trust_improvement_annual"),   # Slow drift
        "formalization_policy":       A("twin.default.formalization_policy"),  # 0.5%/year natural
        "presumptive_tax_simplification": False,
        "property_registry_reform":   False,
    }

    if policy_changes:
        policy.update(policy_changes)

    # System state variables
    state = {
        "year":               0,
        "registered_taxpayers": params["registered_taxpayers"],
        "compliance_rate":    params["tin_rate_pct"] / 100,
        "trust_score":        params["baseline_trust"],
        "mm_users":           params["mobile_money_users"],
        "mm_penetration":     params["mobile_money_users"] / params["adult_population"],
        "msme_registered":    int(
            params["enterprise_stage_population"] *
            A("twin.msme.tin_rate")   # FinScope: 9.7% enterprise TIN rate
        ),
        "tax_revenue_tzs":    (
            params["gdp_usd"] *
            params["tax_to_gdp_current"] *
            params["tzs_per_usd"]
        ),
        "gdp_tzs": (
            params["gdp_usd"] * params["tzs_per_usd"]
        ),
    }

    yearly_states = []

    for year in range(1, n_years + 1):

        # ── GDP grows ────────────────────────────────────────
        state["gdp_tzs"] *= (1 + params["gdp_growth_rate"])

        # ── Adults and mobile money (Block E3.3) ─────────────
        # Adults grow with the population; mobile-money PENETRATION (share of adults) rises toward a cap, closing a fixed share of the remaining gap each
        # year (ASSUMPTIONS twin.mm.penetration_cap, twin.mm.penetration_gap_closure). Users can therefore never exceed adults.
        adults_t = params["adult_population"] * A("twin.growth.adult_population") ** year
        pen_cap = A("twin.mm.penetration_cap")
        if state["mm_penetration"] < pen_cap:
            state["mm_penetration"] += A("twin.mm.penetration_gap_closure") * (pen_cap - state["mm_penetration"])
        state["mm_users"] = min(state["mm_penetration"] * adults_t, adults_t)
        assert state["mm_users"] <= adults_t, "twin: mobile-money users exceed adults"

        # ── Trust dynamics ───────────────────────────────────
        state["trust_score"] += policy["trust_improvement_annual"]

        state["trust_score"] = min(state["trust_score"], A("twin.cap.trust"))

        # ── New registrations ────────────────────────────────
        # Base formalization rate
        new_registrations = (
            state["gdp_tzs"] / params["tzs_per_usd"] /
            params["gdp_usd"] *
            policy["formalization_policy"] *
            params["working_age_population"]
        )

        # USSD nudge effect: applies only to mobile-money users NOT YET REGISTERED (Block E3.3). TRA's registrations are counts of TINs (some held by entities);
        # all of them are conservatively taken to be held by mobile-money users (FinScope: 360 of 361 adult TIN holders use mobile money), which shrinks the pool
        if policy["ussd_nudge_scale"] > 0:
            unregistered_users = max(0.0, state["mm_users"] - state["registered_taxpayers"])
            ussd_registrations = (
                unregistered_users *
                policy["ussd_nudge_scale"] *
                A("twin.ussd.conversion")  # conversion per year
            )
            new_registrations += ussd_registrations

        # Trust effect on registration
        trust_multiplier = 1 + (
            state["trust_score"] - params["baseline_trust"]
        ) * A("twin.trust_multiplier.slope")
        new_registrations *= trust_multiplier
        # registrations can never exceed the adult population (Block E3.3)
        new_registrations = max(0.0, min(new_registrations, adults_t - state["registered_taxpayers"]))

        state["registered_taxpayers"] += int(new_registrations)
        assert state["registered_taxpayers"] <= adults_t, "twin: registrations exceed adults"

        # ── Compliance rate: registrations per ADULT (all adults 16+, FinScope universe grown with the population) ──
        total_adults = adults_t
        state["compliance_rate"] = min(A("twin.cap.compliance_rate"),
            state["registered_taxpayers"] / total_adults
        )

        # ── Revenue calculation ──────────────────────────────
        # Start from current tax revenue baseline
        # scaled by GDP growth — this is the existing
        # formal sector revenue that the twin preserves
        baseline_revenue = (
            params["gdp_usd"] *
            params["tax_to_gdp_current"] *
            params["tzs_per_usd"] *
            (1 + params["gdp_growth_rate"]) ** year
        )

        # Additional revenue from new registrations
        # (new taxpayers above the 3.2M baseline)
        new_registrants = max(
            0,
            state["registered_taxpayers"] -
            params["registered_taxpayers"]
        )
        new_taxpayer_revenue = (
            new_registrants *
            params["mean_tax_informal_tzs"]                 # Block F1: statutory tax on the earnings distribution, not a flat rate on the mean
        )

        # Presumptive tax simplification uplift
        pt_revenue = 0
        if policy["presumptive_tax_simplification"]:
            pt_revenue = (
                state["msme_registered"] *
                params["mean_tax_msme_tzs"] * A("twin.presumptive.uplift_factor")      # mean presumptive tax per enterprise (Block F1)
            )

        state["tax_revenue_tzs"] = (
            baseline_revenue +
            new_taxpayer_revenue +
            pt_revenue
        )

        yearly_states.append({
            "year":                year,
            "gdp_tzs":             round(state["gdp_tzs"], 0),
            "registered_taxpayers": state["registered_taxpayers"],
            "compliance_rate":     round(
                state["compliance_rate"], 4
            ),
            "trust_score":         round(state["trust_score"], 3),
            "mm_users":            round(state["mm_users"], 0),
            "adults":              round(adults_t, 0),
            "mm_penetration":      round(state["mm_penetration"], 4),
            "tax_revenue_tzs":     round(
                state["tax_revenue_tzs"], 0
            ),
            "tax_to_gdp_pct":      round(
                state["tax_revenue_tzs"] /
                state["gdp_tzs"] * 100, 2
            ),
            "new_registrations_yr": int(new_registrations),
        })

    # Summary
    final = yearly_states[-1]
    initial_rev = (
        params["gdp_usd"] *
        params["tax_to_gdp_current"] *
        params["tzs_per_usd"]
    )

    result = {
        "label":                    "MODELLED scenario",
        "type":                     "MODELLED",
        "scenario_note":            "A scenario of the model's own structure with ASSUMPTION inputs (policy strengths, trust and norm dynamics, penetration cap); not a forecast and not a measured outcome.",
        "context_bot_active_mobile_money_accounts": dict(_bot_accounts_context(), note="context only (Block E3.3): BoT counts accounts, not persons; the twin uses FinScope's adult mobile-money users"),
        "policy_scenario":          policy,
        "n_years":                  n_years,
        "registered_taxpayers_definition": (
            "registered_taxpayers = TRA's count of TIN registrations on the Mainland (a stock of registrations, individuals and entities, business and "
            "non-business, active or dormant; base: 6.27 million at the end of 2023/24, NBS Tax Statistics Report 2023/24 from TRA; series in "
            "data/processed/tra_registered_taxpayers.csv). It is NOT FinScope's 1.31 million ADULT TIN holders (a survey estimate of adults who say they "
            "hold a TIN) and the twin's compliance_rate (registered taxpayers divided by the adults of the Entry, Active and Enterprise stages) is therefore "
            "a registrations-per-adult ratio (adults = FinScope's adults 16+, grown with the population), not an adult TIN rate."),
        "adults_in_final_year":     yearly_states[-1]["adults"],
        "mm_users_in_final_year":   yearly_states[-1]["mm_users"],
        "registered_taxpayers_never_exceed_adults": all(y["registered_taxpayers"] <= y["adults"] for y in yearly_states),
        "mm_users_never_exceed_adults": all(y["mm_users"] <= y["adults"] for y in yearly_states),
        "initial_tax_revenue_tzs":  round(initial_rev, 0),
        "final_tax_revenue_tzs":    final["tax_revenue_tzs"],
        "revenue_growth_tzs":       round(
            final["tax_revenue_tzs"] - initial_rev, 0
        ),
        "final_compliance_rate":    final["compliance_rate"],
        "final_registered_taxpayers": final["registered_taxpayers"],
        "final_tax_to_gdp_pct":     final["tax_to_gdp_pct"],
        "final_trust_score":        final["trust_score"],
        "yearly_states":            yearly_states,
        "methodology": (
            "System dynamics digital twin. "
            "Interacting: households, MSMEs, mobile money, "
            "TRA, local governments. "
            "Policy changes propagate through trust dynamics, "
            "social norms, and registration feedback loops."
        )
    }

    print(f"  Initial tax/GDP: "
          f"{params['tax_to_gdp_current']*100:.1f}%")
    print(f"  Final tax/GDP:   {final['tax_to_gdp_pct']}% "
          f"(Year {n_years})")
    print(f"  Revenue growth:  "
          f"TZS {result['revenue_growth_tzs']/1e12:.1f}T")
    print(f"  Final compliance: {final['compliance_rate']:.1%}")

    return result


