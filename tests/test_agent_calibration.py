"""E2.4 / E3.1 / E3.2: the no-intervention agent simulation is calibrated to TRA's registered-taxpayer trend; the fit is reproducible and honestly reported."""
import json
import math
import os
import sys

import numpy as np
import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402


def _cal():
    with open(paths.AGENT_CALIBRATION, encoding="utf-8") as f:
        return json.load(f)


def test_the_calibration_reports_its_target_method_and_fit():
    c = _cal()
    assert c["type"] == "CALIBRATED" and c["status"] == "fit ok"
    assert c["method"]["free_parameters"] == 2 and c["target"]["points_fitted"] == 6 and c["method"]["free_parameters"] < c["target"]["points_fitted"]
    assert "Nelder-Mead" in c["method"]["algorithm"] and "scaling" in c["target"] and "FinScope 2023" in c["target"]["scaling"]
    table = c["fit"]["table"]
    assert [t["fiscal_year"] for t in table] == ["2018/19", "2019/20", "2020/21", "2021/22", "2022/23", "2023/24"]
    rmse = math.sqrt(np.mean([t["difference_pp"] ** 2 for t in table]))
    assert rmse == pytest.approx(c["fit"]["rmse_pp"], abs=1e-9) and rmse <= 0.25
    for t in table:
        assert abs(t["simulated_pct"] - t["target_adult_registration_rate_pct"]) == pytest.approx(abs(t["difference_pp"]), abs=1e-9)
    idf = c["identifiability"]
    assert -1.0 <= idf["correlation_between_parameters"] <= 1.0 and len(idf["profile_rmse_over_conversion_rate"]) == 7 and len(idf["profile_rmse_over_intercept"]) == 7
    assert min(p["rmse_pp"] for p in idf["profile_rmse_over_conversion_rate"]) == pytest.approx(c["fit"]["rmse_pp"], abs=0.05)   # the centre of the profile is the optimum


def test_the_parameters_are_calibrated_entries_read_from_the_file():
    c = _cal()
    for key in ("agents.conversion_rate", "agents.p_comply.intercept"):
        e = assumptions.entry(key)
        assert e["basis"] == "CALIBRATED" and "value" not in e and e["calibration"]["target"] and e["calibration"]["method"], key
    assert assumptions.A("agents.conversion_rate") == c["parameters"]["conversion_rate"]
    assert assumptions.A("agents.p_comply.intercept") == c["parameters"]["intercept"]
    assert c["parameters"]["conversion_rate"] < c["parameters"]["previous"]["conversion_rate"]                 # the typed 0.15 was far too high for the observed trend


def test_the_fit_reproduces_with_the_same_seeds():
    import economic_model as em
    import agent_calibration as ac
    c = _cal()
    params = em.load_base_params()
    fys, tgt, anchor = ac.targets()
    theta = (c["parameters"]["log10_conversion_rate"], c["parameters"]["intercept"])
    n = int(paths.CFG["agent_calibration"]["n_agents"])
    sim1 = ac.simulate(theta, params, n, 6, tgt[0])
    sim2 = ac.simulate(theta, params, n, 6, tgt[0])
    assert np.array_equal(sim1, sim2)                                                                           # seeded: identical
    rmse = float(np.sqrt(np.mean(((sim1 - tgt[1:]) * 100) ** 2)))
    assert rmse == pytest.approx(c["fit"]["rmse_pp"], abs=1e-6) and rmse <= 0.25                               # no-intervention fit within the reported RMSE
    assert np.allclose(sim1 * 100, [t["simulated_pct"] for t in c["fit"]["table"]], atol=1e-9)


def test_the_simulation_outputs_state_their_status_and_the_flag_is_cleared_only_when_calibrated():
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    for key in ("agent_based_simulation", "tier_migration_simulation"):
        assert model[key]["status"].startswith("CALIBRATED (Blocks E2.4 / E3.1)"), key
    assert model["agent_based_simulation"]["scenario"].startswith("interventions")
    c = _cal()
    assert c["status"] == "fit ok"
    import economic_model as em
    assert em.agent_status().startswith("CALIBRATED")
    # a failed or missing calibration keeps the flag
    import shutil, tempfile
    saved = paths.AGENT_CALIBRATION
    tmp = os.path.join(tempfile.mkdtemp(), "missing.json")
    try:
        paths.AGENT_CALIBRATION = tmp
        assert em.agent_status() == "UN-RECALIBRATED - NOT FOR PUBLICATION"
    finally:
        paths.AGENT_CALIBRATION = saved


def test_the_identified_combination_and_the_third_target_search_are_reported():
    """Block E3.2: no compatible third target exists; the identified combination conversion x (mean index + intercept) is reported with its fit."""
    c = _cal()
    ic = c["identifiability"]["identified_combination"]
    assert ic["value"] == pytest.approx(ic["conversion_rate"] * (ic["mean_index_non_registered_at_start"] + ic["intercept"]), rel=1e-9)
    assert ic["fit_rmse_pp"] == pytest.approx(c["fit"]["rmse_pp"], abs=1e-12)
    lo, hi = ic["range_over_profile_points_with_rmse_within_20pct_of_best"]
    assert lo <= ic["value"] <= hi and (hi - lo) / ic["value"] < 0.6                    # the combination varies little along the well-fitting ridge while the parameters vary a lot
    ts = c["third_target_search"]
    assert ts["result"] == "no third target integrated" and len(ts["searched"]) == 3
    assert "Q27" in ts["searched"][0] and "FinScope" in ts["searched"][0]
    assert c["method"]["free_parameters"] == 2 and c["target"]["points_fitted"] == 6
