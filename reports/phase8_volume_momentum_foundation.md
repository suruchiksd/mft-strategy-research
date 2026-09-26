# Phase 8 — Volume + Momentum Foundation

**Research scope: outcome-blind data and methodology foundation. No future returns or predictive-performance statistics were calculated.**

**Decision: CONDITIONAL PASS**

## 1. Volume audit

The accepted historical dataset contains 3,062,267 EQ symbol/date rows, 3,381 observed symbols, and 1,660 exchange sessions. It contains 0 null, 0 zero, and 0 negative volume observations.

| source_format | first_date | last_date | observations | symbols | raw_volume_field | volume_unit | turnover_implied_price_to_close_median | compatibility_assessment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NEW | 2024-07-08 | 2026-09-11 | 1182056 | 3019 | TtlTradgVol | shares | 1.0013 | COMPATIBLE_SHARE_UNITS_NO_DUAL_FORMAT_OVERLAP |
| OLD | 2020-01-01 | 2024-07-05 | 1880211 | 2525 | TTL_TRD_QNTY | shares | 1.0022 | COMPATIBLE_SHARE_UNITS_NO_DUAL_FORMAT_OVERLAP |

OLD `TTL_TRD_QNTY` and NEW `TtlTradgVol` both represent traded shares. Turnover normalization independently reconciles with traded quantity and prices. There are no dates recorded in both formats, so compatibility is supported by schema semantics and continuity diagnostics rather than a same-date dual-format comparison.

## 2. Normalization and coverage

| feature | coverage_pct |
| --- | --- |
| log_volume_surprise_20 | 96.1912 |
| log_volume_surprise_60 | 93.5531 |
| price_return_20 | 96.1912 |
| price_return_5 | 96.5943 |

| feature | count | median | std | p99 | max |
| --- | --- | --- | --- | --- | --- |
| volume_ratio_20 | 1828715 | 0.7127 | 5.5862 | 8.7092 | 4883.6448 |
| volume_ratio_60 | 1778562 | 0.6794 | 4.0419 | 9.3139 | 1620.2495 |
| volume_median_ratio_20 | 1828715 | 0.9755 | 15.0446 | 16.1968 | 7949.4167 |
| volume_median_ratio_60 | 1778562 | 1.0151 | 15.1485 | 19.0819 | 11028.4035 |
| log_volume_surprise_20 | 1828715 | -0.1004 | 0.8025 | 2.6056 | 8.8790 |
| log_volume_surprise_60 | 1778562 | -0.0681 | 0.8562 | 2.7846 | 8.9073 |

All baselines use exactly the prior 20 or 60 exchange sessions and exclude today's volume. Missing sessions, unsafe rows, recorded blocking corporate-action crossings, and dates outside certified corporate-action coverage invalidate the feature explicitly.

Raw mean and median ratios are heavy-tailed. A trailing median is resistant to contamination from prior spikes but produces larger current-day ratios when a spike occurs. Log-volume surprise has materially more stable scale and is retained in the Phase-9 registry; raw mean and median ratios remain in the foundation dataset for audit and sensitivity.

## 3. Corporate-action and listing effects

The action-proximity audit contains 121 action-class/impact/relative-session summaries. Event-date results use recorded source dates, which are not globally verified ex-dates. Feature intervals crossing raw conventional, material unresolved, or ambiguous events are invalidated; no price or volume adjustment factor was applied.

| research_impact | source_events | matched_observations | volume_ratio_20_median | volume_ratio_20_p95 |
| --- | --- | --- | --- | --- |
| LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION | 41 | 41 | 2.8382 | 22.3204 |
| MATERIAL_UNRESOLVED_EVENT | 296 | 180 | 1.4798 | 6.7766 |
| NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM | 8729 | 8044 | 0.7432 | 2.8549 |
| UNKNOWN_OR_AMBIGUOUS | 496 | 403 | 4.8478 | 30.2674 |

First-observation volume is materially more dispersed than established-history volume, so required history is enforced rather than backfilled. Corporate-action ledger silence remains absence of a recorded event, not proof of complete action coverage.

## 4. Stability and redundancy

The normalization correlation audit reports 224 pair/year rows. Mean-ratio, median-ratio, and log-surprise orderings are highly redundant: the all-period 20-session Spearman correlations are above 0.94 for mean/log and above 0.98 for median/log. Across 20 versus 60 sessions, log surprise is also strongly correlated. This is why the registry retains log surprise only rather than multiplying nearly identical hypotheses.

The final seven-candidate registry has 0 pair(s) above the absolute Spearman redundancy threshold of 0.90. One redundant short sign-only interaction was removed before any outcome research; no replacement was added.

## 5. Frozen Phase-9 candidate registry

| candidate_id | name | role | price_component | volume_component | baseline_horizon | directionality |
| --- | --- | --- | --- | --- | --- | --- |
| VM01 | PRICE_RETURN_5_CONTROL | CONTROL_PRICE | price_return_5 | NONE | 0 | DIRECTIONAL_PRICE |
| VM02 | PRICE_RETURN_20_CONTROL | CONTROL_PRICE | price_return_20 | NONE | 0 | DIRECTIONAL_PRICE |
| VM03 | LOG_VOLUME_SURPRISE_20_CONTROL | CONTROL_VOLUME | NONE | log_volume_surprise_20 | 20 | NON_DIRECTIONAL_VOLUME |
| VM04 | LOG_VOLUME_SURPRISE_60_CONTROL | CONTROL_VOLUME | NONE | log_volume_surprise_60 | 60 | NON_DIRECTIONAL_VOLUME |
| VM05 | PRICE5_X_HIGH_VOLUME20 | INTERACTION | price_return_5 | log_volume_surprise_20 | 20 | SIGNED_BY_PRICE_MAGNITUDE |
| VM06 | PRICE20_X_HIGH_VOLUME20 | INTERACTION | price_return_20 | log_volume_surprise_20 | 20 | SIGNED_BY_PRICE_MAGNITUDE |
| VM07 | SIGNED_HIGH_VOLUME20_60 | INTERACTION | sign(price_return_20) | log_volume_surprise_60 | 60 | UP_VERSUS_DOWN |

The controls keep price, volume, and interaction hypotheses separate. All Phase-9 stock rankings must be same-date and within the selected universe. The 1%/99% winsorization applies only to the contemporaneous volume component of interaction candidates; raw source data is preserved.

## 6. Direct answers

1. Historical volume is sufficiently reliable for controlled Factor-3 research: fields are complete and nonnegative, but corporate-action completeness and the non-overlapping format transition remain limitations.
2. OLD and NEW volume fields are compatible share-count fields. No dual-format same-day sample exists for perfect empirical reconciliation.
3. Zero, missing, and negative volume affect 0 accepted EQ rows; zero turnover affects 1,078 rows and is disclosed separately.
4. Corporate-action distortions are material: recorded conventional, material-unresolved, and ambiguous event dates have median 20-session volume ratios well above ordinary non-price-adjustment actions. Recorded blocking crossings are excluded, but source dates and ledger completeness are not globally certified.
5. Log-volume surprise is the most numerically stable candidate normalization. Raw ratios remain useful diagnostics but have extreme right tails.
6. Median baselines resist prior spikes better, while mean baselines shrink subsequent ratios; median ratios have the heavier current-spike tail. Their rankings are too redundant to preregister both.
7. Both 20- and 60-session baselines are usable, with explicit history and continuity requirements.
8. Yearly log-surprise scale is broadly stable; detailed shifts are disclosed in `feature_distribution_yearly.csv`.
9. Feature completeness and raw-volume stability improve with liquidity restrictions; Broad EQ remains an audit tier rather than the proposed primary research universe.
10. Mean ratio, median ratio, and log surprise are highly redundant within a baseline; 20- and 60-session log surprises are also correlated but preserve distinct baseline hypotheses.
11. Phase 9 should test exactly the seven frozen candidates in the registry and no additions.
12. The primary universe is BASIC_LIQUID.
13. MODERATE_LIQUID is the prespecified sensitivity universe.
14. Volume + Momentum research can proceed responsibly under the CONDITIONAL PASS gate.

## 7. Decision and exact Phase-9 design

**CONDITIONAL PASS**

If authorized, Phase 9 should load this immutable foundation and test the seven registry candidates independently in BASIC_LIQUID, with MODERATE_LIQUID as the sole universe sensitivity. It should preregister future horizons before outcome construction, use same-date percentile ranks, report component controls before interactions, apply the frozen interval-validity columns, use chronological validation, non-overlapping outcomes, dependence-aware intervals, and multiple-testing correction across the seven-candidate family. It must not add candidates, combine Factor 2, choose a winning horizon from the full sample, or run a portfolio backtest.

The condition reflects the lack of a same-date OLD/NEW overlap and the accepted corporate-action ledger's source-date/completeness limitations. No future-return, factor-performance, trading, portfolio, Factor-1, or Factor-2 value was created.
