"""Editing Pass 3: the dashboard follows the report. Labels are the report's COMPUTED / MODELLED / CITED plus ILLUSTRATIVE for demo inputs, the Enterprise
metrics equal the year-10 tier distribution of the stored simulation, and the Active page's presumptive schedule is the configured Finance Act 2026 schedule.
Read-only: nothing here writes to the project."""
import json
import os
import re
import sys

import pytest
import yaml

from conftest import ROOT

DASH = os.path.join(ROOT, "dashboard")
ECON = os.path.join(ROOT, "outputs", "stats", "economic_model.json")
OLD_LABELS = ("MODEL-CALCULATED", "FIRST-PASS", "HYPOTHESIS", "CAUSAL ESTIMATE", "EARNED")
SOURCES = [os.path.join(DASH, "Home.py")] + [os.path.join(DASH, "pages", f) for f in sorted(os.listdir(os.path.join(DASH, "pages"))) if f.endswith(".py")] \
    + [os.path.join(DASH, "tdj_lib", f) for f in sorted(os.listdir(os.path.join(DASH, "tdj_lib"))) if f.endswith(".py")]


def _text(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def dash(monkeypatch):
    monkeypatch.syspath_prepend(DASH)
    monkeypatch.chdir(DASH)
    import streamlit as st
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None, raising=False)       # AppTest has no multipage context; links are not under test
    monkeypatch.setattr(st, "switch_page", lambda *a, **k: None, raising=False)
    monkeypatch.delenv("TDJ_PIPELINE_DIR", raising=False)
    return DASH


def test_the_dashboard_labels_are_only_computed_modelled_cited_and_illustrative():
    import importlib
    sys.path.insert(0, DASH)
    try:
        styling = importlib.import_module("tdj_lib.styling")
    finally:
        sys.path.remove(DASH)
    assert [v[0] for v in styling._TIER_NAMES.values()] == ["COMPUTED", "MODELLED", "CITED", "ILLUSTRATIVE"]
    assert set(styling._TIER_NAMES) == {"computed", "modelled", "cited", "illustrative"}
    help_text = styling.EVIDENCE_TIER_HELP.replace("*", "")
    assert help_text == ("Every figure on this dashboard carries the same labels as the report: COMPUTED (from data), MODELLED (a scenario from stated assumptions) "
                         "or CITED (a published figure). Demo inputs are marked ILLUSTRATIVE.")
    used = set()
    for p in SOURCES:
        t = _text(p)
        used |= set(re.findall(r"evidence_tag\(\s*\"(\w+)\"", t))
        for old in OLD_LABELS:
            assert old not in t, (os.path.basename(p), old)
        assert not re.search(r"tag_txt = \"(REAL|EARNED)\"", t), os.path.basename(p)
    assert used and used <= set(styling._TIER_NAMES), used


def test_no_old_evidence_wording_or_superseded_numbers_remain_in_the_dashboard_text():
    for p in SOURCES + [os.path.join(DASH, "README.md")]:
        t = _text(p)
        for old in ("first-pass", "trust before enforcement", "AUC 0.630", "100,000,000", "3.5% for", "Modeled", "modeled "):
            assert old not in t, (os.path.basename(p), old)


def test_every_page_renders_without_an_exception(dash):
    from streamlit.testing.v1 import AppTest
    pages = ["Home.py"] + ["pages/" + f for f in sorted(os.listdir(os.path.join(DASH, "pages"))) if f.endswith(".py")]
    assert len(pages) == 7
    for p in pages:
        at = AppTest.from_file(os.path.join(DASH, p), default_timeout=180)
        at.run()
        assert not at.exception, (p, [str(e.value)[:200] for e in at.exception])


def test_the_home_page_states_the_thesis_and_the_scenario_sentence(dash):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(DASH, "Home.py"), default_timeout=180)
    at.run()
    blob = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Willingness is already high; the barriers are friction and voice." in blob
    assert ("In the project's model, the six stages together reach more than any single stage, because each reaches people the others do not. "
            "These are scenario results on assumed effects, not measured outcomes.") in blob.replace("\n", " ")
    assert "No single stage reaches the compliance outcome" not in blob


@pytest.mark.skipif(not os.path.exists(ECON), reason="outputs/stats/economic_model.json not generated")
def test_enterprise_metrics_equal_the_year_10_distribution_among_registered(dash):
    from streamlit.testing.v1 import AppTest
    with open(ECON, encoding="utf-8") as f:
        y10 = json.load(f)["tier_migration_simulation"]["yearly_tier_distribution"][-1]
    registered = 100.0 - y10["not_registered_pct"]
    below = (y10["level_1_entry_pct"] + y10["level_2_bronze_pct"]) / registered * 100
    above = (y10["level_3_silver_pct"] + y10["level_4_gold_pct"] + y10["level_5_platinum_pct"]) / registered * 100
    at = AppTest.from_file(os.path.join(DASH, "pages", "4_Enterprise.py"), default_timeout=180)
    at.run()
    m = {x.label: x.value for x in at.metric}
    assert m["Adults not yet registered (year 10)"] == "%.1f%%" % y10["not_registered_pct"] == "92.4%"
    assert m["Below Silver (of registered)"] == "%.1f%%" % below == "13.8%"
    assert m["Silver or above (of registered)"] == "%.1f%%" % above == "86.2%"
    assert abs(below + above - 100.0) < 1e-9
    caps = " ".join(c.value for c in at.caption)
    assert "agents start from the FinScope population; interventions multiply registration odds by the tax-morale model's assumed odds ratios, calibrated to TRA's registration trend; tier thresholds are the Ngazi design definitions" in caps
    assert "Afrobarometer survey distributions and income from ILFS earnings" not in caps
    assert "%.1f%% of adults are registered by year 10" % registered in caps                  # the registration rate stated beside the chart


def test_the_active_page_schedule_is_the_configured_finance_act_2026_schedule(dash):
    from streamlit.testing.v1 import AppTest
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        sch = yaml.safe_load(f)["assumptions"]["tax.presumptive_schedule"]["value"]
    assert sch["threshold_turnover"] == 200000000 and sch["above_11m_rate"] == 0.04 and sch["bands"][0][0] == 4000000 and sch["bands"][-1][1] == 11000000
    sys.path.insert(0, DASH)
    try:
        import importlib
        ba = importlib.import_module("tdj_lib.benchmark_adapters")
    finally:
        sys.path.remove(DASH)
    cap = ba.presumptive_caption()
    for needle in ("TZS 4,000,000", "TZS 11,000,000", "11,000,000–200,000,000", "4.0%", "Finance Act 2026", "first twelve months"):
        assert needle in cap, needle
    for old in ("3.5%", "100,000,000"):
        assert old not in cap
    bands = " ".join(b[0] for b in ba.PRESUMPTIVE_BANDS)
    assert "11,000,000 – 200,000,000" in bands and "4.0%" in bands and "3.5%" not in bands
    at = AppTest.from_file(os.path.join(DASH, "pages", "3_Active.py"), default_timeout=180)
    at.run()
    assert not at.exception
    assert cap in " ".join(c.value for c in at.caption)
