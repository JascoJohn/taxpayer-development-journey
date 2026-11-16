"""W3: macro inputs from World Bank snapshots: the gap identity, the common benchmark year, and no network without --fetch."""
import csv
import glob
import io
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import macro_inputs as mi  # noqa: E402
import fetch_worldbank as fw  # noqa: E402


@pytest.fixture(scope="module")
def snap():
    series, _ = mi.load_snapshots()
    return series


@pytest.fixture(scope="module")
def result(snap):
    return mi.compute(snap, "TZA", ["GHA", "KEN", "RWA", "UGA"])


def test_gap_identity_holds(result, snap):
    b, t = result["benchmark"], result["tanzania"]
    y = b["year"]
    gdp = snap[mi.GDP_LCU]["TZA"][y]
    expected = (b["benchmark_pct"] - snap[mi.TAX]["TZA"][y]) / 100.0 * gdp
    assert b["revenue_gap_tzs"] == pytest.approx(expected, rel=1e-12)
    assert b["gap_pp"] == pytest.approx(b["benchmark_pct"] - b["tanzania_same_year_pct"], abs=1e-12)
    assert b["revenue_gap_usd"] == pytest.approx(b["revenue_gap_tzs"] / snap[mi.FX]["TZA"][y], rel=1e-12)      # same-year exchange rate
    assert b["gdp_lcu_tzs_that_year"] == snap[mi.GDP_LCU]["TZA"][y]                                              # no FX step in the TZS gap
    assert t["tax_revenue_tzs"] == pytest.approx(t["tax_to_gdp_pct"] / 100.0 * snap[mi.GDP_LCU]["TZA"][t["latest_year"]], rel=1e-12)


def test_expected_values_from_the_snapshots(result):
    t, b = result["tanzania"], result["benchmark"]
    assert t["latest_year"] == 2024 and round(t["tax_to_gdp_pct"], 2) == 12.26
    assert b["year"] == 2023 and b["policy"] == "peer_average"
    assert round(b["benchmark_pct"], 2) == 13.12 and round(b["tanzania_same_year_pct"], 2) == 11.68
    assert 2.6e12 < b["revenue_gap_tzs"] < 2.9e12                                # about TZS 2.7 trillion, not the former 7.29
    assert b["peer_average_pct"] == pytest.approx(sum(p["tax_to_gdp_pct"] for p in b["peers"].values()) / 4, abs=1e-12)


def test_benchmark_year_is_common_to_all_five_countries_and_the_latest(result, snap):
    b = result["benchmark"]
    tax = snap[mi.TAX]
    five = ["TZA", "GHA", "KEN", "RWA", "UGA"]
    y = b["common_year_all_five"]
    assert all(y in tax[c] for c in five)
    later = [yy for yy in tax["TZA"] if yy > y]
    assert all(not all(yy in tax[c] for c in five) for yy in later)             # no later year has all five
    assert b["year"] == y                                                         # peer_average uses it


def test_cited_target_policy_refuses_to_run_without_a_target(snap):
    with pytest.raises(ValueError):
        mi.compute(snap, "TZA", ["GHA", "KEN", "RWA", "UGA"], benchmark_source="cited_target")
    r = mi.compute(snap, "TZA", ["GHA", "KEN", "RWA", "UGA"], "cited_target", 14.0, "test document p. 1")
    assert r["benchmark"]["year"] == 2024 and r["benchmark"]["gap_pp"] == pytest.approx(14.0 - r["tanzania"]["tax_to_gdp_pct"])
    with pytest.raises(ValueError):
        mi.compute(snap, "TZA", ["GHA", "KEN", "RWA", "UGA"], benchmark_source="something_else")


def test_default_policy_in_config_is_peer_average():
    assert paths.MACRO_CFG["benchmark_source"] == "peer_average"
    assert paths.MACRO_CFG["cited_target_pct"] is None


def test_no_network_access_without_fetch(monkeypatch, tmp_path):
    """Reading the snapshots and running the macro step must not touch the network."""
    import socket
    import urllib.request

    def boom(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    r = mi.run_macro_inputs(out_path=str(tmp_path / "m.json"))
    assert r["benchmark"]["year"] == 2023
    import economic_model
    params = economic_model.load_base_params()
    assert params["gdp_usd"] == pytest.approx(r["tanzania"]["gdp_usd"])


def test_only_the_fetch_module_uses_the_network_and_only_under_fetch_flag():
    offenders = []
    for f in glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        if rel.startswith("src/imported/") or rel in ("src/01_ingest/fetch_worldbank.py", "src/06_figures/capture_dashboard.py"):      # the screenshot script only talks to the local dashboard (127.0.0.1)
            continue
        text = open(f, encoding="utf-8", errors="replace").read()
        if re.search(r"^\s*(import|from)\s+(urllib\.request|requests|socket|http\.client)\b", text, flags=re.M):
            offenders.append(rel)
    assert offenders == []
    with open(os.path.join(ROOT, "run_all.py"), encoding="utf-8") as f:
        text = f.read()
    assert text.count("import fetch_worldbank") == 1
    lines = text.splitlines()
    n = next(k for k, l in enumerate(lines) if "import fetch_worldbank" in l)
    indent = len(lines[n]) - len(lines[n].lstrip())
    k = n - 1
    while len(lines[k]) - len(lines[k].lstrip()) >= indent or not lines[k].strip():
        k -= 1
    assert lines[k].strip() == "if args.fetch:"                                  # the only import sits inside `if args.fetch:`


def test_fetch_saves_the_raw_bytes_and_a_manifest_row(monkeypatch, tmp_path):
    body = b'[{"page":1,"pages":1,"per_page":20000,"total":1,"sourceid":"2","lastupdated":"2026-11-11"},[{"countryiso3code":"TZA","date":"2024","value":12.26}]]'

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(fw.urllib.request, "urlopen", lambda req, timeout=None: FakeResp(body))
    monkeypatch.setattr(paths, "WB_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "WB_MANIFEST", str(tmp_path / "MANIFEST.csv"))
    import datetime
    row = fw.fetch_series("GC.TAX.TOTL.GD.ZS", ["TZA"], "1960:2026", today=datetime.date(2026, 11, 12))
    fw.append_manifest(row)
    assert row["file"] == "GC.TAX.TOTL.GD.ZS_2026-11-12.json"
    assert (tmp_path / row["file"]).read_bytes() == body                           # saved unchanged
    import hashlib
    assert row["sha256"] == hashlib.sha256(body).hexdigest() and row["bytes"] == len(body)
    assert "api.worldbank.org/v2/country/TZA/indicator/GC.TAX.TOTL.GD.ZS" in row["url"]
    with open(tmp_path / "MANIFEST.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["sha256"] == row["sha256"] and rows[0]["retrieved_at"]


def test_model_reads_the_macro_file(result):
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    with open(paths.MACRO_INPUTS, encoding="utf-8") as f:
        mfile = json.load(f)
    p = model["base_parameters"]
    assert p["gdp_usd"] == pytest.approx(mfile["tanzania"]["gdp_usd"])
    assert p["tzs_per_usd"] == pytest.approx(mfile["tanzania"]["fx_tzs_per_usd"])
    assert p["tax_to_gdp_current"] == pytest.approx(mfile["tanzania"]["tax_to_gdp_pct"] / 100.0)
    assert p["tax_to_gdp_target"] == pytest.approx(mfile["benchmark"]["benchmark_pct"] / 100.0)
    ctb = model["current_tax_base"]
    assert ctb["revenue_gap_tzs"] == pytest.approx(round(mfile["benchmark"]["revenue_gap_tzs"]), abs=1)
    assert ctb["benchmark_policy"] == "peer_average" and ctb["benchmark_year"] == 2023
    # none of the old typed constants is left in the code
    code = open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8").read()
    for old in ("78_844_405_385", '"tax_to_gdp_target":    0.165', '"tzs_per_usd":          2_500', '"tax_to_gdp_current":   0.128'):
        assert old not in code
