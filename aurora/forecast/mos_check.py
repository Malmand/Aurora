"""Fairer baseline for the solar forecast: raw NWP after a simple bias correction (MOS).

    python -m aurora.forecast.mos_check

A plain linear correction (model output statistics, MOS) is fitted month by month on earlier data only,
the same way the AURORA forecast is backtested: the training truth ends 3 days before each test month.
Four variants are scored (ECMWF or the 3-model NWP mean, corrected in GHI or in clear-sky index) on the
same sample as docs/validation_forecast.md: daylight, full regime, Nov 2024 to Oct 2026, lead days 1 and 2.
A daily block bootstrap gives the 5 to 95 % range of AURORA's RMSE skill over the best variant.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora.data import paths

from .backtest import EVAL_START

BACKTEST = paths.SITE_DIR / "forecast" / "backtest_solar.parquet"
ECMWF = paths.SITE_DIR / "raw_small" / "previous_runs_ecmwf.parquet"
MIN_CLEAR_SKY_WM2 = 50  # daylight threshold used throughout the forecast evaluation
GAP = pd.Timedelta(days=3)  # training truth stops this long before the test month
K_MAX = 1.5  # clip of the clear-sky index, as in the forecast features
N_BOOT = 500


def rmse(pred: pd.Series, truth: pd.Series) -> float:
    return float(np.sqrt(np.mean((pred - truth) ** 2)))


def load_sample(lead_day: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(all daylight rows with a raw ECMWF value, evaluation rows) for one lead day."""
    b = pd.read_parquet(BACKTEST)
    b = b[b["calibrated"] & (b["lead_day"] == lead_day)].copy()
    b["ecmwf"] = pd.read_parquet(ECMWF)[f"ghi_wm2_d{lead_day}"].reindex(b.index).to_numpy()
    rows = b[(b["ghi_clear"] >= MIN_CLEAR_SKY_WM2) & b["ghi_ref"].notna() & b["ecmwf"].notna()]
    ev = rows[
        (rows.index >= EVAL_START)
        & (rows["regime"] == "full")
        & rows["ghi_nwp_mean"].notna()
        & rows["ghi_persist"].notna()
    ]
    return rows, ev


def mos_forecast(rows: pd.DataFrame, ev: pd.DataFrame, source: str, in_clear_sky_index: bool) -> pd.Series:
    """Bias-corrected forecast for the rows of ev, refitted each month on earlier data only."""
    pred = pd.Series(np.nan, index=ev.index)
    for _, month in ev.groupby(ev.index.tz_convert(None).to_period("M")):
        train = rows[(rows.index < month.index.min() - GAP) & rows[source].notna()]
        if in_clear_sky_index:
            x = (train[source] / train["ghi_clear"]).clip(0, K_MAX)
            y = (train["ghi_ref"] / train["ghi_clear"]).clip(0, K_MAX)
        else:
            x, y = train[source], train["ghi_ref"]
        intercept, slope = np.linalg.lstsq(np.c_[np.ones(len(x)), x], y, rcond=None)[0]
        if in_clear_sky_index:
            k = (month[source] / month["ghi_clear"]).clip(0, K_MAX)
            p = (intercept + slope * k) * month["ghi_clear"]
        else:
            p = intercept + slope * month[source]
        pred.loc[month.index] = p.clip(lower=0).to_numpy()
    return pred


def bootstrap_skill(ev: pd.DataFrame, pred: pd.Series, seed: int = 2026) -> tuple[float, float, float]:
    """RMSE skill (%) of AURORA P50 over pred, with a 5-95 % daily block bootstrap range."""
    sq = pd.DataFrame(
        {"a": (ev["ghi_p50"] - ev["ghi_ref"]) ** 2, "m": (pred - ev["ghi_ref"]) ** 2, "day": ev.index.floor("D")}
    )
    per_day = sq.groupby("day").agg(a=("a", "sum"), m=("m", "sum"), n=("a", "size"))

    def skill(d):
        return 100 * (1 - np.sqrt(d["a"].sum() / d["n"].sum()) / np.sqrt(d["m"].sum() / d["n"].sum()))

    rng = np.random.default_rng(seed)
    draws = [skill(per_day.iloc[rng.integers(0, len(per_day), len(per_day))]) for _ in range(N_BOOT)]
    lo, hi = np.percentile(draws, [5, 95])
    return skill(per_day), lo, hi


def main() -> None:
    """Print the RMSE of every baseline and AURORA's skill over the best bias-corrected one."""
    for lead_day in (1, 2):
        rows, ev = load_sample(lead_day)
        scores = {"AURORA P50": rmse(ev["ghi_p50"], ev["ghi_ref"]), "ECMWF raw": rmse(ev["ecmwf"], ev["ghi_ref"])}
        best = None
        for source, name in (("ecmwf", "ECMWF"), ("ghi_nwp_mean", "NWP mean")):
            for csi in (False, True):
                pred = mos_forecast(rows, ev, source, csi)
                label = f"{name} corrected ({'clear-sky index' if csi else 'GHI'})"
                scores[label] = rmse(pred, ev["ghi_ref"])
                if best is None or scores[label] < scores[best[0]]:
                    best = (label, pred)
        print(f"Lead day {lead_day} (n = {len(ev)}), RMSE W/m2:")
        for k, v in scores.items():
            print(f"  {k:40s} {v:6.1f}")
        s, lo, hi = bootstrap_skill(ev, best[1])
        print(f"  AURORA skill vs best ({best[0]}): {s:.1f} % (5-95 %: {lo:.1f} to {hi:.1f})")


if __name__ == "__main__":
    main()
