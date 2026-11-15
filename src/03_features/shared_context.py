"""
shared_context.py
═══════════════════════════════════════════════════════════════
Tanzania Policy Design Agent — Shared Context Infrastructure
═══════════════════════════════════════════════════════════════

PURPOSE
-------
Single source of truth that every agent reads before starting
and writes to when finishing. Eliminates the coordination
problem between agents — Agent 23 knows what Agent 7 decided.

HOW TO USE IN ANY AGENT
------------------------
    from shared_context import (
        load_context,
        save_context,
        log_agent_run,
        register_intervention,
        register_assumption,
        register_evidence,
        get_finscope_stat,
        get_verified_stat,
        get_lifecycle_population,
        mark_thesis_alignment,
        get_context_summary
    )

    # At the start of every agent function:
    ctx = load_context()

    # At the end of every agent function:
    save_context(ctx)
    log_agent_run(
        agent_name="your_agent_name",
        layer="L1",
        inputs_read=["key1", "key2"],
        outputs_written=["key3"],
        assumptions_made=["assumption text"],
        confidence_score=85
    )

PIPELINE EXECUTION ORDER
------------------------
1. data_layer.py          → populates evidence_store.db
2. shared_context.py      → initializes shared_context.json
3. agent_v3.py            → research engine
4. agent_v3b.py           → innovation layer
5. economic_model.py      → revenue calculations
6. agent_v3c.py           → validation layer
7. agent_v4.py            → outputs (PDF + dashboard)

FILES PRODUCED
--------------
→ shared_context.json     (main shared state)
→ audit_trail.json        (full agent run history)
→ intervention_register.json (all interventions)
→ assumption_ledger.json  (all assumptions)
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional

# ============================================================
# FILE PATHS
# ============================================================
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths
import run_meta
import re as _re
SHARED_CONTEXT_FILE    = paths.SHARED_CONTEXT
AUDIT_TRAIL_FILE       = paths.AUDIT_TRAIL
INTERVENTION_FILE      = paths.INTERVENTION_REGISTER
ASSUMPTION_FILE        = paths.ASSUMPTION_LEDGER

# ============================================================
# MASTER THESIS — never changes, every agent tags against it
# ============================================================
MASTER_THESIS = (
    "Tanzania's tax gap is not a detection problem — it is a "
    "relationship problem. TRA currently operates as a Debt "
    "Collector arriving at the end of the citizen lifecycle. "
    "Transforming TRA into a Civic Partner from birth produces "
    "sustainable voluntary compliance that no enforcement "
    "strategy can match. Behavioral lifecycle interventions "
    "represent the highest-leverage, lowest-cost path to "
    "closing Tanzania's tax gap."
)

# ============================================================
# SIX TRA OBJECTIVES
# Every intervention must map to at least one
# ============================================================
TRA_OBJECTIVES = [
    "expand_tax_base",
    "simplify_small_business_taxation",
    "improve_digital_services",
    "reduce_collection_costs",
    "use_ai_blockchain_big_data",
    "resolve_tax_disputes"
]

# ============================================================
# SIX LIFECYCLE STAGES
# ============================================================
from finscope_segments import LIFECYCLE_STAGES  # single definition (finscope_segments.py)

# ============================================================
# TANZANIA STATISTICS AND LIFECYCLE POPULATIONS
# Block F4: no typed value. Everything is read from the pipeline outputs (outputs/stats/macro_inputs.json, data/processed/twin_inputs.json,
# outputs/tables/tin_by_segment.csv, data/processed/census_age_counts.json). A statistic whose file is missing is simply absent: there is no typed fallback.
# ============================================================
def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _build_tanzania_stats():
    stats = {}

    def put(name, value, unit, source, year):
        stats[name] = {"value": value, "unit": unit, "source": source, "year": year}
    macro = _read_json(paths.MACRO_INPUTS)
    if macro:
        t, b = macro["tanzania"], macro["benchmark"]
        put("tax_to_gdp", round(t["tax_to_gdp_pct"], 2), "%", "World Bank WDI GC.TAX.TOTL.GD.ZS (macro_inputs.json)", t["latest_year"])
        put("peer_average_tax_to_gdp", round(b["benchmark_pct"], 2), "%", "simple mean of the peer countries, World Bank WDI (macro_inputs.json)", b["year"])
        put("gdp_usd", t["gdp_usd"], "USD", "World Bank WDI NY.GDP.MKTP.CD (macro_inputs.json)", t["latest_year"])
        put("tzs_per_usd", round(t["fx_tzs_per_usd"], 2), "TZS", "World Bank WDI PA.NUS.FCRF (macro_inputs.json)", t["latest_year"])
        put("gdp_tzs", t["gdp_lcu_tzs"], "TZS", "World Bank WDI NY.GDP.MKTP.CN (macro_inputs.json)", t["latest_year"])
    twin = _read_json(paths.TWIN_INPUTS)
    if twin:
        p, y = twin["parameters"], twin["base_year"]
        put("population", round(p["base_population"]["value"]), "persons", "Census 2022 10% sample projected with WDI growth (twin_inputs.json)", y)
        put("adult_population", round(p["base_adult_population"]["value"]), "persons", "FinScope Tanzania 2023, weighted adults 16+ (twin_inputs.json)", 2023)
        put("registered_taxpayers", round(p["base_registered_taxpayers"]["value"]), "registrations", "TRA via NBS Tax Statistics Report 2023/24 (twin_inputs.json): TIN registrations, Mainland, not adults", 2024)
        put("mobile_money_users", round(p["base_mobile_money_users"]["value"]), "persons", "FinScope Tanzania 2023, weighted adult mobile-money users (twin_inputs.json)", 2023)
        put("gdp_growth_rate_pct", round(p["base_gdp_growth_rate"]["value"] * 100, 2), "%", "World Bank WDI NY.GDP.MKTP.KD.ZG, mean of the last years (twin_inputs.json)", y)
    return stats


def _lifecycle_populations():
    """Lifecycle populations from the FinScope segments (outputs/tables/tin_by_segment.csv); Seed from the Census 2022 10% sample."""
    import csv
    from finscope_segments import SEED_AGE_MIN, SEED_AGE_MAX
    from census_population import seed_population_from_processed
    out = {"seed": {"population": seed_population_from_processed(), "age_range": "%d-%d" % (SEED_AGE_MIN, SEED_AGE_MAX), "source": "2022 Census 10% sample, x10 (census_population.py)"}}
    try:
        with open(paths.TIN_BY_SEGMENT_CSV, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["segment"] in ("entry", "active", "enterprise", "asset", "legacy"):
                    out[r["segment"]] = {"population": round(float(r["population_weighted"])), "age_range": r["definition"], "source": "FinScope Tanzania 2023, weighted (tin_by_segment.csv)"}
    except FileNotFoundError:
        pass
    return out


# ============================================================
# SIX CITIZEN PERSONAS
# ============================================================
PERSONAS = [
    {
        "name": "Amina",
        "type": "Student",
        "age": 17,
        "location": "Dodoma",
        "stage": "seed",
        "description": "Secondary school student, no income yet"
    },
    {
        "name": "Juma",
        "type": "Boda Boda Rider",
        "age": 24,
        "location": "Dar es Salaam",
        "stage": "entry",
        "description": "Informal transport worker, mobile money user"
    },
    {
        "name": "Fatuma",
        "type": "Market Trader",
        "age": 35,
        "location": "Mwanza",
        "stage": "active",
        "description": "Informal market seller, cash-based business"
    },
    {
        "name": "Hassan",
        "type": "Digital Creator",
        "age": 26,
        "location": "Dar es Salaam",
        "stage": "entry",
        "description": "Online content creator, mixed digital income"
    },
    {
        "name": "Mama Rehema",
        "type": "Pastoralist",
        "age": 45,
        "location": "Arusha region",
        "stage": "asset",
        "description": "Livestock owner, asset-rich but cash-poor"
    },
    {
        "name": "Bakari",
        "type": "Youth Entrepreneur",
        "age": 22,
        "location": "Mbeya",
        "stage": "entry",
        "description": "Small business starter, first-time employer"
    }
]


# ============================================================
# CONTEXT SCHEMA
# The full structure of shared_context.json
# ============================================================
def _empty_interventions() -> dict:
    return {
        "total_generated": 0,
        "total_validated": 0,
        "total_approved": 0,
        "by_stage": {s: [] for s in LIFECYCLE_STAGES},
        "by_objective": {o: [] for o in TRA_OBJECTIVES},
        "top_5": []
    }


def _empty_context() -> dict:
    """Returns a fresh empty shared context object."""
    run_meta.stamp("shared_context.json", "created_at")
    return {
        "meta": {
            "pipeline_run_id": run_meta.pipeline_run_id(),
            "agents_completed": [],
            "agents_pending": [],
            "pipeline_status": "initialized"
        },
        "thesis": {
            "statement": MASTER_THESIS,
            "alignment_scores": {},
            "challenges_identified": [],
            "refinements_suggested": []
        },
        "tanzania_stats": _build_tanzania_stats(),
        "lifecycle_populations": _lifecycle_populations(),
        "finscope": {
            "loaded": False,
            "source": "FinScope Tanzania 2023",
            "total_adult_population": None,
            "tin_rate_pct": None,
            "mobile_money_rate_pct": None,
            "mm_no_tin_count": None,
            "by_stage": {}
        },
        "economic_model": {
            "loaded": False,
            "current_tax_revenue_tzs": None,
            "revenue_gap_tzs": None,
            "scenarios": {}
        },
        "interventions": _empty_interventions(),
        "evidence": {
            "total_items": 0,
            "high_confidence_count": 0,
            "api_verified_count": 0,
            "by_stage": {s: [] for s in LIFECYCLE_STAGES}
        },
        "assumptions": {
            "total": 0,
            "stress_tested": 0,
            "items": []
        },
        "validation": {
            "critic_reviews": [],
            "red_team_findings": [],
            "equity_flags": [],
            "legal_flags": [],
            "unintended_consequences": []
        },
        "report_sections": {
            "executive_summary": None,
            "section_1_problem": None,
            "section_2_theory_of_change": None,
            "section_3_framework": None,
            "section_4_lifecycle": None,
            "section_5_innovation": None,
            "section_6_prioritization": None,
            "section_7_political_economy": None,
            "section_8_roadmap": None,
            "section_9_me_framework": None,
            "section_10_risk": None,
            "section_11_impact": None,
            "section_12_recommendations": None,
            "section_13_why_tra": None
        },
        "objective_crosswalk": {
            s: {o: None for o in TRA_OBJECTIVES}
            for s in LIFECYCLE_STAGES
        },
        "conflicts": [],
        "quality_scores": {}
    }


# ============================================================
# LOAD AND SAVE
# ============================================================
def load_context() -> dict:
    """
    Loads shared context from disk.
    Creates a fresh context if none exists.
    Call this at the START of every agent.
    """
    if os.path.exists(SHARED_CONTEXT_FILE):
        with open(SHARED_CONTEXT_FILE, "r", encoding="utf-8") as f:
            ctx = json.load(f)
        for _k in ("created_at", "last_updated"):
            ctx["meta"].pop(_k, None)      # timestamps live in run_meta.json
        ctx["meta"]["pipeline_run_id"] = run_meta.pipeline_run_id()
        return ctx
    else:
        return _empty_context()


def save_context(ctx: dict) -> None:
    """
    Saves shared context to disk.
    Call this at the END of every agent.
    """
    ctx["meta"].pop("last_updated", None)
    run_meta.stamp("shared_context.json", "last_updated")
    with open(SHARED_CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)


def initialize_context() -> dict:
    """
    Creates a fresh context and saves it.
    Call this once at the start of a new pipeline run.
    Overwrites any existing context.
    """
    ctx = _empty_context()
    save_context(ctx)
    _initialize_audit_trail()
    _initialize_intervention_register()
    _initialize_assumption_ledger()
    print("  ✓ Shared context initialized")
    print(f"  ✓ Pipeline run ID: {ctx['meta']['pipeline_run_id']}")
    return ctx


# ============================================================
# AUDIT TRAIL
# Every agent call is logged here
# ============================================================
def _initialize_audit_trail() -> None:
    """Creates a fresh audit trail file."""
    trail = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "runs": []
    }
    with open(AUDIT_TRAIL_FILE, "w", encoding="utf-8") as f:
        json.dump(trail, f, indent=2)


def log_agent_run(
    agent_name: str,
    layer: str,
    inputs_read: list = None,
    outputs_written: list = None,
    assumptions_made: list = None,
    confidence_score: int = 0,
    section_key: str = None,
    notes: str = None
) -> str:
    """
    Logs one agent execution to the audit trail.
    Returns the run_id for this execution.

    Parameters
    ----------
    agent_name      : Name of the agent (e.g. "citizen_persona_agent")
    layer           : Pipeline layer (e.g. "L1", "L3", "L5")
    inputs_read     : List of context keys or files this agent read
    outputs_written : List of context keys or files this agent wrote
    assumptions_made: List of assumption strings this agent made
    confidence_score: Agent's self-reported confidence 0-100
    section_key     : Report section this agent fills (e.g. "section_4_lifecycle")
    notes           : Any additional notes
    """
    run_id = str(uuid.uuid4())[:8]

    entry = {
        "run_id": run_id,
        "agent_name": agent_name,
        "layer": layer,
        "section_key": section_key,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "inputs_read": inputs_read or [],
        "outputs_written": outputs_written or [],
        "assumptions_made": assumptions_made or [],
        "confidence_score": confidence_score,
        "notes": notes
    }

    if os.path.exists(AUDIT_TRAIL_FILE):
        with open(AUDIT_TRAIL_FILE, "r", encoding="utf-8") as f:
            trail = json.load(f)
    else:
        trail = {"created_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), "runs": []}

    trail["runs"].append(entry)

    with open(AUDIT_TRAIL_FILE, "w", encoding="utf-8") as f:
        json.dump(trail, f, indent=2)

    # Also update context
    ctx = load_context()
    if agent_name not in ctx["meta"]["agents_completed"]:
        ctx["meta"]["agents_completed"].append(agent_name)
    save_context(ctx)

    return run_id


# ============================================================
# INTERVENTION REGISTER
# Every intervention gets a unique ID and full genealogy
# ============================================================
def _initialize_intervention_register() -> None:
    """Creates a fresh intervention register."""
    register = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": 0,
        "interventions": []
    }
    with open(INTERVENTION_FILE, "w", encoding="utf-8") as f:
        json.dump(register, f, indent=2)


def normalise_title(title) -> str:
    """Strip stray markdown (asterisks, backticks) and collapse whitespace."""
    t = _re.sub(r"[*`]+", "", title or "")
    return _re.sub(r"\s+", " ", t).strip()


def _stable_intervention_id(lifecycle_stage, title) -> str:
    """INT-xxxxxx, xxxxxx = first 6 hex characters of SHA-1 over (stage + normalised title).
    If two interventions in the same register would collide, a counter is added to the second."""
    existing = set()
    if os.path.exists(INTERVENTION_FILE):
        try:
            with open(INTERVENTION_FILE, "r", encoding="utf-8") as f:
                existing = {i.get("intervention_id") for i in json.load(f).get("interventions", [])}
        except (json.JSONDecodeError, OSError):
            existing = set()
    base = "%s|%s" % ((lifecycle_stage or "").strip().lower(), normalise_title(title).lower())
    n = 0
    while True:
        cand = run_meta.sha1_id("INT", base if n == 0 else "%s|%d" % (base, n))
        if cand not in existing:
            return cand
        n += 1


def reset_context_interventions() -> None:
    """Empty the interventions block of shared_context.json (the register is rebuilt on every run)."""
    ctx = load_context()
    ctx["interventions"] = _empty_interventions()
    save_context(ctx)


def register_intervention(
    title: str,
    description: str,
    lifecycle_stage: str,
    objectives: list,
    evidence_ids: list = None,
    feasibility_score: int = 0,
    impact_score: int = 0,
    cost_estimate_tzs: float = None,
    revenue_estimate_tzs: float = None,
    timeframe: str = None,
    creating_agent: str = None,
    draft_policy_language: str = None,
    pilot_design: str = None,
    tags: list = None
) -> str:
    """
    Registers one intervention in the intervention register.
    Returns the unique intervention_id.

    Parameters
    ----------
    title               : Short intervention title
    description         : Full description
    lifecycle_stage     : One of LIFECYCLE_STAGES
    objectives          : List of TRA_OBJECTIVES this serves
    evidence_ids        : List of evidence_item IDs from evidence_store.db
    feasibility_score   : 0-100
    impact_score        : 0-100
    cost_estimate_tzs   : Implementation cost in TZS
    revenue_estimate_tzs: Expected revenue in TZS
    timeframe           : "immediate" | "short_term" | "medium_term" | "long_term"
    creating_agent      : Name of agent that generated this
    draft_policy_language: Actual legislative wording if applicable
    pilot_design        : Pilot specification text
    tags                : Additional tags (e.g. "behavioral", "digital", "legal")
    """
    title = normalise_title(title)
    intervention_id = _stable_intervention_id(lifecycle_stage, title)

    roi = None
    if cost_estimate_tzs and revenue_estimate_tzs \
            and cost_estimate_tzs > 0:
        roi = round(revenue_estimate_tzs / cost_estimate_tzs, 2)

    intervention = {
        "intervention_id": intervention_id,
        "title": title,
        "description": description,
        "lifecycle_stage": lifecycle_stage,
        "objectives_served": objectives,
        "evidence_ids": evidence_ids or [],
        "feasibility_score": feasibility_score,
        "impact_score": impact_score,
        "composite_score": round(
            (feasibility_score * 0.4 + impact_score * 0.6), 1
        ),
        "cost_estimate_tzs": cost_estimate_tzs,
        "revenue_estimate_tzs": revenue_estimate_tzs,
        "roi": roi,
        "timeframe": timeframe,
        "creating_agent": creating_agent,
        "validation_status": "pending",
        "critic_approvals": 0,
        "critic_rejections": 0,
        "validation_history": [],
        "draft_policy_language": draft_policy_language,
        "pilot_design": pilot_design,
        "tags": tags or [],
        "thesis_alignment": None,
        "validated_at": None
    }

    if os.path.exists(INTERVENTION_FILE):
        with open(INTERVENTION_FILE, "r", encoding="utf-8") as f:
            register = json.load(f)
    else:
        register = {"total": 0, "interventions": []}

    register["interventions"].append(intervention)
    register["total"] = len(register["interventions"])
    run_meta.stamp_item("intervention_register.json", intervention_id)

    with open(INTERVENTION_FILE, "w", encoding="utf-8") as f:
        json.dump(register, f, indent=2, ensure_ascii=False)

    # Update context counts
    ctx = load_context()
    ctx["interventions"]["total_generated"] += 1
    if lifecycle_stage in ctx["interventions"]["by_stage"]:
        ctx["interventions"]["by_stage"][lifecycle_stage].append(
            intervention_id
        )
    for obj in objectives:
        if obj in ctx["interventions"]["by_objective"]:
            ctx["interventions"]["by_objective"][obj].append(
                intervention_id
            )
    save_context(ctx)

    return intervention_id


def validate_intervention(
    intervention_id: str,
    approved: bool,
    critic_name: str,
    critique: str
) -> None:
    """
    Records a critic's verdict on one intervention.
    Updates validation_status when 2/3 critics have voted.

    critic_name/critique used to be accepted and silently discarded --
    only the aggregate approve/reject counters were kept, so the actual
    per-critic reasoning behind every vote this pipeline has ever cast
    was never persisted anywhere real. Both are now appended to
    validation_history so report_data_assembler.py/agent_v4.py can show
    the critic's real objections next to the final human decision,
    not just a bare vote count.
    """
    if not os.path.exists(INTERVENTION_FILE):
        return

    with open(INTERVENTION_FILE, "r", encoding="utf-8") as f:
        register = json.load(f)

    for intervention in register["interventions"]:
        if intervention["intervention_id"] == intervention_id:
            if approved:
                intervention["critic_approvals"] += 1
            else:
                intervention["critic_rejections"] += 1

            intervention.setdefault("validation_history", []).append({
                "critic_name": critic_name,
                "approved": approved,
                "critique": critique,
                "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            # 2/3 rule: approved if 2+ critics approve
            total_votes = (intervention["critic_approvals"] +
                           intervention["critic_rejections"])
            if total_votes >= 2:
                if intervention["critic_approvals"] >= 2:
                    intervention["validation_status"] = "approved"
                    intervention["validated_at"] = \
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ctx = load_context()
                    ctx["interventions"]["total_approved"] += 1
                    save_context(ctx)
                else:
                    intervention["validation_status"] = "rejected"
            break

    with open(INTERVENTION_FILE, "w", encoding="utf-8") as f:
        json.dump(register, f, indent=2, ensure_ascii=False)


def get_approved_interventions(
    lifecycle_stage: str = None,
    objective: str = None
) -> list:
    """
    Returns all approved interventions.
    Optionally filtered by lifecycle stage or objective.
    """
    if not os.path.exists(INTERVENTION_FILE):
        return []

    with open(INTERVENTION_FILE, "r", encoding="utf-8") as f:
        register = json.load(f)

    results = [
        i for i in register["interventions"]
        if i["validation_status"] == "approved"
    ]

    if lifecycle_stage:
        results = [
            i for i in results
            if i["lifecycle_stage"] == lifecycle_stage
        ]

    if objective:
        results = [
            i for i in results
            if objective in i["objectives_served"]
        ]

    return sorted(
        results,
        key=lambda x: x["composite_score"],
        reverse=True
    )


# ============================================================
# ASSUMPTION LEDGER
# Every agent registers every assumption it makes
# ============================================================
def _initialize_assumption_ledger() -> None:
    """Creates a fresh assumption ledger."""
    ledger = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": 0,
        "assumptions": []
    }
    with open(ASSUMPTION_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)


def register_assumption(
    assumption_text: str,
    made_by_agent: str,
    category: str,
    confidence: str,
    evidence_support: str = None,
    stress_tested: bool = False,
    stress_test_result: str = None,
    section_reference: str = None
) -> str:
    """
    Registers one assumption in the assumption ledger.
    Returns assumption_id.

    Parameters
    ----------
    assumption_text  : The full assumption statement
    made_by_agent    : Agent name that made this assumption
    category         : "behavioral" | "economic" | "political" |
                       "technical" | "demographic" | "legal"
    confidence       : "HIGH" | "MEDIUM" | "LOW"
    evidence_support : What evidence supports this assumption
    stress_tested    : Has this been tested by assumption stress agent
    stress_test_result: What happened when tested
    section_reference: Which report section uses this assumption
    """
    assumption_id = run_meta.sha1_id("ASS", "%s|%s" % (assumption_text, made_by_agent))

    assumption = {
        "assumption_id": assumption_id,
        "assumption_text": assumption_text,
        "made_by_agent": made_by_agent,
        "category": category,
        "confidence": confidence,
        "evidence_support": evidence_support,
        "stress_tested": stress_tested,
        "stress_test_result": stress_test_result,
        "section_reference": section_reference
    }

    if os.path.exists(ASSUMPTION_FILE):
        with open(ASSUMPTION_FILE, "r", encoding="utf-8") as f:
            ledger = json.load(f)
    else:
        ledger = {"total": 0, "assumptions": []}

    # Dedup on (assumption_text, made_by_agent) -- this is the PRIMARY
    # path (assumption_ledger.log_assumption() calls this whenever
    # shared_context is importable, which is always), so the same gap
    # already fixed in assumption_ledger._write_direct()'s fallback
    # path was still live here. Without this, e.g. economic_model.py's
    # calculate_cost_benefit() logging 6 assumptions on every re-run
    # would accumulate 6 fresh UUID-keyed duplicates each time.
    for existing in ledger["assumptions"]:
        if (existing["assumption_text"] == assumption_text
                and existing["made_by_agent"] == made_by_agent):
            return existing["assumption_id"]

    ledger["assumptions"].append(assumption)
    ledger["total"] = len(ledger["assumptions"])
    run_meta.stamp_item("assumption_ledger.json", assumption_id)

    with open(ASSUMPTION_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

    ctx = load_context()
    ctx["assumptions"]["total"] += 1
    if stress_tested:
        ctx["assumptions"]["stress_tested"] += 1
    save_context(ctx)

    return assumption_id


# ============================================================
# EVIDENCE HELPERS
# Quick access to verified statistics
# ============================================================
def get_verified_stat(indicator_name: str) -> Optional[dict]:
    """
    Returns a Tanzania statistic read from the pipeline outputs (no typed values).
    Falls back to None if not found.
    Use this when evidence_store.db may not be available.
    """
    return _build_tanzania_stats().get(indicator_name, None)


def get_finscope_stat(
    ctx: dict,
    stage: str,
    metric: str
) -> Optional[float]:
    """
    Returns a FinScope-measured statistic for a lifecycle stage.
    Returns None if FinScope data has not been loaded yet.

    Parameters
    ----------
    ctx    : The current shared context dict
    stage  : Lifecycle stage name (e.g. "entry")
    metric : e.g. "tin_rate_pct", "mm_rate_pct",
             "intervention_target", "top_barrier"
    """
    if not ctx["finscope"]["loaded"]:
        return None

    stage_data = ctx["finscope"]["by_stage"].get(stage, {})
    return stage_data.get(metric, None)


def get_lifecycle_population(
    ctx: dict,
    stage: str
) -> int:
    """
    Returns the population for a lifecycle stage.
    Uses FinScope data if loaded, otherwise Census estimates.
    """
    finscope_stage = ctx["finscope"]["by_stage"].get(stage, {})
    finscope_pop = finscope_stage.get("population", None)

    if finscope_pop:
        return finscope_pop

    default = ctx["lifecycle_populations"].get(stage, {})
    return default.get("population", 0)


def load_finscope_summary(finscope_summary_path: str) -> dict:
    """
    Loads the output of your local FinScope analysis script
    (finscope_summary.json) into the shared context.

    Run your local analysis script first to produce
    finscope_summary.json, then call this function.

    Parameters
    ----------
    finscope_summary_path : Path to finscope_summary.json
    """
    if not os.path.exists(finscope_summary_path):
        print(f"  ✗ FinScope summary not found at "
              f"{finscope_summary_path}")
        print("  → Run your local finscope_analysis.py first")
        return {}

    with open(finscope_summary_path, "r",
              encoding="utf-8") as f:
        summary = json.load(f)

    ctx = load_context()

    ctx["finscope"]["loaded"] = True
    ctx["finscope"]["total_adult_population"] = \
        summary.get("total_adult_population")
    ctx["finscope"]["tin_rate_pct"] = \
        summary.get("tin_rate")
    ctx["finscope"]["mobile_money_rate_pct"] = \
        summary.get("mm_rate")
    ctx["finscope"]["mm_no_tin_count"] = \
        summary.get("mm_no_tin")

    # Load by-stage data
    for stage, data in summary.get("by_stage", {}).items():
        ctx["finscope"]["by_stage"][stage] = data
        # Also update lifecycle populations with real numbers
        if "population" in data:
            if stage in ctx["lifecycle_populations"]:
                ctx["lifecycle_populations"][stage]["population"] = \
                    data["population"]
                ctx["lifecycle_populations"][stage]["source"] = \
                    "FinScope Tanzania 2023"

    save_context(ctx)

    print(f"  ✓ FinScope data loaded")
    print(f"  ✓ TIN rate: {ctx['finscope']['tin_rate_pct']}% "
          f"of adult population")
    print(f"  ✓ MM-no-TIN target: "
          f"{ctx['finscope']['mm_no_tin_count']:,} people")

    return summary


def load_economic_model(economic_model_path: str) -> dict:
    """
    Loads economic_model.json into the shared context.
    Agents can then cite scenario figures when generating
    interventions.

    Parameters
    ----------
    economic_model_path : Path to economic_model.json
    """
    if not os.path.exists(economic_model_path):
        print(f"  ✗ Economic model not found at "
              f"{economic_model_path}")
        return {}

    with open(economic_model_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    ctx = load_context()

    ctx["economic_model"]["loaded"] = True
    ctx["economic_model"]["current_tax_revenue_tzs"] = \
        model.get("current_tax_base", {}).get(
            "current_tax_revenue_tzs"
        )
    ctx["economic_model"]["revenue_gap_tzs"] = \
        model.get("current_tax_base", {}).get("revenue_gap_tzs")

    for scenario_name, scenario_data in \
            model.get("scenarios", {}).items():
        ctx["economic_model"]["scenarios"][scenario_name] = {
            "additional_revenue_tzs": scenario_data.get(
                "total_additional_annual_revenue_tzs"
            ),
            "new_taxpayers": scenario_data.get(
                "total_new_taxpayers"
            ),
            "new_tax_to_gdp_pct": scenario_data.get(
                "new_tax_to_gdp_pct"
            )
        }

    save_context(ctx)

    print(f"  ✓ Economic model loaded")
    conservative = ctx["economic_model"]["scenarios"].get(
        "conservative", {}
    )
    if conservative:
        rev = conservative.get("additional_revenue_tzs", 0)
        print(f"  ✓ Conservative scenario: "
              f"TZS {rev:,.0f} additional revenue")

    return model


# ============================================================
# THESIS ALIGNMENT
# Every agent tags its output against the master thesis
# ============================================================
def mark_thesis_alignment(
    agent_name: str,
    alignment: str,
    explanation: str
) -> None:
    """
    Records how an agent's output relates to the master thesis.

    Parameters
    ----------
    agent_name  : The agent making the alignment call
    alignment   : "SUPPORTS" | "CHALLENGES" | "REFINES"
    explanation : Brief explanation of the alignment
    """
    ctx = load_context()
    ctx["thesis"]["alignment_scores"][agent_name] = {
        "alignment": alignment,
        "explanation": explanation,
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if alignment == "CHALLENGES":
        ctx["thesis"]["challenges_identified"].append({
            "from": agent_name,
            "challenge": explanation
        })
    elif alignment == "REFINES":
        ctx["thesis"]["refinements_suggested"].append({
            "from": agent_name,
            "refinement": explanation
        })

    save_context(ctx)


# ============================================================
# CONFLICT REGISTRATION
# When agents disagree, log it explicitly
# ============================================================
def register_conflict(
    agent_a: str,
    agent_b: str,
    topic: str,
    position_a: str,
    position_b: str,
    resolution: str = None,
    tiebreak_rule: str = None
) -> str:
    """
    Logs a conflict between two agents.
    Makes disagreements explicit and traceable.

    Tiebreak rules:
    - "legal_veto"     : Legal agent always wins
    - "economic_threshold": Economic agent wins if ROI < 1x
    - "human_review"   : Flag for human decision
    - "majority_vote"  : Majority of critics decides
    """
    conflict_id = f"CON-{str(uuid.uuid4())[:6].upper()}"

    conflict = {
        "conflict_id": conflict_id,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "topic": topic,
        "position_a": position_a,
        "position_b": position_b,
        "resolution": resolution,
        "tiebreak_rule": tiebreak_rule,
        "status": "unresolved" if not resolution else "resolved",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    ctx = load_context()
    ctx["conflicts"].append(conflict)
    save_context(ctx)

    return conflict_id


# ============================================================
# REPORT SECTION WRITER
# Agents save their section content here
# ============================================================
# ============================================================
# QUALITY SCORING
# Agents report their confidence; synthesized at the end
# ============================================================
def record_quality_score(
    agent_name: str,
    score: int,
    dimension: str,
    notes: str = None
) -> None:
    """
    Records a quality score for any dimension.
    Used by the review simulation agent and the coherence agent.

    Parameters
    ----------
    agent_name : Agent or reviewer reporting the score
    score      : 0-100
    dimension  : e.g. "economist_reviewer", "tra_reviewer",
                 "policy_reviewer", "coherence", "evidence"
    notes      : Specific criticisms or praise
    """
    ctx = load_context()
    ctx["quality_scores"][f"{agent_name}_{dimension}"] = {
        "score": score,
        "dimension": dimension,
        "notes": notes,
        "recorded_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }
    save_context(ctx)


# ============================================================
# CONTEXT SUMMARY
# Quick status overview for debugging and progress tracking
# ============================================================
def get_context_summary(ctx: dict = None) -> dict:
    """
    Returns a summary of the current pipeline state.
    Useful for printing progress between agent runs.
    """
    if ctx is None:
        ctx = load_context()

    finscope_loaded = ctx["finscope"]["loaded"]
    econ_loaded = ctx["economic_model"]["loaded"]

    summary = {
        "pipeline_run_id": ctx["meta"]["pipeline_run_id"],
        "last_updated": run_meta.get("shared_context.json", "last_updated"),
        "agents_completed": len(ctx["meta"]["agents_completed"]),
        "finscope_loaded": finscope_loaded,
        "economic_model_loaded": econ_loaded,
        "interventions_generated": ctx["interventions"]["total_generated"],
        "interventions_approved": ctx["interventions"]["total_approved"],
        "assumptions_logged": ctx["assumptions"]["total"],
        "sections_completed": sum(
            1 for v in ctx["report_sections"].values()
            if v is not None
        ),
        "conflicts_logged": len(ctx["conflicts"]),
        "thesis_alignments": len(ctx["thesis"]["alignment_scores"])
    }

    if finscope_loaded:
        summary["tin_rate_pct"] = ctx["finscope"]["tin_rate_pct"]
        summary["mm_no_tin_target"] = ctx["finscope"]["mm_no_tin_count"]

    if econ_loaded:
        conservative = ctx["economic_model"]["scenarios"].get(
            "conservative", {}
        )
        summary["conservative_revenue_tzs"] = conservative.get(
            "additional_revenue_tzs"
        )

    return summary


def print_status(ctx: dict = None) -> None:
    """Prints a readable pipeline status to the console."""
    s = get_context_summary(ctx)

    print("\n" + "─" * 50)
    print(f"  Pipeline: {s['pipeline_run_id']} │ "
          f"{s['last_updated']}")
    print("─" * 50)
    print(f"  Agents completed:       {s['agents_completed']}")
    print(f"  FinScope loaded:        "
          f"{'✓' if s['finscope_loaded'] else '✗'}")
    print(f"  Economic model loaded:  "
          f"{'✓' if s['economic_model_loaded'] else '✗'}")
    print(f"  Interventions generated:{s['interventions_generated']}")
    print(f"  Interventions approved: {s['interventions_approved']}")
    print(f"  Assumptions logged:     {s['assumptions_logged']}")
    print(f"  Report sections done:   {s['sections_completed']}/14")
    print(f"  Conflicts logged:       {s['conflicts_logged']}")
    print("─" * 50 + "\n")


# ============================================================
# EVIDENCE CONTEXT BUILDER FOR AGENT PROMPTS
# Injects verified stats into any agent prompt
# ============================================================
def build_agent_evidence_context(
    ctx: dict,
    stage: str = None
) -> str:
    """
    Builds a formatted evidence string for injection into
    any agent prompt. Includes Tanzania stats, FinScope data
    for the specified stage, and economic model figures.

    Parameters
    ----------
    ctx   : Current shared context
    stage : Optional lifecycle stage for stage-specific data
    """
    lines = [
        "═" * 50,
        "VERIFIED EVIDENCE BASE — inject into all reasoning",
        "═" * 50,
        "",
        "TANZANIA KEY STATISTICS (verified sources):"
    ]

    for key, stat in _build_tanzania_stats().items():
        lines.append(
            f"  • {key}: {stat['value']} {stat['unit']} "
            f"({stat['year']}) — {stat['source']}"
        )

    if ctx["finscope"]["loaded"] and stage:
        stage_data = ctx["finscope"]["by_stage"].get(stage, {})
        if stage_data:
            lines += [
                "",
                f"FINSCOPE DATA — {stage.upper()} STAGE "
                f"(FinScope Tanzania 2023):"
            ]
            for k, v in stage_data.items():
                lines.append(f"  • {k}: {v}")

    if ctx["economic_model"]["loaded"]:
        lines += [
            "",
            "REVENUE SCENARIOS (economic_model.py — Python formulas):"
        ]
        for scenario, data in \
                ctx["economic_model"]["scenarios"].items():
            rev = data.get("additional_revenue_tzs", 0)
            lines.append(
                f"  • {scenario}: TZS {rev:,.0f} additional revenue"
            )

    lines += [
        "",
        "EVIDENCE RULE: Every recommendation must cite",
        "at least one HIGH confidence verified source.",
        "═" * 50
    ]

    return "\n".join(lines)


# ============================================================
# MAIN RUNNER
# Initialize the shared context at the start of a pipeline run
# ============================================================
def run_shared_context_setup(
    finscope_summary_path: str = paths.FINSCOPE_SUMMARY,
    economic_model_path: str = paths.ECONOMIC_MODEL
) -> dict:
    """
    Master setup function.
    Call this BEFORE running any agents.
    Initializes all infrastructure files.
    Loads FinScope and economic model if available.
    """
    print("\n" + "═" * 60)
    print("  SHARED CONTEXT SETUP")
    print("  Initializing pipeline infrastructure")
    print("═" * 60 + "\n")

    # Step 1: Initialize fresh context
    print("STEP 1: INITIALIZING CONTEXT FILES")
    print("-" * 40)
    ctx = initialize_context()

    # Step 2: Load FinScope if available
    print("\nSTEP 2: LOADING FINSCOPE DATA")
    print("-" * 40)
    if os.path.exists(finscope_summary_path):
        load_finscope_summary(finscope_summary_path)
    else:
        print(f"  ✗ {finscope_summary_path} not found")
        print("  → Run finscope_analysis.py first")
        print("  → Continuing with Census 2022 estimates")

    # Step 3: Load economic model if available
    print("\nSTEP 3: LOADING ECONOMIC MODEL")
    print("-" * 40)
    if os.path.exists(economic_model_path):
        load_economic_model(economic_model_path)
    else:
        print(f"  ✗ {economic_model_path} not found")
        print("  → Run economic_model.py first")

    # Step 4: Reload and print final status
    ctx = load_context()

    print("\n" + "═" * 60)
    print("  SHARED CONTEXT SETUP COMPLETE")
    print("═" * 60)
    print("\n  Files produced:")
    print("  → shared_context.json")
    print("  → audit_trail.json")
    print("  → intervention_register.json")
    print("  → assumption_ledger.json")

    print_status(ctx)

    print("  Next step: Run agent_v3.py")
    print("═" * 60)

    return ctx


if __name__ == "__main__":
    run_shared_context_setup()