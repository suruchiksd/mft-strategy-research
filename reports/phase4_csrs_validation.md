# Phase 4 — Chronological CSRS Validation

**Overall classification: RESEARCH FURTHER**

## 1. Acceptance and scope

Phase 4 completed successfully. The builder verified the accepted Phase-3 build ID `aeabe4a61aa23901e85a76102a80bfc73c5d09c090b7fc0dc145a2db51539fbf`, the factor-panel SHA-256 `9a57c8467ef15827eec8a49ac75af386e80c305f3bbfccf407ac7e45ed8fd347`, all 48 Phase-3 panel acceptance checks, and the certified cutoff of 2026-07-17 before analysis. The accepted 188,451-row factor panel was read without modification; observations after the cutoff did not enter validation.

All five formation horizons and all six outcome horizons remained frozen, giving all 30 pairs in every applicable validation view. There was no parameter fitting, winner selection, combined score, portfolio return, execution model, or trading rule. Results remain **conditional current-universe research**.

The 11 requested analytical CSVs reproduced byte-for-byte. All 11 Phase-4 tests and all 64 project tests passed.

## 2. Methods

Expanding-window folds evaluate 2021, 2022, 2023, 2024, 2025, and 2026 YTD using only history ending before each evaluation year. Since CSRS has no fitted parameter, the historical window is evidence available at the time and does not change the factor or select a pair.

Fixed blocks are exactly:

- Research/development: 2020-01-01 through 2022-12-31
- Validation: 2023-01-01 through 2024-12-31
- Out-of-sample holdout: 2025-01-01 through 2026-07-17

Phase-4 spread statistics use the equal-weighted mean of each date's D10-minus-D1 cross-sectional outcome. Fixed-period files also retain the pooled-observation D10-D1 estimate because unequal daily cross-section sizes can make the two disagree. Neither is portfolio P&L.

Non-overlapping samples use the position of each signal date in the certified market-session calendar. For outcome horizon `H`, every offset `0..H-1` is evaluated; no offset is selected.

Dependence-aware intervals use a deterministic circular moving-block bootstrap of daily IC and daily D10-D1 series: 2,000 replications, 95% percentile interval, fixed base seed 20260914, and block length `max(10, 2H)` sessions. This block rule was set from the outcome-overlap structure before inspecting interval significance.

Leave-one-symbol-out statistics exactly remove each symbol, rerank remaining observations within date, and recompute deciles. Sector influence does the same for each of the 29 uniquely mapped sectors. The 116 unique mappings are used; three unmapped names and the one conflicted name remain in the comparison universe and are never assigned invented sectors.

Coverage-quality bands are defined independently for each formation horizon using retained-history quartiles: bottom quartile is `MATERIAL_REDUCED`, middle half is `MODERATE`, and top quartile is `HIGH`. Eligibility is never loosened. Cross-section threshold sensitivity filters dates only and does not rerank or use outcomes to define thresholds.

## 3. Expanding-window evidence

Across six future evaluation years and six outcome horizons (36 evaluation cells per formation):

| Formation | Positive IC cells | Negative IC cells | Positive daily-spread cells | Interpretation |
|---:|---:|---:|---:|---|
| 5 | 10 | 26 | 26 | Rank reversal dominates, but tail spreads often disagree |
| 10 | 13 | 23 | 27 | Weak and inconsistent |
| 20 | 20 | 16 | 24 | Changes from early weakness to later strength |
| 40 | 22 | 14 | 22 | Continuation occurs, with material negative years |
| 60 | 31 | 5 | 19 | Most consistent IC sign; spread consistency is weak |

The 40-session formation is negative across every outcome horizon in 2021 and 2023, positive throughout 2022 and 2024, mixed in 2025, and unusually strong throughout 2026 YTD. Averaged across outcomes, its annual evaluation IC is -0.0385, 0.0329, -0.0125, 0.0227, 0.0026, and 0.0633 from 2021 through 2026.

The 60-session formation has positive IC in 31/36 evaluation cells. It is positive in most periods, but 2025 is negative at the 1/2/3/5-session outcomes. Its 2026 IC is positive while every daily D10-D1 spread is negative. Rank continuation and extreme-tail performance therefore do not confirm each other consistently.

The 5-session signal is negative in 26/36 chronological IC cells. Its short outcomes retain reversal-like behavior, while longer outcomes are less stable.

## 4. Fixed holdout evidence

| Formation | Positive IC pairs | Mean IC across outcomes | Positive daily spreads | Positive pooled spreads | Mean daily spread |
|---:|---:|---:|---:|---:|---:|
| 5 | 2/6 | -0.00474 | 4/6 | 1/6 | 0.0936% |
| 10 | 4/6 | 0.00685 | 6/6 | 1/6 | 0.2059% |
| 20 | 6/6 | 0.01136 | 2/6 | 0/6 | 0.1525% |
| 40 | 6/6 | 0.02286 | 4/6 | 2/6 | 0.3006% |
| 60 | 6/6 | 0.00786 | 1/6 | 0/6 | -0.1913% |

The holdout supports positive rank continuation for 20, 40, and 60 sessions. It does not give consistent extreme-decile confirmation. The strongest holdout Rank IC occurs at 40/20 (0.04394), with an equal-date mean spread of 1.1404%; its pooled spread is only 0.0647%. At 60 sessions, all six holdout ICs are positive but five equal-date spreads and all six pooled spreads are negative.

The holdout is not independent of Phase-3 discovery in a strict experimental sense: its boundaries were prescribed only in Phase 4 after Phase-3 full-sample results had been viewed. It is a fixed chronological diagnostic, not a pristine preregistered holdout.

## 5. Non-overlap and uncertainty

Mean non-overlapping-offset IC has the same sign as the full daily estimate for all 30 pairs. For 40 sessions, all six offset-averaged ICs are positive and every individual offset is positive for outcomes 1, 2, 3, and 5; the 10- and 20-session outcomes have some negative offsets. For 60 sessions, all six offset means are positive and every offset is positive for outcomes 1, 2, 3, 5, and 10; the 20-session outcome has negative offsets. The 5-session formation has negative offset means for all six outcomes and every offset is negative for outcomes 1, 2, 3, and 5.

Dependence-aware uncertainty is much less favorable than ordinary Phase-3 t-statistics:

- None of the six 40-session IC intervals is wholly above zero.
- None of the six 60-session IC intervals is wholly above zero.
- No D10-D1 spread interval for any formation is wholly positive or negative.
- The 5-session IC interval is wholly negative for outcomes 1, 2, 3, and 5; its 10- and 20-session intervals cross zero.
- The 10/1 IC interval is wholly negative; its other intervals cross zero.

For illustration, 40/20 mean IC is 0.01666 with 95% interval [-0.02978, 0.06797], and its mean daily spread is 0.7591% with interval [-0.5672%, 2.1855%]. The 60/5 mean IC is 0.01507 with interval [-0.01106, 0.04274]. These wide intervals do not establish dependable positive effects.

## 6. Year and leave-one-year influence

Year sign consistency remains the main weakness of 40 sessions. Depending on outcome, only three or four of seven years have positive IC. Removing 2026 reduces the formation's mean-across-outcomes IC to 0.00032; removing 2021 raises it to 0.01572. The average stays positive under every single-year omission, but individual horizon pairs can turn negative.

The 60-session mean-across-outcomes IC remains positive under every year omission, ranging from 0.00876 when 2026 is omitted to 0.01705 when 2025 is omitted. Individual outcomes remain uncertain, and spread sensitivity is larger than IC sensitivity.

The 5-session mean IC remains negative after every year omission. This supports a persistent short-formation reversal tendency, although longer outcome horizons and tail spreads are inconsistent.

## 7. Cross-section and source-quality sensitivity

Dates below 50 and below 80 names are the same small early-date set. Excluding them materially weakens continuation:

| Formation | Baseline mean IC | Mean IC at >=50/80 | Mean IC at >=100 | Mean dates removed at >=100 |
|---:|---:|---:|---:|---:|
| 5 | -0.01253 | -0.01407 | -0.01317 | 89.8 |
| 10 | -0.00390 | -0.00653 | -0.00810 | 125.2 |
| 20 | 0.00092 | -0.00437 | -0.00348 | 129.8 |
| 40 | 0.00719 | -0.00131 | 0.00082 | 152.7 |
| 60 | 0.01173 | 0.00380 | 0.00635 | 183.2 |

The 40-session full-sample IC is sensitive to the small-cross-section dates; the 60-session estimate remains positive but is roughly halved. Thresholds are diagnostics and are not proposed as eligibility or optimization rules.

Retained-history quartiles do not show that low-quality names alone create the effect. For 40 sessions, mean IC across outcomes is 0.01150 in the high band, 0.00495 in the materially reduced band, and -0.00245 in the middle band. For 60 sessions it is 0.00720, -0.00252, and 0.01889 respectively. The heterogeneity is substantial and not monotonic in source coverage.

## 8. Symbol and sector influence

No single symbol removes the broad 40/60 continuation sign across outcomes, but individual long-outcome estimates are sensitive. The largest absolute IC changes are:

- 40 sessions: excluding HINDZINC changes 40/20 IC by +0.00698; excluding SHRIRAMFIN changes it by -0.00524.
- 60 sessions: excluding SHRIRAMFIN changes 60/20 IC by -0.00603; excluding INFY changes it by +0.00458.

Tail spreads are more fragile. Excluding INFY changes the 40/20 daily spread by -0.3969%; excluding HDFCBANK changes 60/20 by -0.4138%.

Sector effects are larger than individual-name effects. Software is the most influential sector at the longer outcomes: excluding it changes 40/20 IC by -0.01162 and daily spread by -0.8294%, and changes 60/20 IC by -0.00839 and spread by -0.8094%. The IC estimates remain positive after those exclusions, but the spread effect can change sign. This is an influence result using current unique mappings; it is not Sector Relative Momentum and does not establish historical sector membership.

## 9. Formation classifications

| Formation | Classification | Evidence |
|---:|---|---|
| 5 | **REVERSAL-LIKE** | Full sample and every non-overlap mean are negative; four short-outcome bootstrap intervals are below zero; holdout longer outcomes weaken the conclusion |
| 10 | **INCONCLUSIVE** | Four holdout ICs are positive, but four full-sample ICs and 23/36 forward cells are negative |
| 20 | **INCONCLUSIVE** | All holdout ICs are positive, but development/validation history, non-overlap signs, and pooled holdout spreads disagree |
| 40 | **PROMISING BUT UNSTABLE** | All holdout and non-overlap mean ICs are positive; year signs, small-cross-section sensitivity, tail spreads, and uncertainty intervals are weak |
| 60 | **PROMISING BUT UNSTABLE** | Strongest year-sign consistency and positive holdout ICs; holdout spreads are mostly negative and all confidence intervals cross zero |

These labels describe independent evidence. They do not select a formation or authorize a combined CSRS score.

## 10. Overall decision

**RESEARCH FURTHER**

CSRS has not failed: the 40- and 60-session rank relationships survive the fixed holdout and offset-averaged non-overlap views, 60-session IC is positive in 31/36 forward cells, and no single stock or sector fully explains the IC sign. The evidence is not strong enough for trading-rule or portfolio research because dependence-aware intervals include zero throughout, 40-session evidence is sensitive to small early cross-sections and 2026, 60-session extreme-tail returns fail in the holdout, and sector influence is material.

The 40- and 60-session formations should remain explicit hypotheses for further external/forward validation. This is retention for research, not selection for deployment or combination. The 5-session formation should remain a reversal diagnostic and negative control; 10 and 20 remain inconclusive controls.

Survivorship bias remains material because all periods use the current 120-symbol universe. Current sector mappings also lack historical effective dates. The corporate-action cutoff prevents certification after 2026-07-17 and shortens the 2026 evaluation, especially for longer outcomes. Neither limitation was repaired or hidden in Phase 4.

## 11. Outputs and verification

Created under `reports/csrs/validation/`:

- `expanding_window_results.csv`
- `fixed_period_results.csv`
- `leave_one_year_out.csv`
- `nonoverlap_results.csv`
- `uncertainty_intervals.csv`
- `year_stability.csv`
- `cross_section_sensitivity.csv`
- `coverage_quality_sensitivity.csv`
- `leave_one_symbol_out.csv`
- `sector_influence.csv`
- `formation_classification.csv`
- `phase4_build_manifest.json`
- `phase4_rebuild_verification.json`

Commands run:

```bash
.venv/bin/python scripts/build_phase4_validation.py
.venv/bin/python scripts/build_phase4_validation.py --verify-rebuild
.venv/bin/python -m pytest tests/test_phase4_validation.py tests/test_phase4_integration.py -q
.venv/bin/python -m pytest -q
```

Results:

- Phase-4 tests: 11 passed in 0.15 seconds.
- Full project suite: 64 passed in 1.53 seconds.
- Deterministic rebuild: 11/11 CSV outputs byte-identical.
- Phase-4 build ID: `a6143ab2dc46503ba412740c43a46cb2ac613d22042871bf81d29abfc1ea8727`.

## 12. Recommended exact Phase-5 scope

Phase 5 should address external validity before any trading-rule or portfolio design:

1. Extend and reaccept corporate-action coverage beyond 2026-07-17, preserving a new untouched prospective window.
2. Obtain point-in-time universe membership, listings, and delistings, then repeat the same frozen 30-pair tests in a historically eligible universe. If unavailable, state that limitation as a formal gate.
3. Preregister 40- and 60-session continuation as hypotheses and 5/10/20 as controls before opening the new window; retain every horizon in reports.
4. Require an adequate number of non-overlapping 20-session blocks and report family-wise or false-discovery-aware uncertainty across the 30 tests.
5. Recheck the rank-versus-tail disagreement and software-sector influence without building a sector factor or changing ranks based on results.
6. Set a written gate for later trading-rule research: chronological sign stability, dependence-aware interval evidence, and robustness to point-in-time universe and sector influence must jointly improve.

Phase 5 should not construct a portfolio, choose a final formation, add execution assumptions, combine factors, or start Sector Relative Momentum or Volume + Momentum.
