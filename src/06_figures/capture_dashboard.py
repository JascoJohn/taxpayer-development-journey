"""Dashboard screenshots (Block F4; opt-in: `python run_all.py --screenshots`).

Starts the Streamlit dashboard headless on a free local port, opens each of the seven pages in headless Chromium (Playwright) at a fixed viewport, waits until the page has rendered and
saves outputs/figures/dashboard_<page>.png. The server is stopped afterwards. Needs `pip install playwright` and `python -m playwright install chromium`
(environment/requirements-screenshots.txt); nothing here runs without --screenshots. The screenshots are not byte-reproducible (browser rendering) and are not part of the idempotency check.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # src/
import paths  # noqa: E402

PAGES = [("home", ""), ("seed", "Seed"), ("entry", "Entry"), ("active", "Active"), ("enterprise", "Enterprise"), ("asset", "Asset"), ("legacy", "Legacy")]
VIEWPORT = {"width": 1400, "height": 2800}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  screenshots skipped: Playwright is not installed (pip install -r environment/requirements-screenshots.txt; python -m playwright install chromium)")
        return []
    dash = os.path.join(paths.ROOT, "dashboard")
    out_dir = os.path.join(paths.ROOT, "outputs", "figures")
    os.makedirs(out_dir, exist_ok=True)
    port = _free_port()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", os.path.join(dash, "Home.py"), "--server.headless", "true", "--server.port", str(port),
                             "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"], cwd=dash, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    written = []
    try:
        base = "http://127.0.0.1:%d" % port
        for _ in range(120):
            try:
                urllib.request.urlopen(base + "/_stcore/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit("the dashboard did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            for name, route in PAGES:
                page.goto(base + "/" + route, wait_until="networkidle")
                page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60000)
                page.wait_for_timeout(4000)                                   # let the metrics finish rendering
                # Plotly's JavaScript bundle is loaded the first time a chart is shown (Home, the first page, needs 5-8 s on a cold start): wait until every chart on the page has drawn
                page.wait_for_function("() => Array.from(document.querySelectorAll('[data-testid=\"stPlotlyChart\"]')).every(e => e.querySelector('.js-plotly-plot svg.main-svg'))", timeout=60000)
                page.wait_for_timeout(1000)
                path = os.path.join(out_dir, "dashboard_%s.png" % name)
                page.screenshot(path=path, full_page=True)
                written.append(path)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
    print("  screenshots: %d dashboard pages written to outputs/figures" % len(written))
    return written


if __name__ == "__main__":
    main()
