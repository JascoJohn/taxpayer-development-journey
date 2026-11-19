"""Pass 6B-1 H7: Figure 1.1 like for like, the taxable-capacity outputs, and the CITED register facts."""
import csv
import json
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import cited_facts  # noqa: E402


def test_figure_1_1_compares_2023_with_2023_and_shows_2024_separately():
    with open(paths.MACRO_INPUTS, encoding="utf-8") as f:
        m = json.load(f)
    b, t = m["benchmark"], m["tanzania"]
    assert b["common_year_all_five"] == 2023 and b["tanzania_same_year_pct"] == pytest.approx(11.68, abs=0.005) and b["benchmark_pct"] == pytest.approx(13.12, abs=0.005)
    assert abs(b["gap_pp"]) == pytest.approx(1.45, abs=0.005) and b["revenue_gap_tzs"] / 1e12 == pytest.approx(2.72, abs=0.005)
    assert t["latest_year"] == 2024 and t["tax_to_gdp_pct"] == pytest.approx(12.26, abs=0.005)
    code = open(os.path.join(ROOT, "src", "06_figures", "fig_a5_macro_gap.py"), encoding="utf-8").read()
    assert 'b["tanzania_same_year_pct"]' in code and "[COMPUTED from CITED World Bank WDI series]" in code and 'marker="D"' in code
    assert 'vals = [t["tax_to_gdp_pct"]]' not in code                                 # the 2024 value is no longer a bar against 2023 peers
    assert os.path.exists(os.path.join(ROOT, "outputs", "figures", "fig_a5_macro_gap.png"))


def test_taxable_capacity_overall_owners_and_owners_with_receipts():
    with open(paths.TAXABLE_CAPACITY_JSON, encoding="utf-8") as f:
        d = json.load(f)
    assert d["all_adults"]["share_above_4m_pct"] == pytest.approx(1.19, abs=0.01) and d["all_adults"]["share_above_11m_pct"] == pytest.approx(0.44, abs=0.01)
    assert d["business_owners"]["share_above_4m_pct"] == pytest.approx(7.4, abs=0.05) and d["business_owners"]["share_above_11m_pct"] == pytest.approx(2.65, abs=0.02)
    assert d["owners_with_receipts_in_the_reference_month"]["share_above_4m_pct"] > d["business_owners"]["share_above_4m_pct"]
    assert set(d["by_stage"]) == {"entry", "active", "enterprise", "workers", "asset", "legacy"} and len(d["by_zone"]) > 0 and "COMPUTED" in d["label"]
    assert any("wage" in n for n in d["notes"]) and any("Zanzibar" in n for n in d["notes"])


def test_taxable_capacity_tables_follow_the_disclosure_rule():
    with open(paths.TAXABLE_CAPACITY_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert {r["group"] for r in rows} >= {"all adults", "business owners", "owners with receipts in the reference month", "entry", "active", "enterprise", "workers", "asset", "legacy"}
    assert all(r["evidence_type"] == "COMPUTED" for r in rows)
    for r in rows:
        base = int(r["n_unweighted"])
        if base >= 10 and r["n_above_unweighted"] != "":
            assert int(r["n_above_unweighted"]) >= 10                               # a numerator under 10 is never written
        if r["n_above_unweighted"] == "" and base >= 10:
            assert r["low_precision"] == "True"                                     # ... and the estimate is flagged
    with open(paths.TAXABLE_CAPACITY_ZONE_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["n_above_unweighted"] != "":
                assert int(r["n_above_unweighted"]) >= 10


def test_cited_facts_are_cited_with_source_and_what_they_do_not_show():
    with open(paths.CITED_FACTS_JSON, encoding="utf-8") as f:
        d = json.load(f)
    f = d["facts"]
    assert f["tra_active_business_tins_fy2023_24"]["value"] == 1851184 and f["tra_dormant_business_tins_fy2023_24"]["value"] == 123993 and f["tra_tin_stock_mainland_fy2023_24"]["value"] == 6272000
    assert all(x["evidence_type"] == "CITED" and x["source"] and x["does_not_show"] for x in f.values())
    assert "Finance Act 2022 s. 106" in f["nin_to_tin_provision"]["source"] and "s. 22(2)" in f["nin_to_tin_provision"]["source"]
    assert "Round 9" in f["afrobarometer_r9_r10_tax_module"]["value"] or "Round 8" in f["afrobarometer_r9_r10_tax_module"]["value"]
    assert "not a count of adult taxpayers" in d["reading"] or "are not counts of adult taxpayers" in d["reading"]
    assert d["derived"]["business_tins_active_plus_dormant_fy2023_24"] == 1851184 + 123993 and d["derived"]["tin_stock_matches_pipeline_series"] in (True, None)
    with open(paths.CITED_FACTS_CSV, encoding="utf-8", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == len(f)


def test_the_cited_stock_equals_the_pipeline_series():
    with open(paths.TRA_REGISTERED_TAXPAYERS_CSV, encoding="utf-8", newline="") as fh:
        used = [float(r["registered_taxpayers"]) for r in csv.DictReader(fh) if r["status"] == "used"]
    assert used[-1] == paths.CFG["cited_facts"]["tra_tin_stock_mainland_fy2023_24"]["value"]
    assert cited_facts.run_cited_facts()["derived"]["tin_stock_matches_pipeline_series"] is True
