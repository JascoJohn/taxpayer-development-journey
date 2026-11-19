"""Shared helpers: every test works on a throw-away copy of the project, never on the real outputs."""
import hashlib
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED_DIRS = ["outputs/stats", "outputs/tables", "outputs/figures", "data/interim", "data/processed"]

# Restricted raw data (not redistributed: NBS and FSDT terms, Afrobarometer form, MoF workbook; see docs/data_terms.md and data/raw/SOURCES.csv). Tests that need them skip with a clear
# message when they are absent; tests that need only published files (the tracked outputs, data/processed, the World Bank snapshots) always run.
RAW_FILES = {
    "FinScope Tanzania 2023 respondent file": "data/raw/finscope/FinScope.csv",
    "FinScope Tanzania 2023 data map": "data/raw/finscope/FinScope Datamap.xlsx",
    "ILFS 2024 microdata": "data/raw/ilfs/ILFS2024-URT-FINAL - Anonymized.sav",
    "Census 2022 10% sample": "data/raw/census/TPHC2022_TenPercent_DEMOGRAPHICS.sav",
    "Afrobarometer Round 8 Tanzania": "data/raw/afrobarometer/afrobarometer_release-data_tan_r8_en_2021-06-10.sav",
    "HBS 2017/18 individual file": "data/raw/hbs_2017_18/HBS_2017-18_Final_Individual_Data.dta",
    "HBS 2017/18 consumption aggregate": "data/raw/hbs_2017_18/HBS_2017-18_Consumption_Aggregate.dta",
    "HBS 2017/18 Form I S10C1": "data/raw/hbs_2017_18/Other_Sections_of_Form_I/S10C1.dta",
    "TRA collections workbook FY2024/25": "data/raw/tra/TAX_COLLECTION_FOR_THE_FINANCIAL_YEAR_2024-25.xlsx",
}
RAW_DOCUMENTS = ["data/raw/nbs", "data/raw/tra", "data/raw/bot", "data/raw/tcra", "data/raw/tax_exemptions"]


def missing_raw():
    """Names of the restricted raw files that are not on disk (empty when everything is present)."""
    return [name for name, rel in RAW_FILES.items() if not os.path.exists(os.path.join(ROOT, *rel.split("/")))]


def raw_documents_present():
    return all(os.path.isdir(os.path.join(ROOT, *d.split("/"))) and os.listdir(os.path.join(ROOT, *d.split("/"))) for d in RAW_DOCUMENTS)


# Timeout of one full `run_all.py` in a throw-away copy. Raised from 900 s (run_all helper) and 1,800 s (shared pipeline run) to 2,400 s in Pass 6B-1: the pipeline now also reads the HBS 2017/18
# microdata, computes the reach scenarios and the three income bases of Table 5.1, and the baseline suite on `main` already lost one test (test_idempotency::test_no_timestamps_in_data_outputs) to
# the 900 s limit on this machine. The limit only guards against a hang; it does not change what is tested.
PIPELINE_TIMEOUT_S = 2400

SKIP_RAW_REASON = "restricted raw data not present (%s): see README.md, 'How to obtain the raw data'"
requires_raw = pytest.mark.skipif(bool(missing_raw()), reason=SKIP_RAW_REASON % ", ".join(missing_raw()))
requires_documents = pytest.mark.skipif(not raw_documents_present(), reason="the saved TRA / NBS / BoT / TCRA / MoF documents are not present (data/raw is not redistributed): see README.md, 'How to obtain the raw data'")


def skip_without_raw():
    if missing_raw():
        pytest.skip(SKIP_RAW_REASON % ", ".join(missing_raw()))


def _copy_project(dst):
    os.makedirs(dst, exist_ok=True)
    for name in ("run_all.py", "config.yaml"):
        shutil.copy2(os.path.join(ROOT, name), os.path.join(dst, name))
    shutil.copytree(os.path.join(ROOT, "src"), os.path.join(dst, "src"),
                    ignore=shutil.ignore_patterns("__pycache__", "imported"))
    os.makedirs(os.path.join(dst, "data", "raw", "finscope"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "data", "raw", "finscope", "FinScope.csv"), os.path.join(dst, "data", "raw", "finscope"))
    shutil.copy2(os.path.join(ROOT, "data", "raw", "finscope", "FinScope Datamap.xlsx"), os.path.join(dst, "data", "raw", "finscope"))
    # the small MoF workbook is copied; the large census and ILFS microdata are NOT copied: the copied config.yaml points at
    # the originals by absolute path (paths.resolve accepts absolute paths); they are only read.
    xl_dir = os.path.join(ROOT, "data", "raw", "tax_exemptions")
    os.makedirs(os.path.join(dst, "data", "raw", "tax_exemptions"), exist_ok=True)
    for f in os.listdir(xl_dir):
        shutil.copy2(os.path.join(xl_dir, f), os.path.join(dst, "data", "raw", "tax_exemptions"))
    wb_dir = os.path.join(ROOT, "data", "raw", "worldbank")                  # small, tracked World Bank snapshots
    shutil.copytree(wb_dir, os.path.join(dst, "data", "raw", "worldbank"))
    cfg_path = os.path.join(dst, "config.yaml")
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = fh.read()
    for rel in ("data/raw/census/TPHC2022_TenPercent_DEMOGRAPHICS.sav", "data/raw/ilfs/ILFS2024-URT-FINAL - Anonymized.sav",
                "data/raw/afrobarometer/afrobarometer_release-data_tan_r8_en_2021-06-10.sav",
                "data/raw/hbs_2017_18/HBS_2017-18_Final_Individual_Data.dta", "data/raw/hbs_2017_18/HBS_2017-18_Consumption_Aggregate.dta", "data/raw/hbs_2017_18/Other_Sections_of_Form_I/S10C1.dta",
                "data/raw/tra/TAX_COLLECTION_FOR_THE_FINANCIAL_YEAR_2024-25.xlsx"):
        assert rel in cfg, rel
        cfg = cfg.replace(rel, os.path.join(ROOT, *rel.split("/")).replace(os.sep, "/"))
    # the targeting model is run with a lighter cross-validation in the tests (same code, seeds and data; fewer repeats, a shorter
    # C grid and fewer boosting rounds) so that a full pipeline run stays within a few minutes
    for pat, repl in ((r"cv_repeats: 3", "cv_repeats: 1"), (r"(?m)^    c_grid: \[[^\]]*\]", "    c_grid: [0.003, 0.03]"),
                      (r"(?m)^  variants_c_grid: \[[^\]]*\]", "  variants_c_grid: [0.01, 1.0]"), (r"max_iter: 200,", "max_iter: 40,"),
                      (r"(?m)^  n_agents: 100000 ", "  n_agents: 20000 "), (r"(?m)^  n_draws: 10000$", "  n_draws: 2000")):
        cfg, n = re.subn(pat, repl, cfg)
        assert n == 1, pat
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(cfg)
    os.makedirs(os.path.join(dst, "docs"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "docs", "interventions.yaml"), os.path.join(dst, "docs"))              # the authored interventions (a tracked input of the register)
    for d in GENERATED_DIRS:
        os.makedirs(os.path.join(dst, d), exist_ok=True)


@pytest.fixture(scope="session")
def pipeline_run(tmp_path_factory):
    """ONE full `run_all.py --clean` in a throw-away copy, shared (read-only) by the tests that inspect the published outputs.
    (Development shortcut: TDJ_TEST_PROJECT=<folder with finished outputs> inspects that folder instead of running the pipeline.)"""
    existing = os.environ.get("TDJ_TEST_PROJECT")
    if existing:
        return existing
    skip_without_raw()
    dst = str(tmp_path_factory.mktemp("shared") / "proj")
    _copy_project(dst)
    r = subprocess.run([sys.executable, os.path.join(dst, "run_all.py"), "--clean"], cwd=os.path.dirname(dst), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1"), timeout=PIPELINE_TIMEOUT_S)
    assert r.returncode == 0, r.stderr[-3000:]
    return dst


@pytest.fixture
def project(tmp_path):
    skip_without_raw()
    dst = str(tmp_path / "proj")
    _copy_project(dst)
    return dst


def run_all(project_dir, *args, cwd=None):
    """Run run_all.py of the copied project in a subprocess (working directory is NOT the project)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return subprocess.run([sys.executable, os.path.join(project_dir, "run_all.py"), *args],
                          cwd=cwd or os.path.dirname(project_dir), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=PIPELINE_TIMEOUT_S)


def snapshot(project_dir, exclude=("run_meta.json",), only=None):
    """{relative path: sha256} of every file in the generated folders."""
    out = {}
    for d in GENERATED_DIRS:
        base = os.path.join(project_dir, d)
        for r, _, files in os.walk(base):
            for f in files:
                if f in exclude or (only and f not in only):
                    continue
                p = os.path.join(r, f)
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, project_dir).replace(os.sep, "/")] = hashlib.sha256(fh.read()).hexdigest()
    return out
