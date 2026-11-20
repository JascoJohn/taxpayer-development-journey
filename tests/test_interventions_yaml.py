"""F4: the interventions come from docs/interventions.yaml; the frozen LLM sections, src/imported and the typed values are gone."""
import os
import re
import sys

import pytest
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402


def _yaml():
    with open(os.path.join(ROOT, "docs", "interventions.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_the_yaml_holds_the_six_stage_tools_with_the_agreed_names_and_is_marked_reviewed():
    y = _yaml()
    assert y["status"].startswith("REVIEWED by the owner") and "2026-11-13" in y["status"] and "llm_drafts_not_adopted" not in y
    items = y["interventions"]
    assert [i["stage"] for i in items] == ["seed", "entry", "active", "enterprise", "asset", "legacy"]
    names, labels = paths.CFG["names"], paths.CFG["stage_economics"]["report_names"]
    for i in items:
        assert i["name"] == names[i["stage"]]["full"] and i["old_names"], i["stage"]                                    # the names of Editing Pass 1; the old names stay for traceability
        assert i["mechanism"] and i["target_group"] and i["cost_reference"]["source"].startswith("programme cost assumption (signed off; composition not recorded)")   # no citation of a private file
        assert i["report_pdf_page"] == labels[i["stage"]]["pdf_page"]
        assert "eNgazi" not in i["mechanism"] and "ENgazi" not in i["mechanism"]
    for stage in ("entry", "active", "enterprise", "legacy"):
        item = next(i for i in items if i["stage"] == stage)
        assert item["cost_reference"]["cost_tzs"] == assumptions.A("stage.cost.%s_tzs" % stage)
    assert next(i for i in items if i["stage"] == "asset")["cost_reference"]["stated"] is False
    assert next(i for i in items if i["stage"] == "seed")["cost_reference"]["cost_range_tzs"] == assumptions.A("stage.cost.seed_tzs")
    drafts = yaml.safe_load(open(os.path.join(ROOT, "_archive", "interventions_llm_drafts.yaml"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "_archive", "interventions_llm_drafts.yaml")) else None
    if drafts is not None:                                                                                                  # (the archive is tracked, so an outsider has it)
        assert len(drafts["llm_drafts_not_adopted"]) == 8


def test_the_registrar_reads_the_yaml_and_nothing_else():
    code = open(os.path.join(ROOT, "src", "04_models", "intervention_registrar.py"), encoding="utf-8").read()
    assert "INTERVENTIONS_YAML" in code and "report_sections" not in code.replace("report_sections.json, now in _archive/frozen/", "") and "cost_benefit" not in code.replace("cost-benefit", "")
    assert not hasattr(paths, "REPORT_SECTIONS") and paths.INTERVENTIONS_YAML.endswith("interventions.yaml")


def test_the_frozen_sections_and_the_imported_scripts_are_no_longer_inputs():
    assert not os.path.exists(os.path.join(ROOT, "outputs", "frozen", "report_sections.json"))
    assert not os.path.exists(os.path.join(ROOT, "src", "imported"))
    for dirpath, _, files in os.walk(os.path.join(ROOT, "src")):
        for f in files:
            if f.endswith(".py") and f != "extract_interventions_once.py":
                text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                assert not re.search(r"^\s*(import|from)\s+(imported|economic_model_per_intervention|wvs_loader|ilfs_loader|data_layer_expansion)\b", text, re.M), f
                assert "report_sections.json" not in text.replace("report_sections.json, now in _archive/frozen/", "") or f in ("shared_context.py",), f


def test_no_typed_macro_values_remain_in_shared_context_and_home():
    sc = open(os.path.join(ROOT, "src", "03_features", "shared_context.py"), encoding="utf-8").read()
    for typed in ("TANZANIA_STATS = {", "LIFECYCLE_POPULATIONS_DEFAULT", "68560157", "35000000", "3200000", "12.4,", "2500,", "78844405385", "4.1% GDP"):
        assert typed not in sc, typed
    home = open(os.path.join(ROOT, "dashboard", "Home.py"), encoding="utf-8").read()
    assert "9,915" not in home and "1997" not in home
