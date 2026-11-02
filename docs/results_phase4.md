# Phase 4 results: storms, value of forecasting, full years, sizing, sensitivity, costs

Code: [`aurora/experiments/phase4.py`](../aurora/experiments/phase4.py) (runs) and [`phase4_tables.py`](../aurora/experiments/phase4_tables.py) (tables). Every number below comes from a CSV in [`results/phase4/`](../results/phase4/); `tables.md` there holds all tables in full. Rebuild the tables from the committed runs with `python -m aurora.experiments.phase4 tables`.

**Inputs are not measurements.** Weather is ERA5 reanalysis, PV comes from pvlib for an assumed array, and the load is the Phase 1 **synthetic** series. Fuel tank, resupply interval, diesel unit ratings and every controller weight are `ASSUMPTION`s (`data/itbayat/site.yaml`).

**CEST is capped at 72 h** in `aurora/twin/cest.py`. A value shown as "≥72 h (model cap)" means the battery and P10 solar carry critical load for at least 72 h; the true value is not known.

Controllers: **A** diesel only (status quo), **B** PV + battery with a simple rule, **C** AURORA (MILP rolling-horizon MPC on the forecast). Every run uses the Phase 2 forecast (`--forecast phase2`), an MPC horizon that ends with the newest forecast issue (25 to 48 h) and 32 Monte Carlo scenarios.

## Headline: the recommended system in three typhoons, tanker 14 days late

The recommended system is **500 kWp PV and a 375 kW / 1,000 kWh battery** (base capex 196 M PHP). It is the cheapest size in the sweep where C has no critical outage and a median CEST of at least 24 h on the Mawar 14-day case (section 4).

Stress case for every storm: the tank holds 6,000 L (10 %) when the tanker due the next day is delayed by 14 days. Each run lasts 18 days.

| Storm (forecast) | Ctl | Critical outage (h) | Critical unserved (kWh) | Flexible shed (kWh) | Diesel (L) | CEST median | CEST min |
|---|---|---|---|---|---|---|---|
| Mawar 2023 (backup forecast) | A | 217 | 10,763 | 21,861 | 8,948 | 0 h | 0 h |
| | B | 15 | 510 | 1,894 | 8,069 | 0 h | 0 h |
| | C | **0** | 0 | 944 | 8,037 | ≥72 h (model cap) | 0 h |
| Ragasa 2025 (full forecast) | A | 214 | 10,658 | 21,210 | 8,957 | 0 h | 0 h |
| | B | 28 | 972 | 3,268 | 7,282 | 0 h | 0 h |
| | C | **1** | 35 | 3,131 | 7,357 | ≥72 h (model cap) | 0 h |
| Mekkhala 2026 (full forecast) | A | 225 | 11,140 | 25,461 | 9,249 | 0 h | 0 h |
| | B | 40 | 1,312 | 4,582 | 7,313 | 0 h | 0 h |
| | C | **3** | 60 | 4,750 | 7,358 | ≥72 h (model cap) | 0 h |

Source: `rec_storms.csv`. With 3- and 7-day delays, neither B nor C loses critical load at this size; A loses 46 to 57 h with a 7-day delay.

- Adding PV and a battery (A to B) removes most of the outage: 217 to 225 h become 15 to 40 h.
- AURORA (B to C) removes most of the rest: 15 to 40 h become 0 to 3 h. It does this mainly by keeping the battery charged and shedding flexible load earlier.
- **The recommended size meets the 0 h criterion only on the storm it was chosen on.** On Ragasa and Mekkhala, C still loses 1 h and 3 h (35 and 60 kWh of critical energy). Section 7 explains why these last hours are lost.
- "Backup forecast" for Mawar: before Feb 2024 the NWP archive has no GHI, so the Phase 2 forecast for 2023 is the reduced model (JMA plus persistence and sun geometry). Ragasa and Mekkhala use the full Phase 2 model.

Storm choice: Mawar (Betty) 2023, plus the two strongest storms after Nov 2024 in `typhoon_events.csv`, ranked by the lowest central pressure while within 500 km: Ragasa (905 hPa, closest 154 km, Sep 2025) and Mekkhala (934 hPa, 288 km, Jun 2026). Champi (Oct 2026) ranks second but its 18-day window runs past the end of the data, so it is skipped. Each window starts at local midnight three days before the closest approach.

## 1. Storm runs at INL and case sizing

Critical outage hours, tanker 3 / 7 / 14 days late (`storms.csv`):

| Storm | Sizing | A | B | C |
|---|---|---|---|---|
| Mawar 2023 | INL (300 kWp, 300 kWh) | 0 / 49 / 217 | 0 / 0 / 89 | 0 / 0 / 5 |
| | case (500 kWp, 1,500 kWh) | 0 / 49 / 217 | 0 / 0 / 2 | 0 / 0 / 0 |
| Ragasa 2025 | INL | 0 / 46 / 214 | 0 / 0 / 92 | 0 / 0 / 5 |
| | case | 0 / 46 / 214 | 0 / 0 / 13 | 0 / 0 / 0 |
| Mekkhala 2026 | INL | 0 / 57 / 225 | 0 / 6 / 105 | 0 / 0 / 6 |
| | case | 0 / 57 / 225 | 0 / 0 / 37 | 0 / 0 / 2 |

Flexible load shed, diesel litres and cost (113 PHP/L), and median and minimum CEST for every run are in `storms.csv`. The pattern:

- **Flexible shed.** At INL sizing with a 14-day delay, C sheds more than B (12,258 vs 10,489 kWh for Mawar) and in return loses 5 h of critical load instead of 89 h. At case sizing C sheds less than B or about the same.
- **Diesel.** C uses 1 to 15 % less diesel than B in most runs. The largest saving is at INL sizing with a 7-day delay (Ragasa: 6,381 vs 7,535 L, minus 15 %). At case sizing with a 14-day delay C can use slightly more (Ragasa: 7,289 vs 7,136 L), because it keeps the battery full.
- **CEST.** B's median CEST is 0 h in every storm run, because B drains the battery to its 20 % floor before diesel starts. C's median is about 5 h at INL sizing (a 300 kWh battery holds about 5 h of critical load above the reserve) and ≥72 h (model cap) at case sizing. The minimum CEST is 0 h for every controller in every 7- and 14-day run, because at some hour the battery reaches the reserve.

## 2. Value of forecasting

C was rerun on every storm, sizing and delay with four forecasts. Totals over the 18 runs (`vof.csv`, `vof_by_storm.csv`):

| Forecast | Critical outage (h) | Flexible shed (MWh) | Diesel (L) | Fallback steps |
|---|---|---|---|---|
| Perfect (truth) | 0 | 54.3 | 106,669 | 0 |
| Phase 2 (AURORA) | 18 | 55.3 | 106,901 | 0 |
| Raw NWP mean | 16 | 57.4 | 108,233 | 1,080 |
| Smart persistence | 20 | 61.2 | 108,464 | 432 |

**The value of the forecast is modest and mixed.**

- On diesel and flexible shedding the Phase 2 forecast is closest to perfect: 0.2 % more diesel than perfect, against 1.5 % for raw NWP and 1.7 % for persistence; 1.8 % more shedding, against 5.6 % and 12.6 %.
- On critical outage hours it is not better than the baselines: 18 h, against 16 h for raw NWP and 20 h for persistence. All of these hours fall in the 14-day runs. Only perfect foresight gives 0 h.
- **The raw NWP runs are partly not NWP.** In 2023 the archive holds no NWP GHI, so every Mawar step with `phase2:nwp` comes from the persistence fallback (252 of 264 steps in the 14-day run; 1,080 fallback steps in all). Ragasa has a few such steps. So the raw NWP row is NWP only for Ragasa and Mekkhala, and for Mawar it is persistence. The persistence row also has 432 fallback steps, where the Phase 2 smart persistence was missing.
- The differences are a few hours out of about 18 days and lie close to the MILP's own noise (next paragraph). They do not show that a better forecast prevents outages; they show that it trims diesel and shedding a little.

**Mawar 7-day INL: why 2,649 kWh were shed with persistence and 1,718 kWh with Phase 2.** These two runs differed only in the forecast (Phase 3, both with the issue-aligned horizon and 64 scenarios). To check, C was rerun with 64 scenarios and four forecasts (`decomposition.csv`):

| Solar forecast | Demand forecast | Flexible shed (kWh) | First shed (PHT) |
|---|---|---|---|
| twin persistence | twin persistence | 2,834 | 31 May 01:00 |
| twin persistence | Phase 2 | 2,589 | 28 May 08:00 |
| Phase 2 | twin persistence | 2,222 | 1 Jun 01:00 |
| Phase 2 | Phase 2 | 1,718 | 1 Jun 01:00 |

- The Phase 2 run reproduces 1,718 kWh exactly.
- The persistence run gives 2,834 kWh, not 2,649. The inputs are identical (CEST matches hour for hour); the runs first differ at hour 52 in one diesel set point. This is the MILP choosing another solution within its 0.5 % optimality gap (this run was solved on a different machine). So about 190 kWh is solver noise.
- **The forecast explains the rest, about 1,100 kWh.** Swapping only the solar forecast to Phase 2 removes 610 kWh; swapping only the demand forecast removes 250 kWh; swapping both removes 1,120 kWh.
- Mechanism (`decomp_forecast_bias.csv`, mean per day over the window): the Phase 2 solar P50 is closer to truth (absolute error 176 vs 255 kWh/day) and its critical P90 is unbiased (minus 2 kWh/day against plus 24 kWh/day for persistence). A smaller critical P90 lowers the fuel the MPC thinks critical load needs after the horizon, so it sheds later and less. The 3-day scenario passes on 31 May, and the Phase 2 runs start shedding a day later than the persistence run.
- In this window 176 of the 528 Phase 2 forecast hours seen at the daily issue times came from the fallback, because the 2023 backtest has missing values.

## 3. Full years, Nov 2024 to Oct 2026

No tanker delays; deliveries every 30 days. Mean of the two years, with the range across the two years in brackets (`year.csv`, `year_by_period.csv`). Critical outage was 0 h for every controller and size in both years.

| Size | Ctl | Diesel (L/yr) | CO2 (t/yr) | Renewable share (%) | Curtailed (MWh/yr) | Battery throughput (MWh/yr) | CEST median | CEST ≥ 24 h (% of hours) |
|---|---|---|---|---|---|---|---|---|
| all | A | 365,306 | 979 | 0 | 0 | 0 | 0 h | 0 |
| INL | B | 259,368 (253,945 to 264,791) | 695 | 31.9 | 1.4 | 35 | 0 h | 0 |
| | C | 248,312 (242,458 to 254,167) | 665 | 31.1 | 5.6 | 87 | 4.9 h | 0 |
| case | B | 182,336 (173,098 to 191,574) | 489 | 52.1 | 0.5 | 208 | 0 h | 17 |
| | C | 173,333 (164,084 to 182,582) | 465 | 51.2 | 7.7 | 238 | ≥72 h (model cap) | 82 |
| recommended | B | 188,761 (181,097 to 196,426) | 506 | 50.3 | 26.0 | 185 | 0 h | 18 |
| | C | 182,109 (173,840 to 190,378) | 488 | 49.0 | 39.6 | 211 | 52 h (32 to ≥72) | 63 |

CEST percentiles (P10 to P90) are in `year.csv`. For C at the recommended size: P10 4.4 h, P25 16.5 h, P75 and P90 ≥72 h (model cap).

**Two effects, reported separately** (`effects_year.csv`):

| Size | A to B: adding PV and battery | B to C: AURORA's own effect |
|---|---|---|
| INL | 105,937 L/yr less diesel (29.0 %), 284 t CO2, 12.0 M PHP/yr | 11,056 L/yr less (4.3 %), 30 t CO2, 1.25 M PHP/yr; median CEST 0 to 4.9 h |
| case | 182,970 L/yr (50.1 %), 490 t, 20.7 M PHP/yr | 9,003 L/yr (4.9 %), 24 t, 1.02 M PHP/yr; median CEST 0 to ≥72 h (model cap) |
| recommended | 176,544 L/yr (48.3 %), 473 t, 19.9 M PHP/yr | 6,652 L/yr (3.5 %), 18 t, 0.75 M PHP/yr; median CEST 0 to 52 h |

Fuel cost at 113 PHP/L. In a normal year AURORA's main gain is CEST: the island would keep critical load running for days instead of hours if diesel stopped.

**Why C has a lower renewable share and more curtailment than B, yet burns less diesel.** Hourly runs, both years:

| Size | Ctl | Diesel output (MWh) | Fuel (kL) | L per kWh | Mean unit loading | Unit-hours | Mean SOC | Curtailed (MWh) |
|---|---|---|---|---|---|---|---|---|
| INL | B | 1,774 | 513 | 0.289 | 0.58 | 16,451 | 0.26 | 2.8 |
| | C | 1,794 | 491 | 0.274 | 0.74 | 12,939 | 0.79 | 11.1 |
| recommended | B | 1,294 | 374 | 0.289 | 0.59 | 11,902 | 0.35 | 51.3 |
| | C | 1,329 | 360 | 0.271 | 0.78 | 9,123 | 0.70 | 78.2 |

- C runs fewer units, each nearer full load. The fuel curve has a no-load term, so this lowers litres per kWh from 0.289 to about 0.27. C produces 1 to 3 % *more* diesel kWh but burns about 4 % *less* fuel.
- C holds the battery much fuller (mean SOC 0.70 to 0.79 against 0.26 to 0.35), because the risk and CEST terms reward stored energy. A full battery has less room for midday PV, so more PV is curtailed. Some diesel energy also goes into the battery and is lost to charging losses.
- Renewable share is computed from diesel kWh, not litres, so it falls slightly (by 0.8 to 1.3 points) while fuel falls.
- Battery cycling is high: C runs 289 equivalent full cycles a year at INL sizing (B: 118). A 15-year battery life is unlikely at that rate; see the limitations.

## 4. Sizing sweep: Mawar 2023, tanker 14 days late

PV 0 to 600 kWp, battery 0 to 2,000 kWh, battery power = min(kWh per hour, 375 kW) (`ASSUMPTION`; it reproduces both the INL and the case battery). Full grids in `sweep.csv` and `tables.md`.

C critical outage (h):

| PV \ battery | 0 | 250 | 500 | 750 | 1,000 | 1,250 | 1,500 | 2,000 kWh |
|---|---|---|---|---|---|---|---|---|
| 0 kWp | 174 | 130 | 126 | 126 | 125 | 121 | 120 | 115 |
| 200 | 92 | 4 | 6 | 8 | 7 | 6 | 6 | 6 |
| 300 | 67 | 4 | 3 | 6 | 4 | 6 | 5 | 4 |
| 400 | 54 | 8 | 8 | 5 | 4 | 3 | 3 | 5 |
| 500 | 49 | 10 | 5 | 2 | **0** | 0 | 0 | 0 |
| 600 | 44 | 7 | 4 | 0 | 0 | 0 | 0 | 0 |

C median CEST (h):

| PV \ battery | 250 | 500 | 750 | 1,000 | 1,250 | 1,500 | 2,000 kWh |
|---|---|---|---|---|---|---|---|
| 300 kWp | 4 | 9 | 16 | 28 | 35 | 40 | 63 |
| 400 | 4 | 8 | 14 | 32 | 42 | ≥72 (cap) | ≥72 (cap) |
| 500 | 4 | 9 | 19 | **≥72 (cap)** | ≥72 (cap) | ≥72 (cap) | ≥72 (cap) |
| 600 | 4 | 9 | 27 | ≥72 (cap) | ≥72 (cap) | ≥72 (cap) | ≥72 (cap) |

- **Recommended: 500 kWp, 375 kW / 1,000 kWh** (196 M PHP base capex). The other sizes that meet both conditions cost more: 600 kWp / 750 kWh costs 207 M PHP and 500 kWp / 1,250 kWh costs 209 M PHP.
- With 200 to 400 kWp of PV, C never reaches 0 h on this storm: 3 to 8 h of critical outage remain at any battery size (with less PV, 11 h or more). Below 500 kWp, energy is short, not storage.
- B never reaches 0 h below 600 kWp and 1,250 kWh, and its median CEST is 0 h at every size, because the rule always drains the battery first.
- Where extra battery stops adding CEST: for C at 500 to 600 kWp, beyond 1,000 kWh the median is already at the 72 h cap (`sweep_marginal_cest.csv`). For B a bigger battery adds no median CEST at all.
- The outage grid is not smooth (for example 4 h at 300 kWp / 1,000 kWh, 6 h at 1,250 kWh). These few hours sit at the end of the 14-day delay, where the result depends on a few litres of fuel and on solver noise (section 7).

## 5. Sensitivity at the recommended size: Mawar, tanker 14 days late

(`sensitivity.csv`)

| Case | A outage (h) | B outage (h) | B shed (kWh) | C outage (h) | C shed (kWh) | C diesel (L) | C CEST median |
|---|---|---|---|---|---|---|---|
| Base | 217 | 15 | 1,894 | 0 | 944 | 8,037 | ≥72 h (model cap) |
| Diesel 65 PHP/L | 217 | 15 | 1,894 | 0 | 1,142 | 8,057 | ≥72 h (model cap) |
| Diesel 140 PHP/L | 217 | 15 | 1,894 | 0 | 876 | 8,054 | ≥72 h (model cap) |
| Delay weights 0.7/0.2/0.1 | 217 | 15 | 1,894 | 0 | 944 | 8,037 | ≥72 h (model cap) |
| Shedding penalty 50 PHP/kWh | 217 | 15 | 1,894 | 0 | 942 | 8,044 | ≥72 h (model cap) |
| Shedding penalty 300 PHP/kWh | 217 | 15 | 1,894 | 0 | 934 | 8,033 | ≥72 h (model cap) |
| Shedding penalty 500 PHP/kWh | 217 | 15 | 1,894 | 6 | 849 | 8,044 | ≥72 h (model cap) |
| Starting tank −50 % (3,000 L) | 288 | 86 | 9,459 | 3 | 11,827 | 5,044 | 19.7 h |
| Starting tank +50 % (9,000 L) | 145 | 0 | 0 | 0 | 2 | 8,284 | ≥72 h (model cap) |
| Battery at 80 % capacity | 217 | 27 | 3,200 | 0 | 2,733 | 8,049 | 26.0 h |
| Load +12 % | 230 | 44 | 5,389 | 2 | 6,021 | 8,386 | 23.5 h |

Diesel cost for each case is in `sensitivity.csv`. A and B do not use the forecast or the penalties, so only the tank, battery and load cases change them.

- **The trade-off between shedding and critical outage** (figure `results/phase4/tradeoff_shed_vs_outage.pdf`): C sheds about as much as B or more, and in return loses far fewer critical hours. With half the starting fuel, C sheds 2,368 kWh more than B (11,827 vs 9,459) and loses 3 h instead of 86 h. Raising the shedding penalty to 500 PHP/kWh, equal to the fuel-scarcity penalty, removes the reason to shed early: C sheds 95 kWh less and loses 6 h of critical load. At 50 and 300 PHP/kWh the result barely moves (0 h, 934 to 944 kWh shed).
- **The delay weights have no effect at this size, and they are applied.** The run uses the 0.7/0.2/0.1 prior (checked in the job parameters): the belief about the late tanker is 0.67/0.33 after the 3-day scenario passes, against 0.6/0.4 at base. But at 500 kWp / 1,000 kWh the MPC sees a fuel shortfall only in the last two days of the 14-day delay (it sheds 254 and 687 kWh on days 13 and 14, and 4 kWh before). By then the 3- and 7-day scenarios have passed and the 14-day scenario has weight 1.0 under either prior. So every MPC decision is the same and the results match to the litre. The weights would matter for a smaller system, where the shortfall shows up while several scenarios are still open (for example INL sizing, which starts shedding on 1 June, while the 7- and 14-day scenarios are both still open). No rerun was needed.
- Fuel stock is the strongest lever: half the tank turns 0 h into 3 h even for C, and the median CEST falls to 20 h.
- A battery at 80 % capacity or 12 % more load keeps C at 0 to 2 h of outage, at the price of more shedding and a median CEST near 24 h.

## 6. Costs (PHP)

Unit costs (`site.yaml`, `cost_crosscheck.csv`):

| Case | PV (PHP/kWp) | Battery (PHP/kWh + PHP/kW) | Basis |
|---|---|---|---|
| Low | 67,200 | 14,560 + 30,240 | Ocon and Bertheau (2019) Table 1 as published, at 56 PHP/USD (`ASSUMPTION`) |
| Base | 221,915 | 48,082 + 99,862 | NPC bid BCS 2023-0570 (Sabtang, Batanes): ceiling of PHP 57,697,900 for ≥180 kWp + ≥120 kW / 120 kWh, split with the Ocon and Bertheau cost structure |
| High | 277,394 | 60,103 + 124,828 | base × 1.25 (`ASSUMPTION`) |

Capex: INL 33.6 / 111.0 / 138.7 M PHP (low / base / high), case 66.8 / 220.5 / 275.7 M PHP, recommended 59.5 / 196.5 / 245.6 M PHP. The battery is replaced in year 15 (Ocon and Bertheau battery life) at the same cost case. O&M 2 % of capex per year (`ASSUMPTION`). WACC 9.94 % and a 20-year life (Ocon and Bertheau 2019). The diesel plant is sunk in every option and there is no salvage value.

Cross-check: the Sabtang ceiling is about 5,700 USD per kWp of PV; the base-case INL and case systems are 6,600 and 7,900 USD per kWp. All are inside the ESMAP (2019) mini-grid range (1,420 to 22,689 USD/kW) and above its median (about 3,900 USD/kW). IRENA (2026) gives 667 USD/kW for utility-scale PV and 140 USD/kWh for four-hour utility-scale batteries in 2025; these are utility-scale references only and are not used.

### A to B: the hardware investment

At 113 PHP/L, fuel saving of B against A (`costs_hardware.csv`):

| Size | Capex base (M PHP) | Fuel saving (M PHP/yr) | Simple payback low / base / high (y) | Discounted payback at 9.94 %, low / base / high | LCOE at 9.94 %, low / base / high (PHP/kWh) |
|---|---|---|---|---|---|
| Diesel only (A) | 0 | 0 | | | 31.4 |
| INL | 111.0 | 12.0 | 2.8 / 9.3 / 11.6 | 3.7 y / **none** / **none** | 26.1 / 34.8 / 37.9 |
| case | 220.5 | 20.7 | 3.2 / 10.7 / 13.3 | 4.4 y / **none** / **none** | 23.3 / 41.0 / 47.3 |
| recommended | 196.5 | 19.9 | 3.0 / 9.8 / 12.3 | 4.0 y / **none** / **none** | 23.0 / 38.5 / 44.1 |

**At the Sabtang bid price and a 9.94 % WACC, the hardware does not pay back within its 20-year life, at any size and any diesel price (65, 113 or 140 PHP/L).** The simple payback of about 10 years hides the year-15 battery replacement, the O&M and the discounting. The base-case LCOE (35 to 41 PHP/kWh) is above diesel-only generation (31.4 PHP/kWh at 113 PHP/L).

- WACC sensitivity (arithmetic only; the diesel use is unchanged): at the base cost and 113 PHP/L there is no discounted payback even at 4 % or 6 %. At 140 PHP/L the base case pays back at 4 % (INL 11.1 y, recommended 16.2 y, case 19.3 y) and at 6 % (INL 16.4 y, recommended 19.0 y), but not at 9.94 %.
- At the low cost (Ocon and Bertheau 2019 as published) every size pays back: in 2.8 to 10.5 years at 9.94 % (depending on size and diesel price), with an LCOE of 23 to 26 PHP/kWh at 113 PHP/L. At the high cost there is no discounted payback in any case.
- **Context.** NPC is already paying for this kind of hardware: it put a 180 kWp + 120 kWh system for Sabtang out to bid in Nov 2023, and it planned 250 kWp of PV for Itbayat (Manila Bulletin, 1 May 2021). Off-grid generation already costs NPC 3 to 4 times the tariff it charges (Philstar, 29 May 2026). So the hardware decision is a public-service decision that is being made anyway; the question for AURORA is what it adds on top.

### B to C: AURORA's own effect

AURORA's added cost is a controller and software cost, an `ASSUMPTION`: 2.5 M PHP one-off (range 1 to 5 M) plus 0.5 M PHP a year (range 0.2 to 1 M), annualised to 0.79 M PHP/yr at 9.94 % (`costs_aurora.csv`).

| Size | Extra diesel saved (L/yr) | Fuel saving at 113 PHP/L (M PHP/yr) | Net of running cost (M PHP/yr) | Fuel-only discounted payback at 9.94 % | Flexible shed added in a normal year | Critical outage avoided (normal year) | Median CEST gained |
|---|---|---|---|---|---|---|---|
| INL | 11,056 | 1.25 | 0.75 | 4.3 y | 31 kWh/yr | 0 h | 0 to 4.9 h |
| case | 9,003 | 1.02 | 0.52 | 6.9 y | 0 | 0 h | 0 to ≥72 h (model cap) |
| recommended | 6,652 | 0.75 | 0.25 | **not within 20 y** (NPV −0.35 M PHP) | 40 kWh/yr | 0 h | 0 to 52 h |

- **At the recommended size, the fuel saving alone does not repay AURORA within 20 years at 113 PHP/L. At 65 PHP/L the fuel-only payback is never, because the saving is below the annual running cost.** At INL and case sizing the fuel saving repays it in 4 to 7 years at 113 PHP/L, but not within 20 years at 65 PHP/L.
- This is expected. **AURORA's purpose is resilience, not fuel savings.** In a normal year nobody loses power with B or C. AURORA's value shows during a fuel disruption: it keeps critical load served when B cannot, and it keeps the battery charged so CEST is days, not zero.

**Cost per critical outage hour avoided, per event (leading figure).** Hours avoided by C against B in each storm run, and AURORA's annualised base cost divided by the event rate and by those hours (`aurora_cost_per_event.csv`, base controller cost, 9.94 %):

| Storm, tanker 14 days late | Size | B outage (h) | C outage (h) | Avoided (h) | PHP per hour avoided at 0.4 / 0.85 / 1.05 events per year |
|---|---|---|---|---|---|
| Mawar 2023 | recommended | 15 | 0 | 15 | 132,075 / 62,153 / 50,314 |
| Ragasa 2025 | recommended | 28 | 1 | 27 | 73,375 / 34,529 / 27,952 |
| Mekkhala 2026 | recommended | 40 | 3 | 37 | 53,544 / 25,197 / 20,398 |
| Mawar 2023 | INL | 89 | 5 | 84 | 23,585 / 11,099 / 8,985 |
| Ragasa 2025 | INL | 92 | 5 | 87 | 22,771 / 10,716 / 8,675 |
| Mekkhala 2026 | INL | 105 | 6 | 99 | 20,011 / 9,417 / 7,623 |

With a 3- or 7-day delay C avoids nothing at the recommended or case size, because B also rides those through; at INL sizing C avoids 6 h with a 7-day delay in Mekkhala.

Expected over a year (`costs_aurora.csv`): weighting the 3-, 7- and 14-day runs by the overdue-delay weights (0.5 / 0.3 / 0.2) gives 5.3 h avoided per event at the recommended size, 18.6 h at INL size and 3.3 h at case size. With the documented disruption rate:

| Size | PHP per hour avoided, base rate 0.85/yr | low rate 0.4/yr | high rate 1.05/yr | upper bound 4.15/yr | base rate, controller cost low / high |
|---|---|---|---|---|---|
| recommended | 177,017 | 376,162 | 143,300 | 36,257 | 70,807 / 354,035 |
| INL | 50,123 | 106,512 | 40,576 | 10,266 | 20,049 / 100,246 |
| case | 279,687 | 594,336 | 226,414 | 57,285 | 111,875 / 559,375 |

- Event rates are the documented fuel disruptions to Batanes power: base 0.85 per year (4 weather-driven disruptions, Jan 2022 to Oct 2026), high 1.05 (adding the Apr 2026 national diesel shortage), low 0.4 (7 disruptions since 2009). The 4.15 per year rate counts every storm within 330 km (IBTrACS); most of those did not stop fuel deliveries, so it is an upper bound only.
- Each documented disruption is assumed to look like the stress case simulated here (tank at 6,000 L, tanker 3 to 14 days late).
- **Disruptions depend on conditions along the shipping route, not only on typhoon distance from Itbayat.** In two of the documented events the tanker was stranded at Bolinao, Pangasinan, in monsoon weather. A storm-distance trigger alone misses such events.
- AURORA costs more per hour avoided at the larger sizes because the hardware already removes most outage hours there; at INL sizing B loses about 90 h in a 14-day disruption, and AURORA turns that into 5 to 6 h for about 10,000 PHP per hour avoided.
- WACC sensitivity (4 % and 6 %) is in `costs_aurora.csv`: it changes the annualised controller cost from 0.79 to 0.68 M PHP/yr and the cost per hour in proportion.

## 7. Why INL sizing with a 14-day delay loses 5 h here and 0 h in Phase 3

Phase 3 (Mawar, INL, 14-day delay) reported 0 h of critical outage for C; this run reports 5 h (107.5 kWh). What changed and what happens:

- **Inputs changed.** Phase 3 used the twin's persistence forecast and 64 scenarios; Phase 4 uses the Phase 2 forecast and 32 scenarios. Weather, load, tank and delay are the same.
- **Both runs end with an almost empty tank.** Phase 3 reached 0 L. Here the tank falls to 12.7 L at 01:00 PHT on 10 June, 23 h before the tanker arrives (00:00 PHT 11 June). One unit at its 30 % minimum load burns about 20 L an hour, so 12.7 L cannot start a unit. The battery is at its 20 % floor, and the 5 outage hours are the dawn of 10 June and the evening of 10 June.
- **This is a knife edge.** C sheds 12,258 kWh here against 12,814 kWh in Phase 3, a difference of 4 %, and the 107 kWh of critical energy lost is under 1 % of the shedding. With a perfect forecast and the same 32 scenarios C loses 0 h (`vof.csv`); with raw NWP it loses 2 h and with persistence 5 h. Without reruns the shares of the forecast, the scenario count and the solver gap cannot be separated.
- **Model limitation it reveals.** The MILP plans the fuel tank down to 0 L and does not know that the last 20 L or so cannot be used, because a unit cannot run below its minimum load. A small fuel reserve in the MPC (for example one hour of minimum-load burn) would likely remove these last hours. This is a recommended change for the next version; it was not run here.
- The same mechanism explains the 1 to 3 h left at the recommended size in Ragasa and Mekkhala.

## Limitations

- **The load is synthetic** and the weather is reanalysis (ERA5) with modelled PV. There are no field data. Real plant logs drop in through `data/itbayat/load_hourly.parquet`.
- **Fuel logistics are assumed.** Tank volume (60,000 L), resupply interval (30 days), the starting tank in a disruption (6,000 L) and the delay weights are `ASSUMPTION`s. The results are most sensitive to the starting tank.
- **Diesel unit ratings are assumed** (three equal units of 186.7 kW, 30 % minimum load, linear fuel curve).
- **Costs.** The base case scales a 2023 bid ceiling for a smaller island; it is not an award price. Battery replacement at year 15 is assumed even though C cycles the INL battery about 290 times a year, which would likely shorten its life. No salvage value, no diesel O&M, no change in diesel price over time. AURORA's controller cost is an `ASSUMPTION`.
- **Storms.** Three storms, one stress pattern (low tank plus a late tanker). The recommended size was chosen on one of them and does not reach 0 h on the other two. The disruption rates come from news reports, several not yet read in full ([verify] entries in `SOURCES.md`).
- **The forecast for Mawar 2023 is the backup (reduced) model,** and the raw-NWP comparison for 2023 is persistence in disguise.
- **Solver noise.** The MILP solves to a 0.5 % gap with a 10 s limit. Runs on different machines can choose different near-optimal plans; in the Mawar 7-day check this moved flexible shedding by about 190 kWh (7 %). Differences of a few hours or a few hundred kWh between single runs are within this noise.
- **CEST is capped at 72 h**, so medians reported as "≥72 h (model cap)" are lower bounds.
- **Full years** are run in four half-year chunks; SOC and the tank restart at each chunk start (1 Nov and 1 May).
