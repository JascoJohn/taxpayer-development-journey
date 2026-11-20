"""
intervention_registrar.py

Builds the intervention register (outputs/stats/intervention_register.json and the interventions block of data/interim/shared_context.json) from
docs/interventions.yaml (Block F4). The YAML holds the six stage tools (the names of config.yaml `names:`, with the report's old names in `old_names`; one sentence of its mechanism, the target group and the cost
reference of the first version's Table 40). The earlier inputs are gone: the frozen LLM-generated section (report_sections.json, now in _archive/frozen/) and the cost-benefit block of the economic model
(removed in Block F0). The YAML was reviewed by the owner on 2026-11-13; the eight LLM-drafted interventions are in _archive/interventions_llm_drafts.yaml and are not registered.

Every run REPLACES the register (no accumulation); ids are derived from stage and title (shared_context._stable_intervention_id); validation_status stays 'pending' (no critic
process has run); scores stay 0 (nothing is scored); revenue is not estimated here (Table 5.1 is computed by src/04_models/stage_economics.py).

Usage:
    python intervention_registrar.py
"""

import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

from shared_context import register_intervention, reset_context_interventions

YAML_FILE = paths.INTERVENTIONS_YAML
REGISTER_FILE = paths.INTERVENTION_REGISTER


def _timeframe(cost_tzs):
    """Implementation timeframe bucket from the cost reference alone (None when no cost is stated: an honest gap, not a guess)."""
    if cost_tzs is None:
        return None
    if cost_tzs < 100_000_000:
        return "immediate"
    if cost_tzs < 500_000_000:
        return "short_term"
    if cost_tzs < 2_000_000_000:
        return "medium_term"
    return "long_term"


def load_interventions(yaml_path=YAML_FILE):
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["interventions"]


def register_all(yaml_path=YAML_FILE, register_path=REGISTER_FILE, force=False):
    """Rebuilds the register from the YAML. `force` is kept for older callers and changes nothing (the register is always replaced)."""
    os.makedirs(os.path.dirname(register_path), exist_ok=True)
    with open(register_path, "w", encoding="utf-8") as f:
        json.dump({"total": 0, "interventions": []}, f, indent=2, ensure_ascii=False)
    reset_context_interventions()
    registered = []
    for item in load_interventions(yaml_path):
        ref = item.get("cost_reference") or {}
        cost = ref.get("cost_tzs")
        if cost is None and ref.get("cost_range_tzs"):
            cost = float(max(ref["cost_range_tzs"]))             # a stated range: the upper bound (understating a budget is the more harmful error)
        iid = register_intervention(
            title=item["name"],
            description=item["mechanism"],
            lifecycle_stage=item["stage"],
            objectives=[],                                        # not stated in the report per tool: left empty, not guessed
            cost_estimate_tzs=cost,
            revenue_estimate_tzs=None,                            # revenue is computed in Table 5.1 (stage_economics.py), not here
            timeframe=_timeframe(cost),
            creating_agent="docs/interventions.yaml",
            tags=["report_stage_tool"],
        )
        registered.append((iid, item["name"]))
        print(f"  Registered: {iid} -- {item['name']}")
    print(f"\n  Total registered: {len(registered)} (the six stage tools of the report). validation_status='pending' for all: no critic process has run.")
    return registered


if __name__ == "__main__":
    register_all(force="--force" in sys.argv)
