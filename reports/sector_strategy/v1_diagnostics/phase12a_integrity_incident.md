# Phase 12A integrity incident and recovery

Status: RESOLVED. The authoritative Phase 12A publication is restored to
`9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5`.

The accepted historical build was `9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5`. A different, unaccepted workspace state,
`c2ce47c379da33d39f40a232d2bed03a32bfd33d55f35fa8cc966434b42bec2d`, was
found in the published Phase 12A directory. The `c2ce` manifest matched its
then-present files, but it did not match the accepted build and was not
accepted.

## Controlled recovery

The current Phase 12A analytical code and accepted Phase 11 inputs were replayed
into isolated temporary directories under four independent process conditions:
`PYTHONHASHSEED=0`, `PYTHONHASHSEED=1`, `PYTHONHASHSEED=2`, and the default
process seed. Each replay produced all 17 analytical outputs byte-for-byte
identically and independently computed build ID `9a3b56f...`.

The original builder then regenerated the normal publication and independently
computed `9a3b56f...`. Its verification passed 17/17 byte-identical. The
published analytical files now equal the controlled authoritative replay.

## c2ce comparison

Compared with the controlled `9a3b` replay, the unaccepted `c2ce` state had:

| Output | Classification | Evidence |
|---|---|---|
| `cost_attribution.csv` | `NUMERIC_DIFFERENCE` | cost totals and shares differed materially |
| `drawdown_sector_attribution.csv` | `SEMANTIC_DIFFERENCE` | accepted contribution columns were absent |
| `drawdown_stock_attribution.csv` | `SEMANTIC_DIFFERENCE` | accepted contribution columns were absent |
| `gross_sector_contribution.csv` | `NUMERIC_DIFFERENCE` | values differed at floating-point aggregation precision |
| `gross_year_contribution.csv` | `NUMERIC_DIFFERENCE` | values differed at floating-point aggregation precision |
| `operational_exception_audit.csv` | `SEMANTIC_DIFFERENCE` | trapped-session and unavailable-position fields differed |
| `sector_rank_boundary_churn.csv` | `ORDER_ONLY` | deterministic row sorting made values identical |
| `stock_rank_boundary_churn.csv` | `ORDER_ONLY` | deterministic row sorting made values identical |
| `turnover_decomposition.csv` | `SEMANTIC_DIFFERENCE` | row count differed, 762 versus 747 |
| `turnover_yearly.csv` | `SEMANTIC_DIFFERENCE` | row count differed, 31 versus 29 |
| `weight_rebalance_attribution.csv` | `NUMERIC_DIFFERENCE` | weight-restoration notionals differed |
| `phase12a_sector_strategy_v1_diagnostics.md` | `SEMANTIC_DIFFERENCE` | report text/hash differed |
| `phase12a_build_manifest.json` | `MANIFEST_ONLY` | identified the unaccepted `c2ce` state |

The remaining analytical outputs were byte-identical between the compared
states. The differences were therefore not a harmless serialization-only
variant.

## Provenance finding

The session log shows the accepted `9a3b` build and verification completed,
followed by a later filesystem write that left the `c2ce` files. File mtimes
place the drift after the final source edits and after the accepted replay.
The available log does not identify a unique writer command or prove whether
that write came from an older process finishing late. The exact writer cause is
therefore **UNPROVEN**. The reproducible finding is that `c2ce` was a transient,
unaccepted workspace overwrite; it is not the accepted analytical state.

## Invariants and scope

No Phase 12A analytical conclusion changed. The accepted conclusions remain:
implementation failure dominant within a BOTH diagnosis; development turnover
shares of approximately 87.293% sector entry/exit, 10.235% within-sector stock
replacement, 2.222% weight rebalancing, and 0.250% forced operational; six
EQ-to-BE affected holdings; maximum development drawdown of approximately
-46.22%; and no fabricated price or exit.

No V2 P&L was inspected or calculated. No post-2026-09-17 strategy performance
was inspected. Phase 12B remains unfrozen work in progress and was not run.
