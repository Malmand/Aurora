"""Fixed-tilt PV array model (pvlib, PVWatts), shared by the validation and the twin.

Radiation inputs follow the raw_small convention: the value at timestamp T is
the mean of the hour ending at T. Sun position is taken at mid-interval.
The array is an ASSUMPTION until the design is fixed (tilt about latitude,
south facing, 14 % system losses, 96 % inverter efficiency).
"""

from __future__ import annotations

import pandas as pd

from . import paths

PV = dict(tilt=20.0, azimuth=180.0, gamma_pdc=-0.0037, losses_frac=0.14, inv_eff=0.96)


def _solpos(index: pd.DatetimeIndex) -> pd.DataFrame:
    import pvlib

    mid = index - pd.Timedelta(minutes=30)
    sp = pvlib.solarposition.get_solarposition(mid, paths.LAT, paths.LON)
    sp.index = index
    return sp


def pv_ac_per_kwp(w: pd.DataFrame, temp: pd.Series, wind: pd.Series | None = None, pv: dict = PV) -> pd.Series:
    """Hourly AC output in kW per kWp from columns ghi_wm2, dni_wm2, dhi_wm2 (hour ending)."""
    import pvlib

    sp = _solpos(w.index)
    dni_extra = pvlib.irradiance.get_extra_radiation(w.index)
    poa = pvlib.irradiance.get_total_irradiance(
        pv["tilt"],
        pv["azimuth"],
        sp["apparent_zenith"],
        sp["azimuth"],
        w["dni_wm2"].clip(lower=0),
        w["ghi_wm2"].clip(lower=0),
        w["dhi_wm2"].clip(lower=0),
        dni_extra=dni_extra,
        model="haydavies",
    )["poa_global"].fillna(0)
    ws = wind.reindex(w.index).fillna(1.0) if wind is not None else pd.Series(1.0, index=w.index)
    tc = pvlib.temperature.sapm_cell(
        poa,
        temp.reindex(w.index).interpolate().bfill().ffill(),
        ws,
        **pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_polymer"],
    )
    pdc = pvlib.pvsystem.pvwatts_dc(poa, tc, 1.0, pv["gamma_pdc"])
    return (pdc * (1 - pv["losses_frac"]) * pv["inv_eff"]).clip(lower=0).rename("pv_kw_per_kwp")


def clearsky(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Ineichen clear sky (pvlib Linke turbidity climatology), hour-ending labels."""
    import pvlib

    loc = pvlib.location.Location(paths.LAT, paths.LON)
    mid = index - pd.Timedelta(minutes=30)
    cs = loc.get_clearsky(mid, model="ineichen")
    cs.index = index
    return cs.rename(columns={"ghi": "ghi_wm2", "dni": "dni_wm2", "dhi": "dhi_wm2"})
