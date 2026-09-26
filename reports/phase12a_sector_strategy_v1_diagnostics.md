# Phase 12A — Sector Momentum Strategy V1 Failure Diagnostics

**Diagnostic conclusion: BOTH, with implementation failure dominant.** No V2 strategy or alternative P&L was constructed.

## Why V1 failed

The factor remained strong in Phase 7 and V1 produced 264.21% in the already-accepted zero-cost simulation. Translation failed through high recurring turnover, compounding execution drag, EQ-to-BE tradability events, and portfolio risk. At 25 bps per side the result fell to 68.10%, Sharpe 0.484, with a -46.22% drawdown. The short holdout was close to NIFTYBEES, so it was not the decisive rejection reason.

## 1. Turnover and cost attribution

Development turnover shares were: sector entry/exit 87.29%; within-sector replacement 10.24%; equal-weight resizing 2.22%; operational 0.25%. All-in execution-cost shares were respectively 87.29%, 10.24%, 2.22%, and 0.25%.

| Cause | Median weekly normalized turnover | P90 | P95 |
|---|---:|---:|---:|
| SECTOR_ENTRY_EXIT | 0.659 | 1.325 | 1.332 |
| WITHIN_SECTOR_STOCK_REPLACEMENT | 0.000 | 0.227 | 0.429 |
| WEIGHT_REBALANCING | 0.016 | 0.039 | 0.050 |
| FORCED_OPERATIONAL | 0.000 | 0.000 | 0.000 |

The five largest turnover dates were 2024-01-15 (1.990), 2023-03-06 (1.985), 2022-09-19 (1.983), 2024-04-08 (1.982), 2025-04-28 (1.981). Sector entry/exit dominates both rupee turnover and execution cost; the fixed cost model makes class cost shares nearly proportional to notional.

## 2. Selection stability and rank-boundary churn

Median sector and stock Jaccard similarities were 0.500 and 0.385. A typical week retained 2 of three sectors and 5 of nine stocks. Average uninterrupted selection durations were 2.30 sector cycles and 2.07 stock cycles. Small 3/4/5 boundary moves represented 16.83% of sector changes and 63.79% of measurable within-sector stock changes. Boundary churn was material for liquidity-ranked stocks but explains a minority of sector changes.

Yearly mean Jaccard values ranged from 0.398 to 0.496 for sectors and 0.355 to 0.448 for stocks.

## 3. Equal-weight resizing

Pure resizing contributed 2.22% of turnover. Among retained stocks, absolute pre-trade target deviations had median 0.32%, P90 0.92%, and P95 1.24%. Equal-weight restoration is measurable but is not the main turnover source.

## 4. Operational exceptions

All 534 records reconcile: 378 stale marks, 78 unavailable-exit attempts, and 78 capacity-blocked entries. HATHWAY, EASEMYTRIP, TRIDENT, REFEX, KITEX, and OLAELEC transferred from EQ to BE while held; 376 of 378 stale dates contain the symbol explicitly in BE and two raw dates omit it. Their first-unavailable marked values total ₹598,485 across separate incidents. Maximum simultaneous trapped marked capital was ₹266,058 on 2024-12-05. Initial trapped weights ranged from 10.73% to 12.64%. Every trapped position eventually exited on a later valid open; none remained at development end. No zero price or fabricated exit was used.

## 5. Drawdown attribution

The largest episode peaked 2024-09-24, troughed 2026-04-02, reached -46.22%, and was unrecovered at development end. It contained 25 net-negative sectors and 112 net-negative stocks. Its largest negative sectors were oil_gas, textiles, aviation; its largest negative stocks were KITEX, OLAELEC, INDIGO, HAL, ZEEL. The six operationally affected names contributed ₹-148,197 during the ₹-625,805 peak-to-trough loss. The result is a combination: broad adverse sector exposure and stock losses dominate, while trapped names and execution costs aggravated it.

## 6. Gross alpha attribution

On the accepted 25-bps position path before execution-cost deduction, the top five stocks contributed 32.07% of total gross contribution and the top three sectors contributed 37.31%. No single stock supplied more than 7.19%; the largest sector supplied 14.64%. Gross gains were reasonably distributed, with meaningful but not singular concentration. This path-based attribution reconciles exactly to accepted net equity plus observed costs; it is not a newly simulated zero-cost portfolio.

## 7. Factor versus implementation and static mapping

The diagnosis is **BOTH, with implementation failure dominant**. Robust Phase-7 rank evidence and positive accepted gross performance argue against wholesale factor failure. Gross drawdown, negative 2025 performance, and the negative holdout still show genuine factor/portfolio cyclicality. Weekly sector replacement, costs, individual-stock representation, and EQ-to-BE events were implementation failures.

All V1 holdings used stable-identity, uniquely mapped names and the five-stock sector floor; direct unmapped/conflicted/sparse-sector exposure was zero by construction. Static-current mappings remain historically unverified, so classification bias cannot be ruled out or quantified as point-in-time truth.

## 8. V2 boundary

Any V2 must first solve tradability, unavailable exits, stale valuation, trapped-position capacity, turnover/cost feasibility, and drawdown acceptance. Numerical buffers, bands, counts, cadence, costs, and fallback rules remain preregistration decisions. The inspected period through 2026-09-17 is development evidence; fresh V2 validation must start strictly afterward.
