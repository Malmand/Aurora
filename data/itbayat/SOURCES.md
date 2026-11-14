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

- **IRENA2025** IRENA (2026). *Renewable Power Generation Costs in 2025.* International Renewable Energy Agency, Abu Dhabi. ISBN 978-92-9260-749-4. Executive summary: https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2026/Jul/IRENA_TEC_RPGC_2025_Executive_summary_2026.pdf. Values transcribed by the user from the executive summary (the cloud session could not reach irena.org): utility-scale PV global weighted-average total installed cost 2025 (Figure S1, p. 6); four-hour utility-scale battery installed cost 2025 (p. 3 and p. 8). Utility-scale reference only; not used for the Itbayat costs.
- **NPC_BCS_2023_0570** National Power Corporation (NPC), Philippines. Public bidding BCS 2023-0570, PR HO-PIB24-002: supply and installation of a solar PV (at least 180 kWp) plus battery (at least 120 kW / 120 kWh) system with transformers and civil works, Sabtang (Savidug) Island, Batanes. Bid opening 21 Nov 2023. Approved budget for the contract (ABC) PHP 57,697,900, a ceiling, not an award price. Values provided by the user; the bid document was not opened from the cloud session. [verify] add the NPC or PhilGEPS URL and access date.
- **ESMAP2019** ESMAP (2019). *Mini Grids for Half a Billion People: Market Outlook and Handbook for Decision Makers.* Energy Sector Management Assistance Program, Technical Report 014/19, World Bank, Washington DC. [verify] URL (World Bank Open Knowledge Repository) and the table or figure with the mini-grid capex median (about 3,900 USD/kW) and range (1,420 to 22,689 USD/kW); values provided by the user.
- **MB2021** Manila Bulletin, 1 May 2021: NPC plans 250 kWp of solar PV for Itbayat. News, used as evidence of the plan only. Provided by the user; [verify] URL and access date.
- **NPC_MEP2025** National Power Corporation (NPC), Corporate Planning Department. *Missionary Electrification Plan 2025-2029.* https://www.napocor.gov.ph/wp-content/uploads/Operations/NPC_Missionary_Electrification_Plan_2025-2029.pdf. Read in full by this repo (14 Nov 2026, PDF uploaded by the user). Used: Annex A, NPC-SPUG plant statistics as of 25 Dec 2024 (Itbayat DPP 850 kW rated, 740 kW dependable, December 2024 peak 215 kW); Annex M, diesel-solar hybridization for Itbayat (180 kWp, 120 kWh, PHP 51,949,600); Annex P, RE compliance (248 MWh/yr from 2028); Annex R, p. 114 of the PDF, supply and demand profile of Itbayat DPP, 2019-2023 historical and 2024-2029 forecast (peak, rated and dependable capacity, energy sales, gross generation).
- **DOE_MEDP2016** Department of Energy, Philippines. *2016-2020 Missionary Electrification Development Plan.* https://rise.esmap.org/data/files/library/philippines/Renewable%20Energy/Phillipines_Electrification%20Plan%20medp_2016-2020.pdf. Used: Annex C, p. 88, NPC-SPUG plant use and losses and fuel rate as of Dec 2015 (Itbayat DPP fuel rate 0.326 L/kWh, PUAL 6.20 %); Annex B.1 (2015 gross generation 581.4 MWh, 18 h service).
- **DOE_MEDP2024** Department of Energy, Philippines. *2024-2028 Missionary Electrification Development Plan.* Used as a cross-check: Annex 1, 2023 power statistics of missionary and off-grid areas (Itbayat: 24 h service, 1.086 MW rated, 0.740 MW dependable, 2023 peak 0.260 MW, 2023 consumption 981.705 MWh). PDF uploaded by the user; [verify] add the DOE URL.
- **ERC_2025_060** Energy Regulatory Commission, Philippines. Order of 28 April 2025, ERC Case No. 2025-060 RC, petition of NPC for the UCME availment for CY 2026. https://spug.napocor.gov.ph/erc/Order_2025-060%20RC.pdf. Used: p. 4, NPC delivered diesel price for CY 2026, 65.3769 PHP/L plus 11.6923 PHP/L hauling (77.0692 PHP/L), and the CY 2023 actual average of 63.7284 PHP/L.

- **PHILSTAR2026** Philstar, 29 May 2026: off-grid generation costs NPC 3 to 4 times the tariff. News, used as context only. Provided by the user; [verify] URL and access date.

- **NEWS_DISRUPTIONS** Documented fuel disruptions to Batanes power (news; evidence of events only; provided by the user; [verify] URL and access date for each):
  - Philstar, 15 Sep 2009: fuel ship in dry dock.
  - Philstar, 12 Oct 2011: no funds for diesel, Jun to Oct 2011.
  - Manila Bulletin, 3 Sep 2022: fuel disruption, Sep 2022.
  - GMA News, 29 May 2023, and Rappler (Jun 2023): Typhoon Betty (Mawar).
  - Bombo Radyo Tuguegarao, 5 Aug 2023: southwest monsoon.
  - Manila Times, 5 Aug 2025: Itbayat food and fuel shortage. [verify] not read.
  - GMA News, Apr 2026: national diesel shortage.
  In two of these events the tanker was stranded at Bolinao, Pangasinan, in monsoon weather (provided by the user).

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

`load_synthetic_hourly.parquet` is **synthetic**: no hourly measured load for Itbayat is public. Since 14 Nov 2026 it is **calibrated to NPC's annual figures for Itbayat DPP** (`npc_itbayat_dpp` in `site.yaml`, source NPC_MEP2025 Annex R). For each year the relative profile r(t) (hourly shape, season, temperature, Sunday, noise; all `ASSUMPTION`s) is mapped to k·r(t)^γ, with γ chosen so the year's load factor and k so its gross generation match NPC; the annual peak then matches too. k and γ are interpolated between mid-year points so there is no step on 1 January. 2019-2023 are NPC historical values; 2024-2026 are NPC's forecast, since NPC has not yet published actuals for them. Years before 2019 use the 2019 values. The critical-load ratings are still `ASSUMPTION`s. Before calibration the series had a load factor of 0.60 and 1,242 MWh in 2023 against NPC's 0.46 and 1,068 MWh, with a 237 kW peak against 264 kW. Daily-mean temperature comes from ERA5 only (it agrees with the PAGASA Basco normals within +0.6 °C). Real plant logs replace it with `python -m aurora.data.build_itbayat --load <file>`.

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
| diesel_rated_kw_npc | 850 | kW | NPC_MEP2025 | 2023 | high | verified | Itbayat DPP total installed (rated) capacity 2022-2023, MEP 2025-2029 Annex R. Dependable 740 kW; largest unit 200 kW dependable. NPC plant statistics of 25 Dec 2024 (Annex A) give the same 850 / 740 kW. Cross-check only: the twin keeps the INL current state (560 kW available) as the harder case. |
| diesel_largest_unit_kw_npc | 200 | kW | NPC_MEP2025 | 2023 | high | verified | Dependable capacity of the largest unit. Supports diesel_unit_kw_assumed (186.7 kW). |
| diesel_fuel_rate_2015_npc | 0.326 | L/kWh | DOE_MEDP2016 | 2015-12 | medium | verified | Itbayat DPP 2015 fuel rate, MEDP 2016-2020 Annex C (p. 88). Basco DPP 0.259, allowable about 0.30. Older, smaller plant on 18 h service; the twin's curve averages 0.278 L/kWh. Sensitivity case. |
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
| annual_energy_mwh | 1068 | MWh/yr | NPC_MEP2025 | 2023 | high | verified | Itbayat DPP gross generation 2023 (historical), 1,067.943 MWh; energy sales 1,045.195 MWh. MEP 2025-2029 Annex R, p. 114 of the PDF. Year-by-year values in npc_itbayat_dpp below. |
| peak_demand_kw_2023_npc | 264 | kW | NPC_MEP2025 | 2023 | high | verified | Annual peak demand 2023, last historical year in MEP 2025-2029 Annex R (p. 114). DOE MEDP 2024-2028 Annex 1 gives 260 kW and 981.7 MWh consumption for 2023 (cross-check). |
| peak_demand_kw_dec2024_npc | 215 | kW | NPC_MEP2025 | 2024-12-25 | high | verified | Peak load for the month of December 2024, MEP 2025-2029 Annex A (NPC-SPUG plant statistics as of 25 Dec 2024). Off-season month. |
| load_factor_2023_npc | 0.462 | fraction | NPC_MEP2025 | 2023 | high | computed | 1,067.943 MWh / (0.264 MW x 8760 h). The pre-calibration synthetic load had 0.60. |
| energized_households_npc | 1009 | households | NPC_MEP2025 | 2024 | high | verified | MEP 2025-2029 Annex R; 923 households in the 2020 census, 5 barangays. Annex M lists 1,035 electrified households. |
| diesel_price_php_per_l | 113 | PHP/L | INL2025 | 2025-01-30 | medium | verified | INL: about 113 PHP/L (about 7.52 USD/gal), described as fluctuating. Base case. The team case study used 65 PHP/L (known problem 1). |
| diesel_price_low_php_per_l | 77.07 | PHP/L | ERC_2025_060 | 2025-04-28 | high | verified | NPC delivered diesel price projected for CY 2026, average over all SPUG plants: 65.3769 PHP/L delivered plus 11.6923 PHP/L hauling. ERC Order, Case 2025-060 RC, p. 4. NPC's CY 2023 actual average was 63.73 PHP/L before hauling. Low case; replaces the unsourced 65 PHP/L of the team case. |
| diesel_price_high_php_per_l | 140 | PHP/L | BRIEF |  | low | ASSUMPTION | Sensitivity high case. |
| fuel_supply_months_now | 2 | months | INL2025 | 2025-01-30 | medium | verified | 'About 2 months' of supply with the current system. |
| fuel_supply_months_with_inl_system | 3 | months | INL2025 | 2025-01-30 | medium | verified |  |
| fuel_storage_l | **missing** | L | INL2025 |  | low | missing | Not in the INL report. Ask NPC-SPUG. Needed for the Phase 3 fuel state; until then derive from 'about 2 months of supply' as an ASSUMPTION. |
| resupply_interval_days | **missing** | days | INL2025 |  | low | missing | Not in the INL report. |
| fuel_storage_l_assumed | 52000 | L | ASSUMPTION |  | low | ASSUMPTION | Stands in for the missing fuel_storage_l. 2 months (INL) x 853 L/day, the diesel-only use of NPC's 2024 gross generation (1,124 MWh/yr x 0.277 L/kWh / 365). Was 60,000 L before the load was calibrated to NPC (1,306 MWh/yr synthetic). Sensitivity range [30000, 90000]. |
| resupply_interval_days_assumed | 30 | days | ASSUMPTION |  | low | ASSUMPTION | Stands in for the missing resupply_interval_days. Each delivery tops the tank up to capacity. Sensitivity range [14, 60]. |
| overdue_delay_scenarios_days | [3, 7, 14] | days after the planned delivery | ASSUMPTION |  | low | ASSUMPTION | Possible total delays of an overdue tanker. Scenarios already passed are dropped and the weights renormalised. Sensitivity range [[2, 5, 10], [5, 10, 21]]. |
| overdue_delay_weights | [0.5, 0.3, 0.2] | probability | ASSUMPTION |  | low | ASSUMPTION | Prior weights of the delay scenarios. With the 500 vs 150 PHP/kWh penalties, flexible load is shed only when P(fuel shortfall) > 0.3. Sensitivity range [[0.7, 0.2, 0.1], [0.2, 0.3, 0.5]]. |
| overdue_resupply_days_assumed | 7 | days | ASSUMPTION |  | low | ASSUMPTION | Fallback once all delay scenarios have passed: the MPC plans as if the tanker arrives this many days from now (rolling). Sensitivity range [3, 14]. |
| php_per_usd | 56 | PHP/USD | TEAM_CASE |  | low | ASSUMPTION | Exchange rate used by the team case study. Used for the low cost case (Ocon and Bertheau 2019 in USD) and the ESMAP cross-check; base and high costs are in PHP. Sensitivity range [50, 60]. |
| npc_sabtang_abc_php | 57697900 | PHP | NPC_BCS_2023_0570 | 2023-11-21 | medium | verified | Approved budget for the contract (ceiling, not an award price) for >=180 kWp PV and >=120 kW / 120 kWh battery with transformers and civil works, Sabtang (Savidug) Island, Batanes. Provided by the user. |
| npc_sabtang_pv_kwp | 180 | kWp | NPC_BCS_2023_0570 | 2023-11-21 | medium | verified | Minimum PV size in the bid. |
| npc_sabtang_battery_kw | 120 | kW | NPC_BCS_2023_0570 | 2023-11-21 | medium | verified | Minimum battery power in the bid. |
| npc_sabtang_battery_kwh | 120 | kWh | NPC_BCS_2023_0570 | 2023-11-21 | medium | verified | Minimum battery energy in the bid. |
| ocon2019_pv_capex_usd_per_kw | 1200 | USD/kW | OCON2019 | 2019 | medium | verified | Table 1, PV capex. Transcribed by the user. |
| ocon2019_battery_capex_usd_per_kwh | 260 | USD/kWh | OCON2019 | 2019 | medium | verified | Table 1, battery energy capex. Transcribed by the user. |
| ocon2019_battery_capex_usd_per_kw | 540 | USD/kW | OCON2019 | 2019 | medium | verified | Table 1, battery power (converter) capex. Transcribed by the user. |
| ocon2019_wacc | 0.0994 | fraction per year | OCON2019 | 2019 | medium | verified | WACC for discounted payback and LCOE. Provided by the user. |
| ocon2019_project_life_yr | 20 | years | OCON2019 | 2019 | medium | verified | Project life for discounted payback and LCOE. Provided by the user. |
| cost_high_factor_assumed | 1.25 | multiplier on the base cost | ASSUMPTION |  | low | ASSUMPTION | High cost case: Itbayat is more remote than Sabtang, and the ABC is a 2023 ceiling. Sensitivity range [1.1, 1.5]. |
| esmap2019_minigrid_capex_median_usd_per_kw | 3900 | USD/kW | ESMAP2019 | 2019 | low | verified | Mini-grid capex median, about 3,900 USD/kW; range 1,420 to 22,689 USD/kW. Cross-check only. Provided by the user. |
| irena2025_pv_capex_usd_per_kw | 667 | USD/kW | IRENA2025 | 2026-07 | medium | verified | Utility-scale PV, global weighted-average total installed cost, 2025 (Figure S1, p. 6). Transcribed by the user from the executive summary. Utility-scale reference only. |
| irena2025_battery_capex_usd_per_kwh | 140 | USD/kWh | IRENA2025 | 2026-07 | medium | verified | Four-hour utility-scale battery installed cost, 2025 (p. 3 and p. 8). Transcribed by the user from the executive summary. Utility-scale reference only. |
| fuel_disruption_rate_base_per_yr | 0.85 | events/yr | NEWS_DISRUPTIONS | 2026-10 | low | computed | 4 weather-driven disruptions, Jan 2022 to Oct 2026: Sep 2022 (MB 3 Sep 2022), May-Jun 2023 Typhoon Betty (GMA 29 May 2023; Rappler), Aug 2023 southwest monsoon (Bombo Radyo 5 Aug 2023), Aug 2025 Itbayat food and fuel shortage (Manila Times 5 Aug 2025, [verify] not read). Rate as given by the user (4 / 4.8 y = 0.83). |
| fuel_disruption_rate_high_per_yr | 1.05 | events/yr | NEWS_DISRUPTIONS | 2026-10 | low | computed | Base events plus the Apr 2026 national diesel shortage (GMA). Rate as given by the user (5 / 4.8 y = 1.03). |
| fuel_disruption_rate_low_per_yr | 0.4 | events/yr | NEWS_DISRUPTIONS | 2026-10 | low | computed | All 7 documented disruptions since 2009, adding Sep 2009 (Philstar 15 Sep 2009, fuel ship in dry dock) and Jun-Oct 2011 (Philstar 12 Oct 2011, no funds for diesel). 7 / 17.8 y = 0.39. |
| storm_rate_within_330km_per_yr | 4.15 | events/yr | IBTRACS | 2026-10 | medium | computed | Storm centres at least as close as Mawar 2023 (<= 330 km), typhoon_events.csv, 49 storms in 11.8 y. Upper bound only: most storms did not interrupt fuel supply. |
| npc_offgrid_cost_vs_tariff_ratio | [3, 4] | generation cost / tariff | PHILSTAR2026 | 2026-05-29 | low | verified | Off-grid generation costs NPC 3 to 4 times the tariff it charges (news report). Context only. Provided by the user. |
| npc_itbayat_planned_pv_kwp | 250 | kWp | MB2021 | 2021-05-01 | low | verified | NPC planned 250 kWp of PV for Itbayat (news report). Context only; not used in the model. |
| ocon2019_battery_life_yr | 15 | years | OCON2019 | 2019 | medium | verified | Battery lifetime; the battery (energy and power parts) is replaced in year 15 at the same cost case. Provided by the user. |
| aurora_capex_php_assumed | 2500000 | PHP | ASSUMPTION |  | low | ASSUMPTION | One-off AURORA controller cost: EMS computer, metering and comms links, integration and commissioning on top of the PV and battery controls that B already needs. Sensitivity range [1000000, 5000000]. |
| aurora_opex_php_per_yr_assumed | 500000 | PHP/yr | ASSUMPTION |  | low | ASSUMPTION | Annual AURORA software cost: NWP data, forecast retraining, maintenance and remote support. Sensitivity range [200000, 1000000]. |
| om_frac_of_capex_per_year_assumed | 0.02 | fraction of capex per year | ASSUMPTION |  | low | ASSUMPTION | PV and battery O&M, used for the net payback. Sensitivity range [0.01, 0.03]. |
| sweep_battery_c_rate_cap_kw_assumed | 375 | kW | ASSUMPTION |  | low | ASSUMPTION | Sizing sweep battery power = min(kWh x 1 per h, 375 kW). Reproduces both INL (300 kW / 300 kWh) and case (375 kW / 1,500 kWh). Sensitivity range [250, 500]. |
| co2_shadow_price_php_per_t | 2800 | PHP/t CO2 | ASSUMPTION |  | low | ASSUMPTION | Emissions term of the MPC objective (about 50 USD/t). The Philippines has no carbon price; this is a design weight. Sensitivity range [0, 5600]. |
| distribution_voltage_kv | 0.48 | kV | INL2025 | 2025-01-30 | medium | verified | Primary distribution 480 V; secondary 240 V via step-down transformers. |
| pv_kwp_inl | 300 | kWp | INL2025 | 2025-01-30 | medium | verified |  |
| battery_kw_inl | 300 | kW | INL2025 | 2025-01-30 | medium | verified |  |
| battery_kwh_inl | 300 | kWh | INL2025 | 2025-01-30 | medium | verified |  |
| pv_kwp_case | 500 | kWp | TEAM_CASE |  | low | ASSUMPTION | Illustrative size from the team case study. |
| battery_kwh_case | 1500 | kWh | TEAM_CASE |  | low | ASSUMPTION |  |
| battery_kw_case | 375 | kW | TEAM_CASE |  | low | ASSUMPTION | Battery power of the team case study (0.25 C). Sensitivity range [300, 750]. |
| pv_kwp_npc | 180 | kWp | NPC_MEP2025 | 2025 | high | verified | NPC's own diesel-solar hybridization plan for Itbayat DPP: 180 kWp PV with 120 kWh BESS, budget PHP 51,949,600 (Annex M, pre-implementation); RE compliance from 2028 with 248 MWh/yr of RECs (Annex P). Annex R shows it in 2026. |
| battery_kwh_npc | 120 | kWh | NPC_MEP2025 | 2025 | high | verified |  |
| battery_kw_npc | 120 | kW | ASSUMPTION |  | low | ASSUMPTION | Power rating not stated for Itbayat; the Sabtang bid of the same size asks for at least 120 kW / 120 kWh (NPC_BCS_2023_0570). Sensitivity range [60, 120]. |
| capex_npc_hybrid_php | 51949600 | PHP | NPC_MEP2025 | 2025 | high | verified | Budget requirement for the Itbayat 180 kWp / 120 kWh hybridization, MEP 2025-2029 Annex M. |
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
| flex_feeder_blocks | 4 | blocks | ASSUMPTION |  | low | ASSUMPTION | Flexible (household) load is cut in whole feeder blocks by line staff, not by the exact kW. Model v2; model v1 (Phase 4) shed continuously. Sensitivity range [2, 8]. |
| crit_noise_sigma | 0.12 | fraction | ASSUMPTION |  | low | ASSUMPTION | Hour-to-hour variability of critical demand around its synthetic schedule (AR(1) multiplicative, stationary SD). Model v1 had a fixed schedule. Sensitivity range [0.05, 0.25]. |
| crit_noise_rho | 0.9 | - | ASSUMPTION |  | low | ASSUMPTION | AR(1) coefficient of the critical-demand variability (hourly). Sensitivity range [0.7, 0.97]. |
| fuel_reserve_l_assumed | 250 | L | ASSUMPTION |  | low | ASSUMPTION | Fuel AURORA's plan tries not to go below (about 12 h of one unit at minimum load), so a generator can still start. Fixes the 12.7 L near-miss of model v1. Sensitivity range [0, 500]. |
| operator_plan_delay_days_assumed | 14 | d | ASSUMPTION |  | low | ASSUMPTION | Rationing operator (controller O): once the tanker is overdue, it rations fuel so the tank lasts until this many days after the planned delivery (the longest delay scenario), as NPC and BATANELCO did with curtailment in 2022 and 2023. Sensitivity range [7, 21]. |
| operator_sfc_loading_assumed | 0.7 | fraction | ASSUMPTION |  | low | ASSUMPTION | Average generator loading the operator assumes when converting energy to litres. Sensitivity range [0.5, 0.9]. |
| crit_clinic_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |
| crit_water_kw | 20 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [10, 30]. |
| crit_telecom_kw | 5 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [2.5, 7.5]. |
| crit_municipal_kw | 10 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [5, 15]. |
| crit_cold_storage_kw | 15 | kW | ASSUMPTION |  | low | ASSUMPTION | Sensitivity range [7.5, 22.5]. |

<!-- END VALUE TABLE -->
