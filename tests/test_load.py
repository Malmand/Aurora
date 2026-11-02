"""Tests use an artificial temperature series (test fixture, not site data)."""
import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.data.load import read_real_load, synthetic_load
from aurora.data.site import load_site, value


def _index():
    return pd.date_range(pd.Timestamp("2021-01-01", tz=paths.LOCAL_TZ).tz_convert("UTC"),
                         pd.Timestamp("2025-12-31 23:00", tz=paths.LOCAL_TZ).tz_convert("UTC"), freq="h")


def _temp(idx):
    doy = idx.tz_convert(paths.LOCAL_TZ).dayofyear
    return pd.Series(27 + 3 * np.sin(2 * np.pi * (doy - 100) / 365), index=idx)


def test_peak_scaled_and_balance():
    site = load_site()
    idx = _index()
    df = synthetic_load(idx, _temp(idx), site)
    loc = df.index.tz_convert(paths.LOCAL_TZ)
    ref = site["load_model"]["reference_year"]
    assert np.isclose(df.loc[loc.year == ref, "total_kW"].max(), value(site, "peak_demand_kw"))
    assert (df["flex_kW"] >= 0).all()
    assert np.allclose(df["critical_kW"] + df["flex_kW"], df["total_kW"])
    crit_cols = [c for c in df if c.startswith("crit_")]
    assert np.allclose(df[crit_cols].sum(axis=1), df["critical_kW"])
    assert df.attrs["synthetic"] == "True"


def test_shape_season_and_evening_peak():
    idx = _index()
    df = synthetic_load(idx, _temp(idx))
    loc = df.index.tz_convert(paths.LOCAL_TZ)
    by_month = df["total_kW"].groupby(loc.month).mean()
    assert by_month.idxmax() in (5, 6, 7)
    by_hour = df["total_kW"].groupby(loc.hour).mean()
    assert by_hour.idxmax() in (18, 19, 20)
    # growth since 2021 matches the INL figure (+12 %) within noise
    peaks = df["total_kW"].groupby(loc.year).max()
    assert 0.07 < peaks[2024] / peaks[2021] - 1 < 0.17


def test_real_load_path(tmp_path):
    t = pd.date_range("2024-01-01", periods=48, freq="h")
    p = tmp_path / "plant.csv"
    pd.DataFrame({"timestamp": t, "total_kW": 150.0}).to_csv(p, index=False)
    df = read_real_load(p)
    assert df.attrs["synthetic"] == "False"
    assert df.index.tz is not None and len(df) == 48
    assert (df["critical_kW"] > 0).all() and np.allclose(df["flex_kW"], 150 - df["critical_kW"])
