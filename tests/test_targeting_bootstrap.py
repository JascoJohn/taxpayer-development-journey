"""Pass 6B-1 H6: the targeting multiplier bootstrap (respondent bootstrap refit in every replicate), its cache, the leakage-adjusted AUC and the leave-one-zone-out AUC; publication rules."""
import json
import os
import sys

import numpy as np
import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import targeting_bootstrap as tb  # noqa: E402
import run_all  # noqa: E402

needs_cache = pytest.mark.skipif(not os.path.exists(paths.TARGETING_BOOTSTRAP), reason="outputs/cache/targeting_bootstrap.json not computed (python run_all.py --full-bootstrap)")


def _cache():
    with open(paths.TARGETING_BOOTSTRAP, encoding="utf-8") as f:
        return json.load(f)


def test_decile_stats_arithmetic():
    n = 100
    pred = np.linspace(0.20, 0.01, n)                      # descending: the first 10 persons are the top decile
    y = np.zeros(n, int)
    y[:12] = 1
    w = np.ones(n)
    entry = np.ones(n, bool)
    mult, obs, top10k, all10k, n_top_tin = tb._decile_stats(pred, y, w, entry)
    top = pred[:10]
    assert mult == pytest.approx(top.mean() / pred.mean())
    assert obs == pytest.approx((y[:10].mean()) / y.mean())
    assert top10k == pytest.approx(top.mean() * 10000) and all10k == pytest.approx(pred.mean() * 10000) and n_top_tin == 10
    w2 = np.where(np.arange(n) < 10, 3.0, 1.0)             # weights change the top decile's size: 10% of the WEIGHTED population
    m2, _, _, _, _ = tb._decile_stats(pred, y, w2, entry)
    assert m2 != mult
    only_entry = np.arange(n) < 50
    m3, *_ = tb._decile_stats(pred, y, w, only_entry)
    assert m3 == pytest.approx(pred[:5].mean() / pred[:50].mean())


def test_the_observed_ratio_is_published_only_with_ten_tin_holders_in_every_top_decile():
    import pandas as pd
    base = {"b": range(200), "multiplier": np.linspace(3.5, 5.0, 200), "observed_ratio": np.linspace(1.0, 7.0, 200), "top_per10k_cal": np.linspace(300, 400, 200), "entry_per10k_cal": np.full(200, 75.0)}
    ok = tb._summarise("register", pd.DataFrame({**base, "tin_holders_in_top_decile": np.full(200, 12)}), 200)
    assert ok["observed_ratio_published"] and set(ok["observed_ratio"]) == {"median", "ci95"}
    bad = tb._summarise("register", pd.DataFrame({**base, "tin_holders_in_top_decile": np.r_[np.full(199, 12), 4]}), 200)
    assert not bad["observed_ratio_published"] and bad["observed_ratio"]["published"] is False and "ci95" not in bad["observed_ratio"] and "fewer than 10 TIN holders" in bad["observed_ratio"]["reason"]
    for r in (ok, bad):
        lo, hi = r["multiplier"]["ci95"]
        assert lo < r["multiplier"]["median"] < hi and r["replicates_used"] == 200


def test_run_all_has_the_full_bootstrap_flag_and_calls_the_step():
    assert run_all.parse_args(["--full-bootstrap"]).full_bootstrap is True and run_all.parse_args([]).full_bootstrap is False
    code = open(os.path.join(ROOT, "run_all.py"), encoding="utf-8").read()
    assert "targeting_bootstrap.run_targeting_bootstrap(full=args.full_bootstrap)" in code


@needs_cache
def test_the_cache_records_parameters_and_hashes():
    c = _cache()
    p = c["parameters"]
    assert p["replicates"] == 1000 and p["seed_base"] == 20230604 and p["c_not_retuned_per_replicate"] is True
    assert set(p["hashes"]) == {"finscope_csv_sha256", "targeting_config_sha256", "targeting_model_json_sha256", "code_sha256"} and all(len(v) == 64 for v in p["hashes"].values())
    assert "COMPUTED" in c["label"] and c["evidence_type"] == "COMPUTED"
    assert any("never written" in r for r in c["publication_rules"])


@needs_cache
def test_the_multipliers_match_the_pass_6c_bootstrap_and_carry_their_intervals():
    m = _cache()["models"]
    reg, sur = m["register"], m["survey"]
    assert reg["replicates_used"] == sur["replicates_used"] == 1000
    assert reg["multiplier"]["median"] == pytest.approx(4.43, abs=0.1) and reg["multiplier"]["ci95"] == pytest.approx([3.80, 5.11], abs=0.15)       # PASS6C E7: 4.4x (3.8-5.1)
    assert sur["multiplier"]["median"] == pytest.approx(6.39, abs=0.15) and sur["multiplier"]["ci95"] == pytest.approx([5.59, 7.36], abs=0.2)         # PASS6C E7: 6.4x (5.6-7.4)
    for r in (reg, sur):
        assert r["share_replicates_multiplier_below_1"] == 0.0
        assert r["multiplier"]["ci95"][0] < r["multiplier"]["median"] < r["multiplier"]["ci95"][1]
    pair = _cache()["dashboard_pair_per_10000_reached"]["register_only"]
    assert pair["targeted"]["median"] == pytest.approx(341, rel=0.02) and pair["random"] == pytest.approx(76.95, abs=0.05)                         # 341 against 77: the observed Entry rate x the multiplier (the dashboard's own construction)
    assert pair["targeted"]["ci95"] == pytest.approx([292, 393], rel=0.05)


@needs_cache
def test_the_observed_ratio_is_never_published_without_an_interval_or_with_a_numerator_under_10():
    for r in _cache()["models"].values():
        if r["observed_ratio_published"]:
            assert "ci95" in r["observed_ratio"]
        else:
            assert r["observed_ratio"]["published"] is False and "median" not in r["observed_ratio"]
    text = json.dumps(_cache())
    assert "n_tin_top" not in text


@needs_cache
def test_the_leakage_adjusted_and_leave_one_zone_out_auc():
    c = _cache()
    lk, lz = c["leakage_adjusted_auc"], c["leave_one_zone_out"]
    assert lk["published_survey_model"]["held_out_auc_weighted"] == pytest.approx(0.946, abs=0.003)
    assert lk["without_formal_product_columns"]["held_out_auc_weighted"] == pytest.approx(0.941, abs=0.003) and lk["source_columns_dropped"] == 243
    assert lk["without_formal_product_columns"]["n_encoded_features"] < lk["published_survey_model"]["n_encoded_features"]
    assert lz["pooled_loZo_auc_weighted"] == pytest.approx(0.795, abs=0.01) and lz["range_by_zone"] == pytest.approx([0.745, 0.863], abs=0.01) and len(lz["by_zone"]) == 9
    for z in lz["by_zone"]:
        assert ("tin_holders" in z) == (not z["low_precision"])                      # a numerator is written only at 10 or more


@needs_cache
def test_the_cache_check_reads_without_recomputing(capsys):
    c = tb.run_targeting_bootstrap(full=False)
    assert c is not None and c["cache_check"]
    assert "targeting bootstrap read from cache" in capsys.readouterr().out
