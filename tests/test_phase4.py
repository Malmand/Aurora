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
    assert P.cost_basis()["basis"] == "interim ASSUMPTION"      # published values not yet transcribed
    assert P.capex_usd(300, 300, 300) == pytest.approx(300 * 1500 + 300 * 450 + 300 * 150)
    from aurora.data.site import load_site
    v = load_site()["values"]
    v["pv_capex_usd_per_kw_irena2025"]["value"] = 1000.0         # SYNTHETIC test values
    v["battery_capex_usd_per_kwh_nrel_atb2025"]["value"] = 200.0
    c = P.cost_basis(v)
    assert c["basis"] == "published" and c["bat_source"] == "NREL_ATB2025"
    assert P.capex_usd(300, 300, 300, site=v) == pytest.approx(1.5 * (300 * 1000 + 300 * 200))
    sw = pd.DataFrame([
        dict(controller="C", pv_kwp=600, bat_kwh=500, bat_kw=375, crit_outage_h=0, cest_median_h=30),
        dict(controller="C", pv_kwp=200, bat_kwh=1000, bat_kw=375, crit_outage_h=0, cest_median_h=40),
        dict(controller="C", pv_kwp=100, bat_kwh=500, bat_kw=375, crit_outage_h=3, cest_median_h=40),
        dict(controller="C", pv_kwp=100, bat_kwh=750, bat_kw=375, crit_outage_h=0, cest_median_h=20),
        dict(controller="B", pv_kwp=0, bat_kwh=0, bat_kw=0, crit_outage_h=0, cest_median_h=99),
    ])
    r = P.recommended(sw)
    assert (r.pv_kwp, r.bat_kwh) == (200, 1000)                  # cheapest that meets both conditions
