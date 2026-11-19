"""W-TARGET (Pass 6B-1) - Honest intervals for the Entry targeting claims, behind `python run_all.py --full-bootstrap`.

Promoted from the Pass 6A (D4) and Pass 6C (E7) diagnostics. Three parts, all aggregates (no respondent-level rows, no numerators of fewer than 10 are written):

1. RESPONDENT BOOTSTRAP of the top-decile MULTIPLIER among Entry-age adults (16-24), refitting the model in every replicate.
   Per replicate b (seed = targeting.seeds.bootstrap + b): resample all respondents with replacement (each keeps its survey weight); out-of-fold predictions on the resampled data with
   StratifiedGroupKFold (group = original respondent, so nobody is in the training and the test part of one replicate); logistic C = the point-estimate C (not re-tuned per replicate);
   features and standardisation are refit inside every fold; modelled multiplier = mean prediction of the top decile (10% of the weighted Entry population) / mean prediction of Entry; observed ratio =
   observed TIN rate of the top decile / Entry rate. Two models: SURVEY model (the full feature set, band-calibrated predictions) and REGISTER-only model (age, sex, region, urban/rural: what TRA can
   obtain from its own records; raw out-of-fold ranking, levels band-calibrated for the per-10,000 pair).
2. LEAKAGE-ADJUSTED AUC: the survey model refit without every column of a formal-product family (banking, credit, insurance, pension, vehicle, land title, securities, formal employment, plus the
   columns the leakage review marks UNCERTAIN) and the six top-30 columns the analyst classified as consequences of holding a TIN (config.yaml targeting.leakage_adjustment): same split, CV and seeds.
3. LEAVE-ONE-ZONE-OUT AUC of the register-only model (nine NBS zones; the held-out zone gets no region effect): per zone and pooled.

Publication rules: a multiplier is always published with its 95% interval; the OBSERVED top-decile ratio is published only with its interval and only if the TIN holders in the top decile are 10 or more
in every replicate used (else it is flagged low precision and the number is withheld); numerators under 10 are never written.

Cached result: outputs/cache/targeting_bootstrap.json (outside the folders that --clean empties), with its parameters and hashes (data, config block, this code, library versions, seeds).
A normal run reads the cache and checks the hashes; `--full-bootstrap` recomputes it (about 1,000 replicates x 2 models: tens of minutes on 8-12 cores, OS processes, one thread each).
Evidence type: COMPUTED (survey data); the multiplier is a ratio of model predictions, not a causal effect.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import disclosure

CFG = paths.CFG["targeting"]
CACHE = paths.TARGETING_BOOTSTRAP
SHARD_DIR = os.path.join(paths.ROOT, "data", "interim", "targeting_bootstrap")
LABEL = "COMPUTED from FinScope Tanzania 2023 (respondent bootstrap, 95% intervals); a ratio of model predictions, not a causal effect"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _targeting():
    import targeting_model as T
    return T


def _setup(model):
    """Feature matrix, labels, weights, ages, stages and the point-estimate C of one model ('survey' or 'register')."""
    T = _targeting()
    import leakage_review
    from finscope_segments import WEIGHT_VAR, lifecycle_stage, tin_holder_mask
    df = T.load_frame()
    y = tin_holder_mask(df).astype(int).to_numpy()
    w = pd.to_numeric(df[WEIGHT_VAR]).to_numpy(float)
    age = pd.to_numeric(df["c8c"]).to_numpy(float)
    stage = pd.Series(lifecycle_stage(df), index=df.index).to_numpy()
    stored = json.load(open(paths.TARGETING_MODEL, encoding="utf-8"))
    if model == "survey":
        X, _ = T.build_features(df)
        flagged = T.single_feature_screen(X, y, w, float(CFG["feature_rules"]["max_single_feature_auc"]))
        X = X.drop(columns=[c for c, _ in flagged])
        dm = pd.read_excel(paths.FINSCOPE_DATAMAP, sheet_name="Variables", header=1)
        labels = dict(zip(dm["Variable"].astype(str), dm["Label"].astype(str)))
        rr = leakage_review.review(sorted({T.source_column(c) for c in X.columns}), labels)
        requires = {r["feature"] for r in rr if r["class"] == "REQUIRES_TIN"}
        X = X.loc[:, [c for c in X.columns if T.source_column(c) not in requires]]
        C = float(stored["hyperparameters"]["logistic_regression"]["C"])
        calibrate = True
    else:
        X = T.variant_matrix(df, list(CFG["variants"]["core"]["features"]))
        C = float(stored["variants"]["core"]["logistic_C"])
        calibrate = False
    return {"T": T, "df": df, "y": y, "w": w, "age": age, "stage": stage, "X": X, "C": C, "calibrate": calibrate, "review": (rr if model == "survey" else None)}


def _decile_stats(pred, yy, ww, entry_mask):
    idx = np.where(entry_mask)[0]
    order = idx[np.argsort(-pred[idx])]
    cum = np.cumsum(ww[order]) / ww[order].sum()
    top = order[cum <= 0.10 + 1e-12]
    if len(top) == 0:
        top = order[:1]
    overall = np.average(pred[idx], weights=ww[idx])
    mult = np.average(pred[top], weights=ww[top]) / overall
    obs_all = np.average(yy[idx], weights=ww[idx])
    obs_top = np.average(yy[top], weights=ww[top])
    return mult, (obs_top / obs_all if obs_all > 0 else np.nan), np.average(pred[top], weights=ww[top]) * 10000, overall * 10000, int(yy[top].sum())


def _one_replicate(S, b):
    from sklearn.model_selection import StratifiedGroupKFold
    T = S["T"]
    y, w, age, stage, Xv = S["y"], S["w"], S["age"], S["stage"], S["X"].to_numpy(float)
    rng = np.random.default_rng(int(CFG["seeds"]["bootstrap"]) + b)
    samp = rng.choice(len(y), size=len(y), replace=True)
    yb, wb, ab, sb, Xb = y[samp], w[samp], age[samp], stage[samp], Xv[samp]
    pred = np.zeros(len(samp))
    sgk = StratifiedGroupKFold(n_splits=int(CFG["cv_folds"]), shuffle=True, random_state=int(CFG["seeds"]["cv"]) + 1 + b)
    for a, bb in sgk.split(Xb, yb, groups=samp):
        pred[bb], _ = T.fit_predict("logit", S["C"], pd.DataFrame(Xb[a]), yb[a], wb[a], pd.DataFrame(Xb[bb]))
    em = sb == "entry"
    if yb[em].sum() == 0:
        return None
    bands = [tuple(x) for x in CFG["agent_age_bands"]]
    try:
        cal, _ = T.band_calibration(pred, yb, wb, ab, bands)
    except Exception:
        cal = pred
    use = cal if S["calibrate"] else pred
    mult, obs_ratio, _, _, n_top_tin = _decile_stats(use, yb, wb, em)
    _, _, top_cal, all_cal, _ = _decile_stats(cal, yb, wb, em)
    return {"b": b, "multiplier": float(mult), "observed_ratio": float(obs_ratio), "top_per10k_cal": float(top_cal), "entry_per10k_cal": float(all_cal), "tin_holders_in_top_decile": n_top_tin}


def run_shard(model, n_rep, shard, nshards):
    """One OS process: replicates b = shard, shard + nshards, ... written to data/interim/targeting_bootstrap/."""
    S = _setup(model)
    res = [_one_replicate(S, b) for b in range(n_rep) if b % nshards == shard]
    os.makedirs(SHARD_DIR, exist_ok=True)
    pd.DataFrame([r for r in res if r]).to_csv(os.path.join(SHARD_DIR, "shard_%s_%d.csv" % (model, shard)), index=False)


def _summarise(model, d, n_requested):
    q = lambda c: {"median": float(d[c].median()), "ci95": [float(d[c].quantile(0.025)), float(d[c].quantile(0.975))]}
    min_top_tin = int(d["tin_holders_in_top_decile"].min())
    obs_ok = min_top_tin >= disclosure.MIN_BASE
    out = {"model": model, "replicates_used": int(len(d)), "replicates_requested": int(n_requested), "multiplier": q("multiplier"), "share_replicates_multiplier_below_1": float((d["multiplier"] < 1).mean()),
           "top_decile_per_10000_reached": q("top_per10k_cal"), "entry_per_10000": float(d["entry_per10k_cal"].median())}
    if obs_ok:
        out["observed_ratio"] = q("observed_ratio")
    else:
        out["observed_ratio"] = {"published": False, "reason": "in at least one replicate fewer than %d TIN holders fall in the top decile: the observed ratio is low precision and its interval reaches zero; do not publish it as a number" % disclosure.MIN_BASE,
                                 "ci95_for_the_record": [float(d["observed_ratio"].quantile(0.025)), float(d["observed_ratio"].quantile(0.975))]}
    out["observed_ratio_published"] = bool(obs_ok)
    return out


def leakage_adjusted_auc():
    """Held-out weighted AUC of the survey model (a) as published and (b) without every formal-product-family column, the UNCERTAIN ones and the analyst-classified consequence columns."""
    from sklearn.model_selection import train_test_split
    S = _setup("survey")
    T, y, w, X, rr = S["T"], S["y"], S["w"], S["X"], S["review"]
    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=float(CFG["test_size"]), stratify=y, random_state=int(CFG["seeds"]["split"]))
    n_rep = int(CFG["cv_repeats"])
    cons = set(CFG["leakage_adjustment"]["consequence_source_columns"])
    families = set(CFG["leakage_adjustment"]["formal_product_families"])
    fam_cols = {r["feature"] for r in rr if r["family"] in families or r["class"] == "UNCERTAIN"} | cons
    out = {}
    for name, cols in (("published_survey_model", X.columns), ("without_formal_product_columns", [c for c in X.columns if T.source_column(c) not in fam_cols])):
        ev = T.evaluate_model(X.loc[:, cols], y, w, tr, te, n_rep, with_hgb=False)
        t = ev["held_out_test"]["logistic_regression"]
        out[name] = {"n_encoded_features": int(len(cols)), "held_out_auc_weighted": float(t["roc_auc_weighted"]), "held_out_auc_unweighted": float(t["roc_auc_unweighted"])}
    out["source_columns_dropped"] = len(fam_cols)
    return out


def leave_one_zone_out():
    """Register-only model (age, sex, region, urban/rural): AUC on a zone the model never saw, per zone and pooled; the held-out zone gets no region effect."""
    from sklearn.model_selection import train_test_split
    S = _setup("register")
    T, df, y, w = S["T"], S["df"], S["y"], S["w"]
    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=float(CFG["test_size"]), stratify=y, random_state=int(CFG["seeds"]["split"]))
    zones = paths.CFG["zones"]["regions"]
    reg2zone = {r: z for z, rs in zones.items() for r in rs}
    zone = df["reg_name"].astype(str).str.strip().map(reg2zone)
    assert zone.notna().all(), df.loc[zone.isna(), "reg_name"].unique()
    zone = zone.to_numpy()
    ev = T.evaluate_model(S["X"], y, w, tr, te, int(CFG["cv_repeats"]), with_hgb=False, c_grid=CFG["variants_c_grid"])
    C = ev["C"]
    p_all = np.zeros(len(y))
    rows = []
    for z in sorted(set(zone)):
        m_te = zone == z
        p, _ = T.fit_predict("logit", C, S["X"][~m_te], y[~m_te], w[~m_te], S["X"][m_te])
        p_all[m_te] = p
        n_tin = int(y[m_te].sum())
        row = {"zone": z, "n": int(m_te.sum()), "low_precision": bool(n_tin < disclosure.MIN_BASE), "loZo_auc_weighted": float(T._weighted_auc(y[m_te], p, w[m_te]))}
        if not disclosure.is_suppressed(n_tin):
            row["tin_holders"] = n_tin                                    # a numerator is written only at 10 or more
        rows.append(row)
    return {"C": C, "pooled_loZo_auc_weighted": float(T._weighted_auc(y, p_all, w)), "random_split_auc_weighted": float(ev["held_out_test"]["logistic_regression"]["roc_auc_weighted"]),
            "range_by_zone": [min(r["loZo_auc_weighted"] for r in rows), max(r["loZo_auc_weighted"] for r in rows)], "by_zone": rows,
            "note": "the zones have few TIN holders; zones flagged low_precision rest on fewer than %d TIN holders" % disclosure.MIN_BASE}


def _parameters(n_rep, nshards):
    import sklearn
    block = json.dumps({k: CFG[k] for k in ("seeds", "test_size", "cv_folds", "cv_repeats", "logistic", "feature_rules", "agent_age_bands", "variants_c_grid", "variants", "leakage_adjustment")}, sort_keys=True, default=str)
    return {"replicates": n_rep, "shards": nshards, "seed_base": int(CFG["seeds"]["bootstrap"]), "cv_seed_base": int(CFG["seeds"]["cv"]) + 1, "cv_folds": int(CFG["cv_folds"]), "entry_ages": "16-24", "top_decile_share": 0.10,
            "c_not_retuned_per_replicate": True, "python": sys.version.split()[0], "scikit_learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__,
            "hashes": {"finscope_csv_sha256": _sha(paths.FINSCOPE_CSV), "targeting_config_sha256": hashlib.sha256(block.encode()).hexdigest(), "targeting_model_json_sha256": _sha(paths.TARGETING_MODEL),
                       "code_sha256": _sha(os.path.abspath(__file__))}}


def dashboard_pair(models):
    """Per 10,000 Entry-age adults reached: the OBSERVED Entry TIN rate (outputs/tables/tin_by_segment.csv) is what random selection finds; targeted selection finds that rate times the bootstrap multiplier
    (the dashboard's own construction), with the multiplier's 95% interval."""
    import csv
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        entry = next(r for r in csv.DictReader(f) if r["segment"] == "entry")
    rate = float(entry["tin_rate_pct"]) / 100.0 * 10000
    out = {"random_is_the_observed_entry_rate_per_10000": rate}
    for k, label in (("register", "register_only"), ("survey", "survey_model")):
        m = models[k]["multiplier"]
        out[label] = {"targeted": {"median": rate * m["median"], "ci95": [rate * m["ci95"][0], rate * m["ci95"][1]]}, "random": rate}
    return out


def refresh_pair():
    """Recompute only the dashboard pair in the cache (cheap; the replicates are untouched)."""
    c = load_cache()
    c["dashboard_pair_per_10000_reached"] = dashboard_pair(c["models"])
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=1, ensure_ascii=False)
    return c


def full_bootstrap(n_rep=None, nshards=None):
    """Recompute everything and write the cache (slow)."""
    n_rep = int(n_rep or CFG["bootstrap_replicates_full"])
    nshards = int(nshards or min(8, os.cpu_count() or 1))
    t0 = time.time()
    os.makedirs(SHARD_DIR, exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
    results = {}
    for model in ("register", "survey"):
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--shard", model, str(n_rep), str(s), str(nshards)], env=env) for s in range(nshards)]
        for p in procs:
            if p.wait() != 0:
                raise SystemExit("targeting bootstrap shard failed (%s)" % model)
        d = pd.concat([pd.read_csv(os.path.join(SHARD_DIR, "shard_%s_%d.csv" % (model, s))) for s in range(nshards)], ignore_index=True).sort_values("b")
        results[model] = _summarise(model, d, n_rep)
        print("  targeting bootstrap, %s model: multiplier %.2fx (95%% %.2f-%.2f), %d replicates" % (model, results[model]["multiplier"]["median"], *results[model]["multiplier"]["ci95"], len(d)), flush=True)
    leak, lozo = leakage_adjusted_auc(), leave_one_zone_out()
    out = {"label": LABEL, "type": "COMPUTED (survey data)", "evidence_type": "COMPUTED", "parameters": _parameters(n_rep, nshards), "models": results, "leakage_adjusted_auc": leak, "leave_one_zone_out": lozo,
           "publication_rules": ["a multiplier is published with its 95% interval", "the observed top-decile ratio is published only with its interval and only when every replicate has at least %d TIN holders in the top decile" % disclosure.MIN_BASE,
                                 "numerators under %d are never written" % disclosure.MIN_BASE],
           "dashboard_pair_per_10000_reached": dashboard_pair(results),
           "elapsed_seconds": round(time.time() - t0)}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


def load_cache():
    """The cached bootstrap result (None when it has not been computed)."""
    if not os.path.exists(CACHE):
        return None
    with open(CACHE, encoding="utf-8") as f:
        return json.load(f)


def run_targeting_bootstrap(full=False, n_rep=None, nshards=None):
    """run_all.py step: recompute with --full-bootstrap, otherwise read the cache and check its hashes against the data and the config now."""
    if full:
        return full_bootstrap(n_rep, nshards)
    c = load_cache()
    if c is None:
        print("  no cached targeting bootstrap (outputs/cache/targeting_bootstrap.json): run `python run_all.py --full-bootstrap` to compute it")
        return None
    note = []
    if os.path.exists(paths.FINSCOPE_CSV) and _sha(paths.FINSCOPE_CSV) != c["parameters"]["hashes"]["finscope_csv_sha256"]:
        note.append("the FinScope file differs from the one the cache was computed on")
    block = json.dumps({k: CFG[k] for k in ("seeds", "test_size", "cv_folds", "cv_repeats", "logistic", "feature_rules", "agent_age_bands", "variants_c_grid", "variants", "leakage_adjustment")}, sort_keys=True, default=str)
    if hashlib.sha256(block.encode()).hexdigest() != c["parameters"]["hashes"]["targeting_config_sha256"]:
        note.append("config.yaml targeting differs from the one the cache was computed with")
    c["cache_check"] = note or ["cache parameters match the current data and config"]
    print("  targeting bootstrap read from cache: register-only %.1fx (%.1f-%.1f), survey model %.1fx (%.1f-%.1f); %s" % (
        c["models"]["register"]["multiplier"]["median"], *c["models"]["register"]["multiplier"]["ci95"], c["models"]["survey"]["multiplier"]["median"], *c["models"]["survey"]["multiplier"]["ci95"], "; ".join(c["cache_check"])))
    return c


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "--shard":
        run_shard(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    else:
        run_targeting_bootstrap(full=True)
