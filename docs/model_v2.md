# Model v2 (Phase 4b): making the twin less optimistic

Phase 4 (model v1) showed AURORA keeping the clinic powered through a 14-day fuel delay where a simple rule failed. Five shortcuts made that comparison too kind to AURORA. Model v2 removes them. Every new number is an `ASSUMPTION` in `data/itbayat/site.yaml`, with a range.

| # | Shortcut in model v1 | Model v2 | Where |
|---|---|---|---|
| 1 | The only alternative to AURORA was a simple rule that never rations fuel. Real operators do: NPC and BATANELCO ran power curtailment in Sep 2022 and 2023. | New baseline **O, the rationing operator**: the simple rule plus rotating brownouts once the tanker is overdue, sized from the fuel gauge and the last 24 h of meter readings so the fuel lasts until the latest plausible arrival (14 days late). No forecast. | `aurora/twin/controllers.py` `RationingOperator` |
| 2 | Household load was cut by the exact kW. | Household load is cut in **whole feeder blocks** (4). AURORA's planned cut is rounded up to whole blocks. | `aurora/twin/plant.py` `step` |
| 3 | Critical demand was a fixed schedule known exactly. | Critical demand **varies** around the schedule (AR(1), SD 12 %); AURORA's forecast carries matching bands. | `aurora/twin/inputs.py`, `forecasts.CriticalBand` |
| 4 | AURORA's plan could run the tank to almost zero (12.7 L in one run, too little to start a generator). | AURORA keeps a **250 L reserve**. | `aurora/twin/mpc.py` |
| 5 | The system size was chosen on typhoon Mawar alone, then tested on it. | The size is chosen on **all three storms**. | `aurora/experiments/phase4b.py` `recommended` |

## Stress tests (chosen size, tanker 14 days late, all three storms)

| Test | What happens |
|---|---|
| `gen_fail` | Only one of the three working diesel units is available for the whole event. |
| `pv_damage` | Solar output halves from the storm's closest approach on (the operator and forecast see it). |
| `comms_down` | No weather forecast: AURORA runs on the backup persistence forecast for the whole event. |
| `clinic_shared` | The clinic shares the last household feeder, so cutting all homes also cuts the clinic. |

## Run

```bash
pip install -e ".[dev]"
python -m aurora.experiments.phase4b run --stage A --workers 8   # sweep on 3 storms + INL-size storms
python -m aurora.experiments.phase4b run --stage B --workers 8   # chosen size: storms, 2 years, stress, forecast value
python -m aurora.experiments.phase4b tables                      # results/phase4b/tables.md, impact.json
python -m aurora.plotting.slides impact                  # figures/slides/impact.png
```

Both stages resume where they stopped. Model v1 outputs are not kept in the repository; rerun `python -m aurora.experiments.phase4` to rebuild them.

## Limits that remain

Synthetic demand, ERA5 reanalysis weather, no field data, assumed tank size and delivery interval. Storm damage to lines and generators beyond the stress tests is not modelled. CEST is capped at 72 h.
