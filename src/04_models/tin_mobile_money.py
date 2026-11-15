"""W6 - mobile money and TIN holding on the REAL FinScope 2023 data (replaces the simulated propensity-score matching).

LABEL (every output carries it): "COMPUTED; observational, cross-sectional association; not a causal estimate".

1. Descriptives: share of TIN holders who use mobile money; TIN rate among users and non-users, with unweighted counts.
   Disclosure rule (config.yaml disclosure): the non-user numerator is about 1 TIN holder, so that cell keeps its estimate, is
   flagged low_precision, and the numerator itself is not published.
2. Survey-weighted logistic regression: TIN ~ mobile money + age, age squared, sex, residence (RU), education, main income
   source (FinScope 2023 has NO income amount: the main income source stands in for an income band; business ownership is
   exactly the union of three of its categories, so it enters through it); a second fit adds region. Because almost no non-user holds a TIN (near-separation) the primary fit is a FIRTH-PENALISED
   logit (Jeffreys-prior penalty, weighted information); the unpenalised fit is reported to show the separation.
   Standard errors: Taylor-linearised sandwich on the RECONSTRUCTED design of Block B (PSU = enumeration area,
   strata = region x cluster type), t-based intervals with PSUs - strata degrees of freedom.
3. Average marginal effect of mobile money: mean over respondents (survey weights) of p(MM=1, x) - p(MM=0, x), in
   percentage points, with a delta-method 95% CI from the same design-based covariance.

Outputs (aggregates only): outputs/stats/tin_mobile_money.json, outputs/tables/tin_mobile_money.csv
"""

import csv
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
from finscope_segments import WEIGHT_VAR, tin_holder_mask
from survey_design import ci95, linearised_ratio

LABEL = "COMPUTED; observational, cross-sectional association; not a causal estimate"
DESIGN_COLS = ["reg_code", "dist_code", "ward_code1", "ea_code", "clustertype"]
USECOLS = ["c27__13", "MM", "c8c", "c9", "RU", "c11", "IncomeMain", "BusO", "reg_name", WEIGHT_VAR] + DESIGN_COLS

EDUCATION_MAP = {
    "No formal education": "No formal education",
    "Some primary": "Some primary",
    "Primary completed": "Primary completed",
    "Post primary technical training": "Primary completed",
    "Some secondary": "Secondary (some or O-level)",
    "Secondary competed-O level": "Secondary (some or O-level)",
    "Secondary completed-A level": "A-level, university or higher",
    "Some University or other higher education": "A-level, university or higher",
    "University or higher education completed": "A-level, university or higher",
}
MIN_LEVEL_FOR_INCOME_CATEGORY = 30


# ------------------------------------------------------------------ data
def prepare(df, complete=True):
    """Analysis frame: outcome, treatment, covariates (categorical levels with the reference first) and the design labels."""
    d = pd.DataFrame(index=df.index)
    d["tin"] = tin_holder_mask(df).astype(int)
    d["mm"] = (df["MM"].astype(str).str.strip() == "MM").astype(int)
    d["age"] = pd.to_numeric(df["c8c"], errors="coerce")
    d["sex"] = df["c9"].astype(str).str.strip()
    d["residence"] = df["RU"].astype(str).str.strip()
    d["education"] = df["c11"].astype(str).str.strip().map(EDUCATION_MAP)
    inc = df["IncomeMain"].astype(str).str.strip()
    small = inc.map(inc.value_counts()) < MIN_LEVEL_FOR_INCOME_CATEGORY
    d["income_source"] = inc.where(~small, "Other (small categories)")
    d["business_owner"] = (df["BusO"].astype(str).str.strip() == "Business owners").astype(int)
    d["region"] = df["reg_name"].astype(str).str.strip()
    d["w"] = pd.to_numeric(df[WEIGHT_VAR], errors="coerce")
    d["psu"] = df[["reg_code", "dist_code", "ward_code1", "ea_code"]].astype(str).agg("|".join, axis=1)
    d["strata"] = df["reg_code"].astype(str) + "|" + df["clustertype"].astype(str)
    if complete:                       # the model sample: respondents with a stated age, education and weight
        d = d.dropna(subset=["age", "education", "w"])
    return d


REFERENCES = {"sex": "Female", "residence": "Rural", "education": "Primary completed", "income_source": "Farmers and fishers", "region": None}


def design_matrix(d, with_region):
    cols, names, groups = [np.ones(len(d))], ["intercept"], {}
    def add(name, vec, group=None):
        cols.append(np.asarray(vec, dtype=float)); names.append(name)
        if group:
            groups.setdefault(group, []).append(name)
    add("mobile_money", d["mm"])
    age = d["age"].to_numpy(float)
    add("age_per_10_years", (age - 40) / 10.0)
    add("age_squared_per_100", ((age - 40) / 10.0) ** 2)
    # business ownership (BusO) is exactly the union of three main-income-source categories (traders, service providers), so it
    # enters through income_source below; a separate dummy would be perfectly collinear
    cats = ["sex", "residence", "education", "income_source"] + (["region"] if with_region else [])
    for c in cats:
        ref = REFERENCES.get(c) or d[c].value_counts().index[0]
        for lev in sorted(d[c].unique()):
            if lev != ref:
                add("%s: %s" % (c, lev), (d[c] == lev), c)
    return np.column_stack(cols), names


# ------------------------------------------------------------------ Firth-penalised weighted logit
def _fit(X, y, a, firth=True, max_iter=500, tol=1e-7, score_tol=1e-5):
    n, k = X.shape
    beta = np.zeros(k)
    def penalised_ll(b):
        eta = X @ b
        ll = float(np.sum(a * (y * eta - np.logaddexp(0.0, eta))))
        if firth:
            p = expit(eta)
            A = X.T @ ((a * p * (1 - p))[:, None] * X)
            sign, logdet = np.linalg.slogdet(A)
            ll += 0.5 * logdet if sign > 0 else -1e12
        return ll
    cur = penalised_ll(beta)
    converged = False
    for it in range(1, max_iter + 1):
        eta = X @ beta
        p = expit(eta)
        W = a * p * (1 - p)
        A = X.T @ (W[:, None] * X)
        try:
            Ainv = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            break
        if firth:
            h = W * np.einsum("ij,jk,ik->i", X, Ainv, X)
            score = X.T @ (a * (y - p) + h * (0.5 - p))
        else:
            score = X.T @ (a * (y - p))
        if np.max(np.abs(score)) < score_tol:       # the (penalised) score is zero: converged
            converged = True
            break
        step = Ainv @ score
        mx = np.max(np.abs(step))
        if mx > 5:                                  # cap the step (separation)
            step *= 5 / mx
        t = 1.0
        while t > 1e-6:
            new = penalised_ll(beta + t * step)
            if new >= cur - 1e-10:
                break
            t /= 2
        beta = beta + t * step
        cur = new
        if np.max(np.abs(t * step)) < tol:
            converged = True
            break
    return {"beta": beta, "converged": converged, "iterations": it, "penalised_loglik": cur}


def robust_cov(X, y, a, beta, firth, strata, psu):
    """Sandwich covariance from PSU totals of the (Firth-modified) score contributions; returns (V, n_psu, n_strata, bread_inv)."""
    eta = X @ beta
    p = expit(eta)
    W = a * p * (1 - p)
    A = X.T @ (W[:, None] * X)
    Ainv = np.linalg.inv(A)
    u = (a * (y - p))[:, None] * X
    if firth:
        h = W * np.einsum("ij,jk,ik->i", X, Ainv, X)
        u = u + (h * (0.5 - p))[:, None] * X
    frame = pd.DataFrame(u)
    frame["h"], frame["c"] = strata, psu
    tot = frame.groupby(["h", "c"], sort=False).sum().reset_index()
    meat = np.zeros((X.shape[1], X.shape[1]))
    n_str = tot["h"].nunique()
    lonely = 0
    for _, g in tot.groupby("h", sort=False):
        m = len(g)
        if m < 2:
            lonely += 1
            continue
        z = g.drop(columns=["h", "c"]).to_numpy(float)
        z = z - z.mean(axis=0)
        meat += m / (m - 1.0) * (z.T @ z)
    V = Ainv @ meat @ Ainv
    return V, len(tot), n_str, lonely, Ainv


def ame_mobile_money(X, names, beta, V, a):
    """Average marginal effect of mobile money (percentage points) with a delta-method standard error."""
    j = names.index("mobile_money")
    X1, X0 = X.copy(), X.copy()
    X1[:, j], X0[:, j] = 1.0, 0.0
    p1, p0 = expit(X1 @ beta), expit(X0 @ beta)
    wsum = a.sum()
    ame = float(np.sum(a * (p1 - p0)) / wsum)
    g = ((a * p1 * (1 - p1))[:, None] * X1 - (a * p0 * (1 - p0))[:, None] * X0).sum(axis=0) / wsum
    se = float(math.sqrt(max(g @ V @ g, 0.0)))
    return ame, se, float(np.sum(a * p1) / wsum), float(np.sum(a * p0) / wsum)


# ------------------------------------------------------------------ descriptives
def _rate_row(label, d, mask, a_col="w"):
    w = d[a_col].to_numpy(float)
    m = mask.to_numpy(bool)
    tin = d["tin"].to_numpy(bool)
    n, num = int(m.sum()), int((m & tin).sum())
    pop = float(w[m].sum())
    rate = float(w[m & tin].sum() / pop * 100) if pop > 0 else float("nan")
    r, se, n_psu, n_str, _ = linearised_ratio((m & tin).astype(float), m.astype(float), w, d["strata"].to_numpy(), d["psu"].to_numpy())
    lo, hi = ci95(r, se, n_psu, n_str) if num > 0 else (float("nan"), float("nan"))
    row = {"group": label, "n_unweighted_base": n, "n_unweighted_numerator": num, "weighted_population": pop, "tin_rate_pct": rate,
           "ci95_low_pct": lo * 100 if lo == lo else None, "ci95_high_pct": hi * 100 if hi == hi else None}
    return disclosure.apply_to_row(row, "n_unweighted_base", "n_unweighted_numerator", ["tin_rate_pct", "ci95_low_pct", "ci95_high_pct"], ["weighted_population"])


def descriptives(d):
    w = d["w"].to_numpy(float)
    tin = d["tin"].to_numpy(bool)
    mm = d["mm"].to_numpy(bool)
    n_tin = int(tin.sum())
    holders_w = float(w[tin].sum())
    share = float(w[tin & mm].sum() / holders_w * 100)
    r, se, n_psu, n_str, _ = linearised_ratio((tin & mm).astype(float), tin.astype(float), w, d["strata"].to_numpy(), d["psu"].to_numpy())
    lo, hi = ci95(r, se, n_psu, n_str)
    share_row = {"n_unweighted_base": n_tin, "n_unweighted_numerator": int((tin & mm).sum()), "share_of_tin_holders_using_mm_pct": share,
                 "ci95_low_pct": lo * 100, "ci95_high_pct": hi * 100, "weighted_tin_holders": holders_w}
    share_row = disclosure.apply_to_row(share_row, "n_unweighted_base", "n_unweighted_numerator", ["share_of_tin_holders_using_mm_pct", "ci95_low_pct", "ci95_high_pct"],
                                        ["weighted_tin_holders"])
    rows = [_rate_row("All adults (16+)", d, pd.Series(True, index=d.index)),
            _rate_row("Mobile-money users", d, d["mm"] == 1),
            _rate_row("Non-users of mobile money", d, d["mm"] == 0)]
    return share_row, rows


# ------------------------------------------------------------------ model
def fit_model(d, with_region, firth=True):
    X, names = design_matrix(d, with_region)
    y = d["tin"].to_numpy(float)
    a = d["w"].to_numpy(float)
    a = a / a.mean()
    fit = _fit(X, y, a, firth=firth)
    out = {"names": names, "n": int(len(y)), "converged": bool(fit["converged"]), "iterations": int(fit["iterations"]), "firth": bool(firth)}
    beta = fit["beta"]
    out["max_abs_coefficient"] = float(np.max(np.abs(beta)))
    if not fit["converged"] or not np.all(np.isfinite(beta)):
        return out, None
    V, n_psu, n_str, lonely, _ = robust_cov(X, y, a, beta, firth, d["strata"].to_numpy(), d["psu"].to_numpy())
    df_ = max(n_psu - n_str, 1)
    t = float(stats.t.ppf(0.975, df_))
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    ame, ame_se, p1, p0 = ame_mobile_money(X, names, beta, V, a)
    out.update({"design": {"n_psu": n_psu, "n_strata": n_str, "strata_with_one_psu": lonely, "degrees_of_freedom": df_},
                "beta": beta.tolist(), "se": se.tolist(), "t_crit": t,
                "ame_pp": ame * 100.0, "ame_se_pp": ame_se * 100.0, "ame_ci95_pp": [(ame - t * ame_se) * 100.0, (ame + t * ame_se) * 100.0],
                "mean_predicted_if_all_mm_pct": p1 * 100.0, "mean_predicted_if_no_mm_pct": p0 * 100.0})
    return out, (X, names)


def coefficient_rows(d, model, with_region):
    """Table rows (disclosure applied): one per model term."""
    rows = []
    tin = d["tin"].to_numpy(bool)
    t = model["t_crit"]
    for name, b, s in zip(model["names"], model["beta"], model["se"]):
        if name == "intercept":
            continue
        if name in ("mobile_money",):
            users = d["mm"].to_numpy(bool)
            base = int(len(d))
            num = int(min((tin & users).sum(), (tin & ~users).sum()))       # the thinner arm decides the precision
        elif ":" in name:
            col, lev = name.split(": ", 1)
            m = (d[col] == lev).to_numpy(bool)
            base, num = int(m.sum()), int((m & tin).sum())
        else:
            base, num = int(len(d)), int(tin.sum())
        row = {"model": "with region" if with_region else "primary", "term": name, "log_odds": b, "se": s, "ci95_low": b - t * s, "ci95_high": b + t * s,
               "odds_ratio": math.exp(b), "or_ci95_low": math.exp(b - t * s), "or_ci95_high": math.exp(b + t * s),
               "p_value": float(2 * (1 - stats.t.cdf(abs(b / s), 500))) if s > 0 else None,
               "n_unweighted_base": base, "n_unweighted_numerator": num}
        rows.append(disclosure.apply_to_row(row, "n_unweighted_base", "n_unweighted_numerator",
                                            ["log_odds", "se", "ci95_low", "ci95_high", "odds_ratio", "or_ci95_low", "or_ci95_high", "p_value"]))
    return rows


def run_tin_mobile_money(csv_path=None, json_path=None, table_path=None):
    csv_path = csv_path or paths.FINSCOPE_CSV
    json_path = json_path or paths.TIN_MOBILE_MONEY
    table_path = table_path or paths.TIN_MOBILE_MONEY_CSV
    df = pd.read_csv(csv_path, usecols=USECOLS, low_memory=False)
    d = prepare(df)
    share_row, desc_rows = descriptives(prepare(df, complete=False))      # descriptives use all 9,915 respondents

    primary_model, _ = fit_model(d, with_region=False, firth=True)
    region_model, _ = fit_model(d, with_region=True, firth=True)
    plain_model, _ = fit_model(d, with_region=False, firth=False)
    use_region = bool(region_model["converged"] and "ame_pp" in region_model)
    headline = region_model if use_region else primary_model

    table = []
    for r in desc_rows:
        table.append({"section": "descriptive", "model": "", "term": r["group"], "estimate": r["tin_rate_pct"], "ci95_low": r["ci95_low_pct"], "ci95_high": r["ci95_high_pct"],
                      "n_unweighted_base": r["n_unweighted_base"], "n_unweighted_numerator": r["n_unweighted_numerator"], "low_precision": r.get("low_precision", False),
                      "suppressed": r.get("suppressed", False), "label": LABEL})
    for nm, mdl, wr in (("primary", primary_model, False), ("with region", region_model, True)):
        if "beta" not in mdl:
            continue
        for r in coefficient_rows(d, mdl, wr):
            table.append({"section": "model coefficient (log-odds, Firth)", "model": r["model"], "term": r["term"], "estimate": r["log_odds"], "ci95_low": r["ci95_low"], "ci95_high": r["ci95_high"],
                          "n_unweighted_base": r["n_unweighted_base"], "n_unweighted_numerator": r["n_unweighted_numerator"], "low_precision": r.get("low_precision", False),
                          "suppressed": r.get("suppressed", False), "label": LABEL})
        table.append({"section": "average marginal effect of mobile money (percentage points)", "model": nm, "term": "mobile_money", "estimate": mdl["ame_pp"], "ci95_low": mdl["ame_ci95_pp"][0],
                      "ci95_high": mdl["ame_ci95_pp"][1], "n_unweighted_base": mdl["n"], "n_unweighted_numerator": None, "low_precision": True, "suppressed": False, "label": LABEL})

    mm_idx = primary_model["names"].index("mobile_money")
    result = {
        "label": LABEL,
        "type": "COMPUTED (survey data); association, not causal",
        "source": "FinScope Tanzania 2023, respondent-level; survey weight population_wt; design RECONSTRUCTED (PSU = enumeration area, strata = region x cluster type)",
        "population": "descriptives: all 9,915 adult respondents; models: the %d with a stated education level" % primary_model["n"],
        "outcome": "holds a Taxpayer Identification Number (c27__13 = Yes)",
        "disclosure_rule": "unweighted numerators below %d are not published and the estimate is flagged low_precision; bases below %d are suppressed" % (disclosure.LOW_PRECISION_NUMERATOR, disclosure.MIN_BASE),
        "descriptives": {"share_of_tin_holders_using_mobile_money": share_row, "tin_rate_by_group": desc_rows},
        "model_specification": {"covariates": ["mobile money", "age, age squared", "sex", "residence (Dar es Salaam / other urban / rural / Zanzibar)"] + (["region (each region of mainland Tanzania and Zanzibar; in the headline model only)"] if use_region else [])
                                + ["education", "main income source (no income amount exists in FinScope 2023; it also carries business ownership, which BusO derives from it)"],
                                "covariates_note": "these are the covariates of the headline model reported here (headline_model); the other model is the same without region" if use_region else "these are the covariates of the headline model reported here (headline_model)",
                                "estimator": "survey-weighted logistic regression, Firth-penalised (Jeffreys prior with weighted information), because almost no non-user holds a TIN",
                                "standard_errors": "Taylor-linearised sandwich, PSU totals within strata (reconstructed design), t intervals", "weights": "population_wt normalised to mean 1"},
        "headline_model": "with region" if use_region else "primary",
        "average_marginal_effect_of_mobile_money": {
            "percentage_points": headline["ame_pp"], "ci95_percentage_points": headline["ame_ci95_pp"], "se_pp": headline["ame_se_pp"],
            "mean_predicted_tin_rate_if_all_use_mm_pct": headline["mean_predicted_if_all_mm_pct"], "mean_predicted_tin_rate_if_none_use_mm_pct": headline["mean_predicted_if_no_mm_pct"],
            "label": LABEL},
        "odds_ratio_mobile_money": {"primary": math.exp(primary_model["beta"][mm_idx]) if "beta" in primary_model else None,
                                    "primary_ci95": [math.exp(primary_model["beta"][mm_idx] - primary_model["t_crit"] * primary_model["se"][mm_idx]),
                                                     math.exp(primary_model["beta"][mm_idx] + primary_model["t_crit"] * primary_model["se"][mm_idx])] if "beta" in primary_model else None,
                                    "with_region": math.exp(region_model["beta"][region_model["names"].index("mobile_money")]) if "beta" in region_model else None},
        "model_diagnostics": {
            "primary_firth": {k: primary_model[k] for k in ("converged", "iterations", "n", "max_abs_coefficient", "design") if k in primary_model},
            "with_region_firth": {k: region_model[k] for k in ("converged", "iterations", "n", "max_abs_coefficient", "design") if k in region_model},
            "unpenalised_comparison": {**{k: plain_model[k] for k in ("converged", "iterations", "max_abs_coefficient") if k in plain_model},
                                       "mobile_money_log_odds": plain_model["beta"][mm_idx] if "beta" in plain_model else None,
                                       "note": "the unpenalised weighted logit is shown only to document near-separation (a very large coefficient or non-convergence); it is not used"},
            "region_model_used_for_headline": use_region},
        "replaces": "the simulated propensity-score matching (planted 6 pp effect; reported 9.0 / 5.94 pp), the typed difference-in-differences and the typed synthetic control, all retired in Block D2",
    }
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    os.makedirs(os.path.dirname(table_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    cols = ["section", "model", "term", "estimate", "ci95_low", "ci95_high", "n_unweighted_base", "n_unweighted_numerator", "low_precision", "suppressed", "label"]
    with open(table_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in table:
            wr.writerow([("" if r[c] is None else ("%.4f" % r[c] if isinstance(r[c], float) else r[c])) for c in cols])
    ame = result["average_marginal_effect_of_mobile_money"]
    print("  TIN share of holders using MM %.1f%%; TIN rate users %.2f%% / non-users %.3f%% (low precision); AME %.2f pp (95%% CI %.2f to %.2f); region model %s" % (
        share_row["share_of_tin_holders_using_mm_pct"], desc_rows[1]["tin_rate_pct"], desc_rows[2]["tin_rate_pct"], ame["percentage_points"],
        ame["ci95_percentage_points"][0], ame["ci95_percentage_points"][1], "used" if use_region else "not used"))
    return result


if __name__ == "__main__":
    run_tin_mobile_money()
