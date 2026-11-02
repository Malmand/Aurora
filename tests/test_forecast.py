import numpy as np
import pandas as pd
import pytest

from aurora.forecast import baselines, quantile as Qm
from aurora.forecast.features import QUANTILES, issue_times, lead_day_of, lead_features
from aurora.forecast.geometry import clearsky_index, hourly_clearsky, season


def test_crps_of_point_forecast_equals_mae():
    rng = np.random.default_rng(0)
    y, f = rng.normal(size=500), rng.normal(size=500)
    Q = np.repeat(f[:, None], len(QUANTILES), axis=1)
    assert np.allclose(Qm.crps_quantiles(y, Q), np.abs(y - f))


def test_crps_ensemble_single_member_is_mae():
    y = np.array([1.0, 2.0])
    E = np.array([[0.5], [3.0]])
    assert np.allclose(Qm.crps_ensemble(y, E), [0.5, 1.0])


def test_pinball():
    assert Qm.pinball(np.array([1.0]), np.array([0.0]), 0.9)[0] == pytest.approx(0.9)
    assert Qm.pinball(np.array([0.0]), np.array([1.0]), 0.9)[0] == pytest.approx(0.1)


def test_conformal_restores_coverage():
    """Quantiles that are too narrow get ~80 % coverage after the conformal shift."""
    rng = np.random.default_rng(1)
    n = 4000
    y = rng.normal(size=2 * n)
    z = np.array([-1.2816, 0.0, 1.2816]) * 0.5          # band half as wide as it should be
    levels = (0.1, 0.5, 0.9)
    Q = np.tile(z, (2 * n, 1))
    pool_scores = y[:n, None] - Q[:n]
    g = pd.DataFrame({"lead_day": 1, "season": ["JJA"] * n})
    Qc, ok = Qm.calibrate(Q[n:], g, pool_scores, g, levels=levels, keep_median=True, lo=None)
    picp = np.mean((y[n:] >= Qc[:, 0]) & (y[n:] <= Qc[:, 2]))
    raw = np.mean((y[n:] >= Q[n:, 0]) & (y[n:] <= Q[n:, 2]))
    assert ok.all() and raw < 0.6 and abs(picp - 0.8) < 0.03
    assert np.all(np.diff(Qc, axis=1) >= 0)


def test_calibrate_falls_back_when_pool_small():
    Q = np.tile([0.1, 0.5, 0.9], (10, 1))
    g = pd.DataFrame({"lead_day": 1, "season": ["DJF"] * 10})
    Qc, ok = Qm.calibrate(Q, g, np.zeros((5, 3)), g.iloc[:5].reset_index(drop=True), levels=(0.1, 0.5, 0.9))
    assert not ok.any() and np.allclose(Qc, Q)


def test_clearsky_and_index():
    idx = pd.date_range("2024-06-01", periods=48, freq="h", tz="UTC")
    cs = hourly_clearsky(idx)
    local = idx.tz_convert("Asia/Manila")
    noon = cs["ghi_clear"][local.hour == 12]
    night = cs["ghi_clear"][local.hour == 1]
    assert (noon > 900).all() and (night == 0).all()
    k = clearsky_index(cs["ghi_clear"] * 0.5, cs["ghi_clear"])
    assert np.allclose(k[cs["daylight"]], 0.5) and k[~cs["daylight"]].isna().all()


def test_issue_window_and_causality():
    idx = pd.date_range("2024-06-01 17:00", periods=48, freq="h", tz="UTC")
    for ld in (1, 2):
        it = issue_times(idx, ld)
        lead = (idx - it) / pd.Timedelta(hours=1)
        assert lead.min() >= 24 * (ld - 1) + 1 and lead.max() <= 24 * ld
        assert (it.hour == 16).all()
    assert list(lead_day_of([1, 24, 25, 48])) == [1, 1, 2, 2]


def test_persistence_features_never_use_the_future():
    idx = pd.date_range("2024-05-25", "2024-06-10", freq="h", tz="UTC")
    base = hourly_clearsky(idx)
    base["k_sat"] = np.arange(len(idx), dtype=float)     # k encodes the time it was observed
    base["season"] = season(idx)
    for ld in (1, 2):
        X = lead_features(base, {}, ld)
        it = issue_times(idx, ld)
        obs_pos = X["k_persist"].dropna()
        # the persisted value was observed at or before the issue time
        assert (idx[obs_pos.astype(int).to_numpy()] <= it[base.index.get_indexer(obs_pos.index)]).all()
        pm = X["k_prevday_mean"].dropna()
        # day-mean of the previous local day: all its hours end before the issue time
        assert (pm.to_numpy() < base.index.get_indexer(it[base.index.get_indexer(pm.index)])).all()


def test_fallback_widens_and_is_monotone():
    rng = np.random.default_rng(2)
    n = 3000
    kc = np.full(n, 0.7)
    kp = np.clip(0.7 + rng.normal(0, 0.2, n), 0, 1.2)
    y = np.clip(0.5 * kp + 0.35 + rng.normal(0, 0.1, n), 0, 1.3)
    ld, s = np.full(n, 1), np.array(["JJA"] * n)
    par = baselines.fit_fallback(pd.Series(kp), pd.Series(kc), pd.Series(y), pd.Series(ld), pd.Series(s))
    assert 0.3 < par["w"][1] < 0.7
    Q1 = baselines.predict_fallback(par, kp, kc, ld, s, widen=1.0)
    Q2 = baselines.predict_fallback(par, kp, kc, ld, s, widen=1.25)
    j10, j90 = QUANTILES.index(0.1), QUANTILES.index(0.9)
    assert np.all(np.diff(Q2, axis=1) >= 0)
    assert (Q2[:, j90] - Q2[:, j10]).mean() > (Q1[:, j90] - Q1[:, j10]).mean()
    assert abs(np.mean((y >= Q1[:, j10]) & (y <= Q1[:, j90])) - 0.8) < 0.05
    # missing persistence -> climatology-centred forecast, still finite
    Qn = baselines.predict_fallback(par, np.full(3, np.nan), kc[:3], ld[:3], s[:3])
    assert np.isfinite(Qn).all()


def test_climatology_table_quantiles_sorted():
    idx = pd.date_range("2020-01-01", periods=24 * 400, freq="h", tz="UTC")
    k = pd.Series(np.random.default_rng(3).uniform(0, 1, len(idx)), index=idx)
    tab = baselines.climatology_table(k)
    q = tab[[c for c in tab.columns if c.startswith("q")]].to_numpy()
    assert np.all(np.diff(q, axis=1) >= 0)
    assert len(baselines.climatology(tab, idx[:10])) == 10


def test_from_backtest_schema_and_night_zero():
    from aurora.forecast import operational as O

    it = pd.Timestamp("2025-07-01 16:00", tz="UTC")
    w = O.window(it)
    day = w[(w.tz_convert("Asia/Manila").hour >= 7) & (w.tz_convert("Asia/Manila").hour <= 17)]
    solar = pd.DataFrame({"issue_time": it, **{f"pv_kw_per_kwp_p{p}": 0.1 * (i + 1)
                                                for i, p in enumerate((10, 50, 90))}}, index=day)
    dem = pd.DataFrame({"issue_time": it, **{f"{c}_p{p}": float(p) for c in ("critical", "flex")
                                             for p in (10, 50, 90)}}, index=w)
    df = O.from_backtest(solar, dem, it, pv_kwp=300)
    assert list(df.columns) == O.SCHEMA and len(df) == 48
    assert (df["timestamp"] > it).all() and df["timestamp"].iloc[-1] == it + pd.Timedelta(hours=48)
    night = ~df["timestamp"].isin(day)
    assert (df.loc[night, "solar_kW_p50"] == 0).all()
    assert np.allclose(df.loc[~night, "solar_kW_p50"], 60.0)
    assert (df["solar_kW_p10"] <= df["solar_kW_p50"]).all() and not df["fallback"].any()
    with pytest.raises(ValueError):
        O.normalise_issue("2025-07-01T03:00Z")


def test_fallback_flag_when_no_nwp():
    from aurora.forecast import operational as O

    if not (O.MODEL_DIR / "bundle.pkl").exists():
        pytest.skip("models not built (python -m aurora.forecast.build)")
    it = pd.Timestamp("2025-07-01 16:00", tz="UTC")
    df = O.forecast_issue(it, nwp=None, ghi_obs=None)
    assert df["fallback"].all() and list(df.columns) == O.SCHEMA
    assert (df["solar_kW_p10"] <= df["solar_kW_p50"]).all() and (df["solar_kW_p50"] <= df["solar_kW_p90"]).all()
    assert df["solar_kW_p90"].max() > 0
