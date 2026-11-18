"""Inputs, truth and feature tables for the solar forecast.

Lead-time convention (causal by construction). A forecast is issued once a day
at ``ISSUE_HOUR_UTC`` (16 UTC = 00:00 PHT, local midnight) for the next 48 hours,
so lead day 1 is the next local day and lead day 2 the day after:

* lead day 1: target hours issue+1 h .. issue+24 h, NWP columns ``*_d1``;
* lead day 2: target hours issue+25 h .. issue+48 h, NWP columns ``*_d2``.

``_dN`` holds the value from the run issued N days before the target hour
(lead about 24N to 24N+23 h, see aurora/data/rawio.py), so every NWP value used
was available at the issue time. Context features (neighbouring hours, day
means) are taken inside one issue window only. This is conservative: an operator would have
a run up to one day newer. Only variables archived at d1 and d2 are used; the
low/mid/high cloud split exists only at d0 and is therefore not usable.

Observations used as features (persistence) come from the reference product
at t - 24 h (lead day 1) or t - 48 h (lead day 2), i.e. the same hour on the
local day that ends at the issue time, plus that day's mean clear-sky index. Data latency of the satellite product
is ignored.

Reference truth: Open-Meteo satellite radiation (a satellite retrieval). ERA5
is used as a cross-check. Neither is a measurement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths, rawio

from .geometry import K_MAX, clearsky_index, hourly_clearsky, season

ISSUE_HOUR_UTC = 16  # 00:00 PHT
LEAD_DAYS = (1, 2)
GHI_MODELS = ("ecmwf", "gfs", "icon")  # JMA is not served with radiation
ALL_MODELS = ("ecmwf", "gfs", "icon", "jma")
NWP_VARS = ("ghi_wm2", "cloud_pct", "temp_c", "rh_pct", "precip_mm", "mslp_hpa", "wind_ms", "gust_ms")
QUANTILES = tuple(np.round(np.arange(0.05, 0.951, 0.05), 2))  # 19 levels, used for CRPS
BAND = (0.1, 0.9)  # the 80 % band reported as P10/P90


def lead_day_of(lead_h):
    return np.where(np.asarray(lead_h) <= 24, 1, 2)


def load_nwp(models=ALL_MODELS) -> dict[str, pd.DataFrame]:
    out = {}
    for m in models:
        df = rawio.read(rawio.previous_runs_path(m))
        if df is not None:
            out[m] = df
    return out


def load_truth() -> pd.DataFrame:
    """Hourly reference (satellite) and cross-check (ERA5) GHI with clear-sky terms."""
    sat = rawio.read(rawio.SATELLITE)
    era = rawio.read(rawio.ERA5)
    if sat is None:
        raise FileNotFoundError(f"{rawio.SATELLITE} missing; run scripts/download_itbayat.py")
    idx = pd.date_range(sat.index.min(), sat.index.max(), freq="h")
    base = hourly_clearsky(idx)
    base["ghi_sat"] = sat["ghi_wm2"].reindex(idx)
    if era is not None:
        base["ghi_era5"] = era["ghi_wm2"].reindex(idx)
        base["temp_era5"] = era["temp_c"].reindex(idx)
        base["wind_era5"] = era["wind_ms"].reindex(idx)
        base["mslp_era5"] = era["mslp_hpa"].reindex(idx)
    base["k_sat"] = clearsky_index(base["ghi_sat"], base["ghi_clear"])
    base["season"] = season(idx)
    return base


def mslp_climatology(base: pd.DataFrame, end="2022-01-01") -> pd.Series:
    """ERA5 mean sea-level pressure by month and UTC hour, 2015-2021 (before any test data)."""
    s = base.loc[: pd.Timestamp(end, tz="UTC") - pd.Timedelta(hours=1), "mslp_era5"].dropna()
    return s.groupby([s.index.month, s.index.hour]).mean()


def lead_features(
    base: pd.DataFrame, nwp: dict[str, pd.DataFrame], ld: int, mslp_clim: pd.Series | None = None
) -> pd.DataFrame:
    """Feature table for lead day ``ld``, one row per target hour (UTC, hour-ending)."""
    idx = base.index
    X = pd.DataFrame(index=idx)
    local = idx.tz_convert(paths.LOCAL_TZ)
    X["hour_local"] = local.hour
    doy = local.dayofyear.to_numpy()
    X["doy_sin"], X["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    X["cos_zenith"] = base["cos_zenith"]
    X["ghi_clear"] = base["ghi_clear"]
    gc = base["ghi_clear"].where(base["ghi_clear"] > 1.0)
    iss = issue_times(idx, ld)

    ks, clouds, mslps, gusts = [], [], [], []
    for m in ALL_MODELS:
        df = nwp.get(m)
        if df is None:
            continue
        df = df.reindex(idx)
        for v in NWP_VARS:
            c = f"{v}_d{ld}"
            if c not in df:
                continue
            if v == "ghi_wm2":
                k = (df[c] / gc).clip(0, K_MAX)
                X[f"k_{m}"] = k
                ks.append(k)
            else:
                X[f"{v}_{m}"] = df[c]
                if v == "cloud_pct":
                    clouds.append(df[c])
                elif v == "mslp_hpa":
                    mslps.append(df[c])
                elif v == "gust_ms":
                    gusts.append(df[c])
    if ks:
        K = pd.concat(ks, axis=1)
        X["k_nwp_mean"] = K.mean(axis=1)
        X["k_nwp_std"] = K.std(axis=1, ddof=0).where(K.notna().sum(axis=1) >= 2)
        X["k_nwp_min"], X["k_nwp_max"] = K.min(axis=1), K.max(axis=1)
        X["n_ghi_models"] = K.notna().sum(axis=1)
        # temporal context inside the same forecast (the whole run is known at issue time)
        km = X["k_nwp_mean"]
        for sh in (-2, -1, 1, 2):
            X[f"k_nwp_mean_s{sh:+d}"] = km.shift(sh, freq="h").reindex(idx)
        X["k_nwp_mean_3h"] = km.rolling(3, center=True, min_periods=1).mean()
        X["k_nwp_daymean"] = km.groupby(iss).transform("mean")
        for m in GHI_MODELS:
            if f"k_{m}" in X:
                X[f"k_{m}_daymean"] = X[f"k_{m}"].groupby(iss).transform("mean")
    if clouds:
        C = pd.concat(clouds, axis=1)
        X["cloud_mean"], X["cloud_std"] = C.mean(axis=1), C.std(axis=1, ddof=0)
        X["cloud_mean_3h"] = X["cloud_mean"].rolling(3, center=True, min_periods=1).mean()
        X["cloud_daymean"] = X["cloud_mean"].groupby(iss).transform("mean")
    if mslps:
        P = pd.concat(mslps, axis=1)
        pmin = P.min(axis=1)
        X["mslp_min"] = pmin
        # 24 h pressure tendency in the same lead-day field (the earlier value was issued earlier still)
        X["mslp_tend24"] = pmin - pmin.shift(24, freq="h").reindex(idx)
        if mslp_clim is not None:
            clim = mslp_clim.reindex(pd.MultiIndex.from_arrays([idx.month, idx.hour])).to_numpy()
            X["mslp_anom"] = pmin.to_numpy() - clim
    if gusts:
        X["gust_max"] = pd.concat(gusts, axis=1).max(axis=1)

    # persistence from the reference product: same hour on the last day observed before issue
    lag = 24 * ld
    X["k_persist"] = base["k_sat"].shift(lag, freq="h").reindex(idx)
    # mean k of the whole local day before the issue date (complete before the issue time)
    daymean = base["k_sat"].groupby(local.date).mean()
    prev = (iss.tz_convert(paths.LOCAL_TZ).normalize() - pd.Timedelta(days=1)).date
    X["k_prevday_mean"] = daymean.reindex(prev).to_numpy()
    return X


def issue_times(idx: pd.DatetimeIndex, ld: int) -> pd.DatetimeIndex:
    """Issue time of the lead-day ``ld`` forecast that covers each target hour."""
    h = pd.Timedelta(hours=ISSUE_HOUR_UTC)
    issue = (idx - pd.Timedelta(hours=1) - h).floor("D") + h
    return issue - pd.Timedelta(days=ld - 1)


def target_frame(base: pd.DataFrame, X: pd.DataFrame, ld: int) -> pd.DataFrame:
    """Rows with their issue time, lead hour, truth, and flags used in the backtest."""
    idx = X.index
    issue = issue_times(idx, ld)
    lead_h = ((idx - issue) / pd.Timedelta(hours=1)).astype(int)
    T = pd.DataFrame(
        {
            "issue_time": issue,
            "lead_h": lead_h,
            "lead_day": ld,
            "k_true": base["k_sat"],
            "ghi_true": base["ghi_sat"],
            "ghi_clear": base["ghi_clear"],
            "daylight": base["daylight"],
            "season": base["season"],
        },
        index=idx,
    )
    if "ghi_era5" in base:
        T["ghi_era5"] = base["ghi_era5"]
    # raw NWP GHI (each model and the mean) for the baselines
    cols = [c for c in X.columns if c.startswith("k_") and c.split("_", 1)[1] in GHI_MODELS]
    for c in cols:
        T[f"ghi_nwp_{c[2:]}"] = X[c] * base["ghi_clear"]
    if cols:
        T["ghi_nwp_mean"] = X[cols].mean(axis=1) * base["ghi_clear"]
    T["has_ghi_nwp"] = X[cols].notna().any(axis=1) if cols else False
    # forecast air temperature and wind (model mean) for the PV cell temperature
    for v, name in (("temp_c", "temp_fc"), ("wind_ms", "wind_fc")):
        vc = [c for c in X.columns if c.startswith(f"{v}_")]
        T[name] = X[vc].mean(axis=1) if vc else np.nan
    for c in ("temp_era5", "wind_era5"):
        if c in base:
            T[c] = base[c]
    return T
