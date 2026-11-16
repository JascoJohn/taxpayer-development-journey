"""Two consecutive --clean runs give byte-identical outputs (only run_meta.json may differ)."""
import os

from conftest import run_all, snapshot

EXPECTED = {
    "outputs/stats/assumption_ledger.json", "outputs/stats/economic_model.json", "outputs/stats/finscope_report.txt",
    "outputs/stats/intervention_register.json",
    "data/interim/finscope_feature_store.json", "data/interim/finscope_summary.json", "data/interim/shared_context.json",
    "data/processed/finscope_active_benchmark.json", "data/processed/finscope_region_activity.json",
    # Block B
    "outputs/stats/tin_reconciliation.json", "outputs/stats/tax_exemption_rate.json", "outputs/stats/seed_population.json",
    "outputs/stats/ilfs_summary.json", "outputs/tables/tin_by_segment.csv", "outputs/tables/ilfs_informality.csv",
    "data/processed/census_age_counts.json", "data/processed/ilfs_indicators.json",
    # Block C
    "outputs/stats/macro_inputs.json",
    # Block D
    "outputs/stats/tin_mobile_money.json", "outputs/tables/tin_mobile_money.csv",
    "outputs/stats/targeting_model.json", "outputs/tables/targeting_deciles.csv", "data/processed/agent_cells.json",
    # Block E1
    "outputs/tables/targeting_variants.csv", "outputs/tables/targeting_leakage_review.csv", "data/processed/afrobarometer_morale.json",
    "outputs/tables/tax_morale_components.csv", "data/processed/agent_trust_morale.json", "data/processed/agent_income.json",
    # Block E2
    "data/processed/tra_registered_taxpayers.csv", "data/processed/twin_inputs.json", "data/processed/agent_calibration.json",
    "outputs/stats/stage_economics.json", "outputs/tables/table40_stage_economics.csv",
    # Block F
    "data/processed/ilfs_tax_base.json",
} | {"outputs/figures/%s.%s" % (n, e) for n in ("fig_5_1_modelled_compliance", "fig_5_2_digital_twin", "fig_5_3_table40_roi_by_stage", "fig_5_4_persistence_sensitivity", "fig_a1_tin_by_segment",
                                              "fig_a2_tax_morale_components", "fig_a3_targeting_deciles", "fig_a4_targeting_variants", "fig_a5_macro_gap", "journey_graphic", "cover_poster", "theory_of_change") for e in ("png", "svg")}


def test_two_clean_runs_are_byte_identical(project):
    r1 = run_all(project, "--clean")
    assert r1.returncode == 0, r1.stderr[-2000:]
    s1 = snapshot(project)
    assert set(s1) == EXPECTED, set(s1) ^ EXPECTED
    assert os.path.exists(os.path.join(project, "outputs", "stats", "run_meta.json"))

    r2 = run_all(project, "--clean")
    assert r2.returncode == 0, r2.stderr[-2000:]
    s2 = snapshot(project)
    assert s1 == s2, [k for k in s1 if s1[k] != s2.get(k)]


def test_no_timestamps_in_data_outputs(project):
    import re
    assert run_all(project, "--clean").returncode == 0
    ts = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")
    for rel in snapshot(project):
        if rel.endswith(".png"):                     # binary figures carry no metadata timestamp (checked through byte-identical re-runs)
            continue
        with open(os.path.join(project, rel), encoding="utf-8") as f:
            assert not ts.search(f.read()), rel
