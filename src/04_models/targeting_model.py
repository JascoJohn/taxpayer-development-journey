"""W9 - real-data targeting model (primary model since Block E2.0: without the REQUIRES_TIN features): who among Tanzania's adults is likely to hold a TIN (FinScope 2023, n = 9,915).

Replaces the synthetic "50,000 real records" model of economic_model.build_segmentation_model (retired in Block D3).

* Population: every adult respondent; outcome: TIN holding (c27__13 = Yes); survey weight population_wt.
* Features: every suitable column of the FinScope data map beyond the former six (demographics, education, livelihood, business
  ownership, mobile money and digital use, financial access, region-level or coarser geography), one-hot encoded. EXCLUDED, with a
  reason each in the leakage audit: the outcome, all identity-document items (c27__*), anything about registration with
  authorities (D6_4*), identity-linked items (c24_2a, gov_2__7), weights / design columns / geography finer than region,
  free-form or very high-cardinality columns, near-constant columns, and any single feature that alone reaches a weighted
  AUC above the configured ceiling (mechanically tied to the outcome).
* Models: L2-regularised logistic regression (primary, interpretable; C chosen by repeated stratified CV on the training set) and a
  HistGradientBoosting comparator. Stratified 20% held-out test set + repeated stratified 5-fold CV on the training set. Metrics:
  ROC-AUC, PR-AUC (base rate about 3.8%), Brier score, calibration table; survey weights in fitting and evaluation, unweighted
  numbers reported alongside. All seeds and hyper-parameters are in config.yaml `targeting:`.
* Scoring: out-of-fold propensities of the primary model for every respondent; the Entry segment (ages 16-24) is summarised
  as propensity DECILES (weighted population, mean predicted propensity, observed TIN rate, unweighted n) with the disclosure
  rule (config.yaml disclosure). Only aggregates are written: no respondent-level rows, no per-person scores.
* The targeting multiplier (the report's "1.9x"): mean predicted propensity of the top-scored share of the Entry population divided
  by the mean predicted propensity of the whole Entry population (the definition used by the dashboard's Entry page).
* Agent population for the simulations (data/processed/agent_cells.json): weighted cells (age band x mobile money x urban x propensity
  decile), pooled so that every published cell has at least min_base respondents; the simulations resample agents from them.

Outputs: outputs/stats/targeting_model.json, outputs/tables/targeting_deciles.csv, data/processed/agent_cells.json
"""

import csv
import json
import math
import os
import re
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from scipy.special import expit, logit as _logit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure
import leakage_review
from finscope_segments import WEIGHT_VAR, HOUSEHOLD_WEIGHT_VAR, lifecycle_stage, tin_holder_mask

CFG = paths.CFG["targeting"]
LABEL = "COMPUTED; observational, cross-sectional prediction model; scores rank adults by likeness to TIN holders, not causal"
OUTCOME = "c27__13"

# ---------------------------------------------------------------- exclusions (leakage audit)
EXCLUDE_RULES = [
    ("outcome", re.compile(r"^c27__13$"), "the outcome itself (holds a TIN)"),
    ("identity_documents", re.compile(r"^c27__\d+$"), "document-holding items of the same question as the outcome (national ID, voter ID, passport, pay slip, title deed ...): identity documents and anything mechanically tied to the TIN item"),
    ("business_registration", re.compile(r"^D6_4(a|b|c.*)$"), "registration of the business with a government authority: tax registration / TIN is part of formal registration"),
    ("identity_linked", re.compile(r"^(c24_2a|gov_2__7)$"), "identity-linked items (SIM registered to the National ID; no proof of identity)"),
    ("weights_design_ids", re.compile(r"^(SN|population_wt|Household_weight|reg_code|dist_code|ward_code1|ea_code)$"), "weights, serial number, design columns and numeric geography codes (not features)"),
    ("geography_finer_than_region", re.compile(r"^(dist_name|ward_name)$"), "geography finer than region (district, ward)"),
]
KEEP_GEOGRAPHY = {"reg_name", "RU", "clustertype", "MZ"}          # region or coarser


def _is_yes_no(values):
    s = set(str(v).strip() for v in values)
    return s <= {"Yes", "No", "nan", ""} and "Yes" in s


def load_frame(csv_path=None):
    return pd.read_csv(csv_path or paths.FINSCOPE_CSV, low_memory=False)


# ---------------------------------------------------------------- feature construction
def build_features(df):
    """Returns (X, audit): X is a numeric DataFrame of encoded features, audit lists every excluded column with its reason."""
    rules = CFG["feature_rules"]
    max_levels, min_share, const_share = int(rules["max_levels"]), float(rules["min_level_share"]), float(rules["constant_share"])
    audit = []
    cols = {}
    n = len(df)
    for c in df.columns:
        hit = next((r for r in EXCLUDE_RULES if r[1].match(c)), None)
        if hit:
            audit.append({"variable": c, "reason_class": hit[0], "reason": hit[2]})
            continue
        s = df[c]
        if s.dtype == bool:
            s = s.astype(int)
        if pd.api.types.is_numeric_dtype(s):
            v = pd.to_numeric(s, errors="coerce")
            v = v.fillna(v.median())
            if v.nunique() <= 1:
                audit.append({"variable": c, "reason_class": "constant", "reason": "no variation"})
                continue
            cols[c] = v.astype(float)
            continue
        s = s.astype(object).where(s.notna(), "missing").astype(str).str.strip()
        vc = s.value_counts()
        if len(vc) > max_levels:
            audit.append({"variable": c, "reason_class": "high_cardinality", "reason": "%d levels (more than %d): free-form amounts, names or codes" % (len(vc), max_levels)})
            continue
        if vc.iloc[0] / n >= const_share:
            audit.append({"variable": c, "reason_class": "near_constant", "reason": "one level holds %.2f%% of respondents" % (vc.iloc[0] / n * 100)})
            continue
        if _is_yes_no(vc.index):
            cols[c + "=Yes"] = (s == "Yes").astype(float)
            continue
        for lev, cnt in vc.items():
            if cnt / n >= min_share and lev not in ("missing", ""):
                cols["%s=%s" % (c, lev)] = (s == lev).astype(float)
    X = pd.DataFrame(cols, index=df.index)
    X = X.loc[:, X.std() > 0]
    return X, audit


def _weighted_auc(y, p, w=None):
    try:
        return float(roc_auc_score(y, p, sample_weight=w))
    except ValueError:
        return float("nan")


def single_feature_screen(X, y, w, ceiling):
    """Columns whose weighted AUC (either direction) alone exceeds the ceiling: mechanically tied to the outcome."""
    flagged = []
    for c in X.columns:
        a = _weighted_auc(y, X[c].to_numpy(), w)
        a = max(a, 1 - a) if a == a else 0.5
        if a > ceiling:
            flagged.append((c, a))
    return flagged


def top_by_single_auc(X, y, w, k):
    """The k columns with the highest single-feature weighted AUC (either direction), computed on the training set only."""
    s = []
    for c in X.columns:
        a = _weighted_auc(y, X[c].to_numpy(), w)
        s.append((max(a, 1 - a) if a == a else 0.5, c))
    s.sort(reverse=True)
    return [(c, a) for a, c in s[:k]]


def hgb_permutation_importance(model, Xte, yte, wte, candidates, seed):
    """Drop in held-out weighted ROC-AUC when one candidate column is shuffled (mean of `permutation_repeats` shuffles)."""
    rng = np.random.default_rng(seed)
    base = _weighted_auc(yte, model.predict_proba(Xte)[:, 1], wte)
    out = []
    for c in candidates:
        drops = []
        for _ in range(int(CFG["permutation_repeats"])):
            Xp = Xte.copy()
            Xp[c] = rng.permutation(Xp[c].to_numpy())
            drops.append(base - _weighted_auc(yte, model.predict_proba(Xp)[:, 1], wte))
        out.append({"feature": c, "permutation_importance_auc_drop": float(np.mean(drops))})
    out.sort(key=lambda r: -r["permutation_importance_auc_drop"])
    return out[:20]


def label_search(columns, excluded_names):
    """Search the data map labels for tax / registration / identity wording and say what happened to every hit."""
    terms = CFG["label_search_terms"]
    rx = re.compile(r"|".join(terms), re.I)
    try:
        dm = pd.read_excel(paths.FINSCOPE_DATAMAP, sheet_name="Variables", header=1)
    except Exception:
        return {"terms": terms, "status": "data map not available in this run", "hits": []}
    hits = []
    for _, r in dm.iterrows():
        name, label = str(r.get("Variable")), str(r.get("Label"))
        if rx.search(label) or rx.search(name):
            hits.append({"variable": name, "label": label[:140], "action": "excluded" if name in excluded_names else "kept (not tied to TIN holding)"})
    return {"terms": terms, "status": "searched", "n_hits": len(hits), "hits": hits}


# ---------------------------------------------------------------- metrics
def metrics(y, p, w):
    y = np.asarray(y)
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    w = np.asarray(w, float)
    return {
        "roc_auc_weighted": _weighted_auc(y, p, w), "roc_auc_unweighted": _weighted_auc(y, p),
        "pr_auc_weighted": float(average_precision_score(y, p, sample_weight=w)), "pr_auc_unweighted": float(average_precision_score(y, p)),
        "brier_weighted": float(np.average((p - y) ** 2, weights=w)), "brier_unweighted": float(np.mean((p - y) ** 2)),
        "base_rate_weighted": float(np.average(y, weights=w)), "base_rate_unweighted": float(np.mean(y)),
    }


def _summ(rows):
    out = {}
    for k in rows[0]:
        v = np.array([r[k] for r in rows], float)
        out[k] = {"mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)) if len(v) > 1 else 0.0}
    return out


# ---------------------------------------------------------------- model factories
def make_logit(c):
    return LogisticRegression(C=c, penalty="l2", max_iter=int(CFG["logistic"]["max_iter"]), random_state=int(CFG["seeds"]["model"]))


def make_hgb():
    g = CFG["gradient_boosting"]
    return HistGradientBoostingClassifier(max_depth=int(g["max_depth"]), learning_rate=float(g["learning_rate"]), max_iter=int(g["max_iter"]),
                                          l2_regularization=float(g["l2_regularization"]), min_samples_leaf=int(g["min_samples_leaf"]),
                                          early_stopping=False, random_state=int(CFG["seeds"]["model"]))


def fit_predict(kind, c, Xtr, ytr, wtr, Xte):
    """Fit on (Xtr, ytr, wtr) and return predicted probabilities for Xte. Logit features are standardised with the training moments."""
    wtr = wtr / wtr.mean()
    if kind == "logit":
        sc = StandardScaler().fit(Xtr)
        m = make_logit(c)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(sc.transform(Xtr), ytr, sample_weight=wtr)
        return m.predict_proba(sc.transform(Xte))[:, 1], (sc, m)
    m = make_hgb()
    m.fit(Xtr, ytr, sample_weight=wtr)
    return m.predict_proba(Xte)[:, 1], (None, m)


def calibration_table(y, p, w, bins=10):
    """Test-set calibration: equal-weight groups of the predicted probability. Disclosure rule applied to each group."""
    order = np.argsort(p)
    cum = np.cumsum(w[order]) / w.sum()
    grp = np.minimum((cum * bins).astype(int), bins - 1)
    rows = []
    for g in range(bins):
        idx = order[grp == g]
        if len(idx) == 0:
            continue
        row = {"group": g + 1, "n_unweighted": int(len(idx)), "n_tin_unweighted": int(y[idx].sum()),
               "mean_predicted_pct": float(np.average(p[idx], weights=w[idx]) * 100), "observed_tin_rate_pct": float(np.average(y[idx], weights=w[idx]) * 100)}
        rows.append(disclosure.apply_to_row(row, "n_unweighted", "n_tin_unweighted", ["mean_predicted_pct", "observed_tin_rate_pct"]))
    return rows


# ---------------------------------------------------------------- E1 / E2: restricted variants and leakage refits
def variant_matrix(df, columns):
    """Encoded features built ONLY from the listed survey columns: age (numeric) and its square, every other column one-hot."""
    cols = {}
    for c in columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            v = pd.to_numeric(s, errors="coerce")
            v = v.fillna(v.median()).astype(float)
            cols[c] = v
            cols[c + "^2"] = v ** 2
        else:
            s = s.astype(object).where(s.notna(), "missing").astype(str).str.strip()
            for lev in sorted(s.unique()):
                cols["%s=%s" % (c, lev)] = (s == lev).astype(float)
    X = pd.DataFrame(cols, index=df.index)
    return X.loc[:, X.std() > 0]


def source_column(encoded_name):
    return re.split(r"=|\^2", encoded_name)[0]


def evaluate_model(X, y, w, tr, te, n_rep, with_hgb, c_grid=None):
    """Same design as the survey model: stratified split (tr, te), C of the L2 logit chosen by repeated stratified CV on the training
    set (weighted ROC-AUC), one held-out evaluation, 5-fold out-of-fold propensities for every respondent."""
    seeds = CFG["seeds"]
    Xtr, Xte, ytr, yte, wtr, wte = X.iloc[tr], X.iloc[te], y[tr], y[te], w[tr], w[te]
    cv = RepeatedStratifiedKFold(n_splits=int(CFG["cv_folds"]), n_repeats=n_rep, random_state=int(seeds["cv"]))
    splits = list(cv.split(Xtr, ytr))
    best_c, best_auc, best_summ = None, -1.0, None
    for c in (c_grid or CFG["logistic"]["c_grid"]):
        folds = []
        for a, b in splits:
            p, _ = fit_predict("logit", float(c), Xtr.iloc[a], ytr[a], wtr[a], Xtr.iloc[b])
            folds.append(metrics(ytr[b], p, wtr[b]))
        summ = _summ(folds)
        if summ["roc_auc_weighted"]["mean"] > best_auc:
            best_auc, best_c, best_summ = summ["roc_auc_weighted"]["mean"], float(c), summ
    p_logit, _ = fit_predict("logit", best_c, Xtr, ytr, wtr, Xte)
    test = {"logistic_regression": metrics(yte, p_logit, wte)}
    if with_hgb:
        p_hgb, _ = fit_predict("hgb", None, Xtr, ytr, wtr, Xte)
        test["gradient_boosting"] = metrics(yte, p_hgb, wte)
    oof = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=int(CFG["cv_folds"]), shuffle=True, random_state=int(seeds["cv"]) + 1)
    for a, b in skf.split(X, y):
        oof[b], _ = fit_predict("logit", best_c, X.iloc[a], y[a], w[a], X.iloc[b])
    return {"C": best_c, "cv_on_training_set": {"repeats": n_rep, "roc_auc_weighted": best_summ["roc_auc_weighted"], "roc_auc_unweighted": best_summ["roc_auc_unweighted"]},
            "held_out_test": test, "out_of_fold_all_adults": metrics(y, oof, w), "_oof": oof}


def _multiplier_summary(m):
    return {"top_decile": m["modelled_top_decile"], "ci95": m["bootstrap_ci95_top_decile"], "observed_top_decile": m["observed_top_decile"]}


def run_variants(df, y, w, tr, te, n_rep, entry_ctx):
    """E1: CORE and EXTENDED variants. Returns the 'variants' block (without the survey model, which the caller adds)."""
    out = {}
    for key, spec in CFG["variants"].items():
        X = variant_matrix(df, spec["features"])
        ev = evaluate_model(X, y, w, tr, te, n_rep, with_hgb=True, c_grid=CFG["variants_c_grid"])
        _, mult = entry_deciles(ev["_oof"], y, w, *entry_ctx)
        out[key] = {"label": spec["label"], "features": list(spec["features"]),
                    "obtainability": {f: CFG["feature_obtainability"][f] for f in spec["features"]},
                    "n_encoded_features": int(X.shape[1]), "encoded_from_columns": sorted({source_column(c) for c in X.columns}),
                    "logistic_C": ev["C"], "c_grid": list(CFG["variants_c_grid"]), "cross_validation": ev["cv_on_training_set"], "held_out_test": ev["held_out_test"],
                    "out_of_fold_all_adults": ev["out_of_fold_all_adults"], "entry_multiplier": _multiplier_summary(mult)}
    return out


def run_leakage_refits(df, X_all, X_primary, y, w, tr, te, n_rep, review_rows, entry_ctx, primary_summary):
    """Comparison fits around the primary model (the survey model without the REQUIRES_TIN features): the model with ALL features (the Block D
    model) and the sensitivity fit that also drops the UNCERTAIN features."""
    cls = {r["feature"]: r["class"] for r in review_rows}
    out = {}
    ev = evaluate_model(X_all, y, w, tr, te, n_rep, with_hgb=True)
    _, mult = entry_deciles(ev["_oof"], y, w, *entry_ctx)
    out["survey_model_block_d"] = {"label": "all features (the Block D model; not the primary model since Block E2.0)", "n_encoded_features": int(X_all.shape[1]), "logistic_C": ev["C"],
                                   "cross_validation": ev["cv_on_training_set"], "held_out_test": ev["held_out_test"], "held_out_test_logistic": ev["held_out_test"]["logistic_regression"],
                                   "out_of_fold_all_adults": ev["out_of_fold_all_adults"], "entry_multiplier": _multiplier_summary(mult)}
    out["without_requires_tin"] = primary_summary
    drop_src = {c for c, k in cls.items() if k in ("REQUIRES_TIN", "UNCERTAIN")}
    keep = [c for c in X_primary.columns if source_column(c) not in drop_src]
    Xr = X_primary[keep]
    ev = evaluate_model(Xr, y, w, tr, te, n_rep, with_hgb=False)
    _, mult = entry_deciles(ev["_oof"], y, w, *entry_ctx)
    out["without_requires_tin_and_uncertain"] = {"dropped_classes": ["REQUIRES_TIN", "UNCERTAIN"], "role": "sensitivity check", "n_source_columns_dropped": len(drop_src),
                                                  "n_encoded_features_dropped": int(X_all.shape[1] - Xr.shape[1]), "n_encoded_features_kept": int(Xr.shape[1]), "logistic_C": ev["C"],
                                                  "cross_validation": ev["cv_on_training_set"], "held_out_test": ev["held_out_test"], "out_of_fold_all_adults": ev["out_of_fold_all_adults"],
                                                  "entry_multiplier": _multiplier_summary(mult)}
    return out


# ---------------------------------------------------------------- E3: calibration by age band
def band_calibration(oof, y, w, age, bands):
    """Intercept shift on the logit scale, per age band, so that the weighted mean prediction equals the observed weighted TIN rate
    of the band. Ranking is unchanged within a band. Returns (calibrated predictions, table rows). The disclosure rule applies to
    the table (a band's numerator below the threshold is withheld and the row flagged)."""
    cal = np.array(oof, float)
    lg = _logit(np.clip(oof, 1e-9, 1 - 1e-9))
    tol, max_iter = float(CFG["calibration"]["tolerance"]), int(CFG["calibration"]["max_iter"])
    rows = []
    for i, (lo, hi) in enumerate(bands):
        m = (age >= lo) & ((age <= hi) if i < len(bands) - 1 else np.ones(len(age), bool))
        target = float(np.average(y[m], weights=w[m]))
        before = float(np.average(oof[m], weights=w[m]))
        a, b = -30.0, 30.0
        for _ in range(max_iter):
            mid = (a + b) / 2
            if float(np.average(expit(lg[m] + mid), weights=w[m])) < target:
                a = mid
            else:
                b = mid
            if b - a < tol:
                break
        shift = (a + b) / 2
        cal[m] = expit(lg[m] + shift)
        after = float(np.average(cal[m], weights=w[m]))
        row = {"age_from": lo, "age_to": hi, "n_unweighted": int(m.sum()), "n_tin_unweighted": int(y[m].sum()), "observed_tin_rate_pct": target * 100,
               "mean_predicted_before_pct": before * 100, "logit_shift": float(shift), "mean_predicted_after_pct": after * 100}
        rows.append(disclosure.apply_to_row(row, "n_unweighted", "n_tin_unweighted", ["observed_tin_rate_pct", "mean_predicted_before_pct", "mean_predicted_after_pct", "logit_shift"]))
    return cal, rows


# ---------------------------------------------------------------- main
def run_targeting_model(csv_path=None, json_path=None, deciles_path=None, cells_path=None, quick=False, variants_path=None, review_path=None):
    json_path = json_path or paths.TARGETING_MODEL
    deciles_path = deciles_path or paths.TARGETING_DECILES_CSV
    cells_path = cells_path or paths.AGENT_CELLS
    variants_path = variants_path or paths.TARGETING_VARIANTS_CSV
    review_path = review_path or paths.TARGETING_LEAKAGE_REVIEW_CSV
    df = load_frame(csv_path)
    y = tin_holder_mask(df).astype(int).to_numpy()
    w = pd.to_numeric(df[WEIGHT_VAR]).to_numpy(float)
    stage = pd.Series(lifecycle_stage(df), index=df.index).to_numpy()
    X, audit = build_features(df)
    flagged = single_feature_screen(X, y, w, float(CFG["feature_rules"]["max_single_feature_auc"]))
    for name, a in flagged:
        audit.append({"variable": name, "reason_class": "single_feature_leakage", "reason": "weighted AUC %.3f on its own exceeds the ceiling %.2f" % (a, float(CFG["feature_rules"]["max_single_feature_auc"]))})
    X = X.drop(columns=[c for c, _ in flagged])
    # Block E2.0 decision: the PRIMARY model is the survey model WITHOUT the features that REQUIRE a TIN (leakage review, E2 of Block E1);
    # the model with all features (Block D) and the fit that also drops the UNCERTAIN features are reported as comparisons
    dm_labels = {}
    try:
        dmf = pd.read_excel(paths.FINSCOPE_DATAMAP, sheet_name="Variables", header=1)
        dm_labels = dict(zip(dmf["Variable"].astype(str), dmf["Label"].astype(str)))
    except Exception:
        pass
    review_rows = leakage_review.review(sorted({source_column(c) for c in X.columns}), dm_labels)
    requires = {r["feature"] for r in review_rows if r["class"] == "REQUIRES_TIN"}
    X_all = X
    for r in review_rows:
        if r["class"] == "REQUIRES_TIN":
            audit.append({"variable": r["feature"], "reason_class": "requires_tin", "reason": "obtaining or holding it requires a TIN (leakage review): " + r["basis"][:160]})
    X = X.loc[:, [c for c in X_all.columns if source_column(c) not in requires]]
    seeds = CFG["seeds"]
    n_rep = 1 if quick else int(CFG["cv_repeats"])

    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=float(CFG["test_size"]), stratify=y, random_state=int(seeds["split"]))
    Xtr, Xte, ytr, yte, wtr, wte = X.iloc[tr], X.iloc[te], y[tr], y[te], w[tr], w[te]

    # --- repeated stratified CV on the training set: choose C for the logit, report both models
    cv = RepeatedStratifiedKFold(n_splits=int(CFG["cv_folds"]), n_repeats=n_rep, random_state=int(seeds["cv"]))
    splits = list(cv.split(Xtr, ytr))
    cv_results = {}
    best_c, best_auc = None, -1.0
    for c in CFG["logistic"]["c_grid"]:
        folds = []
        for a, b in splits:
            p, _ = fit_predict("logit", float(c), Xtr.iloc[a], ytr[a], wtr[a], Xtr.iloc[b])
            folds.append(metrics(ytr[b], p, wtr[b]))
        cv_results["logit_C=%g" % c] = _summ(folds)
        if cv_results["logit_C=%g" % c]["roc_auc_weighted"]["mean"] > best_auc:
            best_auc, best_c = cv_results["logit_C=%g" % c]["roc_auc_weighted"]["mean"], float(c)
    folds = []
    for a, b in splits:
        p, _ = fit_predict("hgb", None, Xtr.iloc[a], ytr[a], wtr[a], Xtr.iloc[b])
        folds.append(metrics(ytr[b], p, wtr[b]))
    cv_results["gradient_boosting"] = _summ(folds)

    # --- final fits and held-out test evaluation (once)
    p_logit, (sc, lm) = fit_predict("logit", best_c, Xtr, ytr, wtr, Xte)
    p_hgb, (_, hm) = fit_predict("hgb", None, Xtr, ytr, wtr, Xte)
    test = {"logistic_regression": metrics(yte, p_logit, wte), "gradient_boosting": metrics(yte, p_hgb, wte)}
    calibration = {"logistic_regression": calibration_table(yte, p_logit, wte), "gradient_boosting": calibration_table(yte, p_hgb, wte)}

    # --- interpretability
    coefs = pd.Series(lm.coef_[0], index=X.columns)
    top = coefs.reindex(coefs.abs().sort_values(ascending=False).index)[:30]
    logit_coef = [{"feature": k, "standardised_coefficient": float(v)} for k, v in top.items()]
    hgb_imp = hgb_permutation_importance(hm, Xte, yte, wte, [c for c, _ in top_by_single_auc(Xtr, ytr, wtr, int(CFG["permutation_candidates"]))], int(seeds["model"]))

    # --- out-of-fold propensities of the primary model for EVERY respondent (never written out as rows)
    oof = np.zeros(len(df))
    skf = StratifiedKFold(n_splits=int(CFG["cv_folds"]), shuffle=True, random_state=int(seeds["cv"]) + 1)
    for a, b in skf.split(X, y):
        oof[b], _ = fit_predict("logit", best_c, X.iloc[a], y[a], w[a], X.iloc[b])
    oof_metrics = metrics(y, oof, w)

    urban = (df["clustertype"].astype(str).str.strip() == "Urban").to_numpy()      # survey cluster type (covers Zanzibar's urban areas)
    biz = (df["BusO"].astype(str).str.strip() == "Business owners").to_numpy()
    mm = (df["MM"].astype(str).str.strip() == "MM").to_numpy()

    entry = stage == "entry"
    age = pd.to_numeric(df["c8c"]).to_numpy(float)
    # E3: predicted LEVELS recalibrated within each age band (intercept shift on the logit scale; ranking unchanged)
    oof_cal, cal_rows = band_calibration(oof, y, w, age, [tuple(b) for b in CFG["agent_age_bands"]])
    entry_ctx = (entry, urban, biz, mm, df, seeds)
    deciles, multiplier = entry_deciles(oof_cal, y, w, *entry_ctx, oof_raw=oof)
    cells = agent_cells(df, oof, y, w, urban, mm, oof_cal)
    card = scoring_card(df, y, w, quick)

    # E1: restricted variants; E2: comparison fits (same split, CV design, seeds and metrics as the primary model)
    variants = run_variants(df, y, w, tr, te, n_rep, entry_ctx)
    primary_summary = {"dropped_classes": ["REQUIRES_TIN"], "n_source_columns_dropped": len(requires), "n_encoded_features_dropped": int(X_all.shape[1] - X.shape[1]),
                       "n_encoded_features_kept": int(X.shape[1]), "logistic_C": best_c, "cross_validation": {"repeats": n_rep, "roc_auc_weighted": cv_results["logit_C=%g" % best_c]["roc_auc_weighted"],
                                                                                                          "roc_auc_unweighted": cv_results["logit_C=%g" % best_c]["roc_auc_unweighted"]},
                       "held_out_test": {"logistic_regression": test["logistic_regression"]}, "out_of_fold_all_adults": oof_metrics, "entry_multiplier": _multiplier_summary(multiplier),
                       "note": "this is the PRIMARY model (Block E2.0 decision); its Entry multiplier is the band-calibrated one"}
    refits = run_leakage_refits(df, X_all, X, y, w, tr, te, n_rep, review_rows, entry_ctx, primary_summary)

    result = {
        "label": LABEL, "type": "COMPUTED (survey data)",
        "source": "FinScope Tanzania 2023, respondent-level; weights population_wt; reconstructed design for any interval",
        "population": "all %d adult respondents; outcome TIN holding (c27__13 = Yes), %d holders (%.2f%% unweighted, %.2f%% weighted)" % (len(df), y.sum(), y.mean() * 100, np.average(y, weights=w) * 100),
        "split": {"train": int(len(tr)), "test": int(len(te)), "test_size": float(CFG["test_size"]), "stratified": True, "seed": int(seeds["split"])},
        "disclosure_rule": "bins/deciles with fewer than %d unweighted respondents are suppressed; numerators below %d are not published and the estimate is flagged low_precision" % (disclosure.MIN_BASE, disclosure.LOW_PRECISION_NUMERATOR),
        "features": {"n_encoded_features": int(X.shape[1]), "n_source_columns_used": int(len({re.split(r"=", c)[0] for c in X.columns})),
                     "groups_included": "demographics, education, livelihood and income source, business ownership, mobile money and digital use, financial access and products, household, region-level or coarser geography"},
        "leakage_audit": {"n_excluded_columns": len(audit), "excluded": audit,
                          "excluded_by_class": {k: sum(1 for a in audit if a["reason_class"] == k) for k in sorted({a["reason_class"] for a in audit})},
                          "data_map_label_search": label_search(df.columns, {a["variable"] for a in audit}),
                          "single_feature_ceiling_weighted_auc": float(CFG["feature_rules"]["max_single_feature_auc"]),
                          "feature_review": {"question": "Does obtaining or holding the product behind a retained feature REQUIRE a TIN in Tanzania?",
                                             "classes": {"REQUIRES_TIN": "excluded from the first refit", "NO_REQUIREMENT": "kept (no requirement found in the sources read)",
                                                         "UNCERTAIN": "kept in the first refit, dropped in the sensitivity fit"},
                                             "formal_employment_note": "Formal employment registered for PAYE is a legitimate predictor, not leakage: TRA observes it. It is kept (class NO_REQUIREMENT, decision column).",
                                             "sources_read": {k: {"title": v[0], "url": v[1], "accessed": leakage_review.ACCESSED} for k, v in leakage_review.SOURCES.items()},
                                             "not_checked": leakage_review.NOT_READ_NOTE,
                                             "n_features_reviewed": len(review_rows),
                                             "count_by_class": {k: sum(1 for r in review_rows if r["class"] == k) for k in ("REQUIRES_TIN", "NO_REQUIREMENT", "UNCERTAIN")},
                                             "columns": "feature, label, class, basis, source_url (plus family, topic, decision)",
                                             "rows": review_rows},
                          "refits": refits,
                          "primary_model_decision": "Block E2.0: the primary model is the survey model WITHOUT the features that require a TIN (D6_3a__4, owning motorised transport for the business); Entry deciles, agent cells and the dashboard use it; the model with all features and the fit that also drops the UNCERTAIN features are comparison / sensitivity fits"},
        "hyperparameters": {"logistic_regression": {"penalty": "l2", "C": best_c, "c_grid": CFG["logistic"]["c_grid"], "selected_by": "repeated stratified CV, weighted ROC-AUC, training set only"},
                            "gradient_boosting": dict(CFG["gradient_boosting"])},
        "seeds": dict(seeds),
        "cross_validation": {"folds": int(CFG["cv_folds"]), "repeats": n_rep, "on": "training set (80%)", "results": cv_results},
        "held_out_test": test, "calibration_test_set": calibration,
        "out_of_fold_all_adults": oof_metrics,
        "logistic_top_coefficients": logit_coef, "gradient_boosting_top_permutation_importance": hgb_imp,
        "entry_segment": {"definition": "ages %d-24 (finscope_segments.lifecycle_stage == 'entry'); out-of-fold propensities of the primary model" % (paths.SEED_AGE_BAND[1] + 1),
                          "n_unweighted": int(entry.sum()), "deciles": deciles, "targeting_multiplier": multiplier},
        "scoring_card": card,
        "calibration_by_age_band": {"method": "intercept shift on the logit scale per age band so that the weighted mean out-of-fold prediction equals the observed weighted TIN rate of the band; the ranking within a band is unchanged",
                                    "bands": cal_rows},
        "variants": {"note": "same outcome, population, stratified split, repeated-CV design, seeds and metrics as the survey model; features limited to what TRA holds or could obtain",
                     "survey_model_block_d": {"label": "SURVEY: all %d encoded features (the Block D model; comparison only)" % X_all.shape[1], "n_encoded_features": int(X_all.shape[1]),
                                              "logistic_C": refits["survey_model_block_d"]["logistic_C"], "held_out_test": refits["survey_model_block_d"]["held_out_test"],
                                              "out_of_fold_all_adults": refits["survey_model_block_d"]["out_of_fold_all_adults"], "entry_multiplier": refits["survey_model_block_d"]["entry_multiplier"]},
                     "primary": {"label": "PRIMARY: survey model without the REQUIRES_TIN feature (%d encoded features)" % X.shape[1], "n_encoded_features": int(X.shape[1]), "logistic_C": best_c,
                                 "held_out_test": test, "out_of_fold_all_adults": oof_metrics, "entry_multiplier": _multiplier_summary(multiplier)},
                     **variants},
        "agent_population": {"file": paths.CFG["files"]["agent_cells"], "n_cells": len(cells["cells"]), "pooling": cells["pooling"],
                             "calibration": "mean_propensity is the band-calibrated prediction; mean_propensity_uncalibrated is the raw out-of-fold mean"},
    }
    for p in (json_path, deciles_path, cells_path, variants_path, review_path):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    with open(cells_path, "w", encoding="utf-8") as f:
        json.dump(cells, f, indent=1, ensure_ascii=False)
    cols = ["decile", "n_unweighted", "n_tin_unweighted", "weighted_population", "mean_predicted_pct", "mean_predicted_uncalibrated_pct", "observed_tin_rate_pct", "urban_pct", "business_owner_pct", "mobile_money_pct", "low_precision", "suppressed"]
    with open(deciles_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for r in deciles:
            wr.writerow([("" if r.get(c) is None else ("%.4f" % r[c] if isinstance(r.get(c), float) else r.get(c, False if c in ("low_precision", "suppressed") else ""))) for c in cols])
    write_variants_csv(variants_path, result)
    with open(review_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["feature", "label", "class", "basis", "source_url", "family", "topic", "decision"])
        for r in review_rows:
            wr.writerow([r["feature"], r["label"], r["class"], r["basis"], r["source_url"], r["family"], r["topic"], r["decision"]])
    t = test["logistic_regression"]; g = test["gradient_boosting"]
    print("  targeting: %d features; test ROC-AUC logit %.3f (unweighted %.3f) / boosting %.3f; Entry top-decile multiplier %.2fx" % (
        X.shape[1], t["roc_auc_weighted"], t["roc_auc_unweighted"], g["roc_auc_weighted"], multiplier["modelled_top_decile"]))
    return result


def write_variants_csv(path, result):
    """E1/E2 comparison table: the survey model, the restricted variants and the leakage refits side by side (held-out logistic model)."""
    v = result["variants"]
    refits = result["leakage_audit"]["refits"]
    entries = [("PRIMARY: survey model without the REQUIRES_TIN feature", v["primary"]), ("SURVEY (Block D): all features (comparison)", v["survey_model_block_d"]),
               ("EXTENDED: CORE + mobile money + business ownership / income source", v["extended"]), ("CORE: age, sex, region, urban/rural", v["core"]),
               ("SENSITIVITY: survey model without REQUIRES_TIN and UNCERTAIN items", refits["without_requires_tin_and_uncertain"])]
    cols = ["model", "n_encoded_features", "logistic_C", "roc_auc_weighted", "roc_auc_unweighted", "pr_auc_weighted", "pr_auc_unweighted", "brier_weighted", "brier_unweighted",
            "boosting_roc_auc_weighted", "boosting_roc_auc_unweighted", "entry_multiplier_top_decile", "entry_multiplier_ci95_low", "entry_multiplier_ci95_high", "entry_observed_ratio_top_decile_low_precision"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(cols)
        for name, e in entries:
            t = e["held_out_test"]["logistic_regression"] if "logistic_regression" in e["held_out_test"] else e["held_out_test"]
            g = e["held_out_test"].get("gradient_boosting") if isinstance(e["held_out_test"], dict) else None
            m = e["entry_multiplier"]
            nfeat = e.get("n_encoded_features", e.get("n_encoded_features_kept"))
            wr.writerow([name, nfeat, e.get("logistic_C", ""), "%.4f" % t["roc_auc_weighted"], "%.4f" % t["roc_auc_unweighted"], "%.4f" % t["pr_auc_weighted"], "%.4f" % t["pr_auc_unweighted"],
                         "%.5f" % t["brier_weighted"], "%.5f" % t["brier_unweighted"], "%.4f" % g["roc_auc_weighted"] if g else "", "%.4f" % g["roc_auc_unweighted"] if g else "",
                         "%.3f" % m["top_decile"], "%.3f" % m["ci95"][0], "%.3f" % m["ci95"][1], "" if m["observed_top_decile"] is None else "%.3f" % m["observed_top_decile"]])


def entry_deciles(oof, y, w, entry, urban, biz, mm, df, seeds, oof_raw=None):
    """Weighted propensity deciles of the Entry segment (decile 1 = highest propensity) and the targeting multipliers.
    `oof` are the (band-calibrated) predictions used for the levels; `oof_raw`, when given, are the uncalibrated predictions
    (same ranking within the band): their means are reported next to the calibrated ones."""
    idx = np.where(entry)[0]
    order = idx[np.argsort(-oof[idx])]
    wsum = w[order].sum()
    cum = np.cumsum(w[order]) / wsum
    grp = np.minimum((cum - 1e-12).clip(0) * 10, 9).astype(int)
    rows = []
    for g in range(10):
        ii = order[grp == g]
        if len(ii) == 0:
            continue
        row = {"decile": g + 1, "n_unweighted": int(len(ii)), "n_tin_unweighted": int(y[ii].sum()), "weighted_population": float(w[ii].sum()),
               "mean_predicted_pct": float(np.average(oof[ii], weights=w[ii]) * 100), "observed_tin_rate_pct": float(np.average(y[ii], weights=w[ii]) * 100),
               "urban_pct": float(np.average(urban[ii], weights=w[ii]) * 100), "business_owner_pct": float(np.average(biz[ii], weights=w[ii]) * 100),
               "mobile_money_pct": float(np.average(mm[ii], weights=w[ii]) * 100)}
        keys = ["mean_predicted_pct", "observed_tin_rate_pct", "urban_pct", "business_owner_pct", "mobile_money_pct"]
        if oof_raw is not None:
            row["mean_predicted_uncalibrated_pct"] = float(np.average(oof_raw[ii], weights=w[ii]) * 100)
            keys.append("mean_predicted_uncalibrated_pct")
        rows.append(disclosure.apply_to_row(row, "n_unweighted", "n_tin_unweighted", keys, ["weighted_population"]))
    overall = float(np.average(oof[idx], weights=w[idx]))
    def curve(share):
        top = order[cum <= share + 1e-12] if share < 1 else order
        if len(top) == 0:
            top = order[:1]
        return float(np.average(oof[top], weights=w[top]) / overall)
    def top_mean(share):
        top = order[cum <= share + 1e-12] if share < 1 else order
        if len(top) == 0:
            top = order[:1]
        return float(np.average(oof[top], weights=w[top]))
    shares = [0.05, 0.10, 0.20, 0.30, 0.50]
    top_decile = curve(0.10)
    # bootstrap CI of the modelled multiplier (resampling Entry respondents; seeded)
    rng = np.random.default_rng(int(seeds["bootstrap"]))
    boots = []
    for _ in range(int(CFG["bootstrap_replicates"])):
        b = rng.choice(idx, size=len(idx), replace=True)
        o = b[np.argsort(-oof[b])]
        c = np.cumsum(w[o]) / w[o].sum()
        t = o[c <= 0.10 + 1e-12]
        t = t if len(t) else o[:1]
        boots.append(np.average(oof[t], weights=w[t]) / np.average(oof[b], weights=w[b]))
    obs_overall = float(np.average(y[idx], weights=w[idx]))
    top_ids = order[cum <= 0.10 + 1e-12]
    obs_top = float(np.average(y[top_ids], weights=w[top_ids])) if len(top_ids) and obs_overall > 0 else None
    multiplier = {"definition": "mean predicted propensity of the top-scored share of the Entry population / mean predicted propensity of the whole Entry population (weighted)",
                  "modelled_top_decile": top_decile, "bootstrap_ci95_top_decile": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
                  "by_share_reached": [{"share": s, "multiplier": curve(s), "targeted_tin_holders_per_10000_reached": top_mean(s) * 10000, "random_tin_holders_per_10000_reached": overall * 10000} for s in shares],
                  "observed_top_decile": obs_top / obs_overall if obs_top is not None else None,
                  "entry_calibration": {"mean_predicted_tin_rate_pct": overall * 100, "observed_tin_rate_pct": obs_overall * 100,
                                        "note": ("levels are recalibrated within the Entry band (intercept shift on the logit scale), so the mean prediction equals the observed rate; the ranking, and therefore the multiplier, is essentially unchanged"
                                                 if oof_raw is not None else "levels as predicted by the model")},
                  "observed_note": "ratio of observed TIN rates in the top decile and overall; Entry has only %d TIN holders, so it is low precision" % int(y[idx].sum()),
                  "previous_value_report": 1.9, "previous_definition": "synthetic model: 101 targeted vs 52 random registrations from 500 messages (top 10% of a 5,000-person synthetic sample)"}
    if oof_raw is not None:
        raw_overall = float(np.average(oof_raw[idx], weights=w[idx]))
        raw_top = order[cum <= 0.10 + 1e-12]
        multiplier["entry_calibration"]["uncalibrated_mean_predicted_tin_rate_pct"] = raw_overall * 100
        multiplier["modelled_top_decile_uncalibrated"] = float(np.average(oof_raw[raw_top], weights=w[raw_top]) / raw_overall)
    return rows, multiplier


def agent_cells(df, oof, y, w, urban, mm, oof_cal=None):
    """Weighted cells (age band x mobile money x urban x propensity decile) for the simulations; pooled to at least min_base respondents.
    Deciles are cut on the raw out-of-fold propensity; mean_propensity is the band-calibrated prediction (oof_cal), mean_propensity_uncalibrated the raw one."""
    cal = oof if oof_cal is None else oof_cal
    bands = CFG["agent_age_bands"]
    age = pd.to_numeric(df["c8c"]).to_numpy()
    order = np.argsort(-oof)
    cum = np.cumsum(w[order]) / w.sum()
    decile = np.empty(len(df), int)
    decile[order] = np.minimum((cum - 1e-12).clip(0) * 10, 9).astype(int) + 1
    band_idx = np.full(len(df), -1)
    for i, (lo, hi) in enumerate(bands):
        band_idx[(age >= lo) & (age <= hi)] = i
    cells, dropped_w, dropped_n, pooled = [], 0.0, 0, 0
    for bi, (lo, hi) in enumerate(bands):
        for m_ in (0, 1):
            for u_ in (0, 1):
                grp = np.where((band_idx == bi) & (mm.astype(int) == m_) & (urban.astype(int) == u_))[0]
                if len(grp) == 0:
                    continue
                parts = [[d, d, grp[decile[grp] == d]] for d in range(1, 11)]
                parts = [p for p in parts if len(p[2])]
                while len(parts) > 1 and min(len(p[2]) for p in parts) < disclosure.MIN_BASE:
                    j = min(range(len(parts)), key=lambda k: len(parts[k][2]))
                    nb = j - 1 if j > 0 and (j == len(parts) - 1 or len(parts[j - 1][2]) <= len(parts[j + 1][2])) else j + 1
                    a, b = sorted((j, nb))
                    parts[a] = [parts[a][0], parts[b][1], np.concatenate([parts[a][2], parts[b][2]])]
                    del parts[b]
                    pooled += 1
                for d_lo, d_hi, ii in parts:
                    if len(ii) < disclosure.MIN_BASE:
                        dropped_w += float(w[ii].sum()); dropped_n += len(ii)
                        continue
                    cell = {"age_from": lo, "age_to": hi, "mobile_money": bool(m_), "urban": bool(u_), "decile_from": d_lo, "decile_to": d_hi,
                            "n_unweighted": int(len(ii)), "weighted_population": float(w[ii].sum()),
                            "mean_propensity": float(np.average(cal[ii], weights=w[ii])), "mean_propensity_uncalibrated": float(np.average(oof[ii], weights=w[ii])),
                            "propensity_rank": float(1 - (d_lo + d_hi - 1) / 20.0),
                            "tin_rate": float(np.average(y[ii], weights=w[ii]))}
                    if disclosure.is_low_precision(len(ii), int(y[ii].sum())):
                        disclosure.flag_low_precision(cell, ["tin_rate"])
                    cells.append(cell)
    return {"source": "FinScope Tanzania 2023, out-of-fold propensities of the primary targeting model",
            "type": "COMPUTED; aggregates only (cells of at least %d respondents)" % disclosure.MIN_BASE,
            "label": LABEL, "age_bands": bands,
            "pooling": {"adjacent_propensity_deciles_merged_until_each_cell_has_at_least": disclosure.MIN_BASE, "merges": pooled,
                        "respondents_in_groups_too_small_to_publish": dropped_n, "weighted_population_dropped": dropped_w},
            "cells": cells}


def scoring_card(df, y, w, quick):
    """A small, interpretable logit (age, urban, business owner, mobile money, education) with its intercept, for the dashboard's
    individual score: a calibrated probability, observational, not causal."""
    age = pd.to_numeric(df["c8c"]).to_numpy(float)
    urban = (df["clustertype"].astype(str).str.strip() == "Urban").to_numpy(float)
    biz = (df["BusO"].astype(str).str.strip() == "Business owners").to_numpy(float)
    mm = (df["MM"].astype(str).str.strip() == "MM").to_numpy(float)
    edu_map = {"No formal education": 0, "Some primary": 1, "Primary completed": 2, "Post primary technical training": 2, "Some secondary": 3, "Secondary competed-O level": 3,
               "Secondary completed-A level": 4, "Some University or other higher education": 4, "University or higher education completed": 4}
    edu = df["c11"].astype(str).str.strip().map(edu_map).fillna(2).to_numpy(float)
    feats = {"age_per_10_years": (age - 40) / 10.0, "age_squared_per_100": ((age - 40) / 10.0) ** 2, "urban_residence": urban, "business_owner": biz,
             "mobile_money": mm, "education_level_0_to_4": edu}
    Z = np.column_stack(list(feats.values()))
    m = LogisticRegression(C=float(CFG["scoring_card_C"]), max_iter=2000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(Z, y, sample_weight=w / w.mean())
    p = m.predict_proba(Z)[:, 1]
    return {"label": LABEL, "features": list(feats), "coefficients": {k: float(v) for k, v in zip(feats, m.coef_[0])}, "intercept": float(m.intercept_[0]),
            "fit": "L2-regularised logistic regression, C = %g, survey-weighted, all adults" % float(CFG["scoring_card_C"]),
            "in_sample_weighted_roc_auc": _weighted_auc(y, p, w),
            "age_centering": "age is entered as (age - 40) / 10; the dashboard computes the same transformation"}


if __name__ == "__main__":
    run_targeting_model()
