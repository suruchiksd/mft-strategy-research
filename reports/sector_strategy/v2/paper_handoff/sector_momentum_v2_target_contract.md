# Sector Momentum V2 target-state contract

The production adapter must receive one frozen weekly target-state file. It
must contain the schema version `SECTOR_MOMENTUM_V2_SIGNAL_V1` and these fields:

`strategy_id`, `strategy_version`, `strategy_preregistration_hash`,
`strategy_build_reference`, `rebalance_id`, `signal_date`,
`execution_earliest_date`, `sector`, `sector_code`,
`sector_strength_rank`, `symbol`, `liquidity_rank`, `selection_status`,
`target_weight`, `target_slot`, `current_holding_expected`, `exit_intent`,
`signal_series`, `tradability_status`, `corporate_action_safe`,
`replacement_priority`, and `reason`.

The adapter must reject a missing or malformed file, duplicate symbol within a
rebalance, duplicate execution date, unauthorized strategy hash/version,
non-EQ new entry, invalid weight, or more than nine active target positions.
It must fail closed with no new order.

The target file describes intent and frozen replacement ordering. It does not
contain broker fills, historical trades, or historical P&L. The production
engine must derive orders from this target state plus current Portfolio state,
cash, and supported execution quotes.
