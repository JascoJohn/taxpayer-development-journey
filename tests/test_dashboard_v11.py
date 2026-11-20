"""Dashboard v1.1, B (interactive Figure 5.1) and C (turnover check): the interactive logic reproduces the report's figures from the tracked outputs (no raw data needed)."""
import itertools
import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
sys.path.insert(0, os.path.join(ROOT, "src"))
from tdj_lib import fig51  # noqa: E402


def _json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def inp():
    return fig51.load_inputs(os.path.join(ROOT, "outputs", "stats", "figure_5_1_inputs.json"))


@pytest.fixture(scope="module")
def model():
    return _json("outputs", "stats", "economic_model.json")["tax_morale_model"]


# ---------------------------------------------------------------------------------------------------- B: interactive Figure 5.1
def test_none_on_is_today(inp, model):
    assert round(fig51.combined_probability(inp, []) * 100, 2) == 3.83
    assert fig51.combined_probability(inp, []) == pytest.approx(model["baseline_compliance_probability"], abs=5e-7)


def test_all_six_on_is_the_combined_effect(inp, model):
    assert len(inp["interventions"]) == 6
    p = fig51.combined_probability(inp, list(inp["interventions"]))
    assert round(p * 100, 2) == 10.17
    assert p == pytest.approx(model["combined_intervention_probability"], abs=5e-7)


def test_best_single_intervention(inp, model):
    name, p = fig51.best_single(inp)
    assert name == "presumptive_tax_simplification" and round(p * 100, 2) == 5.56
    assert p == pytest.approx(max(v["new_compliance_prob"] for v in model["intervention_effects"].values()), abs=5e-7)


def test_every_solo_matches_the_model(inp, model):
    for k, v in model["intervention_effects"].items():
        assert fig51.solo_probability(inp, k) == pytest.approx(v["new_compliance_prob"], abs=5e-7)


def test_separate_gains_sum_is_the_reported_naive_sum(inp, model):
    naive = fig51.separate_gains_sum(inp, list(inp["interventions"])) * 100
    assert round(naive, 2) == 12.02
    assert naive == pytest.approx(model["naive_sum_of_solo_effects_pct"], abs=1e-3)


def test_pairs_follow_the_models_odds_ratio_by_set(inp, model):
    """The model's own odds ratios of the active sets (1, 2 and 6 interventions) give the same probability as the interactive rule."""
    base = fig51.baseline_probability(inp)
    odds0 = base / (1 - base)
    for key, orr in model["odds_ratio_by_active_set"].items():
        names = key.split("+")
        if len(names) == 1:
            continue                                         # a solo effect is computed with the score cap: checked against new_compliance_prob above
        odds = odds0 * orr
        assert fig51.combined_probability(inp, names) == pytest.approx(odds / (1 + odds), abs=2e-6)


def test_combined_never_exceeds_the_separate_gains_and_note_updates(inp):
    names = list(inp["interventions"])
    for r in range(2, 7):
        for combo in itertools.combinations(names, r):
            assert fig51.combined_probability(inp, combo) <= fig51.separate_gains_sum(inp, combo) + 1e-12
    assert "diminishing returns" in fig51.explain(inp, names) and "12.02%" in fig51.explain(inp, names)
    assert "nothing to combine" in fig51.explain(inp, names[:1])
    assert "No stage" in fig51.explain(inp, [])
    assert fig51.explain(inp, names[:3]) != fig51.explain(inp, names[:4])


# ---------------------------------------------------------------------------------------------------- C: turnover check
from tdj_lib import turnover_check as tc  # noqa: E402


@pytest.fixture(scope="module")
def schedule():
    return tc.presumptive_schedule()


def test_presumptive_tax_matches_the_pipelines_schedule(schedule):
    import paths  # noqa: F401  (puts the src/<stage> folders on sys.path)
    stage_dir = os.path.join(ROOT, "src", "04_models")
    if stage_dir not in sys.path:                       # another test's monkeypatch can restore sys.path after `paths` was first imported, so do not rely on the import alone
        sys.path.insert(0, stage_dir)
    import statutory_tax
    for t in [0, 1_000_000, 4_000_000, 4_000_001, 5_500_000, 7_000_000, 9_000_000, 11_000_000, 11_000_001, 50_000_000, 199_999_999, 200_000_000]:
        got = tc.presumptive_tax(t, schedule)
        assert got == pytest.approx(float(statutory_tax.presumptive(np.array([float(t)]))[0]), rel=1e-12, abs=1e-6), t


def test_above_the_ceiling_the_regime_does_not_apply(schedule):
    r = tc.check(schedule["threshold_turnover"] + 1, 211_377.0, 754_920.0, 1_811_810.0, schedule)
    assert r["tax_tzs"] is None and "does not apply" in r["tax_text"]


def test_position_within_the_band(schedule):
    p25, med, p75 = 200_000.0, 700_000.0, 1_800_000.0
    assert tc.check(100_000, p25, med, p75, schedule)["position"] == "below"
    assert tc.check(1_000_000, p25, med, p75, schedule)["position"] == "between"
    assert tc.check(5_000_000, p25, med, p75, schedule)["position"] == "above"
    assert tc.check(med, p25, med, p75, schedule)["approx_percentile"] == pytest.approx(50.0)
    assert tc.check(p25, p25, med, p75, schedule)["approx_percentile"] == pytest.approx(25.0)
    assert tc.check(p75, p25, med, p75, schedule)["approx_percentile"] == pytest.approx(75.0)
    assert 25.0 < tc.check(1_000_000, p25, med, p75, schedule)["approx_percentile"] < 75.0


def test_the_input_is_not_stored():
    """The check is a pure function: the module touches no session state, cache, logger, file or print (checked on the syntax tree, docstrings excluded)."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(tc))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] if n.module else "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not (names & {"session_state", "cache_data", "cache_resource", "cache", "open", "print", "logging", "getLogger"})
    assert not (imported & {"streamlit", "logging"})
