"""Rebuild all Phase 1 site data for Itbayat.

    python scripts/download_itbayat.py          # once, on a machine with network quota
    python -m aurora.data.build_itbayat [--load PLANT_LOG.csv]

Reads only data/itbayat/raw_small/ (see aurora/data/rawio.py); never touches
the network. Steps: check site.yaml and regenerate SOURCES.md's table; check
the raw inputs; IBTrACS typhoon flags and events; hourly load (synthetic, or
real logs with --load); validation report. A missing input is reported and its
step skipped. No data are substituted. Exit code 2 means an input is missing.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from . import paths, rawio, site as site_mod, typhoons, validate
from .load import read_real_load, synthetic_load


def _inputs(status: dict):
    for name, p in {**rawio.PHASE1_FILES, **rawio.PHASE2_FILES}.items():
        if p.exists():
            df = pd.read_parquet(p, columns=[])
            status[name] = f"{p.name}: {len(df)} rows {df.index.min():%Y-%m-%d}..{df.index.max():%Y-%m-%d}"
        else:
            status[name] = f"MISSING {p.relative_to(paths.ROOT)} (run scripts/download_itbayat.py)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--load", default=None, help="CSV/parquet of real hourly plant load (timestamp,total_kW[,critical_kW])")
    a = ap.parse_args(argv)
    status: dict[str, str] = {}

    # 1. site values
    s = site_mod.load_site()
    site_mod.write_sources(s)
    probs = site_mod.check(s, paths.SOURCES_MD.read_text())
    if probs:
        print("site.yaml problems:\n  " + "\n  ".join(probs))
        return 1
    n_missing = sum(e["status"] == "missing" for e in s["values"].values())
    n_unver = sum(e["status"] == "brief_unverified" for e in s["values"].values())
    status["site.yaml"] = f"ok ({len(s['values'])} values; {n_unver} brief_unverified, {n_missing} missing)"

    # 2. raw inputs (Phase 2 NWP files are listed for information)
    _inputs(status)

    # 3. typhoons
    if rawio.IBTRACS.exists():
        flags, ev = typhoons.build()
        status["typhoons"] = f"{len(ev)} storms within 500 km since 2015"
    else:
        status["typhoons"] = "skipped (IBTrACS input missing)"

    # 4. load
    if a.load:
        df = read_real_load(a.load, s)
        df.to_parquet(paths.LOAD_REAL)
        status["load"] = f"real logs {a.load} -> {paths.LOAD_REAL.name}"
    else:
        temp, tsrc = None, "none"
        for name, p in (("ERA5", rawio.ERA5), ("NASA POWER", rawio.NASA_POWER)):
            if p.exists():
                temp, tsrc = pd.read_parquet(p, columns=["temp_c"])["temp_c"], name
                break
        end = temp.index.max() if temp is not None else pd.Timestamp.now(tz="UTC").floor("D")
        idx = pd.date_range(pd.Timestamp("2015-01-01", tz=paths.LOCAL_TZ).tz_convert("UTC"), end, freq="h")
        df = synthetic_load(idx, temp, s)
        df.attrs["temperature_input"] = tsrc
        df.to_parquet(paths.LOAD_SYNTH)
        status["load"] = (f"SYNTHETIC -> {paths.LOAD_SYNTH.name} (temperature from {tsrc}; "
                          f"peak {df['total_kW'].max():.0f} kW)")

    # 5. validation
    out = validate.build_report()
    status["validation"] = str(out.relative_to(paths.ROOT))

    print("\nPhase 1 build summary")
    for k, v in status.items():
        print(f"  {k:12s} {v}")
    missing = [k for k, v in status.items() if v.startswith("MISSING")]
    if missing:
        print(f"\nMissing inputs: {', '.join(missing)}. Run scripts/download_itbayat.py, then rebuild.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
