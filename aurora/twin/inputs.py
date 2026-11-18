"""Actual ("truth") hourly inputs for the twin, built only from committed files.

Convention: every row is one hourly step and its timestamp is the START of the
step, in UTC (the team digital-twin schema). Radiation in raw_small/ is the mean
of the hour ending at its label, so PV is shifted back by one hour.

Weather truth is ERA5 by default (brief, Phase 4: "real ERA5 weather"); the
satellite retrieval can be used instead for radiation. Neither is a measurement.
Load is the Phase 1 SYNTHETIC series unless data/itbayat/load_hourly.parquet
(real plant logs) exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import paths, pvmodel, rawio


def load_frame() -> tuple[pd.DataFrame, bool]:
    if paths.LOAD_REAL.exists():
        return pd.read_parquet(paths.LOAD_REAL), False
    return pd.read_parquet(paths.LOAD_SYNTH), True


def crit_variability(index: pd.DatetimeIndex, sigma: float, rho: float, seed: int = 4242) -> np.ndarray:
    """Multiplicative AR(1) factor for critical demand (model v2), stationary SD `sigma`.

    Drawn once over the whole synthetic-load index with a fixed seed and then
    looked up by timestamp, so every job and controller sees the same series."""
    load, _ = load_frame()
    full = load.index
    rng = np.random.default_rng(seed)
    e = rng.normal(0.0, sigma * np.sqrt(1 - rho**2), len(full))
    ar = np.empty(len(full))
    acc = 0.0
    for i, x in enumerate(e):
        acc = rho * acc + x
        ar[i] = acc
    f = pd.Series(np.clip(1.0 + ar, 0.5, 1.6), index=full)
    return f.reindex(index).fillna(1.0).to_numpy()


def build(start=None, end=None, radiation: str = "era5", crit_noise: bool = False) -> pd.DataFrame:
    """Columns: pv_kw_per_kwp, pv_clear_kw_per_kwp, crit_kW, flex_kW, temp_c,
    tc_within_500km. attrs record the sources and the synthetic flag.

    crit_noise (model v2): critical demand varies around its synthetic schedule
    (site.yaml crit_noise_sigma, crit_noise_rho). The total is kept, so the
    flexible load absorbs the change (clipped at zero)."""
    era5 = pd.read_parquet(rawio.ERA5)
    if radiation == "era5":
        rad = era5[["ghi_wm2", "dni_wm2", "dhi_wm2"]]
    elif radiation == "satellite":
        rad = pd.read_parquet(rawio.SATELLITE)[["ghi_wm2", "dni_wm2", "dhi_wm2"]]
    else:
        raise ValueError(radiation)
    if start is not None:
        lo = pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tzinfo is None else pd.Timestamp(start)
        rad = rad[rad.index > lo - pd.Timedelta(hours=1)]
    if end is not None:
        hi = pd.Timestamp(end, tz="UTC") if pd.Timestamp(end).tzinfo is None else pd.Timestamp(end)
        rad = rad[rad.index <= hi + pd.Timedelta(hours=1)]
    rad = rad.dropna()
    pv = pvmodel.pv_ac_per_kwp(rad, era5["temp_c"], era5["wind_ms"])
    cs = pvmodel.clearsky(rad.index)
    pvc = pvmodel.pv_ac_per_kwp(cs, era5["temp_c"], None)
    shift = pd.Timedelta(hours=1)  # hour-ending -> step start
    df = pd.DataFrame({"pv_kw_per_kwp": pv.values, "pv_clear_kw_per_kwp": pvc.values}, index=rad.index - shift)
    load, synthetic = load_frame()
    df = df.join(load[["critical_kW", "flex_kW"]].rename(columns={"critical_kW": "crit_kW"}), how="inner")
    df["temp_c"] = era5["temp_c"].reindex(df.index).interpolate().to_numpy()
    if paths.TYPHOON_HOURLY.exists():
        tf = pd.read_parquet(paths.TYPHOON_HOURLY)
        df["tc_within_500km"] = tf["tc_within_500km"].reindex(df.index).fillna(False).astype(bool).to_numpy()
    if crit_noise:
        from ..data.site import load_site, value

        s = load_site()
        f = crit_variability(df.index, float(value(s, "crit_noise_sigma")), float(value(s, "crit_noise_rho")))
        total = df["crit_kW"] + df["flex_kW"]
        df["crit_kW"] = df["crit_kW"] * f
        df["flex_kW"] = (total - df["crit_kW"]).clip(lower=0.0)
    if start is not None:
        df = df[df.index >= lo]
    if end is not None:
        df = df[df.index < hi]
    df.index.name = "timestamp"
    df.attrs.update(
        radiation=radiation,
        load_synthetic=str(synthetic),
        crit_noise=str(crit_noise),
        note="Truth = reanalysis/retrieval PV and %s load; not measured." % ("SYNTHETIC" if synthetic else "logged"),
    )
    return df
