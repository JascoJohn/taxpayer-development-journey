"""Design-based (Taylor-linearised) standard errors and confidence intervals for weighted ratios.

Used by tin_by_segment.py (FinScope) and ilfs_indicators.py (ILFS).

Estimator: a (domain) ratio R = sum(w * num) / sum(w * den), e.g. the weighted share of TIN holders within a
lifecycle stage (num = stage * TIN, den = stage). All observations stay in the data set when a domain is
estimated (sub-population estimation), so the variance accounts for the random size of the domain.

Variance (stratified one-stage cluster design, primary sampling units drawn with replacement):
    z_i = w_i * (num_i - R * den_i) / sum(w * den)
    z_hc = sum of z_i over the units of PSU c in stratum h
    Var(R) = sum_h  n_h / (n_h - 1) * sum_c (z_hc - mean_h(z))^2
The finite-population correction is ignored (sampling fractions are small). Strata with a single PSU
cannot contribute a variance term; they are counted and reported, never silently dropped.

Confidence interval: logit-transformed (the default of Stata's `svy: proportion`), Student-t with
df = number of PSUs - number of strata; this keeps the interval inside 0-100% and handles rates near 0.
"""

import math

import numpy as np
import pandas as pd
from scipy import stats


def linearised_ratio(num, den, weights, strata, psu):
    """Returns (ratio, standard error, n_psu, n_strata, n_lonely_strata) for sum(w*num)/sum(w*den).

    num, den, weights: 1-D numeric arrays; strata, psu: 1-D label arrays (psu labels must be unique across
    strata, build them with a composite key)."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    w = np.asarray(weights, dtype=float)
    d_total = float((w * den).sum())
    if d_total <= 0:
        return float("nan"), float("nan"), 0, 0, 0
    ratio = float((w * num).sum()) / d_total
    z = w * (num - ratio * den) / d_total
    frame = pd.DataFrame({"z": z, "h": np.asarray(strata), "c": np.asarray(psu)})
    psu_totals = frame.groupby(["h", "c"], sort=False)["z"].sum().reset_index()
    var = 0.0
    lonely = 0
    n_psu = len(psu_totals)
    n_strata = psu_totals["h"].nunique()
    for _, g in psu_totals.groupby("h", sort=False):
        n_h = len(g)
        if n_h < 2:
            lonely += 1
            continue
        var += n_h / (n_h - 1.0) * float(((g["z"] - g["z"].mean()) ** 2).sum())
    return ratio, math.sqrt(var), n_psu, n_strata, lonely


def ci95(ratio, se, n_psu, n_strata):
    """95% confidence interval for a proportion in [0, 1]: logit scale, Student-t. Returns (low, high) in [0, 1].
    Falls back to the (truncated) normal interval when the ratio is 0 or 1 or the se is 0."""
    if not (ratio == ratio) or not (se == se):
        return float("nan"), float("nan")
    df = max(n_psu - n_strata, 1)
    t = float(stats.t.ppf(0.975, df))
    if 0.0 < ratio < 1.0 and se > 0:
        se_logit = se / (ratio * (1.0 - ratio))
        centre = math.log(ratio / (1.0 - ratio))
        lo = centre - t * se_logit
        hi = centre + t * se_logit
        return 1.0 / (1.0 + math.exp(-lo)), 1.0 / (1.0 + math.exp(-hi))
    return max(ratio - t * se, 0.0), min(ratio + t * se, 1.0)


def design_df(n_psu, n_strata):
    return max(n_psu - n_strata, 1)
