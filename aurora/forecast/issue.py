"""Write one 48 h forecast CSV (digital-twin schema plus P10/P50/P90 bands).

    python -m aurora.forecast.issue --issue 2025-07-20T16:00Z           # from the committed backtest
    python -m aurora.forecast.issue --issue 2025-07-20T16:00Z --no-nwp  # force the comms-loss fallback
    python -m aurora.forecast.issue --live                              # latest NWP from Open-Meteo

Issue times are 16:00 UTC (00:00 PHT). ``--live`` needs network access and the
models from ``python -m aurora.forecast.build``; if the NWP request fails the
output is the fallback forecast with ``fallback = True``.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from . import operational as O
from .build import LEAN_DEMAND, LEAN_SOLAR


def main(argv=None) -> int:
    """Issue one 48 h forecast CSV (archived, live, or the no-NWP fallback)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", help="issue time, e.g. 2025-07-20T16:00Z")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--no-nwp", action="store_true", help="simulate a failed NWP request")
    ap.add_argument("--pv-kwp", type=float, default=O.PV_KWP_INL, help="PV array size (kWp DC), default 300")
    ap.add_argument("--out", default=str(O.ISSUE_DIR))
    a = ap.parse_args(argv)
    from pathlib import Path

    out = Path(a.out)
    if a.live:
        df, note = O.live(a.issue, pv_kwp=a.pv_kwp)
        print(note)
    elif not a.issue:
        ap.error("--issue or --live is required")
    elif a.no_nwp:
        from .features import load_truth

        it = O.normalise_issue(a.issue)
        truth = load_truth()["ghi_sat"]
        df = O.forecast_issue(it, nwp=None, ghi_obs=truth[truth.index <= it], pv_kwp=a.pv_kwp)
    else:
        solar, dem = pd.read_parquet(LEAN_SOLAR), pd.read_parquet(LEAN_DEMAND)
        df = O.from_backtest(solar, dem, a.issue, a.pv_kwp)
    print(O.write_csv(df, out, tag="_fallback" if df["fallback"].any() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
