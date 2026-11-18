> **Superseded (model v1, Nov 2026).** Current numbers: [`docs/headline_numbers.md`](headline_numbers.md) and the README. Kept for the record.

# Slide content: AURORA, Global Sustainability Challenge 2026-27 (Sustainable Energy)

Nine slides in the GSC template order. Each slide has a headline, the text, the figure and where every number comes from. Figures are in `figures/final/` (PDF for print, PNG for the deck). Keep text short on the slide; the detail is for the speaker notes.

Numbers come from `results/phase4/` and `docs/results_summary.md`. News items are evidence of events only; several are still marked [verify] in `data/itbayat/SOURCES.md` and must be checked before submission.

---

## 1. Title

**AURORA: keeping the lights on when the fuel boat cannot come**

Forecast-driven, resilience-aware energy management for remote diesel-backed solar microgrids. Case study: Itbayat island, Batanes, Philippines.

Team names, university, GSC 2026-27, Sustainable Energy theme.

Figure: none, or a cropped panel A of `figa_site_system.png` (Itbayat and the typhoon tracks) as a background strip.

---

## 2. Summary

**One island, one question: if diesel stopped now, how long would the clinic keep running?**

- Itbayat (about 3,100 people) runs on diesel brought by sea. Storms and monsoon seas stop the tanker.
- AURORA forecasts sun and demand 48 hours ahead, plans the solar, battery and diesel every hour, and shows one number: the Community Energy Survival Time (CEST).
- In a simulated 14-day fuel delay during typhoon Mawar, critical services lose **217 h** of power on diesel alone, **15 h** with solar and battery on a simple rule, and **0 h** with AURORA.
- Solar and battery halve diesel use (−183,000 L and −490 t CO2 a year); AURORA keeps a median of **52 h** of survival time in hand, against 0 h for the simple rule.

Figure: `figc_outage_storms.png` (small) or the three-number row from slide 7.

Sources: `rec_storms.csv`; `year.csv`.

---

## 3. Problem

**Every few years, Batanes runs short of diesel.**

Documented fuel disruptions to Batanes power:

| When | What happened | Source |
|---|---|---|
| Sep 2009 | Fuel ship in dry dock | Philstar, 15 Sep 2009 |
| Jun to Oct 2011 | No funds for diesel | Philstar, 12 Oct 2011 |
| Sep 2022 | Fuel disruption | Manila Bulletin, 3 Sep 2022 |
| May to Jun 2023 | Typhoon Betty (Mawar) | GMA News, 29 May 2023; Rappler |
| Aug 2023 | Southwest monsoon | Bombo Radyo Tuguegarao, 5 Aug 2023 |
| Aug 2025 | Itbayat food and fuel shortage | Manila Times, 5 Aug 2025 [verify: not yet read] |
| Apr 2026 | National diesel shortage | GMA News, Apr 2026 |

- Four weather-driven disruptions since Jan 2022, about **0.85 a year**.
- In two events the tanker was stranded at **Bolinao, Pangasinan**, in monsoon weather: the risk lies along the whole shipping route, not only at the island.
- The island holds about **2 months** of fuel; diesel costs about **113 PHP/L**; peak demand is about **250 kW** (INL, 2025).
- Off-grid power already costs NPC **3 to 4 times** the tariff it charges (Philstar, 29 May 2026).

Figure: `figa_site_system.png`, panel A (map of the Luzon Strait with the three storm tracks, the 300 and 500 km rings around Itbayat, the schematic fuel route from Bolinao and an inset of the Batanes islands).

Speaker note: a diesel-only island has no buffer. When the tank is empty, the clinic, the water pumps and the phone tower go dark together.

---

## 4. Idea

**Plan with the forecast, protect what matters, and show how long the island can last.**

- **Forecast** sun and demand 48 hours ahead with uncertainty bands (P10, P50, P90), corrected from global weather models with machine learning.
- **Plan** every hour: an optimiser decides when to run diesel, charge the battery and, if fuel is running out, shed flexible load early so that critical load never goes dark.
- **Show** one number to the operator: CEST, the hours the clinic, water and phones could run on battery and sun alone if diesel stopped now.

Figure: `figa_site_system.png`, panel B (system overview with the AURORA layer).

---

## 5. What's new

**Not just less diesel: a controller built for the day the fuel does not come.**

- **Fuel-aware planning.** AURORA tracks the tank and the late tanker as uncertain (3, 7 or 14 days) and starts protecting critical load before the tank is empty.
- **Survival time as the target.** It keeps the battery charged for resilience, not only for cost. Median CEST in a normal year is 52 h against 0 h for a simple rule.
- **A forecast that beats its inputs.** Solar forecast error is 11 % (day 1) and 8 % (day 2) below ECMWF, the leading global model, and 46 to 47 % below persistence, with calibrated bands (80 % band covers 81.7 %).
- **Honest about what it is worth.** The better forecast trims diesel and shedding only a little in storms; most of the resilience comes from fuel-aware planning.

Figure: `figf_forecast_skill.png` (forecast skill by lead day) next to `figd_cest_mawar14d.png` (share of each day's hours with at least 24 h of survival time: AURORA 73 %, simple rule 26 % while the tanker is late).

Sources: `docs/validation_forecast.md`; `year.csv`; `results/phase4/vof.csv`.

---

## 6. Plan

**From simulation to the island.**

1. **Now (done):** site data, forecast, digital twin with AURORA, three real typhoons, two full years, sizing and costs. All open code; every number has a source or is marked as an assumption.
2. **Next 3 months:** get real plant logs and fuel records from NPC-SPUG; replace the synthetic demand and the assumed tank size; rerun.
3. **Pilot (6 to 12 months):** run AURORA in advisory mode beside the operator on an island where NPC is already installing solar and battery (Sabtang bid 2023; 250 kWp planned for Itbayat), showing CEST on a simple screen.
4. **Then:** closed-loop control once the advisory results are trusted.

Figure: `figb_dispatch_mawar14d.png` (what the operator would see: tank, battery and critical load through the storm).

---

## 7. Impact

**Critical services stay on through a 14-day fuel delay.**

Three numbers, all from the recommended system (500 kWp solar, 375 kW / 1,000 kWh battery):

- **217 h → 0 h** critical outage in typhoon Mawar with the tanker 14 days late (1 h and 3 h in two later typhoons). Source: `rec_storms.csv`.
- **−183,000 litres of diesel and −490 t of CO2 a year**, mostly from adding solar and battery. Source: `year.csv`.
- **52 h** median survival time in a normal year, against 0 h for a simple rule. Source: `year.csv`.

Figure: `figc_outage_storms.png` (main), `fige_year_diesel_co2.png` (small).

Speaker note on cost: AURORA does the job of a much bigger battery. With the simple rule the same system needs 2,000 kWh of battery instead of 1,000 kWh to get close (1 h of outage instead of 0 h); that extra battery costs about 48 M PHP, AURORA about 6.8 M PHP over 20 years (`figg_sizing_sweep.png`). The solar and battery themselves break even at 68 to 98 % of NPC's Sabtang bid price (`figh_hardware_payback.png`); NPC is building such systems anyway.

---

## 8. Growth

**634 off-grid islands in the Philippines alone.**

- Castro et al. (2022) analysed solar, battery and diesel hybrid systems for 634 Philippine off-grid islands.
- AURORA needs only public weather data, the plant's own meters and its fuel records, so it can be added to any hybrid system NPC installs.
- The same approach fits island grids across Southeast Asia and the Pacific that face typhoons and long fuel routes.
- Sizing: AURORA also tells planners how much battery is enough. On Itbayat, beyond 1,000 kWh at 500 kWp, extra battery stops adding resilience.

Figure: `figg_sizing_sweep.png` (where extra battery stops adding survival time, and how much more battery the simple rule needs to match AURORA).

---

## 9. Extras

**Limits, stated plainly, and what we would need.**

- The island's demand is **synthetic** (no hourly data is public); the weather is **ERA5 reanalysis**, not a measurement; there are **no field data**.
- Fuel tank size, delivery interval and diesel unit ratings are **assumptions**; results are most sensitive to fuel in the tank when the tanker is late.
- **Hardware economics depend on capital cost and finance**: no payback at the Sabtang price and 9.94 %; break-even at 68 to 98 % of that price; about 4 years at cheaper published costs.
- Survival time is capped at 72 h in the model.
- What would help most: plant logs, fuel delivery records and tank size from NPC-SPUG.

Figure: `figh_hardware_payback.png` (20-year NPV against installed cost, with the break-even price marked).

Links: code and data repository; `docs/results_phase4.md`; `docs/results_summary.md`.
