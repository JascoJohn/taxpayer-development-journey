"""
Regenerates every data file the dashboard reads, fully standalone from the raw FinScope file.

Order matters: economic_model.py's run_economic_model() reads finscope_summary.json (to overlay
real FinScope-measured values over its hardcoded defaults), and intervention_registrar.py's
register_all() reads both report_sections.json and economic_model.json. The tier-migration
simulation is deliberately NOT part of run_economic_model() itself (see the "D.2" comment above
run_tier_migration_simulation() in economic_model.py), so it is run here as its own step and
merged into the same economic_model.json run_economic_model() just wrote.

Usage:
    python run_all.py                    full run from data\\raw\\ (same as --from-raw)
    python run_all.py --from-processed   skip FinScope ingestion, the respondent-level models (TIN/mobile money, targeting) and the census/ILFS microdata steps; read data\\interim\\ and data\\processed\\
    python run_all.py --clean            empty outputs\\stats, outputs\\tables, data\\interim, data\\processed first
    python run_all.py --fetch            fetch the World Bank WDI snapshots first (the only network call), then run
    python run_all.py --llm              opt-in flag, not used in this project yet (exits with an error)

Timestamps and the run id go to outputs\\stats\\run_meta.json, not into the data files.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import paths  # resolves every location from config.yaml; puts src/<stage> folders on sys.path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Regenerate every file the dashboard reads.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--from-raw", action="store_true",
                      help="full run from data/raw/ (default)")
    mode.add_argument("--from-processed", action="store_true",
                      help="skip FinScope ingestion and the census/ILFS steps; read data/interim/ and data/processed/")
    p.add_argument("--clean", action="store_true",
                   help="empty outputs/stats, outputs/tables, outputs/figures, data/interim, data/processed first (never data/raw, docs, report/)")
    p.add_argument("--fetch", action="store_true", help="opt-in network fetch of the World Bank WDI snapshots (data/raw/worldbank/); no network call without it")
    p.add_argument("--screenshots", action="store_true", help="opt-in: screenshots of the 7 dashboard pages with Playwright (outputs/figures/dashboard_*.png); needs environment/requirements-screenshots.txt and a Chromium download")
    p.add_argument("--full-bootstrap", action="store_true", help="recompute the targeting multiplier bootstrap (1,000 respondent replicates x 2 models, refit in every replicate; tens of minutes) and its cache outputs/cache/targeting_bootstrap.json; without it the cache is read")
    p.add_argument("--llm", action="store_true", help="opt-in LLM calls (not used in this project yet)")
    return p.parse_args(argv)


def clean():
    root = os.path.realpath(paths.ROOT)
    for d in paths.CLEAN_DIRS:
        real = os.path.realpath(d)
        if not real.startswith(root + os.sep):
            raise SystemExit("refusing to clean a folder outside the project: %s" % d)
        os.makedirs(d, exist_ok=True)
        for name in os.listdir(d):
            if name == ".gitkeep" or name.startswith("README"):          # placeholder that keeps an otherwise empty folder in git; the folder READMEs are documentation, not outputs
                continue
            full = os.path.join(d, name)
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
        print("  cleaned", os.path.relpath(d, paths.ROOT))


def required_for_processed():
    """Files a --from-processed run reads instead of the raw microdata (census and ILFS aggregates included)."""
    return [paths.FINSCOPE_SUMMARY, paths.FINSCOPE_REGION_ACTIVITY, paths.FINSCOPE_ACTIVE_BENCHMARK, paths.INTERVENTIONS_YAML,
            paths.CENSUS_AGE_COUNTS, paths.ILFS_INDICATORS, paths.AGENT_CELLS, paths.AFROBAROMETER_MORALE, paths.AGENT_TRUST_MORALE, paths.AGENT_INCOME, paths.TWIN_INPUTS, paths.TRA_REGISTERED_TAXPAYERS_CSV, paths.AGENT_CALIBRATION, paths.ILFS_TAX_BASE, paths.HBS_TURNOVER, paths.TRA_COLLECTIONS_JSON]


def required_raw():
    """Raw inputs a --from-raw run needs."""
    return [paths.FINSCOPE_CSV, paths.TAX_EXEMPTIONS_XLSX, paths.CENSUS_SAV, paths.ILFS_SAV, paths.AFROBAROMETER_SAV, paths.HBS_INDIVIDUAL, paths.HBS_CONSUMPTION, paths.HBS_S10C, paths.TRA_COLLECTIONS_XLSX]


def main(argv=None):
    args = parse_args(argv)
    if args.llm:
        print("--llm: not used in this project yet", file=sys.stderr)
        return 2
    if args.clean and args.from_processed:
        print("--clean cannot be combined with --from-processed (it would delete the processed inputs)", file=sys.stderr)
        return 2

    if args.from_processed:
        missing = [os.path.relpath(p, paths.ROOT) for p in required_for_processed() if not os.path.exists(p)]
        if missing:
            print("--from-processed: required file(s) missing: %s\n"
                  "Run `python run_all.py --from-raw` first." % ", ".join(missing), file=sys.stderr)
            return 2
        if not os.path.exists(paths.TAX_EXEMPTIONS_XLSX) and not os.path.exists(paths.TAX_EXEMPTION_RATE):
            print("--from-processed: neither %s nor %s exists" % (os.path.relpath(paths.TAX_EXEMPTIONS_XLSX, paths.ROOT),
                                                                  os.path.relpath(paths.TAX_EXEMPTION_RATE, paths.ROOT)), file=sys.stderr)
            return 2
    else:
        missing = [os.path.relpath(p, paths.ROOT) for p in required_raw() if not os.path.exists(p)]
        if missing:
            print("--from-raw: raw input(s) missing: %s" % ", ".join(missing), file=sys.stderr)
            return 2

    wb_missing = [os.path.relpath(p, paths.ROOT) for p in paths.WB_SNAPSHOTS.values() if not os.path.exists(p)]
    if wb_missing and not args.fetch:
        print("World Bank snapshot(s) named in config.yaml missing: %s\nRun `python run_all.py --fetch` (network) and update worldbank.snapshots."
              % ", ".join(wb_missing), file=sys.stderr)
        return 2

    if args.clean:
        print("CLEAN")
        clean()

    if args.fetch:
        print("FETCH: World Bank WDI snapshots (network)")
        import fetch_worldbank
        fetch_worldbank.fetch_all()
        print("  The run below uses the snapshots named in config.yaml (worldbank.snapshots); update that block to adopt the new files.")

    import run_meta
    import finscope_analysis
    import tin_by_segment
    import tax_exemptions
    import census_population
    import ilfs_indicators
    import macro_inputs
    import economic_model
    import intervention_registrar
    import finscope_region_activity_loader
    import finscope_active_benchmark_loader
    import tin_mobile_money
    import targeting_model
    import targeting_bootstrap
    import afrobarometer_morale
    import agent_inputs
    import twin_inputs
    import agent_calibration
    import hbs_turnover
    import cited_facts
    import tra_collections
    import reach_scenarios
    import stage_economics
    import dashboard_inputs

    mode = "from-processed" if args.from_processed else "from-raw"
    run_meta.record_run(mode=mode, clean=bool(args.clean), started_at=run_meta.now(),
                        pipeline_run_id=run_meta.pipeline_run_id(), python=sys.version.split()[0])

    if not args.from_processed:
        print("=" * 60)
        print("STEP 1: FinScope summary statistics")
        print("=" * 60)
        finscope_analysis.run_finscope_analysis()
    else:
        print("STEP 1: skipped (--from-processed): using", os.path.relpath(paths.FINSCOPE_SUMMARY, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 2: TIN rate by lifecycle stage (one stratification, one weight; reconciliation check)")
    print("=" * 60)
    if os.path.exists(paths.FINSCOPE_CSV):
        tin_by_segment.run_tin_by_segment()
    else:
        print("  skipped: %s not present (this step reads respondent-level FinScope data)" % os.path.relpath(paths.FINSCOPE_CSV, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 2a: TIN holding and mobile money (observational association, real FinScope respondents)")
    print("=" * 60)
    if not args.from_processed:
        tin_mobile_money.run_tin_mobile_money()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.TIN_MOBILE_MONEY, paths.ROOT), "if present")

    print("\n" + "=" * 60)
    print("STEP 2b: Real-data targeting model (all adults, TIN holding); agent population for the simulations")
    print("=" * 60)
    if not args.from_processed:
        targeting_model.run_targeting_model()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.AGENT_CELLS, paths.ROOT), "and", os.path.relpath(paths.TARGETING_MODEL, paths.ROOT), "if present")

    print("\n" + "=" * 60)
    print("STEP 2c: Targeting multiplier intervals (respondent bootstrap), leakage-adjusted AUC, leave-one-zone-out AUC (cached; --full-bootstrap recomputes)")
    print("=" * 60)
    if args.full_bootstrap and (args.from_processed or not os.path.exists(paths.FINSCOPE_CSV)):
        print("--full-bootstrap needs the FinScope microdata and cannot be combined with --from-processed", file=sys.stderr)
        return 2
    targeting_bootstrap.run_targeting_bootstrap(full=args.full_bootstrap)

    print("\n" + "=" * 60)
    print("STEP 3: Tax exemption and relief rates (MoF workbook, Q1 2023/24)")
    print("=" * 60)
    if os.path.exists(paths.TAX_EXEMPTIONS_XLSX):
        tax_exemptions.run_tax_exemptions()
    else:
        print("  skipped: workbook not present; using", os.path.relpath(paths.TAX_EXEMPTION_RATE, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 3a: Tax morale components (Afrobarometer R8) and agent trust / morale / income cell distributions (Afrobarometer R8, ILFS 2024)")
    print("=" * 60)
    if not args.from_processed:
        afrobarometer_morale.run_afrobarometer_morale()
        agent_inputs.run_agent_inputs()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.AFROBAROMETER_MORALE, paths.ROOT), os.path.relpath(paths.AGENT_TRUST_MORALE, paths.ROOT), "and", os.path.relpath(paths.AGENT_INCOME, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 4: Census 2022 10% sample: Seed population")
    print("=" * 60)
    if not args.from_processed:
        census_population.run_census_population()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.CENSUS_AGE_COUNTS, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 5: ILFS 2024 indicators")
    print("=" * 60)
    if not args.from_processed:
        ilfs_indicators.run_ilfs_indicators()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.ILFS_INDICATORS, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 5b: TRA registered taxpayers and the base parameters of the reach scenarios (published figures, WDI, Census, ILFS)")
    print("=" * 60)
    if not args.from_processed:
        twin_inputs.run_twin_inputs()
    else:
        print("  skipped (--from-processed): using", os.path.relpath(paths.TWIN_INPUTS, paths.ROOT), "and", os.path.relpath(paths.TRA_REGISTERED_TAXPAYERS_CSV, paths.ROOT))

    print("\n" + "=" * 60)
    print("STEP 6: Macro inputs (World Bank WDI snapshots; no network)")
    print("=" * 60)
    macro_inputs.run_macro_inputs()

    print("\n" + "=" * 60)
    print("STEP 6b: Calibration of the agent simulation to TRA's registered-taxpayer trend (no-intervention scenario)")
    print("=" * 60)
    agent_calibration.run_agent_calibration()              # needs only data/processed (agent cells, income, trust and morale, the TRA series) and outputs/tables/tin_by_segment.csv: runs in both modes

    print("\n" + "=" * 60)
    print("STEP 7: Economic model (15 components)")
    print("=" * 60)
    economic_model.run_economic_model()

    print("\n" + "=" * 60)
    print("STEP 8: Tier-migration simulation (Enterprise dashboard)")
    print("=" * 60)
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        _em_json = json.load(f)
    base_parameters = _em_json["base_parameters"]
    tier_result = economic_model.run_tier_migration_simulation(
        base_parameters, n_agents=paths.N_AGENTS, n_years=paths.N_YEARS, morale_model=_em_json["tax_morale_model"]
    )
    with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
        model = json.load(f)
    model["tier_migration_simulation"] = tier_result
    with open(paths.ECONOMIC_MODEL, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("STEP 8a: HBS 2017/18 turnover of household-business owners (aggregates; revenue per registrant, taxable capacity, Mzani wa Kodi bands)")
    print("=" * 60)
    hbs_turnover.run_hbs_turnover(from_processed=args.from_processed)           # with --from-processed the aggregates are read from data/processed/hbs_turnover.json (no microdata)
    tra_collections.run_tra_collections(from_processed=args.from_processed)    # TRA FY2024/25 collections (CITED aggregates) for the scale check
    cited_facts.run_cited_facts()                                               # register facts CITED from published documents (config.yaml cited_facts)

    print("\n" + "=" * 60)
    print("STEP 8b: Table 5.1 stage economics (costs, revenue, NPV, ROI for the six stages; Monte Carlo)")
    print("=" * 60)
    stage_economics.run_stage_economics(from_processed=args.from_processed)      # with --from-processed the ILFS tax base is read from data/processed/ilfs_tax_base.json (no microdata)

    print("\n" + "=" * 60)
    print("STEP 8b2: Dashboard inputs (Scenario lab parameters, interactive Figure 5.1)")
    print("=" * 60)
    dashboard_inputs.run_dashboard_inputs()                                      # reads data/processed/ilfs_tax_base.json (written just above) and economic_model.json; aggregates only

    print("\n" + "=" * 60)
    print("STEP 8c: Reach scenarios (Figure 5.2) with the scale check against TRA FY2024/25")
    print("=" * 60)
    reach_scenarios.run_reach_scenarios(from_processed=args.from_processed)

    print("\n" + "=" * 60)
    print("STEP 9: Intervention register (rebuilt on every run)")
    print("=" * 60)
    intervention_registrar.register_all(force=True)

    if not args.from_processed:
        print("\n" + "=" * 60)
        print("STEP 10: FinScope region x activity prevalence")
        print("=" * 60)
        finscope_region_activity_loader.build_finscope_region_activity_data()

        print("\n" + "=" * 60)
        print("STEP 11: FinScope active-stage benchmark")
        print("=" * 60)
        finscope_active_benchmark_loader.build_finscope_active_benchmark_data()
    else:
        print("\nSTEPS 10-11: skipped (--from-processed): using data/processed/")

    print("\n" + "=" * 60)
    print("STEP 12: Figures (src/06_figures; outputs/figures/*.png and .svg)")
    print("=" * 60)
    import run_figures
    run_figures.run_figures()
    if args.screenshots:
        print("\n" + "=" * 60)
        print("STEP 12b: Dashboard screenshots (Playwright, --screenshots)")
        print("=" * 60)
        import capture_dashboard
        capture_dashboard.main()

    run_meta.record_run(finished_at=run_meta.now())
    print("\n" + "=" * 60)
    print("DONE -- every file the dashboard reads has been regenerated (%s)" % mode)
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
