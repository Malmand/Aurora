"""Phase 4 helpers: storm selection, sizing rule, capex, recommended-size rule."""
import pandas as pd
import pytest

from aurora.experiments import phase4 as P


def test_storm_selection_and_windows():
    st = P.select_storms()
    assert list(st.index) == ["mawar2023", "ragasa2025", "mekkhala2026"]
    assert st.loc["mawar2023", "start"] == "2023-05-27"          # the Phase 3 demo window
    assert st.loc["mawar2023", "forecast_regime"].startswith("backup")
    assert (st.loc[["ragasa2025", "mekkhala2026"], "forecast_regime"] == "full Phase 2 model").all()
    assert "CHAMPI" in st.attrs["skipped"]                       # its 18-day window runs past the data end


def test_sweep_sizing_reproduces_inl_and_case_power():
    assert P.sized(300, 300).bat_kw == 300 and P.sized(500, 1500).bat_kw == 375
    assert P.sized(0, 0).bat_kw == 0


def test_capex_and_recommended_rule():
    u = P.unit_costs()
    assert P.capex_php(180, 120, 120) == pytest.approx(57_697_900)          # reproduces the Sabtang ABC
    pv, e, w = u["base"]
    assert pv * 180 / 57_697_900 == pytest.approx(1200 * 180 / (1200 * 180 + 260 * 120 + 540 * 120))
    assert u["low"] == pytest.approx([1200 * 56, 260 * 56, 540 * 56])
    assert u["high"] == pytest.approx(1.25 * u["base"])
    sw = pd.DataFrame([
        dict(controller="C", pv_kwp=600, bat_kwh=500, bat_kw=375, crit_outage_h=0, cest_median_h=30),
        dict(controller="C", pv_kwp=200, bat_kwh=1000, bat_kw=375, crit_outage_h=0, cest_median_h=40),
        dict(controller="C", pv_kwp=100, bat_kwh=500, bat_kw=375, crit_outage_h=3, cest_median_h=40),
        dict(controller="C", pv_kwp=100, bat_kwh=750, bat_kw=375, crit_outage_h=0, cest_median_h=20),
        dict(controller="B", pv_kwp=0, bat_kwh=0, bat_kw=0, crit_outage_h=0, cest_median_h=99),
    ])
    r = P.recommended(sw)
    assert (r.pv_kwp, r.bat_kwh) == (200, 1000)                  # cheapest that meets both conditions


def test_discounted_payback_with_replacement():
    from aurora.experiments.phase4_tables import discounted_payback
    assert discounted_payback(100, [50] * 20, 0.0) == pytest.approx(2.0)
    assert discounted_payback(100, [10] * 20, 0.0) == pytest.approx(10.0)
    flows = [10] * 20
    flows[14] -= 120                  # replacement in year 15 undoes the payback; recovered? cum(20) = 80 < 100
    assert pd.isna(discounted_payback(100, flows, 0.0))
    flows = [20] * 20
    flows[14] -= 60                   # capex 250: repaid in year 13, dips to 240 in year 15, repaid again in year 16
    assert discounted_payback(250, flows, 0.0) == pytest.approx(15.5)
    assert pd.isna(discounted_payback(100, [5] * 20, 0.0994))


def test_aurora_cost_per_outage_hour(tmp_path, monkeypatch):
    from aurora.experiments import phase4_tables as T
    monkeypatch.setattr(T, "OUT", tmp_path)
    rows = []                                                    # SYNTHETIC storm results
    for st in ("s1", "s2"):
        for d, b in zip((3, 7, 14), (0, 10, 50)):
            rows += [dict(storm=st, sizing="inl", delay_days=d, controller="B", crit_outage_h=b),
                     dict(storm=st, sizing="inl", delay_days=d, controller="C", crit_outage_h=0)]
    sm, pe = T.aurora_resilience(pd.DataFrame(rows))
    assert sm.loc[0, "avoided_h_per_event"] == pytest.approx(0.3 * 10 + 0.2 * 50)
    ann = 2.5e6 * T.crf(0.0994, 20) + 0.5e6
    assert sm.loc[0, "php_per_h_avoided_rate_base_cost_base"] == pytest.approx(ann / (0.85 * 13.0))
    assert sm.loc[0, "events_per_yr_upper_bound"] == 4.15
    assert pe.loc[2, "php_per_h_avoided_rate_base"] == pytest.approx(ann / 0.85 / 50)
    assert pe["php_per_h_avoided_rate_base"].isna().sum() == 2      # 3-day delay: nothing avoided
