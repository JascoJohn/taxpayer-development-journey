"""E3.6 - sign-off sheet for a review session: every register row that is ASSUMPTION or UNKNOWN and NOT yet signed off.

Reads docs/assumptions_register.csv (value, basis class, rationale, what it feeds, sensitivity, john_signoff) and docs/assumption_sensitivity.json
(+/-20% re-runs: does a change move a published value by more than 5%?) and writes docs/signoff_sheet.csv and docs/signoff_sheet.md.

Rows are grouped by area (morale model, agent model, tier, digital twin, stage economics, macro, other). Within a group the rows that feed a published claim or a dashboard
value come first; rows that feed nothing published go into the final section "model internals: document only" (one table). Each row carries a recommendation
(SIGN as is / REVISE / RETIRE) with its reason: the recommendations are the analyst's, for the owner's decision. Not part of run_all.py (it needs the sensitivity file).

Run:  python src/tools/build_signoff_sheet.py
"""

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

GROUPS = [("morale", "Morale model"), ("agent", "Agent model"), ("tier", "Tier"), ("twin", "Digital twin"), ("stage", "Stage economics"), ("macro", "Macro"), ("other", "Other")]
SIGN, REVISE, RETIRE = "SIGN as is", "REVISE", "RETIRE"


def group_of(key):
    if key.startswith("tax_morale."):
        return "morale"
    if key.startswith("agents."):
        return "agent"
    if key.startswith("tier."):
        return "tier"
    if key.startswith("twin.") or key.startswith("base."):
        return "twin"
    if key.startswith("stage.") or key.startswith("tax."):
        return "stage"
    if key.startswith("macro."):
        return "macro"
    return "other"


def feeds_published(feeds):
    """A row feeds something published when its text names a claim or a dashboard value."""
    return bool(re.search(r"C\d{3}", feeds or "")) or "dashboard" in (feeds or "").lower()


# recommendations: (pattern on the key, verdict, reason). {s} is replaced by the sensitivity text of the row. First match wins.
def recommend(key, ctx):
    s = ctx["sens"]
    eff = ctx["effective_pit_rate_pct"]
    R = [
        (r"^tax_morale\.weight\.", SIGN, "Judgement weights of the five drivers (literature direction, no data fix them). They set the composition of the index; the level is anchored to the observed TIN rate and the scale is fitted, so the effect sizes are only partly exposed. Keep the label 'assumed weights'. " + s),
        (r"^tax_morale\.trust_penalty", RETIRE, "The penalty applies only when the trust score is below 0.5; the data baseline is 0.785 (Afrobarometer), so it never binds in the published runs. " + s),
        (r"^tax_morale\.effect\.", SIGN, "Assumed driver uplift of one intervention: the ONLY source of the size of Fig 5.1's solo and combined effects, which are therefore assumed uplifts, not findings. Sign it as an assumption, or supply a study (Rwanda RRA, HMRC nudge trials) to replace it. " + s),
        (r"^tax_morale\.combined_discount", SIGN, "Diminishing-returns factor on the combined effect of several interventions (0.6); also drives the agent model's pair of interventions. A modelling convention, not measured. " + s),
        (r"^agents\.edu\.min_age", SIGN, "Definition of who civic tax education reaches (urban adults aged 18 and over); a reach rule, not an effect size. " + s),
        (r"^agents\.p_comply\.(trust|morale|income|mm)_weight", SIGN, "After Block E3.1 these weights only rank which agents register first (the LEVEL of registration is calibrated by the conversion rate and the intercept, which absorb the scale). They cannot be fitted with the two TRA targets. Signing them as ranking weights unblocks C062. " + s),
        (r"^tier\.initial_tenure", SIGN, "Starting tenure (1-3 years) of already-registered agents; a design choice that only affects the first years of the tier chart. " + s),
        (r"^tier\.filing\.clip", SIGN, "Bounds of the filing-reliability trait (0.05-0.99); design bounds. " + s),
        (r"^tier\.threshold\.", SIGN, "Ngazi tier threshold as displayed on the Enterprise page and stated in the report (design parameter): sign as the report's own definition. " + s),
        (r"^base\.presumptive_tax_rate", SIGN, "3% equals the statutory marginal rate for turnover of TZS 4-11 million (First Schedule para 2(3)); could be reclassified DATA. " + s),
        (r"^twin\.mm\.penetration_cap", SIGN, "NEW (E3.3): ceiling of mobile-money penetration (90% of adults; FinScope 2023: 71.7%). A structural assumption; not signed yet. " + s),
        (r"^twin\.mm\.penetration_gap_closure", SIGN, "NEW (E3.3): share of the remaining gap to the cap closed each year (10%, about 1.8 points a year from today). A structural assumption; not signed yet. " + s),
        (r"^twin\.school_curriculum", RETIRE, "The school-curriculum policy is switched off in both published scenarios, so these constants never act. " + s),
        (r"^twin\.social_norm\.feedback|^twin\.cap\.social_norm", RETIRE, "The social-norm score is updated but never enters registrations or revenue: a dead state variable. " + s),
        (r"^twin\.default\.trust_improvement_annual|^twin\.policy\.trust_improvement_annual|^twin\.cap\.trust", SIGN, "Scenario inputs for the drift of trust (1% a year without policy, 2.5% with it, capped at 0.85); they act through the trust multiplier. Label as scenario assumptions. " + s),
        (r"^twin\.trust_multiplier\.slope", SIGN, "Structural elasticity of registration to trust (x2); no panel data link them here. Scenario assumption. " + s),
        (r"^twin\.cap\.compliance_rate", SIGN, "Ceiling of registrations per adult (0.8): a structural cap that bounds the rate; the adult-population ceiling (E3.3) is now the hard constraint. " + s),
        (r"^twin\.ussd\.conversion", SIGN, "Yearly share of unregistered mobile-money users who register when the nudge is fully scaled (15%); a scenario input with no trial evidence. The policy twin's registrations scale with it; label as a scenario. " + s),
        (r"^twin\.policy\.ussd_nudge_scale", SIGN, "Policy scenario: nudge deployed at 60% of full scale; a scenario choice. " + s),
        (r"^twin\.presumptive\.uplift_factor", SIGN, "Share of presumptive-tax potential assumed collected once simplification is on (0.5); no collection data. Immaterial: the term adds under 0.2% to the policy scenario's revenue, so it does not move a published value. Scenario input. " + s),
        (r"^interventions\.", RETIRE, "Typed cost and revenue of the old intervention list; Table 40 is now computed (Block E2.5) and no claim reads these. They feed only the unpublished cost-benefit and optimizer blocks: retire the blocks with them. " + s),
        (r"^simulation\.(n_agents|n_years|random_seed)", SIGN, "Simulation design choice (size, horizon, seed). The 'yes' for size and seed is on the Entry-tier share (about 0.2% of agents), so the absolute change is under 0.05 percentage points; the larger shares move little. " + s),
        (r"^disclosure\.", SIGN, "Disclosure rule of the project (minimum base 10; low-precision numerator 10); a publication policy, not a model constant. " + s),
        (r"^dashboard\.", SIGN, "Design parameter stated in the report and on the dashboard; sign as the report's own definition. " + s),
    ]
    for pat, verdict, why in R:
        if re.search(pat, key):
            return verdict, why
    return SIGN, "Design choice; no data bear on it. " + s


def main():
    reg_path = paths.ASSUMPTIONS_REGISTER
    with open(reg_path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)]
    with open(paths.ASSUMPTION_SENSITIVITY, encoding="utf-8") as f:
        sens_json = json.load(f)
    sens = sens_json["results"]
    design = sens_json.get("design_rows", {})
    eff = {"rate": float("nan"), "income": "n/a"}          # the Block E3 REVISE rows (twin tax rate, levy) were resolved in Block F1 / F2
    out = []
    for r in rows:
        if r["basis_class"] not in ("ASSUMPTION", "UNKNOWN") or r["john_signoff"]:
            continue
        key = r["key"]
        if key in design:
            stext = design[key]["text"]
            flag = design[key]["flag"]
        else:
            stext = r["sensitivity"]
            res = sens.get(key)
            flag = res["flag"] if res else "not computed"
        verdict, why = recommend(key, {"sens": "Sensitivity (+/-20%%): %s." % stext, "effective_pit_rate_pct": eff})
        pub = feeds_published(r["feeds"])
        out.append({"group": group_of(key), "key": key, "value": r["value"], "basis_class": r["basis_class"], "rationale_or_source": r["source_reference_rationale"],
                    "feeds": r["feeds"], "moves_a_published_value_by_more_than_5pct": {">5%": "yes", "<=5%": "no", "no effect": "no effect"}.get(flag, flag), "sensitivity_detail": stext,
                    "recommendation": verdict, "recommendation_detail": why, "section": "published" if pub else "internals"})
    order = {g: i for i, (g, _) in enumerate(GROUPS)}
    out.sort(key=lambda x: (x["section"] == "internals", order[x["group"]], 0 if x["moves_a_published_value_by_more_than_5pct"] == "yes" else 1, x["key"]))
    cols = ["group", "key", "value", "basis_class", "rationale_or_source", "feeds", "moves_a_published_value_by_more_than_5pct", "sensitivity_detail", "recommendation", "recommendation_detail", "section"]
    csv_path = os.path.join(paths.ROOT, "docs", "signoff_sheet.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out)

    # ------------------------------------------------------------ markdown
    names = dict(GROUPS)
    L = ["# Sign-off sheet (Block E3.6)", "",
         "Every register row that is ASSUMPTION or UNKNOWN and NOT yet signed off, for a review session. Source: `docs/assumptions_register.csv` and the +/-20% sensitivity runs "
         "(`docs/assumption_sensitivity.json`). Recommendations are the analyst's; the decision is the owner's. The same rows are in `docs/signoff_sheet.csv`.", ""]
    L += ["## Counts", "", "| Area | Rows to sign | feed a published claim or dashboard value | model internals | ASSUMPTION | UNKNOWN | SIGN as is | REVISE | RETIRE |", "|---|---|---|---|---|---|---|---|---|"]
    tot = [0] * 8
    for g, nm in GROUPS:
        rs = [x for x in out if x["group"] == g]
        c = [len(rs), sum(1 for x in rs if x["section"] == "published"), sum(1 for x in rs if x["section"] == "internals"), sum(1 for x in rs if x["basis_class"] == "ASSUMPTION"),
             sum(1 for x in rs if x["basis_class"] == "UNKNOWN"), sum(1 for x in rs if x["recommendation"] == SIGN), sum(1 for x in rs if x["recommendation"] == REVISE), sum(1 for x in rs if x["recommendation"] == RETIRE)]
        tot = [a + b for a, b in zip(tot, c)]
        L.append("| %s | %s |" % (nm, " | ".join(str(v) for v in c)))
    L.append("| **Total** | %s |" % " | ".join("**%d**" % v for v in tot))
    L += ["", "Sensitivity column: 'yes' = a +/-20% change moves at least one published value of the function by more than 5% (relative); 'no' = it does not; 'no effect' = the published values do not move at all "
          "(the constant is inactive in the published runs). Within each area the rows that feed a published claim come first, and those that move a published value by more than 5% come first among them.", ""]
    for g, nm in GROUPS:
        rs = [x for x in out if x["group"] == g and x["section"] == "published"]
        L += ["## %s" % nm, ""]
        if not rs:
            L += ["No unsigned row feeds a published claim in this area.", ""]
            continue
        L += ["| key | value | class | rationale or source | feeds | moves a published value >5%? | recommendation |", "|---|---|---|---|---|---|---|"]
        for x in rs:
            L.append("| `%s` | %s | %s | %s | %s | %s | **%s**: %s |" % (x["key"], x["value"].replace("|", "/")[:60], x["basis_class"], x["rationale_or_source"].replace("|", "/")[:260], x["feeds"].replace("|", "/")[:120],
                                                                        x["moves_a_published_value_by_more_than_5pct"], x["recommendation"], x["recommendation_detail"].replace("|", "/")))
        L.append("")
    ins = [x for x in out if x["section"] == "internals"]
    L += ["## Model internals: document only", "", "These rows feed no published claim and no dashboard value; they are listed so that the register is complete.", "",
          "| area | key | value | class | what it is | recommendation |", "|---|---|---|---|---|---|"]
    for x in ins:
        L.append("| %s | `%s` | %s | %s | %s | **%s** |" % (names[x["group"]], x["key"], x["value"].replace("|", "/")[:40], x["basis_class"], x["rationale_or_source"].replace("|", "/")[:160], x["recommendation"]))
    L.append("")
    with open(os.path.join(paths.ROOT, "docs", "signoff_sheet.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("sign-off sheet: %d rows (%d published, %d internals); %s" % (len(out), len(out) - len(ins), len(ins), {n: sum(1 for x in out if x["group"] == g) for g, n in GROUPS}))
    return out


if __name__ == "__main__":
    main()
