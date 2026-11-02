"""Phase 3 digital twin: energy balance, SOC bounds, critical load, fuel, CEST, MPC.

Tests use small hand-made inputs (labelled synthetic here) so they run fast and
do not depend on the committed weather files, except the last one.
"""
import numpy as np
import pandas as pd
import pytest

from aurora.twin import cest, controllers, forecasts, metrics, mpc, params, plant, scenarios, simulate

P = params.from_site("inl")


def synthetic_truth(days=4, pv_scale=1.0, start="2024-06-01 16:00"):
    """SYNTHETIC test truth: bell-shaped PV (local noon = 04 UTC), flat-ish load."""
    idx = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    h_loc = (idx.hour + 8) % 24
    pv = np.clip(np.sin(np.pi * (h_loc - 6) / 12), 0, None) * 0.7 * pv_scale
    crit = np.where((h_loc >= 7) & (h_loc < 18), 65.0, 40.0)
    flex = 100 + 60 * np.exp(-0.5 * ((h_loc - 19) / 2) ** 2)
    return pd.DataFrame({"pv_kw_per_kwp": pv, "pv_clear_kw_per_kwp": np.clip(np.sin(np.pi * (h_loc - 6) / 12), 0, None) * 0.7,
                         "crit_kW": crit, "flex_kW": flex}, index=idx)


def check_physics(run, p, has_battery=True):
    assert run["balance_resid"].abs().max() < 1e-6
    if has_battery:
        assert run["soc_end"].min() >= p.soc_min - 1e-9
        assert run["soc_end"].max() <= p.soc_max + 1e-9
    assert (run["tank_end"] >= -1e-6).all()
    assert (run["shed"] <= run["flex"] + 1e-9).all()
    assert (run["unserved_crit"] <= run["crit"] + 1e-9).all()
    on = run["n_on"].to_numpy()
    lo = on * p.unit_kw * p.min_load_frac
    assert (run["diesel"].to_numpy() >= lo - 1e-6).all()
    assert (run["diesel"].to_numpy() <= on * p.unit_kw + 1e-6).all()


# ---------------------------------------------------------------- plant
@pytest.mark.parametrize("solar,crit,flex,dec", [
    (0.0, 50, 150, plant.Decision(n_on=0)),                       # battery + emergency start
    (250.0, 50, 50, plant.Decision(n_on=1, p_diesel=100)),        # surplus with a unit on
    (100.0, 60, 100, plant.Decision(n_on=1, p_diesel=186.7)),     # diesel charging battery
    (0.0, 65, 200, plant.Decision(n_on=3, p_diesel=10)),          # over-committed
])
def test_plant_step_balance_and_bounds(solar, crit, flex, dec):
    for soc in (P.soc_min, 0.5, P.soc_max):
        o = plant.step(P, soc, 1e5, solar, crit, flex, dec)
        assert abs(o["balance_resid"]) < 1e-9
        assert P.soc_min - 1e-9 <= o["soc_end"] <= P.soc_max + 1e-9
        assert o["unserved_crit"] == pytest.approx(0.0)
        n = o["n_on"]
        assert n * P.unit_kw * P.min_load_frac - 1e-9 <= o["diesel"] <= n * P.unit_kw + 1e-9


def test_plant_no_fuel_sheds_flex_before_critical():
    o = plant.step(P, P.soc_min, 0.0, 0.0, 50, 100, plant.Decision(n_on=1, p_diesel=150))
    assert o["n_on"] == 0 and o["diesel"] == 0
    assert o["shed"] == pytest.approx(100)
    assert o["unserved_crit"] == pytest.approx(50)
    assert abs(o["balance_resid"]) < 1e-9


def test_fuel_tank_delayed_delivery():
    t0 = pd.Timestamp("2024-06-01", tz="UTC")
    s = plant.FuelSchedule(1000.0, 10, first=t0 + pd.Timedelta(days=1), delays={t0 + pd.Timedelta(days=1): 3})
    tank = plant.FuelTank(s, 100.0)
    tank.receive(t0 + pd.Timedelta(days=2))
    assert tank.level == 100.0                                   # not yet: delayed
    exp = tank.expected_arrivals(t0 + pd.Timedelta(days=2), t0 + pd.Timedelta(days=3), overdue_days=7)
    assert exp[0] == t0 + pd.Timedelta(days=9)                    # overdue: assumed 7 days on
    tank.receive(t0 + pd.Timedelta(days=4))
    assert tank.level == 1000.0


# ---------------------------------------------------------------- controllers, full loop
@pytest.mark.parametrize("ctl", ["A", "B", "C"])
def test_runs_close_energy_balance_and_serve_critical(ctl):
    tr = synthetic_truth(days=3)
    fc = forecasts.PerfectForecast(tr, P.pv_kwp)
    run = simulate.run(tr, P, ctl, fc, hours=24, horizon=24)
    check_physics(run, P, has_battery=ctl != "A")
    assert run["unserved_crit"].sum() == pytest.approx(0.0, abs=1e-6)   # ample diesel and fuel
    k = metrics.kpis(run, P)
    assert k["crit_outage_h"] == 0 and k["relaxed_steps"] == 0


def test_mpc_protects_critical_when_fuel_is_short():
    """Fuel for critical load but not for all load, no delivery: B runs dry, C must not."""
    tr = synthetic_truth(days=4, pv_scale=0.15)          # SYNTHETIC overcast spell
    fc = forecasts.PerfectForecast(tr, P.pv_kwp)
    t0 = tr.index[0]
    sched = plant.FuelSchedule(P.tank_l, 30, first=t0 + pd.Timedelta(days=20))
    out = {}
    for c in ("B", "C"):
        out[c] = simulate.run(tr, P, c, fc, hours=48, horizon=24, schedule=sched, tank0=1300.0)
        check_physics(out[c], P)
    assert out["B"]["unserved_crit"].sum() > 1.0
    assert out["C"]["unserved_crit"].sum() == pytest.approx(0.0, abs=1e-6)
    assert out["C"]["shed"].sum() > 0


def test_mpc_hard_critical_and_relaxed_fallback():
    H = 6
    base = dict(solar=np.zeros(H), crit=np.full(H, 50.0), flex=np.full(H, 50.0), e0=P.soc_min * P.bat_kwh,
                n_prev=0, delivery_steps=[], need_q=None, crit_need_after=0.0)
    plan = mpc.solve(mpc.MPCInput(tank0=1e4, **base), P)
    assert not plan["relaxed"] and plan["unserved"].sum() == 0
    bal = plan["p_diesel"] + plan["discharge"] - plan["charge"] - plan["curtail"]
    assert np.allclose(bal, base["crit"] + base["flex"] - plan["shed"], atol=1e-5)
    plan = mpc.solve(mpc.MPCInput(tank0=0.0, **base), P)      # no fuel, empty battery
    assert plan["relaxed"] and plan["unserved"].sum() > 0


# ---------------------------------------------------------------- CEST and risk
def test_cest_constant_load():
    p = P.with_(bat_kwh=100.0, bat_kw=100.0, eta=1.0, soc_cest=0.3)
    # 70 kWh above the reserve, 10 kW critical, no sun -> 7 h
    assert cest.cest_hours(1.0, np.zeros(48), np.full(48, 10.0), p) == pytest.approx(7.0)
    assert cest.cest_hours(0.3, np.zeros(48), np.full(48, 10.0), p) == 0.0
    # enough sun all the time -> censored at the cap
    assert cest.cest_hours(0.5, np.full(48, 20.0), np.full(48, 10.0), p, cap=72) == 72.0


def test_quantile_sampling_reproduces_bands():
    rng = np.random.default_rng(0)
    H = 5
    q10, q50, q90 = np.full(H, 20.0), np.full(H, 50.0), np.full(H, 70.0)
    u = scenarios.correlated_uniforms(20000, H, 0.9, rng)
    x = scenarios.inverse_cdf(u, q10, q50, q90, 0.0, 1e9)
    got = np.percentile(x, [10, 50, 90], axis=0).mean(axis=1)
    assert got == pytest.approx([20, 50, 70], abs=1.0)


def test_survival_need_and_risk():
    p = P.with_(eta=1.0, bat_kw=1000.0)
    sol = np.zeros((2, 4))
    crit = np.array([[10.0] * 4, [20.0] * 4])
    need = scenarios.survival_need(sol, crit, p, window=4)
    assert need[:, 0] == pytest.approx([40.0, 80.0])
    have = lambda soc: (soc - p.soc_cest) * p.bat_kwh  # noqa: E731
    soc = p.soc_cest + 50.0 / p.bat_kwh
    assert have(soc) == pytest.approx(50.0)
    assert scenarios.risk_now(need[:, 0], soc, p) == pytest.approx(0.5)


# ---------------------------------------------------------------- forecast loader
def test_csv_forecast_loader(tmp_path):
    tr = synthetic_truth(days=3)
    t0 = tr.index[24]
    idx = pd.date_range(t0, periods=24, freq="h", tz="UTC")
    df = pd.DataFrame({"issue_time": t0, "timestamp": idx.strftime("%Y-%m-%dT%H:%M:%SZ")})
    for b in forecasts.BASES:
        df[f"{b}_p10"], df[f"{b}_p50"], df[f"{b}_p90"] = 1.0, 3.0, 2.0   # crossing on purpose
    df["fallback"] = False
    df.to_csv(tmp_path / "synthetic_issue.csv", index=False)
    f = forecasts.CSVForecast(tmp_path, tr, P.pv_kwp)
    out = f(t0, 48)
    assert len(out) == 48
    assert (out.iloc[:24]["solar_kW_p90"] == 3.0).all()                 # sorted
    assert not out.iloc[:24]["fallback"].any() and out.iloc[24:]["fallback"].all()
    early = f(tr.index[0], 24)                                           # before any issue
    assert early["fallback"].all()


def test_params_use_inl_current_state_and_both_sizings():
    assert P.n_units * P.unit_kw == pytest.approx(560.0, abs=0.5)
    assert P.diesel_php_per_l == 113
    c = params.from_site("case")
    assert (P.pv_kwp, P.bat_kwh) == (300, 300) and (c.pv_kwp, c.bat_kwh) == (500, 1500)
