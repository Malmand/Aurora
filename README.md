# AURORA solo

Forecast-driven, resilience-aware energy management for remote diesel-backed solar microgrids, applied to **Itbayat island, Batanes, Philippines**.

AURORA asks one question a community operator can act on: **if diesel stopped arriving now, how long could the clinic, water and phones keep running?** That is the Community Energy Survival Time (CEST).

This is Mohamed Al-Mandhari's individual development repository for the AURORA project (Global Sustainability Challenge 2026-27). The team repository is [aurora-gsc/aurora-digital-twin](https://github.com/aurora-gsc/aurora-digital-twin).

## Plan

| Phase | What | Status |
|---|---|---|
| 1 | Itbayat site data, weather, typhoon tracks, validation | In progress: pipeline done; ERA5 download and document checks pending |
| 2 | Probabilistic solar and demand forecast (P10/P50/P90, 48 h) | Planned |
| 3 | Digital twin with MILP rolling-horizon MPC and CEST | Planned |
| 4 | Year runs, real typhoon weeks, value of forecasting, sizing | Planned |
| 5 | Figures, results summary, slide and video content | Planned |
| 6 | Operator screen (optional) | Planned |

Details: [`docs/CLOUD_BRIEF.md`](docs/CLOUD_BRIEF.md).

## Quick start

```bash
pip install -e ".[dev]"
python -m aurora.data.build_itbayat          # rebuild all Phase 1 site data
python -m aurora.data.build_itbayat --load plant_log.csv   # use real plant logs instead of the synthetic load
pytest
```

Phase 1 outputs live in [`data/itbayat/`](data/itbayat/): `site.yaml` and `SOURCES.md` (every site number with its source and status), hourly weather parquet files (ERA5, satellite, NASA POWER), IBTrACS typhoon flags and events, and the **synthetic** hourly load. The validation report is [`docs/validation_site.md`](docs/validation_site.md).

None of the weather products is a measurement. ERA5 is a reanalysis; the satellite and NASA POWER series are retrievals. The load is synthetic until plant logs are available.
