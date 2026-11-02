# Digital twin with MILP rolling-horizon MPC (Phase 3)

Code: [`aurora/twin/`](../aurora/twin/). Tests: [`tests/test_twin.py`](../tests/test_twin.py).
Demonstration run: `python -m aurora.twin.run --demo` writes [`results/twin/`](../results/twin/).

The twin simulates the Itbayat grid hour by hour: PV, battery, diesel units, fuel tank and the critical and flexible loads. It runs three controllers on the same inputs and scores them on fuel, critical outages and Community Energy Survival Time (CEST).

**Inputs are not measurements.** By default, weather truth is ERA5 reanalysis (or the satellite retrieval, with `radiation="satellite"`). Load is the Phase 1 **synthetic** series. Every system and controller number comes from `data/itbayat/site.yaml`, and 31 of them are `ASSUMPTION`s with a sensitivity range (see the last section).

## What was ported, and what was fixed

These parts of `aurora-gsc/aurora-digital-twin` (Mohamed's code) were ported and rewritten:

| Team repo | Here |
|---|---|
| `digital_twin/aurora_skeleton.py`: `step`, `run`, `cest` | `plant.py` (now with diesel units, minimum load and a fuel tank), `simulate.py`, `cest.py` |
| `digital_twin/forecast_io.py`: time columns, time zones, `_p10/_p90` and `_low/_high` bands | `forecasts.read_forecast_csv`, `CSVForecast` |
| `case_batanes.py`: controllers A/B/C, stress test, KPIs | `controllers.py`, `run.py`, `metrics.py` |

Katharina's `forecasting/` was not used.

These known problems from `docs/CLOUD_BRIEF.md` were fixed:

| Problem in the team case study | Now |
|---|---|
| Diesel 65 PHP/L | 113 PHP/L base (INL). 65 and 140 PHP/L are in `site.yaml` for Phase 4 |
| One 790 kW diesel block, flat 0.277 L/kWh | INL current state: 3 working units, 560 kW in total. Unit commitment with a 30 % minimum load and a linear fuel curve |
| Only 500 kWp / 1.5 MWh | Both sizings: `inl` (300 kWp, 300 kW / 300 kWh) and `case` (500 kWp, 375 kW / 1.5 MWh) |
| Synthetic clear-sky × cloud-normal weather | ERA5 hourly from `raw_small/`, with PV from pvlib (`aurora/data/pvmodel.py`, the same array as the Phase 1 yield check) |
| Synthetic typhoon (solar × 0.12 for 5 days), fuel stock "2 days" | Real typhoon weather windows. The fuel tank is a state with scheduled deliveries, each of which can be delayed |
| CEST computed on actual solar, down to the 20 % hard floor | CEST on forecast P10 solar and P90 critical demand, down to the 30 % reserve (definition in the brief) |
| Heuristic AURORA rule | MILP rolling-horizon MPC (PuLP + HiGHS) |

## Time convention

Each row is one hourly step, and its timestamp (UTC) marks the start of the step. Radiation in `raw_small/` is the mean of the hour ending at its label, so PV is shifted back one hour. The forecast schema is the Phase 2 schema: `solar_kW_p10/p50/p90`, `demand_critical_kW_p10/p50/p90`, `demand_flex_kW_p10/p50/p90`, `fallback`.

## Plant (`plant.py`)

The controller sends a decision: units committed, a diesel set point and planned flexible shedding. The plant applies that decision to the **actual** solar and load, and the battery forms the grid. When the battery cannot cover the mismatch, the plant moves diesel within the committed range, then starts more units if the tank allows, then sheds flexible load. Critical load goes unserved only after all of that. A surplus goes first to the battery, then diesel turns down and units stop, then PV is curtailed. Every step satisfies this energy balance exactly (the tests check it):

PV used + diesel + discharge = charge + critical served + flexible served

Fuel use of n committed units producing P kW over one hour is F = a P_u n + b P. Here P_u = 186.7 kW is the assumed unit rating, a = 0.04 L/h per kW and b = 0.22 L/kWh. At 70 % loading this gives 0.277 L/kWh, the team value. Each delivery tops the tank up to capacity (60,000 L assumed). Deliveries are planned every 30 days (assumed), and any one of them can be delayed.

## Controllers (`controllers.py`)

- **A, diesel only.** The status quo. No PV, no battery, fewest units that carry the load.
- **B, simple rule.** PV and battery, no forecast. Solar serves the load, any surplus charges the battery, and a deficit is drawn from the battery down to its 20 % floor before diesel starts.
- **C, AURORA MPC.** A MILP over a 48 h horizon on the forecast. C applies the first hour, then re-solves.

### MILP (`mpc.py`)

For each step t of the horizon, on the P50 forecast:

min Σ_t [c_f F_t + c_deg (P_c,t + P_x,t) + c_shed L_t + c_st s_t] + (c_risk / (H Q)) Σ_t Σ_q z_q,t + c_sc w − v_e e_H

c_f is the diesel price plus the CO2 shadow cost per litre. P_c and P_x are battery charge and discharge. L is the flexible load shed, s counts unit starts, e is battery energy, z and w are the risk and fuel-autonomy shortfalls defined below, and v_e values the energy left in the battery at the horizon end at the diesel energy it displaces.

The constraints:

- **Power balance.** PV − curtailment + P_d + P_x − P_c = D_crit + D_flex − L. There is no slack on critical load, so it is a hard constraint.
- **Battery.** e_t+1 = e_t + η P_c − P_x / η, with E soc_min ≤ e ≤ E soc_max.
- **Diesel.** n_t P_u m ≤ P_d ≤ n_t P_u, where n_t is an integer from 0 to 3 and m is the minimum load. Starts satisfy s_t ≥ n_t − n_t−1.
- **Fuel.** V_t+1 = V_t − F_t, with V ≥ 0. V resets to capacity at an expected delivery. An overdue tanker is expected 7 days from now, re-estimated every hour.
- **Risk.** z_q,t ≥ N_q,t − (e_t − E soc_cest), with z ≥ 0.
- **Fuel autonomy.** w ≥ C_need − V_H / sfc_min − (e_H − E soc_cest), with w ≥ 0.

If the hard model is infeasible (fuel and battery cannot physically carry critical load), C solves it again with a critical slack at 1e5 PHP/kWh and flags the step `relaxed`. A binary that forbids simultaneous charge and discharge is available (`exclusive_battery=True`). It is off by default: with losses, a degradation cost and free curtailment, the solver never chooses both at once, and the objective came out identical in a benchmark. The relative MIP gap is 0.5 %.

### Risk term and R(t) (`scenarios.py`)

The twin draws 64 Monte Carlo scenarios of solar and critical demand from the forecast quantiles. Each hour's CDF is piecewise linear through P10, P50 and P90 and extended linearly to the tails. A Gaussian copula with AR(1) correlation of 0.9 for solar and 0.95 for demand links the hours, so a cloudy morning tends to stay cloudy. For each scenario and start hour, a backward recursion gives the battery energy above the reserve that critical load needs to survive the next 24 h with diesel off. The scenarios are then sorted into 16 equal quantile groups, giving N_q,t.

- In the MILP, z is the expected shortfall of stored energy against N, a linear surrogate for the shortfall probability.
- In the output, **R(t)** is the share of scenarios in which the battery at the start of step t cannot carry critical load through the 24 h window if diesel stopped then.

### Fuel autonomy

C_need is the critical deficit (P90 critical minus P10 solar, with the last forecast day repeated) from the horizon end until the next expected delivery. Its penalty (500 PHP/kWh) is higher than the flexible-shedding penalty (150 PHP/kWh). So when fuel runs short, C sheds flexible load first to keep fuel for the clinic, water and telecoms.

## CEST (`cest.py`)

CEST counts the hours that critical load can run on the battery plus forecast P10 solar, with diesel and flexible load off, before SOC reaches the 30 % reserve. Critical demand is taken at P90. Beyond the 48 h forecast, the last 24 h are repeated, and values above 72 h are reported as 72 h (censored). The battery's power limits apply to both charge and discharge. All controllers are scored with the same forecast, so their CEST values are comparable. Controller A has no battery, so its CEST is 0 by definition.

## Forecast providers (`forecasts.py`)

- `PerfectForecast`: truth with zero spread. This is the upper bound for the value-of-forecasting runs.
- `PersistenceForecast`: the twin's own baseline, used until Phase 2 lands. P50 is daily smart persistence of the clear-sky index (PV over the last 24 h divided by clear-sky PV). P10 and P90 come from the daily clear-sky index of the last 30 days. Load uses the same hour of the last observed day, with ±2 % bands on critical and ±10 % on flexible. It uses only data from before the issue time.
- `CSVForecast(folder)`: reads the Phase 2 output files, one CSV per issue time. At each step it uses the newest issue at or before that step. Any hours that issue does not cover come from persistence with 1.5× wider bands and `fallback=True`, which also covers the case where comms are down.

## Demonstration: typhoon Mawar (Betty), late May 2023

`python -m aurora.twin.run --demo`. The window runs for 10 days from 27 May 2023, 00:00 PHT, with ERA5 weather and the synthetic load. Mawar passed 329 km from Itbayat on 30 May. The forecast is the twin's persistence baseline. Stress assumption: the tank holds 6,000 L (10 %) when the tanker due on 28 May is delayed 7 days, to 4 June. Phase 4 runs the full set (Sep 2022 and Betty, delays of 3, 7 and 14 days, value of forecasting).

| Sizing | Ctl | Diesel (L) | Fuel (M PHP) | CO2 (t) | RE share (%) | Flex shed (kWh) | Critical unserved (kWh) | Critical outage (h) | Battery throughput (kWh) | CEST median (h) | CEST ≥ 12 h (%) | CEST ≥ 24 h (%) | Mean R | Tank min (L) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| inl | A | 7,969 | 0.90 | 21.4 | 0.0 | 4,984 | 2,419 | 49 | 0 | 0.0 | 0.0 | 0.0 | 1.00 | 0 |
| inl | B | 6,757 | 0.76 | 18.1 | 35.9 | 0 | 0 | 0 | 1,459 | 0.0 | 0.4 | 0.0 | 0.89 | 437 |
| inl | C | 5,898 | 0.67 | 15.8 | 35.6 | 2,352 | 0 | 0 | 2,941 | 4.9 | 20.4 | 0.0 | 0.74 | 1,260 |
| case | A | 7,969 | 0.90 | 21.4 | 0.0 | 4,984 | 2,419 | 49 | 0 | 0.0 | 0.0 | 0.0 | 1.00 | 0 |
| case | B | 4,227 | 0.48 | 11.3 | 59.6 | 0 | 0 | 0 | 7,408 | 0.0 | 27.9 | 27.1 | 0.56 | 2,425 |
| case | C | 4,291 | 0.49 | 11.5 | 55.1 | 0 | 0 | 0 | 7,333 | 72.0 | 85.8 | 81.7 | 0.07 | 2,368 |

Source: `results/twin/demo_mawar2023_kpis.csv`. The hourly runs are in `results/twin/demo_mawar2023_{inl,case}/run_{A,B,C}.csv`.

What this shows, and what it does not:

- **Diesel only runs dry.** A runs out of fuel about 6 days into the delay and leaves critical load unserved for 49 h.
- **INL sizing.** B gets through with 437 L left. C uses 13 % less diesel, but it sheds 2,352 kWh of flexible load as insurance, because it assumes the late tanker is always 7 more days away. Looking back, this delay did not need that insurance. The setting is `overdue_resupply_days_assumed` (range 3 to 14 days) and Phase 4 should sweep it. With a 300 kWh battery, CEST stays short (median 4.9 h for C), because 195 kWh above the reserve covers about 5 h of critical load at night (35 kW) and less in the evening (49 to 65 kW).
- **Case sizing.** Fuel use is about the same for B and C (+1.5 % for C). The difference is resilience: C keeps the battery charged ahead of the low-sun days, so median CEST is 72 h (censored) against 0 h for B, and R drops from 0.56 to 0.07.
- This is one window, one assumed tank level and the persistence forecast. These numbers show the twin works. They are not the headline results, which come from Phase 4.

The case where the hard constraint matters is checked in `tests/test_twin.py::test_mpc_protects_critical_when_fuel_is_short`: under an overcast spell, the fuel is enough for critical load but not for all load. There B runs dry and leaves critical load unserved, while C sheds flexible load and serves all critical load.

## Run time

On the cloud container, C takes 0.25 to 0.5 s per hourly step (PuLP model build plus the HiGHS solve), so a full year is about 40 to 75 min. A and B run in seconds. Phase 4 should run its scenarios in parallel processes.

## Assumptions used by the twin

Every value is in `data/itbayat/site.yaml`, with its range listed in `SOURCES.md`. New in Phase 3:

| Key | Value | Why it is needed |
|---|---|---|
| `diesel_units_available` | 3 | INL: 4 units, one out of service (computed) |
| `diesel_unit_kw_assumed` | 186.7 kW | Unit ratings are missing; 560 kW split equally |
| `diesel_min_loading_frac` | 0.30 | (Phase 1) |
| `diesel_fuel_noload_l_per_h_per_kw`, `diesel_fuel_slope_l_per_kwh` | 0.04, 0.22 | Linear fuel curve; 0.277 L/kWh at 70 % load |
| `diesel_start_cost_php` | 300 PHP | Stops unit cycling in the MPC |
| `co2_kg_per_l` | 2.68 | IPCC 2006 defaults × 0.84 kg/L density [verify table pages] |
| `co2_shadow_price_php_per_t` | 2,800 PHP/t | Emissions term (design weight, no Philippine carbon price) |
| `fuel_storage_l_assumed` | 60,000 L | Tank volume is missing; 2 months × 991 L/day |
| `resupply_interval_days_assumed` | 30 d | Resupply interval is missing |
| `overdue_resupply_days_assumed` | 7 d | MPC belief about an overdue tanker |
| `battery_kw_case` | 375 kW | Team case battery power |
| `battery_eta_oneway`, `battery_soc_min/max/initial` | 0.95, 0.20/0.95/0.60 | Battery model |
| `battery_degradation_php_per_kwh` | 4.0 PHP/kWh | Throughput wear cost |
| `voll_flex_php_per_kwh` | 150 PHP/kWh | Flexible shedding penalty |
| `risk_penalty_php_per_kwh`, `risk_window_h` | 50 PHP/kWh, 24 h | Risk term |
| `fuel_scarcity_penalty_php_per_kwh` | 500 PHP/kWh | Fuel autonomy term |
| `php_per_usd` | 56 | Team case exchange rate |

Fixed model settings in code: 48 h horizon, 64 scenarios in 16 groups, AR(1) correlations of 0.9 (solar) and 0.95 (demand), CEST cap of 72 h, 0.5 % MIP gap.

## Limitations

- The load is synthetic. The weather truth is reanalysis, and PV comes from a model with an assumed array. There are no field data yet.
- Diesel unit ratings, tank volume and resupply interval are assumptions until NPC-SPUG figures arrive.
- The plant model has no spinning-reserve rule, no ramp limits and no battery ageing over the run (only a wear cost).
- The demonstration uses the twin's persistence baseline, not the Phase 2 forecast.
