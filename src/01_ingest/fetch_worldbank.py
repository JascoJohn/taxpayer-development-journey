"""World Bank WDI snapshot fetcher: the ONLY code in this project that calls the network.

Called only by `run_all.py --fetch`. For every series listed under `worldbank.series` in config.yaml it requests all
available years from the WDI API v2, saves the RAW response unchanged to
    data/raw/worldbank/<indicator>_<YYYY-MM-DD>.json
and appends one row (URL, retrieval timestamp, SHA-256, size) to data/raw/worldbank/MANIFEST.csv.
Nothing is parsed or altered here. The analysis (macro_inputs.py) reads the snapshots named under `worldbank.snapshots`
in config.yaml; after a fetch, copy the new file names into that block to adopt them.

WDI data are licensed CC BY 4.0 (attribute: World Bank, World Development Indicators).
"""

import csv
import datetime
import hashlib
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/
import paths

TIMEOUT_SECONDS = 60
ATTEMPTS = 4
MANIFEST_COLUMNS = ["indicator", "countries", "years", "file", "url", "retrieved_at", "sha256", "bytes"]


def series_url(indicator, countries, years):
    base = paths.WB_CFG["api_base"].rstrip("/")
    return "%s/country/%s/indicator/%s?format=json&per_page=20000&date=%s" % (base, ";".join(countries), indicator, years)


def fetch_series(indicator, countries, years, today=None):
    """Download one series and save the raw bytes. Returns the manifest row (dict)."""
    url = series_url(indicator, countries, years)
    req = urllib.request.Request(url, headers={"User-Agent": "tdj-pipeline/1.0"})
    body = None
    for attempt in range(1, ATTEMPTS + 1):          # the WDI gateway answers 502 / times out now and then
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read()
            if body[:1] == b"[":
                break
            raise ValueError("response is not a JSON array")
        except Exception as e:
            print("    attempt %d/%d failed for %s: %s" % (attempt, ATTEMPTS, indicator, e))
            if attempt == ATTEMPTS:
                raise
            time.sleep(10)
    stamp = (today or datetime.date.today()).isoformat()
    os.makedirs(paths.WB_SNAPSHOT_DIR, exist_ok=True)
    fname = "%s_%s.json" % (indicator, stamp)
    with open(os.path.join(paths.WB_SNAPSHOT_DIR, fname), "wb") as f:      # unchanged bytes
        f.write(body)
    return {"indicator": indicator, "countries": ";".join(countries), "years": years, "file": fname, "url": url,
            "retrieved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}


def append_manifest(row):
    new = not os.path.exists(paths.WB_MANIFEST)
    with open(paths.WB_MANIFEST, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)


def fetch_all():
    """Fetch every configured series. Returns the list of manifest rows."""
    rows = []
    years = paths.WB_CFG["years"]
    for s in paths.WB_CFG["series"]:
        row = fetch_series(s["indicator"], s["countries"], years)
        append_manifest(row)
        rows.append(row)
        print("  %-18s %-22s %7d bytes  sha256 %s...  -> %s" % (row["indicator"], row["countries"], row["bytes"], row["sha256"][:12], row["file"]))
    print("  Manifest: %s. To adopt these snapshots set worldbank.snapshots in config.yaml to the file names above." %
          os.path.relpath(paths.WB_MANIFEST, paths.ROOT))
    return rows


if __name__ == "__main__":
    fetch_all()
