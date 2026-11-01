"""Rebuild all Phase 1 site data for Itbayat.

    python -m aurora.data.build_itbayat [--refresh] [--load PLANT_LOG.csv]

Steps: check site.yaml and regenerate SOURCES.md's table; download weather
(ERA5, satellite, NASA POWER); IBTrACS typhoon flags and events; hourly load
(synthetic, or real logs with --load); validation report. A blocked download is
reported and the step is skipped. No data are substituted. Exit code 2 means
at least one step was blocked.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from . import paths, site as site_mod, typhoons, validate, weather
from .http import DownloadBlocked
from .load import read_real_load, synthetic_load


def _weather(refresh: bool, status: dict):
    jobs = [("ERA5", weather.fetch_era5, paths.WEATHER_ERA5),
            ("Satellite", weather.fetch_satellite, paths.WEATHER_SAT),
            ("NASA POWER", weather.fetch_power, paths.WEATHER_POWER)]
    for name, fn, p in jobs:
        if p.exists() and not refresh:
            status[name] = f"cached ({p.name})"
            continue
        try:
            df = fn()
            weather.save(df, p)
            status[name] = f"downloaded {len(df)} h -> {p.name}"
        except DownloadBlocked as exc:
            status[name] = f"BLOCKED: {exc}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
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

    # 2. weather
    _weather(a.refresh, status)

    # 3. typhoons
    try:
        if paths.TYPHOON_HOURLY.exists() and not a.refresh:
            status["IBTrACS"] = "cached"
        else:
            flags, ev = typhoons.build()
            status["IBTrACS"] = f"{len(ev)} storms within 500 km since 2015"
    except DownloadBlocked as exc:
        status["IBTrACS"] = f"BLOCKED: {exc}"

    # 4. load
    if a.load:
        df = read_real_load(a.load, s)
        df.to_parquet(paths.LOAD_REAL)
        status["load"] = f"real logs {a.load} -> {paths.LOAD_REAL.name}"
    else:
        temp, tsrc = None, "none"
        for name, p in (("ERA5", paths.WEATHER_ERA5), ("NASA POWER", paths.WEATHER_POWER)):
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
    blocked = [k for k, v in status.items() if v.startswith("BLOCKED")]
    if blocked:
        print(f"\nBlocked: {', '.join(blocked)}. Re-run when the source is reachable.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
