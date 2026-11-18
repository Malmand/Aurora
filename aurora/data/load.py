"""Hourly load for Itbayat: SYNTHETIC model, or real plant logs via --load.

No hourly measured load for Itbayat is public. The synthetic series combines:
  * a relative hourly shape (local time) with an evening peak,
  * a seasonal term peaking in May-July,
  * temperature sensitivity on the daily-mean temperature anomaly
    (anomaly from its own monthly climatology, so it does not double-count season),
  * a Sunday factor and AR(1) multiplicative noise,
  * calibration to NPC's annual figures for Itbayat DPP (site.yaml npc_itbayat_dpp,
    MEP 2025-2029 Annex R): for each year, total = k * rel**gamma with gamma set
    so the year's load factor and k so its gross generation match NPC. k and gamma
    are interpolated between mid-year points (no step on 1 January); years outside
    the table take the nearest year's values.
  * (legacy, if npc_itbayat_dpp is absent) INL peak growth and peak_demand_kw scaling.
Critical load = sum of fixed-rating components with day/night factors.
Flexible = total - critical.
All shape parameters are ASSUMPTIONs (site.yaml: load_model).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import paths
from .site import load_site, value

COMPONENTS = ["clinic", "water", "telecom", "municipal", "cold_storage"]


def _critical(local: pd.DatetimeIndex, site: dict) -> pd.DataFrame:
    prof = site["load_model"]["critical_profiles"]
    h = local.hour
    out = {}
    for name in COMPONENTS:
        p = prof[name]
        kw = value(site, p["kw"])
        a, b = p["day_hours"]
        day = (h >= a) & (h < b)
        out[f"crit_{name}_kW"] = np.where(day, p["day"], p["night"]) * kw
    return pd.DataFrame(out, index=local.tz_convert("UTC"))


def _gamma_for_lf(r: np.ndarray, lf: float) -> float:
    """gamma such that mean(r**g) / max(r**g) = lf (bisection; LF falls as gamma rises)."""
    r = r / r.max()
    lo, hi = 0.05, 8.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if np.mean(r**mid) > lf:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _calibrate_npc(rel: np.ndarray, local: pd.DatetimeIndex, npc: dict):
    """Map rel to k*rel**gamma per year so NPC's annual peak and gross generation match."""
    yrs = np.asarray(npc["years"], int)
    peak = np.asarray(npc["peak_kw"], float)
    gen = np.asarray(npc["gross_gen_mwh"], float) * 1000.0
    rel = np.asarray(rel, float)
    year = local.year.to_numpy()
    k_y, g_y, mid, e_fit = [], [], [], []
    partial = []
    for y, pk, e in zip(yrs, peak, gen):
        sel = year == y
        if sel.sum() < 24 * 360:  # partial year: scale the nearest full year by energy below
            if sel.any():
                partial.append((y, e))
            continue
        hours = 8784 if pd.Timestamp(year=int(y), month=12, day=31).dayofyear == 366 else 8760
        lf = e / (pk * hours)
        r = rel[sel]
        g = _gamma_for_lf(r, lf)
        k_y.append(pk / r.max() ** g)
        g_y.append(g)
        mid.append(y + 0.5)
        e_fit.append(e)
    if not mid:
        raise ValueError("no NPC calibration year covered by the index")
    for y, e in partial:  # same gamma, k scaled by NPC's energy ratio
        j = int(np.argmin(np.abs(np.asarray(mid) - (y + 0.5))))
        k_y.append(k_y[j] * e / e_fit[j])
        g_y.append(g_y[j])
        mid.append(y + 0.5)
        e_fit.append(e)
    o = np.argsort(mid)
    mid, k_y, g_y = (list(np.asarray(v)[o]) for v in (mid, k_y, g_y))
    t = local.year + (local.dayofyear.to_numpy() - 0.5) / 365.25
    gam = np.interp(t, mid, g_y)
    logk = np.interp(t, mid, np.log(k_y))
    total = np.exp(logk) * rel**gam
    info = {f"gamma_{int(m - 0.5)}": f"{g:.3f}" for m, g in zip(mid, g_y)}
    return total, info


def synthetic_load(index_utc: pd.DatetimeIndex, temp_c: pd.Series | None, site: dict | None = None) -> pd.DataFrame:
    """SYNTHETIC hourly load (total, critical, flexible kW) from the site load model.

    Hourly shape x season x temperature x Sunday factor x noise, then mapped to NPC's yearly peak and
    energy (calibration in site.yaml). Critical loads follow their own schedules. Every factor is an ASSUMPTION.
    """
    site = site or load_site()
    m = site["load_model"]
    local = index_utc.tz_convert(paths.LOCAL_TZ)
    shape = np.asarray(m["hourly_shape"], float)[local.hour]
    doy = local.dayofyear.to_numpy()
    seasonal = 1 + m["seasonal_amplitude"] * np.cos(2 * np.pi * (doy - m["seasonal_peak_doy"]) / 365.25)
    sunday = np.where(local.dayofweek == 6, m["sunday_factor"], 1.0)

    if temp_c is not None:
        t = temp_c.reindex(index_utc)
        t.index = local
        daily = t.resample("D").mean()
        clim = daily.groupby(daily.index.month).transform("mean")
        anom = (daily - clim).reindex(local.floor("D")).to_numpy()
        tempf = 1 + m["temp_coeff_per_c"] * np.nan_to_num(anom)
    else:
        tempf = np.ones(len(index_utc))

    rng = np.random.default_rng(m["seed"])
    eps = rng.normal(0, m["noise_sigma"] * np.sqrt(1 - m["noise_rho"] ** 2), len(index_utc))
    ar = np.empty_like(eps)
    acc = 0.0
    for i, e in enumerate(eps):
        acc = m["noise_rho"] * acc + e
        ar[i] = acc
    noise = 1 + ar

    rel = shape * seasonal * sunday * tempf * noise
    npc = site.get("npc_itbayat_dpp")
    if npc is not None:
        total, info = _calibrate_npc(rel, local, npc)
        meta = dict(calibration="NPC MEP 2025-2029 Annex R annual peak and gross generation", **info)
    else:
        g_total = value(site, "peak_growth_since_2021")
        ref = m["reference_year"]
        g = (1 + g_total) ** (1 / (ref - 2021)) - 1
        years = local.year + (doy - 1) / 365.25
        growth = (1 + g) ** (np.minimum(years, ref + 1) - (ref + 1))
        rel = rel * growth
        in_ref = local.year == ref
        if not in_ref.any():
            raise ValueError(f"reference year {ref} not in the index")
        total = rel * (value(site, "peak_demand_kw") / rel[in_ref].max())
        meta = dict(peak_kw=str(value(site, "peak_demand_kw")), reference_year=str(ref), annual_growth=f"{g:.4f}")

    crit = _critical(local, site)
    # a few night hours of the earliest years fall below the assumed critical ratings:
    # hold the total at the critical load there (flexible load 0)
    total = np.maximum(total, crit.sum(axis=1).to_numpy())
    df = crit.copy()
    df.insert(0, "total_kW", total)
    df.insert(1, "critical_kW", crit.sum(axis=1).to_numpy())
    df.insert(2, "flex_kW", df["total_kW"] - df["critical_kW"])
    if (df["flex_kW"] < 0).any():
        raise ValueError("critical load exceeds total in some hours; check ratings")
    df.index.name = "time"
    df.attrs.update(
        synthetic="True",
        description="SYNTHETIC hourly load for Itbayat. Not measured.",
        **meta,
        temperature_input="ERA5 temp_c" if temp_c is not None else "none",
    )
    return df


def read_real_load(path: Path, site: dict | None = None) -> pd.DataFrame:
    """Read plant logs: CSV or parquet with a timestamp column and total_kW.

    Timestamps without a zone are taken as local time (PHT). If critical_kW is
    absent, the critical component model is applied.
    """
    site = site or load_site()
    path = Path(path)
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    tcol = next(c for c in df.columns if c.lower() in ("timestamp", "time", "datetime"))
    t = pd.to_datetime(df[tcol])
    t = t.dt.tz_localize(paths.LOCAL_TZ) if t.dt.tz is None else t
    df.index = pd.DatetimeIndex(t).tz_convert("UTC")
    df.index.name = "time"
    df = df.drop(columns=[tcol]).resample("h").mean()
    if "critical_kW" not in df:
        crit = _critical(df.index.tz_convert(paths.LOCAL_TZ), site)
        df = df.join(crit)
        df["critical_kW"] = crit.sum(axis=1)
    df["flex_kW"] = (df["total_kW"] - df["critical_kW"]).clip(lower=0)
    df.attrs.update(synthetic="False", description=f"Measured load from {path.name}")
    return df
