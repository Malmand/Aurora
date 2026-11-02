# AURORA solo

Forecast-driven, resilience-aware energy management for remote diesel-backed solar microgrids, applied to **Itbayat island, Batanes, Philippines**.

AURORA asks one question a community operator can act on: **if diesel stopped arriving now, how long could the clinic, water and phones keep running?** That is the Community Energy Survival Time (CEST).

This is Mohamed Al-Mandhari's individual development repository for the AURORA project (Global Sustainability Challenge 2026-27). The team repository is [aurora-gsc/aurora-digital-twin](https://github.com/aurora-gsc/aurora-digital-twin).

## Plan

| Phase | What | Status |
|---|---|---|
| 1 | Itbayat site data, weather, typhoon tracks, validation | Done: inputs in `data/itbayat/raw_small/`, 18 site values verified, 4 still missing (see `SOURCES.md`) |
| 2 | Probabilistic solar and demand forecast (P10/P50/P90, 48 h) | Next: NWP inputs downloaded (ECMWF from Feb 2024; GFS, ICON, JMA from 2022) |
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
python -m aurora.twin.run --demo             # digital twin: A/B/C on the Mawar (Betty) 2023 window -> results/twin/
python -m aurora.twin.run --controllers C --sizing case --start 2023-05-27 --days 10 --forecast csv:forecasts/   # Phase 2 forecast files
pytest
```

Phase 1 outputs live in [`data/itbayat/`](data/itbayat/): `site.yaml` and `SOURCES.md` (every site number with its source and status), the downloaded inputs in `raw_small/` (ERA5, satellite radiation, NASA POWER, IBTrACS, and previous-run NWP forecasts for Phase 2), IBTrACS typhoon flags and events, and the **synthetic** hourly load. The validation report is [`docs/validation_site.md`](docs/validation_site.md).

The digital twin is described in [`docs/twin.md`](docs/twin.md): plant and fuel-tank model, the MILP (PuLP + HiGHS), the risk term R(t), CEST, and every assumption it uses.

None of the weather products is a measurement. ERA5 is a reanalysis; the satellite and NASA POWER series are retrievals. The load is synthetic until plant logs are available.
