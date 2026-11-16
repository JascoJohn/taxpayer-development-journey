"""E2.5 / E3.4: Table 40 stage economics: NPV factors from the formula, all six stages, seeded Monte Carlo, statutory tax schedules, 20-year ageing, Asset break-even."""
import csv
import json
import os
import sys

import numpy as np
import pytest

from conftest import ROOT, missing_raw

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402
import stage_economics as se  # noqa: E402

STAGES = ["seed", "entry", "active", "enterprise", "asset", "legacy"]


def _res(project=None):
    p = paths.STAGE_ECONOMICS if project is None else os.path.join(project, "outputs", "stats", "stage_economics.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_the_npv_factors_match_the_annuity_formula_for_each_rate():
    res = _res()
    for rate in (0.05, 0.10, 0.12):
        for n in (5, 10, 20):
            want = sum((1 + rate) ** -t for t in range(1, n + 1))
            assert se.annuity_factor(rate, n) == pytest.approx(want, abs=1e-12)
            assert res["annuity_factors"]["%g" % rate]["years_%d" % n] == pytest.approx(want, abs=1e-12)
    assert se.annuity_factor(0.05, 5) == pytest.approx(4.3295, abs=1e-4)       # the factor the old code typed as 4.33 for "10%"
    assert se.annuity_factor(0.10, 5) == pytest.approx(3.7908, abs=1e-4)
    code = open(os.path.join(ROOT, "src", "04_models", "stage_economics.py"), encoding="utf-8").read()
    assert "rev * 4.33" not in code and "annuity_factor(" in code                       # the typed NPV factor is gone (the cost-benefit block that used it was removed in Block F0)
    assert res["discount_rate"] == 0.10 and res["discount_sensitivities"] == [0.05, 0.12] and res["horizon_years"] == 10


def test_all_six_stages_are_present_with_costs_from_the_report():
    res = _res()
    assert list(res["stages"]) == STAGES
    with open(paths.TABLE40_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["stage"] for r in rows] == STAGES + ["portfolio_excluding_asset"]
    c = {s: res["stages"][s]["monte_carlo_at_10pct"] for s in STAGES}
    lo, hi = assumptions.A("stage.cost.seed_tzs")
    assert (lo, hi) == (260_000_000, 1_060_000_000) and lo <= c["seed"]["cost"]["p10"] and c["seed"]["cost"]["p90"] <= hi
    assert c["seed"]["revenue_pv"]["mean"] == 0 and "no revenue claimed" in res["stages"]["seed"]["revenue_note"]
    for s, cost in (("entry", 420e6), ("active", 600e6), ("enterprise", 750e6), ("legacy", 700e6)):
        assert assumptions.A("stage.cost.%s_tzs" % s) == cost
        assert c[s]["cost"]["median"] == pytest.approx(cost, rel=0.1)                                      # log-normal overrun around the stated figure
    assert "NOT STATED" in res["stages"]["asset"]["cost_basis"] and "stage.cost.asset_tzs" not in assumptions.keys()      # the placeholder is retired (E3.4)
    assert "cost" not in c["asset"] and "roi" not in c["asset"]
    for s in STAGES[1:]:
        if s == "asset":
            continue
        m = c[s]
        assert m["revenue_pv"]["p10"] <= m["revenue_pv"]["median"] <= m["revenue_pv"]["p90"] and m["roi"]["p10"] <= m["roi"]["p90"]
    assert res["seed_upper_cost_bound_tzs"] == 1_060_000_000
    for key in ("stage.reach_share", "stage.persistence", "stage.intervention_for_uptake", "stage.cost_overrun_sigma", "stage.uptake_log_odds_sd"):
        assert assumptions.entry(key)["basis"] == "ASSUMPTION"
    # the typed revenue and ROI of the old Table 40 are not reproduced by the model (they came from typed constants)
    roi = [c[s]["roi"]["median"] for s in ("entry", "active", "enterprise", "legacy")]
    typed = (20.7, 21.3, 5.5, 3.6)    # typed ROI of the old Table 40 (entry, active, enterprise, legacy)
    assert all(r < 0.8 * t for r, t in zip(roi, typed))


def test_the_statutory_tax_schedules_are_applied_as_written():
    inc = np.array([0.0, 3_240_000, 6_240_000, 9_120_000, 12_000_000, 20_000_000])
    assert list(se.pit(inc)) == [0, 0, 240_000, 816_000, 1_536_000, 1_536_000 + 0.30 * 8_000_000]
    assert se.pit(np.array([4_000_000.0]))[0] == pytest.approx(0.08 * 760_000)
    t = np.array([3_000_000.0, 5_000_000, 7_000_000, 9_000_000, 11_000_000, 50_000_000, 250_000_000])               # schedule of the Finance Act 2026: ceiling 200M, 4.0% above 11M
    got = se.presumptive(t)
    assert got[0] == 0 and got[1] == pytest.approx(30_000) and got[2] == pytest.approx(90_000) and got[3] == pytest.approx(150_000)
    assert got[4] == pytest.approx(210_000) and got[5] == pytest.approx(0.04 * 50_000_000) and got[6] == pytest.approx(se.pit(np.array([250_000_000.0]))[0])


def test_the_monte_carlo_is_reproducible_with_seeds(tmp_path):
    fp = bool(missing_raw())                                   # without the ILFS microdata the tax base is read from data/processed/ilfs_tax_base.json
    a = se.run_stage_economics(json_path=str(tmp_path / "a.json"), csv_path=str(tmp_path / "a.csv"), from_processed=fp)
    b = se.run_stage_economics(json_path=str(tmp_path / "b.json"), csv_path=str(tmp_path / "b.csv"), from_processed=fp)
    assert open(tmp_path / "a.json", "rb").read() == open(tmp_path / "b.json", "rb").read()
    assert open(tmp_path / "a.csv", "rb").read() == open(tmp_path / "b.csv", "rb").read()
    published = _res()
    assert a["stages"]["entry"]["monte_carlo_at_10pct"]["roi"] == published["stages"]["entry"]["monte_carlo_at_10pct"]["roi"]
    assert a["n_draws"] == 10_000


def test_stage_names_are_the_agreed_names_and_the_mapping_is_unchanged():
    res = _res()
    want = {"seed": "Michezo ya Kodi (Tax Learning Games)", "entry": "Ujumuishaji wa Kikodi (Taxpayer Targeting and Registration Tool)", "active": "Mzani wa Kodi (Presumptive Tax Estimator)",
            "enterprise": "Hatua za Kodi (Tax Progression Dashboard)", "asset": "Mali-Alama za Kodi (Tax Asset Score)", "legacy": "Urithi wa Kodi (Tax Legacy Score)"}      # config.yaml names (Editing Pass 1)
    for s, name in want.items():
        assert res["stages"][s]["report_name"] == name
    mapping = assumptions.A("stage.intervention_for_uptake")
    assert mapping == {"entry": "USSD_registration_nudge", "active": "presumptive_tax_simplification", "enterprise": "community_compliance_norms",
                       "asset": "visible_tax_returns", "legacy": "civic_tax_education"}
    for s, k in mapping.items():
        assert res["stages"][s]["morale_model_key"] == k == res["stages"][s]["mapped_intervention"]
    assert res["stages"]["seed"]["morale_model_key"] is None and "no intervention effect is mapped" in res["stages"]["seed"]["revenue_note"]


def test_twenty_year_columns_the_persistence_sensitivity_and_the_ageing_path_are_present():
    res = _res()
    with open(paths.TABLE40_CSV, encoding="utf-8", newline="") as f:
        rows = {r["stage"]: r for r in csv.DictReader(f)}
    for col in ("pv_revenue_20y_median_tzs", "roi_20y_median", "roi_20y_p10", "roi_20y_p90", "npv_20y_median_tzs", "roi_10y_aged_median",
                "roi_20y_median_persistence_0p75", "roi_20y_median_persistence_0p90", "roi_20y_median_persistence_0p95", "break_even_cost_20y_median_tzs"):
        assert col in rows["entry"], col
    assert res["long_horizon_years"] == 20 and res["horizon_years"] == 10
    for s in ("entry", "active", "enterprise", "legacy"):
        v = res["stages"][s]["variants"]
        assert set(v) >= {"horizon_10_flat", "horizon_10_aged", "horizon_20_flat", "horizon_20_aged", "horizon_20_aged_persistence_0.75", "horizon_20_aged_persistence_0.90", "horizon_20_aged_persistence_0.95"}
        r = [v["horizon_20_aged_persistence_%s" % p]["0.1"]["revenue_pv"]["median"] for p in ("0.75", "0.90", "0.95")]
        assert r[0] <= r[1] <= r[2]                                                     # the lifecycle value rises with persistence
        assert v["horizon_10_flat"]["0.1"]["revenue_pv"]["median"] == res["stages"][s]["monte_carlo_at_10pct"]["revenue_pv"]["median"]    # the signed-off 10-year headline is the flat variant
        assert v["horizon_20_flat"]["0.1"]["revenue_pv"]["median"] >= v["horizon_10_flat"]["0.1"]["revenue_pv"]["median"]
    assert assumptions.A("stage.persistence") == [0.5, 0.75, 0.9]                      # the signed-off value is unchanged
    path = res["age_earnings_path"]["multipliers"]
    assert set(path) == {"entry", "active", "enterprise", "asset", "legacy"} and all(len(p) == 20 and p[0] == pytest.approx(1.0) for p in path.values())
    assert path["entry"][19] > 1.5 and path["asset"][19] < 1.0 and path["legacy"][19] < 1.0   # young cohorts earn more as they age, older ones less
    for typ, bands in res["age_earnings_path"]["band_profiles_mean_tax_per_person_tzs"].items():
        assert all(b["n_unweighted"] >= paths.CFG["disclosure"]["min_base"] for b in bands if not b["note"]), typ


def test_ageing_paths_follow_the_profile_exactly():
    profiles = {t: {a: 100.0 if a < 30 else 200.0 for a in range(0, 98)} for t in ("all", "nonowner", "owner")}
    shares = {s: {2: 1.0} for s in se.GROUP}
    shares["entry"] = {0: 0.5, 1: 0.5}                    # bands 16-19 and 20-24
    ag = se.ageing_paths(profiles, shares, 20)
    g = ag["entry"]["g_tzs"]
    assert g[0] == pytest.approx(100.0)                                                  # all registrants are under 30 at registration
    assert g[19] == pytest.approx(200.0)                                                 # after 19 years all are 35 or older
    assert ag["entry"]["multiplier"][19] == pytest.approx(2.0)


def test_asset_has_a_break_even_block_and_is_excluded_from_the_portfolio():
    res = _res()
    asset = res["stages"]["asset"]
    be = asset["break_even_cost"]
    assert "Asset pays back at any programme cost below TZS" in be["statement_10_years"] and "Asset pays back at any programme cost below TZS" in be["statement_20_years"]
    by = be["by_variant_and_rate_tzs"]
    for v in ("horizon_10_flat", "horizon_20_aged", "horizon_20_aged_persistence_0.90"):
        for rate in ("0.1", "0.05", "0.12"):
            d = by[v][rate]
            assert d["p10"] <= d["median"] <= d["p90"] and d["median"] > 0
    assert by["horizon_10_flat"]["0.05"]["median"] > by["horizon_10_flat"]["0.1"]["median"] > by["horizon_10_flat"]["0.12"]["median"]      # a lower discount rate gives a higher break-even cost
    assert by["horizon_10_flat"]["0.1"]["median"] == asset["monte_carlo_at_10pct"]["revenue_pv"]["median"]                              # break-even cost = discounted revenue (ROI = 1)
    port = res["portfolio"]
    assert port["excludes"] == ["asset"]
    ex = ["seed", "entry", "active", "enterprise", "legacy"]
    assert port["central_at_10pct"]["cost"] == pytest.approx(sum(res["stages"][s]["central_at_10pct"]["cost"] for s in ex))
    assert port["central_at_10pct"]["revenue_pv"] == pytest.approx(sum(res["stages"][s]["central_at_10pct"]["revenue_pv"] for s in ex))
    assert "asset_revenue_reported_separately" in res
    with open(paths.TABLE40_CSV, encoding="utf-8", newline="") as f:
        rows = {r["stage"]: r for r in csv.DictReader(f)}
    assert rows["asset"]["cost_median_tzs"] == "" and rows["asset"]["roi_median"] == "" and float(rows["asset"]["break_even_cost_10y_median_tzs"]) > 0
    assert float(rows["portfolio_excluding_asset"]["cost_median_tzs"]) > 0
