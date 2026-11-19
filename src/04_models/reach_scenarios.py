"""W-REACH (Pass 6B-1) - Reach scenarios: what the four stage tools could add to the revenue of the Tanzania Revenue Authority, at Table 5.1's reach and at 10, 25 and 50% reach (Figure 5.2).

Replaces the retired digital twin (src/retired/README.md; PASS6A D2, PASS6C E1, PASS6D F4/F5). Same arithmetic as Table 5.1 (stage_economics.py), so the two cannot disagree:
    new registrants of a stage = population x reach x [expit(logit p + ln OR) - p]      (the same 10,000 draws and seed as Table 5.1)
    registrants alive in year t = sum over entry years c (ramp of 5 years) of new/ramp x persistence^(t - c)
    incremental revenue in year t = alive x revenue per registrant (CENTRAL income basis: HBS 2017/18 receipts of owners with receipts; stage mapping B; Workers 25-44 have no lever)
    active payers owing tax = alive x the share of the stage's registrants who owe tax (> nil) under the central basis
Levers: Entry, Active, Enterprise, Legacy (four) and, as a secondary set, Entry + Active. Reach: Table 5.1's own draws (triangular, stage-specific) and a flat 10, 25 and 50%.
The TRA REGISTRATION TREND is its own component, drawn as its own dashed line and never added to a tool's effect: the formalisation trend of twin_inputs.json (calibrated on the TRA series)
registers new taxpayers each year whatever the tools do; they are priced with the TIN-holder-weighted mix of the stages' revenue per registrant (Workers 25-44 at the ILFS non-owner value).
Scale check: the year-10 increment against the TRA FY2024/25 collections (individuals' income tax; domestic revenue; total gross), CITED from the workbook (tra_collections.py).
Also stored: the full-reach implication of Figure 5.1 (the morale model has no reach factor), so that it is not read as comparable with Table 5.1.
Everything here is MODELLED (scenario); revenue per registrant is COMPUTED from survey data; the TRA figures are CITED. Not a forecast.

Outputs: outputs/stats/reach_scenarios.json, outputs/tables/reach_scenarios_year10.csv, outputs/tables/reach_scenarios_by_year.csv
"""
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
from assumptions import A
import stage_economics as se

LABEL = "[MODELLED] scenario: stage population x reach x uplift x revenue per registrant; not a forecast"
HORIZON = 10
SETS = {"four_levers": ["entry", "active", "enterprise", "legacy"], "entry_active": ["entry", "active"]}
REACH = {"table5_1_reach": None, "reach_10pct": 0.10, "reach_25pct": 0.25, "reach_50pct": 0.50}


def _delta(inp):
    return np.maximum(1.0 / (1.0 + np.exp(-(np.log(inp["p"] / (1 - inp["p"])) + inp["lnor"]))) - inp["p"], 0.0)


def cohort(spec, inp, owing_share, reach, draws, ramp):
    """Registrants (cumulative, alive), active payers owing tax and revenue by year for one stage (arrays years x draws)."""
    r = inp["reach"] if reach is None else np.full(draws, float(reach))
    new_total = np.minimum(spec["population"] * r * _delta(inp), spec["population"] * (1 - inp["p"]))       # never more than the stage's unregistered adults
    pers = inp["persist"]
    cum, alive = np.zeros((HORIZON, draws)), np.zeros((HORIZON, draws))
    for t in range(1, HORIZON + 1):
        cum[t - 1] = new_total * min(t, ramp) / ramp
        a = np.zeros(draws)
        for c in range(1, min(t, ramp) + 1):
            a += new_total / ramp * pers ** (t - c)
        alive[t - 1] = a
    return {"cum": cum, "alive": alive, "payers": alive * owing_share, "rev": alive * inp["tax"]}


def _q(a):
    return np.median(a, axis=1), np.percentile(a, 10, axis=1), np.percentile(a, 90, axis=1)


def trend_component(tax, hbs, specs, inputs, seg_rows, draws, ramp):
    """The TRA registration trend as its own component (registrants alive, active payers owing tax, revenue) priced with the TIN-holder-weighted mix of stage values."""
    tra_stock = float(A("base.registered_taxpayers"))
    trend = float(A("twin.default.formalization_policy")) * float(A("base.working_age_population"))
    fin_total = float(seg_rows["overall"]["tin_holders_weighted"])
    share_a = fin_total / tra_stock                                              # FinScope's adult TIN holders as a share of the TRA stock (the trend applies to adult holders only)
    holders = {s: float(seg_rows[s]["tin_holders_weighted"]) for s in ("entry", "active", "enterprise", "workers", "asset", "legacy")}
    tot = sum(holders.values())
    rng = np.random.default_rng(int(se.cfg()["seed"]) + 2)
    taxd, owing = np.zeros(draws), 0.0
    for s, h in holders.items():
        wk = h / tot
        if s == "workers":                                                       # HBS has no wage income: Workers 25-44 are priced at the ILFS non-owner value (the published Active value of Table 40)
            w = tax["workers_ilfs"]
            taxd += wk * np.clip(rng.normal(w["mean_tax_per_person_tzs"], w["se_tzs"], draws), 0.0, None)
            owing += wk * w["share_paying_any_tax_pct"] / 100.0
        else:
            taxd += wk * inputs[s]["tax"]
            owing += wk * se.tax_for(s, se.BASES["central"], tax, hbs)[2] / 100.0
    rng2 = np.random.default_rng(int(se.cfg()["seed"]) + 1)
    lo, mode, hi = A("stage.persistence")
    pers = rng2.triangular(lo, mode, hi, draws)
    alive = np.zeros((HORIZON, draws))
    for t in range(1, HORIZON + 1):
        a = np.zeros(draws)
        for c in range(1, t + 1):
            a += trend * share_a * pers ** (t - c)
        alive[t - 1] = a
    return {"alive": alive, "payers": alive * owing, "rev": alive * taxd, "mix_tax_median_tzs": float(np.median(taxd)), "share_owing": owing, "trend_new_registrants_per_year": trend * share_a}


def run_reach_scenarios(from_processed=False, json_path=None, year10_csv=None, by_year_csv=None):
    json_path = json_path or paths.REACH_SCENARIOS
    year10_csv = year10_csv or paths.REACH_YEAR10_CSV
    by_year_csv = by_year_csv or paths.REACH_BY_YEAR_CSV
    draws, ramp = int(se.cfg()["n_draws"]), int(A("stage.ramp_years"))
    seg = {}
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            seg[r["segment"]] = r
    with open(paths.CENSUS_AGE_COUNTS, encoding="utf-8") as f:
        seed_pop = float(json.load(f)["bands"]["seed_6_15"]["expanded_x10"])
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        morale = json.load(f)["tax_morale_model"]
    conv = morale["calibration"]["conversion"]
    tax, _ = se.load_tax_base(None, from_processed)
    hbs = se.load_hbs()
    specs = se.build_specs(seg, tax, hbs, se.BASES["central"], conv, A("stage.intervention_for_uptake"), seed_pop)
    inputs = se.draw_all(specs)
    owing = {s: se.tax_for(s, se.BASES["central"], tax, hbs)[2] / 100.0 for s in se.LEVERS}
    macro = json.load(open(paths.MACRO_INPUTS, encoding="utf-8"))["tanzania"]
    gdp0, ratio0, g_real = float(macro["gdp_lcu_tzs"]), float(macro["tax_to_gdp_pct"]) / 100.0, float(A("base.gdp_growth_rate"))
    gdp_t = np.array([gdp0 * (1 + g_real) ** t for t in range(1, HORIZON + 1)])
    tr = trend_component(tax, hbs, specs, inputs, seg, draws, ramp)
    base_total = ratio0 * gdp_t[:, None] + tr["rev"]
    by_year, y10 = [], []
    for sname, stages in SETS.items():
        for rname, rv in REACH.items():
            cs = [cohort(specs[s], inputs[s], owing[s], rv, draws, ramp) for s in stages]
            L = {k: sum(c[k] for c in cs) for k in ("cum", "alive", "payers", "rev")}
            dg = (base_total + L["rev"]) / gdp_t[:, None] * 100 - base_total / gdp_t[:, None] * 100
            for yi in range(HORIZON):
                rec = {"set": sname, "scenario": rname, "year": yi + 1}
                for nm, arr in (("registrants_cum", L["cum"]), ("alive_registrants", L["alive"]), ("active_payers_owing_tax", L["payers"]), ("incremental_revenue_tzs", L["rev"]), ("incremental_tax_to_gdp_pp", dg),
                                ("trend_revenue_tzs", tr["rev"]), ("trend_active_payers_owing_tax", tr["payers"])):
                    med, p10, p90 = _q(arr)
                    rec[nm + "_median"], rec[nm + "_p10"], rec[nm + "_p90"] = float(med[yi]), float(p10[yi]), float(p90[yi])
                by_year.append(rec)
            y10.append({"set": sname, "scenario": rname, "registrants_cum": float(np.median(L["cum"][-1])), "alive_registrants": float(np.median(L["alive"][-1])),
                        "active_payers_owing_tax": float(np.median(L["payers"][-1])), "payers_p10": float(np.percentile(L["payers"][-1], 10)), "payers_p90": float(np.percentile(L["payers"][-1], 90)),
                        "incremental_revenue_tzs": float(np.median(L["rev"][-1])), "revenue_p10": float(np.percentile(L["rev"][-1], 10)), "revenue_p90": float(np.percentile(L["rev"][-1], 90)),
                        "incremental_tax_to_gdp_pp": float(np.median(dg[-1]))})
    # ---- scale check against the TRA FY2024/25 collections (CITED) and the full-reach implication of Figure 5.1
    import tra_collections
    tra = tra_collections.run_tra_collections(from_processed=True)["tzs"]
    main = next(r for r in y10 if r["set"] == "four_levers" and r["scenario"] == "table5_1_reach")
    ea = next(r for r in y10 if r["set"] == "entry_active" and r["scenario"] == "table5_1_reach")
    hi = next(r for r in y10 if r["set"] == "four_levers" and r["scenario"] == "reach_50pct")
    scale = {"year10_increment_tzs": {"four_levers_table5_1_reach": main["incremental_revenue_tzs"], "entry_active_table5_1_reach": ea["incremental_revenue_tzs"], "four_levers_reach_50pct": hi["incremental_revenue_tzs"]},
             "tra_fy2024_25_tzs": {k: tra[k] for k in ("individuals_income_tax", "domestic_revenue", "total_gross", "paye")}, "pct_of": {}}
    for nm, v in scale["year10_increment_tzs"].items():
        scale["pct_of"][nm] = {"individuals_income_tax": v / tra["individuals_income_tax"] * 100, "domestic_revenue": v / tra["domestic_revenue"] * 100, "total_gross": v / tra["total_gross"] * 100}
    scale["note"] = ("the modelled increment is a small fraction of what TRA collects: it is nowhere near the retired twin's TZS 6.15 trillion (about 22 times the FY2023/24 individuals' income tax); "
                     "TRA FY2024/25 is nominal, the increment is in constant 2024 TZS (no wage growth or inflation)")
    adults = float(seg["overall"]["population_weighted"])
    base_p = morale["baseline_compliance_probability"]
    best = max(v["new_compliance_prob"] for v in morale["intervention_effects"].values())
    comb = morale["combined_intervention_probability"]
    fig51 = {"reading": "Figure 5.1 (tax morale model) has NO reach factor: it is the effect if every adult is reached, so it is not comparable with Table 5.1 or Figure 5.2, which multiply by reach",
             "adults_16_plus": adults, "baseline_tin_probability": base_p, "best_single_probability": best, "combined_probability": comb,
             "extra_tin_holders_best_single_at_full_reach": (best - base_p) * adults, "extra_tin_holders_combined_at_full_reach": (comb - base_p) * adults,
             "table5_1_new_registrants_median_four_levers": main["registrants_cum"]}
    result = {"label": LABEL, "evidence_type": "MODELLED (scenario); revenue per registrant COMPUTED (HBS 2017/18, ILFS 2024, statutory schedule CITED); TRA collections CITED", "income_basis": se.BASES["central"], "stage_mapping": "B",
              "horizon_years": HORIZON, "n_draws": draws, "seed": int(se.cfg()["seed"]), "sets": SETS, "reach_scenarios": {k: ("Table 5.1 reach (stage-specific triangular draws)" if v is None else "%d%% of every stage's adults" % round(v * 100)) for k, v in REACH.items()},
              "year10": y10, "by_year": by_year, "trend_component": {"label": "TRA registration trend: its own component, never added to a tool's effect", "new_registrants_per_year": tr["trend_new_registrants_per_year"],
                                                                      "mix_revenue_per_registrant_median_tzs": tr["mix_tax_median_tzs"], "share_owing_tax": tr["share_owing"],
                                                                      "year10_active_payers_owing_tax_median": float(np.median(tr["payers"][-1])), "year10_revenue_median_tzs": float(np.median(tr["rev"][-1]))},
              "scale_check_tra_fy2024_25": scale, "figure_5_1_full_reach_implication": fig51,
              "notes": ["Workers 25-44 have no revenue lever and are not in any scenario", "constant 2024 TZS: no wage growth or inflation; revenue is income tax and presumptive tax only (no VAT, no second-round effects)",
                        "80% bands are the 10th to 90th percentile of the Monte Carlo (the same draws as Table 5.1)"]}
    for p in (json_path, year10_csv, by_year_csv):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    with open(year10_csv, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        cols = list(y10[0]) + ["evidence_type"]
        wr.writerow(cols)
        for r in y10:
            wr.writerow(["%.6g" % r[c] if isinstance(r[c], float) else r[c] for c in cols[:-1]] + ["MODELLED (scenario)"])
    with open(by_year_csv, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        cols = list(by_year[0]) + ["evidence_type"]
        wr.writerow(cols)
        for r in by_year:
            wr.writerow(["%.6g" % r[c] if isinstance(r[c], float) else r[c] for c in cols[:-1]] + ["MODELLED (scenario)"])
    print("  Reach scenarios (central basis, mapping B): year-10 increment at Table 5.1 reach TZS %.2fB (four levers; %.2f%% of FY2024/25 individuals' income tax), at 50%% reach TZS %.2fB; Entry + Active %.2fB; %.0f active payers owing tax" % (
        main["incremental_revenue_tzs"] / 1e9, scale["pct_of"]["four_levers_table5_1_reach"]["individuals_income_tax"], hi["incremental_revenue_tzs"] / 1e9, ea["incremental_revenue_tzs"] / 1e9, main["active_payers_owing_tax"]))
    return result


if __name__ == "__main__":
    run_reach_scenarios()
