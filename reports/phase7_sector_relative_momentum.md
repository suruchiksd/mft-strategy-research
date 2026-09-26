# Phase 7 — Sector Relative Momentum

**Research label: STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH**

**Overall Factor-2 decision: CONDITIONAL PASS**

## 1. Acceptance and construction

Phase 7 built successfully from accepted Phase-5 and Phase-6 artifacts. The primary panel has 60,312 sector/date rows, 53,089 valid equal-weight daily sector returns (88.02%), 36 sectors, and certified valid daily coverage from 2020-03-27 through 2026-07-17.

Daily sector returns use only that date's Basic Liquid, exact unique-mapped, stable-identity constituents. Each stock return requires safe adjacent-session endpoints and the accepted Phase-5 corporate-action coverage/crossing rules. Formation windows compound the historical daily sector-return sequence; date-T membership is never backfilled. Outcomes begin at T+1.

The primary sector-size floor is five. Equal weighting is applied across valid constituent stock returns, and every sector remains one observation in sector ranking regardless of its stock count.

## 2. Rank-IC evidence

| formation_horizon | mean_ic | positive_pairs | mean_q5_q1 | positive_q_spreads |
| --- | --- | --- | --- | --- |
| 5 | 0.051663 | 6 | 0.003217 | 6 |
| 10 | 0.063081 | 6 | 0.004200 | 6 |
| 20 | 0.075691 | 6 | 0.004764 | 6 |
| 40 | 0.067782 | 6 | 0.004194 | 6 |
| 60 | 0.063780 | 6 | 0.004074 | 6 |

All 30 frozen formation/outcome pairs are reported. Positive future sector returns alone are not treated as evidence; the decision uses cross-sector Rank IC, tail spreads, chronology, dependence-aware uncertainty, and sensitivities.

Evidence by future outcome horizon:

| future_horizon | mean_ic | positive_pairs | mean_q5_q1 |
| --- | --- | --- | --- |
| 1 | 0.040292 | 5 | 0.000832 |
| 2 | 0.045599 | 5 | 0.001431 |
| 3 | 0.053134 | 5 | 0.001991 |
| 5 | 0.063399 | 5 | 0.003298 |
| 10 | 0.083739 | 5 | 0.006324 |
| 20 | 0.100233 | 5 | 0.010662 |

## 3. Quintiles and tails

| formation_horizon | mean_q5_q1 | positive_pairs | mean_monotonicity | mean_q1 | mean_q5 |
| --- | --- | --- | --- | --- | --- |
| 5 | 0.003217 | 6 | 0.966667 | 0.007521 | 0.010449 |
| 10 | 0.004200 | 6 | 1.000000 | 0.007103 | 0.011046 |
| 20 | 0.004764 | 6 | 1.000000 | 0.006856 | 0.011497 |
| 40 | 0.004194 | 6 | 1.000000 | 0.006893 | 0.010970 |
| 60 | 0.004074 | 6 | 1.000000 | 0.006815 | 0.010454 |

Quintiles are assigned only when at least 15 formation-valid sectors exist. Q5 is strongest and Q1 weakest. Detailed pooled distributions and Top/Bottom 20% and three-sector diagnostics are in the companion CSVs.

## 4. Year and holdout stability

| formation_horizon | positive_year_cells | negative_year_cells | total_year_cells | median_year_ic |
| --- | --- | --- | --- | --- |
| 5 | 42 | 0 | 42 | 0.050067 |
| 10 | 42 | 0 | 42 | 0.057678 |
| 20 | 41 | 1 | 42 | 0.076331 |
| 40 | 42 | 0 | 42 | 0.059943 |
| 60 | 42 | 0 | 42 | 0.064769 |

| formation_horizon | holdout_mean_ic | positive_holdout_pairs | holdout_mean_q5_q1 |
| --- | --- | --- | --- |
| 5 | 0.048942 | 6 | 0.002603 |
| 10 | 0.064441 | 6 | 0.003552 |
| 20 | 0.074680 | 6 | 0.004229 |
| 40 | 0.065055 | 6 | 0.003160 |
| 60 | 0.047154 | 6 | 0.002249 |

The fixed holdout is 2025-01-01 through the certified cutoff 2026-07-17. Expanding folds use only history ending before each evaluation year; no parameters are fit or selected in those histories.

## 5. Non-overlap and uncertainty

| formation_horizon | nonoverlap_mean_ic | positive_nonoverlap_pairs |
| --- | --- | --- |
| 5 | 0.051669 | 6 |
| 10 | 0.063069 | 6 |
| 20 | 0.075689 | 6 |
| 40 | 0.067782 | 6 |
| 60 | 0.063779 | 6 |

| formation_horizon | positive_95pct_intervals | negative_95pct_intervals |
| --- | --- | --- |
| 5 | 6 | 0 |
| 10 | 6 | 0 |
| 20 | 6 | 0 |
| 40 | 6 | 0 |
| 60 | 6 | 0 |

All H offsets of H-spaced exchange-session observations are retained. Confidence intervals use a deterministic circular moving-block bootstrap with 2,000 replications and block length max(10, 2H). P-values are two-sided null probabilities from centered series with the same block construction.

## 6. Multiple testing

| formation_horizon | bh_positive | holm_positive |
| --- | --- | --- |
| 5 | 6 | 6 |
| 10 | 6 | 6 |
| 20 | 6 | 6 |
| 40 | 6 | 6 |
| 60 | 6 | 6 |

Benjamini-Hochberg and Holm corrections cover exactly the 30 primary Rank-IC hypotheses. Negative rejections are labelled negative relationships and are not counted as successful momentum.

## 7. Sector-size sensitivity

| minimum_sector_size | formation_horizon | mean_ic | positive_pairs | sign_preservation |
| --- | --- | --- | --- | --- |
| 3 | 5 | 0.046684 | 6 | 1.000000 |
| 3 | 10 | 0.058157 | 6 | 1.000000 |
| 3 | 20 | 0.072351 | 6 | 1.000000 |
| 3 | 40 | 0.064506 | 6 | 1.000000 |
| 3 | 60 | 0.058491 | 6 | 1.000000 |
| 5 | 5 | 0.051663 | 6 | 1.000000 |
| 5 | 10 | 0.063081 | 6 | 1.000000 |
| 5 | 20 | 0.075691 | 6 | 1.000000 |
| 5 | 40 | 0.067782 | 6 | 1.000000 |
| 5 | 60 | 0.063780 | 6 | 1.000000 |
| 10 | 5 | 0.066449 | 6 | 1.000000 |
| 10 | 10 | 0.075584 | 6 | 1.000000 |
| 10 | 20 | 0.096358 | 6 | 1.000000 |
| 10 | 40 | 0.092537 | 6 | 1.000000 |
| 10 | 60 | 0.088039 | 6 | 1.000000 |

The 3, 5, and 10 thresholds were frozen before results and are all disclosed. The primary remains five regardless of which threshold performs best.

## 8. Universe and mapping sensitivity

| research_tier | formation_horizon | mean_ic | positive_pairs | sign_preservation |
| --- | --- | --- | --- | --- |
| STABLE_IDENTITY_BASIC_LIQUID | 5 | 0.051663 | 6 | 1.000000 |
| STABLE_IDENTITY_BASIC_LIQUID | 10 | 0.063081 | 6 | 1.000000 |
| STABLE_IDENTITY_BASIC_LIQUID | 20 | 0.075691 | 6 | 1.000000 |
| STABLE_IDENTITY_BASIC_LIQUID | 40 | 0.067782 | 6 | 1.000000 |
| STABLE_IDENTITY_BASIC_LIQUID | 60 | 0.063780 | 6 | 1.000000 |
| STABLE_IDENTITY_BROAD | 5 | 0.065607 | 6 | 1.000000 |
| STABLE_IDENTITY_BROAD | 10 | 0.079358 | 6 | 1.000000 |
| STABLE_IDENTITY_BROAD | 20 | 0.091948 | 6 | 1.000000 |
| STABLE_IDENTITY_BROAD | 40 | 0.073612 | 6 | 1.000000 |
| STABLE_IDENTITY_BROAD | 60 | 0.071890 | 6 | 1.000000 |
| STABLE_IDENTITY_MODERATE_LIQUID | 5 | 0.054602 | 6 | 1.000000 |
| STABLE_IDENTITY_MODERATE_LIQUID | 10 | 0.061813 | 6 | 1.000000 |
| STABLE_IDENTITY_MODERATE_LIQUID | 20 | 0.076016 | 6 | 1.000000 |
| STABLE_IDENTITY_MODERATE_LIQUID | 40 | 0.061553 | 6 | 1.000000 |
| STABLE_IDENTITY_MODERATE_LIQUID | 60 | 0.063713 | 6 | 1.000000 |
| STATIC_UNIQUE_BROAD | 5 | 0.064169 | 6 | 1.000000 |
| STATIC_UNIQUE_BROAD | 10 | 0.077754 | 6 | 1.000000 |
| STATIC_UNIQUE_BROAD | 20 | 0.090844 | 6 | 1.000000 |
| STATIC_UNIQUE_BROAD | 40 | 0.071304 | 6 | 1.000000 |
| STATIC_UNIQUE_BROAD | 60 | 0.071130 | 6 | 1.000000 |

The Basic Liquid stable-identity tier remains primary. Moderate Liquid, stable Broad, and static-unique Broad are sensitivity views and cannot replace it after observing results.

## 9. Sector influence and concentration

| formation_horizon | max_abs_ic_change | max_abs_spread_change |
| --- | --- | --- |
| 5 | 0.006263 | 0.000973 |
| 10 | 0.009179 | 0.001057 |
| 20 | 0.009804 | 0.001135 |
| 40 | 0.009106 | 0.001070 |
| 60 | 0.008767 | 0.001206 |

Leave-one-sector-out results retain every sector in the official evidence. The detailed output identifies finance, software, healthcare, automobiles, capital goods, and any other sector with larger influence without constructing a sector-specific strategy.

## 10. Formation classifications

| research_label | formation_horizon | classification | positive_primary_pairs | negative_primary_pairs | positive_holdout_pairs | negative_holdout_pairs | positive_nonoverlap_pairs | negative_nonoverlap_pairs | positive_95pct_ic_intervals | negative_95pct_ic_intervals | positive_bh_rejections | positive_holm_rejections | sensitivity_cells_positive_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH | 5 | ROBUST | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 1.000000 |
| STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH | 10 | ROBUST | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 1.000000 |
| STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH | 20 | ROBUST | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 1.000000 |
| STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH | 40 | ROBUST | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 1.000000 |
| STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH | 60 | ROBUST | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 1.000000 |

These are descriptive classifications under prespecified evidence rules. They do not select a formation or possible holding horizon.

## 11. Static-classification limitation

Every sector label is current/static and lacks historical effective dates. Favorable evidence could reflect historical misclassification after business changes, restructurings, mergers, or symbol changes. Identity filtering reduces known ambiguity but cannot certify past sector membership. This severe external-validity limitation caps otherwise robust evidence at CONDITIONAL PASS.

## 12. Direct answers

1. Factor-2 research and interval acceptance completed successfully.
2. Recent sector strength predicts subsequent relative sector strength in this static-classification sample.
3. All five formation horizons have positive mean IC at every frozen outcome; 20 sessions is strongest on average and 5 sessions is weakest.
4. All six outcomes are positive; evidence generally strengthens from 1 toward 20 sessions rather than decaying inside the tested range.
5. Mean Rank IC is positive in all 30 cells.
6. Pooled quintile means are monotonic or nearly monotonic across formations.
7. Q5 outperforms Q1 in all 30 cells.
8. Year evidence is positive in 209 of 210 cells; the exception is 2020 at formation 20/outcome 20.
9. Every formation/outcome IC remains positive in the 2025–2026 holdout.
10. Every horizon pair remains positive when all non-overlap offsets are averaged.
11. All 30 Rank-IC intervals and 30 of 30 Q5–Q1 intervals are wholly above zero.
12. All 30 primary Rank-IC tests survive both Benjamini-Hochberg and Holm correction in the positive direction.
13. IC signs are preserved across every 3/5/10 sector-size sensitivity cell.
14. IC signs are preserved across Basic, Moderate, stable Broad, and static-unique Broad tiers.
15. No single-sector exclusion flips a primary IC sign (0 sign flips). Media/entertainment, electricals, capital goods, trading, and alcohol have the largest measured changes; finance is not dominant and software influence appears mainly in some tail spreads.
16. Static classification remains a severe limitation: zero labels are historically effective-dated.
17. Sector Relative Momentum is credible enough to retain as Factor 2 under the **CONDITIONAL PASS** gate, subject to the static-classification condition.

## 13. Decision and exact Phase-8 scope

The overall decision is **CONDITIONAL PASS**. This is factor evidence, not execution profitability or portfolio performance.

If authorized, Phase 8 should be an independent Factor-2 robustness stage: preregister one untouched chronological evaluation window or obtain effective-dated sector classifications; preserve every Phase-7 tier and parameter; test classification revisions, constituent-return aggregation robustness, and dependence-aware chronology. It must not combine factors, optimize a winning horizon, define trading rules, or simulate a portfolio unless separately authorized.

No Factor 1 signal, Volume + Momentum value, combined score, trading rule, portfolio return, capital allocation, stop, target, or execution assumption was created.
