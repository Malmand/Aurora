"""Artificial track fixture: a storm moving due north through the site's longitude."""

import numpy as np
import pandas as pd

from aurora.data import paths
from aurora.data.typhoons import events, haversine_km, site_flags, to_hourly


def test_haversine_one_degree_latitude():
    assert abs(haversine_km(0, 0, 1, 0) - 111.19) < 0.1


def _track():
    t = pd.date_range("2023-05-29", periods=17, freq="3h", tz="UTC")
    lat = np.linspace(paths.LAT - 6, paths.LAT + 6, len(t))
    return pd.DataFrame(
        {"SID": "X", "NAME": "TEST", "time": t, "LAT": lat, "LON": paths.LON, "wind_kt": 80.0, "pres_hpa": 950.0}
    )


def test_flags_and_events():
    h = to_hourly(_track())
    assert len(h) == 49  # 48 h span, hourly inclusive
    idx = pd.date_range("2023-05-28", "2023-06-02", freq="h", tz="UTC")
    f = site_flags(h, idx)
    # speed 12 deg / 48 h = 0.25 deg/h = ~27.8 km/h; within 300 km about +-10.8 h
    n300 = int(f["tc_within_300km"].sum())
    n500 = int(f["tc_within_500km"].sum())
    assert 20 <= n300 <= 23 and 35 <= n500 <= 37
    assert not f["tc_within_300km"].iloc[0]
    ev = events(h)
    assert len(ev) == 1 and ev.loc[0, "closest_km"] < 1
