"""W-CITED (Pass 6B-1) - Register facts CITED from published documents, stored with their source, page and what they do NOT show.

The values live in config.yaml (`cited_facts:`); nothing here is estimated. The module (1) writes outputs/stats/cited_facts.json and outputs/tables/cited_facts.csv, and (2) checks the TIN stock against the
series the pipeline already reads (data/processed/tra_registered_taxpayers.csv: the 2023/24 value used by the model must equal the cited 6,272,000), so the two cannot drift apart.
Evidence type: CITED. These are counts of TINs of businesses (TRA audited statements) and of all TIN registrations (NBS Tax Statistics): neither is a count of adult taxpayers, and neither is comparable
with FinScope's 1.31 million adult TIN holders.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

LABEL = "CITED from published documents (TRA audited statements FY2023/24; NBS Tax Statistics 2023/24; Finance Act 2022; Afrobarometer R9/R10); not estimated"


def run_cited_facts():
    facts = paths.CFG["cited_facts"]
    rows = []
    for key, f in facts.items():
        rows.append({"key": key, "value": f["value"], "unit": f["unit"], "source": f["source"], "does_not_show": f["does_not_show"], "evidence_type": "CITED"})
    by = {r["key"]: r for r in rows}
    # the pipeline's own TIN-stock series must agree with the cited stock
    stock = None
    if os.path.exists(paths.TRA_REGISTERED_TAXPAYERS_CSV):
        with open(paths.TRA_REGISTERED_TAXPAYERS_CSV, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("status") == "used":
                    stock = float(r["registered_taxpayers"])
        if stock is not None:
            assert stock == by["tra_tin_stock_mainland_fy2023_24"]["value"], (stock, "the cited TIN stock differs from data/processed/tra_registered_taxpayers.csv")
    active, dormant = by["tra_active_business_tins_fy2023_24"]["value"], by["tra_dormant_business_tins_fy2023_24"]["value"]
    result = {"label": LABEL, "type": "CITED", "facts": {r["key"]: {k: r[k] for k in ("value", "unit", "source", "does_not_show", "evidence_type")} for r in rows},
              "derived": {"business_tins_active_plus_dormant_fy2023_24": active + dormant, "active_share_of_business_tins_pct": active / (active + dormant) * 100,
                          "tin_stock_fy2023_24": by["tra_tin_stock_mainland_fy2023_24"]["value"], "tin_stock_matches_pipeline_series": (stock == by["tra_tin_stock_mainland_fy2023_24"]["value"]) if stock is not None else None,
                          "note": "COMPUTED from the cited counts: arithmetic only"},
              "reading": "TRA's own active business TINs (1.85 million) and the TIN stock (6.27 million, entities and dormant TINs included) are not counts of adult taxpayers; FinScope's 1.31 million adult TIN holders is a survey estimate of persons"}
    os.makedirs(os.path.dirname(paths.CITED_FACTS_JSON), exist_ok=True)
    with open(paths.CITED_FACTS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    os.makedirs(os.path.dirname(paths.CITED_FACTS_CSV), exist_ok=True)
    with open(paths.CITED_FACTS_CSV, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["key", "value", "unit", "source", "does_not_show", "evidence_type"])
        for r in rows:
            wr.writerow([r[c] for c in ("key", "value", "unit", "source", "does_not_show", "evidence_type")])
    print("  Cited register facts: %d (TRA active business TINs %s, dormant %s, TIN stock %s)" % (len(rows), format(active, ","), format(dormant, ","), format(by["tra_tin_stock_mainland_fy2023_24"]["value"], ",")))
    return result


if __name__ == "__main__":
    run_cited_facts()
