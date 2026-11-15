"""Builds the FINAL claims map docs/claims_map.csv from the working draft (Block F5). Not part of run_all.py.

The draft (docs/claims_map_draft.csv, kept in _archive/) accumulated one group of columns per work block (block_b_*, ..., block_f_*). The final map has one row per claim of the
submitted report and the columns: claim_id, location, current value, type, label, source script, output file, status. For each claim the LATEST block that touched it decides the
value, type, source and status; an untouched claim keeps the draft's own value, type and source.

  label  COMPUTED / MODELLED / CITED (the evidence type), or the reason a claim is not a data claim (ASSUMPTION report-stated, DESIGN RULE, REMOVED, n/a ...)

Run:  python src/tools/build_claims_map.py [path to the draft]
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

BLOCKS = ["f", "e3", "e2", "e1", "d", "c", "b"]
SCRIPT_RE = re.compile(r"((?:src|dashboard)[/\\][\w/\\.\-]+?\.py)")
OUT_RE = re.compile(r"((?:outputs|data|docs)[/\\][\w/\\.\-<>]+?\.(?:json|csv|png|svg|md|yaml))")


def pick(row, suffix):
    for b in BLOCKS:
        v = row.get("block_%s_%s" % (b, suffix), "")
        if v:
            return v, b
    return "", None


def classify(typ, draft_type):
    t = (typ or draft_type or "").upper()
    if t.startswith("MODELLED"):
        return "MODELLED"
    if t.startswith("COMPUTED / CITED"):
        return "COMPUTED / CITED / MODELLED"
    if t.startswith("COMPUTED"):
        return "COMPUTED"
    if t.startswith("CITED"):
        return "CITED"
    if t.startswith("ASSUMPTION"):
        return "ASSUMPTION (report-stated)"
    if t.startswith("DESIGN"):
        return "DESIGN RULE"
    if t.startswith("REMOVE"):
        return "REMOVED"
    return "n/a (not a data claim)"


def main(draft=None):
    draft = draft or os.path.join(paths.ROOT, "_archive", "claims_map_draft.csv")
    if not os.path.exists(draft):
        draft = os.path.join(paths.ROOT, "docs", "claims_map_draft.csv")
    with open(draft, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        val, vb = pick(r, "new_value")
        typ, tb = pick(r, "type")
        src, sb = pick(r, "source")
        if not src:
            src, sb = pick(r, "source_script_and_output")
        st, stb = pick(r, "status")
        cur = val or r["value"]
        typ = typ or r["proposed_type"]
        src = src or r["current_source"]
        status = st or r["status"]
        scripts = sorted(set(m.replace("\\", "/") for m in SCRIPT_RE.findall(src)))
        outs = sorted(set(m.replace("\\", "/") for m in OUT_RE.findall(src)))
        out.append({"claim_id": r["claim_id"], "location": r["location"], "current value": cur, "type": typ, "label": classify(typ, r["proposed_type"]),
                    "source script": "; ".join(scripts) if scripts else ("" if "hard-coded" not in src else src), "output file": "; ".join(outs), "status": status})
    path = os.path.join(paths.ROOT, "docs", "claims_map.csv")
    cols = ["claim_id", "location", "current value", "type", "label", "source script", "output file", "status"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out)
    print("wrote", path, len(out), "claims")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
