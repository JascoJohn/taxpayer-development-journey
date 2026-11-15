"""Generates docs/assumptions_register.csv (and docs/model_internals.csv) from config.yaml `assumptions:`,
docs/assumption_sensitivity.json and docs/constants_inventory_draft.csv.

The register has one row per in-scope constant: key, value, basis class, source / reference / rationale, claims and dashboard
values it feeds, sensitivity, and an empty `john_signoff` column for the owner to fill in. A claim fed by an UNKNOWN constant
is BLOCKED (listed in `blocks_claims`). Rows for dashboard-code design parameters and the simulation sizes in config.yaml
(`simulation:`) are added so that every ledger-relevant claim is covered.

Run:  python src/tools/build_assumptions_register.py
"""

import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import assumptions

CLAIM_RE = re.compile(r"C(\d{3})(?:-C(\d{3}))?")

# constants outside the config block that feed a claim or a dashboard value (documented, not moved)
EXTRA_ROWS = [
    ("simulation.n_agents", paths.CFG["simulation"]["n_agents"], "ASSUMPTION", "Size of the agent-based and tier-migration simulations (500,000), already in config.yaml `simulation:`. A stated design choice; results vary little with it.", "C061, C062", "config.yaml simulation:"),
    ("simulation.n_years", paths.CFG["simulation"]["n_years"], "ASSUMPTION", "Simulation horizon (10 years), already in config.yaml `simulation:`.", "C061, C062, C079", "config.yaml simulation:"),
    ("simulation.random_seed", paths.CFG["simulation"]["random_seed"], "ASSUMPTION", "Random seed 42 (reproducibility only), already in config.yaml `simulation:`.", "C061, C062, C027", "config.yaml simulation:"),
    ("disclosure.min_base", paths.CFG["disclosure"]["min_base"], "ASSUMPTION", "Disclosure rule (Block D1): a published cell with fewer unweighted respondents than this is suppressed. Replaced the dashboard's own threshold of 8 (MIN_N_FOR_ANY_ESTIMATE now reads this value).", "C060", "config.yaml disclosure:"),
    ("disclosure.low_precision_numerator", paths.CFG["disclosure"]["low_precision_numerator"], "ASSUMPTION", "Disclosure rule (Block D1): a published cell whose unweighted numerator is below this is flagged low precision (numerator withheld).", "C060", "config.yaml disclosure:"),
    ("dashboard.min_n_for_confident_estimate", 20, "ASSUMPTION", "Cells with fewer than 20 respondents are shown as indicative only (design parameter, MIN_N_FOR_CONFIDENT_ESTIMATE).", "C060", "dashboard code (not moved)"),
    ("dashboard.ngazi_standing_ceiling", 800, "ASSUMPTION", "Achievable ceiling of the Ngazi score is 800/1000 on purpose (design parameter in dashboard/pages/5_Asset.py; the report states it).", "C063", "dashboard code (not moved)"),
    ("dashboard.legacy_blend_weights", [0.667, 0.333], "ASSUMPTION", "Succession blend 0.667 / 0.333 of own score and successor score (design parameter in dashboard/pages/6_Legacy.py; the report states it).", "C066", "dashboard code (not moved)"),
    ("dashboard.illustrative_asset_score", 760, "ASSUMPTION", "Illustrative Asset Score output (760/1000) with illustrative component inputs; labelled illustrative in the caption (dashboard/pages/5_Asset.py).", "C076", "dashboard code (not moved)"),
    ("dashboard.illustrative_legacy_score", 92, "ASSUMPTION", "Illustrative Kodi Legacy Score output (92/100) with illustrative inputs (dashboard/pages/6_Legacy.py); the components sum to 100 but the card says 92.", "C077", "dashboard code (not moved)"),
]

# what each function of the inventory feeds (for the model-internals table)
INTERNALS = {
    "load_base_params": ("economic_model.json base_parameters, scenarios, monte_carlo, sensitivity_analysis, compliance_funnel revenue potential, property and mobile-money blocks", "no mapped claim and no dashboard value reads them; 10 base parameters, 5 morale baselines and the 4 macro values that feed in-scope functions were moved or replaced"),
    "calculate_mobile_money_opportunity": ("mobile_money_opportunity", "not quoted in the report, not displayed"),
    "run_scenario_analysis": ("scenarios (conservative / moderate / ambitious)", "not quoted in the report, not displayed (its totals feed only the sensitivity analysis)"),
    "calculate_demographic_dividend": ("demographic_dividend", "not quoted in the report, not displayed (capture rates 20% / 80%)"),
    "run_monte_carlo_simulation": ("monte_carlo", "not quoted in the report, not displayed"),
    "build_tax_morale_model": ("tax_morale_model", "in scope except the lifecycle-stage adjustments (by_lifecycle_stage), which no claim or page uses; all other constants moved. Block E1: three of the five baselines (trust, social norm, fairness) are DATA from Afrobarometer Round 8; simplicity and enforcement stay ASSUMPTIONS (no defensible mapping); the weights and effect sizes were not recalibrated"),
    "run_agent_based_simulation": ("agent_based_simulation", "its output is not quoted or displayed; the population constants it shares with the tier-migration simulation moved (agents.*); Block E1: trust and morale come from Afrobarometer and income from ILFS aggregate cell distributions (DATA), non-earners enter with zero income (ASSUMPTION); Block E3.1: interventions multiply the agents' yearly registration odds by the tax-morale model's odds ratios (the trust / morale uplift path and the norm feedback are retired)"),
    "run_tier_migration_simulation": ("tier_migration_simulation", "in scope: all constants moved (agents.*, tier.*); Block E1: trust, morale and income are DATA (aggregate cells of Afrobarometer Round 8 and ILFS 2024)"),
    "run_digital_twin": ("digital_twin_baseline, digital_twin_policy", "in scope: all constants moved (twin.*); Block E3.3: mobile-money users are FinScope adult users growing with the adult population plus a rise in penetration toward a cap; registrations and users never exceed adults; labelled MODELLED scenario"),
    "run_causal_inference_analysis": ("(removed)", "RETIRED in Block D2: difference-in-differences, simulated propensity-score matching and typed synthetic control removed; 30 constants listed as RETIRED in the register; replaced by the observational association in src/04_models/tin_mobile_money.py"),
    "run_sensitivity_analysis": ("sensitivity_analysis", "not quoted in the report, not displayed (test grids of the scenario model)"),
    "build_compliance_funnel_model": ("compliance_funnel", "not quoted in the report and not displayed; its Payment stage now reads the MoF rate (tax_exemption_rate.json) and the 65% filing share is a TRA estimate typed in the code"),
    "build_segmentation_model": ("(removed)", "RETIRED in Block D3: synthetic 50,000-record segmentation model removed (seg.*, lifecycle.* listed as RETIRED); replaced by src/04_models/targeting_model.py on real FinScope respondents"),
    "run_economic_model": ("assembly of economic_model.json", "the three twin-policy values moved (twin.policy.*); the 10 billion TZS budget is an optimizer setting"),
    "(module)": ("shared_context.json (agent infrastructure: macro stats table, personas, stage labels)", "not read by the model or the dashboard; typed copies of macro statistics there are stale (gdp, tax-to-GDP of peers) and are not used"),
}


def claims_in(text):
    out = []
    for m in CLAIM_RE.finditer(text or ""):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        out += ["C%03d" % i for i in range(a, b + 1)]
    return out


def sensitivity_text(res):
    if not res:
        return "not applicable (DATA input read from a file)" if True else ""
    return "%s (max change %.1f%% in %s)" % (res["flag"], res["max_rel_change_pct"], res.get("most_affected_value") or "-")


# label of each ASSUMPTION / UNKNOWN row (Block F0): what kind of statement the constant is; DATA, CALIBRATED and RETIRED rows carry none
LABEL_RULES = [
    (r"^tax_morale\.effect\.", "assumed uplift"),
    (r"^tax_morale\.(weight\.|combined_discount)", "assumed weight"),
    (r"^tax_morale\.baseline\.enforcement", "assumed score"),
    (r"^agents\.p_comply\.", "ranking weight"),
    (r"^tier\.(threshold\.|filing\.clip|initial_tenure)", "Ngazi design definition"),
    (r"^twin\.", "twin scenario assumption"),
    (r"^(simulation|disclosure|dashboard)\.", "technical/design parameter"),
    (r"^stage\.", "Table 40 scenario assumption"),
    (r"^(agents|tier)\.", "technical/design parameter"),
]
# notes appended to the sensitivity text of a row
SENSITIVITY_NOTES = {
    "tier.filing.clip_high": "NOTE: the large change is an artefact: +20% pushes the bound 0.99 above 1, which a reliability cannot exceed",
}


def label_of(key, basis):
    if basis not in ("ASSUMPTION", "UNKNOWN"):
        return ""
    for pat, lab in LABEL_RULES:
        if re.search(pat, key):
            return lab
    return "technical/design parameter"


def build(out_path=None):
    out_path = out_path or paths.ASSUMPTIONS_REGISTER
    try:
        with open(paths.ASSUMPTION_SENSITIVITY, "r", encoding="utf-8") as f:
            sens = json.load(f)["results"]
    except FileNotFoundError:
        sens = {}
    rows = []
    for key in sorted(assumptions.keys()):
        e = assumptions.entry(key)
        value = json.dumps(e["value"]) if "value" in e else "read from " + e["from"]
        rows.append({"key": key, "value": value, "basis_class": e["basis"], "source_reference_rationale": e["source"], "feeds": assumptions.feeds_text(key),
                     "sensitivity": sensitivity_text(sens.get(key)) if key in sens else "n/a (DATA read from a file)",
                     "location": "config.yaml assumptions:"})
    for key, value, basis, why, feeds, loc in EXTRA_ROWS:
        rows.append({"key": key, "value": json.dumps(value), "basis_class": basis, "source_reference_rationale": why, "feeds": assumptions.expand_tokens(feeds),
                     "sensitivity": "not computed (not part of the model run)", "location": loc})
    for key, e in sorted((paths.CFG.get("retired_assumptions") or {}).items()):
        value = json.dumps(e["value"]) if "value" in e else "read from " + e.get("from", "")
        rows.append({"key": key, "value": value, "basis_class": "RETIRED",
                     "source_reference_rationale": "RETIRED (%s): %s | former basis %s: %s" % (e.get("retired_in", ""), e.get("retired_reason", ""), e["basis"], e["source"]),
                     "feeds": assumptions.expand_tokens(e["feeds"]), "sensitivity": "n/a (retired; not read by any code)", "location": "config.yaml retired_assumptions:"})
    signoffs = {k: assumptions.entry(k)["signoff"] for k in assumptions.keys() if assumptions.entry(k).get("signoff")}
    signoffs.update(paths.CFG.get("register_extra_signoffs") or {})                 # simulation.*, disclosure.*, dashboard.* rows live outside the assumptions block
    sens_notes = SENSITIVITY_NOTES
    blocked = {}
    for r in rows:
        if r["basis_class"] == "UNKNOWN" and r["key"] not in signoffs:       # Block E3.5: an UNKNOWN constant the owner has signed off as a stated assumption no longer blocks its claims
            for c in claims_in(r["feeds"]):
                blocked.setdefault(c, []).append(r["key"])
    unsigned_published = []
    for r in rows:
        r["blocks_claims"] = "; ".join(sorted(set(claims_in(r["feeds"])) & set(blocked))) if (r["basis_class"] == "UNKNOWN" and r["key"] not in signoffs) else ""
        r["john_signoff"] = signoffs.get(r["key"], "")
        r["label"] = label_of(r["key"], r["basis_class"])
        if r["key"] in sens_notes:
            r["sensitivity"] = r["sensitivity"] + "; " + sens_notes[r["key"]]
        if r["basis_class"] in ("ASSUMPTION", "UNKNOWN") and not r["john_signoff"] and (claims_in(r["feeds"]) or "dashboard" in r["feeds"].lower()):
            unsigned_published.append(r["key"])
    cols = ["key", "value", "basis_class", "label", "source_reference_rationale", "feeds", "sensitivity", "location", "blocks_claims", "john_signoff"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    build.unsigned_published = unsigned_published

    # model internals table (one table, by function of the constants inventory)
    inv_path = os.path.join(paths.ROOT, "docs", "constants_inventory_draft.csv")
    with open(inv_path, "r", encoding="utf-8-sig", newline="") as f:
        inv = list(csv.DictReader(f))
    by_fn = {}
    for r in inv:
        by_fn.setdefault((r["file"], r["function"]), 0)
        by_fn[(r["file"], r["function"])] += 1
    with open(os.path.join(paths.ROOT, "docs", "model_internals.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["file", "function", "constants_in_inventory", "outputs_it_feeds", "status_and_reason"])
        for (file, fn), n in sorted(by_fn.items()):
            if file == "shared_context.py" and fn != "(module)":
                outs, why = INTERNALS["(module)"]
            else:
                outs, why = INTERNALS.get(fn, INTERNALS["(module)"] if file == "shared_context.py" else ("", ""))
            w.writerow([file, fn, n, outs, why])
    return rows, blocked


if __name__ == "__main__":
    rows, blocked = build()
    import collections
    print(len(rows), "rows;", dict(collections.Counter(r["basis_class"] for r in rows)))
    print("blocked claims:", len(blocked), sorted(blocked))
