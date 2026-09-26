# Phase 3 — CSRS Factor Research

**Decision: RESEARCH FURTHER**

## 1. Executive summary

Interval-level acceptance succeeded: all 48 factor-panel acceptance checks and all 53 project tests passed, the 188,451 accepted Phase-2 rows were retained, and an independent rebuild reproduced the factor panel and analytical CSVs byte-for-byte. The certified primary analysis ends on 2026-07-17. These results are **conditional current-universe research** and are not a survivorship-bias-free historical NSE study.

CSRS evidence is mixed. The 40- and 60-session formations have positive mean Rank IC at every tested 1/2/3/5/10/20-session outcome horizon. The strongest full-sample pair is 40-session formation / 20-session outcome (mean IC 0.01666; D10-D1 mean outcome spread 0.4348%). The 5-session formation has negative mean IC at all six horizons, with its worst result at the 5-session outcome (mean IC -0.02024; D10-D1 -0.0126%). The 10- and 20-session formations change from weak reversal at short outcomes to continuation at 10–20 sessions.

The positive evidence is small, weakly monotonic, unstable by year, and stronger at longer outcome horizons. It therefore does not establish an MFT holding horizon or execution profitability. CSRS remains a credible candidate for further validation, especially at 40–60-session formation lengths, but the present evidence is insufficient for PASS or CONDITIONAL PASS.

## 2. Implementation and acceptance

Created:

- `config/csrs_research.yaml`: locked horizons, interval rules, cutoff, and deterministic ranking/quantile policies.
- `src/mft_research/csrs/`: interval validation, independent factor ranks, descriptive analyses, plotting, and panel acceptance checks.
- `scripts/build_csrs_factor.py`: verifies accepted Phase-2 artifact hashes before building.
- `tests/test_csrs_*.py`: interval safety, no-lookahead, ranking, quantiles, known IC, contract, and deterministic-rebuild tests.
- `data/derived/csrs_factor_panel.parquet`: 188,451 rows, 18 MiB.
- `reports/csrs/`: all requested CSVs, the build/rebuild evidence, 48-check panel acceptance file, and five plots.

The builder did not rebuild or modify Phase-2 artifacts. It verified their accepted build ID and hashes before reading them. No source price was adjusted, no event was reclassified, and no combined or weighted CSRS score exists.

Trading horizons use the uncompressed Phase-2 observed market-session calendar. Every required symbol/date row from one endpoint through the other must exist and be research-eligible. Blocking corporate actions are tested over `(start, end]`. Ranking is within date and horizon only; ties sort deterministically by raw momentum and then symbol. The ordinal rank is weakest=1 to strongest=N and percentile is `(rank-1)/(N-1)`.

All valid cross-sections had at least 10 names, so the minimum of 2 for IC and 10 for deciles removed no otherwise valid dates. Deciles use `floor((rank-1)*10/N)+1`; D10 is strongest.

## 3. Interval coverage

### Formation observations

| Formation | Valid | Invalid | Valid % | Certified valid dates |
|---:|---:|---:|---:|---|
| 5 | 172,235 | 16,216 | 91.40% | 2020-01-08 to 2026-07-17 |
| 10 | 163,874 | 24,577 | 86.96% | 2020-01-15 to 2026-07-17 |
| 20 | 150,310 | 38,141 | 79.76% | 2020-01-29 to 2026-07-17 |
| 40 | 127,743 | 60,708 | 67.79% | 2020-06-25 to 2026-07-17 |
| 60 | 109,696 | 78,755 | 58.21% | 2020-07-23 to 2026-07-17 |

The cross-sectional count distributions were:

| Formation | Minimum | P5 | Median | Mean | P95 | Maximum |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 10 | 98 | 114 | 112.13 | 120 | 120 |
| 10 | 10 | 97 | 113 | 111.10 | 119.3 | 120 |
| 20 | 10 | 95 | 113 | 109.48 | 119 | 120 |
| 40 | 10 | 92 | 111 | 106.36 | 118 | 119 |
| 60 | 10 | 10 | 110 | 103.10 | 118 | 118 |

### Outcome observations

| Outcome | Valid | Invalid | Valid % | Certified signal dates |
|---:|---:|---:|---:|---|
| 1 | 180,916 | 7,535 | 96.00% | 2020-01-01 to 2026-07-16 |
| 2 | 178,594 | 9,857 | 94.77% | 2020-01-01 to 2026-07-15 |
| 3 | 176,399 | 12,052 | 93.60% | 2020-01-01 to 2026-07-14 |
| 5 | 172,235 | 16,216 | 91.40% | 2020-01-01 to 2026-07-10 |
| 10 | 163,874 | 24,577 | 86.96% | 2020-01-01 to 2026-07-03 |
| 20 | 150,310 | 38,141 | 79.76% | 2020-01-01 to 2026-06-18 |

Reason counts overlap because one interval may fail more than one safety rule. For formations 5/10/20/40/60 respectively, notable overlapping counts were:

| Safety reason | 5 | 10 | 20 | 40 | 60 |
|---|---:|---:|---:|---:|---:|
| Unsafe intervening session | 14,471 | 22,290 | 34,768 | 55,154 | 71,047 |
| Signal row ineligible | 3,742 | 3,742 | 3,742 | 3,742 | 3,742 |
| Endpoint ineligible | 3,739 | 3,738 | 3,737 | 3,736 | 3,736 |
| Insufficient history | 597 | 1,193 | 2,383 | 4,764 | 7,144 |
| Corporate-action coverage uncertified | 1,200 | 1,200 | 1,200 | 1,200 | 1,200 |
| Unresolved corporate-action crossing | 80 | 160 | 320 | 640 | 960 |
| Missing/unsafe session interval | 58 | 111 | 221 | 440 | 660 |
| Identity contamination | 4 | 4 | 4 | 4 | 4 |

The 16 unresolved/ambiguous current-universe events are preserved as explicit crossing failures. They add no exclusive primary failures because each affected interval also crosses a Phase-2-ineligible session, but the corporate-action reason remains independently recorded. The coverage cutoff accounts for 1,200 formation observations per horizon. Future-label coverage failures rise from 1,320 at 1 session to 3,600 at 20 sessions because their intended target date moves beyond certification; some also have unavailable endpoints.

IRFC contaminated rows cannot enter valid intervals. Four formation rows carry the overlapping identity-contamination reason at every formation horizon; Phase-2 row and intervening-session rules exclude the broader contaminated region.

New listings receive no artificial history. At the 60-session formation, valid/observed counts were TMCV 84/178, TATACAP 24/198, HYUNDAI 308/440, JIOFIN 538/731, and MANKIND 515/803. Other materially reduced histories reflect accepted source quality: BAJAJHLDNG 225/1,635, SOLARINDS 374/1,635, CGPOWER 618/1,635, LODHA 519/1,312, TATACOMM 741/1,635, ABB 782/1,635, and OFSS 811/1,635 at 60 sessions.

## 4. Rank IC and horizon evidence

| Formation | Mean IC across outcomes | Positive-IC outcomes | Mean D10-D1 | Positive spreads | Mean decile monotonicity |
|---:|---:|---:|---:|---:|---:|
| 5 | -0.01253 | 0/6 | 0.0262% | 4/6 | -0.168 |
| 10 | -0.00390 | 2/6 | 0.0955% | 6/6 | 0.277 |
| 20 | 0.00092 | 2/6 | 0.0720% | 5/6 | 0.251 |
| 40 | 0.00719 | 6/6 | 0.1424% | 6/6 | 0.061 |
| 60 | 0.01173 | 6/6 | 0.0452% | 5/6 | 0.358 |

The best pair by mean IC and D10-D1 spread is 40/20: IC 0.01666 over 1,064 dates, D10 2.5902%, D1 2.1555%, spread 0.4348%. The best IC for 60-session formation is 60/5 at 0.01507, but its D10-D1 spread is only 0.0369%. The worst mean IC is 5/5 at -0.02024; the most negative spread is 5/3 at -0.0237%.

Across formation horizons, mean IC improves as the outcome extends: -0.00423, -0.00307, -0.00124, -0.00077, 0.00443, and 0.00898 for 1/2/3/5/10/20 sessions. Mean D10-D1 spreads similarly increase from 0.0217% at one session to 0.2104% at 20 sessions. This describes slow-emerging continuation rather than a clear very-short-horizon effect. It does not select a holding period.

The ordinary t-statistics in `rank_ic_summary.csv` are descriptive diagnostics only. Multi-session outcomes overlap, daily cross-sections are serially dependent, and these statistics are not independent-observation inference.

## 5. Quantiles and sides

D10 exceeds D1 in 26 of 30 formation/outcome pairs, but decile paths are only modestly monotonic. Across the five formations, mean decile-rank correlations range from -0.168 to 0.358; no horizon has all nine adjacent decile means rising. The 40-session signal has positive extreme spreads throughout despite weak internal ordering. Thus, the tails support some continuation while the full rank distribution is not reliably smooth.

Top/bottom diagnostics are broadly consistent across 5%, 10%, and 20% cuts for the stronger formations. For 40-session formation, the 10% top-minus-bottom spreads are 0.0135%, 0.1082%, and 0.3832% at 1/5/20-session outcomes. For 60-session formation they are 0.0322%, 0.0186%, and 0.0163%. The 60/20 top 5% spread is negative (-0.0315%) even though wider 10% and 20% cuts are positive.

Both tails generally have positive absolute outcome returns. Relative to the full eligible cross-section, the stronger-name tail is usually above average while the weaker-name tail is often near or above average. The evidence is therefore driven more by winner continuation than by persistent absolute or broad-relative weakening of losers. This is diagnostic and does not choose a deployment side.

## 6. Year stability

Average IC across outcome horizons by year and formation:

| Year | 5 | 10 | 20 | 40 | 60 |
|---:|---:|---:|---:|---:|---:|
| 2020 | -0.0215 | -0.0028 | -0.0291 | -0.0368 | 0.0182* |
| 2021 | -0.0074 | -0.0007 | -0.0149 | -0.0385 | 0.0049 |
| 2022 | -0.0166 | -0.0005 | 0.0120 | 0.0329 | 0.0218 |
| 2023 | -0.0306 | -0.0285 | -0.0148 | -0.0125 | 0.0050 |
| 2024 | -0.0017 | -0.0062 | 0.0151 | 0.0227 | 0.0206 |
| 2025 | -0.0112 | 0.0091 | 0.0166 | 0.0026 | -0.0049 |
| 2026 YTD | 0.0071 | 0.0011 | 0.0002 | 0.0633 | 0.0327 |

`*` The 2020 60-session estimate is sparse: only 109 summed daily-IC observations across its six outcome analyses, including five dates for the 20-session outcome.

The 40-session evidence reverses sign in 2020, 2021, and 2023, strengthens in 2022 and 2024, is nearly flat with negative average spreads in 2025, and is unusually strong in 2026 YTD. Its strongest yearly pair is 40/20 in 2026 YTD (IC 0.0993, spread 2.7996%, 113 dates); 40/20 was also strong in 2022 but negative in 2020–2021. The 60-session formation is positive in most years but reverses in 2025, where its mean spread across outcomes is -0.6775%. Results are not confined to one positive year, yet sign changes and 2026 strength make temporal stability a material weakness.

## 7. Interpretation and limitations

CSRS contains some predictive cross-sectional information at 40–60-session formations, particularly for outcomes measured 10–20 sessions later. The evidence does not generalize to short formations: 5-session momentum is a short-term reversal signal in Rank IC terms. Quantile monotonicity is weak, tail spreads are economically small at short outcomes, and year effects are unstable.

The main limitations are:

- The 120-symbol universe is selected from current partitions. Survivorship bias is material and could inflate historical continuation; no historical membership reconstruction was attempted.
- Corporate actions are certified only through 2026-07-17. Later rows remain in the panel but cannot enter primary factor or outcome observations.
- The 16 unresolved/ambiguous events are conservatively blocked, but no total-return reconstruction or entitlement-basket treatment was attempted.
- Long intervals lose substantial data when they cross an accepted ineligible session. This is scientifically safer but creates symbol- and period-dependent coverage.
- All results are full-sample descriptive research. There is no held-out or walk-forward evaluation, executable return, transaction cost, or portfolio inference.
- Overlapping outcome labels invalidate ordinary independent-sample inference.

These weaknesses, combined with parameter disagreement across five independently tested formations, warrant **RESEARCH FURTHER**. CSRS is credible enough to retain as a candidate Factor 1, but it is not yet validated for combination or deployment.

## 8. Validation evidence

Commands run:

```bash
.venv/bin/python scripts/build_csrs_factor.py
.venv/bin/python scripts/build_csrs_factor.py --verify-rebuild
.venv/bin/python -m pytest tests/test_csrs_intervals.py tests/test_csrs_factor_analysis.py tests/test_csrs_integration.py -q
.venv/bin/python -m pytest -q
```

Results:

- CSRS-specific suite: 16 passed.
- Full project suite: 53 passed in 1.41 seconds.
- Factor-panel acceptance: 48/48 checks passed.
- Determinism: panel Parquet and all analytical CSVs reproduced byte-for-byte.
- CSRS build ID: `aeabe4a61aa23901e85a76102a80bfc73c5d09c090b7fc0dc145a2db51539fbf`.

## 9. Recommended exact Phase-4 scope

Phase 4 should remain CSRS validation research and should be preregistered before examining its results:

1. Freeze the five formation horizons and six outcome horizons; do not combine them or pick a winner from this full sample.
2. Run expanding-window and leave-one-year-out chronological validation, reporting every horizon pair and treating 2026 YTD as incomplete.
3. Add dependence-aware uncertainty estimates using horizon-spaced non-overlapping samples and a documented block bootstrap or HAC procedure.
4. Run sensitivity checks to cross-section size, exclusion concentration, and leave-one-symbol/industry-group-out influence without changing the factor definition.
5. Obtain or explicitly decline a historical point-in-time universe source; quantify how that decision limits any later claim.
6. Extend and reaccept corporate-action coverage before using observations after 2026-07-17.
7. Decide whether the validated evidence supports retaining one or more independent CSRS horizons for later factor-combination research.

Phase 4 should not include portfolio construction, execution assumptions, Sector Relative Momentum, Volume + Momentum, or a combined CSRS score.
