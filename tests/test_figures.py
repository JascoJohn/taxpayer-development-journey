"""F4: the figure scripts (src/06_figures) read only published outputs, write PNG and SVG deterministically, and bake no figure number into an image."""
import hashlib
import importlib
import os
import re
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401

FIG_SRC = os.path.join(ROOT, "src", "06_figures")
EXPECTED = ["fig_5_1_modelled_compliance", "fig_5_2_reach_scenarios", "fig_5_3_table40_roi_by_stage", "fig_5_4_tornado_central", "fig_a1_tin_by_segment", "fig_a2_tax_morale_components",
            "fig_a3_targeting_deciles", "fig_a4_targeting_variants", "fig_a5_macro_gap"]


def test_one_script_per_figure_and_a_runner():
    scripts = sorted(f[:-3] for f in os.listdir(FIG_SRC) if f.startswith("fig_") and f.endswith(".py"))
    assert scripts == sorted(EXPECTED)
    assert os.path.exists(os.path.join(FIG_SRC, "run_figures.py")) and os.path.exists(os.path.join(FIG_SRC, "capture_dashboard.py"))
    run_all = open(os.path.join(ROOT, "run_all.py"), encoding="utf-8").read()
    assert "run_figures.run_figures()" in run_all and "--screenshots" in run_all and "capture_dashboard" in run_all


def _drawn_strings(src):
    """String constants passed to the calls that draw text (text, set_title, labels, legend entries, annotate)."""
    import ast
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if fname in ("text", "set_title", "set_xlabel", "set_ylabel", "annotate", "legend", "suptitle", "title", "set_xticklabels", "set_yticklabels", "plot", "bar", "barh", "errorbar", "axhline", "label_bars"):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        out.append(sub.value)
    return out


def test_the_scripts_read_no_raw_data_and_draw_no_figure_number():
    for name in EXPECTED:
        src = open(os.path.join(FIG_SRC, name + ".py"), encoding="utf-8").read()
        assert "data/raw" not in src and "ILFS_SAV" not in src and "FINSCOPE_CSV" not in src, name
        assert not [t for t in _drawn_strings(src) if re.search(r"(Figure|Fig\.?)\s*\d", t)], name           # the report numbers its figures; no number is baked into an image
        assert "plt.title(" not in src and "suptitle(" not in src, name


def test_the_journey_graphic_uses_the_configured_names_and_the_original_size():
    from PIL import Image
    src = open(os.path.join(FIG_SRC, "journey_graphic.py"), encoding="utf-8").read()
    assert 'paths.CFG["names"]' in src and "Madarasa" not in src and "Targeting Priority" not in src and "ENgazi" not in src
    png, svg = (os.path.join(ROOT, "outputs", "figures", "journey_graphic" + e) for e in (".png", ".svg"))
    assert Image.open(png).size == (5200, 2028)
    assert 'width="5200px" height="2028px"' in open(svg, encoding="utf-8").read(600)


def test_the_published_figures_exist_as_png_and_svg():
    for name in EXPECTED:
        png, svg = (os.path.join(ROOT, "outputs", "figures", name + e) for e in (".png", ".svg"))
        assert os.path.exists(png) and open(png, "rb").read(8) == b"\x89PNG\r\n\x1a\n", name
        assert os.path.exists(svg) and b"<svg" in open(svg, "rb").read(2000), name


def test_the_figures_are_byte_reproducible(tmp_path, monkeypatch):
    import _style
    monkeypatch.setattr(_style, "FIG_DIR", str(tmp_path / "a"))
    first = {}
    for name in EXPECTED:
        mod = importlib.import_module(name)
        for p in mod.make():
            first[os.path.basename(p)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    monkeypatch.setattr(_style, "FIG_DIR", str(tmp_path / "b"))
    for name in EXPECTED:
        for p in importlib.import_module(name).make():
            assert hashlib.sha256(open(p, "rb").read()).hexdigest() == first[os.path.basename(p)], p
    assert len(first) == 2 * len(EXPECTED)
    # the SVGs carry no timestamp and no figure number as text (the text is drawn as paths)
    for p in os.listdir(tmp_path / "a"):
        if p.endswith(".svg"):
            t = open(tmp_path / "a" / p, encoding="utf-8").read()
            assert "<dc:date>" not in t and not re.search(r">\s*(Figure|Fig\.?)\s*\d", t)


def test_the_cover_poster_and_theory_of_change_use_the_configured_names_and_the_original_sizes():
    from PIL import Image
    for name, size in (("cover_poster", (1054, 1492)), ("theory_of_change", (2837, 1121))):
        src = open(os.path.join(FIG_SRC, name + ".py"), encoding="utf-8").read()
        assert 'paths.CFG["names"]' in src, name
        for old in ("Madarasa", "Targeting Priority", "ENgazi", "Karibu TIN", "The Ladder", "OWNED BY TRA", "VALUE FOR TRA", "Innovation" + " Challenge"):
            assert not [t for t in _drawn_strings(src) if old in t], (name, old)
        png, svg = (os.path.join(ROOT, "outputs", "figures", name + e) for e in (".png", ".svg"))
        assert Image.open(png).size == size
        assert 'width="%dpx" height="%dpx"' % size in open(svg, encoding="utf-8").read(600)


def test_every_number_on_the_cover_poster_is_listed_with_a_claim_that_carries_it():
    """Editing Pass 1b (R8): the poster's numbers come from the CURRENT values of docs/claims_map.csv (POSTER_NUMBERS names the claim ids)."""
    import csv
    sys.path.insert(0, FIG_SRC)
    import cover_poster
    claims = {r["claim_id"]: r["current value"] for r in csv.DictReader(open(os.path.join(ROOT, "docs", "claims_map.csv"), encoding="utf-8-sig"))}
    assert len(cover_poster.POSTER_NUMBERS) >= 12
    for shown, what, ids, label in cover_poster.POSTER_NUMBERS:
        token = re.search(r"\d[\d,.]*\d|\d", shown).group(0)
        listed = re.findall(r"C\d{3}", ids)
        assert listed and all(i in claims for i in listed), (shown, ids)
        assert any(token in claims[i] or token.replace(",", "") in claims[i].replace(",", "") for i in listed), (shown, ids)
        assert label.split(" ")[0] in ("COMPUTED", "MODELLED"), (shown, label)
    assert not any(s == "61.8%" or s == "58.2%" or s == "40.4%" for s, *_ in cover_poster.POSTER_NUMBERS)


def test_the_theory_of_change_uses_the_owner_age_bands():
    """Editing Pass 2 (S1.3): role plus age band per stage."""
    src = open(os.path.join(FIG_SRC, "theory_of_change.py"), encoding="utf-8").read()
    for needle in ("Ages 6\u201315", "Ages 16\u201324", "ages 25\u201344", "ages 25\u201364", "ages 45\u201364", "Ages 65+"):
        assert needle in src, needle
    assert "Birth" not in src and "Age 15" not in src
