# Cloud session brief: AURORA solo, Itbayat

Start each Claude Code cloud session on `Malmand/aurora_solo` with:

> Read `CLAUDE.md` and `docs/CLOUD_BRIEF.md`, then do Phase N. Follow every rule in `CLAUDE.md`.

The phases are sized so each can be one session. Run them in order: 1, then 2 and 3 in parallel, then 4, then 5. Phase 6 is optional.

Deadlines: team decides the site by 4 Nov 2026; full deck draft 15 Nov; submission 20 Nov (hard deadline 22 Nov).

---

## Context

AURORA is a forecast-driven, resilience-aware energy management layer for remote diesel-backed solar microgrids (Global Sustainability Challenge 2026-27, Sustainable Energy theme). Its headline metric is the **Community Energy Survival Time (CEST)**: hours that critical loads (clinic, water pumping, telecoms) can run on battery plus forecast P10 solar if diesel stopped now, until SOC hits a 30 % reserve.

Case study: **Itbayat, Batanes, Philippines** (lat 20.78, lon 121.84). About 3,100 people, NPC-SPUG diesel-only grid, fuel by sea. Typhoons stopped fuel deliveries in Sep 2022 and Jun 2023 (Typhoon Betty / Mawar).

The team repo `aurora-gsc/aurora-digital-twin` already has:
- `digital_twin/` (main): hourly dispatch loop, CEST, forecast loader. Mohamed's code, may be ported.
- branch `digital-twin-case-study`: `case_batanes.py`, synthetic Itbayat year, typhoon stress test, cost model, figures, operator-screen and user-journey mock-ups. Mohamed's code, may be ported.
- `forecasting/`: Katharina's day-ahead GHI corrector (HistGradientBoosting on ECMWF IFS day-1 forecasts vs ERA5, Bologna). **Ideas only, no code copying.**

### Known problems to fix (do not carry them over silently)
1. **Diesel price.** Case study assumes 65 PHP/L. The INL report gives about 113 PHP/L. Use 113 as base, 65 and 140 as sensitivity.
2. **Diesel plant.** DOE off-grid list (2021) says 1.086 MW installed / 0.79 MW dependable. INL (Jan 2025) says four units, 660 kW combined, one 100 kW unit out of service. Use INL as current state, record both.
3. **System size.** Case study uses 500 kWp PV / 1.5 MWh battery (illustrative). INL proposes 300 kW PV and 300 kW / 300 kWh battery. Run both and say which one the headline numbers use.
4. **Synthetic weather.** Case study weather is clear-sky x PAGASA cloud normals. Replace with real hourly reanalysis.
5. **Katharina's corrector is worse than raw NWP** on its own test set (MAE 21.4 vs 18.4 W/m2, all hours). A forecast that loses to its input cannot be shown to judges. Ours must beat raw NWP and persistence, reported as skill scores.
6. **Point forecast only.** CEST and the risk term need P10/P50/P90. Calibrated bands are required.
7. **Day-ahead only.** The MPC horizon is 24 to 48 h, so the forecast must cover lead times out to 48 h.

---

## Phase 1: Site data and validation (`data/itbayat/`)

Build the single source of truth for the site.

- `SOURCES.md` and `site.yaml`: population, diesel units and ratings, peak demand (about 250 kW, peaks May to July, +12 % since 2021), fuel price, fuel storage and resupply interval (INL: proposed system extends supply from about 2 to about 3 months), critical loads, distribution voltage. One row per value: value, unit, source, date, confidence.
- Sources to read and extract from (all listed in the team update):
  - INL report: Davis, R. Z. (2025), *Enhancing Power Resilience for Remote Communities ... Itbayat Island*, INL/RPT-25-83061, https://www.osti.gov/servlets/purl/3014068
  - DOE off-grid plant list: https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/05a_lvm_off-grid_loepp-09302022.pdf
  - PhilAtlas census: https://www.philatlas.com/luzon/r02/batanes/itbayat.html
  - PAGASA Basco climatological normals 1991-2020: https://pubfiles.pagasa.dost.gov.ph/pagasaweb/files/cad/CLIMATOLOGICAL%20NORMALS%20(1991-2020)/BASCO%20RADAR.pdf
  - Ocon and Bertheau (2019), J. Sustain. Dev. Energy Water Environ. Syst.: https://www.sdewes.org/jsdewes/pid6.0230
  - Tsai et al. (2020), Energies 13(1), 8: https://www.mdpi.com/1996-1073/13/1/8
  - Castro, Pascasio and Ocon (2022), Energy 257, 124599, and its CC BY 4.0 dataset doi:10.17632/cg5z25rj8y.1 (634 Philippine off-grid islands; check for an Itbayat row: peak load, diesel units, optimal sizing)
  - Event evidence (news, for the problem slide only): Manila Bulletin Sep 2022, Rappler Jun 2023, GMA Apr 2026, Philstar May 2026, Asia Business Outlook Mar 2025, Yale Clean Energy Forum policy memo Jan 2026.
- Weather: hourly Open-Meteo ERA5 for the site, 2015 to present (GHI, DNI, DHI, temperature, wind, cloud cover, pressure). Save as parquet.
- Typhoons: IBTrACS West Pacific tracks; flag every hour with a storm centre within 300 km and 500 km of Itbayat; list named events, especially Sep 2022 and late May / early Jun 2023.
- **Validation report** `docs/validation_site.md`: ERA5 monthly GHI and temperature vs PAGASA Basco normals and vs the solar resource in Tsai et al. (2020); annual PV yield vs any figure in Castro et al. (2022). Table plus one figure, with % differences and a one-line verdict each.
- Load: no hourly measured data exists publicly. Build a synthetic hourly load scaled to the INL 250 kW peak with May to July seasonality, temperature sensitivity and an evening peak; split critical (clinic, water, telecoms, municipal, cold storage) and flexible. Label it synthetic. Provide a `--load` path so real plant logs drop in.

Done when: `python -m aurora.data.build_itbayat` rebuilds everything, the validation report exists, and every site number has a source or `ASSUMPTION`.

## Phase 2: Forecasting module (`aurora/forecast/`), written from scratch

Same idea as the team prototype (correct NWP with ML), made accurate, probabilistic and useful for dispatch.

**Inputs.** Open-Meteo previous-runs API, lead days 1 and 2, from several NWP models: ECMWF IFS, GFS, ICON, JMA (strong over East Asia). Add ensemble spread (ECMWF ENS / GEFS via the ensemble API) as an uncertainty feature if available. Variables: GHI, cloud cover (low/mid/high), temperature, humidity, precipitation, pressure, wind and gusts.

**Target.** Clear-sky index k = GHI / GHI_clear (pvlib Ineichen with Linke turbidity), daylight hours only. This removes the daily cycle so errors are not hidden by night-time zeros. Convert back to GHI, then to PV kW with pvlib for the chosen array (tilt, azimuth, temperature model, inverter).

**Truth.** ERA5 is a reanalysis, not a sensor. Use a satellite-derived product as the main reference where available (Open-Meteo satellite radiation API, NASA POWER hourly, or CAMS), cross-check with ERA5, and say in the README which one is the reference and why. Never call any of these "measured".

**Model.** LightGBM quantile regression for P10/P50/P90 per lead time, then split-conformal calibration by lead day and season so the 80 % band really covers about 80 %. Monotone quantiles (sort or fix crossings).

**Typhoon awareness.** Add storm-proximity features from the NWP fields (pressure drop, gusts) and evaluate separately on IBTrACS-flagged hours.

**Fallback.** If the live NWP request fails (comms are often down in a typhoon), fall back to climatology-conditioned persistence with widened bands and set a `fallback=True` flag in the output.

**Evaluation** (`docs/validation_forecast.md`), rolling-origin backtest over at least 12 months, daylight hours:
- Baselines: raw NWP (each model and their mean), smart persistence, climatology.
- Point: MAE, RMSE, bias, skill score vs raw NWP and vs smart persistence.
- Probabilistic: pinball loss, CRPS, PICP for the 80 % band, mean band width.
- Split by lead day, season, and typhoon vs normal hours.
- Must beat raw NWP and smart persistence on RMSE and CRPS. If it does not, report honestly and fix before Phase 4.

**Demand forecast.** Quantile model on temperature, hour, weekday and season, trained on the Phase 1 synthetic load, ready for real logs. Clearly labelled.

**Output.** One CSV per issue time, 48 h ahead, matching the digital twin schema plus bands: `issue_time, timestamp, solar_kW_p10, solar_kW_p50, solar_kW_p90, demand_critical_kW_p10..p90, demand_flex_kW_p10..p90, fallback`.

Figures: skill by lead time; reliability (PICP) diagram; one typhoon week with bands vs truth.

## Phase 3: Digital twin with MILP rolling-horizon MPC (`aurora/twin/`)

- Port the dispatch loop, CEST and forecast loader from the team repo; port `case_batanes.py` logic and fix the known problems above.
- `mpc.py`: the proposal's MILP in Pyomo or PuLP with HiGHS. Power balance, SOC dynamics with charge/discharge efficiencies, SOC bounds, diesel on/off binary with minimum loading, hard constraint that critical load is never shed, objective = fuel + emissions + battery degradation + risk + shed penalty. Horizon 48 h, hourly, apply first step, re-solve.
- Risk term: 50 to 100 Monte Carlo scenarios drawn from the forecast quantiles (interpolate a CDF from P10/P50/P90), R(t) = probability of critical shortfall. CEST computed on the P10 trajectory with diesel off at every step.
- Fuel stock as a state: tank level, resupply events, and delayed resupply in stress tests.
- Keep three controllers: A diesel only, B simple rule, C AURORA MPC. Unit tests for energy balance closure, SOC bounds, and "critical unserved = 0 whenever physically possible".

## Phase 4: Results (`aurora/experiments/`)

All with real ERA5 weather and the Phase 2 backtest forecasts.

1. Full-year runs for A, B, C at INL sizing (300 kWp / 300 kWh) and at 500 kWp / 1.5 MWh.
2. Real typhoon weeks from IBTrACS (at least Sep 2022 and the Betty event in 2023) with fuel resupply delayed 3, 7 and 14 days.
3. **Value of forecasting**: rerun C with perfect forecasts, AURORA forecasts, raw NWP, and persistence. Report diesel, critical outage hours and CEST for each. This is the proof that the forecast is useful, not just accurate.
4. Sizing sweep: PV 0 to 600 kWp, battery 0 to 2 MWh. Where does extra battery stop adding CEST, for B and C?
5. Sensitivity: diesel price 65 / 113 / 140 PHP/L, battery at 80 % capacity, load +12 %.
6. Costs: capex, annual fuel saving, simple payback, using sourced or clearly assumed unit costs.

Per run report: diesel litres and cost, CO2, renewable share, critical outage hours, battery throughput, CEST (median, min, % of hours above 12 h and 24 h).

## Phase 5: Deck-ready outputs

- Figures in `figures/` (CLAUDE.md style): site and system overview; typhoon-week dispatch A vs B vs C with fuel tank level; CEST over time; value-of-forecast bar chart; sizing sweep; forecast skill and reliability.
- `docs/results_summary.md`: one page, plain words, three big numbers for the impact slide, all sourced to a script and a CSV.
- `docs/slide_content.md`: text and figure choice for each of the 9 slides (Title, Summary, Problem, Idea, What's new, Plan, Impact, Growth, Extras), matching the GSC template, plus a 2-minute video script.
- README with quick start, results table, honest limitations (synthetic load, reanalysis truth, no field data yet).

Done when: `make all` (or `python -m aurora.run_all`) rebuilds every figure and table from committed data, `pytest` passes, and the PR summary lists every assumption.

## Phase 6 (optional): Operator screen

A Streamlit app (`app/`) replaying a typhoon week hour by hour: CEST gauge, forecast bands, battery and fuel tank levels, AURORA's recommended action with a one-line reason ("Charging battery from diesel now: low sun forecast for 36 h, CEST would fall below 12 h"). Record a short screen capture for the video.
