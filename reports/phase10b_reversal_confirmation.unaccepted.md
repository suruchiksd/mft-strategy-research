# Phase 10B — Preregistered Cross-Sectional Reversal Confirmation

**Overall Phase-10 decision: FAIL**

This report separates historical discovery evidence from the untouched post-2026-07-17 confirmation. It remains factor research; no factor combination, trading rule, or portfolio was created.

## A. Corporate-action extension

The frozen official-NSE extension received **CONDITIONAL PASS FOR REVERSAL CONFIRMATION**. It preserves structured official responses through 2026-09-11, uses official ex-date as the blocking date, maps symbols exactly without fuzzy matching, and blocks splits, bonuses, rights, reorganizations, unknown purposes, and identifier conflicts. Overlap recovered 60/61 accepted blocking events. GUJGASLTD was the sole false negative, and its price series ended before the missed event. Extension build `8ad77b280031a1f9d99f6ce85a2078e6f6457a3ffdc39a9a0c6e9857225abc13` was frozen before this confirmation inspected outcomes.

## B. Discovery evidence

The accepted Phase-9 controls were reoriented mathematically before confirmation: REV05 and REV20 each had positive historical Rank IC at all six outcomes. These 2020-01-01 through 2026-07-17 results are discovery evidence, not out-of-sample evidence.

## C. Untouched confirmation coverage

Signal dates begin strictly after 2026-07-17. Every admitted outcome ends by the certified price/corporate-action boundary of 2026-09-11.

| candidate_id | future_horizon | first_confirmation_signal_date | last_usable_signal_date | valid_dates | stock_observations |
| --- | --- | --- | --- | --- | --- |
| REV05 | 1 | 2026-07-20 | 2026-09-10 | 39 | 55580 |
| REV05 | 2 | 2026-07-20 | 2026-09-09 | 38 | 53995 |
| REV05 | 3 | 2026-07-20 | 2026-09-08 | 37 | 52410 |
| REV05 | 5 | 2026-07-20 | 2026-09-04 | 35 | 49273 |
| REV05 | 10 | 2026-07-20 | 2026-08-28 | 30 | 41606 |
| REV05 | 20 | 2026-07-20 | 2026-08-14 | 20 | 26870 |
| REV20 | 1 | 2026-07-20 | 2026-09-10 | 39 | 54277 |
| REV20 | 2 | 2026-07-20 | 2026-09-09 | 38 | 52734 |
| REV20 | 3 | 2026-07-20 | 2026-09-08 | 37 | 51194 |
| REV20 | 5 | 2026-07-20 | 2026-09-04 | 35 | 48161 |
| REV20 | 10 | 2026-07-20 | 2026-08-28 | 30 | 40737 |
| REV20 | 20 | 2026-07-20 | 2026-08-14 | 20 | 26508 |

## D. Confirmation evidence

- **REV05**: mean IC across horizons 0.002651; positive primary 4/6; positive MODERATE 4/6; positive non-overlap means 4/6; 95% IC intervals above zero 2/6; classification **CONTRADICTORY**.
- **REV20**: mean IC across horizons -0.018339; positive primary 1/6; positive MODERATE 2/6; positive non-overlap means 1/6; 95% IC intervals above zero 0/6; classification **CONTRADICTORY**.

Complete deciles, tails, every non-overlap offset, deterministic circular-block intervals, universe sensitivity, and leave-one-date influence are in the companion CSVs. A factor rank is fixed from signal-valid stocks before outcome availability is applied.

## E. Interpretation

The preregistered evaluability floor is 20 daily IC dates for every horizon and the `SUPPORTED` threshold is 60. These thresholds were not changed. The classifications reflect direction, BASIC/MODERATE consistency, non-overlap results, and whether dropping one date flips a supporting sign. Confidence intervals are descriptive in this short untouched sample.

The exact next stage is to follow the frozen classification gate. If Phase 10 does not pass, collect more genuinely untouched certified dates under the same definitions. If it passes conditionally, a separately authorized complementarity study may test reversal alongside Sector Relative Momentum with its design frozen first. Phase 11 was not started.

Build ID: `359d9317148bcde3376c2c9703f0836c12056ae634df5476c7ecb79b2e84ae68`.
