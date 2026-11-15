"""E2.4 / E3.1 - calibration of the agent-based simulation to TRA's registered-taxpayer trend.

Block E3.1 harmonised the agent mechanism with the tax-morale model: trust and morale no longer evolve (the uplift path and the community-norm feedback are retired);
interventions multiply the agent's yearly registration ODDS by the morale model's odds ratios. The no-intervention path changed structurally, so this calibration (same
target, same method) was re-run. Block E3.2 looked for a third, independent target and found none that is compatible (see `third_target_search` in the output); the
two-target calibration is kept and its identified combination is reported.

Target. The NO-INTERVENTION scenario (the USSD nudge and the urban education programme switched off) must
reproduce the growth of TRA's registered taxpayers over the overlapping years 2017/18 - 2023/24 (data/processed/tra_registered_taxpayers.csv).
Scaling. TRA counts TIN registrations (Mainland stock, individuals and entities), the agents carry an adult TIN rate. The TRA series is therefore used as an
INDEX anchored to the FinScope 2023 adult TIN rate: target(t) = 3.83% x registered(t) / registered(2023/24). The simulated population starts in 2017/18 at
target(2017/18) (the starting propensities are rescaled, ranking kept) and runs 6 years; simulated year k is compared with fiscal year 2017/18 + k.
Free parameters (2, against 6 target points): agents.conversion_rate and a new intercept of the compliance-probability formula, agents.p_comply.intercept.
Every other constant keeps its current value. Method: Nelder-Mead on the sum of squared differences (percentage points), fixed seed and common random numbers
(the simulation is a deterministic function of the two parameters), then finite-difference identifiability diagnostics and profiles.

Output: data/processed/agent_calibration.json (parameters, fit, identifiability, scaling statement).
"""

import csv
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import minimize, minimize_scalar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import assumptions

CFG = paths.CFG["agent_calibration"]


def _em():
    import economic_model
    return economic_model


def targets():
    with open(paths.TRA_REGISTERED_TAXPAYERS_CSV, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "used"]
    last = float(rows[-1]["registered_taxpayers"])
    anchor = _em().observed_adult_tin_rate()
    n = int(CFG["years"])
    tail = rows[-(n + 1):]
    return [r["fiscal_year"] for r in tail], np.array([anchor * float(r["registered_taxpayers"]) / last for r in tail]), anchor


def simulate(theta, params, n_agents, years, start_rate, full=False):
    """No-intervention path of the adult registration rate for `years` years (array of exact rates); the full result of the run if `full`."""
    conv, intercept = float(10 ** theta[0]), float(theta[1])
    em = _em()
    with assumptions.override({"agents.conversion_rate": conv, "agents.p_comply.intercept": intercept}):
        res = em.run_agent_based_simulation(params, n_agents=n_agents, n_years=years, interventions=False, initial_rate=start_rate, quiet=True)
    if full:
        return res
    return np.array([r["compliance_rate_exact"] for r in res["yearly_results"]])


def run_agent_calibration(json_path=None, n_agents=None):
    json_path = json_path or paths.AGENT_CALIBRATION
    em = _em()
    n_agents = int(n_agents or CFG["n_agents"])
    params = em.load_base_params()
    fys, tgt, anchor = targets()
    start, obs = tgt[0], tgt[1:]
    years = len(obs)

    def resid(theta):
        return (simulate(theta, params, n_agents, years, start) - obs) * 100.0         # percentage points

    def sse(theta):
        r = resid(theta)
        return float(np.sum(r ** 2))

    lo_c, hi_c = float(CFG["log10_conversion_bounds"][0]), float(CFG["log10_conversion_bounds"][1])
    lo_a, hi_a = float(CFG["intercept_bounds"][0]), float(CFG["intercept_bounds"][1])

    def bounded(theta):                              # penalise leaving the bounds so Nelder-Mead stays inside
        pen = 0.0
        if not (lo_c <= theta[0] <= hi_c):
            pen += 1e3 * (max(lo_c - theta[0], 0) + max(theta[0] - hi_c, 0)) + 1e3
        if not (lo_a <= theta[1] <= hi_a):
            pen += 1e3 * (max(lo_a - theta[1], 0) + max(theta[1] - hi_a, 0)) + 1e3
        return pen
    best = None
    for st in CFG["starts"]:
        r = minimize(lambda t: sse(t) + bounded(t), np.array(st, float), method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": int(CFG["max_iter"])})
        if best is None or r.fun < best.fun:
            best = r
    theta = best.x
    r0 = resid(theta)
    rmse = float(math.sqrt(np.mean(r0 ** 2)))

    # identifiability: Jacobian of the residuals by central differences, covariance sigma^2 (J'J)^-1
    steps = np.array([0.01, 0.002])
    J = np.zeros((years, 2))
    for j in range(2):
        d = np.zeros(2); d[j] = steps[j]
        J[:, j] = (resid(theta + d) - resid(theta - d)) / (2 * steps[j])
    jtj = J.T @ J
    sing = np.linalg.svd(J, compute_uv=False)
    try:
        s2 = float(np.sum(r0 ** 2) / max(years - 2, 1))
        cov = s2 * np.linalg.inv(jtj)
        se = np.sqrt(np.diag(cov))
        corr = float(cov[0, 1] / (se[0] * se[1]))
    except np.linalg.LinAlgError:
        se, corr = np.array([float("nan")] * 2), float("nan")
    # profiles: fix one parameter on a grid, re-optimise the other
    prof = {"conversion": [], "intercept": []}
    for d in CFG["profile_offsets"]["log10_conversion"]:
        c = theta[0] + d
        f = lambda a: sse(np.array([c, a]))
        rr = minimize_scalar(f, bounds=(lo_a, hi_a), method="bounded", options={"xatol": 1e-4, "maxiter": 40})
        prof["conversion"].append({"log10_conversion": float(c), "conversion_rate": float(10 ** c), "best_intercept": float(rr.x), "rmse_pp": float(math.sqrt(rr.fun / years))})
    for d in CFG["profile_offsets"]["intercept"]:
        a = theta[1] + d
        f = lambda c: sse(np.array([c, a]))
        rr = minimize_scalar(f, bounds=(lo_c, hi_c), method="bounded", options={"xatol": 1e-3, "maxiter": 40})
        prof["intercept"].append({"intercept": float(a), "best_log10_conversion": float(rr.x), "best_conversion_rate": float(10 ** rr.x), "rmse_pp": float(math.sqrt(rr.fun / years))})

    full = simulate(theta, params, n_agents, years, start, full=True)
    sim = np.array([r["compliance_rate_exact"] for r in full["yearly_results"]])
    mean_index = full["mean_index_non_registered_at_start"]
    # the identified combination: conversion x (mean index + intercept) = the average yearly registration probability of a non-registered agent (before clipping at 0 and 1)
    combo = float(10 ** theta[0]) * (mean_index + float(theta[1]))
    for pt in prof["conversion"]:
        pt["combination_conversion_x_index_plus_intercept"] = pt["conversion_rate"] * (mean_index + pt["best_intercept"])
    for pt in prof["intercept"]:
        pt["combination_conversion_x_index_plus_intercept"] = pt["best_conversion_rate"] * (mean_index + pt["intercept"])
    combos = [pt["combination_conversion_x_index_plus_intercept"] for pt in prof["conversion"] if pt["rmse_pp"] <= rmse * 1.2]
    fit = [{"year_index": k + 1, "fiscal_year": fys[k + 1], "target_adult_registration_rate_pct": float(obs[k] * 100), "simulated_pct": float(sim[k] * 100), "difference_pp": float((sim[k] - obs[k]) * 100)} for k in range(years)]
    flat = [p["rmse_pp"] for p in prof["conversion"]]
    result = {
        "label": "calibration of the no-intervention agent simulation to TRA's registered-taxpayer trend",
        "type": "CALIBRATED", "status": "fit ok" if rmse <= float(CFG["rmse_ok_pp"]) else "FIT NOT ACCEPTABLE",
        "target": {"series": "TRA registered taxpayers, Mainland, NBS Tax Statistics Reports (data/processed/tra_registered_taxpayers.csv)", "fiscal_years": fys,
                   "scaling": "index anchored to the FinScope 2023 weighted adult TIN rate (%.4f%%): target(t) = anchor x registered(t) / registered(%s); TRA counts TIN registrations, the agents carry an adult registration rate, so only the GROWTH of the series is matched" % (anchor * 100, fys[-1]),
                   "start_rate_pct": float(start * 100), "points_fitted": years},
        "method": {"free_parameters": 2, "target_points": years, "algorithm": "Nelder-Mead (scipy) on the sum of squared differences in percentage points, starts %s, %d agents, fixed seed (common random numbers)" % (CFG["starts"], n_agents),
                   "fixed": "every other constant of the simulation keeps its current value; the interventions (USSD nudge, urban education) are off; trust and morale are static (Block E3.1: the community-norm feedback and the trust / morale uplift path are retired)"},
        "parameters": {"conversion_rate": float(10 ** theta[0]), "intercept": float(theta[1]), "log10_conversion_rate": float(theta[0]),
                       "previous": {"conversion_rate": 0.15, "intercept": 0.0}},
        "fit": {"rmse_pp": rmse, "table": fit, "converged": bool(best.success), "sse": float(best.fun), "n_function_evaluations": int(best.nfev)},
        "identifiability": {"standard_errors": {"log10_conversion_rate": float(se[0]), "intercept": float(se[1])}, "correlation_between_parameters": corr,
                            "singular_values_of_jacobian": [float(x) for x in sing], "condition_number": float(sing[0] / sing[-1]) if sing[-1] > 0 else float("inf"),
                            "profile_rmse_over_conversion_rate": prof["conversion"], "profile_rmse_over_intercept": prof["intercept"],
                            "reading": "a correlation near +-1 or a flat profile means the two parameters are not separately identified by six points; the product conversion x (weighted index + intercept) is what the data pin down",
                            "identified_combination": {"definition": "conversion_rate x (mean index of the non-registered agents at the start + intercept): the average yearly registration probability of a non-registered agent before clipping (index = trust, morale, income-rank and mobile-money terms)",
                                                       "value": combo, "value_pct_per_year": combo * 100, "mean_index_non_registered_at_start": mean_index, "conversion_rate": float(10 ** theta[0]), "intercept": float(theta[1]),
                                                       "range_over_profile_points_with_rmse_within_20pct_of_best": [float(min(combos)), float(max(combos))],
                                                       "fit_rmse_pp": rmse, "mean_hazard_after_clipping_pct": full["mean_yearly_registration_probability_non_registered_at_start"] * 100}},
        "third_target_search": CFG.get("third_target_search", {}),
    }
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print("  agent calibration: conversion %.5f, intercept %.4f; RMSE %.3f pp over %d points; parameter correlation %.2f; status %s" % (10 ** theta[0], theta[1], rmse, years, corr, result["status"]))
    return result


if __name__ == "__main__":
    run_agent_calibration()
