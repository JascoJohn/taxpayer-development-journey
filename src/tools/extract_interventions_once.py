"""One-off extraction of the interventions into docs/interventions.yaml (Block F4). NOT part of run_all.py.

ALREADY RUN. Since 2026-11-13 (Editing Pass 1) docs/interventions.yaml is maintained by hand (names from config.yaml `names:`, old names in `old_names`, the eight LLM drafts moved to
_archive/interventions_llm_drafts.yaml): do NOT run this again, it would overwrite the reviewed file.

Source 1 (adopted entries): the six stage tools of the submitted report (report/submission_v1, 'The Proposed Solution' sections): the report's own name, one sentence of its mechanism
(worded from the report's own text), the target group, and the cost reference (the report's Table 40 stated cost, PDF p. 52).
Source 2 (drafts, NOT adopted): the eight interventions of the frozen LLM-generated section `section_5_innovations` in report_sections.json: only the name, the stage and the tagline are copied
(no other LLM text), each flagged `in_submission_v1` by looking for the name in the report text. None of them is registered by the pipeline.

The YAML is a DRAFT for the owner's review; after the review the frozen JSON is no longer an input of the pipeline (it is kept in _archive/frozen/).

Run:  python src/tools/extract_interventions_once.py [path to report_sections.json] [path to the report text dump]
"""

import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

ROOT = paths.ROOT

# the report's own wording (submission_v1; PDF page of the section), one sentence per stage tool
REPORT_TOOLS = [
    {"stage": "seed", "name": "Madarasa Ya Kodi", "report_pdf_page": 17,
     "mechanism": "A gamified digital learning platform developed and promoted by TRA, designed to create familiarity with taxes before tax obligations begin.",
     "target_group": "children aged 6-15 (the Seed age band, config.yaml seed_age_band)", "cost_key": "seed"},
    {"stage": "entry", "name": "Targeting Priority Tool (for Smart USSD Registration)", "report_pdf_page": 23,
     "mechanism": "TRA reaches young people through mobile money: a USSD prompt invites registration for a TIN, and ENgazi Registration is a second registration channel; the tool prioritises whom to reach.",
     "target_group": "young adults aged 16-24 (FinScope Entry segment)", "cost_key": "entry"},
    {"stage": "active", "name": "Mzani wa Kodi (Presumptive Tax Reference Tool)", "report_pdf_page": 29,
     "mechanism": "A data-driven presumptive tax reference system built from FinScope microdata: indicative turnover bands by region and primary economic activity, an empirical benchmark for assessments.",
     "target_group": "adults aged 25-44 who are not business owners (FinScope Active segment)", "cost_key": "active"},
    {"stage": "enterprise", "name": "Ngazi Progression Dashboard", "report_pdf_page": 35,
     "mechanism": "A digital taxpayer progression platform: a visible progression pathway over the existing compliance framework; businesses unlock recognition and selected TRA service benefits as they meet compliance milestones.",
     "target_group": "business owners aged 25-64 (FinScope Enterprise segment)", "cost_key": "enterprise"},
    {"stage": "asset", "name": "Mali Alama (Asset Score)", "report_pdf_page": 40,
     "mechanism": "A verified ownership credibility rating built from a citizen's history of declared and verifiable asset ownership; it rewards transparency, not wealth.",
     "target_group": "adults aged 45-64 who are not business owners (FinScope Asset segment)", "cost_key": "asset"},
    {"stage": "legacy", "name": "Kodi Legacy Score and Succession Builder", "report_pdf_page": 47,
     "mechanism": "A lifetime compliance index that preserves a taxpayer's verified compliance history and enables its structured transfer to an approved successor.",
     "target_group": "adults aged 65 and over (FinScope Legacy segment)", "cost_key": "legacy"},
]


def main(frozen_path=None, report_text_path=None):
    frozen_path = frozen_path or next(p for p in (os.path.join(ROOT, "_archive", "frozen", "report_sections.json"), os.path.join(ROOT, "outputs", "frozen", "report_sections.json")) if os.path.exists(p))
    with open(frozen_path, encoding="utf-8") as f:
        content = json.load(f)["section_5_innovations"]["content"]
    report_text = ""
    if report_text_path and os.path.exists(report_text_path):
        report_text = open(report_text_path, encoding="utf-8").read().lower()
    cost = {k.split(".")[-1].replace("_tzs", ""): v["value"] for k, v in paths.CFG["assumptions"].items() if k.startswith("stage.cost.")}
    names = paths.CFG["stage_economics"]["report_names"]
    adopted = []
    for t in REPORT_TOOLS:
        c = cost.get(t["cost_key"])
        ref = {"source": "report/submission_v1 Table 40, PDF p. 52 ('5. Portfolio-Level Impact')"}
        if c is None:
            ref.update({"stated": False, "note": "no cost stated in the report ('Not yet modeled')"})
        else:
            ref.update({"stated": True, "cost_tzs": c if not isinstance(c, list) else None, "cost_range_tzs": c if isinstance(c, list) else None})
        adopted.append({"stage": t["stage"], "name": t["name"], "mechanism": t["mechanism"], "target_group": t["target_group"], "cost_reference": ref,
                        "report_pdf_page": t["report_pdf_page"], "morale_model_key": names[t["stage"]]["morale_model_key"]})
    drafts = []
    for b in re.split(r"INTERVENTION \d+ OF \d+", content)[1:]:
        n, tg, st = re.search(r"NAME:\**\s*(.+)", b), re.search(r"TAGLINE:\**\s*(.+)", b), re.search(r"LIFECYCLE STAGE:\**\s*(.+)", b)
        if not n:
            continue
        name = n.group(1).strip().strip("*").strip()
        short = re.split(r"[—–?(]", name)[0].strip().lower()
        drafts.append({"name": name, "stage": st.group(1).strip().strip("*") if st else None, "tagline": tg.group(1).strip().strip("*") if tg else None,
                       "in_submission_v1": bool(report_text and short and short in report_text) if report_text else None})
    out = {"status": "DRAFT for the owner's review (Block F4). Adopted entries are the six stage tools of the submitted report; drafts are the eight interventions of the frozen LLM-generated section "
                     "(name, stage and tagline only) and are NOT registered by the pipeline.",
           "interventions": adopted, "llm_drafts_not_adopted": drafts}
    path = os.path.join(ROOT, "docs", "interventions.yaml")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# docs/interventions.yaml - DRAFT for the owner's review (written once by src/tools/extract_interventions_once.py; read by src/04_models/intervention_registrar.py)\n")
        yaml.safe_dump(out, f, sort_keys=False, allow_unicode=True, width=160)
    print("wrote", path, "-", len(adopted), "adopted,", len(drafts), "drafts")


if __name__ == "__main__":
    main(*(sys.argv[1:3]))
