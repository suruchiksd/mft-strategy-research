# Production adapter gap audit — final

The installed production module is
`paper_trading.adapters.sector_momentum_v2.adapter`. It now consumes target
state, current Portfolio state, and quote inputs without historical reference
files.

| Feature | Historically certified implementation | Production adapter | Result |
|---|---|---|---|
| Canonical `NSE:<symbol>` identity | Yes | Yes | MATCH |
| Execution-open pretrade valuation | Yes | Yes | MATCH |
| Raw-provider execution fallback | Yes | Yes | MATCH |
| EQ-only new entries | Yes | Yes | MATCH |
| Held EQ→BE exits | Yes | Yes | MATCH |
| 2pp retained resizing | Yes | Yes | MATCH |
| Cash clipping | Yes | Yes | MATCH |
| Max nine actual positions | Yes | Yes | MATCH |
| Sell-before-buy sequencing | Yes | Yes | MATCH |
| End-of-day normalized/raw/previous mark | Yes | Yes | MATCH |
| Portfolio/session persistence | Yes | Yes | MATCH |
| Dry-run order generation | Yes | Yes | MATCH |
| Fail-safe malformed/duplicate state handling | Yes | Yes | MATCH |

The adapter does not import or read `v2_trades.csv`, `v2_positions.csv`,
`v2_equity_curve.csv`, or parity comparison files. Generic engine classes were
not modified.
