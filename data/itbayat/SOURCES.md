# Itbayat site data: sources

Every number that describes Itbayat lives in [`site.yaml`](site.yaml). The value table at the bottom of this file is generated from it (`python -m aurora.data.site --write-sources`), so the two cannot drift apart.

## Status of the numbers (1 Nov 2026)

The primary documents (INL report, DOE off-grid list, PhilAtlas, PAGASA normals, the three journal papers and the Castro et al. dataset) could not be opened from the cloud session: the network policy refused `www.osti.gov`, `legacy.doe.gov.ph`, `www.philatlas.com`, `pubfiles.pagasa.dost.gov.ph`, `www.mdpi.com`, `www.sdewes.org`, `linkinghub.elsevier.com` and `data.mendeley.com`. The bibliographic records below were checked on Crossref. The site values marked `brief_unverified` are the figures quoted in `docs/CLOUD_BRIEF.md` and still have to be checked page by page against the documents. Values marked `missing` are null in `site.yaml`, and `aurora.data.site.value()` refuses to return them.

To close the gap, open each PDF, fill the page number into the `note` field, change `status` to `verified`, and fill in the `missing` rows (unit ratings, fuel tank volume, resupply interval, annual energy, distribution voltage).

## Status vocabulary

| Status | Meaning |
|---|---|
| `verified` | Checked in this repo against the primary document (page given in the note) |
| `brief_unverified` | Quoted in the cloud brief from the named source, not yet checked against it |
| `computed` | Derived by a script in this repo from a sourced number or a downloaded dataset |
| `ASSUMPTION` | No source. Has a sensitivity range, to be run in Phase 4 |
| `missing` | Unknown. Null in `site.yaml` and blocked from use |

## Sources

Site documents:

- **INL2025** Davis, R. Z. (2025). *Enhancing Power Resilience for Remote Communities: A Comprehensive Renewable Energy Solution for Itbayat Island.* Idaho National Laboratory, INL/RPT-25-83061, 30 Jan 2025. doi:[10.2172/3014068](https://doi.org/10.2172/3014068), https://www.osti.gov/servlets/purl/3014068 (title, author and date checked on Crossref).
- **DOE_OFFGRID** Department of Energy, Philippines. *List of existing off-grid power plants* (Luzon, Visayas, Mindanao). https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/05a_lvm_off-grid_loepp-09302022.pdf. The file name suggests the list is dated 30 Sep 2022, while the brief says 2021. [verify]
- **PHILATLAS** PhilAtlas, *Itbayat, Batanes profile*, compiling Philippine Statistics Authority census counts. https://www.philatlas.com/luzon/r02/batanes/itbayat.html. Prefer the PSA census tables themselves once they are reachable.
- **PAGASA_BASCO** PAGASA, *Climatological normals 1991-2020, Basco Radar station.* https://pubfiles.pagasa.dost.gov.ph/pagasaweb/files/cad/CLIMATOLOGICAL%20NORMALS%20(1991-2020)/BASCO%20RADAR.pdf. Transcribe it into `reference/pagasa_basco_normals_1991_2020.csv`.
- **TSAI2020** Tsai, C.-T., Beza, T. M., Wu, W.-B., Kuo, C.-C. (2020). Optimal configuration with capacity analysis of a hybrid renewable energy and storage system for an island application. *Energies* 13(1), 8. doi:[10.3390/en13010008](https://doi.org/10.3390/en13010008). CC BY 4.0. Transcribe its solar resource into `reference/tsai2020_solar.csv`.
- **OCON2019** Ocon, J. D., Bertheau, P. (2019). Energy transition from diesel-based to solar photovoltaics-battery-diesel hybrid system-based island grids in the Philippines: techno-economic potential and policy implication on missionary electrification. *J. Sustain. Dev. Energy Water Environ. Syst.* 7(1), 139-154. doi:[10.13044/j.sdewes.d6.0230](https://doi.org/10.13044/j.sdewes.d6.0230).
- **CASTRO2022** Castro, M. T., Pascasio, J. D. A., Delina, L. L., Balite, P. H. M., Ocon, J. D. (2022). Techno-economic and financial analyses of hybrid renewable energy system microgrids in 634 Philippine off-grid islands: policy implications on public subsidies and private investments. *Energy* 257, 124599. doi:[10.1016/j.energy.2022.124599](https://doi.org/10.1016/j.energy.2022.124599). The brief lists three authors; Crossref lists five. Dataset: doi:[10.17632/cg5z25rj8y.1](https://doi.org/10.17632/cg5z25rj8y.1) (CC BY 4.0, Mendeley Data; not yet opened). Transcribe the Itbayat row into `reference/castro2022_itbayat.csv`.

Project documents:

- **BRIEF** `docs/CLOUD_BRIEF.md` in this repo (project brief; collects the figures from the team update).
- **TEAM_CASE** `aurora-gsc/aurora-digital-twin`, branch `digital-twin-case-study`, `case_batanes.py` (illustrative values, no external source).
- **ASSUMPTION** No source. See the sensitivity range in the table.

Datasets downloaded by `python -m aurora.data.build_itbayat`:

- **ERA5** Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* 146, 1999-2049. doi:[10.1002/qj.3803](https://doi.org/10.1002/qj.3803). Accessed through the Open-Meteo historical weather API, https://open-meteo.com/en/docs/historical-weather-api (`models=era5`). Reanalysis, not a measurement.
- **OM_SAT** Open-Meteo satellite radiation API, https://open-meteo.com/en/docs/satellite-radiation-api. The satellite product behind the Itbayat grid point is not yet recorded. [verify]
- **NASA_POWER** NASA Langley Research Center, POWER Project, hourly API v2, https://power.larc.nasa.gov/ (radiation from CERES SYN1deg, meteorology from MERRA-2, per the API header).
- **IBTRACS** Knapp, K. R., Kruk, M. C., Levinson, D. H., Diamond, H. J., Neumann, C. J. (2010). The International Best Track Archive for Climate Stewardship (IBTrACS). *Bull. Amer. Meteor. Soc.* 91, 363-376. doi:[10.1175/2009BAMS2755.1](https://doi.org/10.1175/2009BAMS2755.1). Data: NOAA NCEI IBTrACS v04r01, West Pacific list.
- **PVLIB** Anderson, K. S. et al. (2023). pvlib python: 2023 project update. *J. Open Source Softw.* 8(92), 5994. doi:[10.21105/joss.05994](https://doi.org/10.21105/joss.05994).

Event evidence for the problem slide only (news; not yet opened from the cloud session): Manila Bulletin Sep 2022, Rappler Jun 2023, GMA Apr 2026, Philstar May 2026, Asia Business Outlook Mar 2025, Yale Clean Energy Forum policy memo Jan 2026. Add each URL and access date here once read.

## Typhoon events

`typhoon_events.csv` is computed from IBTrACS: every storm whose centre came within 500 km of the site since 2015. It gives the closest approach, the hours within 300 km and 500 km, and peak intensity. Intensity takes RSMC Tokyo (JMA, 10-min wind) first, then WMO, then USA (1-min) values, so mixed-agency rows are not strictly comparable. The two fuel-delay events in the brief are tracked as:

- Sep 2022: HINNAMNOR (closest 335 km, 2 Sep 2022) and MUIFA (closest 338 km, 10 Sep 2022). Neither came within 300 km.
- Late May 2023, Typhoon Mawar (PAGASA name Betty): closest 329 km on 30 May 2023 12 UTC, never within 300 km.

So the 300 km flag alone misses both documented disruptions. Sea state at 300 to 350 km is enough to stop deliveries. Phase 2 and 4 should use the 500 km flag (or wind and wave criteria) to define "typhoon hours".

## Synthetic load

`load_synthetic_hourly.parquet` is **synthetic**. No hourly measured load for Itbayat is public. Its shape parameters (`load_model` in `site.yaml`) and the critical-load ratings are `ASSUMPTION`s. The series is scaled so that the peak of the reference year (2024) equals `peak_demand_kw`. Growth (+12 % since 2021, about 3.9 %/yr) is applied up to 2024 and held flat after it, so peaks in 2025-2026 move only with weather and noise (256 and 260 kW in the current build). The 2024 load factor is 0.60 (1,306 MWh/yr). Check that against the INL annual energy once it is read. Daily-mean temperature comes from ERA5, or from NASA POWER (MERRA-2) while ERA5 is not downloaded; the parquet's metadata records which. Real plant logs replace it with `python -m aurora.data.build_itbayat --load <file>`.

## Value table

<!-- BEGIN VALUE TABLE (generated by python -m aurora.data.site --write-sources) -->

| Key | Value | Unit | Source | Date | Confidence | Status | Note |
|---|---|---|---|---|---|---|---|
| latitude | 20.78 | deg N | BRIEF |  | medium | brief_unverified | Town centre. Open-Meteo snaps to its grid; the grid point used is stored in each weather parquet. |
| longitude | 121.84 | deg E | BRIEF |  | medium | brief_unverified |  |
| population | 3100 | persons | PHILATLAS | [verify census year] | medium | brief_unverified | Brief says 'about 3,100'. Read exact census counts from PhilAtlas / PSA. |
| diesel_installed_kw_doe | 1086 | kW | DOE_OFFGRID | 2021 per brief; file name says 2022-09-30 [verify] | medium | brief_unverified | 1.086 MW installed. Recorded for comparison; not the current state. |
| diesel_dependable_kw_doe | 790 | kW | DOE_OFFGRID | 2021 per brief [verify] | medium | brief_unverified |  |
| diesel_units_inl | 4 | units | INL2025 | 2025-01-30 | medium | brief_unverified | Current state used by AURORA (brief, known problem 2). |
| diesel_combined_kw_inl | 660 | kW | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| diesel_out_of_service_kw_inl | 100 | kW | INL2025 | 2025-01-30 | medium | brief_unverified | One 100 kW unit out of service. |
| diesel_available_kw | 560 | kW | INL2025 | 2025-01-30 | medium | computed | 660 - 100 kW. |
| diesel_unit_ratings_kw | **missing** | kW | INL2025 |  | low | missing | Individual ratings of the four units: read from the INL report. |
| diesel_min_loading_frac | 0.3 | fraction of unit rating | ASSUMPTION |  | low | ASSUMPTION | Typical genset minimum loading; replace with INL or NPC-SPUG figure. Sensitivity range [0.25, 0.4]. |
| peak_demand_kw | 250 | kW | INL2025 | 2024 [verify reference year] | medium | brief_unverified |  |
| peak_season | May-July | months | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| peak_growth_since_2021 | 0.12 | fraction | INL2025 | 2025-01-30 | medium | brief_unverified | +12 % peak since 2021. |
| annual_energy_mwh | **missing** | MWh/yr | INL2025 |  | low | missing | Read from INL report; use to check the synthetic load's load factor. |
| diesel_price_php_per_l | 113 | PHP/L | INL2025 | 2025-01-30 | medium | brief_unverified | Base case. The team case study used 65 PHP/L (known problem 1). |
| diesel_price_low_php_per_l | 65 | PHP/L | TEAM_CASE |  | low | ASSUMPTION | Sensitivity low case (value used by the team case study, unsourced there). |
| diesel_price_high_php_per_l | 140 | PHP/L | BRIEF |  | low | ASSUMPTION | Sensitivity high case. |
| fuel_supply_months_now | 2 | months | INL2025 | 2025-01-30 | medium | brief_unverified | 'About 2 months' of supply with the current system. |
| fuel_supply_months_with_inl_system | 3 | months | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| fuel_storage_l | **missing** | L | INL2025 |  | low | missing | Tank capacity; read from INL report or NPC-SPUG. Needed for the Phase 3 fuel state. |
| resupply_interval_days | **missing** | days | INL2025 |  | low | missing |  |
| distribution_voltage_kv | **missing** | kV | INL2025 |  | low | missing |  |
| pv_kwp_inl | 300 | kWp | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| battery_kw_inl | 300 | kW | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| battery_kwh_inl | 300 | kWh | INL2025 | 2025-01-30 | medium | brief_unverified |  |
| pv_kwp_case | 500 | kWp | TEAM_CASE |  | low | ASSUMPTION | Illustrative size from the team case study. |
| battery_kwh_case | 1500 | kWh | TEAM_CASE |  | low | ASSUMPTION |  |
| cest_reserve_soc | 0.3 | fraction | BRIEF |  | medium | ASSUMPTION | CEST definition: SOC reserve floor. Design choice, not a site fact. |
| crit_clinic_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |
| crit_water_kw | 20 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [10, 30]. |
| crit_telecom_kw | 5 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [2.5, 7.5]. |
| crit_municipal_kw | 10 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [5, 15]. |
| crit_cold_storage_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |

<!-- END VALUE TABLE -->
