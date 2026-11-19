"""E2.5 / E3.4 - W11 Table 40: costs, revenues, NPV and ROI for the stages, rebuilt without typed revenue.

Replaces the report's Table 40 revenue column (Entry 8.7-9B, Active 12.8-13B, Enterprise 4.1B, Legacy 2.5B; ROI 20.7x, 21.3x, ~5.5x, ~3.6x), which came from typed
constants (the Entry / Active revenues) or had no source (Enterprise, Legacy), with a calculation whose every uncertain input is an explicit, documented
distribution in config.yaml (assumptions: stage.*).

For each adult stage s (Entry, Active, Enterprise, Asset, Legacy):
    new registrants = N_s x reach_s x [expit(logit(p_s) + ln OR_s) - p_s]
        N_s     stage population (FinScope 2023, outputs/tables/tin_by_segment.csv)
        p_s     the stage's observed weighted TIN rate (with its standard error)
        OR_s    odds ratio of the mapped intervention in the recalibrated morale model (E2.3; an ASSUMPTION uplift); the mapping uses the report's own names (E3.4)
        reach_s share of the stage reached within the ramp period (ASSUMPTION, triangular)
    revenue per registrant per year = mean, over the persons of the stage's target group who are NOT already in the formal net (not a formal employee with social
        security, not the owner of a registered business: ilfs_indicators.classify), of the statutory tax on ILFS 2024 earnings (resident income tax schedule; presumptive
        tax on gross business receipts, up to TZS 100M, for the Enterprise group), zero earners included: DATA-derived. Formal employees are excluded because PAYE
        already registers them, so the marginal registrant is an informal or non-working person
    registrants accumulate over the ramp years and persist at a yearly rate (ASSUMPTION); revenue is received at the end of each year of the horizon,
    discounted at 10% (5% and 12% as sensitivities) with annuity factors from the formula; cost = the report's own stated figure at the start of year 1.
Seed: cost only ("no revenue claimed"; no intervention effect is mapped to Seed). Monte Carlo: 10,000 draws, fixed seed, explicit distributions for reach, observed rate,
log odds ratio, persistence, revenue per registrant and cost. Reported: mean, median and 80% interval (10th-90th percentile) of the discounted revenue, cost, NPV and ROI
(= discounted revenue / cost) per stage and for the portfolio.

Block E3.4 additions
  * 20-year sensitivity next to the signed-off 10-year horizon (the 10-year results are unchanged: flat tax per registrant, as signed off). In the 20-year results the
    revenue per registrant follows the cohort's AGE-EARNINGS path: a registrant of the stage's target group is placed in ILFS age bands (5-year bands, aggregate
    profiles only) and, k years after registering, pays the mean statutory tax of persons of that stage's type (all / non-owners / owners; outside the formal net) of the age
    reached; the path is the ratio g(k) / g(0) of the cohort's mean tax at age + k to its mean tax at registration. The same ageing is applied to every stage. No wage
    growth or inflation (constant TZS, thresholds fixed). The 10-year horizon with ageing is reported as well, so the effect of ageing can be separated from the horizon.
  * the 20-year results at the signed-off persistence distribution and at fixed persistence 0.75, 0.90 and 0.95 (the signed-off value is not changed).
  * Asset: the 617.5M placeholder cost is retired; the BREAK-EVEN COST (the programme cost at which ROI = 1, i.e. the discounted revenue) is reported at 10 / 5 / 12% and for
    10 and 20 years; Asset is excluded from the portfolio cost and ROI, and its revenue is reported separately.

Pass 6B-1 (stage mapping B and bracketed revenue per registrant)
  * Active = business owners without a formal step, Enterprise = owners with a formal step (both 25-64); Workers 25-44 are unpriced (no revenue lever); Asset = non-owners 45-64.
  * INCOME BASIS of the Active and Enterprise revenue per registrant (`income_basis`): hbs_receipts_owners = CENTRAL (HBS 2017/18 receipts of owners with receipts, CPI-uprated, presumptive
    schedule; Pass 6D variant V3), ilfs_gross = bracket HIGH (ILFS 2024 gross receipts, V1), hbs_all_owners = bracket LOW (HBS, all owners, zeros kept, V2). ILFS is never shown alone. Entry, Asset
    and Legacy keep the ILFS values in every basis.
  * The twelve-month nil period is a SENSITIVITY only (legally fitted share of new businesses; full first-year variant).
  * Table 5.1 (central + bracket), Table 5.2 (persistence), break-even revenue per registrant, P(ROI >= 1), 20-year ROI and the central-case tornado are written next to Table 40.

Outputs: outputs/stats/stage_economics.json, outputs/tables/table40_stage_economics.csv (central basis), table5_1_stage_economics.csv, table5_2_persistence_sensitivity.csv,
table5_1_nil_period_sensitivity.csv, fig5_4_tornado_central.csv
"""

import csv
import json
import math
import os
import sys

import copy

import numpy as np
import pyreadstat

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import assumptions
from assumptions import A
import disclosure

LABEL = "scenario calculation: statutory tax on survey earnings x assumed reach and uptake; not a forecast"
STAGES = ["seed", "entry", "active", "enterprise", "asset", "legacy"]
PORTFOLIO_STAGES = ["seed", "entry", "active", "enterprise", "legacy"]      # Asset is excluded from the portfolio cost and ROI (E3.4)
REPORT_TABLE40 = {"seed": "260M-1.06B / not scored", "entry": "420M / 8.7-9B / 20.7x", "active": "600M / 12.8-13B / 21.3x", "enterprise": "750M / 4.1B / ~5.5x",
                  "asset": "not yet modeled", "legacy": "700M / 2.5B / ~3.6x"}
# stage -> (age range of the target group, type of persons whose age-earnings profile applies)
GROUP = {"entry": (16, 24, "all"), "active": (25, 64, "owner"), "enterprise": (25, 64, "owner"), "asset": (45, 64, "nonowner"), "legacy": (65, 97, "all")}      # stage mapping B (Pass 6B-1)
OWNER_STAGES = ("active", "enterprise")
LEVERS = ["entry", "active", "enterprise", "legacy"]                         # the four stages with a revenue lever (Seed is cost only, Asset has no cost, Workers are unpriced)
# income basis -> role in the bracket (owner decision 2)
BASES = {"central": "hbs_receipts_owners", "high": "ilfs_gross", "low": "hbs_all_owners"}
assert A("stage.income_basis_bracket") == BASES, "config.yaml stage.income_basis_bracket differs from the bases implemented in stage_economics.py"
assert A("stage.workers_unpriced") is True, "only the Workers-unpriced mapping is implemented"
BASIS_LABEL = {"hbs_receipts_owners": "HBS 2017/18 receipts of owners with receipts in the reference month (central)", "ilfs_gross": "ILFS 2024 gross receipts of owners (bracket high; never shown alone)",
               "hbs_all_owners": "HBS 2017/18 receipts of all owners, zeros kept (bracket low)"}
HBS_KEY = {"hbs_receipts_owners": "central_owners_with_receipts", "hbs_all_owners": "low_all_owners"}
MAX_AGE = 97


def cfg():
    return paths.CFG["stage_economics"]


def names():
    """Page and Table 40 label of each stage in the report, with the stage tool's name from the top-level `names:` block (Editing Pass 1)."""
    out = {}
    for s, v in cfg()["report_names"].items():
        out[s] = dict(v, name=paths.CFG["names"][s]["full"])
    return out


def annuity_factor(rate, years):
    """Present value of 1 received at the end of each of `years` years at discount `rate`: (1 - (1 + r)^-n) / r."""
    return (1.0 - (1.0 + rate) ** (-years)) / rate if rate else float(years)


from statutory_tax import pit, presumptive, owner_tax   # noqa: E402  (the schedules live in statutory_tax.py since Block F1; re-exported here)


def _weighted_mean_se(x, w):
    m = float(np.average(x, weights=w))
    se = float(np.sqrt(np.sum((w * (x - m)) ** 2)) / np.sum(w))           # ratio-estimator SE ignoring clustering (documented)
    return m, se


def ageing_paths(profiles, shares, n_years):
    """Age-earnings multipliers m(k) = g(k) / g(0), k = 0 .. n_years-1, per stage (Block E3.4).

    profiles[type][age] = mean statutory tax of persons of that type (outside the formal net) at that age (a step function of the 5-year ILFS band);
    shares[stage] = {band_index: share of the stage's target group in that band}. Registrants are spread uniformly over the ages of each band within the group's age
    range; k years after registering a registrant is k years older (ages above 97 keep the profile of 97; deaths and drop-outs are in the persistence rate)."""
    bands = [tuple(b) for b in cfg()["age_bands"]]
    paths_ = {}
    for s, (lo, hi, typ) in GROUP.items():
        prof = profiles[typ]
        ages, wts = [], []
        for bi, (blo, bhi) in enumerate(bands):
            sh = shares[s].get(bi, 0.0)
            if sh <= 0:
                continue
            a_lo, a_hi = max(blo, lo), min(bhi, hi)
            n = a_hi - a_lo + 1
            for a in range(a_lo, a_hi + 1):
                ages.append(a)
                wts.append(sh / n)
        ages, wts = np.array(ages), np.array(wts) / np.sum(wts)
        g = np.array([float(np.sum(wts * np.array([prof[min(a + k, MAX_AGE)] for a in ages]))) for k in range(n_years)])
        paths_[s] = {"g_tzs": g, "multiplier": g / g[0] if g[0] > 0 else np.ones(n_years)}
    return paths_


def ilfs_tax_base(sav_path=None):
    """Mean statutory tax per person of each stage's target group among persons outside the formal net (ILFS 2024), zero earners included, and the age-earnings
    multiplier paths (Block E3.4). Aggregates only."""
    from ilfs_indicators import classify
    c = paths.CFG["twin_inputs"]["ilfs"]
    cols = ["Q06B_MEM_AGE", "WEIGHT", "Q25", "Q27A", "Q30", "Q31A", "Q34", "Q38A", "Q38C", "Q22B_MAIN_ISIC", c["employee_cash"], c["business_net"], c["business_net_period"], c["business_gross"], c["business_gross_period"], c["agri_net"], c["agri_net_period"]]
    df, _ = pyreadstat.read_sav(sav_path or paths.ILFS_SAV, usecols=cols, apply_value_formats=False)
    age = df["Q06B_MEM_AGE"].to_numpy(float)
    ok = (age >= 16) & (age <= 97)
    df, age = df[ok].reset_index(drop=True), age[ok]
    w = df["WEIGHT"].to_numpy(float)
    informal = classify(df)["informal"].to_numpy(dtype=float)
    outside_formal = ~(informal == 0.0)                  # formal employees (social security) and owners of registered businesses are excluded; non-workers stay

    def monthly(col, per):
        v = np.where(df[col].fillna(0).to_numpy(float) > 0, df[col].fillna(0).to_numpy(float), 0.0)
        return v * np.where(df[per].to_numpy(float) == 1, 52.0 / 12.0, 1.0)
    cash = np.where(df[c["employee_cash"]].fillna(0).to_numpy(float) > 0, df[c["employee_cash"]].fillna(0).to_numpy(float), 0.0)
    annual = 12.0 * (cash + monthly(c["business_net"], c["business_net_period"]) + monthly(c["agri_net"], c["agri_net_period"]))
    turnover = 12.0 * monthly(c["business_gross"], c["business_gross_period"])
    owner = df["Q25"].to_numpy(float) == 2                                    # self-employed in non-agricultural activities = the FinScope business-owner proxy
    thr = A("tax.presumptive_schedule")["threshold_turnover"]
    tax_pit = pit(annual)
    tax_owner = owner_tax(turnover, annual)
    # stage mapping B: ILFS has no formal-step flag that matches FinScope's, so Active and Enterprise share the owners' age-earnings profile (the 20-year path); their level comes from income_basis
    groups = {"entry": (age >= 16) & (age <= 24), "active": (age >= 25) & (age <= 64) & owner, "enterprise": (age >= 25) & (age <= 64) & owner,
              "asset": (age >= 45) & (age <= 64) & ~owner, "legacy": age >= 65}
    groups = {k: v & outside_formal for k, v in groups.items()}
    out = {}
    for s, m in groups.items():
        if s in OWNER_STAGES:
            tax = tax_owner[m]
            basis = "presumptive income tax on annualised gross business receipts (Q87B, records kept) up to TZS 100M, income tax on annual net earnings above it"
        else:
            tax = tax_pit[m]
            basis = "resident individual income tax on annual earnings (cash earnings + net business + net agricultural income)"
        wm = w[m]
        mean, se = _weighted_mean_se(tax, wm)
        out[s] = {"n_unweighted": int(m.sum()), "mean_tax_per_person_tzs": mean, "se_tzs": se, "share_paying_any_tax_pct": float(np.average(tax > 0, weights=wm) * 100),
                  "share_with_earnings_pct": float(np.average((turnover[m] if s == "enterprise" else annual[m]) > 0, weights=wm) * 100), "tax_basis": basis}
        assert not disclosure.is_suppressed(out[s]["n_unweighted"])

    # ---- ILFS gross-receipts owner groups (the bracket HIGH: Pass 6D variant V1): owners (Q25 == 2) without / with a registered business (Q38A 1-5), aged 25-64, all owners incl. those outside the formal net
    registered = df["Q38A"].isin([1, 2, 3, 4, 5]).to_numpy()
    gross_groups = {"active": owner & ~registered & (age >= 25) & (age <= 64), "enterprise": owner & registered & (age >= 25) & (age <= 64)}
    for s, m in gross_groups.items():
        mean, sem = _weighted_mean_se(tax_owner[m], w[m])
        out[s + "_ilfs_gross"] = {"n_unweighted": int(m.sum()), "mean_tax_per_person_tzs": mean, "se_tzs": sem, "share_paying_any_tax_pct": float(np.average(tax_owner[m] > 0, weights=w[m]) * 100),
                                  "tax_basis": "presumptive income tax on annualised ILFS gross business receipts (Q87B) up to TZS 200M, owners aged 25-64 %s a registered business (Q38A 1-5)" % ("without" if s == "active" else "with")}
        assert not disclosure.is_suppressed(out[s + "_ilfs_gross"]["n_unweighted"])

    # ---- Workers 25-44 (non-owners outside the formal net): the ILFS value used ONLY to price the TRA registration trend in reach_scenarios.py (Workers have no revenue lever and are not a Table 5.1 stage)
    wm = (age >= 25) & (age <= 44) & ~owner & outside_formal
    mean, sem = _weighted_mean_se(tax_pit[wm], w[wm])
    out["workers_ilfs"] = {"n_unweighted": int(wm.sum()), "mean_tax_per_person_tzs": mean, "se_tzs": sem, "share_paying_any_tax_pct": float(np.average(tax_pit[wm] > 0, weights=w[wm]) * 100),
                           "tax_basis": "resident individual income tax on annual earnings of non-owners aged 25-44 outside the formal net (ILFS 2024); prices the registration trend only"}
    assert not disclosure.is_suppressed(out["workers_ilfs"]["n_unweighted"])

    # ---- age-earnings profiles (aggregate: 5-year bands) of the three person types, and the stage groups' band shares
    bands = [tuple(b) for b in cfg()["age_bands"]]
    type_mask = {"all": outside_formal, "nonowner": outside_formal & ~owner, "owner": outside_formal & owner}
    type_tax = {"all": tax_pit, "nonowner": tax_pit, "owner": tax_owner}
    profiles, band_table = {}, {}
    for typ, tm in type_mask.items():
        prof = {}
        rows = []
        last = 0.0
        for bi, (blo, bhi) in enumerate(bands):
            mb = tm & (age >= blo) & (age <= bhi)
            n = int(mb.sum())
            if disclosure.is_suppressed(n):                  # too few respondents in the band for this type: carry the previous band's value (documented)
                val, note = last, "suppressed (n=%d < min_base): previous band's value carried" % n
            else:
                val, note = float(np.average(type_tax[typ][mb], weights=w[mb])), ""
            last = val
            rows.append({"band": "%d-%d" % (blo, bhi), "n_unweighted": n, "mean_tax_per_person_tzs": val, "note": note})
            for a in range(blo, bhi + 1):
                prof[a] = val
        profiles[typ] = prof
        band_table[typ] = rows
    shares = {}
    for s, (lo, hi, typ) in GROUP.items():
        m = groups[s]
        tot = float(w[m].sum())
        shares[s] = {bi: float(w[m & (age >= blo) & (age <= bhi)].sum() / tot) for bi, (blo, bhi) in enumerate(bands)}
    n_years = int(cfg()["long_horizon_years"])
    ag = ageing_paths(profiles, shares, n_years)
    for s in GROUP:                                          # the path starts at the stage's mean tax per person (same value as above)
        assert abs(ag[s]["g_tzs"][0] - out[s]["mean_tax_per_person_tzs"]) <= 1e-6 * max(1.0, out[s]["mean_tax_per_person_tzs"]) + 1.0, (s, ag[s]["g_tzs"][0], out[s]["mean_tax_per_person_tzs"])
        out[s]["age_earnings_multiplier_by_years_since_registration"] = [float(x) for x in ag[s]["multiplier"]]
    return out, {"band_profiles_mean_tax_per_person_tzs": band_table, "group_definitions": {s: {"ages": "%d-%d" % (g[0], g[1]), "profile_of_persons": g[2]} for s, g in GROUP.items()},
                 "multipliers": {s: [float(x) for x in ag[s]["multiplier"]] for s in GROUP}}


def _tri(rng, spec, n):
    lo, mode, hi = spec
    return rng.triangular(lo, mode, hi, n)


def stated_cost(stage):
    """The report-stated programme cost of an adult stage (signed off); Asset has none (placeholder retired in Block E3.4)."""
    return {"entry": A("stage.cost.entry_tzs"), "active": A("stage.cost.active_tzs"), "enterprise": A("stage.cost.enterprise_tzs"), "legacy": A("stage.cost.legacy_tzs")}[stage]


def draw_inputs(stage, spec, rng, draws):
    """Random inputs of one stage. Draw order and counts are those of Block E2 (the stream is kept even for the Asset cost, which is no longer used), so that
    the signed-off 10-year results are reproduced unchanged."""
    if stage == "seed":
        lo, hi = A("stage.cost.seed_tzs")
        return {"cost": rng.uniform(lo, hi, draws)}
    reach_spec, persist_spec, sd = A("stage.reach_share")[stage], A("stage.persistence"), A("stage.uptake_log_odds_sd")
    reach, persist = _tri(rng, reach_spec, draws), _tri(rng, persist_spec, draws)
    p = np.clip(rng.normal(spec["p"], spec["p_se"], draws), 1e-4, 0.5)
    lnor = np.maximum(rng.normal(math.log(spec["odds_ratio"]), sd, draws), 0.0)       # an intervention cannot lower registration: log odds ratio floored at 0
    tax = np.clip(rng.normal(spec["tax_mean"], spec["tax_se"], draws), 0.0, None)
    overrun = np.exp(rng.normal(0.0, A("stage.cost_overrun_sigma"), draws))
    inp = {"reach": reach, "persist": persist, "p": p, "lnor": lnor, "tax": tax}
    if stage != "asset":                                  # Asset has no stated cost (placeholder retired in E3.4)
        inp["cost"] = stated_cost(stage) * overrun
    return inp


def central_inputs(stage, spec):
    """The central point: mode of the triangles, estimates as published."""
    if stage == "seed":
        lo, hi = A("stage.cost.seed_tzs")
        return {"cost": np.array([(lo + hi) / 2])}
    inp = {"reach": np.array([A("stage.reach_share")[stage][1]]), "persist": np.array([A("stage.persistence")[1]]), "p": np.array([spec["p"]]),
           "lnor": np.array([math.log(spec["odds_ratio"])]), "tax": np.array([spec["tax_mean"]])}
    if stage != "asset":
        inp["cost"] = np.array([stated_cost(stage)])
    return inp


def simulate(stage, spec, inp, rate, horizon, aged=False, persist=None, holiday=False):
    """Arrays of registrants, PV revenue (and cost, NPV, ROI where the stage has a cost) for one stage and one variant.

    horizon  number of years of revenue; aged: revenue per registrant follows the age-earnings path (else flat); persist: a fixed yearly persistence (else the draws);
    holiday  the Finance Act 2026's twelve-month nil presumptive tax from the date of obtaining a TIN (a SENSITIVITY: it covers individuals who obtain a TIN to commence a business, which the
             modelled registrants mostly are not). True = the Enterprise stage's first year of revenue is zero; a dict {stage: factor} = the share of the first year's tax that is still collected
             (the legally fitted variant: 1 - the share of new businesses)."""
    ramp = int(A("stage.ramp_years"))
    first_year = float(holiday.get(stage, 1.0)) if isinstance(holiday, dict) else (0.0 if (holiday and stage == "enterprise") else 1.0)
    if stage == "seed":
        z = np.zeros_like(inp["cost"])
        return {"registrants": z, "revenue_pv": z, "cost": inp["cost"], "npv": -inp["cost"], "roi": z}
    pers = inp["persist"] if persist is None else np.full_like(inp["persist"], float(persist))
    delta = np.maximum(1.0 / (1.0 + np.exp(-(np.log(inp["p"] / (1 - inp["p"])) + inp["lnor"]))) - inp["p"], 0.0)       # the log odds ratio is floored at 0, so the gain is never negative (guards rounding noise)
    new_total = spec["population"] * inp["reach"] * delta
    mult = spec.get("multiplier") if aged else None
    rev = np.zeros_like(new_total)
    for t in range(1, horizon + 1):
        stock_value = np.zeros_like(new_total)
        for c in range(1, min(t, ramp) + 1):
            k = t - c
            stock_value = stock_value + pers ** k * (mult[min(k, len(mult) - 1)] if mult is not None else 1.0) * (first_year if k < 1 else 1.0)
        rev = rev + new_total / ramp * inp["tax"] * stock_value * (1 + rate) ** (-t)
    out = {"registrants": new_total, "revenue_pv": rev}
    if "cost" in inp:
        out.update({"cost": inp["cost"], "npv": rev - inp["cost"], "roi": rev / inp["cost"]})
    return out


def _summ(x):
    return {"mean": float(np.mean(x)), "median": float(np.median(x)), "p10": float(np.percentile(x, 10)), "p90": float(np.percentile(x, 90))}


def _summ_all(d):
    return {k: _summ(v) for k, v in d.items()}


def _portfolio(sims):
    port = {k: sum(sims[s][k] for s in PORTFOLIO_STAGES) for k in ("registrants", "revenue_pv", "cost", "npv")}
    port["roi"] = port["revenue_pv"] / port["cost"]
    return port


def variant_defs(nil_fit=None):
    n_long = int(cfg()["long_horizon_years"])
    n_short = int(A("stage.horizon_years"))
    defs = {"horizon_%d_flat" % n_short: dict(horizon=n_short, aged=False, persist=None),
            "horizon_%d_aged" % n_short: dict(horizon=n_short, aged=True, persist=None),
            "horizon_%d_flat" % n_long: dict(horizon=n_long, aged=False, persist=None),
            "horizon_%d_aged" % n_long: dict(horizon=n_long, aged=True, persist=None)}
    for pv in cfg()["persistence_sensitivity"]:
        defs["horizon_%d_aged_persistence_%s" % (n_long, ("%.2f" % pv))] = dict(horizon=n_long, aged=True, persist=float(pv))
        defs["horizon_%d_flat_persistence_%s" % (n_short, ("%.2f" % pv))] = dict(horizon=n_short, aged=False, persist=float(pv))        # Block F3: the 10-year headline basis too
    defs["horizon_%d_flat_new_tin_holiday" % n_short] = dict(horizon=n_short, aged=False, persist=None, holiday=True)
    if nil_fit:
        defs["horizon_%d_flat_new_tin_holiday_fitted" % n_short] = dict(horizon=n_short, aged=False, persist=None, holiday=dict(nil_fit))
    return defs


def persistence_block(results, rates, base_rate, n_years, n_long):
    """Block F3: persistence side by side (signed-off headline, fixed 0.75, 0.90, 0.95), for 10 and 20 years, per stage and for the portfolio without Asset. Persistence is the key uncertainty."""
    pvs = ["%.2f" % p for p in cfg()["persistence_sensitivity"]]

    def pick(d):
        out = {"revenue_pv": {k: d["revenue_pv"][k] for k in ("median", "p10", "p90")}}
        if "roi" in d:
            out.update({"npv": {k: d["npv"][k] for k in ("median", "p10", "p90")}, "roi": {k: d["roi"][k] for k in ("median", "p10", "p90")}})
        return out
    blocks = {}
    for h, signed, fixed, basis in ((n_years, "horizon_%d_flat" % n_years, ["horizon_%d_flat_persistence_%s" % (n_years, p) for p in pvs], "flat tax per registrant (the signed-off headline basis)"),
                                    (n_long, "horizon_%d_aged" % n_long, ["horizon_%d_aged_persistence_%s" % (n_long, p) for p in pvs], "tax per registrant follows the cohort's age-earnings path (sensitivity basis)")):
        cols = [("signed_off_triangular_0.5_0.75_0.9", signed)] + [("fixed_%s" % p, k) for p, k in zip(pvs, fixed)]
        stages = {s: {name: pick(results[v][base_rate]["stages"][s]) for name, v in cols} for s in STAGES}
        port = {name: pick(results[v][base_rate]["portfolio"]) for name, v in cols}
        blocks["%d" % h] = {"tax_basis": basis, "discount_rate": base_rate, "stages": stages, "portfolio_excluding_asset": port}
    return {"label": "assumed; no data fixes it; key uncertainty",
            "headline": "the signed-off persistence is stage.persistence = triangular (0.5, 0.75, 0.9), mode 0.75; the fixed values 0.75, 0.90 and 0.95 are reported beside it",
            "horizons": blocks}


def load_hbs():
    """HBS 2017/18 aggregates (data/processed/hbs_turnover.json, written by src/03_features/hbs_turnover.py)."""
    try:
        with open(paths.HBS_TURNOVER, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit("%s is missing: run `python run_all.py --from-raw` once with the HBS 2017/18 microdata (it is written by src/03_features/hbs_turnover.py)" % paths.HBS_TURNOVER) from None


def tax_for(stage, basis, tax, hbs):
    """(mean tax per registrant, standard error, share owing any tax in %, description) of one stage under one income basis. Only Active and Enterprise depend on the basis."""
    if stage in OWNER_STAGES:
        if basis == "ilfs_gross":
            t = tax[stage + "_ilfs_gross"]
            return t["mean_tax_per_person_tzs"], t["se_tzs"], t["share_paying_any_tax_pct"], t["tax_basis"]
        g = hbs["groups_mapping_B"][stage][HBS_KEY[basis]]
        return g["tax_mean_tzs"], g["tax_se_tzs"], g["share_owing_tax_pct"], BASIS_LABEL[basis]
    t = tax[stage]
    return t["mean_tax_per_person_tzs"], t["se_tzs"], t["share_paying_any_tax_pct"], t["tax_basis"]


def build_specs(seg, tax, hbs, basis, conv, mapping, seed_pop):
    """Stage specifications (population, TIN rate, odds ratio, revenue per registrant, ageing path) of one income basis."""
    specs = {}
    for s in STAGES[1:]:
        r = seg[s]
        mean, sem, _, _ = tax_for(s, basis, tax, hbs)
        specs[s] = {"population": float(r["population_weighted"]), "p": float(r["tin_rate_pct"]) / 100.0, "p_se": float(r["se_pct"]) / 100.0 if r.get("se_pct") else 0.0,
                    "intervention": mapping[s], "odds_ratio": conv[mapping[s]]["fitted_odds_ratio"], "tax_mean": mean, "tax_se": sem,
                    "multiplier": np.array(tax[s]["age_earnings_multiplier_by_years_since_registration"])}
    specs["seed"] = {"population": seed_pop}
    return specs


def draw_all(specs):
    """One set of random inputs (common random numbers: the stream does not depend on the spec values, so bases and scalings differ only by what is tested)."""
    rng = np.random.default_rng(int(cfg()["seed"]))
    return {s: draw_inputs(s, specs[s], rng, int(cfg()["n_draws"])) for s in STAGES}


def median_roi(specs, stage=None, rate=None, horizon=None, persist=None):
    rate = float(A("stage.discount_rate")) if rate is None else rate
    horizon = int(A("stage.horizon_years")) if horizon is None else horizon
    inp = draw_all(specs)
    sims = {s: simulate(s, specs[s], inp[s], rate, horizon, False, persist) for s in STAGES}
    return float(np.median(_portfolio(sims)["roi"] if stage is None else sims[stage]["roi"]))


def break_even_tau(specs, stages, target_stage=None):
    """Factor by which the revenue per registrant of `stages` must be scaled for the median ROI (of `target_stage`, or of the portfolio) to equal 1 (bisection on the log scale)."""
    lo, hi = 1e-4, 1e4
    for _ in range(60):
        mid = (lo * hi) ** 0.5
        sp = copy.deepcopy(specs)
        for s in stages:
            sp[s]["tax_mean"] *= mid
            sp[s]["tax_se"] *= mid
        if median_roi(sp, target_stage) < 1.0:
            lo = mid
        else:
            hi = mid
    return (lo * hi) ** 0.5


def break_even_block(specs):
    """Break-even revenue per registrant (TZS a year): the tax at which the median 10-year ROI is 1 for Active, Enterprise (each alone) and for the portfolio (the four levers scaled together)."""
    out = {}
    for s in OWNER_STAGES:
        lam = break_even_tau(specs, [s], s)
        out[s] = {"lambda": lam, "revenue_per_registrant_in_basis_tzs": specs[s]["tax_mean"], "break_even_revenue_per_registrant_tzs": specs[s]["tax_mean"] * lam}
    lam = break_even_tau(specs, LEVERS, None)
    out["portfolio_four_levers_scaled_together"] = {"lambda": lam, **{s + "_tzs": specs[s]["tax_mean"] * lam for s in LEVERS}}
    return out


def tornado_central(specs):
    """Tornado of the portfolio's median 10-year ROI on the central case (Figure 5.4): each driver at a low and a high setting, everything else at the central case."""
    base = median_roi(specs)

    def scaled(key, f, stages=LEVERS):
        sp = copy.deepcopy(specs)
        for st in stages:
            sp[st][key] *= f
            if key == "tax_mean":
                sp[st]["tax_se"] *= f
        return sp

    def pm(sp, overrides=None, rate=None, persist=None):
        with assumptions.override(overrides or {}):
            return median_roi(sp, rate=rate, persist=persist)
    reach = A("stage.reach_share")
    rlow = {st: [l, l, m] for st, (l, m, h) in reach.items()}
    rhigh = {st: [m, h, h] for st, (l, m, h) in reach.items()}
    cost_keys = ["stage.cost.%s_tzs" % s for s in ("entry", "active", "enterprise", "legacy")]
    slo, shi = A("stage.cost.seed_tzs")
    disc = [float(A("stage.discount_rate"))] + [float(r) for r in A("stage.discount_sensitivities")]
    rows = [("Reach share, all stages", "lower / upper half of the stated range", pm(specs, {"stage.reach_share": rlow}), pm(specs, {"stage.reach_share": rhigh})),
            ("Uptake odds ratio, all stages", "x0.8 / x1.2", pm(scaled("odds_ratio", 0.8)), pm(scaled("odds_ratio", 1.2))),
            ("Revenue per registrant", "x0.8 / x1.2", pm(scaled("tax_mean", 0.8)), pm(scaled("tax_mean", 1.2))),
            ("Stage populations", "x0.8 / x1.2", pm(scaled("population", 0.8)), pm(scaled("population", 1.2))),
            ("Observed TIN rates", "x0.8 / x1.2", pm(scaled("p", 0.8)), pm(scaled("p", 1.2))),
            ("Programme costs (four stages)", "x1.2 / x0.8", pm(specs, {k: A(k) * 1.2 for k in cost_keys}), pm(specs, {k: A(k) * 0.8 for k in cost_keys})),
            ("Discount rate", "%.0f%% / %.0f%%" % (max(disc) * 100, min(disc) * 100), pm(specs, rate=max(disc)), pm(specs, rate=min(disc))),
            ("Seed programme cost", "upper / lower bound", pm(specs, {"stage.cost.seed_tzs": [shi, shi]}), pm(specs, {"stage.cost.seed_tzs": [slo, slo]})),
            ("Yearly persistence", "fixed 0.50 / 0.90", pm(specs, persist=0.50), pm(specs, persist=0.90))]
    out = [{"driver": a, "setting": b, "median_roi_unfavourable": x, "median_roi_favourable": y, "central": base, "swing": abs(y - x)} for a, b, x, y in rows]
    return sorted(out, key=lambda r: -r["swing"]), base


def compute_results(specs, inputs, central, defs, rates):
    """results[variant][rate] = {"stages": {...}, "portfolio": {...}} for one set of specs (one income basis)."""
    results = {}
    for vname, vd in defs.items():
        results[vname] = {}
        for rate in rates:
            sims = {s: simulate(s, specs[s], inputs[s], rate, vd["horizon"], vd["aged"], vd["persist"], vd.get("holiday", False)) for s in STAGES}
            cent = {s: simulate(s, specs[s], central[s], rate, vd["horizon"], vd["aged"], vd["persist"], vd.get("holiday", False)) for s in STAGES}
            port = _portfolio(sims)
            pc = {k: float(sum(cent[s][k][0] for s in PORTFOLIO_STAGES)) for k in ("registrants", "revenue_pv", "cost", "npv")}
            pc["roi"] = pc["revenue_pv"] / pc["cost"]
            stages = {}
            for s in STAGES:
                stages[s] = {"central": {k: float(v[0]) for k, v in cent[s].items()}, **_summ_all(sims[s])}
                if "roi" in sims[s] and s != "seed":
                    stages[s]["p_roi_ge_1"] = float(np.mean(sims[s]["roi"] >= 1.0))
            results[vname][rate] = {"stages": stages, "portfolio": {"central": pc, **_summ_all(port), "p_roi_ge_1": float(np.mean(port["roi"] >= 1.0))}}
    return results


def load_tax_base(sav_path=None, from_processed=False):
    """The ILFS tax base of Table 40 (mean statutory tax per person of each group, standard errors, age-earnings profiles): computed from the ILFS 2024 microdata and written to
    data/processed/ilfs_tax_base.json (aggregates only), or, with from_processed (the outsider's run without the restricted microdata), read back from that file."""
    path = paths.ILFS_TAX_BASE
    if from_processed:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            raise SystemExit("%s is missing: run `python run_all.py --from-raw` once with the ILFS 2024 microdata (it is written by src/04_models/stage_economics.py)" % path) from None
        return d["tax"], d["ageing"]
    tax, ageing = ilfs_tax_base(sav_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"label": "aggregates of ILFS 2024 earnings with the statutory schedules of config.yaml (assumptions tax.pit_schedule, tax.presumptive_schedule) applied; no respondent-level rows",
                   "schedule_year": "resident schedule: Cap. 332 R.E. 2023 (unchanged by the Finance Acts 2024-2026); presumptive schedule: Finance Act 2026 (in force 1 July 2026)", "tax": tax, "ageing": ageing}, f, indent=1, ensure_ascii=False)
    return tax, ageing


def run_stage_economics(sav_path=None, json_path=None, csv_path=None, from_processed=False, with_extras=True):
    json_path = json_path or paths.STAGE_ECONOMICS
    csv_path = csv_path or paths.TABLE40_CSV
    side = (lambda default, name: default) if csv_path == paths.TABLE40_CSV else (lambda default, name: os.path.join(os.path.dirname(csv_path), name))       # the extra tables follow csv_path when it is overridden (tests)
    table51_path, table52_path = side(paths.TABLE51_CSV, "table5_1_stage_economics.csv"), side(paths.TABLE52_CSV, "table5_2_persistence_sensitivity.csv")
    nil_path, tornado_path = side(paths.NIL_PERIOD_CSV, "table5_1_nil_period_sensitivity.csv"), side(paths.TORNADO_CSV, "fig5_4_tornado_central.csv")
    draws, seed = int(cfg()["n_draws"]), int(cfg()["seed"])
    base_rate = float(A("stage.discount_rate"))
    rates = [base_rate] + [float(r) for r in A("stage.discount_sensitivities")]
    n_years = int(A("stage.horizon_years"))
    n_long = int(cfg()["long_horizon_years"])
    V10, V10A, V20F, V20 = "horizon_%d_flat" % n_years, "horizon_%d_aged" % n_years, "horizon_%d_flat" % n_long, "horizon_%d_aged" % n_long
    pers_keys = ["horizon_%d_aged_persistence_%s" % (n_long, "%.2f" % pv) for pv in cfg()["persistence_sensitivity"]]
    pers10_keys = ["horizon_%d_flat_persistence_%s" % (n_years, "%.2f" % pv) for pv in cfg()["persistence_sensitivity"]]
    PERS_LABEL = "assumed; no data fixes it; key uncertainty"
    # observed stage populations and TIN rates (FinScope 2023)
    seg = {}
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            seg[r["segment"]] = r
    with open(paths.CENSUS_AGE_COUNTS, encoding="utf-8") as f:
        seed_pop = float(json.load(f)["bands"]["seed_6_15"]["expanded_x10"])
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        morale = json.load(f)["tax_morale_model"]
    conv = morale["calibration"]["conversion"]
    tax, ageing = load_tax_base(sav_path, from_processed)
    mapping = A("stage.intervention_for_uptake")
    rn = names()
    for s in STAGES[1:]:                                   # the mapping of the config assumption and the report names must agree
        assert mapping[s] == rn[s]["morale_model_key"], (s, mapping[s], rn[s]["morale_model_key"])
    hbs = load_hbs()
    basis_specs = {b: build_specs(seg, tax, hbs, BASES[b], conv, mapping, seed_pop) for b in BASES}
    specs = basis_specs["central"]                                        # the central income basis: HBS receipts of owners with receipts
    tax_used = {b: {s: dict(zip(("mean_tax_per_person_tzs", "se_tzs", "share_paying_any_tax_pct", "tax_basis"), tax_for(s, BASES[b], tax, hbs))) for s in STAGES[1:]} for b in BASES}
    nb = hbs["groups_mapping_B"]
    nil_fit = {s: 1.0 - nb[s]["central_owners_with_receipts"]["new_business_share_pct"] / 100.0 for s in OWNER_STAGES}      # legally fitted nil period: only businesses younger than 12 months qualify
    defs = variant_defs(nil_fit)

    # one set of random inputs, shared by every rate, variant and income basis (common random numbers); the stream equals Block E2's
    inputs = draw_all(specs)
    central = {s: central_inputs(s, specs[s]) for s in STAGES}
    results = compute_results(specs, inputs, central, defs, rates)
    basis_results = {"central": results}
    for b in ("high", "low"):
        sp = basis_specs[b]
        basis_results[b] = compute_results(sp, draw_all(sp), {s: central_inputs(s, sp[s]) for s in STAGES}, defs, rates)

    def stage_variant_block(s, vname):
        return {"%g" % r: {k: v for k, v in results[vname][r]["stages"][s].items() if k != "central"} for r in rates}

    out_stages = {}
    rows = []
    be_headline = None
    for s in STAGES:
        b = results[V10][base_rate]["stages"][s]
        entry = {"report_name": rn[s]["name"], "report_pdf_page": rn[s]["pdf_page"], "report_table40_label": rn[s]["table40_label"], "morale_model_key": rn[s]["morale_model_key"],
                 "report_table40": REPORT_TABLE40[s], "population": specs[s]["population"],
                 "cost_basis": ("report-stated range, uniform" if s == "seed" else ("NOT STATED in the report (placeholder retired in Block E3.4): no cost is assumed; see break_even_cost" if s == "asset" else "report-stated figure (submission_v1 PDF p. 52)")),
                 "monte_carlo_at_10pct": {k: b[k] for k in ("registrants", "revenue_pv", "cost", "npv", "roi") if k in b}, "central_at_10pct": b["central"],
                 "sensitivity_to_discount_rate": {"%g" % r: {k: results[V10][r]["stages"][s][k] for k in ("npv", "roi", "revenue_pv") if k in results[V10][r]["stages"][s]} for r in rates[1:]},
                 "variants": {v: stage_variant_block(s, v) for v in defs}}
        if s == "seed":
            entry["revenue_note"] = "no revenue claimed (the report does not score Seed on revenue; no intervention effect is mapped to Seed)"
        else:
            entry.update({"observed_tin_rate": specs[s]["p"], "observed_tin_rate_se": specs[s]["p_se"], "mapped_intervention": specs[s]["intervention"], "odds_ratio_morale_model": specs[s]["odds_ratio"],
                          "reach_share_triangular_low_mode_high": A("stage.reach_share")[s], "tax_per_registrant_per_year": tax_used["central"][s], "income_basis": BASES["central"]})
        if s == "asset":
            be = {}
            for vname in (V10, V10A, V20F, V20, *pers_keys):
                be[vname] = {"%g" % r: results[vname][r]["stages"]["asset"]["revenue_pv"] for r in rates}
            headline_10, headline_20 = be[V10]["%g" % base_rate], be[V20]["%g" % base_rate]
            entry["break_even_cost"] = {
                "definition": "the programme cost at which ROI = 1: discounted revenue (mean / median / 10th-90th percentile of the Monte Carlo), by variant and discount rate",
                "statement_10_years": "Asset pays back at any programme cost below TZS %.2f billion (median; 80%% interval %.2f-%.2f billion) over 10 years at a %.0f%% discount rate" % (
                    headline_10["median"] / 1e9, headline_10["p10"] / 1e9, headline_10["p90"] / 1e9, base_rate * 100),
                "statement_20_years": "Asset pays back at any programme cost below TZS %.2f billion (median; 80%% interval %.2f-%.2f billion) over 20 years (age-earnings path, signed-off persistence) at a %.0f%% discount rate" % (
                    headline_20["median"] / 1e9, headline_20["p10"] / 1e9, headline_20["p90"] / 1e9, base_rate * 100),
                "by_variant_and_rate_tzs": be}
            be_headline = entry["break_even_cost"]
        out_stages[s] = entry

        def g(vname, key, stat, rate=base_rate):
            d = results[vname][rate]["stages"][s]
            return ("%.4f" if key == "roi" else "%.0f") % d[key][stat] if key in d else ""
        m = b
        base_cols = [s, rn[s]["name"], REPORT_TABLE40[s], "%.0f" % specs[s]["population"], "" if s == "seed" else "%.4f" % (specs[s]["p"] * 100)]
        if s == "asset":
            blank = [""] * 3
            base_cols += blank + ["%.0f" % m["registrants"]["median"], "%.0f" % m["registrants"]["p10"], "%.0f" % m["registrants"]["p90"],
                                  "%.0f" % m["revenue_pv"]["mean"], "%.0f" % m["revenue_pv"]["median"], "%.0f" % m["revenue_pv"]["p10"], "%.0f" % m["revenue_pv"]["p90"]] + [""] * 8 + ["%.0f" % m["central"]["revenue_pv"], ""]
        else:
            base_cols += ["%.0f" % m["cost"]["median"], "%.0f" % m["cost"]["p10"], "%.0f" % m["cost"]["p90"],
                          "%.0f" % m["registrants"]["median"], "%.0f" % m["registrants"]["p10"], "%.0f" % m["registrants"]["p90"],
                          "%.0f" % m["revenue_pv"]["mean"], "%.0f" % m["revenue_pv"]["median"], "%.0f" % m["revenue_pv"]["p10"], "%.0f" % m["revenue_pv"]["p90"],
                          "%.0f" % m["npv"]["mean"], "%.0f" % m["npv"]["median"], "%.0f" % m["npv"]["p10"], "%.0f" % m["npv"]["p90"],
                          "%.4f" % m["roi"]["mean"], "%.4f" % m["roi"]["median"], "%.4f" % m["roi"]["p10"], "%.4f" % m["roi"]["p90"],
                          "%.0f" % m["central"]["revenue_pv"], "%.4f" % m["central"]["roi"]]
        long_cols = [g(V10A, "revenue_pv", "median"), g(V20, "revenue_pv", "median"), g(V20, "revenue_pv", "p10"), g(V20, "revenue_pv", "p90"),
                     g(V20, "npv", "median"), g(V20, "roi", "median"), g(V20, "roi", "p10"), g(V20, "roi", "p90"),
                     g(V20, "roi", "median", rates[1]), g(V20, "roi", "median", rates[2]), g(V10A, "roi", "median")]
        pers_cols = ([g(k, "revenue_pv", "median") for k in pers_keys] + [g(k, "roi", "median") for k in pers_keys] +
                     [g(k, "roi", "median") for k in pers10_keys] + [g(k, "revenue_pv", "median") for k in pers10_keys] +
                     [g(k, "roi", "p10") for k in pers10_keys] + [g(k, "roi", "p90") for k in pers10_keys] +
                     [g(k, "roi", "p10") for k in pers_keys] + [g(k, "roi", "p90") for k in pers_keys] + [PERS_LABEL])
        if s == "asset":
            bcols = ["%.0f" % results[V10][base_rate]["stages"]["asset"]["revenue_pv"][k] for k in ("median", "p10", "p90")] + ["%.0f" % results[V20][base_rate]["stages"]["asset"]["revenue_pv"][k] for k in ("median", "p10", "p90")]
        else:
            bcols = [""] * 6
        rows.append(base_cols + long_cols + pers_cols + bcols)
    # portfolio without Asset
    pb = results[V10][base_rate]["portfolio"]

    def pg(vname, key, stat, rate=base_rate):
        d = results[vname][rate]["portfolio"][key]
        return ("%.4f" if key == "roi" else "%.0f") % d[stat]
    rows.append(["portfolio_excluding_asset", "Seed + Entry + Active + Enterprise + Legacy (Asset excluded)", "", "", "", "%.0f" % pb["cost"]["median"], "%.0f" % pb["cost"]["p10"], "%.0f" % pb["cost"]["p90"],
                 "%.0f" % pb["registrants"]["median"], "%.0f" % pb["registrants"]["p10"], "%.0f" % pb["registrants"]["p90"], "%.0f" % pb["revenue_pv"]["mean"], "%.0f" % pb["revenue_pv"]["median"],
                 "%.0f" % pb["revenue_pv"]["p10"], "%.0f" % pb["revenue_pv"]["p90"], "%.0f" % pb["npv"]["mean"], "%.0f" % pb["npv"]["median"], "%.0f" % pb["npv"]["p10"], "%.0f" % pb["npv"]["p90"],
                 "%.4f" % pb["roi"]["mean"], "%.4f" % pb["roi"]["median"], "%.4f" % pb["roi"]["p10"], "%.4f" % pb["roi"]["p90"], "%.0f" % pb["central"]["revenue_pv"], "%.4f" % pb["central"]["roi"],
                 pg(V10A, "revenue_pv", "median"), pg(V20, "revenue_pv", "median"), pg(V20, "revenue_pv", "p10"), pg(V20, "revenue_pv", "p90"), pg(V20, "npv", "median"), pg(V20, "roi", "median"),
                 pg(V20, "roi", "p10"), pg(V20, "roi", "p90"), pg(V20, "roi", "median", rates[1]), pg(V20, "roi", "median", rates[2]), pg(V10A, "roi", "median")] +
                [pg(k, "revenue_pv", "median") for k in pers_keys] + [pg(k, "roi", "median") for k in pers_keys] +
                [pg(k, "roi", "median") for k in pers10_keys] + [pg(k, "revenue_pv", "median") for k in pers10_keys] +
                [pg(k, "roi", "p10") for k in pers10_keys] + [pg(k, "roi", "p90") for k in pers10_keys] +
                [pg(k, "roi", "p10") for k in pers_keys] + [pg(k, "roi", "p90") for k in pers_keys] + [PERS_LABEL] + [""] * 6)
    pl = lambda s: ("%.2f" % s).replace(".", "p")
    cols = ["stage", "report_name", "report_table40_cost_revenue_roi", "population", "observed_tin_rate_pct", "cost_median_tzs", "cost_p10_tzs", "cost_p90_tzs", "new_registrants_median", "new_registrants_p10",
            "new_registrants_p90", "pv_revenue_mean_tzs", "pv_revenue_median_tzs", "pv_revenue_p10_tzs", "pv_revenue_p90_tzs", "npv_mean_tzs", "npv_median_tzs", "npv_p10_tzs", "npv_p90_tzs",
            "roi_mean", "roi_median", "roi_p10", "roi_p90", "pv_revenue_central_tzs", "roi_central",
            "pv_revenue_10y_aged_median_tzs", "pv_revenue_20y_median_tzs", "pv_revenue_20y_p10_tzs", "pv_revenue_20y_p90_tzs", "npv_20y_median_tzs", "roi_20y_median", "roi_20y_p10", "roi_20y_p90",
            "roi_20y_median_at_%g" % rates[1], "roi_20y_median_at_%g" % rates[2], "roi_10y_aged_median"] + \
           ["pv_revenue_20y_median_persistence_%s_tzs" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + ["roi_20y_median_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + \
           ["roi_10y_median_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + ["pv_revenue_10y_median_persistence_%s_tzs" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + \
           ["roi_10y_p10_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + ["roi_10y_p90_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + \
           ["roi_20y_p10_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + ["roi_20y_p90_persistence_%s" % pl(pv) for pv in cfg()["persistence_sensitivity"]] + ["persistence_sensitivity_label"] + \
           ["break_even_cost_10y_median_tzs", "break_even_cost_10y_p10_tzs", "break_even_cost_10y_p90_tzs", "break_even_cost_20y_median_tzs", "break_even_cost_20y_p10_tzs", "break_even_cost_20y_p90_tzs"]
    for r in rows:
        assert len(r) == len(cols), (r[0], len(r), len(cols))
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        wr.writerows(rows)

    def port_block(vname_list):
        return {v: {"%g" % r: {k: x for k, x in results[v][r]["portfolio"].items() if k != "central"} for r in rates} for v in vname_list}
    result = {
        "label": LABEL, "type": "MODELLED (scenario); revenue per registrant DATA-derived (statute x ILFS earnings)", "report_table": "submission_v1 PDF p. 52, '5. Portfolio-Level Impact' Table 40",
        "horizon_years": n_years, "long_horizon_years": n_long, "discount_rate": base_rate, "discount_sensitivities": rates[1:], "n_draws": draws, "seed": seed,
        "annuity_factors": {"%g" % r: {"years_%d" % n: annuity_factor(r, n) for n in (5, n_years, n_long)} for r in rates},
        "npv_factor_fix": "the earlier cost-benefit code used 4.33 for a '10%%' 5-year NPV; 4.33 is the 5-year annuity factor at 5%%; at 10%% it is %.4f, and the 10-year factor at 10%% is %.4f" % (annuity_factor(0.10, 5), annuity_factor(0.10, 10)),
        "definitions": {"roi": "discounted revenue / cost (a multiple; 1.0 = break-even)", "npv": "discounted revenue - cost", "cost_timing": "start of year 1 (undiscounted); the same programme cost for the 10- and 20-year horizons",
                        "revenue_timing": "end of each year 1-%d (and 1-%d for the 20-year sensitivity)" % (n_years, n_long),
                        "revenue": "income tax and presumptive tax only (no VAT, no second-round effects); registrants pay the statutory tax on their ILFS-based earnings; constant TZS (no wage growth or inflation)",
                        "headline": "the 10-year, flat-tax results are the signed-off horizon and are unchanged by Block E3.4; the 20-year and ageing results are sensitivities (variants)"},
        "variant_definitions": {"horizon_%d_flat" % n_years: "10 years, tax per registrant constant (signed-off headline)", "horizon_%d_aged" % n_years: "10 years, tax per registrant follows the age-earnings path",
                                "horizon_%d_flat" % n_long: "20 years, tax per registrant constant", "horizon_%d_aged" % n_long: "20 years, age-earnings path, signed-off persistence distribution",
                                **{k: "20 years, age-earnings path, fixed yearly persistence %s" % k.rsplit("_", 1)[1] for k in pers_keys}},
        "age_earnings_path": {"method": ("A registrant of the stage's target group sits in a 5-year ILFS age band; k years after registering the registrant is k years older and pays the mean statutory tax of persons of the "
                                         "stage's type (all persons / non-owners / owners) outside the formal net at that age. multiplier(k) = mean tax at age + k / mean tax at registration, k = 0..%d. Registrants are spread uniformly "
                                         "over the ages of each band inside the group's age range; ages above %d keep the profile of %d; deaths and drop-outs are covered by the persistence rate; no wage growth." % (n_long - 1, MAX_AGE, MAX_AGE)),
                              **ageing},
        "tax_schedule_sources": "Income Tax Act Cap. 332 R.E. 2023, First Schedule paras 1(1) and 2(2)-(3), printed pp. 675-676 (PDF pp. 131-132); schedules in config.yaml assumptions tax.pit_schedule and tax.presumptive_schedule",
        "ilfs_tax_base": tax,
        "stages": out_stages,
        "portfolio": {"excludes": ["asset"], "note": "Asset is excluded from the portfolio cost and ROI (no stated cost); its revenue is reported separately under stages.asset. Seed is in the portfolio as cost only.",
                      "monte_carlo_at_10pct": {k: pb[k] for k in ("registrants", "revenue_pv", "cost", "npv", "roi")}, "central_at_10pct": pb["central"],
                      "sensitivity_to_discount_rate": {"%g" % r: {"npv": results[V10][r]["portfolio"]["npv"], "roi": results[V10][r]["portfolio"]["roi"], "revenue_pv": results[V10][r]["portfolio"]["revenue_pv"]} for r in rates[1:]},
                      "variants": port_block(list(defs))},
        "persistence_sensitivity": persistence_block(results, rates, base_rate, n_years, n_long),
        "new_tin_holiday_sensitivity": {"note": "Finance Act 2026, First Schedule para 2(3) item 2: the presumptive tax is NIL for the first twelve months from obtaining a TIN for an individual who obtains it to commence a business (on application). NOT applied in the headline: "
                                                  "the registrants modelled are existing informal workers and owners. Here the Enterprise stage's first year of revenue per registrant is set to zero (10 years, flat tax, signed-off persistence).",
                                        "enterprise": {"headline": results[V10][base_rate]["stages"]["enterprise"]["roi"], "with_holiday": results["horizon_%d_flat_new_tin_holiday" % n_years][base_rate]["stages"]["enterprise"]["roi"]},
                                        "portfolio_excluding_asset": {"headline": results[V10][base_rate]["portfolio"]["roi"], "with_holiday": results["horizon_%d_flat_new_tin_holiday" % n_years][base_rate]["portfolio"]["roi"]}},
        "asset_revenue_reported_separately": {"horizon_%d_flat_at_10pct" % n_years: results[V10][base_rate]["stages"]["asset"]["revenue_pv"], "horizon_%d_aged_at_10pct" % n_long: results[V20][base_rate]["stages"]["asset"]["revenue_pv"]},
        "assumptions_for_signoff": ["twin penetration cap (E3.3)"],
        "seed_upper_cost_bound_tzs": float(A("stage.cost.seed_tzs")[1]),
    }
    if with_extras:                      # the sensitivity tool turns this off (headline values only)
        # ---------- Pass 6B-1: bracket, break-even revenue per registrant, nil period, tornado, Tables 5.1 / 5.2
        V10F = "horizon_%d_flat_new_tin_holiday_fitted" % n_years
        bases_out = {}
        for b, bn in BASES.items():
            R = basis_results[b]
            blk = {"income_basis": bn, "label": BASIS_LABEL[bn], "stages": {}, "break_even_revenue_per_registrant": break_even_block(basis_specs[b])}
            for s in STAGES:
                r10, r20 = R[V10][base_rate]["stages"][s], R[V20][base_rate]["stages"][s]
                d = {"revenue_per_registrant_tzs": tax_used[b][s]["mean_tax_per_person_tzs"] if s != "seed" else None, "share_paying_any_tax_pct": tax_used[b][s]["share_paying_any_tax_pct"] if s != "seed" else None,
                     "revenue_pv": {k: r10["revenue_pv"][k] for k in ("median", "p10", "p90")}, "revenue_pv_central": r10["central"]["revenue_pv"]}
                if "roi" in r10:
                    d.update({"roi_10y": {k: r10["roi"][k] for k in ("median", "p10", "p90")}, "roi_10y_central": r10["central"]["roi"], "p_roi_ge_1": r10.get("p_roi_ge_1"),
                              "roi_20y": {k: r20["roi"][k] for k in ("median", "p10", "p90")}})
                if s == "asset":
                    d["break_even_cost_10y_tzs"] = {k: r10["revenue_pv"][k] for k in ("median", "p10", "p90")}
                    d["break_even_cost_20y_tzs"] = {k: r20["revenue_pv"][k] for k in ("median", "p10", "p90")}
                blk["stages"][s] = d
            p10, p20 = R[V10][base_rate]["portfolio"], R[V20][base_rate]["portfolio"]
            blk["portfolio_excluding_asset"] = {"roi_10y": {k: p10["roi"][k] for k in ("median", "p10", "p90")}, "roi_10y_central": p10["central"]["roi"], "p_roi_ge_1": p10["p_roi_ge_1"],
                                                "roi_20y": {k: p20["roi"][k] for k in ("median", "p10", "p90")}, "revenue_pv": {k: p10["revenue_pv"][k] for k in ("median", "p10", "p90")}}
            bases_out[b] = blk
        tor, tor_base = tornado_central(specs)
        nil = {"label": "SENSITIVITY only (not in the headline): Finance Act 2026, First Schedule para 2(3) item 2, nil presumptive tax for the first twelve months from obtaining a TIN to commence a business",
               "new_business_share_pct_hbs": {s: nb[s]["central_owners_with_receipts"]["new_business_share_pct"] for s in OWNER_STAGES},
               "headline_portfolio_roi": {k: results[V10][base_rate]["portfolio"]["roi"][k] for k in ("median", "p10", "p90")},
               "legally_fitted_share_of_new_businesses": {"first_year_share_collected": nil_fit, "active_roi_median": results[V10F][base_rate]["stages"]["active"]["roi"]["median"],
                                                          "enterprise_roi_median": results[V10F][base_rate]["stages"]["enterprise"]["roi"]["median"],
                                                          "portfolio_roi": {k: results[V10F][base_rate]["portfolio"]["roi"][k] for k in ("median", "p10", "p90")}},
               "full_first_year_variant_enterprise": {"enterprise_roi_median": results["horizon_%d_flat_new_tin_holiday" % n_years][base_rate]["stages"]["enterprise"]["roi"]["median"],
                                                      "portfolio_roi": {k: results["horizon_%d_flat_new_tin_holiday" % n_years][base_rate]["portfolio"]["roi"][k] for k in ("median", "p10", "p90")}}}
        result.update({"income_basis_central": BASES["central"], "income_bases": bases_out,
                       "bracket_definition": "central = HBS 2017/18 receipts of owners with receipts in the reference month; high = ILFS 2024 gross receipts of owners; low = HBS all owners, zeros kept (ILFS is never shown alone)",
                       "nil_period_sensitivity": nil, "tornado_central": {"portfolio_median_roi_10y_central": tor_base, "drivers": tor},
                       "workers_25_44": {"population": float(seg["workers"]["population_weighted"]), "observed_tin_rate": float(seg["workers"]["tin_rate_pct"]) / 100.0, "note": "no revenue lever: not priced, no cost, no reach"},
                       "evidence_type": "MODELLED (scenario); revenue per registrant COMPUTED from survey data (HBS 2017/18, ILFS 2024) with the statutory schedules CITED"})

        pers_names = [("signed_off_triangular_0.5_0.75_0.9", "signed-off (triangular 0.5-0.75-0.9)")] + [("fixed_%s" % ("%.2f" % pv), "fixed %.2f" % pv) for pv in cfg()["persistence_sensitivity"]]
        t52 = []
        for h, blk in result["persistence_sensitivity"]["horizons"].items():
            for s in [x for x in STAGES if x not in ("seed", "asset")] + ["portfolio_excluding_asset"]:
                for key, lab in pers_names:
                    d = (blk["portfolio_excluding_asset"] if s == "portfolio_excluding_asset" else blk["stages"][s])[key]
                    t52.append([h, s, lab] + ["%.4f" % d["roi"][k] for k in ("median", "p10", "p90")] + ["%.0f" % d["revenue_pv"]["median"], blk["tax_basis"], "MODELLED; " + PERS_LABEL])
        with open(table52_path, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(["horizon_years", "stage", "persistence", "roi_median", "roi_p10", "roi_p90", "pv_revenue_median_tzs", "tax_basis", "evidence_type"])
            wr.writerows(t52)

        cols51 = ["stage", "report_name", "population", "observed_tin_rate_pct", "programme_cost_median_tzs", "new_registrants_median", "new_registrants_p10", "new_registrants_p90"]
        for b in BASES:
            cols51 += ["%s_revenue_per_registrant_tzs" % b, "%s_share_paying_pct" % b, "%s_pv_revenue_median_tzs" % b, "%s_roi_median" % b, "%s_roi_p10" % b, "%s_roi_p90" % b, "%s_p_roi_ge_1" % b, "%s_roi_20y_median" % b]
        cols51 += ["break_even_revenue_per_registrant_central_tzs", "break_even_cost_10y_median_central_tzs", "evidence_type"]
        rows51 = []
        for s in STAGES + ["portfolio_excluding_asset"]:
            port_row = s == "portfolio_excluding_asset"
            rc = results[V10][base_rate]
            src = rc["portfolio"] if port_row else rc["stages"][s]
            row = [s, "Seed + Entry + Active + Enterprise + Legacy (Asset excluded)" if port_row else rn[s]["name"], "" if (port_row or s == "seed") else "%.0f" % specs[s]["population"],
                   "" if (port_row or s == "seed") else "%.4f" % (specs[s]["p"] * 100), "%.0f" % src["cost"]["median"] if "cost" in src else "", "%.0f" % src["registrants"]["median"], "%.0f" % src["registrants"]["p10"], "%.0f" % src["registrants"]["p90"]]
            for b in BASES:
                blk = bases_out[b]["portfolio_excluding_asset"] if port_row else bases_out[b]["stages"][s]
                if s == "seed":
                    row += [""] * 8
                elif s == "asset":
                    row += ["%.0f" % blk["revenue_per_registrant_tzs"], "%.2f" % blk["share_paying_any_tax_pct"], "%.0f" % blk["revenue_pv"]["median"], "", "", "", "", ""]
                else:
                    row += ["" if port_row else "%.0f" % blk["revenue_per_registrant_tzs"], "" if port_row else "%.2f" % blk["share_paying_any_tax_pct"], "%.0f" % blk["revenue_pv"]["median"],
                            "%.4f" % blk["roi_10y"]["median"], "%.4f" % blk["roi_10y"]["p10"], "%.4f" % blk["roi_10y"]["p90"], "%.4f" % blk["p_roi_ge_1"], "%.4f" % blk["roi_20y"]["median"]]
            be = bases_out["central"]["break_even_revenue_per_registrant"]
            row.append("%.0f" % be[s]["break_even_revenue_per_registrant_tzs"] if s in OWNER_STAGES else "")
            row.append("%.0f" % bases_out["central"]["stages"]["asset"]["break_even_cost_10y_tzs"]["median"] if s == "asset" else "")
            row.append("MODELLED (scenario); revenue per registrant COMPUTED")
            rows51.append(row)
        with open(table51_path, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(cols51)
            wr.writerows(rows51)
        with open(tornado_path, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(["driver", "setting", "median_roi_unfavourable", "median_roi_favourable", "central_median_roi", "swing", "evidence_type"])
            wr.writerows([[r["driver"], r["setting"], "%.4f" % r["median_roi_unfavourable"], "%.4f" % r["median_roi_favourable"], "%.4f" % r["central"], "%.4f" % r["swing"], "MODELLED (scenario)"] for r in tor])
        with open(nil_path, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(["variant", "active_roi_median", "enterprise_roi_median", "portfolio_roi_median", "portfolio_roi_p10", "portfolio_roi_p90", "evidence_type"])
            full = results["horizon_%d_flat_new_tin_holiday" % n_years][base_rate]
            for name, rr in (("headline (no nil period)", results[V10][base_rate]), ("legally fitted share of new businesses", results[V10F][base_rate]), ("full first year, Enterprise", full)):
                wr.writerow([name, "%.4f" % rr["stages"]["active"]["roi"]["median"], "%.4f" % rr["stages"]["enterprise"]["roi"]["median"], "%.4f" % rr["portfolio"]["roi"]["median"],
                             "%.4f" % rr["portfolio"]["roi"]["p10"], "%.4f" % rr["portfolio"]["roi"]["p90"], "MODELLED; SENSITIVITY only"])

    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    pw = results[V10][base_rate]["portfolio"]
    print("  Table 40 (10%% discount, %d draws): portfolio excl. Asset cost median TZS %.2fB, PV revenue median %.2fB, ROI median %.3f; 20-year ROI median %.3f; %s" % (
        draws, pw["cost"]["median"] / 1e9, pw["revenue_pv"]["median"] / 1e9, pw["roi"]["median"], results[V20][base_rate]["portfolio"]["roi"]["median"], be_headline["statement_10_years"]))
    return result


if __name__ == "__main__":
    run_stage_economics()
