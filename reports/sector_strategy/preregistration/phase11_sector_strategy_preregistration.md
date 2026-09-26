# Phase 11 — Sector Momentum Strategy V1 Preregistration

**Frozen before any strategy P&L for 2026-08-01 through 2026-09-17 was calculated or inspected.**

## Scope and evidence status

V1 converts only the accepted 20-session Sector Relative Momentum factor into a long-only NSE cash strategy. Sector classifications remain static/current without historical effective dates. Development results are historical strategy simulation, not pristine out-of-sample evidence. The sealed Aug–Sep interval is a strategy-level holdout. True prospective validation starts strictly after 2026-09-17.

REV05, REV20, cross-sectional continuation, and every Volume + Momentum feature are prohibited. Stock selection uses liquidity only and contributes no stock-level alpha.

## Trading rules

On the final NSE trading session of each ISO week, after the close, rank sectors by the accepted Phase-7 20-session compounded equal-weight sector return. Each constituent return uses that session's contemporaneously eligible membership; at least five valid constituents are required. Select the three strongest sectors.

Within each selected sector, select up to three BASIC_LIQUID, uniquely mapped, identity-stable stocks using `avg_turnover_20` descending and symbol ascending as tie-break. If fewer than three exist, select all; do not substitute from another sector. A stock whose intended weekly holding interval crosses a recorded blocking corporate action is excluded for safety and replaced only by the next liquidity-ranked eligible stock in the same selected sector. This risk exclusion is not alpha and avoids fabricated entitlement accounting.

Orders execute at the next NSE session open. Buys receive upward adverse slippage and sells downward adverse slippage. Existing positions are rebalanced to equal weights across actual selections. Quantities are positive whole shares, sell reductions execute first, buys execute in symbol order, and unaffordable quantities are reduced until cash remains nonnegative. No leverage, shorts, stops, targets, regimes, or same-close fills are allowed.

## Costs and capital

Normalized NAV and a ₹5,00,000 example are both required. Gross uses zero costs. Primary net uses 25 bps per side: 20 bps transparent transaction cost plus 5 bps adverse slippage. Prespecified all-in sensitivities are 0, 10, 25, and 50 bps per side; the 10 and 50 cases use 8+2 and 40+10 cost/slippage splits.

## Periods and benchmarks

- Development: 2020-01-01 through 2026-07-17, with the first executable rebalance determined by available 20-session sector history.
- Sealed holdout: 2026-08-01 through 2026-09-17. A July signal may seed the first August execution.
- Prospective paper trading: strictly after 2026-09-17.

The primary consistent benchmark is NIFTYBEES close-to-close price return from certified EQ Bhavcopy data. Certified local NIFTY 50 index data are also reported for development. No certified official NIFTY 50 response was available for the holdout at freeze time, so it is not fabricated.

## Feasibility frozen before P&L

Development contains 325 weekly dates with complete nine-position selections after formation availability. No selected sector had fewer than three eligible stocks. The median valid sector cross-section is 35, and the maximum equal-weight sector exposure is one-third. September 14, 2026 is an NSE holiday, making the Sep-11 signal execute Sep-15. One development selection window crosses a blocking event; the frozen corporate-action replacement rule handles it.

## Acceptance hierarchy

Operational defects, negative cash/leverage, position-limit breaches, holdout drawdown above 20%, or holdout net underperformance worse than 10 percentage points versus NIFTYBEES cause `REJECT STRATEGY V1`.

`READY FOR PAPER TRADING` requires development net CAGR above zero, Sharpe at least 0.50, development drawdown at most 30%, holdout excess at least -2 percentage points, holdout drawdown at most 8%, cost drag at most 2 percentage points, mean weekly gross turnover at most 200%, stock absolute-contribution share at most 50%, and sector absolute-contribution share at most 60%.

`CONDITIONAL PAPER-TRADE CANDIDATE` requires development net CAGR and Sharpe above zero, development drawdown at most 40%, holdout excess at least -5 percentage points, holdout drawdown at most 12%, cost drag at most 4 percentage points, turnover at most 200%, stock contribution concentration at most 70%, and sector concentration at most 75%.

Every other non-reject state is `RESEARCH FURTHER`. These thresholds cannot be changed after holdout inspection.
