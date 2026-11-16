"""--from-processed reproduces the downstream outputs of --from-raw exactly, and fails clearly when inputs are missing."""
import os

from conftest import run_all, snapshot

DOWNSTREAM = {"economic_model.json", "intervention_register.json", "shared_context.json", "assumption_ledger.json"}


def test_from_processed_matches_from_raw(project):
    assert run_all(project, "--clean").returncode == 0
    raw = snapshot(project)
    r = run_all(project, "--from-processed")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "STEP 1: skipped" in r.stdout
    assert "STEP 4: Census" in r.stdout and "skipped (--from-processed): using data/processed/census_age_counts.json" in r.stdout.replace("\\", "/")
    assert "skipped (--from-processed): using data/processed/ilfs_indicators.json" in r.stdout.replace("\\", "/")
    proc = snapshot(project)
    down_raw = {k: v for k, v in raw.items() if os.path.basename(k) in DOWNSTREAM}
    down_proc = {k: v for k, v in proc.items() if os.path.basename(k) in DOWNSTREAM}
    assert len(down_raw) == 4
    assert down_raw == down_proc
    assert raw == proc          # ingestion outputs were left untouched as well


def test_from_processed_names_missing_files(project):
    r = run_all(project, "--from-processed")            # nothing has been generated yet
    assert r.returncode == 2
    assert "finscope_summary.json" in r.stderr and "missing" in r.stderr
    assert "census_age_counts.json" in r.stderr and "ilfs_indicators.json" in r.stderr


def test_clean_cannot_combine_with_from_processed(project):
    r = run_all(project, "--clean", "--from-processed")
    assert r.returncode == 2 and "--clean" in r.stderr


def test_llm_flag_exits_nonzero(project):
    r = run_all(project, "--llm")
    assert r.returncode != 0 and "not used in this project yet" in r.stderr


def test_fetch_is_opt_in():
    """--fetch (World Bank snapshots) is off by default. The flag is parsed here only: the tests never touch the network."""
    import importlib
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    try:
        run_all_module = importlib.import_module("run_all")
    finally:
        sys.path.remove(root)
    assert run_all_module.parse_args([]).fetch is False
    assert run_all_module.parse_args(["--from-processed"]).fetch is False
    assert run_all_module.parse_args(["--fetch"]).fetch is True


def test_clean_never_touches_raw_or_the_authored_interventions(project):
    raw = os.path.join(project, "data", "raw", "finscope", "FinScope.csv")
    frozen = os.path.join(project, "docs", "interventions.yaml")
    sizes = (os.path.getsize(raw), os.path.getsize(frozen))
    assert run_all(project, "--clean").returncode == 0
    assert (os.path.getsize(raw), os.path.getsize(frozen)) == sizes
