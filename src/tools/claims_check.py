"""Claims check in LIST-MISMATCH mode (Pass 6B-1, H8): lists where the report text states a value that the regenerated outputs no longer give; it NEVER edits the report.

Reads docs/claims_map_6b1_changes.csv (written by update_claims_map.py: claim ID, OLD value, NEW value) and the report as it stands (report/final/*.docx and the matching PDF, opened read-only).
For each changed claim it extracts the numbers of the old value that are not in the new value, finds the report paragraphs (and PDF pages) that contain them, and writes docs/pending_text_changes.csv:
  source, claim_id, old, new, report_page, paragraph, evidence_type, status, note
The COVER POSTER (src/06_figures/cover_poster.py, not changed in this pass) is listed too, row by row, with source "cover_poster.py": every number and claim it shows, its current value, and the new value
or "owner wording needed".
New claims (no old value) are listed with the section where the number belongs; retired claims with the reason. The report owner applies the changes in Pass 6B-2.

Run:  python src/tools/claims_check.py --list-mismatch
"""
import argparse
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?\s?(?:%|x|M|B|pp|trillion|billion|million)?")
GENERIC = {"0", "1", "2", "5", "10", "20", "12", "15", "0.5", "0.75", "0.9", "0.90", "0.95", "9915", "34", "16", "24", "25", "44", "64", "65", "45", "6", "2024", "2023", "2021", "2026", "2025", "100", "5%", "10%", "20%"}


def tokens(text):
    out = []
    for m in NUM.finditer(text):
        t = m.group(0).strip().rstrip(",")
        core = t.rstrip("%xMBpptrillionbillionmillion ").replace(",", "")
        if not core or core in GENERIC or t in GENERIC or len(core) < 3 and "." not in core:
            continue
        if t not in out:
            out.append(t)
    return out


def load_report():
    from docx import Document
    docx = sorted(glob.glob(os.path.join(paths.ROOT, "report", "final", "*.docx")))[0]
    pdf = sorted(glob.glob(os.path.join(paths.ROOT, "report", "final", "*.pdf")))[0]
    d = Document(docx)
    paras = [(i + 1, p.text) for i, p in enumerate(d.paragraphs) if p.text.strip()]
    cells = []
    for ti, t in enumerate(d.tables, 1):
        for ri, row in enumerate(t.rows, 1):
            for c in row.cells:
                if c.text.strip():
                    cells.append(("table %d row %d" % (ti, ri), c.text))
    import pymupdf
    pages = [re.sub(r"\s+", " ", p.get_text()) for p in pymupdf.open(pdf)]
    return docx, pdf, paras, cells, pages


def page_of(snippet, pages):
    s = re.sub(r"\s+", " ", snippet).strip()[:50]
    for i, p in enumerate(pages, 1):
        if s and s in p:
            return i
    return ""


def poster_rows():
    """Every number and claim on the cover poster: current value, new value or 'owner wording needed'. The poster itself is not edited."""
    import json
    sys.path.insert(0, os.path.join(paths.ROOT, "src", "06_figures"))
    import cover_poster
    with open(paths.MACRO_INPUTS, encoding="utf-8") as f:
        macro = json.load(f)
    with open(paths.STAGE_ECONOMICS, encoding="utf-8") as f:
        se = json.load(f)
    with open(paths.REACH_SCENARIOS, encoding="utf-8") as f:
        rs = json.load(f)
    b, t24 = macro["benchmark"], macro["tanzania"]
    pm = se["income_bases"]["central"]["portfolio_excluding_asset"]
    lo, hi = se["income_bases"]["low"]["portfolio_excluding_asset"]["roi_10y"]["median"], se["income_bases"]["high"]["portfolio_excluding_asset"]["roi_10y"]["median"]
    f51 = rs["figure_5_1_full_reach_implication"]
    y10 = {(r["set"], r["scenario"]): r for r in rs["year10"]}
    main_, big = y10[("four_levers", "table5_1_reach")], y10[("four_levers", "reach_50pct")]
    rows = []

    def add(ids, where, old, new, label, status, note):
        rows.append({"source": "cover_poster.py", "claim_id": ids, "old": old, "new": new, "report_page": "", "paragraph": where, "evidence_type": label, "status": status, "note": note})
    for shown, what, ids, label in cover_poster.POSTER_NUMBERS:
        where = "key-evidence tile or panel: " + what
        if shown == "12.26%":
            add(ids, "key-evidence tile 5: Tanzania tax-to-GDP, 2024 (WDI)", shown + " (2024)", "%.2f%% (2023, like for like with the peers); the 2024 value (%.2f%%) only as a separate note" % (b["tanzania_same_year_pct"], t24["tax_to_gdp_pct"]), label, "CHANGE: OWNER WORDING NEEDED",
                "the poster sets Tanzania 2024 beside the peers' 2023 benchmark (13.12%); Figure 1.1 is now 2023 against 2023 (owner decision 9): the tile's label, number and year need the owner's wording")
        elif shown == "13.12%":
            add(ids, where, shown, "%.2f%% (unchanged; 2023 peers GHA, KEN, RWA, UGA)" % b["benchmark_pct"], label, "UNCHANGED VALUE; read with tile 5", "value unchanged; read together with the changed Tanzania tile")
        elif shown.startswith("TZS 2.72T"):
            add(ids, where, shown, "TZS %.2fT (unchanged; gap %.2f pp, 2023)" % (b["revenue_gap_tzs"] / 1e12, abs(b["gap_pp"])), label, "UNCHANGED VALUE; read with tile 5", "the gap was always the 2023 comparison; the tile beside it showed the 2024 value")
        elif shown in ("10.17%", "5.56%", "12.0%"):
            add(ids, "MODELLED IMPACT (PORTFOLIO) panel: " + what, shown, "owner wording needed", label, "CHANGE: OWNER WORDING NEEDED",
                "value unchanged (Figure 5.1) but it is the effect if EVERY adult is reached (no reach factor): +%s TIN holders (best single) and +%s (combined) of %.1fM adults, against about %s new registrants at Table 5.1's reach; the panel title reads as an achieved impact" % (
                    format(round(f51["extra_tin_holders_best_single_at_full_reach"]), ","), format(round(f51["extra_tin_holders_combined_at_full_reach"]), ","), f51["adults_16_plus"] / 1e6, format(round(f51["table5_1_new_registrants_median_four_levers"]), ",")))
        else:
            add(ids, where, shown, shown + " (unchanged)", label, "UNCHANGED VALUE", "")
    add("(Table 5.1)", "MODELLED IMPACT panel: no ROI is shown", "none", "portfolio ROI %.2fx central (80%% interval %.2f-%.2f), bracket %.2fx-%.2fx; P(ROI>=1) %.0f%%" % (pm["roi_10y"]["median"], pm["roi_10y"]["p10"], pm["roi_10y"]["p90"], lo, hi, pm["p_roi_ge_1"] * 100), "MODELLED",
        "OWNER WORDING NEEDED", "the poster presents impact without the economics of Table 5.1; whether and how to add them is the owner's call")
    add("(Fig 5.2)", "implications box: 'Sustainable Revenue Growth: compounding relationships unlock revenue well beyond incremental transaction gains.'", "claim of revenue well beyond incremental gains", "owner wording needed", "MODELLED", "CHANGE: OWNER WORDING NEEDED",
        "the scale-checked reach scenarios give a year-10 increment of TZS %.2fB at Table 5.1's reach (TZS %.2fB at 50%% reach) against TZS %.0fB of individuals' income tax (TRA FY2024/25): the claim is not supported at that scale" % (
            main_["incremental_revenue_tzs"] / 1e9, big["incremental_revenue_tzs"] / 1e9, rs["scale_check_tra_fy2024_25"]["tra_fy2024_25_tzs"]["individuals_income_tax"] / 1e9))
    add("(evidence base)", "EVIDENCE BASE box: 'FinScope Tanzania 2023 (n = 9,915) & ILFS 2024; World Bank & International Benchmarks; ...; Monte Carlo Simulation; Agent-Based Modelling'", "FinScope 2023 and ILFS 2024; no HBS or TRA collections", "owner wording needed (add HBS 2017/18 and TRA FY2024/25 collections?)", "CITED / COMPUTED",
        "CHANGE: OWNER WORDING NEEDED", "the revenue per registrant now rests on HBS 2017/18 receipts; the reach scenarios are scale-checked against TRA FY2024/25 collections")
    add("(stages)", "six-stage journey: 'Active: UNDERSTAND (Presumptive Tax Estimator)'; 'Enterprise: PROGRESS'", "stage names and verbs", "names unchanged; Active is now informal business owners 25-64, Enterprise owners with a formal step; Workers 25-44 have no stage box", "n/a", "NO CHANGE NEEDED UNLESS A DEFINITION IS ADDED",
        "the poster states no stage definition or population")
    add("(dashboard)", "'DEMONSTRATED & LIVE': 'All six stages are built, live, and cross-linked' and the static screenshot assets/poster_dashboard_home.png", "dashboard Home screenshot", "owner wording needed if the screenshot is to show the new Home (targeting intervals)", "n/a", "CHECK SCREENSHOT",
        "the Home page gained a targeting-intervals block; the poster uses a static copy of the old screenshot")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-mismatch", action="store_true", default=True)
    ap.parse_args()
    with open(os.path.join(paths.ROOT, "docs", "claims_map_6b1_changes.csv"), encoding="utf-8-sig", newline="") as f:
        changes = list(csv.DictReader(f))
    with open(os.path.join(paths.ROOT, "docs", "claims_map.csv"), encoding="utf-8-sig", newline="") as f:
        cm = {r["claim_id"]: r for r in csv.DictReader(f)}
    docx, pdf, paras, cells, pages = load_report()
    out = []
    for ch in changes:
        cid, old, new = ch["claim_id"], ch["old"], ch["new"]
        row = cm.get(cid, {})
        typ = row.get("label", "")
        if not old:
            out.append({"source": "claims_map.csv", "claim_id": cid, "old": "", "new": new, "report_page": "", "paragraph": row.get("location", ""), "evidence_type": typ, "status": "NEW", "note": "no passage in the report states this: add where the location column says (%s)" % ch["reason"]})
            continue
        toks = [t for t in tokens(old) if t not in tokens(new) and t not in new]
        hits = []
        for idx, text in paras + cells:
            found = [t for t in toks if t in text]
            if found:
                hits.append((len(found), idx, text, found))
        hits.sort(key=lambda h: (-h[0], str(h[1])))
        if ch["status"] == "RETIRED":
            toks = tokens(old)[:6]
        note_extra = ""
        if not hits:                                              # the numbers that changed are not in the report: look for the old claim's own numbers (the statement changes, the value may stay)
            for idx, text in paras + cells:
                found = [t for t in tokens(old)[:6] if t in text]
                if found:
                    hits.append((len(found), idx, text, found))
            hits.sort(key=lambda h: (-h[0], str(h[1])))
            note_extra = "the statement changes although a number may stay the same | "
        if not hits:
            out.append({"source": "claims_map.csv", "claim_id": cid, "old": old, "new": new, "report_page": "", "paragraph": row.get("location", ""), "evidence_type": typ, "status": ch["status"], "note": "no old number found in the report text (picture or table image?); location from the claims map. %s" % ch["reason"]})
            continue
        for n, idx, text, found in hits[:3]:
            out.append({"source": "claims_map.csv", "claim_id": cid, "old": "; ".join(found), "new": new, "report_page": page_of(text, pages), "paragraph": idx, "evidence_type": typ, "status": ch["status"], "note": "%sold text of the claim: %s | %s" % (note_extra, old[:160].replace("\n", " "), ch["reason"])})
    n_claims_rows = len(out)
    out += poster_rows()
    path = os.path.join(paths.ROOT, "docs", "pending_text_changes.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["source", "claim_id", "old", "new", "report_page", "paragraph", "evidence_type", "status", "note"], lineterminator="\r\n")
        wr.writeheader()
        wr.writerows(out)
    print("pending_text_changes.csv: %d rows (%d from the claims map, %d from cover_poster.py; report: %s, %d paragraphs, %d PDF pages); the report and the poster were only read" % (len(out), n_claims_rows, len(out) - n_claims_rows, os.path.basename(docx), len(paras), len(pages)))


if __name__ == "__main__":
    main()
