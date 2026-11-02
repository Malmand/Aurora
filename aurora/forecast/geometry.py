"""Sun position, clear-sky irradiance and the clear-sky index target.

All series use the repository convention: UTC index, radiation is the mean of
the hour *ending* at the timestamp. Clear-sky GHI is therefore averaged over
the hour (six 10-minute samples), not taken at the end point, so that the
clear-sky index k = GHI / GHI_clear is not biased near sunrise and sunset.

Clear-sky model: Ineichen and Perez (2002), Solar Energy 73(3), 151-157,
doi:10.1016/S0038-092X(02)00045-2, with the monthly Linke turbidity climatology
shipped with pvlib (Remund et al. 2003). Altitude is set to 0 m (ASSUMPTION).
The exact clear-sky level only sets the normalisation: forecasts are made in k
and converted back with the same GHI_clear, so a bias in GHI_clear cancels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths

ALTITUDE_M = 0.0          # ASSUMPTION, see module docstring
DAYLIGHT_MIN_CLEAR = 50.0  # W/m2: hours used for training and evaluation
K_MAX = 1.3               # physical cap on the clear-sky index (cloud enhancement)
_OFFSETS_MIN = (-55, -45, -35, -25, -15, -5)


def hourly_clearsky(index: pd.DatetimeIndex, lat=paths.LAT, lon=paths.LON) -> pd.DataFrame:
    """Hour-mean clear-sky GHI/DNI/DHI and mid-hour solar geometry for hour-ending stamps."""
    import pvlib

    index = pd.DatetimeIndex(index)
    loc = pvlib.location.Location(lat, lon, tz="UTC", altitude=ALTITUDE_M)
    sub = pd.DatetimeIndex(np.concatenate([index + pd.Timedelta(minutes=m) for m in _OFFSETS_MIN]))
    cs = loc.get_clearsky(sub, model="ineichen")
    n = len(index)
    out = pd.DataFrame(index=index)
    for c, name in (("ghi", "ghi_clear"), ("dni", "dni_clear"), ("dhi", "dhi_clear")):
        out[name] = cs[c].to_numpy().reshape(len(_OFFSETS_MIN), n).mean(axis=0)
    sp = pvlib.solarposition.get_solarposition(index - pd.Timedelta(minutes=30), lat, lon)
    out["zenith"] = sp["apparent_zenith"].to_numpy()
    out["sun_azimuth"] = sp["azimuth"].to_numpy()
    out["cos_zenith"] = np.cos(np.radians(out["zenith"])).clip(lower=0)
    out["daylight"] = out["ghi_clear"] >= DAYLIGHT_MIN_CLEAR
    return out


def clearsky_index(ghi: pd.Series, ghi_clear: pd.Series) -> pd.Series:
    """k = GHI / GHI_clear, NaN where the clear-sky GHI is below the daylight threshold."""
    k = ghi / ghi_clear.where(ghi_clear >= DAYLIGHT_MIN_CLEAR)
    return k.clip(lower=0, upper=K_MAX)


def season(index: pd.DatetimeIndex) -> np.ndarray:
    """Meteorological season of the local date: DJF, MAM, JJA, SON."""
    m = pd.DatetimeIndex(index).tz_convert(paths.LOCAL_TZ).month
    return np.array(["DJF", "DJF", "MAM", "MAM", "MAM", "JJA", "JJA", "JJA",
                     "SON", "SON", "SON", "DJF"])[m - 1]


def ghi_to_pv_per_kwp(ghi: pd.Series, temp_c: pd.Series, wind_ms: pd.Series | None) -> pd.Series:
    """Hour-mean GHI -> AC kW per kWp with the shared array model (aurora/data/pvmodel.py).

    Forecasts give GHI only, so it is split into DNI and DHI with the Erbs model
    (pvlib) at mid-hour sun position before calling pvmodel. The same split is
    applied to forecast quantiles and to the reference series. PV rises
    monotonically with GHI for fixed weather, so converted quantiles remain
    quantiles of PV power to a good approximation.
    """
    import pvlib

    from aurora.data import pvmodel

    idx = ghi.index
    g = ghi.clip(lower=0).fillna(0.0)
    mid = idx - pd.Timedelta(minutes=30)
    zen = pvlib.solarposition.get_solarposition(mid, paths.LAT, paths.LON)["apparent_zenith"].to_numpy()
    dec = pvlib.irradiance.erbs(g.to_numpy(), zen, mid.dayofyear.to_numpy())
    w = pd.DataFrame({"ghi_wm2": g.to_numpy(), "dni_wm2": np.nan_to_num(dec["dni"]),
                      "dhi_wm2": np.nan_to_num(dec["dhi"])}, index=idx)
    t = temp_c.reindex(idx)
    if t.isna().all():
        t = pd.Series(27.0, index=idx)      # only if no temperature at all; cell temperature effect is small
    pv = pvmodel.pv_ac_per_kwp(w, t, wind_ms.reindex(idx) if wind_ms is not None else None)
    return pv.where(g > 0, 0.0)
