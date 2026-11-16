"""Editing Pass 4: published outputs carry the report's evidence labels, the TIN / mobile-money specification lists the headline model's covariates, the dashboard follows the report's wording,
and the screenshot script waits for the charts. Read-only."""
import json
import os
import re

import pytest

from conftest import ROOT

OLD_TIER_STRINGS = ("first-pass", "model-calculated", "MODEL-CALCULATED", "FIRST-PASS", "hypothesis-tier")
OUT_DIRS = ["outputs/stats", "outputs/tables", "data/processed", "data/interim"]


def _text(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
        return f.read()


def test_published_outputs_carry_no_old_evidence_tier_strings():
    scanned = 0
    for d in OUT_DIRS:
        full = os.path.join(ROOT, *d.split("/"))
        if not os.path.isdir(full):
            continue
        for base, _, files in os.walk(full):
            for f in files:
                if f.endswith((".json", ".csv", ".txt", ".md")):
                    t = open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()
                    scanned += 1
                    for s in OLD_TIER_STRINGS:
                        assert s not in t, (d, f, s)
    assert scanned > 10


def test_the_source_labels_are_the_reports_types():
    for rel in ("src/04_models/tin_mobile_money.py", "src/04_models/targeting_model.py"):
        t = _text(rel)
        m = re.search(r'^LABEL = "([^"]+)"', t, re.M)
        assert m and m.group(1).startswith("COMPUTED; observational"), rel
        assert "first-pass" not in t, rel
    assert "not a causal estimate" in _text("src/04_models/tin_mobile_money.py")                  # the disclaimer stays; it is not a tier


@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "outputs", "stats", "tin_mobile_money.json")), reason="outputs not generated")
def test_the_mobile_money_specification_lists_the_headline_models_covariates():
    j = json.loads(_text("outputs/stats/tin_mobile_money.json"))
    cov = " | ".join(j["model_specification"]["covariates"])
    assert j["headline_model"] == "with region"
    assert "region" in cov and "residence (Dar es Salaam / other urban / rural / Zanzibar)" in cov and "education" in cov and "main income source" in cov
    assert j["label"].startswith("COMPUTED; observational")
    assert j["average_marginal_effect_of_mobile_money"]["label"] == j["label"]


def test_the_dashboard_follows_the_report_wording():
    active, ent = _text("dashboard/pages/3_Active.py"), _text("dashboard/pages/4_Enterprise.py")
    assert "Active removes uncertainty at the point where many informal businesses first" in active
    assert "Ngazi gives taxpayers a visible experience that engaging with the tax authority is" in ent
    for rel in ("dashboard/pages/3_Active.py", "dashboard/pages/4_Enterprise.py", "dashboard/Home.py"):
        t = _text(rel)
        for old in ("strengthens trust", "tested experience", "use_container_width"):
            assert old not in t, (rel, old)


def test_the_screenshot_script_waits_for_every_chart():
    t = _text("src/06_figures/capture_dashboard.py")
    assert "stPlotlyChart" in t and "svg.main-svg" in t and "wait_for_function" in t
