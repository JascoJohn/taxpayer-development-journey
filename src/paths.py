"""Single place where file locations are resolved.

Every location is read from config.yaml and resolved relative to the project root
(the folder that contains config.yaml), never relative to the current working directory.

Importing this module also puts the numbered stage folders under src/ on sys.path so
that the scripts can keep importing each other by bare module name
(e.g. `from shared_context import ...`).
"""

import os
import sys

import yaml

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SRC_DIR)

with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as _f:
    CFG = yaml.safe_load(_f)


def resolve(rel_path):
    """Project-root-relative path from config.yaml ('/' separated) -> absolute OS path.
    An absolute path in config.yaml is used as it is (the tests use this to point a throw-away project
    copy at the large raw files instead of copying them)."""
    if os.path.isabs(str(rel_path)):
        return os.path.normpath(str(rel_path))
    return os.path.normpath(os.path.join(ROOT, *str(rel_path).split("/")))


_F = CFG["files"]

# raw inputs
FINSCOPE_CSV = resolve(_F["finscope_csv"])
FINSCOPE_DATAMAP = resolve(_F["finscope_datamap"])
TAX_EXEMPTIONS_XLSX = resolve(_F["tax_exemptions_xlsx"])
CENSUS_SAV = resolve(_F["census_sav"])
ILFS_SAV = resolve(_F["ilfs_sav"])
AFROBAROMETER_SAV = resolve(_F["afrobarometer_sav"])

# interim
FINSCOPE_SUMMARY = resolve(_F["finscope_summary"])
FINSCOPE_FEATURE_STORE = resolve(_F["finscope_feature_store"])
SHARED_CONTEXT = resolve(_F["shared_context"])

# processed
FINSCOPE_REGION_ACTIVITY = resolve(_F["finscope_region_activity"])
FINSCOPE_ACTIVE_BENCHMARK = resolve(_F["finscope_active_benchmark"])
CENSUS_AGE_COUNTS = resolve(_F["census_age_counts"])
ILFS_INDICATORS = resolve(_F["ilfs_indicators"])

# outputs
ECONOMIC_MODEL = resolve(_F["economic_model"])
FINSCOPE_REPORT = resolve(_F["finscope_report"])
INTERVENTION_REGISTER = resolve(_F["intervention_register"])
ASSUMPTION_LEDGER = resolve(_F["assumption_ledger"])
ASSUMPTION_LEDGER_REPORT = resolve(_F["assumption_ledger_report"])
ASSUMPTION_LEDGER_SUMMARY = resolve(_F["assumption_ledger_summary"])
AUDIT_TRAIL = resolve(_F["audit_trail"])
TIN_BY_SEGMENT_CSV = resolve(_F["tin_by_segment_csv"])
TIN_RECONCILIATION = resolve(_F["tin_reconciliation"])
TAX_EXEMPTION_RATE = resolve(_F["tax_exemption_rate"])
SEED_POPULATION = resolve(_F["seed_population"])
ILFS_INFORMALITY_CSV = resolve(_F["ilfs_informality_csv"])
ILFS_SUMMARY = resolve(_F["ilfs_summary"])
MACRO_INPUTS = resolve(_F["macro_inputs"])
TIN_MOBILE_MONEY = resolve(_F["tin_mobile_money"])
TIN_MOBILE_MONEY_CSV = resolve(_F["tin_mobile_money_csv"])
TARGETING_MODEL = resolve(_F["targeting_model"])
TARGETING_DECILES_CSV = resolve(_F["targeting_deciles_csv"])
AGENT_CELLS = resolve(_F["agent_cells"])
TARGETING_VARIANTS_CSV = resolve(_F["targeting_variants_csv"])
TARGETING_LEAKAGE_REVIEW_CSV = resolve(_F["targeting_leakage_review_csv"])
AFROBAROMETER_MORALE = resolve(_F["afrobarometer_morale"])
TAX_MORALE_COMPONENTS_CSV = resolve(_F["tax_morale_components_csv"])
AGENT_TRUST_MORALE = resolve(_F["agent_trust_morale"])
AGENT_INCOME = resolve(_F["agent_income"])
TWIN_INPUTS = resolve(_F["twin_inputs"])
STAGE_ECONOMICS = resolve(_F["stage_economics"])
TABLE40_CSV = resolve(_F["table40_csv"])
AGENT_CALIBRATION = resolve(_F["agent_calibration"])
TRA_REGISTERED_TAXPAYERS_CSV = resolve(_F["tra_registered_taxpayers_csv"])
ASSUMPTION_SENSITIVITY = resolve(_F["assumption_sensitivity"])
ASSUMPTIONS_REGISTER = resolve(_F["assumptions_register"])

# run metadata (timestamps, run id)
RUN_META = resolve(_F["run_meta"])
CONFIG_FILE = os.path.join(ROOT, "config.yaml")
CLEAN_DIRS = [resolve(p) for p in CFG["clean_dirs"]]

# authored interventions (draft for the owner's review): read by src/04_models/intervention_registrar.py
INTERVENTIONS_YAML = resolve(_F["interventions_yaml"])
ILFS_TAX_BASE = resolve(_F["ilfs_tax_base"])

DISCLOSURE = CFG["disclosure"]

# World Bank snapshots and macro settings, from config.yaml
WB_CFG = CFG["worldbank"]
WB_SNAPSHOT_DIR = resolve(WB_CFG["snapshot_dir"])
WB_MANIFEST = resolve(WB_CFG["manifest"])
WB_SNAPSHOTS = {k: resolve(v) for k, v in WB_CFG["snapshots"].items()}
MACRO_CFG = CFG["macro"]

# Seed stage age band (inclusive), from config.yaml
SEED_AGE_BAND = tuple(int(x) for x in CFG["seed_age_band"])

# seeds and simulation sizes
RANDOM_SEED = CFG["simulation"]["random_seed"]
N_AGENTS = CFG["simulation"]["n_agents"]
N_YEARS = CFG["simulation"]["n_years"]

# File name -> location, used by the dashboard (dashboard/tdj_lib/pipeline_data.py)
PIPELINE_FILES = {
    "economic_model.json": ECONOMIC_MODEL,
    "intervention_register.json": INTERVENTION_REGISTER,
    "finscope_region_activity.json": FINSCOPE_REGION_ACTIVITY,
    "finscope_active_benchmark.json": FINSCOPE_ACTIVE_BENCHMARK,
    "targeting_model.json": TARGETING_MODEL,
    "tin_mobile_money.json": TIN_MOBILE_MONEY,
    "afrobarometer_morale.json": AFROBAROMETER_MORALE,
    "stage_economics.json": STAGE_ECONOMICS,
}


def _add_stage_dirs_to_syspath():
    for name in sorted(os.listdir(SRC_DIR)):
        full = os.path.join(SRC_DIR, name)
        if os.path.isdir(full) and name[:2].isdigit() and full not in sys.path:
            sys.path.insert(0, full)


_add_stage_dirs_to_syspath()
