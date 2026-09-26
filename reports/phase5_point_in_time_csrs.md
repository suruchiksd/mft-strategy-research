# Phase 5 — Point-in-time historical-universe CSRS

**Overall CSRS decision: FAIL**

**SURVIVORSHIP EFFECT: SEVERE**

## 1. Acceptance and scope

Phase 5 reconstructed 3,381 observed NSE EQ tickers and 3,062,267 canonical symbol/date rows from 2020-01-01 through 2026-09-11. It ranks symbols using only contemporaneous point-in-time eligibility. It is factor-outcome research, not portfolio P&L or execution profitability.

The primary tier excludes intervals outside corporate-action coverage (2020-01-09 through 2026-07-17) and intervals crossing any recorded unresolved, material, or raw conventional unit-changing event. Ledger silence is recorded as no recorded event, not proof of corporate-action completeness. The broad tier retains dates outside ledger coverage but still rejects known blocking crossings.

The base is literal `SERIES=EQ`, which includes some exchange-traded products because no consistent effective-dated common-stock classifier exists in the old format. Observed symbols are never fuzzy-merged. No historical ASM/GSM exclusion is applied because no effective-dated archive exists.

## 2. Bhavcopy audit

The archive contains 1,717 files, 1,660 internal sessions, two formats, 61 filename/internal-date mismatches, and one gzip-wrapped XLSX exception. Internal dates resolve 56 identical repeated sessions. Old turnover is normalized from lakhs; new turnover is already rupees. The detailed preimplementation audit is in `reports/phase5_bhavcopy_audit.md`.

## 3. Historical universe size

| year | universe | median_symbols | current120_pct |
| --- | --- | --- | --- |
| 2020 | BASIC_LIQUID | 736.00 | 13.71 |
| 2020 | BROAD_EQ | 1505.00 | 6.72 |
| 2020 | MODERATE_LIQUID | 413.00 | 21.68 |
| 2021 | BASIC_LIQUID | 1008.00 | 10.32 |
| 2021 | BROAD_EQ | 1545.00 | 6.65 |
| 2021 | MODERATE_LIQUID | 594.50 | 16.48 |
| 2021 | STRICT_SENSITIVITY | 318.00 | 29.06 |
| 2022 | BASIC_LIQUID | 1099.00 | 9.83 |
| 2022 | BROAD_EQ | 1798.00 | 6.08 |
| 2022 | MODERATE_LIQUID | 621.00 | 16.75 |
| 2022 | STRICT_SENSITIVITY | 287.50 | 33.70 |
| 2023 | BASIC_LIQUID | 1191.00 | 9.37 |
| 2023 | BROAD_EQ | 1810.00 | 6.14 |
| 2023 | MODERATE_LIQUID | 773.00 | 14.79 |
| 2023 | STRICT_SENSITIVITY | 365.00 | 28.47 |
| 2024 | BASIC_LIQUID | 1393.00 | 8.05 |
| 2024 | BROAD_EQ | 1887.50 | 6.05 |
| 2024 | MODERATE_LIQUID | 932.50 | 11.84 |
| 2024 | STRICT_SENSITIVITY | 497.00 | 21.30 |
| 2025 | BASIC_LIQUID | 1410.00 | 8.23 |
| 2025 | BROAD_EQ | 2098.50 | 5.44 |
| 2025 | MODERATE_LIQUID | 919.00 | 12.62 |
| 2025 | STRICT_SENSITIVITY | 490.00 | 23.01 |
| 2026 | BASIC_LIQUID | 1536.00 | 7.82 |
| 2026 | BROAD_EQ | 2429.00 | 4.89 |
| 2026 | MODERATE_LIQUID | 1048.00 | 11.50 |
| 2026 | STRICT_SENSITIVITY | 577.50 | 20.20 |

There are 3,261 observed EQ tickers outside the current 120. Current-120 observations represent only the percentages shown above within each point-in-time universe.

## 4. Frozen CSRS evidence

| formation_horizon | mean_ic | positive_pairs | mean_spread |
| --- | --- | --- | --- |
| 5 | -0.035018 | 0 | -0.002055 |
| 10 | -0.026494 | 0 | -0.000174 |
| 20 | -0.017881 | 0 | 0.001378 |
| 40 | -0.011804 | 2 | 0.002040 |
| 60 | -0.004953 | 7 | 0.002945 |

`positive_pairs` is out of 24 primary cells per formation (six outcomes across four universe specifications). All five formations and all six outcomes remain frozen.

## 5. Holdout and chronology

| formation_horizon | mean_holdout_ic | positive_holdout_cells | mean_holdout_spread |
| --- | --- | --- | --- |
| 5 | -0.027679 | 0 | -0.002885 |
| 10 | -0.014946 | 0 | -0.001374 |
| 20 | -0.011974 | 0 | -0.001193 |
| 40 | -0.000314 | 9 | -0.000938 |
| 60 | -0.001588 | 11 | -0.001065 |

Year-by-year results disclose every 2021–2026 evaluation cell in `yearly_results.csv`; development, validation, and 2025–2026 holdout blocks are in `fixed_period_results.csv`.

## 6. Non-overlap, dependence, and multiple testing

| formation_horizon | classification | positive_95pct_ic_intervals | negative_95pct_ic_intervals | bh_fdr_rejections |
| --- | --- | --- | --- | --- |
| 5 | REVERSAL-LIKE | 0 | 23 | 23 |
| 10 | REVERSAL-LIKE | 0 | 21 | 21 |
| 20 | REVERSAL-LIKE | 0 | 18 | 17 |
| 40 | FAIL | 0 | 13 | 13 |
| 60 | INCONCLUSIVE | 0 | 8 | 8 |

Confidence intervals use a deterministic circular moving-block bootstrap with block length `max(10, 2H)`. Null p-values use the same block structure; Benjamini–Hochberg and Holm adjustments are applied to each frozen 30-test family within universe, tier, and statistic. These remain approximate because cross-sectional constituents and outcome windows are dependent.

No positive 40- or 60-session Rank-IC interval excludes zero. Every BH rejection for 40/60 is in the negative direction; no positive 40/60 continuation result survives multiple-testing adjustment.

## 7. Current-120 comparison and survivorship

| analysis_tier | universe | formation_horizon | mean_current120_ic | mean_point_in_time_ic | mean_ic_change | ic_sign_reversals | mean_current120_spread | mean_point_in_time_spread | mean_spread_change | mean_current120_observation_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PRIMARY_VERIFIED | BASIC_LIQUID | 5 | -0.012531 | -0.039327 | -0.026796 | 0 | 0.000672 | -0.002483 | -0.003155 | 9.617494 |
| PRIMARY_VERIFIED | BASIC_LIQUID | 10 | -0.003901 | -0.029181 | -0.025281 | 2 | 0.001740 | -0.000417 | -0.002157 | 9.617494 |
| PRIMARY_VERIFIED | BASIC_LIQUID | 20 | 0.000922 | -0.020409 | -0.021331 | 2 | 0.001683 | 0.000923 | -0.000760 | 9.617494 |
| PRIMARY_VERIFIED | BASIC_LIQUID | 40 | 0.007193 | -0.012148 | -0.019341 | 6 | 0.002350 | 0.001957 | -0.000393 | 9.617494 |
| PRIMARY_VERIFIED | BASIC_LIQUID | 60 | 0.011732 | -0.005679 | -0.017411 | 4 | 0.001118 | 0.002760 | 0.001642 | 9.617494 |
| PRIMARY_VERIFIED | BROAD_EQ | 5 | -0.012531 | -0.042826 | -0.030295 | 0 | 0.000672 | -0.003666 | -0.004338 | 5.996146 |
| PRIMARY_VERIFIED | BROAD_EQ | 10 | -0.003901 | -0.033953 | -0.030052 | 2 | 0.001740 | -0.002343 | -0.004084 | 5.996146 |
| PRIMARY_VERIFIED | BROAD_EQ | 20 | 0.000922 | -0.023657 | -0.024579 | 2 | 0.001683 | -0.001120 | -0.002803 | 5.996146 |
| PRIMARY_VERIFIED | BROAD_EQ | 40 | 0.007193 | -0.017883 | -0.025076 | 6 | 0.002350 | -0.000469 | -0.002819 | 5.996146 |
| PRIMARY_VERIFIED | BROAD_EQ | 60 | 0.011732 | -0.009565 | -0.021296 | 5 | 0.001118 | 0.000778 | -0.000340 | 5.996146 |
| PRIMARY_VERIFIED | MODERATE_LIQUID | 5 | -0.012531 | -0.031870 | -0.019339 | 0 | 0.000672 | -0.001050 | -0.001722 | 15.093831 |
| PRIMARY_VERIFIED | MODERATE_LIQUID | 10 | -0.003901 | -0.022630 | -0.018729 | 2 | 0.001740 | 0.001271 | -0.000470 | 15.093831 |
| PRIMARY_VERIFIED | MODERATE_LIQUID | 20 | 0.000922 | -0.015738 | -0.016660 | 2 | 0.001683 | 0.002811 | 0.001128 | 15.093831 |
| PRIMARY_VERIFIED | MODERATE_LIQUID | 40 | 0.007193 | -0.010545 | -0.017737 | 5 | 0.002350 | 0.003100 | 0.000750 | 15.093831 |
| PRIMARY_VERIFIED | MODERATE_LIQUID | 60 | 0.011732 | -0.003798 | -0.015530 | 4 | 0.001118 | 0.004021 | 0.002903 | 15.093831 |
| PRIMARY_VERIFIED | STRICT_SENSITIVITY | 5 | -0.012531 | -0.026049 | -0.013518 | 0 | 0.000672 | -0.001020 | -0.001692 | 25.955315 |
| PRIMARY_VERIFIED | STRICT_SENSITIVITY | 10 | -0.003901 | -0.020214 | -0.016313 | 2 | 0.001740 | 0.000796 | -0.000944 | 25.955315 |
| PRIMARY_VERIFIED | STRICT_SENSITIVITY | 20 | 0.000922 | -0.011718 | -0.012640 | 2 | 0.001683 | 0.002896 | 0.001213 | 25.955315 |
| PRIMARY_VERIFIED | STRICT_SENSITIVITY | 40 | 0.007193 | -0.006640 | -0.013833 | 5 | 0.002350 | 0.003574 | 0.001224 | 25.955315 |
| PRIMARY_VERIFIED | STRICT_SENSITIVITY | 60 | 0.011732 | -0.000771 | -0.012503 | 4 | 0.001118 | 0.004218 | 0.003100 | 25.955315 |

Across the primary comparisons, the mean absolute formation-level IC change is 0.019913, with 55 horizon-pair sign reversals after aggregation. The detailed 240-row comparison reports IC, spread, year stability, uncertainty, and cross-section changes.

The largest Broad-EQ annual mean-IC changes occur in 2022, 2026 YTD, and 2024:

| year | current120_mean_ic | point_in_time_mean_ic | ic_change |
| --- | --- | --- | --- |
| 2021 | -0.011324 | -0.021007 | -0.009683 |
| 2022 | 0.009920 | -0.036560 | -0.046480 |
| 2023 | -0.016273 | -0.026498 | -0.010225 |
| 2024 | 0.010094 | -0.024071 | -0.034165 |
| 2025 | 0.002449 | -0.013127 | -0.015576 |
| 2026 | 0.020871 | -0.015017 | -0.035888 |

## 8. Software influence

| formation_horizon | max_abs_ic_change | max_abs_spread_change |
| --- | --- | --- |
| 5 | 0.002057 | 0.000720 |
| 10 | 0.002073 | 0.000801 |
| 20 | 0.001682 | 0.000828 |
| 40 | 0.001501 | 0.000554 |
| 60 | 0.003673 | 0.001385 |

This uses only unique current curated software mappings and does not construct a sector factor or claim historical sector membership.

## 9. Formation classifications

| formation_horizon | classification | positive_pairs_broad_eq | positive_pairs_basic_liquid | positive_pairs_moderate_liquid | positive_pairs_strict_sensitivity | positive_holdout_pairs_total | fraction_year_cells_positive | bh_fdr_rejections_across_universes | classification_rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | REVERSAL-LIKE | 0 | 0 | 0 | 0 | 0 | 0.0000 | 23 | frozen_cross_universe_chronology_uncertainty_rule |
| 10 | REVERSAL-LIKE | 0 | 0 | 0 | 0 | 0 | 0.0694 | 21 | frozen_cross_universe_chronology_uncertainty_rule |
| 20 | REVERSAL-LIKE | 0 | 0 | 0 | 0 | 0 | 0.1250 | 17 | frozen_cross_universe_chronology_uncertainty_rule |
| 40 | FAIL | 0 | 0 | 1 | 1 | 9 | 0.2708 | 13 | frozen_cross_universe_chronology_uncertainty_rule |
| 60 | INCONCLUSIVE | 1 | 2 | 2 | 2 | 11 | 0.4236 | 8 | frozen_cross_universe_chronology_uncertainty_rule |

The classifications are based on cross-universe direction, chronological holdout direction, yearly consistency, and dependence/multiple-testing evidence. They do not select or combine a formation horizon.

## 10. Answers to the Phase-5 decision questions

1. The archive contains 3,381 observed EQ tickers; 3,261 are outside the current 120.
2. Yearly median sizes are reported above for every frozen universe.
3. The current 120 represent roughly 5–7% of Broad-EQ observations and 20–34% of Strict observations, depending on year.
4. Five-session reversal persists in every universe, year, holdout, non-overlap view, and dependence-aware test.
5. Forty-session continuation does not persist: mean IC is negative in all four universes and only 2/24 primary pairs are positive.
6. Sixty-session continuation does not persist broadly: mean IC is negative in every universe; only 7/24 pairs are positive, concentrated at longer outcomes.
7. No continuation effect survives consistently across Broad, Basic, Moderate, and Strict universes. Liquidity improves long-outcome tail spreads but not the overall Rank-IC sign.
8. No positive 40/60 Rank-IC result survives BH or Holm adjustment.
9. Dependence-aware intervals do not rescue continuation; none of the positive 40/60 estimates has a wholly positive interval.
10. Software influence is smaller in the broader universe than in the current-120 study and does not restore continuation.
11. Current-universe survivorship bias materially inflated continuation; the measured effect is SEVERE.
12. The reversal direction is stable; continuation is absent or confined to isolated long-outcome/liquidity cells.
13. The overall gate is FAIL; CSRS continuation does not qualify for trading-rule research.

## 11. Limitations

- Corporate-action records lack global ex-date and completeness certification; the primary tier is verified against recorded events only.
- Missing future rows for disappearing securities cannot be converted into delisting returns from Bhavcopy alone.
- Literal EQ includes exchange-traded products and old files lack a consistent security master.
- Static sector mappings are not historical classifications.
- The 2026 primary sample ends 2026-07-17 and is partial.
- Statistical factor validation does not establish turnover economics, execution, transaction costs, drawdown, or portfolio profitability.

## 12. Exact next stage

Do not start portfolio construction from the failed continuation hypothesis. A further data-validity stage, if authorized, should obtain an effective-dated security master/delisting treatment and independently complete corporate-action coverage, then use a new untouched forward window to confirm whether the observed short-horizon reversal is real. Converting reversal into a strategy, changing the CSRS definition, or selecting isolated 60/10–20 cells would be new research and is not authorized here. Sector Relative Momentum and Volume + Momentum remain out of scope.
