# AURORA solo

Forecast-driven, resilience-aware energy management for remote diesel-backed solar microgrids, applied to **Itbayat island, Batanes, Philippines**.

AURORA asks one question a community operator can act on: **if diesel stopped arriving now, how long could the clinic, water and phones keep running?** That is the Community Energy Survival Time (CEST).

This is Mohamed Al-Mandhari's individual development repository for the AURORA project (Global Sustainability Challenge 2026-27). The team repository is [aurora-gsc/aurora-digital-twin](https://github.com/aurora-gsc/aurora-digital-twin).

## Plan

| Phase | What | Status |
|---|---|---|
| 1 | Itbayat site data, weather, typhoon tracks, validation | Done: inputs in `data/itbayat/raw_small/`, 18 site values verified, 4 still missing (see `SOURCES.md`) |
| 2 | Probabilistic solar and demand forecast (P10/P50/P90, 48 h) | Done: beats every raw NWP model and smart persistence on RMSE and CRPS over a 24-month backtest; see [`docs/validation_forecast.md`](docs/validation_forecast.md) |
| 3 | Digital twin with MILP rolling-horizon MPC and CEST | Done: `aurora/twin/`, controllers A/B/C, fuel tank, Monte Carlo risk, demo on typhoon Mawar 2023 ([`docs/twin.md`](docs/twin.md)) |
| 4 | Year runs, real typhoon weeks, value of forecasting, sizing | Planned |
| 5 | Figures, results summary, slide and video content | Planned |
| 6 | Operator screen (optional) | Planned |

Details: [`docs/CLOUD_BRIEF.md`](docs/CLOUD_BRIEF.md).

## Quick start

```bash
pip install -e ".[dev,download]"
python scripts/download_itbayat.py           # all external inputs -> data/itbayat/raw_small/ (run locally)
python scripts/download_itbayat.py --source cds   # same, with ERA5 from the Copernicus CDS (~/.cdsapirc)
python -m aurora.data.build_itbayat          # rebuild all Phase 1 site data from raw_small/ (no network)
python -m aurora.data.build_itbayat --load plant_log.csv   # use real plant logs instead of the synthetic load
python -m aurora.forecast.build              # Phase 2 backtest, report, figures, models (~15 min, no network)
python -m aurora.forecast.issue --issue 2025-07-17T16:00Z      # one 48 h forecast CSV
python -m aurora.forecast.issue --issue 2025-07-17T16:00Z --no-nwp   # comms-loss fallback
python -m aurora.twin.run --demo             # digital twin: A/B/C on the Mawar (Betty) 2023 window -> results/twin/
python -m aurora.twin.run --horizon-compare  # MPC horizon: issue-aligned (default) vs fixed 48 h
python -m aurora.twin.run --controllers C --sizing case --start 2025-07-15 --days 7 --forecast phase2   # twin on the Phase 2 backtest forecasts
pytest
```

Phase 1 outputs live in [`data/itbayat/`](data/itbayat/): `site.yaml` and `SOURCES.md` (every site number with its source and status), the downloaded inputs in `raw_small/` (ERA5, satellite radiation, NASA POWER, IBTrACS, and previous-run NWP forecasts for Phase 2), IBTrACS typhoon flags and events, and the **synthetic** hourly load. The validation report is [`docs/validation_site.md`](docs/validation_site.md).

The digital twin is described in [`docs/twin.md`](docs/twin.md): plant and fuel-tank model, the MILP (PuLP + HiGHS), the risk term R(t), CEST, and every assumption it uses.

None of the weather products is a measurement. ERA5 is a reanalysis; the satellite and NASA POWER series are retrievals. The load is synthetic until plant logs are available.

## Phase 2: forecasts (`aurora/forecast/`)

Written from scratch. Daily issue at 00:00 PHT (16:00 UTC), 48 h ahead, hourly.

- **Target**: clear-sky index k = GHI / GHI_clear (pvlib Ineichen, Linke turbidity), daylight hours. Converted back to GHI, split into DNI/DHI (Erbs), then to PV kW with the shared array model `aurora/data/pvmodel.py`, the same one the twin uses (array settings are ASSUMPTIONs).
- **Inputs**: Open-Meteo previous-runs NWP (ECMWF IFS, GFS, ICON with GHI; JMA without), lead day 1 from the run about a day before the target hour, lead day 2 from two days before. All inputs existed at issue time. Persistence features from the reference product. Storm features: NWP minimum pressure, pressure anomaly and 24 h tendency, gusts.
- **Reference ("truth")**: Open-Meteo satellite radiation (0.05°). It observes the island's clouds; ERA5 (0.25°) models them, so ERA5 is the cross-check. Neither is a measurement.
- **Model**: LightGBM quantile regression (19 levels, so CRPS is computable), one model per lead day, refit monthly; split-conformal shift per lead day and season; crossing quantiles sorted.
- **Fallback**: no NWP (comms down) gives climatology-conditioned persistence with bands widened 25 % and `fallback=True`.
- **Demand**: quantile model on hour, weekday, season, forecast temperature and yesterday's load. **Trained on the synthetic Phase 1 load**; it retrains unchanged on real logs.

Backtest, Nov 2024 to Oct 2026 (24 months, rolling origin, satellite reference, daylight hours):

| Lead day | RMSE AURORA | RMSE ECMWF (best raw) | RMSE NWP mean | RMSE persistence | CRPS AURORA | CRPS ECMWF | P10-P90 coverage |
|---|---|---|---|---|---|---|---|
| 1 | 80.6 W/m² | 90.8 | 95.2 | 150.0 | 37.2 | 56.4 | 81.7 % |
| 2 | 92.6 W/m² | 101.3 | 103.8 | 174.3 | 43.3 | 64.4 | 81.7 % |

The twin reads these directly: `python -m aurora.twin.run --forecast phase2` (or `phase2:nwp`, `phase2:persistence` for value-of-forecasting runs). Outputs for Phases 3 and 4: `data/itbayat/forecast/backtest_solar.parquet` (GHI and PV kW-per-kWp bands, raw NWP mean, persistence, reference, 2022 to Oct 2026), `backtest_demand.parquet`, and sample CSVs in `data/itbayat/forecast/issues/` in the digital-twin schema (`issue_time, timestamp, solar_kW_p10..p90, demand_critical_kW_p10..p90, demand_flex_kW_p10..p90, fallback`).

Limits: before Feb 2024 there is no archived NWP GHI, so 2022 to 2023 (including the Sep 2022 and Jun 2023 typhoons) use a reduced JMA-plus-persistence model, and 2022 is predicted by a model trained on 2023 (out of sample, not causal; flagged `reduced_reverse`). Typhoon-hour scores rest on a few storms. Ensemble-spread inputs (ECMWF ENS, GEFS) are not in `raw_small/` yet.
