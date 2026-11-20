# Known issues (open items only)

Closed items are recorded block by block in `CHANGELOG.md`. Updated 2026-11-17 (Editing Pass 5, release v0.9.0).

## Open: owner decisions

1. **The publication candidate of the report is `report/final/Taxpayer_Development_Journey_v1.0.docx` / `.pdf`, built from `report/working/Taxpayer_Development_Journey_working_v6.docx` (Pass 5).** `docs/claims_map.csv` lists every claim (80); `docs/claims_map_v5_check.csv` locates each one in the v6 working copy (80 OK). The report is NOT part of release v0.9.0 (it is added with v1.0.0, together with the three DOIs); `report/` is not tracked except `report/final/` from v1.0.0 on.

## Open: the models

2. **Persistence is the key uncertainty of Table 5.1.** No data fix it (signed-off distribution: triangular 0.5 / 0.75 / 0.9); the lifecycle value roughly doubles between 0.75 and 0.90 and Entry only breaks even from 0.90 (20 years). It is reported side by side in `stage_economics.json` and `table5_2_persistence_sensitivity.csv` (Table 5.2).
3. **Reach and uptake of every stage tool, the mapping of each tool to a morale-model intervention, and the intervention effect sizes are ASSUMPTIONS** (signed off, not measured). Fig 5.1 and the agent and tier simulations show assumed uplifts expressed as odds ratios; the agent effect on year-10 registration is small (+0.7 pp) because the yearly registration probability is about 0.3%.
4. **The agent calibration cannot separate its two parameters** (correlation -0.99); only the combination conversion x (mean index + intercept) = 0.33% a year is identified. No compatible third target was found (FinScope 2017 prints no TIN rate; the 2017 microdata are not held).
5. **The age-earnings path of the 20-year sensitivity is one cross-section** (age and cohort effects are confounded), uses 5-year band means that are noisy for owners aged 55+, and assumes constant TZS.
6. **Statute.** The resident schedule is that of Cap. 332 R.E. 2023 (unchanged by the Finance Acts 2024, 2025 and 2026, checked against the texts); the presumptive schedule is that of the Finance Act 2026 (in force 1 July 2026). Its twelve-month nil tax for a new TIN holder starting a business is NOT applied (reported as a sensitivity). The Finance Act 2023 text (the levy on transfers removed), GN 496A and GN 642A of 2021 were not retrieved (secondary sources: EY, GSMA, the Minister's statement).
7. **No official mobile-money levy collection total** was found (only GSMA estimates: TZS 360 billion for July-December 2021 and TZS 252 billion in 2022). The 2022 ratio to BoT mobile payments (about 0.22%) is indicative, for the earlier regime.
8. **TRA series and the registration trend of the reach scenarios.** TRA registered taxpayers are TIN registrations, not adults; TRA's 2022/23 figure was restated by +17% and its active-business-TIN count halves in 2022/23 without explanation (definition changes). The registration trend used beside the stage tools (never added to a tool's effect) counts registrations per adult. MSME receipts are ILFS household-enterprise receipts, not registered MSMEs. No audit-coverage or penalty data were found, so `tax_morale.baseline.enforcement` is an assumed score.

## Open: data and publishing

9. **Confidence intervals use reconstructed survey designs** (FinScope: enumeration-area PSUs and region x urban/rural strata; ILFS: EA PSUs and region strata). Neither file names strata or PSUs.
10. **`data/raw/SOURCES.csv`**: FSDT data-access terms, the MoF terms of use and the census catalogue match (the NBS page does not name a "10 percent sample" file) are still to be confirmed; the ILFS 2024 citation wording is to be confirmed with NBS.
11. **Dashboard PDFs show the time they are generated** (the "Generated" line of the Asset report and the Legacy certificate): by design, not a data output.
12. **Inherited agent-workflow code** (`shared_context.py`: audit trail, conflict log, validation history) still uses uuid4 and wall-clock times in functions this pipeline does not call.
13. **Dashboard screenshots are not byte-reproducible** (browser rendering) and are opt-in (`--screenshots`).

## Open: the report working copy (Editing Pass 1)


14. **Embedded pictures** (cover poster, Theory of Change, journey graphic, data figures, persona cards, dashboard screenshots) were rebuilt or re-lettered in Passes 1b-3 and carry the new names and numbers; the only remaining typed old-name lettering is listed in item 17.
15. **Neutral names chosen (2026-11-15)**: GitHub repository `taxpayer-development-journey`, dashboard https://taxpayer-development-journey.streamlit.app; the old repository is renamed, the cleaned history is pushed and the old app deleted by the owner (steps in `_archive/publishing/OWNER_STEPS.md`).
16. **C3 / C4 proposal-format headings were left as they are** (decision list in `_archive/process_records/EDIT_PASS1_REPORT.md`).

## Open: the report working copy (Editing Pass 1b)

17. **Pictures with typed text, after Pass 4.** The six persona cards (report and `dashboard/assets`) were edited in Passes 2 and 3 (emblems, certificate seals, cap badge and plaque painted out; "TRA" re-lettered in the text panels in Lora / Lato and in three bubbles; the Seed number and the Entry age label updated; the halo marks around the Joseph bubble removed). Left as they are: the speech-bubble line "TRA kazi zake", the clipboard heading "TRA COMPLIANCES" and the book spine "TRA RETURNS" on the Mzee card (rotated lettering on textured backgrounds); the Neema and Mzee certificates read "TAX OFFICE" in a substitute font; the bubble words "Kodi" are in a comic-style substitute font. The Enterprise, Asset and Legacy output pictures are cropped screenshots of the dashboard (regenerate with `run_all.py --screenshots`).
18. **Body numbers and wording** follow `docs/claims_map.csv` (Passes 2-4); `docs/claims_map_v5_check.csv` lists every claim with its location (80 OK). Wording left unchanged because no approved text covers it (listed in `_archive/process_records/EDIT_PASS4_REPORT.md`): "hypothesis" used as an ordinary word in the Active annex, the "green REAL tag" sentence in the Asset annex (the dashboard tag now reads COMPUTED), and "tested" in other sentences.
19. **Theory of Change descriptors** are the owner's age bands (6-15, 16-24, 25-44, 25-64, 45-64, 65+); the Active, Enterprise and Asset bands are not computed from data (only Seed's `seed_age_band` is configured).
20. **"verified economic identity"** is kept as a lower-case concept (explained at its first mention); "(The Ladder)" labels are removed.
