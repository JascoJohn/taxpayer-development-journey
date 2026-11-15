"""Single definitions of the FinScope survey weight, the lifecycle-stage assignment and the TIN mask.

Every module that needs them imports them from here (finscope_analysis, shared_context,
economic_model and the loaders) instead of re-implementing them.

FinScope Tanzania 2023 columns used:
  population_wt  survey weight (sums to the weighted adult population, 34,134,251)
  c8c            age in years (the file holds respondents aged 16 and over)
  BusO           'Business owners' = business owner
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
TIN_COLUMN = "c27__13"

# Seed age band (inclusive), read from config.yaml (seed_age_band). Entry starts the year after Seed ends.
SEED_AGE_MIN, SEED_AGE_MAX = paths.SEED_AGE_BAND

# Six lifecycle stages, in report order.
LIFECYCLE_STAGES = [
    "seed",        # Age SEED_AGE_MIN-SEED_AGE_MAX (config.yaml seed_age_band; 6-15)
    "entry",       # Age SEED_AGE_MAX+1 to 24 (16-24)
    "active",      # Age 25-44, not a business owner
    "enterprise",  # Business owners aged 25-64
    "asset",       # Age 45-64, not a business owner
    "legacy"       # Age 65+
]

# The five adult stages (FinScope respondents are aged 16+; Seed is not in FinScope).
ADULT_STAGES = ["entry", "active", "enterprise", "asset", "legacy"]

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


def tin_holder_mask(df):
    """True where the respondent holds a TIN (c27__13 == 'Yes')."""
    return yes_mask(df, TIN_COLUMN)


def lifecycle_stage(df):
    """Lifecycle stage of every respondent (numpy array of stage names, 'unknown' if none applies)."""
    age = pd.to_numeric(df[AGE_COLUMN], errors='coerce')
    is_biz = business_owner_mask(df)
    conditions = [
        (age >= SEED_AGE_MIN) & (age <= SEED_AGE_MAX),
        (age > SEED_AGE_MAX) & (age < 25),
        (age >= 25) & (age < 45) & ~is_biz,
        (age >= 25) & (age < 65) & is_biz,
        (age >= 45) & (age < 65) & ~is_biz,
        (age >= 65),
    ]
    return np.select(conditions, LIFECYCLE_STAGES, default='unknown')
