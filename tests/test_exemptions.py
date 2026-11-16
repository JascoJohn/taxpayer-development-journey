"""W2: the MoF exemption rates are read by header label; the funnel uses the DOMESTIC rate, the total is the sensitivity."""
import json
import os
import sys

import pytest

from conftest import requires_documents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths  # noqa: E402,F401
import tax_exemptions as tx  # noqa: E402


@requires_documents
def test_domestic_and_total_are_read_correctly():
    r = tx.extract(paths.TAX_EXEMPTIONS_XLSX)
    c = r["components"]
    assert c["domestic"]["exemption_million_tzs"]["value"] == pytest.approx(79429.6895365685)
    assert c["domestic"]["gross_collection_million_tzs"]["value"] == pytest.approx(3947853.54)
    assert c["domestic"]["rate_pct"] == pytest.approx(2.01197, abs=1e-5)
    assert c["total"]["rate_pct"] == pytest.approx(8.76587, abs=1e-5)
    assert round(c["total"]["rate_pct"], 2) == 8.77                   # the former typed constant
    assert c["customs_excise"]["rate_pct"] == pytest.approx(18.90327, abs=1e-5)
    assert r["prior_year_same_quarter"]["total_rate_pct"] == pytest.approx(7.54483, abs=1e-5)
    # every value carries its source cell
    assert (c["domestic"]["workbook_ratio"]["sheet"], c["domestic"]["workbook_ratio"]["cell"]) == ("Summary", "H6")
    assert c["total"]["workbook_ratio"]["cell"] == "H10"
    assert r["funnel_rate"] == "domestic" and r["sensitivity_rate"] == "total"
    # the rate is recomputed from the two amounts and agrees with the workbook's own ratio
    for part in c.values():
        assert part["rate_pct"] == pytest.approx(part["rate_pct_recomputed"], abs=1e-9)


def test_cells_are_located_by_label_not_by_position(tmp_path):
    """Same table, shifted down two rows and right three columns, with an extra title row: the same values come out."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "A title row that shifts everything"
    dr, dc = 3, 3

    def put(r, c, v):
        ws.cell(r + dr, c + dc, v)
    put(2, 3, "Exemption and Relief (Million)"); put(2, 5, "Departmental Actual Gross Collection (Million)")
    put(2, 7, "Exemption as % of Actual Gross collection.")
    for col, per in ((3, "2022/23 - Q1"), (4, "2023/24 - Q1"), (5, "2022/23 - Q1"), (6, "2023/24 - Q1"), (7, "2022/23 - Q1"), (8, "2023/24 - Q1")):
        put(3, col, per)
    data = {  # row: (label A, label B, exemption22, exemption23, collection22, collection23)
        4: ("Domestic Reliefs", "Large Taxpayers (LTD)", 10, 20, 1000, 1000),
        5: (None, "Other Taxpayers (DRD)", 10, 20, 1000, 1000),
        6: ("Subtotal", None, 20, 40, 2000, 2000),
        7: ("Customs and Excise", "Mainland", 30, 60, 300, 300),
        8: (None, "Zanzibar", 0, 0, 100, 100),
        9: ("Subtotal", None, 30, 60, 400, 400),
        10: ("Total", None, 50, 100, 2400, 2400),
    }
    for r, (a, b, e22, e23, c22, c23) in data.items():
        if a: put(r, 1, a)
        if b: put(r, 2, b)
        put(r, 3, e22); put(r, 4, e23); put(r, 5, c22); put(r, 6, c23)
        put(r, 7, e22 / c22); put(r, 8, e23 / c23)
    path = tmp_path / "shifted.xlsx"
    wb.save(path)
    r = tx.extract(str(path))
    assert r["components"]["domestic"]["rate_pct"] == pytest.approx(2.0)
    assert r["components"]["customs_excise"]["rate_pct"] == pytest.approx(15.0)
    assert r["components"]["total"]["rate_pct"] == pytest.approx(100 / 2400 * 100)
    assert r["components"]["domestic"]["workbook_ratio"]["cell"] == "K9"          # moved: H6 + (3 cols, 3 rows)
    assert r["prior_year_same_quarter"]["total_rate_pct"] == pytest.approx(50 / 2400 * 100)


def test_funnel_uses_the_domestic_rate_and_keeps_the_total_as_sensitivity():
    with open(paths.TAX_EXEMPTION_RATE, encoding="utf-8") as f:
        ex = json.load(f)
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    funnel = model["compliance_funnel"]
    levels = funnel["funnel_levels"]
    filer = levels[5]["count"]
    pay = next(l for l in levels if l["level"].startswith("Pays in full"))
    assert pay["dropout_from_previous"] == round(filer * ex["funnel_rate_pct"] / 100.0)
    assert pay["count"] == filer - pay["dropout_from_previous"]
    assert "DOMESTIC" in pay["source"] and "2023/24 - Q1" in pay["source"]
    sens = funnel["payment_stage_sensitivity"]
    assert sens["exemption_pct_of_collection"] == pytest.approx(ex["sensitivity_rate_pct"])
    assert sens["dropout_from_previous"] == round(filer * ex["sensitivity_rate_pct"] / 100.0)
    assert sens["primary_case"]["basis"] == "domestic"
    assert model["base_parameters"]["exemption_pct_of_collection"] == pytest.approx(ex["components"]["domestic"]["rate_pct"])
    assert model["base_parameters"]["exemption_pct_of_collection"] != pytest.approx(8.77)


def test_no_typed_constant_remains():
    with open(os.path.join(ROOT, "src", "04_models", "economic_model.py"), encoding="utf-8") as f:
        text = f.read()
    assert 'params["exemption_pct_of_collection"] = 8.77' not in text
