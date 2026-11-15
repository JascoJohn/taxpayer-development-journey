"""Runs every figure script of this folder (fig_*.py, in name order) and reports what was written. Called by run_all.py (step 10b); also runnable alone."""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def run_figures():
    written = []
    for f in sorted(os.listdir(HERE)):
        if f.startswith("fig_") and f.endswith(".py"):
            mod = importlib.import_module(f[:-3])
            written += mod.make()
    import journey_graphic                                   # Editing Pass 1: the Chapter 4 journey graphic (not a data figure; no fig_ prefix)
    written += journey_graphic.make()
    import cover_poster, theory_of_change                    # Editing Pass 1b: the rebuilt cover poster and Theory of Change graphic (not data figures; no fig_ prefix)
    written += cover_poster.make()
    written += theory_of_change.make()
    print("  figures: %d files written to outputs/figures (%d figures; PNG and SVG)" % (len(written), len(written) // 2))
    return written


if __name__ == "__main__":
    run_figures()
