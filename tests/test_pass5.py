"""Editing Pass 5: licences, DOI placeholders, the poster, the Zenodo metadata file and the neutral wording of the public files. Read-only."""
import json
import os
import re
import subprocess
import sys

import pytest
import yaml

from conftest import ROOT

TEXT_EXT = (".py", ".md", ".csv", ".json", ".yaml", ".yml", ".txt", ".cff", ".ini", ".toml", ".cfg")


def _text(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8-sig") as f:
        return f.read()


def _public_text_files():
    """The files git would track (text types), without the historical records (diffs, edit logs, changelog)."""
    out = subprocess.run(["git", "ls-files", "-c", "-o", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split("\n")
    skip = ("docs/block_", "docs/edit_pass", "CHANGELOG.md")
    return [f for f in out if f.endswith(TEXT_EXT) and not f.startswith(skip) and os.path.isfile(os.path.join(ROOT, f))]


def test_the_three_licences_are_stated_the_same_way_everywhere():
    readme, lic = _text("README.md"), _text("LICENSE")
    assert lic.startswith("MIT License")
    for t, name in ((readme, "README"), (lic, "LICENSE")):
        assert "CC BY-NC-ND 4.0" in t and "CC BY 4.0" in t, name
    assert "Report and figures: CC BY-NC-ND 4.0" in readme and "Aggregate data: CC BY 4.0" in readme.split("\n")[2]
    assert "CC BY 4.0" in _text("data/processed/README.md") and "CC BY-NC-ND 4.0" in _text("dashboard/README.md")
    assert "## 8. Licences of what is published" in _text("docs/data_terms.md")
    cff = yaml.safe_load(_text("CITATION.cff"))
    assert cff["license"] == "MIT" and cff["version"] == "1.0.0"
    lic_by_type = {r["type"]: r["license"] for r in cff["references"]}
    assert lic_by_type == {"report": "CC-BY-NC-ND-4.0", "dataset": "CC-BY-4.0"}
    assert cff["repository-code"] == "https://github.com/JascoJohn/taxpayer-development-journey" and cff["url"] == "https://taxpayer-development-journey.streamlit.app"


def test_no_doi_placeholder_remains_and_the_three_dois_are_entered():
    found = set()
    for f in _public_text_files():
        if f == "tests/test_pass5.py":
            continue
        t = _text(f)
        for old in ("[Package DOI]", "[Zenodo DOI]", "[Dashboard link]", "[GitHub link]"):
            assert old not in t, (f, old)
        found |= set(re.findall(r"\[(?:Report|Dataset|Code) DOI\]|\[date-released\]", t))
    assert found == set()                                              # version 1.0.0: the three DOIs are entered
    cff = yaml.safe_load(_text("CITATION.cff"))
    assert cff["version"] == "1.0.0" and str(cff["date-released"]) == "2026-11-20" and cff["doi"] == "10.5281/zenodo.24386968"
    assert {i["value"] for i in cff["identifiers"] if i["type"] == "doi"} == {"10.5281/zenodo.24387574", "10.5281/zenodo.24387022", "10.5281/zenodo.24386968"}
    assert cff["preferred-citation"]["type"] == "report" and cff["preferred-citation"]["doi"] == "10.5281/zenodo.24387574"
    readme = _text("README.md")
    for doi in ("10.5281/zenodo.24387574", "10.5281/zenodo.24387022", "10.5281/zenodo.24386968"):
        assert "https://doi.org/" + doi in readme, doi


def test_the_zenodo_metadata_file_describes_the_code_record():
    z = json.loads(_text(".zenodo.json"))
    assert z["title"] == "The Taxpayer Development Journey: Code" and z["upload_type"] == "software" and z["license"] == "MIT"
    assert z["creators"][0]["name"] == "John, Jasco" and z["creators"][0]["orcid"] == "0009-0007-3630-7943"
    assert z["version"] == "1.0.0"
    rel = {(r["identifier"], r["relation"]) for r in z["related_identifiers"]}
    assert ("10.5281/zenodo.24387574", "isSupplementTo") in rel and ("10.5281/zenodo.24387022", "isSupplementedBy") in rel
    assert "10.5281/zenodo.24387574" in z["description"] and "10.5281/zenodo.24387022" in z["description"]


def test_the_poster_has_a_real_qr_code_the_phone_and_the_british_spelling():
    src = _text("src/06_figures/cover_poster.py")
    assert 'DASHBOARD_URL = "https://taxpayer-development-journey.streamlit.app"' in src and "import qrcode" in src and "+255 759 003 950" in src
    assert "MODELLED IMPACT" in src and "MODELED" not in src and "[Dashboard link]" not in src and "QR:" not in src
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=1, border=0)
    q.add_data("https://taxpayer-development-journey.streamlit.app")
    q.make(fit=True)
    assert len(q.get_matrix()) <= 33                                  # large modules: at 3 px each the code scans from the poster
    assert "qrcode==" in _text("environment/requirements.txt")


def test_no_competition_wording_remains_in_the_public_files():
    needles = ["Innovation" + " Challenge", "INNOVATION" + " CHALLENGE", "train" + "novation", "competition" + " objective", "COMPETITION" + " OBJECTIVES"]
    for f in _public_text_files():
        if f.startswith("tests/test_pass5.py"):
            continue
        t = _text(f)
        for n in needles:
            assert n not in t, (f, n)
