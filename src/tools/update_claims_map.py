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
CHANGES = os.path.join(paths.ROOT, "docs", "claims_map_6b2_changes.csv")        # Pass 6B-2 record (the Pass 6B-1 record is docs/claims_map_6b1_changes.csv, written by the earlier run)
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
    seg_txt = lambda s, name: "%s %.2f%% (95%% CI %.2f-%.2f; n=%s, %s respondents reporting a TIN)" % (name, float(P(s)["tin_rate_pct"]), float(P(s)["ci95_low_pct"]), float(P(s)["ci95_high_pct"]), P(s)["n_unweighted"], P(s)["tin_holders_unweighted"])
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
    put("C017", "Survey-reported TIN holding (adults reporting a TIN): overall %.2f%%; %s; %s; %s; %s; %s; %s (stage mapping B)" % (float(P("overall")["tin_rate_pct"]), seg_txt("entry", "Entry"), seg_txt("active", "Active"), seg_txt("enterprise", "Enterprise"), seg_txt("workers", "Non-business owners 25-44"), seg_txt("asset", "Asset"), seg_txt("legacy", "Legacy")),
        status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/stats/tin_reconciliation.json; outputs/tables/tin_by_segment.csv", reason="stage mapping B (owner decision 1)")
    put("C031", "%s; Active population %s (business owners without a formal step, ages 25-64; was 12,110,885 = non-owners 25-44, now the named group Non-business owners 25-44, population %s, no revenue lever)" % (
        seg_txt("active", "Active"), T(float(P("active")["population_weighted"]), 0), T(float(P("workers")["population_weighted"]), 0)), status=ST_RE, script="src/03_features/finscope_segments.py; src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="stage mapping B")
    put("C034", "%s" % T(float(P("enterprise")["population_weighted"]), 0), status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="stage mapping B: owners with a formal step, ages 25-64 (was 3,488,899 = all owners 25-64)")
    put("C035", "%.1f%% report holding a TIN (survey-reported; %s). Registration/licence share: NOT 46.9%%: 20.8%% of non-agricultural self-employed (headline base), 13.7%% of all workers, 32.2%% of non-agricultural private-business workers" % (
        float(P("enterprise")["tin_rate_pct"]), seg_txt("enterprise", "Enterprise")), status=ST_RE, script="src/03_features/ilfs_indicators.py; src/03_features/tin_by_segment.py", out="outputs/stats/ilfs_summary.json; outputs/tables/tin_by_segment.csv", reason="stage mapping B")
    put("C072", "%.2fM (Active: informal business owners 25-64); Non-business owners 25-44 %.1fM" % (float(P("active")["population_weighted"]) / 1e6, float(P("workers")["population_weighted"]) / 1e6), status=ST_RE, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", reason="Figure 4.10 shows the former Active (12.1M); under mapping B that group is Non-business owners 25-44")
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
        "Not covered: farmers and fishers; Zanzibar." % (mz["min_businesses_with_receipts_region_cell"], len(mz["region_activity"]), sum(1 for r in mz["region_activity"] if r.get("suppressed") or r.get("withheld")), sum(1 for r in mz["zone_activity"] if r.get("suppressed") or r.get("withheld")), sum(1 for r in mz["national_activity"] if r.get("suppressed") or r.get("withheld"))),
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
    put("C091", "Figure 5.1 has no reach factor (the effect if every adult is reached): +%s adults reporting a TIN (best single, %.2f%% -> %.2f%%) and +%s (combined, %.2f%%) of %.1fM adults, against %s new registrants (median) across the four stages at Table 5.1's reach." % (
        T(f51["extra_tin_holders_best_single_at_full_reach"], 0), f51["baseline_tin_probability"] * 100, f51["best_single_probability"] * 100, T(f51["extra_tin_holders_combined_at_full_reach"], 0), f51["combined_probability"] * 100, f51["adults_16_plus"] / 1e6,
        T(f51["table5_1_new_registrants_median_four_levers"], 0)), status=ST_NEW, script="src/04_models/reach_scenarios.py", out="outputs/stats/reach_scenarios.json", label="MODELLED", typ="MODELLED", loc="Section 5 | Figure 5.1", reason="new")
    put("C092", "Stage mapping B (FinScope 2023): Active = business owners (BusO) with no formal step (D6_4a not 'Yes', not asked counts as none), ages 25-64; Enterprise = business owners with D6_4a 'Yes', 25-64; Non-business owners 25-44 = non-owners 25-44 (named group, no revenue lever); Asset = non-owners 45-64; Entry 16-24, Legacy 65+, Seed 6-15 unchanged. "
        "Populations: Active %s, Enterprise %s, non-business owners 25-44 %s, Asset %s; they add up to %s adults." % (T(float(P("active")["population_weighted"]), 0), T(float(P("enterprise")["population_weighted"]), 0), T(float(P("workers")["population_weighted"]), 0), T(float(P("asset")["population_weighted"]), 0), T(float(P("overall")["population_weighted"]), 0)),
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

    # ---------------------------------------------------------------- Pass 6B-2: claims for the new text (C099 onwards) and survey-reported wording
    ST_6B2 = "NEW (Pass 6B-2): ADD TO TEXT"
    v = J(os.path.join(paths.ROOT, "_archive", "diagnostics", "pass6b2", "verification.json"))
    v1, v5, v3 = v["V1_figure_5_1_12_0_percent"], v["V5_small_checks"], v["V3_tzs_306b_comparison"]
    g = v1["separate_gains_pct_points"]
    put("C099", "Figure 5.1, like for like: today's survey-reported rate %.2f%% plus the six separate gains (%s percentage points; %.2f in all) = %.2f%%, against the combined model's %.2f%%: the combined result is below the sum of the separate gains (diminishing returns); the 12.0%% of the earlier text is the baseline plus the sum of the gains." % (
        v1["baseline_pct"], ", ".join("%.2f" % x for x in g.values()), v1["sum_of_gains_pct_points"], v1["baseline_plus_sum_pct"], v1["combined_pct"]), status=ST_6B2, script="src/04_models/economic_model.py", out="outputs/stats/economic_model.json",
        label="MODELLED", typ="MODELLED", loc="Section 5.2 | Figure 5.1 cautions", reason="V1: what 12.0% is")
    e = v5["entry_break_even_persistence_20y_age_path"]
    put("C100", "Entry's break-even yearly persistence over 20 years (age-earnings path, central basis) is %.3f: 12-month retention %.0f%% and 24-month retention (persistence squared) %.0f%%, the retention at which Entry pays back (PASS6A D1, reproduced with the current code)." % (
        e["persistence"], e["retention_12_months_pct"], e["retention_24_months_pct"]), status=ST_6B2, script="src/04_models/stage_economics.py; _archive/diagnostics/pass6b2/verification.py", out="_archive/diagnostics/pass6b2/verification.json",
        label="MODELLED", typ="MODELLED", loc="Section 7.3 | economic reference points", reason="PASS6A D1")
    pw = v5["power_calculation"]
    put("C101", "Illustrative sample size (not a result): detecting a rise in first filing from 2%% to 3%% (two-sided 5%% test, 80%% power, two-proportion z test) needs about %s people per compared group (%.0f)." % ("3,800", pw["n_per_group_pooled_variance"]), status=ST_6B2,
        script="_archive/diagnostics/pass6b2/verification.py", out="_archive/diagnostics/pass6b2/verification.json", label="ILLUSTRATIVE (design example)", typ="n/a", loc="Section 7.2 | Entry trial design", reason="illustrative power calculation")
    put("C102", "Scale of the reach scenarios: at 50%% reach the year-10 increment raises the tax-to-GDP ratio by %.4f percentage points (below 0.001); the registration trend's year-10 revenue (TZS %.0fB) is %.0f times the largest lever. Basis of the comparison with TRA FY2024/25 individuals' income tax (TZS 306B, nominal): modelled revenue is in constant 2024 TZS, %.0f%% presumptive tax (Active, Enterprise) and %.0f%% personal income tax on ILFS earnings of Entry and Legacy outside the formal net, of which about %.1f%% of the total is employee cash earnings (PAYE-type, outside the 'Individuals' line)." % (
        v3["tax_to_gdp_year10_50pct_reach_pp"], v3["trend_revenue_year10_tzs"] / 1e9, v3["trend_over_largest_lever"], v3["share_of_year10_increment_by_tax_type_at_table_5_1_reach"]["presumptive_tax_active_enterprise_pct"],
        v3["share_of_year10_increment_by_tax_type_at_table_5_1_reach"]["personal_income_tax_entry_legacy_pct"], v3["paye_type_wage_share"]["approx_pct_of_total_modelled_revenue"]), status=ST_6B2, script="src/04_models/reach_scenarios.py; _archive/diagnostics/pass6b2/v3_composition.py",
        out="outputs/stats/reach_scenarios.json; _archive/diagnostics/pass6b2/v3_composition.json", label="MODELLED", typ="MODELLED", loc="Section 5.3 | Figure 5.2 footnote", reason="V3")
    t16 = v5["figure_4_16a_tier_year10"]
    put("C103", "Figure 4.16a (modelled, year 10): %.1f%% of adults registered; of those, %.1f%% are at Silver or above and %.1f%% below it." % (t16["registered_pct"], t16["silver_or_above_share_of_registered_pct"], 100 - t16["silver_or_above_share_of_registered_pct"]), status=ST_6B2,
        script="src/04_models/economic_model.py", out="outputs/stats/economic_model.json", label="MODELLED", typ="MODELLED", loc="Section 4.4 | Figure 4.16a", reason="draft 4.4-3 numbers confirmed")
    ft = v5["finscope_timing"]
    put("C104", "FinScope Tanzania 2023 fieldwork: %s. Item C27: '%s'" % (ft["fieldwork"], ft["item_C27"]), status=ST_6B2, script="_archive/diagnostics/pass6b2/verification.py", out="_archive/diagnostics/pass6b2/verification.json", label="CITED", typ="CITED", loc="Section 1 | survey and register", reason="V5 FinScope timing")
    ob = se["income_bases"]
    put("C105", "Why the revenue estimates are bracketed: in the HBS reference month 58%% of business owners had no receipts (42%% had); revenue per registrant on ILFS 2024 gross receipts is %.1f times the HBS central value for Active (TZS %s vs %s) and %.1f times for Enterprise (TZS %s vs %s)." % (
        ob["high"]["stages"]["active"]["revenue_per_registrant_tzs"] / ob["central"]["stages"]["active"]["revenue_per_registrant_tzs"], T(ob["high"]["stages"]["active"]["revenue_per_registrant_tzs"], 0), T(ob["central"]["stages"]["active"]["revenue_per_registrant_tzs"], 0),
        ob["high"]["stages"]["enterprise"]["revenue_per_registrant_tzs"] / ob["central"]["stages"]["enterprise"]["revenue_per_registrant_tzs"], T(ob["high"]["stages"]["enterprise"]["revenue_per_registrant_tzs"], 0), T(ob["central"]["stages"]["enterprise"]["revenue_per_registrant_tzs"], 0)),
        status=ST_6B2, script="src/03_features/hbs_turnover.py; src/04_models/stage_economics.py", out="data/processed/hbs_turnover.json; outputs/stats/stage_economics.json", label="COMPUTED", typ="COMPUTED", loc="Section 4.3 | limitation box; Section 5.3", reason="draft 4.3-8")
    put("C106", "About one adult in %.0f has business turnover above TZS 4 million (%.2f%% of adults; HBS 2017/18, uprated to 2024 prices)." % (v5["one_in_nine_and_7_4"]["one_adult_in"], cap["all_adults"]["share_above_4m_pct"]), status=ST_6B2, script="src/03_features/hbs_turnover.py", out="outputs/stats/taxable_capacity.json",
        label="COMPUTED", typ="COMPUTED", loc="Executive Summary; Section 3.3", reason="1 / 1.19% = 83.7 (the draft said 85)")
    put("C107", "FinScope Tanzania 2023: %s of %s adults (%.2f%%) report holding a TIN in their name (survey-reported; item C27); the TRA counts business TINs (1,851,184 active) and TINs on its register (6.272M) are different units (C096)." % (
        T(float(P("overall")["tin_holders_weighted"]), 0), T(float(P("overall")["population_weighted"]), 0), float(P("overall")["tin_rate_pct"])), status=ST_6B2, script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", label="COMPUTED", typ="COMPUTED", loc="Section 1 | survey and register", reason="draft 1-3")
    af = J(paths.AFROBAROMETER_MORALE)
    est = {x["indicator"]: x for x in af["estimates"] if x["level"] == "All adults 18+"}
    a1, a2 = est["trust_tax_office_somewhat_or_a_lot"], est["finding_out_taxes_difficult"]
    put("C108", "Afrobarometer Round 8 Tanzania 2021 (weighted): trust the tax/revenue office somewhat or a lot (Q41J) %.1f%% (95%% CI %.1f-%.1f); finding out which taxes one owes is difficult (Q46A) %.1f%% (95%% CI %.1f-%.1f); n = 2,398." % (
        a1["pct"], a1["ci95_low_pct"], a1["ci95_high_pct"], a2["pct"], a2["ci95_low_pct"], a2["ci95_high_pct"]), status=ST_6B2, script="src/03_features/afrobarometer_morale.py", out="data/processed/afrobarometer_morale.json", label="COMPUTED", typ="COMPUTED", loc="Executive Summary; Sections 3.2, 5.1", reason="figures in the text had no claim")
    ST_6B3 = "NEW (Pass 6B-3): ADD TO TEXT"
    put("C109", "Entry targeting model (FinScope 2023): the full survey model uses 1,293 encoded features, led by banking, mobile-money and other formal-financial-use items (logistic standardised coefficients; gradient boosting: mobile-money registration and tenure first). The register-only model (age, sex, region, urban/rural: four variables, 37 encoded features) is led by age (standardised logit coefficient 3.08, with its square -2.84), then region (largest: Kaskazini Unguja -0.76), urban residence 0.39 and sex 0.24; the EXTENDED variant adds mobile money, business ownership and income source (seven variables, 55 encoded features).", status=ST_6B3,
        script="src/04_models/targeting_model.py; _archive/diagnostics/pass6b3/core_coef.py", out="outputs/stats/targeting_model.json", label="COMPUTED", typ="COMPUTED", loc="Section 4.2; Entry annex", reason="D5: the 'strongest single signal' statements of Section 4.2 and the annex reconciled")
    put("C110", "Table 5.1 notes: the portfolio (without Asset) cost of TZS 3.20B (median) includes Seed's cost (median TZS 0.66B); no cost is included for the shared platform layer; revenue counts only the new registrants a stage adds (Enterprise: the businesses that begin to report a TIN, not the 26.5% who already do); Legacy's 20-year return (0.24) is below its 10-year return (0.28) because the 20-year basis follows the age-earnings path, on which mean tax falls with age above 65 (stage_economics.py: simulate(), age_earnings_multiplier).", status=ST_6B3,
        script="src/04_models/stage_economics.py", out="outputs/stats/stage_economics.json; outputs/tables/table5_1_stage_economics.csv", label="MODELLED", typ="MODELLED", loc="Section 5.3 | note under Table 5.1", reason="D6 checks")
    ST_6B4 = "NEW (Pass 6B-4): ADD TO TEXT"
    put("C111", "Enterprise segment (business owners 25-64 with a formal step, stage mapping B): %.1f%% report holding a TIN (survey-reported, 95%% CI 17.8-37.7, n = 174); so 73.5%% (100 - 26.5) of their owners do not report a TIN." % float(P("enterprise")["tin_rate_pct"]), status=ST_6B4,
        script="src/03_features/tin_by_segment.py", out="outputs/tables/tin_by_segment.csv", label="COMPUTED", typ="COMPUTED", loc="Section 7.2 | Enterprise pilot", reason="F1")
    put("C112", "Table 5.1 (central basis, 10-year, median over 10,000 draws): the stage medians of present-value revenue (Entry 0.183, Active 0.182, Enterprise 0.991, Legacy 0.199 billion) sum to TZS 1.555 billion (1.55 billion) against a portfolio median of TZS 2.001 billion (2.00 billion). Every stage's revenue is right-skewed (skewness 1.6 to 3.3, mean above median) and the stage means sum to the portfolio mean (2.280 billion), so the median of the sum exceeds the sum of the medians. Cost medians: sum 3.119 billion, portfolio 3.196 billion. Asset's median revenue (its break-even cost) is TZS 1.83 billion.", status=ST_6B4,
        script="src/04_models/stage_economics.py; _archive/diagnostics/pass6b3/sum_medians.py", out="outputs/stats/stage_economics.json", label="MODELLED", typ="MODELLED", loc="Section 5.3 | note under Table 5.1; Asset's exclusion", reason="E3, E4")
    put("C113", "Figure 5.1 separate gains (percentage points on today's 3.83%) and their stage tools (config.yaml stage.intervention_for_uptake; docs/interventions.yaml morale_model_key): USSD registration nudge 0.79 -> Entry; civic tax education 0.99 -> Legacy; mobile-money TIN bridge 1.51 -> no stage tool; community compliance norms 1.60 -> Enterprise; visible tax returns 1.56 -> Asset; presumptive tax simplification 1.74 -> Active. Seed has no morale-model key and carries no uplift.", status=ST_6B4,
        script="src/04_models/economic_model.py; config.yaml", out="outputs/stats/economic_model.json", label="MODELLED", typ="MODELLED", loc="Section 5.2 | note under Figure 5.1", reason="E2")
    put("C114", "Tax-to-GDP 2023 from the unrounded values: Tanzania 11.678% and the unweighted peer mean 13.125% (GHA 12.393, KEN 14.063, RWA 13.075, UGA 12.968), a gap of 1.447 percentage points (1.45).", status=ST_6B4,
        script="_archive/diagnostics/pass6b2/verification.py", out="_archive/diagnostics/pass6b2/verification.json", label="COMPUTED", typ="COMPUTED", loc="Section 1; Section 5.1", reason="D8")
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
    # survey-reported wording of the FinScope TIN-rate claims and the corrected 12.0% reading (Pass 6B-2)
    REWORD = {
        "C002": lambda s: "3.83% of adults report holding a TIN (survey-reported; 95% CI 3.24-4.52; n=9915, 361 respondents reporting a TIN)",
        "C011": lambda s: "3.83% (survey-reported TIN holding)",
        "C039": lambda s: s.replace("Legacy TIN rate 3.66%", "Legacy survey-reported TIN rate 3.66%").replace("25 TIN holders", "25 respondents reporting a TIN"),
        "C007": lambda s: s if "survey-reported TIN rate 5.3%" in s else s.replace("TIN rate 5.3% among mobile-money users", "survey-reported TIN rate 5.3% among mobile-money users"),
        "C056": lambda s: s if "survey-reported TIN rate 5.3%" in s else s.replace("TIN rate 5.3% among mobile-money users", "survey-reported TIN rate 5.3% among mobile-money users"),
        "C008": lambda s: s.replace("observed adult TIN rate", "observed adult survey-reported TIN rate"),
        "C055": lambda s: "Baseline 3.83% plus the sum of the six separate gains (8.19 percentage points) = 12.02%, against a combined 10.17%: the combined result is below the like-for-like sum (diminishing returns), see C099.",
    }
    for cid, fn in REWORD.items():
        r = by[cid]
        newv = fn(r["current value"])
        if newv != r["current value"]:
            changes.append({"claim_id": cid, "old": r["current value"], "new": newv, "status": "REWORDED (Pass 6B-2): survey-reported TIN wording", "reason": "Pass 6B-2: survey-reported terminology / V1"})
            r["current value"], r["status"] = newv, "REWORDED (Pass 6B-2): survey-reported TIN wording"
    # the retired claim: the digital twin
    r79 = by["C079"]
    if r79["status"] != "RETIRED":
        changes.append({"claim_id": "C079", "old": r79["current value"], "new": "RETIRED", "status": "RETIRED", "reason": "digital twin retired (PASS6A D2, PASS6C E1, PASS6D F4/F5): its year-10 increment was about TZS 6.15 trillion, about 22 times the FY2023/24 individuals' income tax; replaced by the reach scenarios (C089-C091)"})
        r79["status"] = "RETIRED"
        r79["current value"] = "RETIRED (Pass 6B-1): " + r79["current value"].split(". New taxpayers pay")[0] + ". Reason: the digital twin was retired (PASS6A D2, PASS6C E1, PASS6D F4/F5); Figure 5.2 is now the reach scenarios (C089-C091)."
        r79["output file"] = "src/retired/digital_twin_v0.py"
        r79["source script"] = "src/retired/digital_twin_v0.py"
    r14 = by["C014"]
    if r14["status"] != "RETIRED (Pass 6B-3)":
        changes.append({"claim_id": "C014", "old": r14["current value"], "new": "RETIRED", "status": "RETIRED (Pass 6B-3)", "reason": "the 42.6 percentage-point duty-voice gap is no longer published (Table 3.1 row and Executive Summary clause removed in Pass 6B-3); its two components (65.7% and 23.1%) remain as separate claims"})
        r14["current value"] = "RETIRED (Pass 6B-3): no longer published. " + r14["current value"]
        r14["status"] = "RETIRED (Pass 6B-3)"
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
