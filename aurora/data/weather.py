"""Hourly weather for Itbayat from three independent products.

* ERA5 reanalysis via the Open-Meteo historical archive API (models=era5).
  Main meteorological series (GHI, DNI, DHI, temperature, wind, cloud, pressure).
* Satellite-derived radiation via the Open-Meteo satellite radiation API.
  Used to cross-check ERA5 irradiance (and as the Phase 2 reference candidate).
* NASA POWER hourly (CERES SYN1deg radiation, MERRA-2 meteorology).
  A second independent cross-check.

None of these are measurements. They are reanalysis or satellite retrievals.

Timestamps are stored in UTC. Open-Meteo radiation values are the mean over
the hour *ending* at the timestamp; temperature, wind and pressure are
instantaneous. The time convention of NASA POWER is checked empirically in
the validation step (lag of maximum correlation against the satellite series).
"""
from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd

from . import paths
from .http import get

ERA5_URL = "https://archive-api.open-meteo.com/v1/archive"
SAT_URL = "https://satellite-api.open-meteo.com/v1/archive"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

ERA5_VARS = [
    "shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation",
    "temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation",
    "pressure_msl", "surface_pressure",
    "cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
]
RENAME = {
    "shortwave_radiation": "ghi_wm2",
    "direct_normal_irradiance": "dni_wm2",
    "diffuse_radiation": "dhi_wm2",
    "temperature_2m": "temp_c",
    "relative_humidity_2m": "rh_pct",
    "dew_point_2m": "dewpoint_c",
    "precipitation": "precip_mm",
    "pressure_msl": "mslp_hpa",
    "surface_pressure": "sp_hpa",
    "cloud_cover": "cloud_pct",
    "cloud_cover_low": "cloud_low_pct",
    "cloud_cover_mid": "cloud_mid_pct",
    "cloud_cover_high": "cloud_high_pct",
    "wind_speed_10m": "wind_ms",
    "wind_direction_10m": "wind_dir_deg",
    "wind_gusts_10m": "gust_ms",
}
SAT_VARS = ["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation"]
POWER_VARS = {
    "ALLSKY_SFC_SW_DWN": "ghi_wm2",
    "ALLSKY_SFC_SW_DNI": "dni_wm2",
    "ALLSKY_SFC_SW_DIFF": "dhi_wm2",
    "CLRSKY_SFC_SW_DWN": "ghi_clear_wm2",
    "T2M": "temp_c",
}

START = dt.date(2015, 1, 1)


def default_end() -> dt.date:
    # ERA5T has about 5 days latency; keep a margin.
    return dt.date.today() - dt.timedelta(days=8)


def _years(start: dt.date, end: dt.date):
    y = start.year
    while y <= end.year:
        a = max(start, dt.date(y, 1, 1))
        b = min(end, dt.date(y, 12, 31))
        yield a, b
        y += 1


def _open_meteo(url: str, variables: list[str], start: dt.date, end: dt.date,
                extra: dict | None = None) -> pd.DataFrame:
    frames, meta = [], {}
    for a, b in _years(start, end):
        params = {
            "latitude": paths.LAT, "longitude": paths.LON,
            "start_date": a.isoformat(), "end_date": b.isoformat(),
            "hourly": ",".join(variables), "timezone": "GMT",
            "wind_speed_unit": "ms",
        }
        params.update(extra or {})
        js = get(url, params=params, timeout=300).json()
        meta = {k: js.get(k) for k in ("latitude", "longitude", "elevation")}
        h = js["hourly"]
        df = pd.DataFrame(h)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        frames.append(df.set_index("time"))
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()].rename(columns=RENAME)
    out.attrs.update({f"grid_{k}": str(v) for k, v in meta.items()})
    return out


def fetch_era5(start=START, end=None) -> pd.DataFrame:
    df = _open_meteo(ERA5_URL, ERA5_VARS, start, end or default_end(), {"models": "era5"})
    df.attrs.update(source="ERA5 reanalysis via Open-Meteo historical API (models=era5)",
                    url=ERA5_URL, radiation_convention="mean of preceding hour",
                    note="Reanalysis, not a measurement.")
    return df


def fetch_satellite(start=START, end=None) -> pd.DataFrame:
    df = _open_meteo(SAT_URL, SAT_VARS, start, end or default_end())
    df = df.dropna(how="all")
    df.attrs.update(source="Open-Meteo satellite radiation API", url=SAT_URL,
                    radiation_convention="mean of preceding hour",
                    note="Satellite retrieval, not a measurement.")
    return df


def fetch_power(start=START, end=None) -> pd.DataFrame:
    end = end or default_end()
    frames = []
    for a, b in _years(start, end):
        params = {
            "parameters": ",".join(POWER_VARS), "community": "RE",
            "latitude": paths.LAT, "longitude": paths.LON,
            "start": a.strftime("%Y%m%d"), "end": b.strftime("%Y%m%d"),
            "format": "JSON", "time-standard": "UTC",
        }
        js = get(POWER_URL, params=params, timeout=600).json()
        fill = js.get("header", {}).get("fill_value", -999.0)
        par = js["properties"]["parameter"]
        df = pd.DataFrame(par)
        df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
        frames.append(df.replace(fill, float("nan")))
    out = pd.concat(frames).sort_index().rename(columns=POWER_VARS)
    out = out[~out.index.duplicated()]
    out.index.name = "time"
    return power_to_hour_ending(out)


def power_to_hour_ending(df: pd.DataFrame) -> pd.DataFrame:
    """POWER stamps hourly means at the hour start; Open-Meteo at the hour end.

    Shift POWER by +1 h so all products use hour-ending labels. The lag of
    maximum correlation with the satellite series was +1 h before the shift
    (0.975 vs 0.925 at lag 0, 2015-2026); validate.py re-checks it.
    """
    if df.attrs.get("radiation_convention") == "mean of preceding hour":
        return df
    df = df.copy()
    df.index = df.index + pd.Timedelta(hours=1)
    df.attrs.update(source="NASA POWER hourly v2 (CERES SYN1deg + MERRA-2)", url=POWER_URL,
                    radiation_convention="mean of preceding hour",
                    relabelled="index shifted +1 h from POWER hour-start labels",
                    note="Satellite/reanalysis product, not a measurement.")
    return df


def save(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--product", choices=["era5", "satellite", "power", "all"], default="all")
    ap.add_argument("--start", default=START.isoformat())
    ap.add_argument("--end", default=None)
    a = ap.parse_args(argv)
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else None
    jobs = {"era5": (fetch_era5, paths.WEATHER_ERA5),
            "satellite": (fetch_satellite, paths.WEATHER_SAT),
            "power": (fetch_power, paths.WEATHER_POWER)}
    for name, (fn, p) in jobs.items():
        if a.product in (name, "all"):
            df = fn(start, end)
            save(df, p)
            print(f"{name}: {len(df)} rows {df.index.min()} .. {df.index.max()} -> {p}")


if __name__ == "__main__":
    main()
