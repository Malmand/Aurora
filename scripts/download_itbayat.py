#!/usr/bin/env python
"""Download every external input that Phases 1-2 need, for Itbayat.

Run on a machine with its own network quota (not the cloud session: the free
Open-Meteo quota is shared through the proxy IP there).

    pip install -e ".[download]"
    python scripts/download_itbayat.py                 # everything, ERA5 via Open-Meteo
    python scripts/download_itbayat.py --source cds    # ERA5 via Copernicus CDS (needs ~/.cdsapirc)
    python scripts/download_itbayat.py --only era5 nwp # a subset

Writes zstd-compressed parquet to data/itbayat/raw_small/ plus MANIFEST.json
(source, URL, request, rows, period, sha256). Each finished chunk is cached in
data/itbayat/raw/cache/, so a rerun after a quota error resumes where it
stopped. Nothing is ever filled in: a failed chunk stops that dataset, which is
reported, and the file is not written.

Datasets
  era5       ERA5 hourly 2015-present (Open-Meteo archive, models=era5; or CDS)
  satellite  Open-Meteo satellite radiation API, 2015-present
  power      NASA POWER hourly (CERES SYN1deg + MERRA-2), 2015-present
  nwp        Open-Meteo previous-runs API: ECMWF IFS 0.25, GFS, ICON, JMA;
             lead days 0, 1, 2
  ibtracs    IBTrACS v04r01 West Pacific tracks, seasons 2014 onwards
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurora.data import paths, rawio  # noqa: E402
from aurora.data.http import DownloadBlocked, download, get, get_json  # noqa: E402

ERA5_OM_URL = "https://archive-api.open-meteo.com/v1/archive"
SAT_URL = "https://satellite-api.open-meteo.com/v1/archive"
PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
IBTRACS_URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-"
               "climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv")
POWER_VARS = {"ALLSKY_SFC_SW_DWN": "ghi_wm2", "ALLSKY_SFC_SW_DNI": "dni_wm2",
              "ALLSKY_SFC_SW_DIFF": "dhi_wm2", "CLRSKY_SFC_SW_DWN": "ghi_clear_wm2",
              "T2M": "temp_c", "RH2M": "rh_pct", "WS10M": "wind_ms", "PS": "sp_hpa"}

CACHE = paths.RAW_DIR / "cache"
START = dt.date(2015, 1, 1)
NWP_START = dt.date(2022, 1, 1)   # earliest date requested; empty leading rows are dropped
PAUSE_S = 1.0


# ---------------------------------------------------------------- helpers
def chunks(start: dt.date, end: dt.date, months: int):
    a = start
    while a <= end:
        y, m = a.year + (a.month - 1 + months) // 12, (a.month - 1 + months) % 12 + 1
        b = min(end, dt.date(y, m, 1) - dt.timedelta(days=1))
        yield a, b
        a = b + dt.timedelta(days=1)


def cached(name: str, a: dt.date, b: dt.date, fetch):
    """Fetch one chunk, or reuse it from the cache if complete."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{name}_{a:%Y%m%d}_{b:%Y%m%d}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    df = fetch(a, b)
    if b < dt.date.today() - dt.timedelta(days=10):  # do not cache still-changing recent data
        df.to_parquet(f)
    time.sleep(PAUSE_S)
    return df


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def write(df: pd.DataFrame, path: Path, meta: dict, manifest: dict):
    df = df[~df.index.duplicated()].sort_index()
    df.attrs.update({k: str(v) for k, v in meta.items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    manifest[path.name] = {
        **meta, "rows": len(df), "columns": list(map(str, df.columns)),
        "first": str(df.index.min()) if len(df) else None,
        "last": str(df.index.max()) if len(df) else None,
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256(path), "bytes": path.stat().st_size,
    }
    print(f"  wrote {path.relative_to(ROOT)}: {len(df)} rows, {path.stat().st_size/1e6:.1f} MB")


def om_params(a, b, variables, **extra):
    p = {"latitude": paths.LAT, "longitude": paths.LON, "start_date": a.isoformat(),
         "end_date": b.isoformat(), "hourly": ",".join(variables), "timezone": "GMT",
         "wind_speed_unit": "ms"}
    p.update(extra)
    return p


# ---------------------------------------------------------------- datasets
def era5_open_meteo(start, end, manifest):
    grid = {}

    def fetch(a, b):
        js = get_json(ERA5_OM_URL, om_params(a, b, rawio.ERA5_OM_VARS, models="era5"), timeout=300)
        grid.update(lat=js.get("latitude"), lon=js.get("longitude"), elev=js.get("elevation"))
        return rawio.om_hourly_to_frame(js["hourly"])

    df = pd.concat(cached("era5_om", a, b, fetch) for a, b in chunks(start, end, 12))
    write(df, rawio.ERA5, {
        "source": "ERA5 reanalysis (Hersbach et al. 2020) via Open-Meteo historical API, models=era5",
        "url": ERA5_OM_URL, "radiation_convention": "mean of preceding hour",
        "grid_latitude": grid.get("lat"), "grid_longitude": grid.get("lon"),
        "note": "Reanalysis, not a measurement."}, manifest)


def era5_cds(start, end, manifest):
    import cdsapi
    import xarray as xr

    glat, glon = rawio.era5_grid_point()
    client = cdsapi.Client()

    def fetch(a, b):
        days = pd.date_range(a, b, freq="D")
        req = {
            "product_type": ["reanalysis"], "variable": rawio.CDS_VARIABLES,
            "year": [str(a.year)], "month": [f"{a.month:02d}"],
            "day": sorted({f"{d.day:02d}" for d in days}),
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": [glat, glon, glat, glon],
            "data_format": "netcdf", "download_format": "unarchived",
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "era5.download"
            client.retrieve("reanalysis-era5-single-levels", req, str(target))
            ncs = [target]
            if zipfile.is_zipfile(target):   # mixed instant/accum variables arrive as a zip
                with zipfile.ZipFile(target) as z:
                    z.extractall(tmp)
                ncs = sorted(Path(tmp).glob("*.nc"))
            frames = []
            for nc in ncs:
                with xr.open_dataset(nc) as ds:
                    tname = "valid_time" if "valid_time" in ds.dims else "time"
                    ds = ds.sel(latitude=glat, longitude=glon, method="nearest")
                    keep = [v for v in ds.data_vars if ds[v].dims == (tname,)]
                    f = ds[keep].to_dataframe()[keep]
                    f.index = pd.DatetimeIndex(f.index).tz_localize("UTC")
                    frames.append(f)
        raw = pd.concat(frames, axis=1)
        raw = raw.loc[:, ~raw.columns.duplicated()]
        return rawio.cds_to_schema(raw)

    df = pd.concat(cached("era5_cds", a, b, fetch) for a, b in chunks(start, end, 1))
    write(df, rawio.ERA5, {
        "source": "ERA5 reanalysis (Hersbach et al. 2020), Copernicus CDS reanalysis-era5-single-levels",
        "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels",
        "radiation_convention": "mean of preceding hour (ERA5 accumulation ending at timestamp)",
        "grid_latitude": glat, "grid_longitude": glon,
        "dni_method": "fdir / cos(zenith at mid-hour), 0 for zenith > 87.5 deg",
        "note": "Reanalysis, not a measurement."}, manifest)


def satellite(start, end, manifest):
    grid = {}

    def fetch(a, b):
        js = get_json(SAT_URL, om_params(a, b, rawio.SAT_OM_VARS), timeout=300)
        grid.update(lat=js.get("latitude"), lon=js.get("longitude"))
        return rawio.om_hourly_to_frame(js["hourly"])

    df = pd.concat(cached("satellite", a, b, fetch) for a, b in chunks(start, end, 12)).dropna(how="all")
    write(df, rawio.SATELLITE, {
        "source": "Open-Meteo satellite radiation API", "url": SAT_URL,
        "radiation_convention": "mean of preceding hour",
        "grid_latitude": grid.get("lat"), "grid_longitude": grid.get("lon"),
        "note": "Satellite retrieval, not a measurement. Record the underlying satellite product [verify]."},
        manifest)


def power(start, end, manifest):
    def fetch(a, b):
        p = {"parameters": ",".join(POWER_VARS), "community": "RE", "latitude": paths.LAT,
             "longitude": paths.LON, "start": a.strftime("%Y%m%d"), "end": b.strftime("%Y%m%d"),
             "format": "JSON", "time-standard": "UTC"}
        js = get_json(POWER_URL, p, timeout=600)
        fill = js.get("header", {}).get("fill_value", -999.0)
        df = pd.DataFrame(js["properties"]["parameter"])
        df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
        df.index.name = "time"
        return df.replace(fill, float("nan")).rename(columns=POWER_VARS)

    df = pd.concat(cached("power", a, b, fetch) for a, b in chunks(start, end, 12))
    df = rawio.power_to_hour_ending(df)
    write(df, rawio.NASA_POWER, {
        "source": "NASA POWER hourly v2 (CERES SYN1deg radiation, MERRA-2 meteorology)", "url": POWER_URL,
        "radiation_convention": "mean of preceding hour (relabelled +1 h from POWER hour-start stamps)",
        "note": "Satellite/reanalysis product, not a measurement."}, manifest)


def nwp(start, end, manifest, models):
    for key in models:
        name = rawio.NWP_MODELS[key]
        variables = [f"{v}_previous_day{d}" if d else v
                     for v in rawio.NWP_OM_VARS for d in rawio.LEAD_DAYS]
        print(f" NWP {key} ({name})")

        def fetch(a, b, name=name, variables=variables):
            js = get_json(PREV_URL, om_params(a, b, variables, models=name), timeout=300)
            return rawio.om_previous_runs_to_frame(js["hourly"])

        try:
            df = pd.concat(cached(f"nwp_{key}", a, b, fetch) for a, b in chunks(start, end, 1))
        except DownloadBlocked as exc:
            print(f"  BLOCKED {key}: {exc}")
            manifest.setdefault("_errors", {})[f"previous_runs_{key}"] = str(exc)
            continue
        df = df.dropna(axis=1, how="all")
        first = df.dropna(how="all").index.min()
        df = df.loc[first:] if first is not pd.NaT else df
        write(df, rawio.previous_runs_path(key), {
            "source": f"Open-Meteo previous-runs API, model {name}", "url": PREV_URL,
            "lead_days": "d0 = latest run, dN = run issued N days before (Open-Meteo *_previous_dayN)",
            "radiation_convention": "mean of preceding hour",
            "note": "NWP forecasts archived by Open-Meteo. Columns missing for a model were not served."},
            manifest)


def ibtracs(manifest):
    from aurora.data.typhoons import read_ibtracs
    raw = download(IBTRACS_URL, paths.RAW_DIR / "ibtracs.WP.list.v04r01.csv", force=True)
    df = read_ibtracs(raw, since=2014).set_index("time")
    write(df, rawio.IBTRACS, {
        "source": "IBTrACS v04r01 West Pacific (Knapp et al. 2010, doi:10.1175/2009BAMS2755.1)",
        "url": IBTRACS_URL, "filter": "seasons >= 2014",
        "intensity": "wind_kt/pres_hpa: RSMC Tokyo first, then WMO, then USA"}, manifest)


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=["era5", "satellite", "power", "nwp", "ibtracs"],
                    default=["era5", "satellite", "power", "nwp", "ibtracs"])
    ap.add_argument("--source", choices=["open-meteo", "cds"], default="open-meteo",
                    help="where ERA5 comes from (default open-meteo)")
    ap.add_argument("--start", default=START.isoformat())
    ap.add_argument("--end", default=None, help="default: today - 8 days (ERA5 latency)")
    ap.add_argument("--nwp-start", default=NWP_START.isoformat())
    ap.add_argument("--models", nargs="+", choices=list(rawio.NWP_MODELS), default=list(rawio.NWP_MODELS))
    a = ap.parse_args(argv)
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else dt.date.today() - dt.timedelta(days=8)

    manifest = json.loads(rawio.MANIFEST.read_text(encoding="utf-8")) if rawio.MANIFEST.exists() else {}
    manifest.pop("_errors", None)
    jobs = {
        "era5": lambda: (era5_cds if a.source == "cds" else era5_open_meteo)(start, end, manifest),
        "satellite": lambda: satellite(start, end, manifest),
        "power": lambda: power(start, end, manifest),
        "nwp": lambda: nwp(dt.date.fromisoformat(a.nwp_start), end, manifest, a.models),
        "ibtracs": lambda: ibtracs(manifest),
    }
    failed = []
    for name in a.only:
        print(f"[{name}]")
        try:
            jobs[name]()
        except DownloadBlocked as exc:
            print(f"  BLOCKED: {exc}\n  Finished chunks are cached; rerun later to resume.")
            manifest.setdefault("_errors", {})[name] = str(exc)
            failed.append(name)
    rawio.RAW_SMALL.mkdir(parents=True, exist_ok=True)
    rawio.MANIFEST.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nManifest: {rawio.MANIFEST.relative_to(ROOT)}")
    if failed or manifest.get("_errors"):
        print("Incomplete:", ", ".join(sorted(set(failed) | set(manifest.get("_errors", {})))))
        return 2
    print("All done. Next: python -m aurora.data.build_itbayat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
