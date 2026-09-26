# Phase 9 — Volume + Momentum Predictive Research

**Factor research only. No portfolio, trading rule, factor combination, or execution result was created.**

**Overall Factor-3 decision: FAIL**

## 1. Acceptance and frozen design

Phase 9 verified the accepted Phase-8 build and tested exactly seven frozen candidates against exactly 1/2/3/5/10/20-session outcomes. BASIC_LIQUID is primary; MODERATE_LIQUID is the only universe sensitivity. Forward labels use certified Phase-5 interval safety through 2026-07-17.

## 2. Controls and raw interaction evidence

| candidate | role | mean_ic | positive_pairs | mean_d10_d1 | holdout_mean_ic | positive_holdout | nonoverlap_mean_ic | positive_ic_intervals | negative_ic_intervals | bh_rejections | holm_rejections |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VM01 | CONTROL_PRICE | -0.040292 | 0 | -0.002784 | -0.030480 | 0 | -0.040292 | 0 | 6 | 6 | 6 |
| VM02 | CONTROL_PRICE | -0.022431 | 0 | 0.000239 | -0.011746 | 0 | -0.022431 | 0 | 5 | 5 | 4 |
| VM03 | CONTROL_VOLUME | -0.013916 | 1 | -0.000594 | -0.003274 | 2 | -0.013916 | 0 | 5 | 5 | 4 |
| VM04 | CONTROL_VOLUME | -0.016903 | 0 | -0.000175 | -0.002423 | 2 | -0.016904 | 0 | 5 | 5 | 4 |
| VM05 | INTERACTION | -0.032608 | 0 | -0.003206 | -0.026014 | 0 | -0.032608 | 0 | 6 | 6 | 6 |
| VM06 | INTERACTION | -0.022472 | 0 | -0.001806 | -0.012169 | 0 | -0.022472 | 0 | 6 | 6 | 6 |
| VM07 | INTERACTION | -0.023159 | 0 | -0.001313 | -0.012458 | 0 | -0.023159 | 0 | 6 | 6 | 6 |

Positive IC means higher frozen candidate values precede higher returns; negative IC is reported as reversal-like and is never sign-flipped.

## 3. Incremental interaction evidence

| candidate_id | mean_incremental_ic | positive_pairs | holdout_mean_incremental_ic | positive_holdout_pairs | positive_95pct_intervals | negative_95pct_intervals | bh_rejections | holm_rejections |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VM05 | -0.007357 | 0 | -0.008191 | 0 | 0 | 6 | 6 | 6 |
| VM06 | -0.006276 | 0 | -0.005131 | 0 | 0 | 6 | 6 | 6 |
| VM07 | -0.006174 | 0 | -0.004559 | 0 | 0 | 6 | 6 | 6 |

Each interaction rank was residualized on its two frozen component-control ranks within the same date. Outcomes did not enter residualization. These 18 tests form a separate multiple-testing family.

## 4. Chronology, dependence, and sensitivities

| candidate_id | moderate_mean_ic | moderate_positive_pairs |
| --- | --- | --- |
| VM01 | -0.032789 | 0 |
| VM02 | -0.017204 | 0 |
| VM03 | -0.010221 | 1 |
| VM04 | -0.014883 | 0 |
| VM05 | -0.025862 | 0 |
| VM06 | -0.016932 | 0 |
| VM07 | -0.018678 | 0 |

| candidate_id | NEW | OLD |
| --- | --- | --- |
| VM01 | -0.032811 | -0.043799 |
| VM02 | -0.011949 | -0.027331 |
| VM03 | -0.006402 | -0.017412 |
| VM04 | -0.004452 | -0.022735 |
| VM05 | -0.027892 | -0.034821 |
| VM06 | -0.014036 | -0.026417 |
| VM07 | -0.014373 | -0.027293 |

| candidate_id | mean_abs_ic_change | max_abs_ic_change |
| --- | --- | --- |
| VM01 | 0.000329 | 0.000591 |
| VM02 | 0.000828 | 0.001338 |
| VM03 | 0.000485 | 0.000933 |
| VM04 | 0.000644 | 0.001194 |
| VM05 | 0.000458 | 0.000821 |
| VM06 | 0.000667 | 0.001207 |
| VM07 | 0.000699 | 0.001275 |

The largest absolute correlation between two candidate daily-IC series is 0.938683 for VM06/VM07 at the 3-session outcome. OLD/NEW comparisons are source-era/time-era sensitivity, not a clean format experiment.

All outcome horizons use all non-overlap offsets. Confidence intervals use 2,000 deterministic circular block-bootstrap replications with block length max(10,2H). BH and Holm corrections cover the 42 primary tests; incremental corrections cover a separate 18-test family.

## 5. Candidate classifications

| candidate_id | role | classification | positive_primary_pairs | negative_primary_pairs | positive_holdout_pairs | negative_holdout_pairs | positive_nonoverlap_pairs | negative_nonoverlap_pairs | positive_ic_intervals | negative_ic_intervals | positive_bh_rejections | negative_bh_rejections | positive_year_cell_fraction | negative_year_cell_fraction | moderate_positive_pairs | moderate_negative_pairs | incremental_positive_pairs | incremental_positive_holdout_pairs | incremental_positive_intervals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VM01 | CONTROL_PRICE | REVERSAL-LIKE | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0.000000 | 1.000000 | 0 | 6 | 0 | 0 | 0 |
| VM02 | CONTROL_PRICE | REVERSAL-LIKE | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 5 | 0 | 5 | 0.095238 | 0.904762 | 0 | 6 | 0 | 0 | 0 |
| VM03 | CONTROL_VOLUME | REVERSAL-LIKE | 1 | 5 | 2 | 4 | 1 | 5 | 0 | 5 | 0 | 5 | 0.166667 | 0.833333 | 1 | 5 | 0 | 0 | 0 |
| VM04 | CONTROL_VOLUME | REVERSAL-LIKE | 0 | 6 | 2 | 4 | 0 | 6 | 0 | 5 | 0 | 5 | 0.142857 | 0.857143 | 0 | 6 | 0 | 0 | 0 |
| VM05 | INTERACTION | REVERSAL-LIKE | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0.000000 | 1.000000 | 0 | 6 | 0 | 0 | 0 |
| VM06 | INTERACTION | REVERSAL-LIKE | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0.000000 | 1.000000 | 0 | 6 | 0 | 0 | 0 |
| VM07 | INTERACTION | REVERSAL-LIKE | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0.000000 | 1.000000 | 0 | 6 | 0 | 0 | 0 |

Interaction candidates cannot receive ROBUST POSITIVE without satisfying the preregistered incremental-information rule.

## 6. Direct answers

1. Phase 9 completed successfully under the frozen registry and interval-safety contract.
2. VM01 is classified REVERSAL-LIKE.
3. VM02 is classified REVERSAL-LIKE.
4. VM03/VM04 classifications are REVERSAL-LIKE and REVERSAL-LIKE; their detailed direction and uncertainty are disclosed above.
5. The stronger volume-only mean IC is VM03; no horizon was selected for deployment.
6. VM05 incremental classification is REVERSAL-LIKE.
7. VM06 incremental classification is REVERSAL-LIKE.
8. VM07 incremental classification is REVERSAL-LIKE.
9. Interaction directions, including mixed or negative relationships, are shown without reorientation in the evidence and incremental tables.
10. Holdout signs for all candidates are shown in the primary evidence table.
11. Non-overlap evidence is shown by candidate and all offsets in `nonoverlap_results.csv`.
12. Confidence-interval exclusions are counted in the evidence tables and fully disclosed in the uncertainty CSVs.
13. BH/Holm results are shown above and fully disclosed with direction labels.
14. Every year and all 42 cells are disclosed in `yearly_analysis.csv`; negative and sparse years are retained.
15. MODERATE_LIQUID results are disclosed without replacing BASIC_LIQUID as primary.
16. OLD/NEW source-era signs are disclosed as time-era sensitivity, not format equivalence proof.
17. Excluding already-valid observations within ±5 sessions of recorded actions produces the changes summarized above; rejected crossing intervals were never restored.
18. The most similar predictive pair is VM06/VM07; no candidate was removed.
19. Retention follows the preregistered classification table; raw interaction IC alone is insufficient.
20. The Factor-3 decision is FAIL because the interaction incremental criteria, rather than control performance alone, determine the gate.

## 7. Exact next-stage recommendation

Do not carry Volume + Momentum into factor-combination or trading-rule research. Preserve any control or reversal findings as separate hypotheses only; a new untouched sample would be required before revisiting an interaction.

The current/static sector limitation is irrelevant to Factor 3, but accepted corporate-action coverage and source-era limitations remain. No Factor 1B optimization or Factor-2/Factor-3 combination was performed.
