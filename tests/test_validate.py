import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.data.validate import hourly_stats, monthly_ghi, pct, verdict


def test_monthly_ghi_constant_series():
    idx = pd.date_range(
        pd.Timestamp("2020-01-01", tz=paths.LOCAL_TZ), pd.Timestamp("2021-12-31 23:00", tz=paths.LOCAL_TZ), freq="h"
    ).tz_convert("UTC")
    ghi = pd.Series(250.0, index=idx)  # 6 kWh/m2/day
    m = monthly_ghi(ghi)
    assert np.allclose(m["mean"], 6.0) and (m["n_years"] == 2).all()


def test_hourly_stats_lag_detection():
    idx = pd.date_range("2020-01-01", periods=24 * 30, freq="h", tz="UTC")
    ref = pd.Series(np.clip(np.sin(2 * np.pi * idx.hour / 24), 0, None) * 800, index=idx)
    s = hourly_stats(ref.shift(1), ref)
    assert s["best_lag_h"] == 1
    assert hourly_stats(ref, ref)["rmse"] == 0


def test_verdict():
    assert verdict(pct(104, 100)) == "agrees"
    assert verdict(-8) == "acceptable"
    assert verdict(20).startswith("large")
    assert verdict(np.nan) == "pending"
