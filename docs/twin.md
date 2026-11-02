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

min Σ_t [c_f F_t + c_deg (P_c,t + P_x,t) + c_shed (1 − 0.001 t/H) L_t + c_st s_t] + (c_risk / (H Q)) Σ_t Σ_q z_q,t + c_sc Σ_k π_k (u_k / sfc_min + w_k) − v_e e_H

c_f is the diesel price plus the CO2 shadow cost per litre. P_c and P_x are battery charge and discharge. L is the flexible load shed, s counts unit starts, e is battery energy, z is the risk shortfall and u_k, w_k are the fuel shortfalls of delivery scenario k with probability π_k (both defined below), and v_e values the energy left in the battery at the horizon end at the diesel energy it displaces.

The constraints:

- **Power balance.** PV − curtailment + P_d + P_x − P_c = D_crit + D_flex − L. There is no slack on critical load, so it is a hard constraint.
- **Battery.** e_t+1 = e_t + η P_c − P_x / η, with E soc_min ≤ e ≤ E soc_max.
- **Diesel.** n_t P_u m ≤ P_d ≤ n_t P_u, where n_t is an integer from 0 to 3 and m is the minimum load. Starts satisfy s_t ≥ n_t − n_t−1.
- **Fuel, per delivery scenario k.** V_k,t+1 = V_k,t − F_t, reset to capacity at scenario k's arrival. V_k may go negative in the plan (fuel "borrowed"); u_k ≥ −V_k,t and u_k ≥ 0 measure the largest deficit. The plant enforces the real tank.
- **Risk.** z_q,t ≥ N_q,t − (e_t − E soc_cest), with z ≥ 0.
- **Fuel autonomy.** w_k ≥ C_need,k − (V_k,H + u_k) / sfc_min − (e_H − E soc_cest), with w_k ≥ 0.

If the hard model is infeasible (diesel and battery cannot physically carry critical load), C solves it again with a critical slack at 1e5 PHP/kWh and flags the step `relaxed`. A binary that forbids simultaneous charge and discharge is available (`exclusive_battery=True`). It is off by default: with losses, a degradation cost and free curtailment, the solver never chooses both at once, and the objective came out identical in a benchmark. The relative MIP gap is 0.5 %.

### Risk term and R(t) (`scenarios.py`)

The twin draws 64 Monte Carlo scenarios of solar and critical demand from the forecast quantiles. Each hour's CDF is piecewise linear through P10, P50 and P90 and extended linearly to the tails. A Gaussian copula with AR(1) correlation of 0.9 for solar and 0.95 for demand links the hours, so a cloudy morning tends to stay cloudy. For each scenario and start hour, a backward recursion gives the battery energy above the reserve that critical load needs to survive the next 24 h with diesel off. The scenarios are then sorted into 16 equal quantile groups, giving N_q,t.

- In the MILP, z is the expected shortfall of stored energy against N, a linear surrogate for the shortfall probability.
- In the output, **R(t)** is the share of scenarios in which the battery at the start of step t cannot carry critical load through the 24 h window if diesel stopped then.

### Fuel autonomy under an uncertain tanker delay

Deliveries that are not yet due are taken as on time. Once a tanker is overdue, its total delay is uncertain: 3, 7 or 14 days after the planned time, with weights 0.5, 0.3 and 0.2 (`overdue_delay_scenarios_days`, `overdue_delay_weights`, both ASSUMPTION). Every hour, the scenarios whose arrival time has already passed are dropped and the remaining weights renormalised. After 3 days without the tanker the belief is 0.6 (7 days) and 0.4 (14 days); after 7 days it is the 14-day scenario alone. If all three pass, the MPC assumes the tanker is 7 days away, re-estimated every hour (`overdue_resupply_days_assumed`).

C_need,k is the critical deficit (P90 critical minus P10 solar, last forecast day repeated) from the horizon end to scenario k's next delivery. It is zero when that delivery falls inside the horizon. Shedding 1 kWh of flexible load saves about 1 kWh of diesel in every scenario, so it pays only when 500 PHP/kWh × P(fuel shortfall) is above the 150 PHP/kWh shedding penalty, that is when the probability of a shortfall is above 0.3. With the base weights, a delay that only the 14-day scenario cannot cover (P = 0.2) leads to no shedding until the 3-day scenario has passed. Among equally good plans, shedding is made slightly cheaper later in the horizon, so the MPC defers it while the tanker may still come. The tests check both the belief update and the threshold.

## CEST (`cest.py`)

CEST counts the hours that critical load can run on the battery plus forecast P10 solar, with diesel and flexible load off, before SOC reaches the 30 % reserve. Critical demand is taken at P90. Beyond the 48 h forecast, the last 24 h are repeated, and values above 72 h are reported as 72 h (censored). The battery's power limits apply to both charge and discharge. All controllers are scored with the same forecast, so their CEST values are comparable. Controller A has no battery, so its CEST is 0 by definition.

## Forecast providers (`forecasts.py`)

- `PerfectForecast`: truth with zero spread. This is the upper bound for the value-of-forecasting runs.
- `PersistenceForecast`: the twin's own baseline, used until Phase 2 lands. P50 is daily smart persistence of the clear-sky index (PV over the last 24 h divided by clear-sky PV). P10 and P90 come from the daily clear-sky index of the last 30 days. Load uses the same hour of the last observed day, with ±2 % bands on critical and ±10 % on flexible. It uses only data from before the issue time.
- `CSVForecast(folder)`: reads the Phase 2 output files, one CSV per issue time. At each step it uses the newest issue at or before that step. Any hours that issue does not cover come from persistence with 1.5× wider bands and `fallback=True`, which also covers the case where comms are down.

## Demonstration: typhoon Mawar (Betty), late May 2023

`python -m aurora.twin.run --demo`. The windows start on 27 May 2023, 00:00 PHT, with ERA5 weather and the synthetic load. Mawar passed 329 km from Itbayat on 30 May. The forecast is the twin's persistence baseline. Stress assumption: the tank holds 6,000 L (10 %) when the tanker due on 28 May is delayed. Two delays are run: 7 days (tanker arrives 4 June, window 11 days) and 14 days (tanker arrives 11 June, window 18 days). Each window ends 3 days after the arrival. Phase 4 runs the full set (Sep 2022 and Betty, delays of 3, 7 and 14 days, value of forecasting).

| Delay | Sizing | Ctl | Critical outage (h) | Critical unserved (kWh) | Flex shed (kWh) | Diesel (L) | CEST median (h) | CEST ≥ 12 h (%) | Mean R | Tank min (L) |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 d | inl | A | 49 | 2,419 | 4,984 | 8,975 | 0.0 | 0.0 | 1.00 | 0 |
| 7 d | inl | B | 0 | 0 | 0 | 7,387 | 0.0 | 0.4 | 0.89 | 437 |
| 7 d | inl | C | 0 | 0 | 3,013 | 6,265 | 4.9 | 18.9 | 0.73 | 1,491 |
| 7 d | case | A | 49 | 2,419 | 4,984 | 8,975 | 0.0 | 0.0 | 1.00 | 0 |
| 7 d | case | B | 0 | 0 | 0 | 4,588 | 0.0 | 28.8 | 0.55 | 2,425 |
| 7 d | case | C | 0 | 0 | 0 | 4,680 | 72.0 | 86.0 | 0.07 | 2,307 |
| 14 d | inl | A | 217 | 10,763 | 21,861 | 8,948 | 0.0 | 0.0 | 1.00 | 0 |
| 14 d | inl | B | 89 | 3,104 | 10,488 | 8,446 | 0.0 | 0.2 | 0.90 | 0 |
| 14 d | inl | C | 0 | 0 | 12,673 | 8,386 | 4.8 | 13.7 | 0.77 | 0 |
| 14 d | case | A | 217 | 10,763 | 21,861 | 8,948 | 0.0 | 0.0 | 1.00 | 0 |
| 14 d | case | B | 2 | 70 | 356 | 8,088 | 0.0 | 26.6 | 0.57 | 0 |
| 14 d | case | C | 0 | 0 | 0 | 8,063 | 72.0 | 84.3 | 0.07 | 16 |

Source: `results/twin/demo_mawar2023_kpis.csv`. The hourly runs are in `results/twin/demo_mawar2023_delay{7,14}d_{inl,case}/run_{A,B,C}.csv`. A has no PV or battery, so its row is the same for both sizings.

What this shows, and what it does not:

- **Diesel only runs dry.** A runs out of fuel about 6 days into the delay. That means 49 h of critical outage with a 7-day delay and 217 h with a 14-day delay.
- **B loses critical load when the delay is long.** With the 14-day delay, B empties the tank and loses critical load for 89 h at INL sizing and 2 h at case sizing. C serves all critical load in both cases, from the same fuel.
- **INL sizing, 7-day delay.** C sheds no flexible load for the first 3 days of the delay (previously it shed from the first day). It starts on 31 May, when the 3-day scenario has passed and the belief is 0.4 for a 14-day delay, because 0.4 × 500 > 150 PHP/kWh. The tanker then arrived on day 7, so in hindsight the 3,013 kWh shed was insurance that was not needed. This is the price of the hedge that keeps critical load served in the 14-day run. The trade-off is set by the delay weights and the two penalties, which Phase 4 should sweep. C also uses 15 % less diesel than B here.
- **INL sizing, 14-day delay.** C sheds more flexible load than B (12,673 vs 10,488 kWh) but trades 89 h of critical outage for none. The tank reaches 0 L just before the tanker arrives.
- **Case sizing.** The larger battery and PV carry both delays without shedding. Fuel is about the same for B and C (+2 % at 7 days, −0.3 % at 14 days). C keeps the battery charged, so median CEST is 72 h (censored) against 0 h for B, and mean R is 0.07 against 0.55 to 0.57.
- With a 300 kWh battery, CEST stays short (median about 5 h for C), because 195 kWh above the reserve covers about 5 h of critical load at night (35 kW) and less in the evening (49 to 65 kW).
- This is one storm, one assumed tank level and the persistence forecast. These numbers show the twin works. They are not the headline results, which come from Phase 4.

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
| `overdue_delay_scenarios_days`, `overdue_delay_weights` | 3/7/14 d, 0.5/0.3/0.2 | Belief about an overdue tanker's total delay |
| `overdue_resupply_days_assumed` | 7 d | Fallback once all delay scenarios have passed |
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
