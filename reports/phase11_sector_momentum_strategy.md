# Phase 11 — Sector Momentum Strategy V1

**Decision: REJECT STRATEGY V1**  
**Research label: STATIC-CURRENT-CLASSIFICATION STRATEGY RESEARCH**

## A. Data readiness

Prices and additive corporate-action safety certification cover every NSE session through **2026-09-17**. September 14 was an official exchange holiday. The accepted Phase-5 through Phase-10 artifacts remain unchanged. Sector labels remain current/static with no historical effective dates.

## B. Frozen V1 strategy

The sole alpha is the accepted equal-weight 20-session Sector Relative Momentum signal. At each final NSE session of the ISO week, select the top three valid sectors, then up to three BASIC_LIQUID stocks per sector by trailing 20-session average turnover, breaking ties by symbol. Execute after the next session opens with adverse slippage; hold a maximum of nine long cash positions at equal target weights with whole shares. Recorded blocking corporate actions exclude a candidate for its intended weekly holding interval and promote the next liquid name within the same sector. No stop, target, leverage, stock momentum, reversal, volume signal, or regime rule exists.

Primary net results use 25 bps per side: 20 bps transaction cost plus 5 bps adverse slippage. The fixed sensitivity grid is 0/10/25/50 bps per side.

## C. Development / historical strategy simulation

The simulation begins 2020-05-04 and ends 2026-07-17; this is development evidence, not pristine OOS. Gross cumulative return is 264.21%; primary-net cumulative return is 68.10%, CAGR 8.88%, Sharpe 0.484, volatility 23.92%, and maximum drawdown -46.22%. NIFTYBEES returned 165.37%. It used 324 rebalances and 3967 fills, with mean weekly gross turnover 0.942. The fixed 0/10/25/50 bps BASIC cumulative returns were 0=264.21%, 10=167.17%, 25=68.10%, 50=-22.14%.

The development run recorded 534 operational exceptions, dominated by securities that ceased printing valid EQ opens/closes while held. The simulator retained their last observable mark, blocked unavailable exits, and never fabricated a trade. This breaches the frozen anomaly gate. Development maximum drawdown also exceeds the 40% conditional ceiling. Maximum stock and sector absolute contribution shares were 2.68% and 12.93%.

## D. Sealed strategy holdout

The holdout runs 2026-08-03 through 2026-09-17. Net return is -4.78%; gross return is -2.76%; NIFTYBEES returned -4.46%; net excess is -0.32%. Maximum drawdown is -8.55%; cost drag 2.02%; mean weekly gross turnover 1.212. Seven rebalances executed with no holdout operational anomaly. Maximum stock and sector contribution shares were 20.58% and 31.56%. This short period is not interpreted through annualized performance.

## E. Comparison and decision

V1 is **REJECT STRATEGY V1** under the thresholds frozen before holdout inspection. Holdout direction was broadly benchmark-consistent, but V1 fails because development produced unexecutable exits/stale positions and a -46.22% net drawdown, beyond the frozen 40% conditional limit. Costs are also material: 25 bps per side reduced holdout return by 2.02%. Full metrics, cost sensitivity, positions, trades, contributions, daily drawdowns, and actual signal/execution dates are published separately.

## F. Paper trading

V1 does not pass the frozen paper-trading gate, so no executable handoff is authorized.

The exact build ID is recorded in `reports/sector_strategy/phase11_strategy_build_manifest.json`. Development target rows: 2,916; holdout target rows: 63.
