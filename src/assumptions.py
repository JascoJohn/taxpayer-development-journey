"""Access to the `assumptions:` block of config.yaml.

Every in-scope constant of the economic model (a constant that feeds a claim in docs/claims_map_draft.csv or a value the
dashboard displays) lives in that block with its value, basis class (DATA, LITERATURE, ASSUMPTION, UNKNOWN), source or
rationale and the claims it feeds. The model code reads values with A("key"); there is no typed copy in the code.

Entries without a `value` (basis DATA with a `from` file) are documentation of inputs read from a data file.

`override()` lets the sensitivity analysis run the model with other values without touching config.yaml.
"""

import contextlib
import copy
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

_BLOCK = paths.CFG.get("assumptions") or {}
_overrides = {}


_DATA_CACHE = {}


def _from_data_file(file_key, data_path):
    """Value of a DATA assumption read from a processed file (config.yaml files: <file_key>) at a dotted path (no wildcards)."""
    import json
    path = paths.resolve(paths.CFG["files"][file_key])
    if path not in _DATA_CACHE:
        try:
            with open(path, "r", encoding="utf-8") as f:
                _DATA_CACHE[path] = json.load(f)
        except FileNotFoundError:
            raise SystemExit("%s is missing: run `python run_all.py --from-raw` (it is written by src/03_features/)" % path) from None
    v = _DATA_CACHE[path]
    for part in data_path.split("."):
        v = v[part]
    return v


def A(key):
    """Value of one assumption (a copy for lists and dicts)."""
    if key in _overrides:
        v = _overrides[key]
    else:
        try:
            e = _BLOCK[key]
        except KeyError:
            raise KeyError("assumption %r is not in config.yaml (assumptions:)" % key) from None
        if "value" not in e:
            if e.get("data_file") and e.get("data_path"):
                v = _from_data_file(e["data_file"], e["data_path"])
            else:
                raise KeyError("assumption %r has no value in config.yaml (it is read from %s)" % (key, e.get("from")))
        else:
            v = e["value"]
    return copy.deepcopy(v) if isinstance(v, (list, dict)) else v


def entry(key):
    return _BLOCK[key]


def _fig51():
    """Current Fig 5.1 values from outputs/stats/economic_model.json (tax_morale_model), for the `{FIG51}` token of the `feeds` descriptions."""
    import json
    try:
        with open(paths.ECONOMIC_MODEL, encoding="utf-8") as f:
            m = json.load(f)["tax_morale_model"]
        solo = [v["new_compliance_prob"] * 100 for v in m["intervention_effects"].values()]
        return "Fig 5.1: baseline %.2f%%, solo effects %.1f-%.1f%%, best single %.1f%%, combined %.1f%%, naive sum %.1f%%" % (
            m["baseline_compliance_probability"] * 100, min(solo), max(solo), max(solo), m["combined_intervention_probability"] * 100, m["naive_sum_of_solo_effects_pct"])
    except (FileNotFoundError, KeyError):
        return "Fig 5.1 probabilities: see tax_morale_model in outputs/stats/economic_model.json"


def expand_tokens(text):
    """The `feeds` descriptions never carry typed values: the token {FIG51} is replaced by the current model output."""
    if text and "{FIG51}" in text:
        text = text.replace("{FIG51}", _fig51())
    return text


def feeds_text(key):
    return expand_tokens(_BLOCK[key].get("feeds"))


def keys():
    return list(_BLOCK)


def assumption_id(key):
    """Stable id: ASS- + first 8 hex characters (upper case) of SHA-1(key)."""
    return "ASS-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()


@contextlib.contextmanager
def override(mapping):
    """Temporarily replace the values of some assumptions (used by the sensitivity analysis)."""
    old = dict(_overrides)
    _overrides.update(mapping)
    try:
        yield
    finally:
        _overrides.clear()
        _overrides.update(old)
