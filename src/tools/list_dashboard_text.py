"""Pass 6B-1 (H9): lists the dashboard strings that state a stage definition or a value of the former stage mapping / former Table 40, for the owner's text pass. It rewrites NOTHING.

Scans dashboard/Home.py, dashboard/common.py, dashboard/pages/*.py and dashboard/tdj_lib/*.py for: stage-definition wording (informal / registered business owners, ages 25-44 / 25-64, Active and Enterprise
as groups), the former populations and rates (12.1M, 3.49M, 4.6%, 9.7%), the former Table 40 values and the retired twin. Writes docs/pending_dashboard_text.csv: file, line, text, why_listed.
Run:  python src/tools/list_dashboard_text.py
"""
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

RULES = [
    (r"12[.,]1\d*\s?M|12,110", "former Active population (non-owners 25-44, now Non-business owners 25-44)"),
    (r"3[.,]49\s?M|3,488", "former Enterprise population (all business owners 25-64)"),
    (r"\b4\.6\s?%|\b9\.7\s?%|9\.74", "former Active / Enterprise TIN rate (stage mapping A)"),
    (r"25\s?[–-]\s?44|ages? 25|aged 25", "age band of the former Active stage / stage definition"),
    (r"informal (business|worker|trader|owner)|registered (business|owner)|business owners?\b", "stage-definition wording (Active = informal owners, Enterprise = owners with a formal step under mapping B)"),
    (r"digital twin|\btwin\b", "retired digital twin"),
    (r"\b3\.23|20\.7|21\.3|\b8\.7\b|12\.8-13B|\b5\.5x|\b3\.6x", "former Table 40 value"),
    (r"FinScope has no income|no income or turnover variable|strand", "former Mzani wa Kodi wording (FinScope access strand bridge)"),
    (r"Figure 5\.[234]|Fig\.? 5\.[234]", "figure reference whose content changed (5.2 reach scenarios, 5.3 bracket, 5.4 tornado)"),
]


def main():
    files = [os.path.join(paths.ROOT, "dashboard", "Home.py"), os.path.join(paths.ROOT, "dashboard", "common.py")] + sorted(glob.glob(os.path.join(paths.ROOT, "dashboard", "pages", "*.py"))) + sorted(glob.glob(os.path.join(paths.ROOT, "dashboard", "tdj_lib", "*.py")))
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if not re.search(r"[\"']", s):
                    continue                                      # only lines that carry a string
                for pat, why in RULES:
                    if re.search(pat, s, re.I):
                        rows.append({"file": os.path.relpath(f, paths.ROOT).replace(os.sep, "/"), "line": i, "text": s[:240], "why_listed": why})
                        break
    out = os.path.join(paths.ROOT, "docs", "pending_dashboard_text.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["file", "line", "text", "why_listed"], lineterminator="\r\n")
        wr.writeheader()
        wr.writerows(rows)
    print("pending_dashboard_text.csv: %d strings in %d files (nothing rewritten)" % (len(rows), len({r["file"] for r in rows})))


if __name__ == "__main__":
    main()
