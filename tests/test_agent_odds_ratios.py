"""E3.1: the agent and tier simulations use the SAME mechanism as the tax-morale model: interventions multiply the agent's yearly registration odds by the model's odds ratios."""
import json
import os
import re
import sys

import numpy as np
import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402
import economic_model as em  # noqa: E402

RETIRED = ["agents.ussd.trust_uplift_low", "agents.ussd.trust_uplift_high", "agents.ussd.morale_uplift_low", "agents.ussd.morale_uplift_high",
           "agents.edu.morale_uplift_low", "agents.edu.morale_uplift_high", "agents.norm_uplift_factor"]


def _morale():
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        return json.load(f)["tax_morale_model"]


def _odds(h):
    return h / (1 - h)


def test_the_combination_rule_of_the_morale_model_is_stated_and_consistent():
    m = _morale()
    sets = m["odds_ratio_by_active_set"]
    assert "combination_rule" in m and "combined_discount" in m["combination_rule"]
    solo = {k: v["odds_ratio_implied"] for k, v in m["intervention_effects"].items()}
    for k, v in solo.items():
        assert sets[k] == pytest.approx(v, abs=1e-3)                                    # one intervention: its solo odds ratio
    pair = sets["USSD_registration_nudge+civic_tax_education"] if "USSD_registration_nudge+civic_tax_education" in sets else sets["civic_tax_education+USSD_registration_nudge"]
    assert max(solo["USSD_registration_nudge"], solo["civic_tax_education"]) < pair < solo["USSD_registration_nudge"] * solo["civic_tax_education"]
    allsix = sets["+".join(sorted(solo))]
    p0, pc = m["baseline_compliance_probability"], m["combined_intervention_probability"]
    assert allsix == pytest.approx(_odds(pc) / _odds(p0), rel=2e-3)                    # the rule reproduces the model's own combined effect


def test_hazard_odds_are_multiplied_by_the_morale_models_odds_ratios():
    params = em.load_base_params()
    n = 5000
    rng = np.random.default_rng(1)
    trust, morale, income_rank = rng.random(n), rng.random(n), rng.random(n)
    has_mm = rng.random(n) < 0.7
    urban = rng.random(n) < 0.4
    ages = rng.integers(16, 80, n)
    m = _morale()
    h0, ors0, _ = em._registration_hazard(params, trust, morale, income_rank, has_mm, urban, ages, False, m)
    h1, ors, _ = em._registration_hazard(params, trust, morale, income_rank, has_mm, urban, ages, True, m)
    sets = m["odds_ratio_by_active_set"]
    u, e = "USSD_registration_nudge", "civic_tax_education"
    assert ors0 == {"ussd": 1.0, "edu": 1.0, "both": 1.0}
    assert ors["ussd"] == sets[u] and ors["edu"] == sets[e] and ors["both"] == pytest.approx(sets["+".join(sorted((u, e)))])
    reached_u, reached_e = has_mm, urban & (ages >= assumptions.A("agents.edu.min_age"))
    ratio = _odds(h1[h0 > 0]) / _odds(h0[h0 > 0])
    expect = np.where(reached_u & reached_e, ors["both"], np.where(reached_u, ors["ussd"], np.where(reached_e, ors["edu"], 1.0)))[h0 > 0]
    assert np.allclose(ratio, expect, rtol=1e-9)                                       # every agent's odds are multiplied by exactly the odds ratio of the interventions that reach it
    assert (h1 >= h0).all() and (h1 < 1).all()
    # an agent reached by nothing is unchanged
    none = ~reached_u & ~reached_e
    assert none.any() and np.array_equal(h1[none], h0[none])


def test_the_intervention_effect_in_the_simulation_matches_the_odds_ratios():
    """Year-1 registration among the agents that start unregistered, with and without the interventions (same seed): the odds ratio of the mobile-money group
    reached only by the USSD nudge is the morale model's USSD odds ratio (hazards are small, so the odds ratio of the group rates is close to the per-agent ratio)."""
    params = em.load_base_params()
    m = _morale()
    n = 200_000
    a = em.run_agent_based_simulation(params, n_agents=n, n_years=1, interventions=True, quiet=True, morale_model=m)
    b = em.run_agent_based_simulation(params, n_agents=n, n_years=1, interventions=False, quiet=True, morale_model=m)
    assert a["odds_ratios_applied"] and not b["odds_ratios_applied"]
    sets = m["odds_ratio_by_active_set"]
    assert a["odds_ratios_applied"]["USSD_registration_nudge (mobile-money users)"] == sets["USSD_registration_nudge"]
    ra, rb = a["yearly_results"][0]["compliance_rate_exact"], b["yearly_results"][0]["compliance_rate_exact"]
    r0 = a["initial_compliance_rate"]
    assert a["initial_compliance_rate"] == b["initial_compliance_rate"]                # same population, same seed
    new_a, new_b = (ra - r0) / (1 - r0), (rb - r0) / (1 - r0)                           # year-1 share of the unregistered that register
    pooled = _odds(new_a) / _odds(new_b)
    assert 1.1 < pooled < max(sets.values()) * 1.1                                      # between no effect and the strongest group's odds ratio
    assert a["status"].startswith("CALIBRATED") and "odds ratios" in a["status"]


def test_the_trust_morale_uplift_path_is_retired_with_the_stated_reason():
    for k in RETIRED:
        assert k not in assumptions.keys()
        with pytest.raises(KeyError):
            assumptions.A(k)
    retired = paths.CFG["retired_assumptions"]
    for k in RETIRED:
        assert retired[k]["retired_in"] == "Block E3" and retired[k]["retired_reason"].startswith("replaced by morale-model odds ratios (E3.1)"), k
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    for k in RETIRED:
        assert 'A("%s")' % k not in code, k
    # the tier simulation shares the mechanism
    tier = code[code.index("def run_tier_migration_simulation"):code.index("# F. DIGITAL TWIN: RETIRED")]
    assert "_registration_hazard(" in tier
    assert not re.search(r"trust\[.*\]\s*\+=", tier) and not re.search(r"morale\[.*\]\s*\+=", tier)


def test_c062_is_no_longer_blocked_because_the_ranking_weights_are_signed():
    import csv
    with open(paths.ASSUMPTIONS_REGISTER, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert not [r["key"] for r in rows if "C062" in r["blocks_claims"]]
    w = [r for r in rows if r["key"].startswith("agents.p_comply.") and r["basis_class"] == "UNKNOWN"]
    assert len(w) == 4 and all(r["john_signoff"] == "approved (John, 2026-11-12)" and r["label"] == "ranking weight" for r in w)
