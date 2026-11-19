"""E6: a suppressed region x activity cell falls back to a labelled zone estimate, then a labelled national estimate."""
import json
import os
import sys

import numpy as np
import pytest
import yaml

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))


def _bench(project):
    with open(os.path.join(project, "data", "processed", "finscope_active_benchmark.json"), encoding="utf-8") as f:
        return json.load(f)


def test_the_zones_are_the_nbs_nine_and_cover_every_region_once():
    z = CFG["zones"]
    assert "nine geographic zones" in z["source"] and z["url"].startswith("https://microdata.nbs.go.tz/")
    assert len(z["regions"]) == 9
    regions = [r for regs in z["regions"].values() for r in regs]
    assert len(regions) == len(set(regions)) == 31
    assert {len(v) for v in z["regions"].values()} == {2, 3, 4, 5, 6}


def test_zone_and_national_cells_follow_the_disclosure_rule(pipeline_run):
    b = _bench(pipeline_run)
    assert len(b["zone_rows"]) == 36 and len(b["national_rows"]) == 4
    for r in b["rows"] + b["zone_rows"] + b["national_rows"]:
        if r.get("suppressed"):
            assert r["respondent_count"] is None and r["strand_distribution_pct"] is None
        else:
            assert r["respondent_count"] >= 10
    # the region rows are unchanged by the fallback (same 42 suppressed cells)
    assert sum(1 for r in b["rows"] if r.get("suppressed")) == 42


def _cell(level, key, activity, n, **kw):
    base = {"activity": activity}
    if n < 10:                                                                     # disclosure rule: no counts, no estimate
        base.update({"suppressed": True, "reason": "base < 10"})
    elif level == "region" and n < 30:                                             # publishable under the disclosure rule, below the region-band minimum
        base.update({"n_businesses": n + 5, "n_with_receipts": n, "suppressed": False, "withheld": True, "withheld_reason": "fewer than 30 businesses with receipts"})
    else:
        base.update({"n_businesses": n + 5, "n_with_receipts": n})
        base.update({"p25_tzs": 2e6, "median_tzs": 5e6, "p75_tzs": 12e6, "tax_at_p25_tzs": 0.0, "tax_at_median_tzs": 100000.0, "tax_at_p75_tzs": 480000.0, "share_below_4m_pct": 40.0, "share_4m_to_11m_pct": 40.0,
                     "share_above_11m_pct": 20.0, "low_precision": n < 30, "suppressed": False})
    if level == "region":
        base["region"] = key
    if level == "zone":
        base["zone"] = key
    return base


def _synthetic_pipeline(tmp_path, region_n, zone_n, national_n=500):
    from tdj_lib.pipeline_data import PipelineData
    doc = {"label": "HBS 2017/18, CPI-uprated to 2024, last-month receipts annualised by months operated; owners with receipts", "coverage": ["Farmers and fishers are not covered", "Zanzibar is not covered"],
           "min_businesses_with_receipts_region_cell": 30,
           "region_activity": [_cell("region", "Morogoro", "Service providers", region_n)], "zone_activity": [_cell("zone", "Eastern", "Service providers", zone_n)],
           "national_activity": [_cell("national", None, "Service providers", national_n)]}
    import json
    (tmp_path / "mzani_turnover.json").write_text(json.dumps(doc), encoding="utf-8")
    return PipelineData(str(tmp_path))


def _adapter():
    dash = os.path.join(ROOT, "dashboard")
    if dash not in sys.path:
        sys.path.insert(0, dash)
    from tdj_lib import benchmark_adapters
    return benchmark_adapters


def test_the_region_cell_is_used_only_with_at_least_30_businesses_with_receipts(tmp_path):
    ba = _adapter()
    ok = ba.mzani_adapter("Morogoro", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=30, zone_n=80))
    assert ok.available and ok.level == "region" and ok.geography == "Morogoro" and ok.level_label == "" and ok.sample_size == 30 and not ok.low_precision
    assert ok.median_tzs == 5e6 and ok.tax_median_tzs == 100000.0 and ok.tax_p25_tzs == 0.0


def test_a_thin_region_falls_back_to_the_zone_then_to_the_national_cell(tmp_path):
    ba = _adapter()
    z = ba.mzani_adapter("Morogoro", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=29, zone_n=80))
    assert z.level == "zone" and z.geography == "Eastern zone" and z.level_label.startswith("Zone estimate:") and "fewer than 30 businesses" in z.level_label and z.sample_size == 80
    n = ba.mzani_adapter("Morogoro", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=12, zone_n=9, national_n=500))
    assert n.level == "national" and n.geography == "Mainland Tanzania" and n.level_label.startswith("National (Mainland) estimate:") and n.sample_size == 500
    none = ba.mzani_adapter("Morogoro", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=12, zone_n=9, national_n=7))
    assert not none.available and "Insufficient data" in none.note


def test_a_region_outside_the_survey_is_labelled_not_covered_and_the_mzani_fallback_is_by_zone(tmp_path):
    ba = _adapter()
    res = ba.mzani_adapter("Kaskazini Unguja", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=30, zone_n=80))
    assert res.available and res.level in ("zone", "national") and res.level_label
    assert "not covered" in res.level_label or res.level == "zone"


def test_the_result_carries_the_hbs_label_the_coverage_and_no_finscope_strand_bridge(tmp_path):
    ba = _adapter()
    res = ba.mzani_adapter("Morogoro", "Service providers", pipeline=_synthetic_pipeline(tmp_path, region_n=60, zone_n=80))
    assert res.source_label == "HBS 2017/18, CPI-uprated to 2024, last-month receipts annualised by months operated; owners with receipts"
    assert any("Farmers and fishers" in c for c in res.coverage) and any("Zanzibar" in c for c in res.coverage)
    for gone in ("strand_distribution", "composite_score", "presumptive_category", "presumptive_evidence_tier"):
        assert not hasattr(res, gone), gone
    assert not hasattr(ba, "PRESUMPTIVE_BANDS") and not hasattr(ba, "finscope_adapter")
    page = open(os.path.join(ROOT, "dashboard", "pages", "3_Active.py"), encoding="utf-8").read()
    assert "strand" not in page.lower() and "composite" not in page.lower() and "mzani_adapter" in page


def test_the_published_mzani_file_follows_the_minimum_sizes_and_the_schedule():
    with open(paths.MZANI_TURNOVER, encoding="utf-8") as f:
        m = json.load(f)
    assert m["min_businesses_with_receipts_region_cell"] == 30 and "HBS 2017/18" in m["label"]
    assert any("Farmers and fishers" in c for c in m["coverage"]) and any("Zanzibar" in c for c in m["coverage"])
    assert {r["activity"] for r in m["national_activity"]} == {"Traders - agricultural products (fishers cannot be separated)", "Traders - non-agricultural", "Service providers"}
    for r in m["region_activity"]:
        if r["suppressed"]:                                                         # under 10: no counts, no estimate (the disclosure rule)
            assert r["reason"] == "base < 10" and "n_with_receipts" not in r and "median_tzs" not in r, r
        elif r.get("withheld"):                                                     # 10-29 businesses with receipts: counted, but no region band
            assert 10 <= r["n_with_receipts"] < 30 and "median_tzs" not in r, r
        else:
            assert r["n_with_receipts"] >= 30 and "median_tzs" in r, r
    for r in m["zone_activity"] + m["national_activity"]:
        assert r["suppressed"] == ("n_with_receipts" not in r), r
        assert r["suppressed"] or r["n_with_receipts"] >= 10, r
    import statutory_tax as st
    sch = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))["assumptions"]["tax.presumptive_schedule"]["value"]
    for r in [r for r in m["zone_activity"] if not r["suppressed"]][:6]:
        for q in ("p25", "median", "p75"):
            tax = r["tax_at_%s_tzs" % q]
            x = r["%s_tzs" % q]
            if x > sch["threshold_turnover"]:
                assert tax is None
            else:
                assert tax == pytest.approx(float(st.presumptive(np.array([x]))[0]))
        assert r["p25_tzs"] <= r["median_tzs"] <= r["p75_tzs"]
        assert r["share_below_4m_pct"] + r["share_4m_to_11m_pct"] + r["share_above_11m_pct"] == pytest.approx(100.0, abs=1e-6)
