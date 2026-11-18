> **Superseded (model v1, Nov 2026).** Current numbers: [`docs/headline_numbers.md`](headline_numbers.md) and the README. Kept for the record.

# Video script: AURORA, 2 minutes

About 300 words of voice-over, which fits 2 minutes at about 150 words a minute. Shots use the figures in `figures/final/` and the slides from `docs/slide_content.md`. Animate a figure by revealing panels or lines in order; do not change the data. Where a number appears on screen, its source is given.

| Time | Shot (on screen) | Voice-over |
|---|---|---|
| 0:00 to 0:12 | Title card: "AURORA". Then panel A of `figa_site_system` with the typhoon tracks drawn in one by one around the Itbayat star. | Itbayat is a small island at the northern tip of the Philippines. About three thousand people live there, and every litre of diesel for their power arrives by sea. |
| 0:12 to 0:30 | Slide 3 table of disruptions, rows appearing year by year (2009, 2011, Sep 2022, May to Jun 2023, Aug 2023, Aug 2025, Apr 2026). Highlight "Bolinao". | When typhoons or monsoon seas stop the tanker, the island runs short. That has happened at least seven times since 2009. Twice the tanker was stuck at Bolinao, hundreds of kilometres away, while the island waited. |
| 0:30 to 0:45 | Panel B of `figa_site_system` (system overview); the AURORA box lights up. Then a single large number: "CEST". | Solar panels and batteries help. But a battery only helps in a crisis if it is charged when the crisis starts. AURORA is a control layer that forecasts sun and demand two days ahead, plans every hour, and shows one number: the Community Energy Survival Time. How many hours could the clinic, the water and the phones keep running if diesel stopped now? |
| 0:45 to 1:10 | `figb_dispatch_mawar14d`: panel A (tank) draws first, then panel B (battery), then panel C (outage bars) with the counts 217 h, 15 h, 0 h. | We tested it in a model of Itbayat with real weather from typhoon Mawar, and a tanker fourteen days late. On diesel alone the clinic goes dark for two hundred and seventeen hours. With solar and a battery on a simple rule, fifteen hours. With AURORA, none. |
| 1:10 to 1:25 | `figc_outage_storms`, all three storms. Then `figd_cest_mawar14d`: the B line sits at zero while the C line holds near the 72-hour cap. | In two later typhoons AURORA kept the loss to one and three hours. In normal weather it keeps about two days of survival time in hand, where the simple rule keeps almost none. |
| 1:25 to 1:40 | `fige_year_diesel_co2`. On screen: "−183,000 L diesel a year", "−490 t CO2 a year" (source: `results/phase4/year.csv`). | Over a normal year, solar and battery halve the island's diesel use: about one hundred and eighty thousand litres and nearly five hundred tonnes of carbon dioxide saved. |
| 1:40 to 1:52 | Slide 9 limits, one line at a time: "synthetic demand", "reanalysis weather", "no field data yet", "economics depend on cost and finance". | We are honest about the limits. The island's demand is modelled, the weather is a reanalysis, and nothing has been tested on site yet. Whether the hardware pays for itself depends on its price and the cost of finance. |
| 1:52 to 2:00 | `figg_sizing_sweep` fading to the title card with the team names. | Next, we want real plant data from the island. Because when the boat cannot come, the hours that matter are the ones you can see coming. |

## Notes for recording

- Say "C E S T" or "survival time"; do not read "CEST" as a word.
- Keep the 217 h, 15 h and 0 h on screen long enough to read (at least 3 s each).
- The disruption list comes from news reports; check the [verify] items in `data/itbayat/SOURCES.md` before recording.
- Do not show the payback figure in the video; it needs the explanation on slide 7 and slide 9.
