"""Sensitivity of the published values to every in-scope constant (W12, Block C2.2).

For each constant of the config.yaml `assumptions:` block (except the DATA inputs read from files) the model function that
uses it is re-run with the constant multiplied by 1.2 and by 0.8 (lists and dicts: every numeric element), and the
PUBLISHED values of that function (the values that feed claims or the dashboard) are compared with the unperturbed run.

  flag ">5%"  : a +/-20% change moves at least one published value of that function by more than 5% (relative)
  flag "<=5%" : it does not
  flag "no effect" : the perturbed value is identical after rounding (small integers) or the constant is not used by that run

Integer-valued constants that must stay integers (ages, sample sizes, tenure) are rounded; if rounding returns the original
value the change is reported as "no effect". The tier-migration simulation is run with 50,000 agents instead of 500,000
(both the unperturbed and the perturbed runs), so its values differ slightly from the published ones; the comparison is
like with like. Random seeds are fixed, so the results are reproducible.
(Block D: the segmentation and causal groups were retired with their constants; the tier-migration runs resample the real FinScope agent cells.)
Block E3: the group "stage_economics" (stage.*, tax.*) re-runs the Table 40 Monte Carlo (stage_economics.run_stage_economics with 4,000 draws, outputs to a temporary
folder) and compares the published stage values (10-year and 20-year ROI medians, discounted revenue, portfolio ROI / NPV, Asset break-even cost); the agent / tier runner
reads the morale model's odds ratios. The "design" rows (simulation size and seed) are perturbed through the tier-migration runner.

Run:  python src/tools/assumption_sensitivity.py      (about 5 minutes; writes docs/assumption_sensitivity.json)
It is not part of run_all.py.
"""

import contextlib
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402
import assumptions  # noqa: E402
import economic_model as em  # noqa: E402
import stage_economics as se  # noqa: E402

DELTA = 0.20
THRESHOLD_PCT = 5.0
TIER_AGENTS = 50_000
INT_KEYS = {"tier.initial_tenure_low", "tier.initial_tenure_high"}


# ------------------------------------------------------------------ runners: return {published value name: number}
def _quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def run_morale():
    r = _quiet(em.build_tax_morale_model, em.load_base_params())
    out = {"baseline_compliance_probability": r["baseline_compliance_probability"],
           "combined_intervention_probability": r["combined_intervention_probability"],
           "naive_sum_of_solo_effects_pct": r["naive_sum_of_solo_effects_pct"]}
    for k, v in r["intervention_effects"].items():
        out["solo_" + k] = v["new_compliance_prob"]
    return out


def run_tier():
    r = _quiet(em.run_tier_migration_simulation, em.load_base_params(), n_agents=TIER_AGENTS)
    last = r["yearly_tier_distribution"][-1]
    return {"year10_" + k: v for k, v in last.items() if k != "year"}


def run_stage():
    """Published Table 40 values (Block E3.4): per stage the median ROI at 10 and 20 years and the discounted revenue, the portfolio ROI / NPV, the Asset break-even cost."""
    import tempfile
    saved = paths.CFG["stage_economics"]["n_draws"]
    paths.CFG["stage_economics"]["n_draws"] = 4000
    try:
        with tempfile.TemporaryDirectory() as d:
            r = _quiet(se.run_stage_economics, json_path=os.path.join(d, "s.json"), csv_path=os.path.join(d, "s.csv"), with_extras=False)
    finally:
        paths.CFG["stage_economics"]["n_draws"] = saved
    out = {}
    n_long = r["long_horizon_years"]
    v20 = "horizon_%d_aged" % n_long
    key = "%g" % r["discount_rate"]
    for s, st in r["stages"].items():
        mc = st["monte_carlo_at_10pct"]
        out["pv_revenue_median_10y_" + s] = mc["revenue_pv"]["median"]
        out["pv_revenue_median_20y_" + s] = st["variants"][v20][key]["revenue_pv"]["median"]
        if "roi" in mc and s != "seed":
            out["roi_median_10y_" + s] = mc["roi"]["median"]
            out["roi_median_20y_" + s] = st["variants"][v20][key]["roi"]["median"]
    pm = r["portfolio"]["monte_carlo_at_10pct"]
    out["portfolio_roi_median_10y"] = pm["roi"]["median"]
    out["portfolio_npv_median_10y"] = pm["npv"]["median"]
    out["portfolio_roi_median_20y"] = r["portfolio"]["variants"][v20][key]["roi"]["median"]
    return out


# the headline published values of each group (used for the ranking of the most sensitive constants)
HEADLINE = {
    "morale": ("baseline_compliance_probability", "combined_intervention_probability", "naive_sum_of_solo_effects_pct"),
    "tier": ("year10_not_registered_pct",),
    "stage_economics": ("portfolio_roi_median_10y", "roi_median_10y_"),
}


def is_headline(group, name):
    return any(name == h or (h.endswith("_") and name.startswith(h)) for h in HEADLINE[group])


RUNNERS = {"morale": run_morale, "tier": run_tier, "stage_economics": run_stage}


# ------------------------------------------------------------------ perturbation
def scaled(key, value, factor):
    """Value multiplied by factor (numbers inside lists/dicts too); booleans untouched; INT_KEYS rounded."""
    if isinstance(value, bool):                      # a switch: the "+20%" and "-20%" runs both flip it
        return not value

    def one(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            n = v * factor
            if key in INT_KEYS:
                n = int(round(n))
            return n
        return v
    if isinstance(value, list):
        return [one(x) for x in value]
    if isinstance(value, dict):
        return {k: one(x) for k, x in value.items()}
    return one(value)


def compare(base, new, only=None):
    """(max relative change in per cent, name of the most affected value); `only` restricts the values compared."""
    worst, name = 0.0, None
    for k, b in base.items():
        if only is not None and not only(k):
            continue
        n = new.get(k)
        if n is None or b is None:
            continue
        if b == n:
            continue
        rel = abs(n - b) / max(abs(b), 1e-12) * 100.0
        if rel > worst:
            worst, name = rel, k
    return worst, name


def run(limit_keys=None, verbose=True):
    keys = [k for k in assumptions.keys() if "value" in assumptions.entry(k) and assumptions.entry(k).get("group") in RUNNERS]
    if limit_keys:
        keys = [k for k in keys if k in limit_keys]
    base = {}
    for g, fn in RUNNERS.items():
        if any(assumptions.entry(k).get("group") == g for k in keys):
            base[g] = fn()
    results = {}
    for n, key in enumerate(keys, 1):
        e = assumptions.entry(key)
        g = e["group"]
        res = {"group": g, "published_values_compared": len(base[g])}
        worst, worst_name = 0.0, None
        h_worst, h_name = 0.0, None
        changed = False
        for label, factor in (("plus20", 1 + DELTA), ("minus20", 1 - DELTA)):
            v_new = scaled(key, e["value"], factor)
            if v_new == e["value"]:
                res[label] = {"max_rel_change_pct": 0.0, "most_affected": None, "note": "no effect (integer rounding)"}
                continue
            changed = True
            with assumptions.override({key: v_new}):
                out = RUNNERS[g]()
            rel, name = compare(base[g], out)
            h_rel, h_nm = compare(base[g], out, only=lambda k, g=g: is_headline(g, k))
            res[label] = {"max_rel_change_pct": round(rel, 3), "most_affected": name, "headline_max_rel_change_pct": round(h_rel, 3)}
            if rel > worst:
                worst, worst_name = rel, name
            if h_rel > h_worst:
                h_worst, h_name = h_rel, h_nm
        res["max_rel_change_pct"] = round(worst, 3)
        res["most_affected_value"] = worst_name
        res["headline_max_rel_change_pct"] = round(h_worst, 3)
        res["headline_most_affected"] = h_name
        res["flag"] = (">5%" if worst > THRESHOLD_PCT else "<=5%") if (changed and worst > 0) else "no effect"
        results[key] = res
        if verbose:
            print("  [%3d/%3d] %-55s %-6s max change %9.3f%%  (%s)" % (n, len(keys), key, res["flag"], worst, worst_name))
    return {"method": ("Each in-scope constant multiplied by 1.2 and 0.8 (lists and dicts: every numeric element); the model function that uses it "
                       "is re-run and its published values are compared with the unperturbed run. flag '>5%%' = a published value moves by more than 5%% "
                       "(relative). Tier-migration runs use %d agents. DATA inputs read from files (macro.*) are not perturbed." % TIER_AGENTS),
            "delta": DELTA, "threshold_pct": THRESHOLD_PCT, "tier_agents": TIER_AGENTS, "results": results}


def design_rows():
    """Sensitivity of the design rows of the register (simulation size and seed, Block E3.6): the tier-migration run with the agent count x0.8 / x1.2 and with two other seeds;
    the horizon, the disclosure rule and the dashboard design parameters are not model constants of a published value and are reported as not perturbed."""
    base = run_tier()
    rows = {}
    n0 = TIER_AGENTS
    worst, name = 0.0, None
    for f in (0.8, 1.2):
        old = em.paths.N_AGENTS
        out = _quiet(em.run_tier_migration_simulation, em.load_base_params(), n_agents=int(n0 * f))
        last = {"year10_" + k: v for k, v in out["yearly_tier_distribution"][-1].items() if k != "year"}
        rel, nm = compare(base, last)
        if rel > worst:
            worst, name = rel, nm
    rows["simulation.n_agents"] = {"max_rel_change_pct": round(worst, 3), "most_affected": name, "flag": ">5%" if worst > THRESHOLD_PCT else "<=5%",
                                   "text": "%s (max change %.1f%% in %s with %d and %d agents instead of %d; relative to the unperturbed run)" % (">5%" if worst > THRESHOLD_PCT else "<=5%", worst, name, int(n0 * 0.8), int(n0 * 1.2), n0)}
    worst, name = 0.0, None
    seed0 = em.RANDOM_SEED
    try:
        for sd in (seed0 + 1, seed0 + 2):
            em.RANDOM_SEED = sd
            rel, nm = compare(base, run_tier())
            if rel > worst:
                worst, name = rel, nm
    finally:
        em.RANDOM_SEED = seed0
    rows["simulation.random_seed"] = {"max_rel_change_pct": round(worst, 3), "most_affected": name, "flag": ">5%" if worst > THRESHOLD_PCT else "<=5%",
                                      "text": "%s (max change %.1f%% in %s with seeds %d and %d instead of %d)" % (">5%" if worst > THRESHOLD_PCT else "<=5%", worst, name, seed0 + 1, seed0 + 2, seed0)}
    rows["simulation.n_years"] = {"flag": "n/a", "text": "not perturbed: it defines the horizon of the published year-10 values (changing it changes which year is published)"}
    for k in ("disclosure.min_base", "disclosure.low_precision_numerator"):
        rows[k] = {"flag": "n/a", "text": "not perturbed: a publication rule that decides which cells are suppressed or flagged; it changes no model value"}
    for k in ("dashboard.min_n_for_confident_estimate", "dashboard.ngazi_standing_ceiling", "dashboard.legacy_blend_weights", "dashboard.illustrative_asset_score", "dashboard.illustrative_legacy_score"):
        rows[k] = {"flag": "n/a", "text": "not perturbed: a display / design parameter of the dashboard; no model output depends on it"}
    return rows


if __name__ == "__main__":
    out = run()
    out["design_rows"] = design_rows()
    os.makedirs(os.path.dirname(paths.ASSUMPTION_SENSITIVITY), exist_ok=True)
    with open(paths.ASSUMPTION_SENSITIVITY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    n5 = sum(1 for r in out["results"].values() if r["flag"] == ">5%")
    print("done: %d constants, %d move a published value by more than 5%%" % (len(out["results"]), n5))
