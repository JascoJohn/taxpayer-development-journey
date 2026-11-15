"""W2 - tax exemption and relief rates from the Ministry of Finance workbook.

Reads data/raw/tax_exemptions/<MoF workbook>.XLSX (sheet 'Summary') with openpyxl. Cells are located by their
header labels and row labels, never by fixed row or column numbers:

  * measure groups (header row): 'Exemption and Relief (Million)', 'Departmental Actual Gross Collection (Million)',
    'Exemption as % of Actual Gross collection.'
  * periods (row below the groups): '2023/24 - Q1', '2022/23 - Q1'
  * row blocks (label column found by its 'Domestic Reliefs' cell): 'Domestic Reliefs', 'Customs and Excise', 'Total';
    each block's own 'Subtotal' row.

Extracted for Q1 2023/24 (July-September 2023; ONE QUARTER, not a full year): the total rate, the domestic rate and the
customs/excise rate, each with the exemption and collection amounts (million TZS) and the workbook's own ratio;
plus the workbook's own Q1 2022/23 total for context. Every value carries its source sheet and cell reference.
The rate is recomputed from the two amounts and compared with the workbook's own ratio cell.

Output: outputs/stats/tax_exemption_rate.json
"""

import json
import os
import re
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

SHEET = "Summary"
PERIOD = "2023/24 - Q1"
PERIOD_PRIOR = "2022/23 - Q1"
GROUP_LABELS = {
    "exemption": "exemption and relief",
    "collection": "actual gross collection",
    "rate": "exemption as % of actual gross collection",
}
BLOCKS = {"domestic": "domestic reliefs", "customs_excise": "customs and excise", "total": "total"}
QUARTER_NOTE = ("Single quarter (Q1 2023/24 = July-September 2023), not an annual rate. The total is dominated by "
                "customs and excise; domestic reliefs are the part that applies to the domestic compliance funnel.")


def _norm(v):
    return re.sub(r"\s+", " ", str(v)).strip().lower() if v is not None else ""


def _locate(ws):
    """Finds the (column, row) of every needed cell by labels. Returns (cols, rows, header_rows)."""
    # header rows: the row holding the measure-group labels, and the row below it holding the periods
    group_row = None
    for row in ws.iter_rows():
        labels = {_norm(c.value) for c in row if c.value is not None}
        if any(g in lbl for lbl in labels for g in GROUP_LABELS.values()):
            group_row = row[0].row
            break
    if group_row is None:
        raise ValueError("measure-group header row not found on sheet %s" % SHEET)
    period_row = group_row + 1

    # a measure group spans from its own cell to the next group label (merged cells keep only the first value)
    group_by_col, current = {}, None
    for c in ws[group_row]:
        lbl = _norm(c.value)
        if lbl:
            # the rate label contains the collection label, so test the most specific label first
            current = next((k for k in ("rate", "exemption", "collection") if GROUP_LABELS[k] in lbl), None)
        if current:
            group_by_col[c.column] = current
    cols = {}
    for c in ws[period_row]:
        per = _norm(c.value)
        g = group_by_col.get(c.column)
        if g and per:
            cols[(g, per)] = c.column

    # label columns: the column holding the 'Domestic Reliefs' block label, and the one next to it (sub-lines)
    label_col = None
    for row in ws.iter_rows(min_row=period_row + 1):
        for c in row:
            if _norm(c.value) == BLOCKS["domestic"]:
                label_col = c.column
                break
        if label_col:
            break
    if label_col is None:
        raise ValueError("block label %r not found on sheet %s" % (BLOCKS["domestic"], SHEET))

    # rows: block label (carried down), 'Subtotal' belongs to the block above it
    rows, block = {}, None
    for r in range(period_row + 1, ws.max_row + 1):
        a, b = _norm(ws.cell(r, label_col).value), _norm(ws.cell(r, label_col + 1).value)
        if a in ("subtotal",):
            if block:
                rows[block + ":subtotal"] = r
        elif a == "total":
            rows["total"] = r
        elif a:
            block = a
        if b:
            rows[(block or "") + ":" + b] = r
    return cols, rows, (group_row, period_row)


def _cell(ws, rows, cols, row_key, measure, period):
    col = cols[(measure, _norm(period))]
    r = rows[row_key]
    c = ws.cell(r, col)
    return {"value": float(c.value), "sheet": ws.title, "cell": c.coordinate}


def extract(xlsx_path):
    from openpyxl import load_workbook
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")           # openpyxl: unparseable header/footer in this workbook
        wb = load_workbook(xlsx_path, data_only=True)
    ws = wb[SHEET]
    cols, rows, header_rows = _locate(ws)
    keyrow = {"domestic": "domestic reliefs:subtotal", "customs_excise": "customs and excise:subtotal", "total": "total"}
    parts = {}
    for name, rk in keyrow.items():
        ex = _cell(ws, rows, cols, rk, "exemption", PERIOD)
        co = _cell(ws, rows, cols, rk, "collection", PERIOD)
        rt = _cell(ws, rows, cols, rk, "rate", PERIOD)
        recomputed = ex["value"] / co["value"]
        if abs(recomputed - rt["value"]) > 1e-9:
            raise ValueError("%s: workbook ratio %.10f differs from exemption/collection %.10f" % (name, rt["value"], recomputed))
        parts[name] = {
            "exemption_million_tzs": ex, "gross_collection_million_tzs": co, "workbook_ratio": rt,
            "rate_pct": rt["value"] * 100.0, "rate_pct_recomputed": recomputed * 100.0,
        }
    # sub-lines of the domestic block, for context
    sub = {}
    for label, rk in (("large_taxpayers_ltd", "domestic reliefs:large taxpayers (ltd)"), ("other_taxpayers_drd", "domestic reliefs:other taxpayers (drd)"),
                      ("mainland", "customs and excise:mainland"), ("zanzibar", "customs and excise:zanzibar")):
        if rk in rows:
            sub[label] = {"rate_pct": _cell(ws, rows, cols, rk, "rate", PERIOD)["value"] * 100.0,
                          "cell": _cell(ws, rows, cols, rk, "rate", PERIOD)["cell"]}
    prior = {
        "period": PERIOD_PRIOR,
        "total_rate_pct": _cell(ws, rows, cols, "total", "rate", PERIOD_PRIOR)["value"] * 100.0,
        "total_rate_cell": _cell(ws, rows, cols, "total", "rate", PERIOD_PRIOR)["cell"],
        "domestic_rate_pct": _cell(ws, rows, cols, "domestic reliefs:subtotal", "rate", PERIOD_PRIOR)["value"] * 100.0,
        "customs_excise_rate_pct": _cell(ws, rows, cols, "customs and excise:subtotal", "rate", PERIOD_PRIOR)["value"] * 100.0,
    }
    return {
        "source_file": os.path.basename(xlsx_path),
        "sheet": SHEET,
        "period": PERIOD,
        "period_note": QUARTER_NOTE,
        "header_rows_found": {"measure_groups": header_rows[0], "periods": header_rows[1]},
        "components": parts,
        "domestic_sub_lines_pct": sub,
        "prior_year_same_quarter": prior,
        "funnel_rate": "domestic",
        "funnel_rate_pct": parts["domestic"]["rate_pct"],
        "sensitivity_rate": "total",
        "sensitivity_rate_pct": parts["total"]["rate_pct"],
        "previous_typed_constant_pct": 8.77,
    }


def run_tax_exemptions(xlsx_path=None, out_path=None):
    xlsx_path = xlsx_path or paths.TAX_EXEMPTIONS_XLSX
    out_path = out_path or paths.TAX_EXEMPTION_RATE
    result = extract(xlsx_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    c = result["components"]
    print("  %s: total %.4f%% | domestic %.4f%% | customs/excise %.4f%%  (Q1 2022/23 total %.4f%%)" % (
        PERIOD, c["total"]["rate_pct"], c["domestic"]["rate_pct"], c["customs_excise"]["rate_pct"],
        result["prior_year_same_quarter"]["total_rate_pct"]))
    return result


if __name__ == "__main__":
    run_tax_exemptions()
