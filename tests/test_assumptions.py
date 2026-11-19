"""W12: every in-scope constant is read from config.yaml; ledger ids are stable; claims fed by UNKNOWN constants are BLOCKED."""
import csv
import glob
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402

BASES = {"DATA", "LITERATURE", "ASSUMPTION", "UNKNOWN", "CALIBRATED"}


# Pass 6B-1 assumptions registered with sign-off PENDING (owner decision outstanding): the register shows them with an empty john_signoff
PENDING_6B1_SIGNOFF = {"stage.formal_step_if_not_asked", "stage.workers_unpriced", "stage.income_basis_bracket", "hbs.owners_with_receipts_central", "hbs.receipts_annualisation", "hbs.cpi_uprating"}


def _code():
    parts = []
    for f in glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        if rel in ("src/assumptions.py",) or rel.startswith("src/tools/") or rel.startswith("src/imported/"):
            continue
        parts.append(open(f, encoding="utf-8", errors="replace").read())
    return "\n".join(parts)


def test_every_in_scope_constant_is_read_from_config():
    code = _code()
    missing = []
    for key in assumptions.keys():
        e = assumptions.entry(key)
        if "value" not in e:
            continue                                   # DATA inputs read from a file (macro.*)
        if 'A("%s")' % key not in code:
            missing.append(key)
    assert missing == []


def test_every_entry_is_classified_and_documented():
    keys = assumptions.keys()
    assert len(keys) >= 90
    for key in keys:
        e = assumptions.entry(key)
        assert e["basis"] in BASES, key
        assert e.get("source") and e.get("feeds") and e.get("group"), key
        if "value" not in e:
            assert e["basis"] in ("DATA", "CALIBRATED") and e["from"].endswith(("macro_inputs.json", "afrobarometer_morale.json", "agent_trust_morale.json", "agent_income.json", "twin_inputs.json", "agent_calibration.json")), key
            if e["basis"] == "CALIBRATED":
                assert e["calibration"]["target"] and e["calibration"]["method"], key


def test_typed_copies_are_gone_from_the_code():
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    for old in ('"cost_tzs":    420_000_000', 'true_mm_effect = 0.06', '"baseline_trust":       0.35', "pre_mm_gap = 1.5 ",
                '"Rwanda":       [9.5', "0.012 *", 'trust_penalty = max(0, 0.5'):
        assert old not in code, old
    # Block D: the synthetic segmentation / causal code and its constants are gone; the old loader is retired
    assert not os.path.exists(os.path.join(ROOT, "src", "05_simulation", "finscope_targeting_population_loader.py"))
    for retired in ("run_causal_inference_analysis", "build_segmentation_model", 'A("seg.', 'A("psm.', 'A("did.', 'A("sc.', 'A("lifecycle.', 'synthetic.urban_share'):
        assert retired not in code, retired


def test_values_are_those_of_the_former_typed_constants():
    A = assumptions.A
    # Block E1: three baselines are DATA (Afrobarometer), two stay at their former typed values (ASSUMPTION)
    assert A("tax_morale.baseline.enforcement") == 0.40
    assert A("tax_morale.weight.trust") == 0.30 and A("tax_morale.combined_discount") == 0.6
    for gone in ("sc.comparator.rwanda", "did.region.rural", "seg.n_training", "psm.true_mm_effect"):
        assert gone not in assumptions.keys()
        with pytest.raises(KeyError):
            A(gone)
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    m = model["tax_morale_model"]
    # Block E1: the baselines moved (trust, social norm and fairness now come from Afrobarometer), so the published probabilities moved with them;
    # what stays true is the arithmetic: the naive sum is built from the UNROUNDED probabilities
    unrounded = A("tax_morale.baseline.trust")
    assert 0 < unrounded < 1 and 0 < m["baseline_compliance_probability"] < 1 and 0 < m["combined_intervention_probability"] <= 1
    naive = m["baseline_compliance_probability"] + sum(v["new_compliance_prob"] - m["baseline_compliance_probability"] for v in m["intervention_effects"].values())
    assert m["naive_sum_of_solo_effects_pct"] == pytest.approx(naive * 100, abs=0.1)          # the published probabilities are rounded to 3 decimals, the naive sum is not


def test_override_changes_the_model_and_restores_it():
    import economic_model
    p = economic_model.load_base_params()
    base = economic_model.build_tax_morale_model(p)["combined_intervention_probability"]
    with assumptions.override({"tax_morale.combined_discount": 0.3}):
        assert assumptions.A("tax_morale.combined_discount") == 0.3
        changed = economic_model.build_tax_morale_model(economic_model.load_base_params())["combined_intervention_probability"]
    assert changed != base
    assert assumptions.A("tax_morale.combined_discount") == 0.6
    assert economic_model.build_tax_morale_model(economic_model.load_base_params())["combined_intervention_probability"] == base
    with pytest.raises(KeyError):
        assumptions.A("no.such.key")


def test_ledger_ids_are_stable_across_two_runs(tmp_path, monkeypatch):
    import assumption_ledger as al
    monkeypatch.setattr(al, "LEDGER_FILE", str(tmp_path / "ledger.json"))
    a = al.write_config_ledger()
    first = open(tmp_path / "ledger.json", "rb").read()
    b = al.write_config_ledger()
    second = open(tmp_path / "ledger.json", "rb").read()
    assert first == second and a == b                                              # byte-identical, no growth
    entries = [e for e in b["assumptions"] if "key" in e]
    assert len(entries) == len(assumptions.keys())
    ids = [e["assumption_id"] for e in entries]
    assert len(set(ids)) == len(ids)
    for e in entries:
        assert e["assumption_id"] == "ASS-" + hashlib.sha1(e["key"].encode("utf-8")).hexdigest()[:8].upper()


def test_pipeline_ledger_matches_the_config_block():
    with open(paths.ASSUMPTION_LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    keyed = {e["key"]: e for e in ledger["assumptions"] if "key" in e}
    assert set(keyed) == set(assumptions.keys())
    assert ledger["total"] == len(ledger["assumptions"])


def test_register_covers_every_key_nothing_unsigned_feeds_a_claim_and_c062_is_not_blocked():
    with open(paths.ASSUMPTIONS_REGISTER, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert "john_signoff" in rows[0] and "label" in rows[0]
    ok = "approved (John, 2026-11-12)"                                                                          # Blocks E2.0, E3.5 and F0
    assert set(r["john_signoff"] for r in rows) <= {"", ok}
    by_key = {r["key"]: r for r in rows}
    assert "stage.cost.asset_tzs" not in assumptions.keys()                                                      # the Asset placeholder is RETIRED (E3.4)
    assert by_key["twin.mm.penetration_cap"]["john_signoff"] == ok                                               # signed in Block F0
    assert set(assumptions.keys()) <= set(by_key)
    # F0 check: no unsigned ASSUMPTION or UNKNOWN row feeds a published claim or a dashboard value (the levy lever, the one exception of Block F, was removed by the owner in Editing Pass 1)
    claim_re = re.compile(r"C\d{3}")
    unsigned = [r["key"] for r in rows if r["basis_class"] in ("ASSUMPTION", "UNKNOWN") and not r["john_signoff"]]
    # Pass 6B-1 registered these choices with the owner's sign-off still PENDING (the brief says so); nothing else may be unsigned
    assert set(unsigned) <= PENDING_6B1_SIGNOFF, sorted(set(unsigned) - PENDING_6B1_SIGNOFF)
    unsigned = [k for k in unsigned if k not in PENDING_6B1_SIGNOFF]
    assert unsigned == [], unsigned
    assert all(not r["blocks_claims"] for r in rows if r["key"] not in unsigned)
    # labels
    for pat, lab in (("tax_morale.effect.", "assumed uplift"), ("tax_morale.weight.", "assumed weight"), ("tax_morale.combined_discount", "assumed weight"), ("agents.p_comply.", "ranking weight"),
                     ("tier.threshold.", "Ngazi design definition"), ("twin.", "twin scenario assumption"), ("simulation.", "technical/design parameter"), ("disclosure.", "technical/design parameter"),
                     ("dashboard.", "technical/design parameter")):
        for r in rows:
            if r["key"].startswith(pat) and r["basis_class"] in ("ASSUMPTION", "UNKNOWN"):
                assert r["label"] == lab, (r["key"], r["label"])
    assert "artefact" in by_key["tier.filing.clip_high"]["sensitivity"]                                          # the +20% pushes a bound above 1
    # the feeds descriptions carry the CURRENT values, not the typed 30.6% / 58.2%
    assert not any("30.6%" in r["feeds"] or "58.2%" in r["feeds"] for r in rows if r["basis_class"] != "RETIRED")
    assert any("Fig 5.1: baseline" in r["feeds"] for r in rows if r["key"].startswith("tax_morale."))
    with open(os.path.join(ROOT, "docs", "claims_map.csv"), encoding="utf-8-sig", newline="") as f:
        claims = {r["claim_id"]: r for r in csv.DictReader(f)}
    assert claims["C062"]["status"] != "BLOCKED" and not [c for c, r in claims.items() if r["status"] == "BLOCKED"]
    for c in ("C003", "C005", "C010"):
        assert claims[c]["status"] != "BLOCKED"


def test_sensitivity_flags_are_recorded_for_every_perturbable_constant():
    with open(paths.ASSUMPTION_SENSITIVITY, encoding="utf-8") as f:
        sens = json.load(f)
    res = sens["results"]
    perturbable = [k for k in assumptions.keys() if "value" in assumptions.entry(k) and assumptions.entry(k).get("group") in ("morale", "twin", "tier", "stage_economics")]
    assert set(perturbable) == set(res)
    assert all(r["flag"] in (">5%", "<=5%", "no effect") for r in res.values())
    assert sens["delta"] == 0.2 and sens["threshold_pct"] == 5.0
