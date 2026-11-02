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
