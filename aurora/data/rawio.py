"""Raw input files for Phases 1-2: locations, common schema and conversions.

All downloads are done by ``scripts/download_itbayat.py``, run on a machine
with its own network quota. It writes zstd-compressed parquet files to
``data/itbayat/raw_small/`` plus ``MANIFEST.json``. The pipeline only reads
these files. It never touches the network.

Common weather schema (UTC index named ``time``; radiation is the mean of the
hour *ending* at the timestamp; state variables are instantaneous):

    ghi_wm2, dni_wm2, dhi_wm2, temp_c, rh_pct, dewpoint_c, precip_mm,
    mslp_hpa, sp_hpa, cloud_pct, cloud_low_pct, cloud_mid_pct, cloud_high_pct,
    wind_ms, wind_dir_deg, gust_ms

Previous-runs NWP files use the same names with a lead-day suffix:
``ghi_wm2_d0``, ``ghi_wm2_d1``, ``ghi_wm2_d2``. ``_dN`` is the value for that
hour from the run issued N days earlier (Open-Meteo ``*_previous_dayN``),
so d1 covers lead times of about 24-47 h and d2 about 48-71 h.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths

RAW_SMALL = paths.SITE_DIR / "raw_small"
MANIFEST = RAW_SMALL / "MANIFEST.json"
ERA5 = RAW_SMALL / "era5_hourly.parquet"
SATELLITE = RAW_SMALL / "satellite_radiation_hourly.parquet"
NASA_POWER = RAW_SMALL / "nasa_power_hourly.parquet"
IBTRACS = RAW_SMALL / "ibtracs_wp_tracks.parquet"
NWP_MODELS = {  # our key -> Open-Meteo model name
    "ecmwf": "ecmwf_ifs025",
    "gfs": "gfs_seamless",
    "icon": "icon_seamless",
    "jma": "jma_seamless",
}
LEAD_DAYS = (0, 1, 2)


def previous_runs_path(model: str):
    return RAW_SMALL / f"previous_runs_{model}.parquet"


PHASE1_FILES = {"ERA5": ERA5, "Satellite": SATELLITE, "NASA POWER": NASA_POWER, "IBTrACS": IBTRACS}
PHASE2_FILES = {f"NWP {m}": previous_runs_path(m) for m in NWP_MODELS}

# Open-Meteo variable -> schema name
OM_RENAME = {
    "shortwave_radiation": "ghi_wm2",
    "direct_normal_irradiance": "dni_wm2",
    "diffuse_radiation": "dhi_wm2",
    "direct_radiation": "bhi_wm2",
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
ERA5_OM_VARS = [
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]
SAT_OM_VARS = ["shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation"]
NWP_OM_VARS = [
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
    "wind_gusts_10m",
]


def read(path) -> pd.DataFrame | None:
    """Read a raw_small parquet, or None if it has not been downloaded."""
    return pd.read_parquet(path) if path.exists() else None


def om_hourly_to_frame(hourly: dict) -> pd.DataFrame:
    """Open-Meteo 'hourly' JSON block (timezone=GMT) -> schema frame."""
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    return df.rename(columns=OM_RENAME)


def om_previous_runs_to_frame(hourly: dict) -> pd.DataFrame:
    """Previous-runs JSON block -> columns '<schema>_d<N>'."""
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    cols = {}
    for c in df.columns:
        base, lead = c, 0
        if "_previous_day" in c:
            base, n = c.split("_previous_day")
            lead = int(n)
        cols[c] = f"{OM_RENAME.get(base, base)}_d{lead}"
    return df.rename(columns=cols)


def power_to_hour_ending(df: pd.DataFrame) -> pd.DataFrame:
    """NASA POWER stamps hourly means at the hour start; shift +1 h to hour-ending.

    Checked on 2015-2026: lag of maximum correlation with the satellite series
    was +1 h before the shift (r 0.975 vs 0.925 at lag 0); validate.py re-checks.
    """
    out = df.copy()
    out.index = out.index + pd.Timedelta(hours=1)
    out.index.name = "time"
    return out


# ERA5 from the Copernicus CDS (netCDF short names) -> schema
CDS_VARIABLES = [
    "surface_solar_radiation_downwards",
    "total_sky_direct_solar_radiation_at_surface",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "total_precipitation",
    "mean_sea_level_pressure",
    "surface_pressure",
    "total_cloud_cover",
    "low_cloud_cover",
    "medium_cloud_cover",
    "high_cloud_cover",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "10m_wind_gust_since_previous_post_processing",
]


def era5_grid_point(lat=paths.LAT, lon=paths.LON) -> tuple[float, float]:
    """Nearest point of the 0.25 deg ERA5 grid."""
    return round(lat * 4) / 4, round(lon * 4) / 4


def magnus_rh(t_c, td_c):
    """Relative humidity (%) from temperature and dew point (Magnus, over water)."""
    a, b = 17.625, 243.04
    return 100 * np.exp(a * td_c / (b + td_c) - a * t_c / (b + t_c))


def cds_to_schema(raw: pd.DataFrame, lat=paths.LAT, lon=paths.LON) -> pd.DataFrame:
    """Convert CDS ERA5 point data (UTC index, netCDF short names) to the schema.

    ERA5 accumulations (ssrd, fdir, tp) at time t cover the hour ending at t,
    so they match the hour-ending convention. DNI = fdir / cos(zenith), with the
    zenith at mid-hour; set to 0 when the sun is within 2.5 deg of the horizon.
    """
    import pvlib

    def pick(*names):
        for n in names:
            if n in raw:
                return raw[n]
        return pd.Series(np.nan, index=raw.index)

    out = pd.DataFrame(index=raw.index)
    ssrd, fdir = pick("ssrd") / 3600.0, pick("fdir") / 3600.0
    out["ghi_wm2"] = ssrd.clip(lower=0)
    out["dhi_wm2"] = (ssrd - fdir).clip(lower=0)
    sp_ = pvlib.solarposition.get_solarposition(raw.index - pd.Timedelta(minutes=30), lat, lon)
    cosz = np.cos(np.radians(sp_["zenith"].to_numpy()))
    dni = np.where(cosz > np.cos(np.radians(87.5)), fdir.to_numpy() / np.maximum(cosz, 1e-6), 0.0)
    out["dni_wm2"] = np.clip(dni, 0, 1400)
    t, td = pick("t2m") - 273.15, pick("d2m") - 273.15
    out["temp_c"], out["dewpoint_c"] = t, td
    out["rh_pct"] = magnus_rh(t, td).clip(upper=100)
    out["precip_mm"] = (pick("tp") * 1000).clip(lower=0)
    out["mslp_hpa"], out["sp_hpa"] = pick("msl") / 100, pick("sp") / 100
    for src, dst in (
        ("tcc", "cloud_pct"),
        ("lcc", "cloud_low_pct"),
        ("mcc", "cloud_mid_pct"),
        ("hcc", "cloud_high_pct"),
    ):
        out[dst] = pick(src) * 100
    u, v = pick("u10"), pick("v10")
    out["wind_ms"] = np.hypot(u, v)
    out["wind_dir_deg"] = (np.degrees(np.arctan2(-u, -v)) + 360) % 360
    out["gust_ms"] = pick("fg10", "i10fg", "10fg")
    out.index.name = "time"
    return out
