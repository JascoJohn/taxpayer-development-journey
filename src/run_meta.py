"""Run metadata kept OUT of the data outputs.

* Timestamps (generated-at / created-at / last-updated) are written to outputs/stats/run_meta.json
  instead of into the data files, so two runs of the same inputs give byte-identical data outputs.
* Deterministic identifiers: sha1_id() builds PREFIX-xxxxxx ids from content, and pipeline_run_id()
  hashes the SHA-256 of every input file plus config.yaml.
"""

import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

_run_id_cache = None


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load():
    try:
        with open(paths.RUN_META, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(d):
    os.makedirs(os.path.dirname(paths.RUN_META), exist_ok=True)
    with open(paths.RUN_META, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def stamp(file_key, field, when=None):
    """Record a timestamp for one field of one output file."""
    d = _load()
    d.setdefault("files", {}).setdefault(file_key, {})[field] = when or now()
    _save(d)


def stamp_item(file_key, item_id, field="created_at", when=None):
    """Record a timestamp for one item (an intervention or an assumption) of an output file."""
    d = _load()
    items = d.setdefault("files", {}).setdefault(file_key, {}).setdefault("items", {})
    items.setdefault(item_id, {})[field] = when or now()
    _save(d)


def get(file_key, field, default="n/a"):
    return _load().get("files", {}).get(file_key, {}).get(field, default)


def record_run(**fields):
    d = _load()
    d.setdefault("run", {}).update(fields)
    _save(d)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha1_id(prefix, text, length=6):
    """PREFIX-xxxxxx where xxxxxx = first `length` hex characters (upper case) of SHA-1(text)."""
    return "%s-%s" % (prefix, hashlib.sha1(text.encode("utf-8")).hexdigest()[:length].upper())


def input_files():
    """Every file the pipeline reads as input, plus config.yaml (project-relative names, sorted)."""
    cands = [paths.FINSCOPE_CSV, paths.FINSCOPE_DATAMAP, paths.INTERVENTIONS_YAML, paths.CONFIG_FILE,
             paths.TAX_EXEMPTIONS_XLSX, paths.ILFS_SAV, paths.CENSUS_SAV]
    def rel(p):
        try:
            return os.path.relpath(p, paths.ROOT).replace(os.sep, "/")
        except ValueError:            # a raw file on another drive (absolute path in config.yaml): use its file name
            return os.path.basename(p)
    return sorted((rel(p), p) for p in cands)


def pipeline_run_id():
    """First 8 hex characters of SHA-1 over 'name:sha256' of all input files and config.yaml.
    If the raw files are absent (a --from-processed run on a checkout without data/raw), the id
    recorded by the last run is reused."""
    global _run_id_cache
    if _run_id_cache:
        return _run_id_cache
    present = [(rel, p) for rel, p in input_files() if os.path.exists(p)]
    if not os.path.exists(paths.FINSCOPE_CSV):
        stored = _load().get("run", {}).get("pipeline_run_id")
        if stored:
            _run_id_cache = stored
            return stored
    h = hashlib.sha1()
    for rel, p in present:
        h.update(("%s:%s\n" % (rel, sha256_file(p))).encode("utf-8"))
    _run_id_cache = h.hexdigest()[:8]
    return _run_id_cache
