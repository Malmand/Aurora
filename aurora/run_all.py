"""Rebuild every number and figure of the deck from the committed results.

    python -m aurora.run_all            # headline numbers and every slide figure (under a minute, no simulation)
    python -m aurora.run_all --check    # only check that the headline numbers still match results/headline.json

The simulations themselves (hours of CPU) are run separately:
    python -m aurora.forecast.build                         # Phase 2 forecast backtest
    python -m aurora.experiments.phase4b run --stage A      # sizing sweep, NPC and INL sizes
    python -m aurora.experiments.phase4b run --stage B      # chosen size: storms, years, stress tests
    python -m aurora.experiments.phase4b tables
"""

from __future__ import annotations

import argparse
import sys
import time


def main(argv=None) -> int:
    """Rebuild the headline numbers and every slide figure, or with --check only verify the numbers."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    from .experiments import headline
    from .plotting import calibration, slides

    if a.check:
        return headline.main(["--check"])
    steps = [
        ("headline numbers", lambda: headline.main([])),
        (
            "slide figures (figures/slides/)",
            lambda: [draw() for draw in slides.FIGS.values()],
        ),
        ("load calibration figure", calibration.main),
    ]
    for name, fn in steps:
        t = time.time()
        fn()
        print(f"[done] {name} in {time.time() - t:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
