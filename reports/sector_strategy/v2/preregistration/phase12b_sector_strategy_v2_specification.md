# Phase 12B — Sector Momentum Strategy V2 Specification

> **PREREGISTERED BEFORE V2 P&L**  
> `v2_pnl_inspected = false`  
> `post_2026_09_17_v2_performance_inspected = false`

## Unchanged alpha

V2 uses only the accepted Phase-7 equal-weight 20-session Sector Relative Momentum signal in `STABLE_IDENTITY_BASIC_LIQUID`, with a five-stock sector floor. It remains long-only NSE cash, three sectors, three stocks per sector, maximum nine positions, weekly final-session signals, next-valid-session-open execution, equal intended weights, whole shares, cash only, and no leverage. No reversal, volume, stock-momentum, regime, volatility, stop, target, ATR, machine-learning, or combined signal is permitted.

## Frozen retention rules

- New sectors require strength rank 1–3. Existing sectors remain through rank 5 and exit above rank 5. Vacancies admit only current ranks 1–3, tie-broken by sector code.
- New stocks require signal-time trailing-turnover rank 1–3 within the active sector. Existing stocks remain through rank 5 while all eligibility and tradability conditions pass; ties use symbol.
- The complete liquidity list is hashed at signal close for audit, while execution fallback candidates remain limited to names that were top-three eligible at that signal.
- A retained position is resized only when its absolute deviation from intended equal weight is at least exactly 2 percentage points.

## Tradability and execution

New entries require stable identity, unique mapping, BASIC_LIQUID membership, valid reported EQ row, positive close, positive trailing turnover, recent presence, no point-in-time-known blocked action, and EQ status at the signal. BE never receives a new entry.

At the next session open, ranks remain frozen. An unavailable intended entry is skipped; execution walks only the already-frozen top-three list, then leaves cash. An unavailable exit remains held at its last observable mark and is retried each session. A valid observed EQ or BE open may execute an exit. No missing row becomes a zero price. A trapped position consumes marked capital and one of nine slots.

The raw audit found 376 BE rows across 378 historical stale dates; all 376 observed BE rows had positive opens. Missing rows remain fail-closed. The state-only replay processed 339 signals, never exceeded 9 positions, froze 339 signal-time replacement lists, and created no P&L column.

## Costs and acceptance

Primary cost remains 25 bps per side (20 transaction-cost plus 5 adverse-slippage bps), with fixed 0/10/25/50 sensitivities. Mean weekly gross turnover must be no more than 0.65. The 25-bps net cumulative return, CAGR, and Sharpe must be positive. If the zero-cost cumulative gain is positive, the 25-bps cumulative wealth gain must retain at least 40% of that gain: `(NAV25_end - 1) / (NAV0_end - 1) >= 0.40`. Maximum drawdown at or below -40% rejects V2; passing all gates with drawdown from -40% to below -35% is conditional; drawdown at least -35% is required for ready status. Stock and sector absolute-contribution shares are capped at 50% and 60%.

## Boundary

All data through 2026-09-17 is development evidence. Fresh validation signals must be strictly after 2026-09-17. No post-boundary V2 performance was read. This specification authorizes neither a backtest in Phase 12B, automatic paper trading, nor real-money deployment.
