"""GHI forecast -> PV AC power for the Itbayat array (pvlib).

Array (ASSUMPTION, same as the Phase 1 yield check in aurora/data/validate.py):
fixed tilt 20 deg facing south, Hay-Davies transposition, SAPM open-rack cell
temperature, PVWatts DC with gamma = -0.0037 /degC, 14 % DC losses, inverter
efficiency 0.96, AC limit = DC rating (DC/AC ratio 1.0, ASSUMPTION; the INL
report gives 300 kW PV without saying DC or AC).

GHI is split into DNI and DHI with the Erbs model (pvlib); this applies the same
way to forecast quantiles and to the reference series. Each GHI quantile is
converted separately. PV power rises monotonically with GHI for fixed weather,
so the converted values remain quantiles of PV power to a good approximation.
Cell temperature uses the forecast air temperature and wind speed.
pvlib: Anderson et al. (2023), J. Open Source Softw. 8(92), 5994,
doi:10.21105/joss.05994.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data.validate import PV

DC_AC_RATIO = 1.0
PV_KWP_INL = 300.0
PV_KWP_CASE = 500.0


def pv_ac_per_kwp(ghi: pd.Series, temp_c: pd.Series, wind_ms: pd.Series, geom: pd.DataFrame) -> pd.Series:
    """AC power (kW per kWp DC) for hour-mean GHI. ``geom`` from geometry.hourly_clearsky."""
    import pvlib

    idx = ghi.index
    zen = geom["zenith"].reindex(idx)
    az = geom["sun_azimuth"].reindex(idx)
    g = ghi.clip(lower=0).fillna(0.0)
    mid = idx - pd.Timedelta(minutes=30)
    dni_extra = pd.Series(pvlib.irradiance.get_extra_radiation(mid).to_numpy(), index=idx)
    dec = pvlib.irradiance.erbs(g.to_numpy(), zen.to_numpy(), mid.dayofyear.to_numpy())
    dni = pd.Series(np.nan_to_num(dec["dni"]), index=idx)
    dhi = pd.Series(np.nan_to_num(dec["dhi"]), index=idx)
    poa = pvlib.irradiance.get_total_irradiance(PV["tilt"], PV["azimuth"], zen, az, dni, g, dhi,
                                                dni_extra=dni_extra, model="haydavies")["poa_global"]
    poa = poa.fillna(0).clip(lower=0)
    t = temp_c.reindex(idx).interpolate(limit_direction="both").fillna(27.0)
    ws = wind_ms.reindex(idx).interpolate(limit_direction="both").fillna(3.0)
    tc = pvlib.temperature.sapm_cell(poa, t, ws, **pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][
        "open_rack_glass_polymer"])
    pdc = pvlib.pvsystem.pvwatts_dc(poa, tc, 1.0, PV["gamma_pdc"])  # kW per kWp DC
    pac = (pdc * (1 - PV["losses_frac"]) * PV["inv_eff"]).clip(lower=0, upper=1.0 / DC_AC_RATIO)
    return pac.where(geom["ghi_clear"].reindex(idx) > 0, 0.0)

