"""E2.2: the TRA registered-taxpayer series and the digital-twin base parameters."""
import csv
import json
import os
import re
import sys

import pytest
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import assumptions  # noqa: E402

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))["twin_inputs"]


def _rows(project):
    with open(os.path.join(project, "data", "processed", "tra_registered_taxpayers.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _twin(project):
    with open(os.path.join(project, "data", "processed", "twin_inputs.json"), encoding="utf-8") as f:
        return json.load(f)


def test_the_series_loads_with_definitions_and_provenance(pipeline_run):
    rows = _rows(pipeline_run)
    used = [r for r in rows if r["status"] == "used"]
    assert [r["fiscal_year"] for r in used] == ["%d/%02d" % (y, (y + 1) % 100) for y in range(2011, 2024)]       # 2011/12 ... 2023/24: 13 years
    vals = [float(r["registered_taxpayers"]) for r in used]
    assert vals == sorted(vals) and vals[-1] == 6272000 and vals[0] == 1036000
    for r in rows:
        assert r["coverage"] == "Tanzania Mainland" and r["url"].startswith("https://www.nbs.go.tz/") and r["pdf_page"] and r["table"] and r["document"]
    assert [r["fiscal_year"] for r in rows if r["status"] != "used"] == ["2017/18", "2022/23"]                    # superseded vintages stay visible
    tw = _twin(pipeline_run)
    d = tw["tra_registered_taxpayers"]["definition"]
    assert "TIN registrations" in d and "NOT comparable" in d and "1.31 million" in d
    assert "6.27 million" in tw["kept_separate_from"]["difference"] and "adults" in tw["kept_separate_from"]["finscope_adult_tin_holders"].lower()
    cp6 = tw["tra_registered_taxpayers"]["cp6_definitions"]
    assert cp6["active_business_tin"]["2021/22"] == 3336777 and "transacted within a year" in cp6["note"]


def test_every_transcribed_figure_matches_its_source_document(pipeline_run):
    import pymupdf
    series = CFG["tra_registered_taxpayers"]["series"]
    docs = CFG["tra_registered_taxpayers"]["documents"]
    text = {}
    for key, d in docs.items():
        path = os.path.join(ROOT, *d["file"].split("/"))
        text[key] = re.sub(r"\s+", " ", pymupdf.open(path)[d["pdf_page"] - 1].get_text())
    for r in series:
        pat = r"%s \|? ?%s\b" % (re.escape(r["fy"]), re.escape(format(r["thousands"], ",")))
        flat = text[r["doc"]]
        assert re.search(re.escape(r["fy"]) + r"\s+" + re.escape(format(r["thousands"], ",")), flat), (r, pat)
    for r in CFG["tra_registered_taxpayers"]["superseded"]:
        assert re.search(re.escape(r["fy"]) + r"\s+" + re.escape(format(r["thousands"], ",")), text[r["doc"]]), r
    # Bank of Tanzania series (active mobile-money accounts and value)
    bm = CFG["bot_mobile_money"]
    t22 = " ".join(p.get_text() for p in pymupdf.open(os.path.join(ROOT, *bm["documents"]["nps_2022"]["file"].split("/"))))
    t25 = " ".join(p.get_text() for p in pymupdf.open(os.path.join(ROOT, *bm["documents"]["nps_2025"]["file"].split("/"))))
    flat22, flat25 = re.sub(r"\s+", " ", t22), re.sub(r"\s+", " ", t25)
    for y in (2018, 2019, 2020, 2021, 2022):
        assert format(bm["users_active"][y], ",") in flat22, y
    for y in (2023, 2025):
        assert format(bm["users_active"][y], ",") in flat25, y
    assert "463,207,569" in flat25 and bm["users_active"][2024] == 63207569                                     # the printed typo and the corrected value
    assert format(round(bm["value_tzs_billion"][2023], 2), ",.2f") in flat25 and "198,859" in flat25


def test_the_twin_reads_the_series_and_the_other_base_parameters(pipeline_run):
    tw = _twin(pipeline_run)
    rows = [r for r in _rows(pipeline_run) if r["status"] == "used"]
    base = assumptions.A("base.registered_taxpayers")
    assert base == float(rows[-1]["registered_taxpayers"]) == tw["parameters"]["base_registered_taxpayers"]["value"]
    for key, basis in (("base.gdp_growth_rate", "DATA"), ("base.population", "DATA"), ("base.working_age_population", "DATA"), ("base.registered_taxpayers", "DATA"),
                       ("base.mobile_money_users", "DATA"), ("base.mobile_money_gdp_pct", "DATA"), ("base.informal_worker_avg_income_tzs", "DATA"),
                       ("base.msme_avg_revenue_tzs", "DATA"), ("base.adult_population", "DATA"), ("twin.growth.adult_population", "DATA"), ("twin.default.formalization_policy", "CALIBRATED")):
        e = assumptions.entry(key)
        assert e["basis"] == basis and "value" not in e and e["from"].endswith("twin_inputs.json"), key
        assert assumptions.A(key) == pytest.approx(tw["parameters"][key.replace(".", "_")]["value"], rel=1e-12, abs=0)       # the calibrated slope can differ in the last digit between numpy builds (Pass 6B-2: rebuilt .venv)
    assert tw["parameters"]["twin_default_formalization_policy"]["calibration"]["method"].startswith("ordinary least squares")
    for key in ("twin.ussd.conversion", "twin.trust_multiplier.slope", "twin.presumptive.uplift_factor"):          # retired with the digital twin (Pass 6B-1)
        assert key not in assumptions.keys() and paths.CFG["retired_assumptions"][key]["retired_in"] == "Pass 6B-1", key
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    assert "digital_twin_baseline" not in model                                                                   # retired (Pass 6B-1)
    assert model["base_parameters"]["registered_taxpayers"] == base
    # the typed values are gone
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    assert "3_200_000" not in code and "3200000" not in code
    p = tw["parameters"]
    assert 0.03 < p["base_gdp_growth_rate"]["value"] < 0.08 and 55e6 < p["base_population"]["value"] < 75e6 and p["base_working_age_population"]["value"] < p["base_population"]["value"]
