"""F5: documentation, licence, citation, the final claims map, and no absolute paths in code or tests."""
import csv
import os
import re

import pytest
import yaml

from conftest import ROOT


def _read(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8-sig") as f:
        return f.read()


def test_no_absolute_paths_in_code_tests_and_config():
    pat = re.compile(r"(?<![A-Za-z])[A-Za-z]:\\\\|(?<![A-Za-z:/])[A-Za-z]:/(?!/)[A-Za-z]|/Users/|/home/[a-z]")
    scanned = 0
    for top in ("src", "tests", "dashboard", "environment"):
        for dirpath, _, files in os.walk(os.path.join(ROOT, top)):
            if "__pycache__" in dirpath or "assets" in dirpath:
                continue
            for f in files:
                if f.endswith((".py", ".yaml", ".yml", ".txt", ".ini", ".toml", ".cfg")):
                    text = open(os.path.join(dirpath, f), encoding="utf-8", errors="ignore").read()
                    scanned += 1
                    hits = [m.group(0) for m in pat.finditer(text) if "://" not in text[max(0, m.start() - 1):m.end() + 2]]
                    if f == "test_docs_and_portability.py":
                        continue
                    assert not hits, (top, f, hits[:3])
    for f in ("run_all.py", "config.yaml", "pytest.ini"):
        text = _read(f)
        assert not pat.findall(text.replace("://", "")), f
    assert scanned > 40


def test_readme_licence_citation_and_the_folder_readmes():
    readme = _read("README.md")
    for needle in ("The Taxpayer Development Journey — A Behavioral Lifecycle Architecture for Tax Compliance: Evidence from Tanzania", "--from-raw", "--from-processed", "--fetch", "--screenshots", "--clean", "COMPUTED", "MODELLED", "CITED",
                   "How to obtain the raw data", "CC BY 4.0", "CITATION.cff", "requirements.txt", "Python 3.14", "docs/claims_map.csv", "fig_5_1_modelled_compliance"):
        assert needle in readme, needle
    lic = _read("LICENSE")
    assert lic.startswith("MIT License") and "CC BY 4.0" in lic and "Jasco John" in lic and "Ardhi" not in lic
    cff = yaml.safe_load(_read("CITATION.cff"))
    assert cff["cff-version"] == "1.2.0" and cff["authors"][0]["family-names"] == "John" and cff["authors"][0]["given-names"] == "Jasco" and "affiliation" not in cff["authors"][0]
    assert cff["authors"][0]["orcid"] == "https://orcid.org/0009-0007-3630-7943" and cff["license"] == "MIT"
    proc = _read("data/processed/README.md")
    for f in os.listdir(os.path.join(ROOT, "data", "processed")):
        if not f.startswith("README"):
            assert "`%s`" % f in proc, f


def test_the_final_claims_map_has_the_agreed_columns_and_every_claim():
    with open(os.path.join(ROOT, "docs", "claims_map.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == ["claim_id", "location", "current value", "type", "label", "source script", "output file", "status"]
    ids = [r["claim_id"] for r in rows]
    assert ids == ["C%03d" % i for i in range(1, 111)]          # C080: the computed half of the informality claim C032 (split in Editing Pass 1); C081-C098: Pass 6B-1; C099-C108: Pass 6B-2; C109-C110: Pass 6B-3
    assert {r["type"] for r in rows} == {"COMPUTED", "MODELLED", "CITED", "n/a"}                  # the type column holds exactly these four values; the detail is in the label column
    assert all(r["label"] and r["status"] for r in rows)
    by = {r["claim_id"]: r for r in rows}
    assert by["C079"]["status"] == "RETIRED" and "digital twin was retired" in by["C079"]["current value"] and "digital_twin_v0" in by["C079"]["output file"]       # Pass 6B-1
    assert by["C081"]["status"].startswith("REPLACED") and "3.23x" in by["C081"]["current value"]                                                    # the 3.23x row now has an ID and its replacement
    assert all(by["C%03d" % i]["status"].startswith("NEW") for i in range(82, 99)) and all(by["C%03d" % i]["label"] in ("COMPUTED", "MODELLED", "CITED") for i in range(81, 99))
    assert "BLOCKED" not in {r["status"] for r in rows}
    assert not os.path.exists(os.path.join(ROOT, "docs", "claims_map_draft.csv"))                 # the draft is kept in _archive


def test_the_publishing_checklist_ticks_what_is_done_and_adds_what_is_new():
    t = _read("docs/publishing_checklist.md")
    assert "- [x]" in t and "- [ ]" in t
    for needle in ("ORCID", "Playwright", "claims_map.csv", "Editing Pass 1"):
        assert needle in t, needle
    assert "report_sections" not in _read("docs/known_issues.md").split("## Open")[0]


def test_requirements_list_the_figure_and_document_packages():
    req = _read("environment/requirements.txt")
    for pkg in ("matplotlib==", "PyMuPDF==", "PyYAML==", "pytest==", "streamlit==", "pyreadstat=="):
        assert pkg in req, pkg
    assert "playwright==" in _read("environment/requirements-screenshots.txt")


def test_the_dashboard_text_follows_the_any_tax_authority_rule():
    """Editing Pass 1b (R2): displayed text says 'the tax authority'; 'TRA' stays only as a data source or a named TRA data holding (the keep-list below)."""
    keep = ("live TRA or FinScope data", "published TRA, NBS", "Vehicle + rental (TRA-owned)", "TRA-administered vehicle and rental records", "calibrated to TRA's registration trend")
    dash = os.path.join(ROOT, "dashboard")
    found = []
    for base, _, files in os.walk(dash):
        for f in files:
            if f.endswith(".py"):
                for n, line in enumerate(open(os.path.join(base, f), encoding="utf-8"), 1):
                    s = line.strip()
                    if s.startswith("#") or not re.search(r"\bTRA\b", s):
                        continue
                    if not any(k in s for k in keep):
                        found.append("%s:%d %s" % (f, n, s[:90]))
    # module docstrings / adapter notes that talk about future TRA data feeds are allowed (data sources); displayed strings are not
    found = [x for x in found if not x.startswith(("benchmark_adapters.py", "__init__.py"))]
    assert not found, found
