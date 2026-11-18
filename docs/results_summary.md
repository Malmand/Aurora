# AURORA on Itbayat: results in one page

Itbayat, in Batanes, has about 3,100 people (PhilAtlas) and a diesel-only power grid. All its fuel comes by sea. When typhoons or monsoon seas stop the tanker, the island can run out of diesel: this happened in 2009, 2011, 2022, twice in 2023, 2025 and 2026 (news reports, listed in `data/itbayat/SOURCES.md`).

AURORA is a control layer for an island grid with solar panels, a battery and diesel generators. Every hour it reads a 48-hour forecast of sun and demand, plans the next two days, and keeps a figure in view that an operator can act on: **Community Energy Survival Time (CEST)**, the hours the clinic, water pumps and phones could keep running on battery and sun alone if diesel stopped now.

We tested three ways of running the island in a computer model of Itbayat with real weather (2023 to 2026):
**A** diesel only (today), **B** solar and battery with a simple rule, **C** solar and battery run by AURORA.
The system size is 500 kWp of solar and a 1,000 kWh battery, chosen as the cheapest size that kept critical services running in our test.

## Three numbers

| | Number | What it means | Source |
|---|---|---|---|
| 1 | **217 h → 0 h** | In typhoon Mawar (2023) with the tanker 14 days late, the clinic, water and phones lose power for 217 hours with diesel only, 15 hours with solar and battery on a simple rule, and **0 hours with AURORA**. In two later typhoons AURORA keeps the loss to 1 h and 3 h (simple rule: 28 h and 40 h). | `results/phase4/rec_storms.csv`, rows `delay_days = 14`, column `crit_outage_h` |
| 2 | **183,000 litres a year** | Solar and battery with AURORA cut diesel from 365,000 to 182,000 litres a year (−50 %), avoiding about **490 t of CO2** a year. Most of this comes from the hardware; AURORA's own share is 6,700 litres a year (3.5 %). | `results/phase4/year.csv`, column `diesel_l_per_yr` and `co2_t_per_yr`, sizing `pv500_bat1000` |
| 3 | **0 h → 52 h** | In a normal year the simple rule leaves the battery nearly empty every night, so its survival time is 0 hours half the time. AURORA keeps it charged: the median survival time is **52 hours**, and it is at least 24 hours in 63 % of all hours. | `results/phase4/year.csv`, column `cest_median_h` and `cest_ge24_pct` |

Figures: `figures/final/figc_outage_storms.pdf` (number 1), `fige_year_diesel_co2.pdf` (number 2), `figd_cest_mawar14d.pdf` (survival time through the storm: while the tanker is late, AURORA keeps at least 24 h of survival time in 73 % of hours, the simple rule in 26 %; `results/phase5/figd_cest_daily.csv`).

## What else we found

- **The forecast is better than the weather models it starts from.** For solar power one and two days ahead, AURORA's forecast error is 11 % and 8 % lower than ECMWF, the leading global model, and 46 to 47 % lower than assuming tomorrow is like today (`docs/validation_forecast.md`). In the storm tests, though, a better forecast changed the outcome only a little: the big gain comes from planning for fuel and keeping the battery charged.
- **Hardware economics depend on price and finance.** At the price NPC set for a similar island project (Sabtang, 2023) and a 9.94 % cost of capital, solar and battery do not pay for themselves in fuel savings within 20 years. They break even if installed at **68 to 98 % of that bid price**, depending on system size and cost of capital (4 to 9.94 %); at the cheaper published costs of Ocon and Bertheau (2019) they pay back in about 4 years (`results/phase5/figh_breakeven.csv`, `results/phase4/costs_hardware.csv`, `figh_hardware_payback.pdf`). NPC is already building such systems in Batanes, and off-grid power already costs NPC 3 to 4 times what customers pay (Philstar, 2026).
- **AURORA does the job of a much bigger battery.** With the simple rule, the 500 kWp system still loses 15 h of critical power at 1,000 kWh of battery and needs 2,000 kWh to get down to 1 h; AURORA reaches 0 h at 1,000 kWh. The extra 1,000 kWh costs about **48 M PHP** at the Sabtang-based price (before its year-15 replacement), against about **6.8 M PHP** for AURORA over 20 years at the assumed controller cost (2.5 M PHP plus 0.5 M PHP a year, discounted at 9.94 %) (`results/phase4/sweep.csv`, `figg_sizing_sweep.pdf`).
- **AURORA is about resilience, not fuel.** Its own fuel saving does not repay its assumed cost at the recommended size. What it buys is hours of critical service during a fuel crisis: 15 to 37 hours per 14-day disruption, at roughly 25,000 to 62,000 pesos per hour avoided (`results/phase4/aurora_cost_per_event.csv`).

## Limits, stated plainly

- **The island's demand is synthetic.** No hourly power data for Itbayat is public, so we built a realistic demand profile from the reported 250 kW peak. Real plant logs can replace it without changing the code.
- **The weather is a reanalysis (ERA5), not a measurement**, and solar output comes from a model of an assumed array.
- **There are no field data.** Everything here is a simulation; nothing has been tested on the island.
- **The fuel tank size, delivery interval and diesel unit ratings are assumptions**, because they are not published. The results are most sensitive to how much fuel is in the tank when the tanker is late.
- **The hardware economics depend on capital cost and finance.** Cheaper equipment or cheaper finance changes the answer from "no payback" to "a few years".
- Survival time is capped at 72 hours in the model; "72 hours" means "at least 72 hours".

Full details: `docs/results_phase4.md`. Every figure is rebuilt by `python -m aurora.plotting.phase5`, every table by `python -m aurora.experiments.phase4 tables`.
