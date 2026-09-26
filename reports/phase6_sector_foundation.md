# Phase 6 — Sector Relative Momentum data and methodology foundation

**Foundation decision: CONDITIONAL PASS**

**Historical-sector bias: SEVERE**

## 1. Executive summary

The source audit found 40 current, headerless sector files representing 40 categories. They contain 2,636 physical rows, 1 blank row, 2 duplicate rows, 2,565 distinct symbols, 2,498 uniquely assigned symbols, and 67 symbols assigned to multiple files. No local classification source has historical effective dates.

Direct exact-symbol matching maps 2,180 of 3,381 Phase-5 tickers uniquely; 1,135 are unmapped and 66 conflict. Requiring a non-ambiguous Phase-5 symbol identity leaves 1,988 symbols. Every usable historical observation still relies on a static current label; none is historically verified.

The recommended Phase-7 primary research tier is `STABLE_IDENTITY_BASIC_LIQUID`. It retains 1,547,245 symbol-date observations across 39 sectors. It supports conditional static-classification research, not a genuinely point-in-time sector study.

## 2. Source audit

All 40 curated files parse deterministically by the final underscore in the filename. `construction_supplies_CS.csv` and `sugar_SU.csv` each contain one repeated symbol; `chemicals_CM.csv` contains one blank record. No malformed nonblank record was found. Duplicate physical rows are reported but do not create duplicate membership assignments.

The only separate mapping-shaped local source is a 50-row `stocks_name,sector` Nifty file duplicated byte-for-byte in two projects. It is current/static, has no effective dates, uses broader labels, and cannot establish historical classification. Ranked-universe snapshots and `research_sector_performance.csv` derive their labels from the curated files, so they add no independent provenance. Accepted Bhavcopy identity fields provide partial ISIN evidence only from the new format and contain no sector fields.

## 3. Mapping contract

`sector_research_mapping.parquet` contains one row per exact Phase-5 observed symbol. Conflicts remain null and unresolved; unmapped names remain null. No fuzzy matching or alias stitching occurs. Non-ambiguous exact observed symbols retain themselves as the local identity key; ambiguous identities have no canonical identity assigned.

The provenance states are `STATIC_CURRENT_UNIQUE`, `STATIC_CURRENT_CONFLICT`, and `UNMAPPED`. Historical validity separately records `IDENTITY_AMBIGUOUS`. `HISTORICALLY_VERIFIED` has zero rows because no effective dates were found.

## 4. Historical mapping coverage

| year | universe | eligible_symbols | usable_mapping_symbols | usable_mapping_pct | represented_sectors |
| --- | --- | --- | --- | --- | --- |
| 2020 | BROAD_EQ | 1743 | 1239 | 71.08 | 38 |
| 2021 | BROAD_EQ | 1895 | 1375 | 72.56 | 38 |
| 2022 | BROAD_EQ | 2040 | 1496 | 73.33 | 38 |
| 2023 | BROAD_EQ | 2176 | 1613 | 74.13 | 38 |
| 2024 | BROAD_EQ | 2304 | 1734 | 75.26 | 39 |
| 2025 | BROAD_EQ | 2552 | 1812 | 71.00 | 39 |
| 2026 | BROAD_EQ | 2912 | 1924 | 66.07 | 39 |
| 2020 | BASIC_LIQUID | 1031 | 822 | 79.73 | 37 |
| 2021 | BASIC_LIQUID | 1429 | 1126 | 78.80 | 38 |
| 2022 | BASIC_LIQUID | 1577 | 1243 | 78.82 | 38 |
| 2023 | BASIC_LIQUID | 1689 | 1357 | 80.34 | 38 |
| 2024 | BASIC_LIQUID | 1950 | 1553 | 79.64 | 38 |
| 2025 | BASIC_LIQUID | 1950 | 1498 | 76.82 | 38 |
| 2026 | BASIC_LIQUID | 1953 | 1456 | 74.55 | 39 |
| 2020 | MODERATE_LIQUID | 661 | 546 | 82.60 | 37 |
| 2021 | MODERATE_LIQUID | 1017 | 830 | 81.61 | 37 |
| 2022 | MODERATE_LIQUID | 1056 | 866 | 82.01 | 37 |
| 2023 | MODERATE_LIQUID | 1202 | 1006 | 83.69 | 38 |
| 2024 | MODERATE_LIQUID | 1458 | 1231 | 84.43 | 38 |
| 2025 | MODERATE_LIQUID | 1386 | 1139 | 82.18 | 38 |
| 2026 | MODERATE_LIQUID | 1451 | 1156 | 79.67 | 39 |
| 2021 | STRICT_SENSITIVITY | 536 | 455 | 84.89 | 37 |
| 2022 | STRICT_SENSITIVITY | 538 | 442 | 82.16 | 37 |
| 2023 | STRICT_SENSITIVITY | 716 | 611 | 85.34 | 37 |
| 2024 | STRICT_SENSITIVITY | 913 | 787 | 86.20 | 37 |
| 2025 | STRICT_SENSITIVITY | 882 | 752 | 85.26 | 37 |
| 2026 | STRICT_SENSITIVITY | 968 | 826 | 85.33 | 37 |

Liquid universes improve mapping coverage because the curated files focus on currently active securities. That improvement does not turn static labels into historical labels.

Average usable observation coverage by universe:

| universe | usable_observation_pct |
| --- | --- |
| BASIC_LIQUID | 81.28 |
| BROAD_EQ | 75.05 |
| MODERATE_LIQUID | 83.87 |
| STRICT_SENSITIVITY | 85.38 |

## 5. Sector-size viability

| universe | threshold | mean_symbol_retained_pct | median_usable_sectors_per_date |
| --- | --- | --- | --- |
| BASIC_LIQUID | 3 | 99.63 | 36.00 |
| BASIC_LIQUID | 5 | 98.68 | 35.00 |
| BASIC_LIQUID | 10 | 92.72 | 26.00 |
| BROAD_EQ | 3 | 99.79 | 37.00 |
| BROAD_EQ | 5 | 99.54 | 36.00 |
| BROAD_EQ | 10 | 96.86 | 30.00 |
| MODERATE_LIQUID | 3 | 98.90 | 34.00 |
| MODERATE_LIQUID | 5 | 95.77 | 31.00 |
| MODERATE_LIQUID | 10 | 85.34 | 22.00 |
| STRICT_SENSITIVITY | 3 | 96.37 | 29.00 |
| STRICT_SENSITIVITY | 5 | 89.01 | 23.00 |
| STRICT_SENSITIVITY | 10 | 68.77 | 12.00 |

Thresholds are diagnostics only. They do not change Phase-5 universe membership and no factor or rank is calculated. A five-name threshold retains enough mapped symbol observations in the Basic Liquid tier to be a defensible primary Phase-7 floor, while three and ten names must remain prespecified sensitivity views.

Basic Liquid stable-identity viability by year:

| year | threshold | median_usable_sectors_per_date | min_usable_sectors_per_date | max_usable_sectors_per_date | symbol_observation_retained_pct |
| --- | --- | --- | --- | --- | --- |
| 2020 | 3 | 35.00 | 32 | 36 | 99.18 |
| 2020 | 5 | 28.00 | 23 | 32 | 95.31 |
| 2020 | 10 | 21.00 | 15 | 24 | 86.75 |
| 2021 | 3 | 36.00 | 35 | 36 | 99.69 |
| 2021 | 5 | 34.00 | 31 | 36 | 98.47 |
| 2021 | 10 | 24.00 | 22 | 27 | 91.61 |
| 2022 | 3 | 36.00 | 35 | 37 | 99.69 |
| 2022 | 5 | 35.00 | 32 | 36 | 98.95 |
| 2022 | 10 | 25.00 | 23 | 27 | 92.26 |
| 2023 | 3 | 36.00 | 36 | 37 | 99.64 |
| 2023 | 5 | 35.00 | 34 | 36 | 99.34 |
| 2023 | 10 | 26.00 | 25 | 29 | 93.25 |
| 2024 | 3 | 36.00 | 36 | 37 | 99.74 |
| 2024 | 5 | 36.00 | 35 | 36 | 99.53 |
| 2024 | 10 | 29.00 | 26 | 30 | 95.29 |
| 2025 | 3 | 36.00 | 35 | 36 | 99.72 |
| 2025 | 5 | 36.00 | 34 | 36 | 99.55 |
| 2025 | 10 | 28.00 | 27 | 29 | 94.59 |
| 2026 | 3 | 36.00 | 35 | 37 | 99.77 |
| 2026 | 5 | 35.00 | 34 | 36 | 99.61 |
| 2026 | 10 | 28.00 | 27 | 30 | 95.29 |

Chronically sparse Basic Liquid sectors (median contemporaneous membership below three):

| sector | sector_code | median_stock_count | pct_dates_ge3 | pct_dates_ge5 | dates |
| --- | --- | --- | --- | --- | --- |
| etf | ET | 1.00 | 0.00 | 0.00 | 20 |
| sugar | SU | 1.00 | 11.83 | 0.00 | 1099 |
| ship_building | SB | 2.00 | 0.00 | 0.00 | 1600 |

## 6. Concentration

| universe | median_largest_sector_share_pct | median_top3_sector_share_pct | median_sectors_ge10 |
| --- | --- | --- | --- |
| BASIC_LIQUID | 8.76 | 25.27 | 26.00 |
| BROAD_EQ | 8.22 | 23.44 | 30.00 |
| MODERATE_LIQUID | 9.20 | 24.58 | 22.00 |
| STRICT_SENSITIVITY | 9.83 | 26.56 | 12.00 |

The sector universe is uneven: finance, software, healthcare, automobiles, and capital goods contain many names, while several specialist categories remain sparse. Phase 7 must weight sectors as sector observations rather than allowing stock count alone to make large sectors dominate a sector-level cross-section.

## 7. Static-mapping bias

Historical-sector bias is classified **SEVERE** because 0% of classifications are effective-dated or historically verified. In Broad EQ, static unique labels cover 81.18% of historical symbol-date observations; the stable-identity subset covers 75.09%. There are 312 ambiguous symbol identities, including 192 that otherwise have a unique current mapping. Static mappings can misstate past sector membership after restructurings, business changes, symbol changes, mergers, and delistings. Identity filtering removes objectively ambiguous symbol histories but cannot validate the historical sector itself.

This limitation is strongest among historical names absent from the current mapping and among categories with many conflicts, notably agriculture/sugar and chemicals/fertilisers. It cannot be corrected from the available local data.

## 8. Proposed Phase-7 tiers

| tier | role | universe | require_unique_mapping | require_stable_identity | symbols | historical_observations | observation_pct_of_universe | sector_count | median_stocks_per_sector_date | sector_date_pct_ge3 | sector_date_pct_ge5 | sector_date_pct_ge10 | known_bias | recommended_primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STATIC_UNIQUE_BROAD | SENSITIVITY | BROAD_EQ | True | False | 2180 | 2485936 | 81.18 | 40 | 24.00 | 96.46 | 92.24 | 78.00 | STATIC_CURRENT_CLASSIFICATION_NO_EFFECTIVE_DATES | False |
| STABLE_IDENTITY_BROAD | SENSITIVITY | BROAD_EQ | True | True | 1988 | 2299507 | 75.09 | 39 | 23.00 | 95.56 | 93.09 | 78.62 | STATIC_CURRENT_CLASSIFICATION_NO_EFFECTIVE_DATES | False |
| STABLE_IDENTITY_BASIC_LIQUID | PRIMARY | BASIC_LIQUID | True | True | 1795 | 1547245 | 81.39 | 39 | 16.00 | 95.16 | 90.41 | 68.97 | STATIC_CURRENT_CLASSIFICATION_NO_EFFECTIVE_DATES | True |
| STABLE_IDENTITY_MODERATE_LIQUID | SENSITIVITY | MODERATE_LIQUID | True | True | 1485 | 987205 | 84.08 | 39 | 11.00 | 91.89 | 80.17 | 56.93 | STATIC_CURRENT_CLASSIFICATION_NO_EFFECTIVE_DATES | False |

Primary: `STABLE_IDENTITY_BASIC_LIQUID` with a prespecified minimum sector size of five. Sensitivities: the same tier at three and ten names; `STABLE_IDENTITY_MODERATE_LIQUID` for liquidity; `STABLE_IDENTITY_BROAD` for breadth; and `STATIC_UNIQUE_BROAD` to measure identity-filter impact. Results must be labelled static-current-classification historical research.

## 9. Decision

**CONDITIONAL PASS**. Factor 2 can be researched responsibly only as a conditional static-classification study. Coverage and sector sizes are sufficient in the stable-identity liquid tier, but the absence of effective-dated classifications prevents an unconditional point-in-time claim.

## 10. Exact Phase-7 design

1. Freeze the four tiers and sector-size thresholds (3, 5, 10), with Stable Identity + Basic Liquid and at least five contemporaneous names as primary.
2. Preregister sector-return aggregation, formation horizons, outcome labels, tie handling, and interval safety before viewing factor results.
3. Calculate sector momentum only within each contemporaneous tier/date, report all prespecified parameter cells, and keep stock-level and sector-level sample counts explicit.
4. Repeat chronological holdout, non-overlap, dependence-aware uncertainty, concentration, sector influence, and static-mapping sensitivity analyses.
5. Keep Factor 1B reversal, Volume + Momentum, factor combinations, trading rules, and portfolios outside Phase 7.

No sector return, sector momentum, ranking, combined score, or portfolio/trading P&L was generated in Phase 6.
