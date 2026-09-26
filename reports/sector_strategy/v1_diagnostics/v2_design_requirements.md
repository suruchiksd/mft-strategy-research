# Diagnostic requirements for any future Strategy V2

## MUST FIX

- Freeze a point-in-time tradability contract covering EQ-to-BE transfers, suspensions, absent opens, stale valuation, unexecutable exits, and how trapped positions consume the position limit.
- Freeze execution fallback behavior before new P&L, including what happens when an intended entry or exit has no valid next-session open.
- Define reconciliation rules for last observable marks without fabricating prices or exits.
- Address cost and turnover feasibility with prespecified acceptance limits; do not choose them from the best historical return.
- Freeze portfolio drawdown/risk acceptance and a new validation interval strictly after 2026-09-17.

## SHOULD INVESTIGATE

- Whether rank-boundary changes cause avoidable sector and within-sector replacement churn.
- Whether pure equal-weight restoration is economically material enough to warrant a tolerance concept.
- Whether sector representation through individual stocks creates avoidable idiosyncratic and tradability risk.
- Whether concentration and prolonged underwater periods remain acceptable independently of factor Rank IC.

## OPTIONAL

- Alternative implementation instruments or representation mechanisms, subject to independent data and tradability audits.
- A separate study of execution timing and realized paper slippage after a V2 contract is frozen.

Any rank buffer, weight band, sector count, stock count, rebalance cadence, cost model, fallback rule, or position-limit treatment is a new strategy decision. It requires preregistration; none is selected here. The inspected 2026-08-03 through 2026-09-17 interval is development evidence for any V2 and cannot be reused as fresh validation.
