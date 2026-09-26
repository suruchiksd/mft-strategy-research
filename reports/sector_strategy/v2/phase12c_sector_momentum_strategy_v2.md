# Phase 12C — Sector Momentum Strategy V2 Development Backtest

**Decision: CONDITIONAL PROSPECTIVE CANDIDATE**

This is a V2 DEVELOPMENT / HISTORICAL STRATEGY SIMULATION through 2026-09-17, not fresh out-of-sample validation. The frozen Phase12B specification and acceptance JSON were loaded without modification.

## Results

The first executable date was 2020-05-04. Primary 25-bps cumulative return was 169.93%; gross cumulative return was 364.76%; CAGR 17.15%; Sharpe 0.811; maximum drawdown -36.41%; mean weekly turnover 0.634; cost-retention ratio 0.466.

Cost sensitivity cumulative returns: 0 bps=364.76%, 10 bps=273.41%, 25 bps=169.93%, 50 bps=50.69%.

V2 turnover attribution was {'FORCED_OPERATIONAL': 0.0, 'SECTOR_ENTRY_EXIT': 0.4815341429369501, 'WEIGHT_REBALANCING': 0.00823335516574326, 'WITHIN_SECTOR_STOCK_REPLACEMENT': 0.5102325018973066}. V1 reference shares were sector entry/exit 87.293%, stock replacement 10.235%, weight restoration 2.222%, and operational 0.250%.

The simulation recorded 0 operational events, 0 unavailable exit attempts, 0 stale marks, and no fabricated prices. Maximum simultaneous trapped capital and duration are reported in the machine-readable event/position files. Maximum stock and sector absolute contribution shares were 3.40% and 13.81%.

The acceptance gates were frozen before this run and are recorded individually in `phase12c_v2_acceptance.json`. V2 is not paper-traded and no post-2026-09-17 performance is included.
