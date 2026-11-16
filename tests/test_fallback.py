"""E6: a suppressed region x activity cell falls back to a labelled zone estimate, then a labelled national estimate."""
import json
import os
import sys

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


def test_every_region_cell_has_an_estimate_or_a_labelled_fallback(pipeline_run):
    dash = os.path.join(ROOT, "dashboard")
    sys.path.insert(0, dash)
    from tdj_lib.benchmark_adapters import finscope_adapter, MIN_N_FOR_ANY_ESTIMATE
    from tdj_lib.pipeline_data import PipelineData
    pipe_dir = os.path.join(pipeline_run, "data", "processed")
    pipe = PipelineData(pipe_dir)
    b = _bench(pipeline_run)
    counts = {"region": 0, "zone": 0, "national": 0}
    for row in b["rows"]:
        res = finscope_adapter(row["region"], row["activity"], pipeline=pipe)
        assert res.available, (row["region"], row["activity"])
        counts[res.level] += 1
        if row.get("suppressed"):
            assert res.level in ("zone", "national") and res.level_label, row
            assert res.level_label.startswith("Zone estimate: region cell suppressed, fewer than %d respondents" % MIN_N_FOR_ANY_ESTIMATE) if res.level == "zone" \
                else res.level_label.startswith("National estimate: region and zone cells suppressed, fewer than %d respondents" % MIN_N_FOR_ANY_ESTIMATE)
            assert res.sample_size >= MIN_N_FOR_ANY_ESTIMATE
        else:
            assert res.level == "region" and res.level_label == "" and res.geography == row["region"]
    assert counts == {"region": 82, "zone": 40, "national": 2}
