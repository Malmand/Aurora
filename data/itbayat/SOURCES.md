# Itbayat site data: sources

Every number that describes Itbayat lives in [`site.yaml`](site.yaml). The value table at the bottom of this file is generated from it (`python -m aurora.data.site --write-sources`), so the two cannot drift apart.

## Status of the numbers (2 Nov 2026)

Update 2 Nov 2026: the INL report, DOE off-grid list, PhilAtlas profile, PAGASA normals and Tsai et al. (2020) were read via web fetch outside the cloud session. Values confirmed there are now `verified` (page numbers not recorded). Findings: the DOE list is "as of 31 December 2021"; the INL report does not give unit ratings, tank volume, resupply interval or annual energy, so those stay `missing`; distribution is 480 V primary / 240 V secondary; population is 3,128 (2020 census). The PAGASA PDF is headed 2001-2020 normals despite its URL. Tsai et al. study Batan Island, not Itbayat.

### Original note (1 Nov 2026)

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
- **DOE_OFFGRID** Department of Energy, Philippines. *List of existing off-grid power plants* (Luzon, Visayas, Mindanao). https://legacy.doe.gov.ph/sites/default/files/pdf/electric_power/05a_lvm_off-grid_loepp-09302022.pdf. The document is titled "List of existing power plants (off-grid) as of December 2021".
- **PHILATLAS** PhilAtlas, *Itbayat, Batanes profile*, compiling Philippine Statistics Authority census counts. https://www.philatlas.com/luzon/r02/batanes/itbayat.html. Prefer the PSA census tables themselves once they are reachable.
- **PAGASA_BASCO** PAGASA, *Climatological normals 1991-2020, Basco Radar station.* https://pubfiles.pagasa.dost.gov.ph/pagasaweb/files/cad/CLIMATOLOGICAL%20NORMALS%20(1991-2020)/BASCO%20RADAR.pdf. Transcribe it into `reference/pagasa_basco_normals_1991_2020.csv`.
- **TSAI2020** Tsai, C.-T., Beza, T. M., Wu, W.-B., Kuo, C.-C. (2020). Optimal configuration with capacity analysis of a hybrid renewable energy and storage system for an island application. *Energies* 13(1), 8. doi:[10.3390/en13010008](https://doi.org/10.3390/en13010008). CC BY 4.0. Transcribe its solar resource into `reference/tsai2020_solar.csv`.
- **OCON2019** Ocon, J. D., Bertheau, P. (2019). Energy transition from diesel-based to solar photovoltaics-battery-diesel hybrid system-based island grids in the Philippines: techno-economic potential and policy implication on missionary electrification. *J. Sustain. Dev. Energy Water Environ. Syst.* 7(1), 139-154. doi:[10.13044/j.sdewes.d6.0230](https://doi.org/10.13044/j.sdewes.d6.0230).
- **CASTRO2022** Castro, M. T., Pascasio, J. D. A., Delina, L. L., Balite, P. H. M., Ocon, J. D. (2022). Techno-economic and financial analyses of hybrid renewable energy system microgrids in 634 Philippine off-grid islands: policy implications on public subsidies and private investments. *Energy* 257, 124599. doi:[10.1016/j.energy.2022.124599](https://doi.org/10.1016/j.energy.2022.124599). The brief lists three authors; Crossref lists five. Dataset: doi:[10.17632/cg5z25rj8y.1](https://doi.org/10.17632/cg5z25rj8y.1) (CC BY 4.0, Mendeley Data; not yet opened). Transcribe the Itbayat row into `reference/castro2022_itbayat.csv`.

- **IPCC2006** IPCC (2006). *2006 IPCC Guidelines for National Greenhouse Gas Inventories*, Vol. 2 Energy, Ch. 1 (Table 1.2, net calorific values) and Ch. 2 (Table 2.2, default CO2 emission factors). IGES, Japan. https://www.ipcc-nggip.iges.or.jp/public/2006gl/vol2.html

Project documents:

- **BRIEF** `docs/CLOUD_BRIEF.md` in this repo (project brief; collects the figures from the team update).
- **TEAM_CASE** `aurora-gsc/aurora-digital-twin`, branch `digital-twin-case-study`, `case_batanes.py` (illustrative values, no external source).
- **ASSUMPTION** No source. See the sensitivity range in the table.

Datasets downloaded by `scripts/download_itbayat.py` into `raw_small/` (provenance, request period, row counts and sha256 in `raw_small/MANIFEST.json`; the build reads only these files):

- **ERA5** Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* 146, 1999-2049. doi:[10.1002/qj.3803](https://doi.org/10.1002/qj.3803). Accessed through the Open-Meteo historical weather API, https://open-meteo.com/en/docs/historical-weather-api (`models=era5`), or with `--source cds` from the Copernicus Climate Data Store, https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels (grid point 20.75 N, 121.75 E; DNI derived as direct horizontal / cos zenith). The MANIFEST records which. Reanalysis, not a measurement.
- **OM_SAT** Open-Meteo satellite radiation API, https://open-meteo.com/en/docs/satellite-radiation-api. The satellite product behind the Itbayat grid point is not yet recorded. [verify]
- **NASA_POWER** NASA Langley Research Center, POWER Project, hourly API v2, https://power.larc.nasa.gov/ (radiation from CERES SYN1deg, meteorology from MERRA-2, per the API header).
- **IBTRACS** Knapp, K. R., Kruk, M. C., Levinson, D. H., Diamond, H. J., Neumann, C. J. (2010). The International Best Track Archive for Climate Stewardship (IBTrACS). *Bull. Amer. Meteor. Soc.* 91, 363-376. doi:[10.1175/2009BAMS2755.1](https://doi.org/10.1175/2009BAMS2755.1). Data: NOAA NCEI IBTrACS v04r01, West Pacific list.
- **OM_PREV** Open-Meteo previous-runs API, https://open-meteo.com/en/docs/previous-runs-api: archived ECMWF IFS 0.25°, GFS, ICON and JMA forecasts for lead days 0, 1 and 2 (Phase 2 inputs). The archive start date differs by model; the MANIFEST records the first available hour. [verify per model]
- **PVLIB** Anderson, K. S. et al. (2023). pvlib python: 2023 project update. *J. Open Source Softw.* 8(92), 5994. doi:[10.21105/joss.05994](https://doi.org/10.21105/joss.05994).

Event evidence for the problem slide only (news; not yet opened from the cloud session): Manila Bulletin Sep 2022, Rappler Jun 2023, GMA Apr 2026, Philstar May 2026, Asia Business Outlook Mar 2025, Yale Clean Energy Forum policy memo Jan 2026. Add each URL and access date here once read.

## Typhoon events

`typhoon_events.csv` is computed from IBTrACS: every storm whose centre came within 500 km of the site since 2015. It gives the closest approach, the hours within 300 km and 500 km, and peak intensity. Intensity takes RSMC Tokyo (JMA, 10-min wind) first, then WMO, then USA (1-min) values, so mixed-agency rows are not strictly comparable. The two fuel-delay events in the brief are tracked as:

- Sep 2022: HINNAMNOR (closest 335 km, 2 Sep 2022) and MUIFA (closest 338 km, 10 Sep 2022). Neither came within 300 km.
- Late May 2023, Typhoon Mawar (PAGASA name Betty): closest 329 km on 30 May 2023 12 UTC, never within 300 km.

So the 300 km flag alone misses both documented disruptions. Sea state at 300 to 350 km is enough to stop deliveries. Phase 2 and 4 should use the 500 km flag (or wind and wave criteria) to define "typhoon hours".

## Synthetic load

`load_synthetic_hourly.parquet` is **synthetic**. No hourly measured load for Itbayat is public. Its shape parameters (`load_model` in `site.yaml`) and the critical-load ratings are `ASSUMPTION`s. The series is scaled so that the peak of the reference year (2024) equals `peak_demand_kw`. Growth (+12 % since 2021, about 3.9 %/yr) is applied up to 2024 and held flat after it, so peaks in 2025-2026 move only with weather and noise (256 and 260 kW in the current build). The 2024 load factor is 0.60 (1,306 MWh/yr). Check that against the INL annual energy once it is read. Daily-mean temperature comes from ERA5 only: ERA5 agrees with the PAGASA Basco normals (+0.6 °C annual mean), while NASA POWER (MERRA-2) runs +1.9 °C warm and is not used downstream. Real plant logs replace it with `python -m aurora.data.build_itbayat --load <file>`.

## Value table

<!-- BEGIN VALUE TABLE (generated by python -m aurora.data.site --write-sources) -->

| Key | Value | Unit | Source | Date | Confidence | Status | Note |
|---|---|---|---|---|---|---|---|
| latitude | 20.78 | deg N | PHILATLAS |  | high | verified | PhilAtlas gives 20.7858 N, 121.8407 E. Town centre. Open-Meteo snaps to its grid; the grid point used is stored in each weather parquet. |
| longitude | 121.84 | deg E | PHILATLAS |  | high | verified |  |
| population | 3128 | persons | PHILATLAS | 2020 census | high | verified | 831 households (2015 census, latest on the page); land area 83.13 km2. |
| diesel_installed_kw_doe | 1086 | kW | DOE_OFFGRID | list as of 31 Dec 2021 | high | verified | ITBAYAT DPP, NPC-SPUG, 1.086 MW installed, 24 h operation, commissioned Dec 1996. No unit breakdown. Recorded for comparison; not the current state. checked 2026-11-02 against the document text via web fetch; page not recorded. |
| diesel_dependable_kw_doe | 790 | kW | DOE_OFFGRID | list as of 31 Dec 2021 | high | verified |  |
| diesel_units_inl | 4 | units | INL2025 | 2025-01-30 | medium | verified | Current state used by AURORA (brief, known problem 2). checked 2026-11-02 against the document text via web fetch; page not recorded. |
| diesel_combined_kw_inl | 660 | kW | INL2025 | 2025-01-30 | medium | verified |  |
| diesel_out_of_service_kw_inl | 100 | kW | INL2025 | 2025-01-30 | medium | verified | One 100 kW unit out of service. |
| diesel_available_kw | 560 | kW | INL2025 | 2025-01-30 | medium | computed | 660 - 100 kW. |
| diesel_unit_ratings_kw | **missing** | kW | INL2025 |  | low | missing | Not stated in the INL report (only the 660 kW total and one broken 100 kW unit). Ask NPC-SPUG / BATANELCO. |
| diesel_min_loading_frac | 0.3 | fraction of unit rating | ASSUMPTION |  | low | ASSUMPTION | Typical genset minimum loading; replace with INL or NPC-SPUG figure. Sensitivity range [0.25, 0.4]. |
| diesel_units_available | 3 | units | INL2025 | 2025-01-30 | medium | computed | 4 units minus the one out of service. |
| diesel_unit_kw_assumed | 186.7 | kW | ASSUMPTION |  | low | ASSUMPTION | Unit ratings are missing. Twin splits the 560 kW available equally over the 3 working units. Sensitivity range [140, 260]. |
| diesel_fuel_noload_l_per_h_per_kw | 0.04 | L/h per kW of committed rating | ASSUMPTION |  | low | ASSUMPTION | Linear fuel curve F = a * P_rated * on + b * P. With b = 0.22 this gives 0.277 L/kWh at 70 % loading, the team case value. Sensitivity range [0.02, 0.08]. |
| diesel_fuel_slope_l_per_kwh | 0.22 | L/kWh | ASSUMPTION |  | low | ASSUMPTION | Incremental fuel use of the linear fuel curve. Sensitivity range [0.2, 0.25]. |
| diesel_sfc_team_l_per_kwh | 0.277 | L/kWh | TEAM_CASE |  | low | ASSUMPTION | Team case flat fuel rate, labelled there as an NPC-SPUG rate without a document. Used only to size the assumed fuel tank. Sensitivity range [0.25, 0.33]. |
| diesel_start_cost_php | 300 | PHP per start | ASSUMPTION |  | low | ASSUMPTION | Wear cost per unit start in the MPC objective; stops unit cycling. Sensitivity range [0, 1000]. |
| co2_kg_per_l | 2.68 | kg CO2/L | IPCC2006 | 2006 | high | computed | 74,100 kg CO2/TJ x 43.0 TJ/Gg (IPCC 2006 defaults for gas/diesel oil) x 0.84 kg/L density (ASSUMPTION). Check table pages. [verify] |
| peak_demand_kw | 250 | kW | INL2025 | 2025-01-30 | medium | verified | INL says 'about 250 kW'; the reference year is not stated (report dated Jan 2025). |
| peak_season | May-July | months | INL2025 | 2025-01-30 | medium | verified |  |
| peak_growth_since_2021 | 0.12 | fraction | INL2025 | 2025-01-30 | medium | verified | +12 % peak since 2021. |
| annual_energy_mwh | **missing** | MWh/yr | INL2025 |  | low | missing | Not reported by INL. Candidate source: Castro et al. (2022) dataset row for Itbayat. |
| diesel_price_php_per_l | 113 | PHP/L | INL2025 | 2025-01-30 | medium | verified | INL: about 113 PHP/L (about 7.52 USD/gal), described as fluctuating. Base case. The team case study used 65 PHP/L (known problem 1). |
| diesel_price_low_php_per_l | 65 | PHP/L | TEAM_CASE |  | low | ASSUMPTION | Sensitivity low case (value used by the team case study, unsourced there). |
| diesel_price_high_php_per_l | 140 | PHP/L | BRIEF |  | low | ASSUMPTION | Sensitivity high case. |
| fuel_supply_months_now | 2 | months | INL2025 | 2025-01-30 | medium | verified | 'About 2 months' of supply with the current system. |
| fuel_supply_months_with_inl_system | 3 | months | INL2025 | 2025-01-30 | medium | verified |  |
| fuel_storage_l | **missing** | L | INL2025 |  | low | missing | Not in the INL report. Ask NPC-SPUG. Needed for the Phase 3 fuel state; until then derive from 'about 2 months of supply' as an ASSUMPTION. |
| resupply_interval_days | **missing** | days | INL2025 |  | low | missing | Not in the INL report. |
| fuel_storage_l_assumed | 60000 | L | ASSUMPTION |  | low | ASSUMPTION | Stands in for the missing fuel_storage_l. 2 months (INL) x 991 L/day, the diesel-only use of the 2024 synthetic load (1,306 MWh/yr x 0.277 L/kWh / 365). Sensitivity range [30000, 90000]. |
| resupply_interval_days_assumed | 30 | days | ASSUMPTION |  | low | ASSUMPTION | Stands in for the missing resupply_interval_days. Each delivery tops the tank up to capacity. Sensitivity range [14, 60]. |
| overdue_resupply_days_assumed | 7 | days | ASSUMPTION |  | low | ASSUMPTION | When a tanker is overdue, the MPC plans as if it arrives this many days from now (rolling). Sensitivity range [3, 14]. |
| php_per_usd | 56 | PHP/USD | TEAM_CASE |  | low | ASSUMPTION | Exchange rate used by the team case study. Sensitivity range [50, 60]. |
| co2_shadow_price_php_per_t | 2800 | PHP/t CO2 | ASSUMPTION |  | low | ASSUMPTION | Emissions term of the MPC objective (about 50 USD/t). The Philippines has no carbon price; this is a design weight. Sensitivity range [0, 5600]. |
| distribution_voltage_kv | 0.48 | kV | INL2025 | 2025-01-30 | medium | verified | Primary distribution 480 V; secondary 240 V via step-down transformers. |
| pv_kwp_inl | 300 | kWp | INL2025 | 2025-01-30 | medium | verified |  |
| battery_kw_inl | 300 | kW | INL2025 | 2025-01-30 | medium | verified |  |
| battery_kwh_inl | 300 | kWh | INL2025 | 2025-01-30 | medium | verified |  |
| pv_kwp_case | 500 | kWp | TEAM_CASE |  | low | ASSUMPTION | Illustrative size from the team case study. |
| battery_kwh_case | 1500 | kWh | TEAM_CASE |  | low | ASSUMPTION |  |
| battery_kw_case | 375 | kW | TEAM_CASE |  | low | ASSUMPTION | Battery power of the team case study (0.25 C). Sensitivity range [300, 750]. |
| cest_reserve_soc | 0.3 | fraction | BRIEF |  | medium | ASSUMPTION | CEST definition: SOC reserve floor. Design choice, not a site fact. |
| battery_eta_oneway | 0.95 | fraction | ASSUMPTION |  | medium | ASSUMPTION | Charge and discharge efficiency each (round trip about 0.90). Sensitivity range [0.92, 0.97]. |
| battery_soc_min | 0.2 | fraction | TEAM_CASE |  | low | ASSUMPTION | Hard lower SOC limit (team case value). The CEST reserve (0.30) sits above it. Sensitivity range [0.1, 0.3]. |
| battery_soc_max | 0.95 | fraction | TEAM_CASE |  | low | ASSUMPTION | Sensitivity range [0.9, 1.0]. |
| battery_soc_initial | 0.6 | fraction | TEAM_CASE |  | low | ASSUMPTION | SOC at the start of a run. Sensitivity range [0.3, 0.95]. |
| battery_degradation_php_per_kwh | 4.0 | PHP/kWh of charge or discharge | ASSUMPTION |  | low | ASSUMPTION | 450 USD/kWh replacement (team case) / (4,000 cycles x 0.8 depth x 2 directions) x 56 PHP/USD = 3.9 PHP/kWh. Sensitivity range [2.0, 8.0]. |
| voll_flex_php_per_kwh | 150 | PHP/kWh | ASSUMPTION |  | low | ASSUMPTION | Penalty for shedding flexible load. Above the diesel cost (about 30 PHP/kWh) so shedding is a last resort. Sensitivity range [50, 500]. |
| risk_penalty_php_per_kwh | 50 | PHP/kWh | ASSUMPTION |  | low | ASSUMPTION | Weight on the expected critical energy shortfall if diesel stopped (Monte Carlo), averaged over the horizon. Sensitivity range [0, 200]. |
| risk_window_h | 24 | h | ASSUMPTION |  | low | ASSUMPTION | Window over which R(t) counts a critical shortfall with diesel off. Sensitivity range [12, 48]. |
| fuel_scarcity_penalty_php_per_kwh | 500 | PHP/kWh | ASSUMPTION |  | low | ASSUMPTION | Penalty on critical energy that fuel plus battery at the horizon end cannot cover until the expected delivery. Above voll_flex so flexible load is shed first. Sensitivity range [200, 2000]. |
| crit_clinic_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |
| crit_water_kw | 20 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [10, 30]. |
| crit_telecom_kw | 5 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [2.5, 7.5]. |
| crit_municipal_kw | 10 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [5, 15]. |
| crit_cold_storage_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |

<!-- END VALUE TABLE -->
