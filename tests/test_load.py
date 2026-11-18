"""Tests use an artificial temperature series (test fixture, not site data)."""

import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.data.load import read_real_load, synthetic_load
from aurora.data.site import load_site


def _index():
    return pd.date_range(
        pd.Timestamp("2021-01-01", tz=paths.LOCAL_TZ).tz_convert("UTC"),
        pd.Timestamp("2025-12-31 23:00", tz=paths.LOCAL_TZ).tz_convert("UTC"),
        freq="h",
    )


def _temp(idx):
    doy = idx.tz_convert(paths.LOCAL_TZ).dayofyear
    return pd.Series(27 + 3 * np.sin(2 * np.pi * (doy - 100) / 365), index=idx)


def test_peak_scaled_and_balance():
    site = load_site()
    idx = _index()
    df = synthetic_load(idx, _temp(idx), site)
    loc = df.index.tz_convert(paths.LOCAL_TZ)
    npc = site["npc_itbayat_dpp"]
    for y in (2022, 2023, 2024):  # NPC calibration: annual energy and peak within a few %
        i = npc["years"].index(y)
        d = df.loc[loc.year == y, "total_kW"]
        assert abs(d.sum() / 1000 / npc["gross_gen_mwh"][i] - 1) < 0.04
        assert abs(d.max() / npc["peak_kw"][i] - 1) < 0.04
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
    # load factor follows NPC (0.46 in 2023), not the flat 0.60 of the uncalibrated model
    d = df.loc[loc.year == 2023, "total_kW"]
    assert 0.42 < d.mean() / d.max() < 0.50


def test_real_load_path(tmp_path):
    t = pd.date_range("2024-01-01", periods=48, freq="h")
    p = tmp_path / "plant.csv"
    pd.DataFrame({"timestamp": t, "total_kW": 150.0}).to_csv(p, index=False)
    df = read_real_load(p)
    assert df.attrs["synthetic"] == "False"
    assert df.index.tz is not None and len(df) == 48
    assert (df["critical_kW"] > 0).all() and np.allclose(df["flex_kW"], 150 - df["critical_kW"])
