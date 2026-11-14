# Phase 4b smoke results (14 Nov 2026)

Model v2 on the SYNTHETIC load calibrated to NPC's annual figures for Itbayat DPP, with the plant fix of
commit "Plant: keep a diesel unit at minimum load". Tanker 14 days late, three real typhoons (Mawar 2023,
Ragasa 2025, Mekkhala 2026), controllers A diesel only, B solar + battery no plan, O careful rationing
operator, C AURORA. Sizes: 500 kWp / 1,000 kWh (`cal_*`) and NPC's planned 180 kWp / 120 kWh (`calnpc_*`).
`year_*`: Nov 2024 to Oct 2025 at 500 kWp / 1,000 kWh, A, B and O only.

These feed the draft impact slide (`impact_smoke.json`, `figures/deck/impact_v2_two_outcomes.png`). The full
Phase 4b run (`python -m aurora.experiments.phase4b run --stage A/B`) replaces them; the size it picks may differ.

**Superseded** by the full run in `results/phase4b/` (14 Nov 2026), which picked 300 kWp / 1,500 kWh.
