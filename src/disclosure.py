"""Disclosure rule for every published output (Block D1). The thresholds come from config.yaml `disclosure:`; nothing else
in the project hard-codes them.

  min_base                 a cell whose UNWEIGHTED respondent base is below this has its estimate and count set to null,
                           with "suppressed": true and "reason": "base < <min_base>". Unweighted counts below it are never published.
  low_precision_numerator  a cell with base >= min_base but an unweighted numerator below this keeps its estimate and gets
                           "low_precision": true (and a 95% CI where the design allows it).

The numerator itself is never published when it is below the threshold: only the flag is.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

MIN_BASE = int(paths.CFG["disclosure"]["min_base"])
LOW_PRECISION_NUMERATOR = int(paths.CFG["disclosure"]["low_precision_numerator"])
REASON = "base < %d" % MIN_BASE
_DESIGN_CACHE = {}


def is_suppressed(base):
    return base is None or base < MIN_BASE


def is_low_precision(base, numerator):
    return base is not None and base >= MIN_BASE and numerator is not None and numerator < LOW_PRECISION_NUMERATOR


def suppress(cell, fields):
    """Set the listed fields of a cell (a dict) to null and mark the cell suppressed. Returns the cell."""
    for f in fields:
        if f in cell:
            cell[f] = None
    cell["suppressed"] = True
    cell["reason"] = REASON
    return cell


def suppress_fields(cell, fields):
    """Suppress only some fields of a cell (the rest of the cell is publishable)."""
    for f in fields:
        if f in cell:
            cell[f] = None
    cell.setdefault("suppressed_fields", [])
    cell["suppressed_fields"] += [f for f in fields if f not in cell["suppressed_fields"]]
    cell["suppressed_fields_reason"] = REASON
    return cell


def flag_low_precision(cell, fields, ci=None):
    """Mark estimates of a cell as low precision; `ci` maps a field to [low, high] (per cent) where the design allows."""
    cell["low_precision"] = True
    lp = cell.setdefault("low_precision_fields", [])
    for f in fields:
        if f not in lp:
            lp.append(f)
    ci = {k: v for k, v in (ci or {}).items() if v is not None}
    if ci:
        cell.setdefault("ci95_pct", {}).update(ci)
    return cell


def apply_to_row(row, base_key, numerator_key, estimate_keys, count_keys=()):
    """Disclosure rule for a flat table row (ILFS indicators, TIN by segment).
    base < min_base: estimates and counts become None and the row is marked suppressed.
    numerator < threshold: the numerator count is withheld (never published below the threshold) and the estimates are flagged."""
    base, num = row.get(base_key), row.get(numerator_key)
    if is_suppressed(base):
        return suppress(row, [base_key, numerator_key] + list(estimate_keys) + list(count_keys))
    if num is not None and num < LOW_PRECISION_NUMERATOR:
        row[numerator_key] = None
        flag_low_precision(row, list(estimate_keys))
    return row


def leaf(value, base, numerator):
    """For a scalar leaf of a flat indicator store: the value itself, or an object marking it suppressed / low precision."""
    if is_suppressed(base):
        return {"value": None, "suppressed": True, "reason": REASON}
    if is_low_precision(base, numerator):
        return {"value": value, "low_precision": True}
    return value


def ci95_domain_pct(df, weight_col, domain_mask, indicator_mask, min_numerator=1):
    """95% CI (per cent, logit, design-based on the reconstructed FinScope design) of the weighted share of `indicator_mask`
    within `domain_mask`. Returns [low, high] or None when the design columns are missing or the numerator is zero."""
    import numpy as np
    from survey_design import ci95, linearised_ratio
    cols = ["reg_code", "dist_code", "ward_code1", "ea_code", "clustertype"]
    if any(c not in df.columns for c in cols):
        return None
    dom = np.asarray(domain_mask, dtype=bool)
    num = np.asarray(indicator_mask, dtype=bool) & dom
    if num.sum() < min_numerator or dom.sum() == 0:
        return None
    key = (id(df), len(df))
    if key not in _DESIGN_CACHE:                       # building the labels is slow: once per data frame
        _DESIGN_CACHE.clear()
        psu = df[["reg_code", "dist_code", "ward_code1", "ea_code"]].astype(str).agg("|".join, axis=1)
        strata = df["reg_code"].astype(str) + "|" + df["clustertype"].astype(str)
        _DESIGN_CACHE[key] = (strata.to_numpy(), psu.to_numpy())
    strata, psu = _DESIGN_CACHE[key]
    w = np.asarray(df[weight_col], dtype=float)
    r, se, n_psu, n_str, _ = linearised_ratio(num.astype(float), dom.astype(float), w, strata, psu)
    if not (r == r) or math.isnan(se):
        return None
    lo, hi = ci95(r, se, n_psu, n_str)
    return [round(lo * 100, 1), round(hi * 100, 1)]
