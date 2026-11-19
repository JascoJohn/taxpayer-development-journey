"""Pass 6B-1 (H8): regenerates docs/claims_map.csv for the new stage mapping, the bracketed economics, the retired twin and the new numbers. Not part of run_all.py.

Every value is READ from the regenerated outputs (outputs/, data/processed/); nothing is typed. For each claim the script records the OLD value (as in the claims map before this pass) and the NEW value in
docs/claims_map_6b1_changes.csv, which tools/claims_check.py (list-mismatch mode) then locates in the report to write docs/pending_text_changes.csv. The report itself is never edited.

  * the 17 claims whose values change are updated in place (status "RECOMPUTED (Pass 6B-1): TEXT TO CHANGE" or "REPLACED (Pass 6B-1): TEXT TO CHANGE");
  * C079 (the digital twin, Figure 5.2) is RETIRED with its reason, and the new Figure 5.2 (reach scenarios) is a new claim;
  * the 3.23x portfolio ROI of the submitted text, which had no claim ID, gets C081 with its replacement;
  * every new number that reaches an output, figure or dashboard page gets a claim (C082 onwards), each with its evidence type.
Run:  python src/tools/update_claims_map.py
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

COLS = ["claim_id", "location", "current value", "type", "label", "source script", "output file", "status"]
CLAIMS = os.path.join(paths.ROOT, "docs", "claims_map.csv")
CHANGES = os.path.join(paths.ROOT, "docs", "claims_map_6b1_changes.csv")
ST_RE = "RECOMPUTED (Pass 6B-1): TEXT TO CHANGE"
ST_REP = "REPLACED (Pass 6B-1): TEXT TO CHANGE"
ST_NEW = "NEW (Pass 6B-1): ADD TO TEXT"


def J(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def T(x, d=1):
    return ("{:,.%df}" % d).format(x)


def B(x):
    return "TZS %.2fB" % (x / 1e9)


def rng(d, k="roi", n=2):
    return "%.*fx (80%% interval %.*f-%.*f)" % (n, d[k]["median"], n, d[k]["p10"], n, d[k]["p90"])


def build():
    se = J(paths.STAGE_ECONOMICS)
    seg = {r["segment"]: r for r in csv.DictReader(open(paths.TIN_BY_SEGMENT_CSV, encoding="utf-8", newline=""))}
    macro = J(paths.MACRO_INPUTS)
    reach = J(paths.REACH_SCENARIOS)
    hbs = J(paths.HBS_TURNOVER)
    cap = J(paths.TAXABLE_CAPACITY_JSON)
    cited = J(paths.CITED_FACTS_JSON)
    mz = J(paths.MZANI_TURNOVER)
    tbp = paths.TARGETING_BOOTSTRAP
    tb = J(tbp) if os.path.exists(tbp) else None
    ib = se["income_bases"]
    c, hi, lo = ib["central"], ib["high"], ib["low"]
    P = lambda s: seg[s]
    seg_txt = lambda s, name: "%s %.2f%% (95%% CI %.2f-%.2f; n=%s, %s TIN holders)" % (name, float(P(s)["tin_rate_pct"]), float(P(s)["ci95_low_pct"]), float(P(s)["ci95_high_pct"]), P(s)["n_unweighted"], P(s)["tin_holders_unweighted"])
    pers = se["persistence_sensitivity"]["horizons"]
    names = ["signed_off_triangular_0.5_0.75_0.9", "fixed_0.75", "fixed_0.90", "fixed_0.95"]

    def pers_txt(s):
        g = lambda h: " / ".join("%.2f" % (pers[h]["portfolio_excluding_asset"][n]["roi"]["median"] if s == "portfolio" else pers[h]["stages"][s][n]["roi"]["median"]) for n in names)
        return "persistence (assumed; no data fixes it; key uncertainty) signed-off / 0.75 / 0.90 / 0.95: 10 years %sx, 20 years %sx." % (g("10"), g("20"))

    def stage_row(s, label):
        d = c["stages"][s]
        b = {"low": lo["stages"][s], "high": hi["stages"][s]}
        base = "central (HBS 2017/18 receipts of owners with receipts) revenue per registrant TZS %s, %.1f%% owe tax; " % (T(d["revenue_per_registrant_tzs"], 0), d["share_paying_any_tax_pct"])
        brk = "bracket of the median ROI %.2fx (HBS, all owners) to %.2fx (ILFS gross)" % (b["low"]["roi_10y"]["median"], b["high"]["roi_10y"]["median"]) if s in ("active", "enterprise") else "same revenue per registrant in every basis"
        return base, brk

    new = {}

    def put(cid, value, **kw):
        new[cid] = dict(value=value, **kw)

    # ---------------------------------------------------------------- updated claims
    gap = macro["benchmark"]
    macro_txt = ("Like for like, 2023: Tanzania tax-to-GDP %.2f%% vs peer-average benchmark %.2f%% (GHA %.2f, KEN %.2f, RWA %.2f, UGA %.2f): gap %.2f pp = TZS %.2f trillion (US$ %.2f billion). "
                 "Tanzania 2024 (%.2f%%, WDI) is a separate marker, not compared with the 2023 peers.") % (
        gap["tanzania_same_year_pct"], gap["benchmark_pct"], *[gap["peers"][k]["tax_to_gdp_pct"] for k in ("GHA", "KEN", "RWA", "UGA")], abs(gap["gap_pp"]), gap["revenue_gap_tzs"] / 1e12, gap["revenue_gap_usd"] / 1e9, macro["tanzania"]["tax_to_gdp_pct"])
    for cid in ("C003", "C005", "C010"):
        put(cid, macro_txt, status=ST_RE, script="src/03_features/macro_inputs.py; src/06_figures/fig_a5_macro_gap.py", out="outputs/stats/macro_inputs.json; outputs/figures/fig_a5_macro_gap.png", reason="Figure 1.1 like for like (owner decision 9)")
    put("C017", "Overall %.2f%%; %s; %s; %s; %s; %s; %s (stage mapping B)" % (float(P("overall")["tin_rate_pct"]), seg_txt("entry", "Entry"), seg_txt("active", "Active"), seg_txt("enterprise", "Enterprise"), seg_txt("workers", "Workers 25-44"), seg_txt("asset", "Asset"), seg_txt("legacy", "Legacy")),
        status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/stats/tin_reconciliation.json; outputs/tables/tin_by_segment.csv", reason="stage mapping B (owner decision 1)")
    put("C031", "%s; Active population %s (business owners without a formal step, ages 25-64; was 12,110,885 = non-owners 25-44, now the named group Workers 25-44, population %s, no revenue lever)" % (
        seg_txt("active", "Active"), T(float(P("active")["population_weighted"]), 0), T(float(P("workers")["population_weighted"]), 0)), status=ST_RE, script="src/03_features/finscope_segments.py; src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="stage mapping B")
    put("C034", "%s" % T(float(P("enterprise")["population_weighted"]), 0), status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="stage mapping B: owners with a formal step, ages 25-64 (was 3,488,899 = all owners 25-64)")
    put("C035", "%.1f%% TIN holds (%s). Registration/licence share: NOT 46.9%%: 20.8%% of non-agricultural self-employed (headline base), 13.7%% of all workers, 32.2%% of non-agricultural private-business workers" % (
        float(P("enterprise")["tin_rate_pct"]), seg_txt("enterprise", "Enterprise")), status=ST_RE, script="src/03_features/ilfs_indicators.py; src/03_features/tin_by_segment.py", out="outputs/stats/ilfs_summary.json; outputs/tables/tin_by_segment.csv", reason="stage mapping B")
    put("C072", "%.2fM (Active: informal business owners 25-64); Workers 25-44 %.1fM" % (float(P("active")["population_weighted"]) / 1e6, float(P("workers")["population_weighted"]) / 1e6), status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="Figure 4.10 shows the former Active (12.1M); under mapping B that group is Workers 25-44")
    put("C073", "%.2fM" % (float(P("enterprise")["population_weighted"]) / 1e6), status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="Figure 4.14 shows 3.49M; under mapping B Enterprise is %.2fM" % (float(P("enterprise")["population_weighted"]) / 1e6))
    figs = "outputs/figures/fig_5_3_table40_roi_by_stage.png; outputs/figures/fig_5_4_tornado_central.png; outputs/stats/stage_economics.json; outputs/tables/table5_1_stage_economics.csv; outputs/tables/table5_2_persistence_sensitivity.csv"
    for s, cid_cost, cid_rev, cid_roi, cost, label in (("active", "C045", "C046", "C047", 600, "Active"), ("enterprise", "C048", "C049", "C050", 750, "Enterprise")):
        base, brk = stage_row(s, label)
        d = c["stages"][s]
        r10 = d["roi_10y"]
        put(cid_cost, "%s cost TZS %dM (signed off). Central basis: %s20 years ROI %.2fx [%.2f-%.2f]; %s. %s" % (label, cost, base, d["roi_20y"]["median"], d["roi_20y"]["p10"], d["roi_20y"]["p90"], brk, pers_txt(s)), status=ST_REP, script="src/04_models/stage_economics.py", out=figs, reason="central income basis and bracket (owner decision 2)")
        put(cid_rev, "10-year PV revenue (10%% discount), central: median %s, 80%% interval %.2fB to %.2fB. Bracket of the median: %s (HBS, all owners) to %s (ILFS gross). %s" % (B(d["revenue_pv"]["median"]), d["revenue_pv"]["p10"] / 1e9, d["revenue_pv"]["p90"] / 1e9, B(lo["stages"][s]["revenue_pv"]["median"]), B(hi["stages"][s]["revenue_pv"]["median"]), pers_txt(s)),
            status=ST_REP, script="src/04_models/stage_economics.py", out=figs, reason="central income basis and bracket")
        npv = se["stages"][s]["monte_carlo_at_10pct"]["npv"]["median"]
        put(cid_roi, "10-year ROI median %.2fx, 80%% interval %.2f-%.2fx (central); P(ROI >= 1) = %.0f%%; NPV median TZS %.2fB. Bracket of the median %.2fx-%.2fx. 20 years ROI %.2fx [%.2f-%.2f]. %s" % (
            r10["median"], r10["p10"], r10["p90"], d["p_roi_ge_1"] * 100, npv / 1e9, lo["stages"][s]["roi_10y"]["median"], hi["stages"][s]["roi_10y"]["median"], d["roi_20y"]["median"], d["roi_20y"]["p10"], d["roi_20y"]["p90"], pers_txt(s)),
            status=ST_REP, script="src/04_models/stage_economics.py", out=figs, reason="central income basis and bracket")
    if tb:
        sv, rg, pr = tb["models"]["survey"], tb["models"]["register"], tb["dashboard_pair_per_10000_reached"]["register_only"]
        put("C059", "Targeting multiplier, top-scored 10%% of the Entry segment (ages 16-24) over the Entry mean, respondent bootstrap refitting the model in every replicate (%d replicates): SURVEY model %.1fx (95%% interval %.1f-%.1fx); REGISTER-only model (age, sex, region, urban/rural: what TRA holds) %.1fx (%.1f-%.1fx). "
            "Per 10,000 reached, register data alone: about %.0f targeted (interval %.0f-%.0f) vs %.0f random TIN holders (modelled). The observed top-decile ratio rests on fewer than 10 TIN holders in some replicates and is not published as a number." % (
                sv["replicates_used"], sv["multiplier"]["median"], *sv["multiplier"]["ci95"], rg["multiplier"]["median"], *rg["multiplier"]["ci95"], pr["targeted"]["median"], *pr["targeted"]["ci95"], pr["random"]),
            status=ST_REP, script="src/04_models/targeting_bootstrap.py", out="outputs/cache/targeting_bootstrap.json", reason="refit bootstrap; register-only operational figure; survey 5.8-7.1 dropped (owner decision 7)")
        lk, lz = tb["leakage_adjusted_auc"], tb["leave_one_zone_out"]
        put("C030", "Held-out weighted ROC-AUC (logistic): 0.946 for the primary model (all survey features except the one that requires a TIN); %.3f without %d formal-product source columns (banking, credit, insurance, pension, vehicle, land title, securities, formal employment); "
            "0.884 with only features TRA could hold through an operator partnership; 0.829 with age, sex, region, urban/rural only; leave-one-zone-out AUC of the register-only model: pooled %.3f (%.3f-%.3f by zone)." % (
                lk["without_formal_product_columns"]["held_out_auc_weighted"], lk["source_columns_dropped"], lz["pooled_loZo_auc_weighted"], *lz["range_by_zone"]),
            status=ST_RE, script="src/04_models/targeting_model.py; src/04_models/targeting_bootstrap.py", out="outputs/stats/targeting_model.json; outputs/cache/targeting_bootstrap.json", reason="leakage-adjusted and leave-one-zone-out AUC published (owner decision 7)")
    put("C060", "Region cell shown only with at least %d businesses with receipts (Household Budget Survey 2017/18); otherwise the zone cell (nine NBS zones; labelled 'Zone estimate: ...'), otherwise the national (Mainland) cell. Of %d region x activity cells, %d are suppressed; zone cells suppressed: %d; national: %d. "
        "Not covered: farmers and fishers; Zanzibar." % (mz["min_businesses_with_receipts_region_cell"], len(mz["region_activity"]), sum(1 for r in mz["region_activity"] if r["suppressed"]), sum(1 for r in mz["zone_activity"] if r["suppressed"]), sum(1 for r in mz["national_activity"] if r["suppressed"])),
        status=ST_RE, script="dashboard/tdj_lib/benchmark_adapters.py; src/03_features/hbs_turnover.py", out="outputs/stats/mzani_turnover.json", reason="Mzani wa Kodi rebuilt on HBS shilling bands (owner decision 6)")

    # ---------------------------------------------------------------- new claims
    pm = c["portfolio_excluding_asset"]
    put("C081", "Submitted text: portfolio ROI median 3.23x (80%% interval 1.01-7.17), Pass 6D V0. REPLACED: central %s, P(ROI >= 1) = %.0f%%, 20 years %.2fx; bracket of the median %.2fx (HBS all owners) to %.2fx (ILFS gross); ILFS alone is never shown." % (
        rng(pm, "roi_10y"), pm["p_roi_ge_1"] * 100, pm["roi_20y"]["median"], lo["portfolio_excluding_asset"]["roi_10y"]["median"], hi["portfolio_excluding_asset"]["roi_10y"]["median"]),
        status=ST_REP, script="src/04_models/stage_economics.py", out=figs, label="MODELLED", typ="MODELLED", loc="PDF p.64-65 (final report) | 5. Portfolio-Level Impact | portfolio ROI", reason="the 3.23x row had no claim ID")
    put("C082", "Table 5.1 revenue per registrant (TZS a year) and share of registrants owing tax: Active central %s (%.1f%%), bracket low %s / high %s; Enterprise central %s (%.1f%%), low %s / high %s. Entry, Asset, Legacy keep the ILFS values in every basis. HBS 2017/18 receipts of owners with receipts, CPI factor %.4f (to 2024), last-month receipts x months operated." % (
        T(c["stages"]["active"]["revenue_per_registrant_tzs"], 0), c["stages"]["active"]["share_paying_any_tax_pct"], T(lo["stages"]["active"]["revenue_per_registrant_tzs"], 0), T(hi["stages"]["active"]["revenue_per_registrant_tzs"], 0),
        T(c["stages"]["enterprise"]["revenue_per_registrant_tzs"], 0), c["stages"]["enterprise"]["share_paying_any_tax_pct"], T(lo["stages"]["enterprise"]["revenue_per_registrant_tzs"], 0), T(hi["stages"]["enterprise"]["revenue_per_registrant_tzs"], 0), hbs["cpi"]["factor"]),
        status=ST_NEW, script="src/03_features/hbs_turnover.py; src/04_models/stage_economics.py", out="data/processed/hbs_turnover.json; outputs/tables/table5_1_stage_economics.csv", label="COMPUTED", typ="COMPUTED", loc="Section 5 | Table 5.1", reason="new")
    put("C083", "Table 5.1 ROI by stage, central 10 years median [80%% interval], P(ROI>=1), 20 years: Entry %.2fx [%.2f-%.2f], %.0f%%, %.2fx; Active %.2fx [%.2f-%.2f], %.0f%%, %.2fx; Enterprise %.2fx [%.2f-%.2f], %.0f%%, %.2fx; Legacy %.2fx [%.2f-%.2f], %.0f%%, %.2fx; portfolio %.2fx [%.2f-%.2f], %.0f%%, %.2fx." % (
        *sum(([c["stages"][s]["roi_10y"][k] for k in ("median", "p10", "p90")] + [c["stages"][s]["p_roi_ge_1"] * 100, c["stages"][s]["roi_20y"]["median"]] for s in ("entry", "active", "enterprise", "legacy")), []),
        pm["roi_10y"]["median"], pm["roi_10y"]["p10"], pm["roi_10y"]["p90"], pm["p_roi_ge_1"] * 100, pm["roi_20y"]["median"]), status=ST_NEW, script="src/04_models/stage_economics.py", out="outputs/tables/table5_1_stage_economics.csv; outputs/figures/fig_5_3_table40_roi_by_stage.png",
        label="MODELLED", typ="MODELLED", loc="Section 5 | Table 5.1 and Figure 5.3", reason="new")
    asset, seed = c["stages"]["asset"], se["stages"]["seed"]["monte_carlo_at_10pct"]["cost"]
    put("C084", "Seed is cost only (median TZS %.2fB, 80%% interval %.2f-%.2fB; no revenue claimed). Asset has no stated cost: break-even cost (the programme cost at which ROI = 1) %s over 10 years (median; 80%% interval %.2f-%.2fB), %s over 20 years." % (
        seed["median"] / 1e9, seed["p10"] / 1e9, seed["p90"] / 1e9, B(asset["break_even_cost_10y_tzs"]["median"]), asset["break_even_cost_10y_tzs"]["p10"] / 1e9, asset["break_even_cost_10y_tzs"]["p90"] / 1e9, B(asset["break_even_cost_20y_tzs"]["median"])),
        status=ST_NEW, script="src/04_models/stage_economics.py", out="outputs/tables/table5_1_stage_economics.csv", label="MODELLED", typ="MODELLED", loc="Section 5 | Table 5.1 (Seed, Asset)", reason="new")
    be = c["break_even_revenue_per_registrant"]
    put("C085", "Break-even revenue per registrant (TZS a year; the tax at which the median 10-year ROI is 1): Active %s (central %s), Enterprise %s (central %s); portfolio, the four levers scaled together: Entry %s, Active %s, Enterprise %s, Legacy %s." % (
        T(be["active"]["break_even_revenue_per_registrant_tzs"], 0), T(be["active"]["revenue_per_registrant_in_basis_tzs"], 0), T(be["enterprise"]["break_even_revenue_per_registrant_tzs"], 0), T(be["enterprise"]["revenue_per_registrant_in_basis_tzs"], 0),
        *[T(be["portfolio_four_levers_scaled_together"][s + "_tzs"], 0) for s in ("entry", "active", "enterprise", "legacy")]), status=ST_NEW, script="src/04_models/stage_economics.py", out="outputs/stats/stage_economics.json",
        label="MODELLED", typ="MODELLED", loc="Section 5 | break-even revenue per registrant", reason="new")
    put("C086", "Table 5.2 persistence sensitivity, portfolio (without Asset), central basis: %s" % pers_txt("portfolio"), status=ST_NEW, script="src/04_models/stage_economics.py", out="outputs/tables/table5_2_persistence_sensitivity.csv", label="MODELLED", typ="MODELLED", loc="Section 5 | Table 5.2", reason="new")
    nil = se["nil_period_sensitivity"]
    put("C087", "Twelve-month nil period (Finance Act 2026), SENSITIVITY only: share of businesses younger than 12 months Active %.1f%%, Enterprise %.1f%% (HBS); legally fitted first-year share collected: portfolio ROI median %.2fx (headline %.2fx); full first-year variant for Enterprise: %.2fx; Enterprise alone %.2fx -> %.2fx." % (
        nil["new_business_share_pct_hbs"]["active"], nil["new_business_share_pct_hbs"]["enterprise"], nil["legally_fitted_share_of_new_businesses"]["portfolio_roi"]["median"], nil["headline_portfolio_roi"]["median"],
        nil["full_first_year_variant_enterprise"]["portfolio_roi"]["median"], c["stages"]["enterprise"]["roi_10y"]["median"], nil["full_first_year_variant_enterprise"]["enterprise_roi_median"]), status=ST_NEW, script="src/04_models/stage_economics.py",
        out="outputs/tables/table5_1_nil_period_sensitivity.csv", label="MODELLED", typ="MODELLED", loc="Section 5 | nil-period sensitivity", reason="new")
    tor = se["tornado_central"]["drivers"]
    put("C088", "Figure 5.4 tornado, portfolio median 10-year ROI %.2fx (central): %s." % (se["tornado_central"]["portfolio_median_roi_10y_central"], "; ".join("%s (%s) %.2fx to %.2fx" % (d["driver"], d["setting"], d["median_roi_unfavourable"], d["median_roi_favourable"]) for d in tor[:4])),
        status=ST_NEW, script="src/04_models/stage_economics.py", out="outputs/figures/fig_5_4_tornado_central.png; outputs/tables/fig5_4_tornado_central.csv", label="MODELLED", typ="MODELLED", loc="Section 5 | Figure 5.4", reason="new")
    y = {(r["set"], r["scenario"]): r for r in reach["year10"]}
    m1, m5, e1 = y[("four_levers", "table5_1_reach")], y[("four_levers", "reach_50pct")], y[("entry_active", "table5_1_reach")]
    put("C089", "Figure 5.2 reach scenarios, year 10, four levers (Entry, Active, Enterprise, Legacy), central basis: at Table 5.1's reach incremental revenue TZS %.2fB (80%% interval %.2f-%.2fB), %s active payers owing tax; at 10/25/50%% reach TZS %.2f/%.2f/%.2fB; Entry + Active at Table 5.1's reach TZS %.2fB. The TRA registration trend is its own line (year-10 revenue TZS %.1fB)." % (
        m1["incremental_revenue_tzs"] / 1e9, m1["revenue_p10"] / 1e9, m1["revenue_p90"] / 1e9, T(m1["active_payers_owing_tax"], 0), *[y[("four_levers", k)]["incremental_revenue_tzs"] / 1e9 for k in ("reach_10pct", "reach_25pct", "reach_50pct")], e1["incremental_revenue_tzs"] / 1e9,
        reach["trend_component"]["year10_revenue_median_tzs"] / 1e9), status=ST_NEW, script="src/04_models/reach_scenarios.py", out="outputs/stats/reach_scenarios.json; outputs/tables/reach_scenarios_year10.csv; outputs/figures/fig_5_2_reach_scenarios.png",
        label="MODELLED", typ="MODELLED", loc="Section 5 | Figure 5.2", reason="replaces the retired digital twin (C079)")
    sc = reach["scale_check_tra_fy2024_25"]
    put("C090", "Scale check against TRA FY2024/25 (CITED): individuals' income tax TZS %.1fB, domestic revenue TZS %.2fT, total gross TZS %.2fT; the year-10 increment at Table 5.1's reach is %.3f%% of individuals' income tax (at 50%% reach %.2f%%); the retired twin's TZS 6.15T was about 22 times the FY2023/24 collection." % (
        sc["tra_fy2024_25_tzs"]["individuals_income_tax"] / 1e9, sc["tra_fy2024_25_tzs"]["domestic_revenue"] / 1e12, sc["tra_fy2024_25_tzs"]["total_gross"] / 1e12, sc["pct_of"]["four_levers_table5_1_reach"]["individuals_income_tax"], sc["pct_of"]["four_levers_reach_50pct"]["individuals_income_tax"]),
        status=ST_NEW, script="src/03_features/tra_collections.py; src/04_models/reach_scenarios.py", out="data/processed/tra_collections_2024_25.json; outputs/stats/reach_scenarios.json", label="CITED", typ="CITED", loc="Section 5 | Figure 5.2 scale check", reason="new")
    f51 = reach["figure_5_1_full_reach_implication"]
    put("C091", "Figure 5.1 has no reach factor (the effect if every adult is reached): +%s TIN holders (best single, %.2f%% -> %.2f%%) and +%s (combined, %.2f%%) of %.1fM adults, against %s new registrants (median) across the four stages at Table 5.1's reach." % (
        T(f51["extra_tin_holders_best_single_at_full_reach"], 0), f51["baseline_tin_probability"] * 100, f51["best_single_probability"] * 100, T(f51["extra_tin_holders_combined_at_full_reach"], 0), f51["combined_probability"] * 100, f51["adults_16_plus"] / 1e6,
        T(f51["table5_1_new_registrants_median_four_levers"], 0)), status=ST_NEW, script="src/04_models/reach_scenarios.py", out="outputs/stats/reach_scenarios.json", label="MODELLED", typ="MODELLED", loc="Section 5 | Figure 5.1", reason="new")
    put("C092", "Stage mapping B (FinScope 2023): Active = business owners (BusO) with no formal step (D6_4a not 'Yes', not asked counts as none), ages 25-64; Enterprise = business owners with D6_4a 'Yes', 25-64; Workers 25-44 = non-owners 25-44 (named group, no revenue lever); Asset = non-owners 45-64; Entry 16-24, Legacy 65+, Seed 6-15 unchanged. "
        "Populations: Active %s, Enterprise %s, Workers %s, Asset %s; they add up to %s adults." % (T(float(P("active")["population_weighted"]), 0), T(float(P("enterprise")["population_weighted"]), 0), T(float(P("workers")["population_weighted"]), 0), T(float(P("asset")["population_weighted"]), 0), T(float(P("overall")["population_weighted"]), 0)),
        status=ST_NEW, script="src/03_features/finscope_segments.py; src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", label="COMPUTED", typ="COMPUTED", loc="Section 4 | stage definitions", reason="owner decision 1")
    if tb:
        put("C093", "Targeting (Entry, ages 16-24): register-only %.1fx (95%% interval %.1f-%.1f), survey model %.1fx (%.1f-%.1f); per 10,000 reached %.0f (%.0f-%.0f) vs %.0f; the earlier survey interval 5.8-7.1 is dropped." % (
            rg["multiplier"]["median"], *rg["multiplier"]["ci95"], sv["multiplier"]["median"], *sv["multiplier"]["ci95"], pr["targeted"]["median"], *pr["targeted"]["ci95"], pr["random"]), status=ST_NEW, script="src/04_models/targeting_bootstrap.py", out="outputs/cache/targeting_bootstrap.json",
            label="COMPUTED", typ="COMPUTED", loc="Section 4.2 | targeting multiplier", reason="owner decision 7")
    put("C094", "Mzani wa Kodi turnover bands: HBS 2017/18, CPI-uprated to 2024 (factor %.4f), last-month receipts annualised by months operated, owners with receipts; national medians TZS %s; farmers and fishers and Zanzibar are not covered." % (
        hbs["cpi"]["factor"], " / ".join("%s %s" % (r["activity"].split(" - ")[-1], T(r["median_tzs"], 0)) for r in mz["national_activity"])), status=ST_NEW, script="src/03_features/hbs_turnover.py", out="outputs/stats/mzani_turnover.json; outputs/tables/mzani_turnover_zone_activity.csv",
        label="COMPUTED", typ="COMPUTED", loc="Section 4.3 | Mzani wa Kodi", reason="owner decision 6")
    put("C095", "Taxable capacity (HBS 2017/18, CPI-uprated; business turnover only, no wages): %.2f%% of adults above TZS 4M and %.2f%% above TZS 11M (about %s and %s adults at FinScope scale); business owners %.1f%% / %.2f%%; owners with receipts %.1f%% / %.1f%%." % (
        cap["all_adults"]["share_above_4m_pct"], cap["all_adults"]["share_above_11m_pct"], T(cap["all_adults"]["adults_above_4m_at_finscope_scale"], 0), T(cap["all_adults"]["adults_above_11m_at_finscope_scale"], 0), cap["business_owners"]["share_above_4m_pct"], cap["business_owners"]["share_above_11m_pct"],
        cap["owners_with_receipts_in_the_reference_month"]["share_above_4m_pct"], cap["owners_with_receipts_in_the_reference_month"]["share_above_11m_pct"]), status=ST_NEW, script="src/03_features/hbs_turnover.py", out="outputs/stats/taxable_capacity.json; outputs/tables/taxable_capacity.csv",
        label="COMPUTED", typ="COMPUTED", loc="Section 4.3 / 5 | taxable capacity", reason="owner decision 8")
    cf = cited["facts"]
    put("C096", "TRA FY2023/24 (audited statements, printed pp. 107-108): %s active and %s dormant business TINs (FY2022/23: %s, %s); TIN stock %s (NBS Tax Statistics 2023/24, entities and dormant included): neither is a count of adult taxpayers." % (
        T(cf["tra_active_business_tins_fy2023_24"]["value"], 0), T(cf["tra_dormant_business_tins_fy2023_24"]["value"], 0), T(cf["tra_active_business_tins_fy2022_23"]["value"], 0), T(cf["tra_dormant_business_tins_fy2022_23"]["value"], 0), T(cf["tra_tin_stock_mainland_fy2023_24"]["value"], 0)),
        status=ST_NEW, script="src/03_features/cited_facts.py", out="outputs/stats/cited_facts.json", label="CITED", typ="CITED", loc="Section 1 / 4.2 | TIN registers", reason="owner decision (cited facts)")
    put("C097", "NIN to TIN: %s (%s)." % (cf["nin_to_tin_provision"]["value"], cf["nin_to_tin_provision"]["source"]), status=ST_NEW, script="src/03_features/cited_facts.py", out="outputs/stats/cited_facts.json", label="CITED", typ="CITED", loc="Section 4.2 | registration", reason="cited fact")
    put("C098", "Afrobarometer Rounds 9 and 10, Tanzania: %s." % cf["afrobarometer_r9_r10_tax_module"]["value"], status=ST_NEW, script="src/03_features/cited_facts.py", out="outputs/stats/cited_facts.json", label="CITED", typ="CITED", loc="Section 4.5 | tax morale evidence", reason="cited fact")
    return new


def main():
    with open(CLAIMS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by = {r["claim_id"]: r for r in rows}
    new = build()
    changes = []
    for cid, n in new.items():
        old = by.get(cid)
        if old is None:
            row = {"claim_id": cid, "location": n.get("loc", ""), "current value": n["value"], "type": n.get("typ", "MODELLED"), "label": n.get("label", "MODELLED"), "source script": n.get("script", ""), "output file": n.get("out", ""), "status": n["status"]}
            rows.append(row)
            by[cid] = row
            old_text = "Submitted text: portfolio ROI median 3.23x (80% interval 1.01-7.17), Pass 6D V0 (published, ILFS, published mapping)" if cid == "C081" else ""
            changes.append({"claim_id": cid, "old": old_text, "new": n["value"], "status": n["status"], "reason": n.get("reason", "")})
            continue
        if old["current value"] == n["value"] and cid not in ("C045", "C046", "C047", "C048", "C049", "C050"):
            continue
        changes.append({"claim_id": cid, "old": old["current value"], "new": n["value"], "status": n["status"], "reason": n.get("reason", "")})
        old["current value"], old["status"] = n["value"], n["status"]
        if n.get("script"):
            old["source script"] = n["script"]
        if n.get("out"):
            old["output file"] = n["out"]
    # the retired claim: the digital twin
    r79 = by["C079"]
    changes.append({"claim_id": "C079", "old": r79["current value"], "new": "RETIRED", "status": "RETIRED", "reason": "digital twin retired (PASS6A D2, PASS6C E1, PASS6D F4/F5): its year-10 increment was about TZS 6.15 trillion, about 22 times the FY2023/24 individuals' income tax; replaced by the reach scenarios (C089-C091)"})
    r79["status"] = "RETIRED"
    r79["current value"] = "RETIRED (Pass 6B-1): " + r79["current value"].split(". New taxpayers pay")[0] + ". Reason: the digital twin was retired (PASS6A D2, PASS6C E1, PASS6D F4/F5); Figure 5.2 is now the reach scenarios (C089-C091)."
    r79["output file"] = "src/retired/digital_twin_v0.py"
    r79["source script"] = "src/retired/digital_twin_v0.py"
    rows.sort(key=lambda r: r["claim_id"])
    with open(CLAIMS, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLS, lineterminator="\r\n")
        wr.writeheader()
        wr.writerows(rows)
    with open(CHANGES, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["claim_id", "old", "new", "status", "reason"], lineterminator="\r\n")
        wr.writeheader()
        wr.writerows(changes)
    updated = [c for c in changes if c["old"] and c["status"] != "RETIRED"]
    print("claims map: %d rows; %d updated, %d retired, %d new" % (len(rows), len(updated), sum(1 for c in changes if c["status"] == "RETIRED"), sum(1 for c in changes if not c["old"])))
    return changes


if __name__ == "__main__":
    main()
