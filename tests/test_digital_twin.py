"""E3.3: the digital twin's users and registrations never exceed adults; users are FinScope adult users; the USSD term applies to unregistered users only; outputs are labelled MODELLED."""
import csv
import json
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402
import economic_model as em  # noqa: E402

POLICY = {"ussd_nudge_scale": 0.6, "trust_improvement_annual": 0.025, "presumptive_tax_simplification": True}


def _quiet(fn, *a, **k):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def _model():
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        return json.load(f)


def test_users_and_registrations_never_exceed_adults_in_both_scenarios():
    model = _model()
    for key in ("digital_twin_baseline", "digital_twin_policy"):
        tw = model[key]
        assert tw["registered_taxpayers_never_exceed_adults"] and tw["mm_users_never_exceed_adults"]
        for y in tw["yearly_states"]:
            assert y["registered_taxpayers"] <= y["adults"] and y["mm_users"] <= y["adults"]
            assert y["mm_users"] <= assumptions.A("twin.mm.penetration_cap") * y["adults"] * (1 + 1e-9)
        pen = [y["mm_penetration"] for y in tw["yearly_states"]]
        assert pen == sorted(pen) and pen[-1] <= assumptions.A("twin.mm.penetration_cap")      # penetration rises toward the cap, never beyond it


def test_an_extreme_policy_hits_the_adult_ceiling_instead_of_exceeding_it():
    p = em.load_base_params()
    tw = _quiet(em.run_digital_twin, p, policy_changes={"formalization_policy": 5.0, "ussd_nudge_scale": 1.0})
    last = tw["yearly_states"][-1]
    assert last["registered_taxpayers"] <= last["adults"]
    assert all(y["registered_taxpayers"] <= y["adults"] for y in tw["yearly_states"])


def test_the_user_base_is_finscope_adult_users_and_bot_accounts_are_context_only():
    with open(paths.TWIN_INPUTS, encoding="utf-8") as f:
        ti = json.load(f)
    users = ti["parameters"]["base_mobile_money_users"]
    assert users["basis"] == "DATA" and "FinScope" in users["source"] and "persons, not accounts" in users["source"]
    adults = ti["parameters"]["base_adult_population"]["value"]
    assert 20e6 < users["value"] < adults
    with open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline="") as f:
        overall = next(r for r in csv.DictReader(f) if r["segment"] == "overall")
    assert adults == pytest.approx(float(overall["population_weighted"]), rel=1e-9)         # the same weighted adults as the TIN rate's denominator
    assert assumptions.A("base.mobile_money_users") == users["value"] and assumptions.entry("base.mobile_money_users")["basis"] == "DATA"
    assert ti["bot_active_mobile_money_accounts_context"]["value"] == 63_207_569
    tw = _model()["digital_twin_policy"]
    assert tw["context_bot_active_mobile_money_accounts"]["value"] == 63_207_569 and "context only" in tw["context_bot_active_mobile_money_accounts"]["note"]
    assert tw["yearly_states"][0]["mm_users"] < 0.9 * tw["yearly_states"][0]["adults"]
    # the account-based growth and the population cap are retired
    for k in ("twin.growth.mm_users", "twin.cap.mm_users_share_of_population"):
        assert k not in assumptions.keys() and paths.CFG["retired_assumptions"][k]["retired_in"] == "Block E3"
    e = assumptions.entry("twin.mm.penetration_cap")
    assert e["basis"] == "ASSUMPTION" and e["value"] == 0.90 and e["signoff"] == "approved (John, 2026-11-12)"        # signed in Block F0
    assert assumptions.entry("twin.mm.penetration_gap_closure")["basis"] == "ASSUMPTION" and assumptions.entry("twin.mm.penetration_gap_closure")["signoff"]


def test_the_ussd_term_applies_only_to_users_not_yet_registered():
    p = dict(em.load_base_params())
    still = {"twin.mm.penetration_cap": 0.5, "twin.growth.adult_population": 1.0}              # penetration and adults frozen: mobile-money users stay constant
    # every mobile-money user already registered: the nudge adds nothing
    p["registered_taxpayers"] = p["mobile_money_users"]
    with assumptions.override(still):
        with_nudge = _quiet(em.run_digital_twin, p, policy_changes={"ussd_nudge_scale": 0.6})
        without = _quiet(em.run_digital_twin, p, policy_changes={"ussd_nudge_scale": 0.0})
    assert with_nudge["yearly_states"][0]["new_registrations_yr"] == without["yearly_states"][0]["new_registrations_yr"]
    # half of them registered: the nudge adds conversion x scale x the unregistered half
    p["registered_taxpayers"] = p["mobile_money_users"] * 0.5
    with assumptions.override(still):
        with_nudge = _quiet(em.run_digital_twin, p, policy_changes={"ussd_nudge_scale": 0.6})
        without = _quiet(em.run_digital_twin, p, policy_changes={"ussd_nudge_scale": 0.0})
    extra = with_nudge["yearly_states"][0]["new_registrations_yr"] - without["yearly_states"][0]["new_registrations_yr"]
    expected = p["mobile_money_users"] * 0.5 * 0.6 * assumptions.A("twin.ussd.conversion")
    trust_mult = 1 + (p["baseline_trust"] + assumptions.A("twin.default.trust_improvement_annual") - p["baseline_trust"]) * assumptions.A("twin.trust_multiplier.slope")
    assert extra == pytest.approx(expected * trust_mult, rel=1e-3)


def test_every_twin_output_is_labelled_modelled():
    model = _model()
    for key in ("digital_twin_baseline", "digital_twin_policy"):
        assert model[key]["label"] == "MODELLED scenario" and model[key]["type"] == "MODELLED" and "not a forecast" in model[key]["scenario_note"]
    with open(os.path.join(ROOT, "docs", "claims_map.csv"), encoding="utf-8-sig", newline="") as f:
        claims = {r["claim_id"]: r for r in csv.DictReader(f)}
    assert claims["C079"]["type"] == "MODELLED" and "MODELLED scenario" in claims["C079"]["status"]
