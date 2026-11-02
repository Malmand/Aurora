"""System parameters for the twin, read from data/itbayat/site.yaml.

Two sizings are kept (brief, known problem 3):
  inl   300 kWp PV, 300 kW / 300 kWh battery (INL 2025 proposal)
  case  500 kWp PV, 375 kW / 1500 kWh battery (team case study, illustrative)
The diesel plant is the INL current state (known problem 2): 3 working units,
560 kW. Diesel price base 113 PHP/L (known problem 1).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from ..data.site import load_site, value

SIZINGS = {
    "inl": ("pv_kwp_inl", "battery_kw_inl", "battery_kwh_inl"),
    "case": ("pv_kwp_case", "battery_kw_case", "battery_kwh_case"),
}


@dataclass(frozen=True)
class SystemParams:
    # PV and battery
    pv_kwp: float
    bat_kw: float
    bat_kwh: float
    eta: float              # one-way battery efficiency
    soc_min: float
    soc_max: float
    soc0: float
    soc_cest: float         # CEST reserve line
    # diesel
    n_units: int
    unit_kw: float
    min_load_frac: float
    fuel_a: float           # L/h per kW committed
    fuel_b: float           # L/kWh
    # fuel logistics
    tank_l: float
    resupply_days: float
    overdue_days: float
    # economics and controller weights (PHP)
    diesel_php_per_l: float
    co2_kg_per_l: float
    co2_php_per_t: float
    deg_php_per_kwh: float
    voll_flex: float
    risk_php_per_kwh: float
    risk_window_h: int
    scarcity_php_per_kwh: float
    start_cost_php: float
    php_per_usd: float
    sizing: str = "inl"

    @property
    def fuel_cost_per_l(self) -> float:
        """Fuel plus emissions cost per litre used in the MPC objective."""
        return self.diesel_php_per_l + self.co2_kg_per_l * self.co2_php_per_t / 1000.0

    @property
    def sfc_min_load(self) -> float:
        """L/kWh of one unit at minimum loading (worst case, used for fuel autonomy)."""
        return self.fuel_b + self.fuel_a / self.min_load_frac

    def fuel_l(self, n_on, p_kw):
        """Litres in one hour for n_on committed units producing p_kw in total."""
        return self.fuel_a * self.unit_kw * n_on + self.fuel_b * p_kw

    def with_(self, **kw) -> "SystemParams":
        return replace(self, **kw)

    def as_dict(self) -> dict:
        return asdict(self)


def from_site(sizing: str = "inl", site: dict | None = None, **override) -> SystemParams:
    s = site or load_site()
    v = lambda k: value(s, k)  # noqa: E731
    pv, bkw, bkwh = (v(k) for k in SIZINGS[sizing])
    p = SystemParams(
        pv_kwp=float(pv), bat_kw=float(bkw), bat_kwh=float(bkwh),
        eta=v("battery_eta_oneway"), soc_min=v("battery_soc_min"), soc_max=v("battery_soc_max"),
        soc0=v("battery_soc_initial"), soc_cest=v("cest_reserve_soc"),
        n_units=int(v("diesel_units_available")), unit_kw=v("diesel_unit_kw_assumed"),
        min_load_frac=v("diesel_min_loading_frac"),
        fuel_a=v("diesel_fuel_noload_l_per_h_per_kw"), fuel_b=v("diesel_fuel_slope_l_per_kwh"),
        tank_l=float(v("fuel_storage_l_assumed")), resupply_days=float(v("resupply_interval_days_assumed")),
        overdue_days=float(v("overdue_resupply_days_assumed")),
        diesel_php_per_l=float(v("diesel_price_php_per_l")), co2_kg_per_l=v("co2_kg_per_l"),
        co2_php_per_t=float(v("co2_shadow_price_php_per_t")),
        deg_php_per_kwh=v("battery_degradation_php_per_kwh"), voll_flex=float(v("voll_flex_php_per_kwh")),
        risk_php_per_kwh=float(v("risk_penalty_php_per_kwh")), risk_window_h=int(v("risk_window_h")),
        scarcity_php_per_kwh=float(v("fuel_scarcity_penalty_php_per_kwh")),
        start_cost_php=float(v("diesel_start_cost_php")), php_per_usd=float(v("php_per_usd")),
        sizing=sizing,
    )
    return p.with_(**override) if override else p
