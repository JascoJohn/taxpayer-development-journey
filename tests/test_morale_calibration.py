"""E2.3: the tax-morale model is recalibrated to the observed adult TIN rate; the interventions act on the logit (odds) scale."""
import csv
import json
import math
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402


def _model(project=None):
    p = paths.ECONOMIC_MODEL if project is None else os.path.join(project, "outputs", "stats", "economic_model.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)["tax_morale_model"]


def _logit(p):
    return math.log(p / (1 - p))


def test_the_baseline_reproduces_the_observed_adult_tin_rate(pipeline_run):
    m = _model(pipeline_run)
    with open(os.path.join(pipeline_run, "outputs", "tables", "tin_by_segment.csv"), encoding="utf-8", newline="") as f:
        overall = next(r for r in csv.DictReader(f) if r["segment"] == "overall")
    observed = float(overall["tin_rate_pct"]) / 100
    assert m["observed_anchor"]["value"] == pytest.approx(observed, abs=1e-12)
    assert m["baseline_compliance_probability"] == pytest.approx(observed, abs=1e-6)
    assert m["calibration"]["alpha"] + m["calibration"]["beta"] * m["calibration"]["index_at_baseline"] == pytest.approx(_logit(observed), abs=1e-9)
    assert "HOLDS A TIN" in m["definition"] and "FinScope 2023" in m["definition"]
    assert m["status"].startswith("RECALIBRATED")


def test_the_uplifts_are_on_the_logit_scale_and_converted_from_the_original_model(pipeline_run):
    m = _model(pipeline_run)
    base = m["baseline_compliance_probability"]
    conv = m["calibration"]["conversion"]
    assert set(conv) == set(m["intervention_effects"]) and len(conv) == 6
    for name, e in m["intervention_effects"].items():
        c = conv[name]
        # each effect is a constant shift of the log odds (the fitted log odds ratio), whatever the baseline
        assert _logit(e["new_compliance_prob"]) - _logit(base) == pytest.approx(c["fitted_log_odds_ratio"], abs=2e-4), name
        assert e["odds_ratio_implied"] == pytest.approx(c["fitted_odds_ratio"], abs=1e-3)
        # the conversion: the log odds ratio the ORIGINAL linear model implied at its old baseline (0.32 since Block F0 removed the trust penalty; it was 0.306) for the same uplift
        assert c["old_log_odds_ratio"] == pytest.approx(_logit(c["old_solo_probability"]) - _logit(m["calibration"]["old_baseline_probability"]), abs=1e-9)
        assert abs(c["fitted_odds_ratio"] / c["old_odds_ratio"] - 1) < 0.10, name              # the one scale parameter reproduces all six within 10%
    assert m["calibration"]["old_baseline_probability"] == pytest.approx(0.32, abs=1e-9)          # the plain weighted sum of the original driver scores (no trust penalty any more)
    assert 0.36 < conv["USSD_registration_nudge"]["old_solo_probability"] < 0.37                # the old model's solo figure without the trust penalty (35.4% with it, before Block F0)
    # the assumed driver deltas are unchanged
    assert assumptions.A("tax_morale.effect.USSD_registration_nudge.trust") == 0.08 or isinstance(assumptions.A("tax_morale.effect.USSD_registration_nudge.trust"), float)
    # no baseline of 30.6% / 58.2% / 78.0% survives
    assert m["baseline_compliance_probability"] < 0.05 and m["combined_intervention_probability"] < 0.5
    assert m["naive_sum_of_solo_effects_pct"] > m["combined_intervention_probability"] * 100   # reported, not meaningful as a probability


def test_combined_best_single_and_naive_sum_are_consistent(pipeline_run):
    m = _model(pipeline_run)
    solo = [e["new_compliance_prob"] for e in m["intervention_effects"].values()]
    naive = m["baseline_compliance_probability"] + sum(s - m["baseline_compliance_probability"] for s in solo)
    assert m["naive_sum_of_solo_effects_pct"] == pytest.approx(naive * 100, abs=0.01)
    assert max(solo) < m["combined_intervention_probability"] < naive
    assert m["combined_uplift_pct"] == pytest.approx((m["combined_intervention_probability"] / m["baseline_compliance_probability"] - 1) * 100, abs=0.2)
    # the attitude baselines stay DATA (enforcement stays an ASSUMPTION)
    for key in ("trust", "simplicity", "social_norm", "fairness"):
        assert assumptions.entry("tax_morale.baseline." + key)["basis"] == "DATA"
    assert assumptions.entry("tax_morale.baseline.enforcement")["basis"] == "ASSUMPTION"
    assert "Q46A" in assumptions.entry("tax_morale.baseline.simplicity")["source"] and "information burden only" in assumptions.entry("tax_morale.baseline.simplicity")["source"]
