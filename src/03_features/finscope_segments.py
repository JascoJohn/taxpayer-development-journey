"""Single definitions of the FinScope survey weight, the lifecycle-stage assignment and the TIN mask.

Every module that needs them imports them from here (finscope_analysis, shared_context,
economic_model and the loaders) instead of re-implementing them.

FinScope Tanzania 2023 columns used:
  population_wt  survey weight (sums to the weighted adult population, 34,134,251)
  c8c            age in years (the file holds respondents aged 16 and over)
  BusO           'Business owners' = business owner (FinScope derived flag: main income source is trading or services; no formal step is required)
  D6_4a          'Yes' = the business is registered with a government authority (TRA/ZRA or LGA, D6_4b): the FORMAL STEP of mapping B
  c27__13        'Yes' = holds a Taxpayer Identification Number (TIN)
  Household_weight  household weight used by the region x activity tables
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

WEIGHT_VAR = "population_wt"
HOUSEHOLD_WEIGHT_VAR = "Household_weight"
AGE_COLUMN = "c8c"
BUSINESS_OWNER_COLUMN = "BusO"
BUSINESS_OWNER_VALUE = "Business owners"
FORMAL_STEP_COLUMN = "D6_4a"            # "Is your business registered with any government authority?" (asked of those with a business or farming activity)
TIN_COLUMN = "c27__13"

# Seed age band (inclusive), read from config.yaml (seed_age_band). Entry starts the year after Seed ends.
SEED_AGE_MIN, SEED_AGE_MAX = paths.SEED_AGE_BAND

# Lifecycle stages, in report order. STAGE MAPPING B (Pass 6B-1; owner decision after PASS6A D2, PASS6C E2 and PASS6D F1):
# the business-owner stages are split by the FORMAL STEP, and the non-owners aged 25-44 are a named group with no revenue lever.
LIFECYCLE_STAGES = [
    "seed",        # Age SEED_AGE_MIN-SEED_AGE_MAX (config.yaml seed_age_band; 6-15)
    "entry",       # Age SEED_AGE_MAX+1 to 24 (16-24), whoever they are (unchanged)
    "active",      # Business owner (BusO), NO formal step (D6_4a != 'Yes', including not asked), aged 25-64: informal business owners
    "enterprise",  # Business owner (BusO) WITH a formal step (D6_4a == 'Yes'), aged 25-64: registered business owners
    "workers",     # NOT a business owner, aged 25-44: wage, casual, farm and dependent adults; kept in the population, no revenue lever
    "asset",       # Not a business owner, aged 45-64 (unchanged)
    "legacy"       # Age 65+ (unchanged)
]

# The adult stages (FinScope respondents are aged 16+; Seed is not in FinScope).
ADULT_STAGES = ["entry", "active", "enterprise", "workers", "asset", "legacy"]

# Stage labels used by the synthetic segmentation model (class codes 0-3).
ML_SEGMENT_STAGES = ["entry", "active", "asset", "legacy"]


def yes_mask(df, col):
    """Returns boolean mask where column == 'yes' (any case)."""
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    try:
        series = df[col].astype(object).astype(str)
    except Exception:
        series = df[col].astype(str)
    return series.str.strip().str.lower() == 'yes'


def val_mask(df, col, value):
    """Returns boolean mask where column == value (string)."""
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    try:
        series = df[col].astype(object).astype(str)
    except Exception:
        series = df[col].astype(str)
    return series.str.strip() == str(value)


def survey_weights(df):
    """population_wt as a numeric series (non-numeric -> 0)."""
    return pd.to_numeric(df[WEIGHT_VAR], errors='coerce').fillna(0)


def business_owner_mask(df):
    return val_mask(df, BUSINESS_OWNER_COLUMN, BUSINESS_OWNER_VALUE)


def formal_step_mask(df):
    """True where the respondent's business is registered with a government authority (D6_4a == 'Yes'). A missing or blank answer (not asked) counts as NO formal step (docs/assumptions_register.csv)."""
    from assumptions import A
    mask = yes_mask(df, FORMAL_STEP_COLUMN)
    if A("stage.formal_step_if_not_asked") != "no_formal_step":
        raise ValueError("stage.formal_step_if_not_asked: only 'no_formal_step' is implemented")
    return mask


def tin_holder_mask(df):
    """True where the respondent holds a TIN (c27__13 == 'Yes')."""
    return yes_mask(df, TIN_COLUMN)


def lifecycle_stage(df):
    """Lifecycle stage of every respondent (numpy array of stage names, 'unknown' if none applies)."""
    age = pd.to_numeric(df[AGE_COLUMN], errors='coerce')
    is_biz = business_owner_mask(df)
    formal = formal_step_mask(df)
    conditions = [
        (age >= SEED_AGE_MIN) & (age <= SEED_AGE_MAX),
        (age > SEED_AGE_MAX) & (age < 25),
        (age >= 25) & (age < 65) & is_biz & ~formal,           # active: informal business owners
        (age >= 25) & (age < 65) & is_biz & formal,            # enterprise: owners with a formal step
        (age >= 25) & (age < 45) & ~is_biz,                    # non-business owners 25-44
        (age >= 45) & (age < 65) & ~is_biz,                    # asset
        (age >= 65),
    ]
    return np.select(conditions, LIFECYCLE_STAGES, default='unknown')
