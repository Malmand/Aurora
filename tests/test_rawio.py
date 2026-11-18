"""Conversion tests with small hand-made inputs (fixtures, not site data)."""

import importlib.util
import datetime as dt

import numpy as np
import pandas as pd

from aurora.data import paths, rawio


def test_previous_runs_columns():
    h = {
        "time": ["2024-06-01T00:00", "2024-06-01T01:00"],
        "shortwave_radiation": [100.0, 200.0],
        "shortwave_radiation_previous_day1": [110.0, 190.0],
        "temperature_2m_previous_day2": [28.0, 28.5],
    }
    df = rawio.om_previous_runs_to_frame(h)
    assert list(df.columns) == ["ghi_wm2_d0", "ghi_wm2_d1", "temp_c_d2"]
    assert str(df.index.tz) == "UTC"


def test_cds_conversion_units_and_dni():
    idx = pd.date_range("2024-06-01 01:00", periods=6, freq="h", tz="UTC")  # local morning to noon
    ssrd = np.array([1.8e6, 2.5e6, 3.0e6, 3.2e6, 3.3e6, 3.0e6])  # J/m2 per hour
    raw = pd.DataFrame(
        {
            "ssrd": ssrd,
            "fdir": 0.6 * ssrd,
            "t2m": 301.15,
            "d2m": 297.15,
            "tp": 0.001,
            "msl": 100800.0,
            "sp": 100700.0,
            "tcc": 0.5,
            "lcc": 0.2,
            "mcc": 0.1,
            "hcc": 0.3,
            "u10": 3.0,
            "v10": -4.0,
            "fg10": 8.0,
        },
        index=idx,
    )
    out = rawio.cds_to_schema(raw)
    assert np.allclose(out["ghi_wm2"], ssrd / 3600)
    assert np.allclose(out["dhi_wm2"], 0.4 * ssrd / 3600)
    assert (out["dni_wm2"] >= 0.6 * ssrd / 3600 - 1e-9).all()  # DNI >= horizontal beam
    assert np.allclose(out["temp_c"], 28.0) and np.allclose(out["precip_mm"], 1.0)
    assert np.allclose(out["wind_ms"], 5.0) and np.allclose(out["wind_dir_deg"], 323.13, atol=0.01)
    assert np.allclose(out["mslp_hpa"], 1008.0) and np.allclose(out["cloud_pct"], 50.0)
    assert 78 < out["rh_pct"].iloc[0] < 80


def test_era5_grid_point():
    assert rawio.era5_grid_point() == (20.75, 121.75)


def test_power_shift():
    idx = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    out = rawio.power_to_hour_ending(pd.DataFrame({"ghi_wm2": [0, 1, 2]}, index=idx))
    assert out.index[0] == idx[1]


def test_download_chunks_cover_range():
    spec = importlib.util.spec_from_file_location("dl", paths.ROOT / "scripts" / "download_itbayat.py")
    dl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dl)
    c = list(dl.chunks(dt.date(2015, 1, 1), dt.date(2016, 2, 10), 3))
    assert c[0] == (dt.date(2015, 1, 1), dt.date(2015, 3, 31))
    assert c[-1][1] == dt.date(2016, 2, 10)
    assert all((b2 - a1).days == 1 for (_, a1), (b2, _) in zip(c, c[1:]))
