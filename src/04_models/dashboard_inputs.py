"""Dashboard v1.1: the two small input files of the interactive dashboard (aggregates only, no respondent-level rows).

  outputs/stats/scenario_lab_inputs.json   the parameters of the Table 5.1 simulation (stage_economics.simulate / _portfolio) for each stage, read from config.yaml, the assumptions
                                           register and the pipeline functions of stage_economics.py, so that dashboard/tdj_lib/scenario_lab.py (a pure-NumPy copy that reads ONLY this file)
                                           reproduces stage_economics.json. Nothing is typed here: every value comes from A(), the processed aggregates or the pipeline's own functions.
  outputs/stats/figure_5_1_inputs.json     what the interactive Figure 5.1 needs to recombine the six interventions with the model's own combination rule (economic_model.py,
                                           build_tax_morale_model): the driver scores, weights, the driver deltas of each intervention, the fitted alpha and beta and the combined discount.

Both files are written after stage_economics.py (they read its processed inputs and economic_model.json) and never change an existing output.
"""

import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import assumptions
from assumptions import A
import stage_economics as se

SCENARIO_LAB_INPUTS = paths.SCENARIO_LAB_INPUTS
FIGURE_5_1_INPUTS = paths.FIGURE_5_1_INPUTS


def _pending_signoffs():
    """Assumptions that feed the lab and have no sign-off yet, read from config.yaml (the `signoff` field of the entry, or register_extra_signoffs); retired ones are left out.
    The same rule as the `john_signoff` column of the assumptions register, without reading a file outside the pipeline's own inputs."""
    extra = paths.CFG.get("register_extra_signoffs") or {}
    out = []
    for k, e in paths.CFG["assumptions"].items():
        if not (k.startswith("stage.") or k.startswith("hbs.") or k.startswith("tax.")):
            continue
        if "retired_in" in e or str(e.get("basis", "")).upper() == "RETIRED":
            continue
        if not str(e.get("signoff", "") or extra.get(k, "")).strip():
            out.append({"key": k, "basis_class": e.get("basis", "")})
    return sorted(out, key=lambda r: r["key"])


def _signoff_of(key):
    e = paths.CFG["assumptions"].get(key, {})
    return e.get("signoff", "")


def build_scenario_lab_inputs():
    """The parameters of stage_economics.simulate() for every stage and income basis, as one dictionary."""
    cfg = se.cfg()
    seg = {}
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            seg[r["segment"]] = r
    with open(paths.CENSUS_AGE_COUNTS, encoding="utf-8") as f:
        seed_pop = float(json.load(f)["bands"]["seed_6_15"]["expanded_x10"])
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        conv = json.load(f)["tax_morale_model"]["calibration"]["conversion"]
    tax, _ageing = se.load_tax_base(from_processed=True)
    hbs = se.load_hbs()
    mapping = A("stage.intervention_for_uptake")
    basis_specs = {b: se.build_specs(seg, tax, hbs, se.BASES[b], conv, mapping, seed_pop) for b in se.BASES}
    names = se.names()
    reach, cost_overrun, sd = A("stage.reach_share"), float(A("stage.cost_overrun_sigma")), float(A("stage.uptake_log_odds_sd"))
    seed_lo, seed_hi = A("stage.cost.seed_tzs")
    stages = {"seed": {"name": names["seed"]["name"], "population": basis_specs["central"]["seed"]["population"], "cost_range_tzs": [float(seed_lo), float(seed_hi)],
                       "revenue": "none claimed: Seed counts as cost only"}}
    for s in se.STAGES[1:]:
        cen = basis_specs["central"][s]
        entry = {"name": names[s]["name"], "population": cen["population"], "p": cen["p"], "p_se": cen["p_se"], "mapped_intervention": cen["intervention"],
                 "odds_ratio": cen["odds_ratio"], "reach_triangle": [float(x) for x in reach[s]],
                 "stated_cost_tzs": float(se.stated_cost(s)) if s != "asset" else None,
                 "tax_per_registrant_tzs": {b: {"mean": basis_specs[b][s]["tax_mean"], "se": basis_specs[b][s]["tax_se"]} for b in se.BASES},
                 "age_earnings_multiplier": [float(x) for x in cen["multiplier"]]}
        stages[s] = entry
    pers = [float(x) for x in A("stage.persistence")]
    return {
        "label": "Parameters of the Table 5.1 Monte Carlo (src/04_models/stage_economics.py), read from config.yaml, the assumptions register and the pipeline; no respondent-level rows. "
                 "Read only by dashboard/tdj_lib/scenario_lab.py. MODELLED scenario inputs, not a forecast.",
        "evidence_type": "MODELLED (scenario); revenue per registrant COMPUTED from survey data with the statutory schedules CITED",
        "shared": {
            "stage_order": list(se.STAGES), "portfolio_stages": list(se.PORTFOLIO_STAGES), "revenue_stages": list(se.LEVERS), "owner_stages": list(se.OWNER_STAGES),
            "n_draws": int(cfg["n_draws"]), "seed": int(cfg["seed"]),
            "persistence_triangle": pers, "ramp_years": int(A("stage.ramp_years")), "uptake_log_odds_sd": sd, "cost_overrun_sigma": cost_overrun,
            "discount_rate": float(A("stage.discount_rate")), "discount_sensitivities": [float(r) for r in A("stage.discount_sensitivities")],
            "horizon_years": int(A("stage.horizon_years")), "long_horizon_years": int(cfg["long_horizon_years"]),
            "income_bases": {b: se.BASES[b] for b in se.BASES}, "income_basis_labels": {b: se.BASIS_LABEL[se.BASES[b]] for b in se.BASES}, "central_income_basis": "central",
            "persistence_fixed_sensitivities": [float(x) for x in cfg["persistence_sensitivity"]],
            "distributions": {
                "reach": "triangular(low, mode, high) of the stage's reach_triangle",
                "persistence": "triangular(persistence_triangle), or a fixed value",
                "p": "normal(p, p_se), clipped to [1e-4, 0.5]",
                "log_odds_ratio": "normal(ln(odds_ratio), shared.uptake_log_odds_sd), floored at 0",
                "tax_per_registrant": "normal(mean, se), floored at 0",
                "cost": "stated cost x exp(normal(0, shared.cost_overrun_sigma)); Seed: uniform(cost_range_tzs)",
                "draw_order": "one generator, seeded once; stages in stage_order, within a stage: reach, persistence, p, log odds ratio, tax, overrun (Seed: cost only)"},
        },
        "signoff": {k: _signoff_of(k) for k in ("stage.cost.seed_tzs", "stage.cost.entry_tzs", "stage.cost.active_tzs", "stage.cost.enterprise_tzs", "stage.cost.legacy_tzs", "stage.cost_overrun_sigma",
                                                  "stage.reach_share", "stage.uptake_log_odds_sd", "stage.persistence", "stage.ramp_years", "stage.horizon_years", "stage.discount_rate")},
        "assumptions_awaiting_signoff": _pending_signoffs(),
        "stages": stages,
    }


def build_figure_5_1_inputs():
    """What the interactive Figure 5.1 needs: the model's own combination rule (economic_model.build_tax_morale_model) with its fitted constants."""
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        m = json.load(f)["tax_morale_model"]
    cal = m["calibration"]
    drivers = list(m["baseline_scores"])
    effects = {}
    for key in m["intervention_effects"]:                        # the six interventions, from the model's own output; the driver deltas are the config assumptions tax_morale.effect.*
        effects[key] = {d: float(A("tax_morale.effect.%s.%s" % (key, d))) for d in drivers if ("tax_morale.effect.%s.%s" % (key, d)) in paths.CFG["assumptions"]}
    mapping = A("stage.intervention_for_uptake")
    stage_of = {v: k for k, v in mapping.items()}
    names = se.names()
    return {
        "label": "Inputs of the interactive Figure 5.1: the tax morale model's driver scores, weights, intervention deltas, fitted alpha and beta and the combined discount (economic_model.py build_tax_morale_model). "
                 "MODELLED; the effects are assumed uplifts.",
        "evidence_type": "MODELLED",
        "form": cal["form"], "alpha": cal["alpha"], "beta": cal["beta"], "combined_discount": float(A("tax_morale.combined_discount")),
        "baseline_scores": m["baseline_scores"], "weights": m["weights"], "drivers": drivers,
        "observed_adult_tin_rate": m["observed_anchor"]["value"], "observed_anchor_source": m["observed_anchor"]["source"],
        "interventions": {k: {"deltas": effects[k], "stage": stage_of.get(k), "stage_name": names[stage_of[k]]["name"] if k in stage_of else None} for k in m["intervention_effects"]},
        "reported": {"baseline_compliance_probability": m["baseline_compliance_probability"], "combined_intervention_probability": m["combined_intervention_probability"],
                     "naive_sum_of_solo_effects_pct": m["naive_sum_of_solo_effects_pct"],
                     "solo_new_compliance_prob": {k: v["new_compliance_prob"] for k, v in m["intervention_effects"].items()}},
        "combination_rule": m["combination_rule"],
    }


def run_dashboard_inputs():
    for path, builder in ((SCENARIO_LAB_INPUTS, build_scenario_lab_inputs), (FIGURE_5_1_INPUTS, build_figure_5_1_inputs)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(builder(), f, indent=1, ensure_ascii=False)
        print("  wrote", os.path.relpath(path, paths.ROOT))


if __name__ == "__main__":
    run_dashboard_inputs()
