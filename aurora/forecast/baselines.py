"""Reference forecasts: raw NWP, smart persistence, climatology, and the comms-loss fallback.

* Raw NWP: each model's GHI at the lead day, and their mean (features.target_frame).
* Smart persistence: k at the same hour on the last observed day times today's
  clear-sky GHI (Yang et al. 2020, Solar Energy 210, 20-37,
  doi:10.1016/j.solener.2020.04.019, for the definition and skill scores).
* Climatology: k by calendar month and local hour from the reference product
  before the test period; mean for point scores, 19 empirical quantiles for
  probabilistic scores.
* Fallback (used when no NWP arrives, e.g. communications down in a typhoon):
  climatology-conditioned persistence k = w k_persist + (1 - w) k_clim with w
  fitted per lead day on past data; bands from the past residual quantiles of
  that forecast by lead day and season, widened by ``WIDEN`` about the median.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths

from .features import QUANTILES
from .geometry import K_MAX

WIDEN = 1.25  # ASSUMPTION: extra width on fallback bands


def _keys(index: pd.DatetimeIndex):
    local = pd.DatetimeIndex(index).tz_convert(paths.LOCAL_TZ)
    return local.month.to_numpy(), local.hour.to_numpy()


def climatology_table(k_hist: pd.Series) -> pd.DataFrame:
    """Mean and 19 quantiles of k by (month, local hour)."""
    k = k_hist.dropna()
    m, h = _keys(k.index)
    g = k.groupby([m, h])
    tab = g.quantile(list(QUANTILES)).unstack()
    tab.columns = [f"q{round(100 * t):02d}" for t in QUANTILES]
    tab["mean"] = g.mean()
    tab.index.names = ["month", "hour"]
    return tab


def climatology(tab: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    m, h = _keys(index)
    out = tab.reindex(pd.MultiIndex.from_arrays([m, h])).set_axis(index)
    return out


def fit_fallback(
    k_persist: pd.Series, k_clim: pd.Series, k_true: pd.Series, lead_day: pd.Series, season: pd.Series
) -> dict:
    """Least-squares weight per lead day and residual quantiles per (lead day, season)."""
    df = pd.DataFrame({"p": k_persist, "c": k_clim, "y": k_true, "ld": lead_day, "s": season}).dropna()
    par = {"w": {}, "res": {}}
    for ld, d in df.groupby("ld"):
        x, r = (d["p"] - d["c"]).to_numpy(), (d["y"] - d["c"]).to_numpy()
        w = float(np.clip((x @ r) / max(x @ x, 1e-9), 0, 1))
        par["w"][int(ld)] = w
        res = d["y"] - (d["c"] + w * (d["p"] - d["c"]))
        par["res"][(int(ld), "all")] = np.quantile(res, QUANTILES)
        for s, rs in res.groupby(d["s"]):
            if len(rs) >= 150:
                par["res"][(int(ld), s)] = np.quantile(rs, QUANTILES)
    return par


def predict_fallback(par: dict, k_persist, k_clim, lead_day, season, widen=WIDEN) -> np.ndarray:
    """19 quantiles of k (n x 19). Missing persistence falls back to climatology."""
    kp, kc = np.asarray(k_persist, float), np.asarray(k_clim, float)
    kp = np.where(np.isnan(kp), kc, kp)
    ld, s = np.asarray(lead_day), np.asarray(season)
    Q = np.full((len(kp), len(QUANTILES)), np.nan)
    j50 = QUANTILES.index(0.5)
    for i in range(len(kp)):
        w = par["w"].get(int(ld[i]), 0.0)
        r = par["res"].get((int(ld[i]), s[i]), par["res"].get((int(ld[i]), "all")))
        if r is None:
            continue
        mu = kc[i] + w * (kp[i] - kc[i])
        Q[i] = mu + r[j50] + widen * (r - r[j50])
    return np.sort(np.clip(Q, 0, K_MAX), axis=1)
