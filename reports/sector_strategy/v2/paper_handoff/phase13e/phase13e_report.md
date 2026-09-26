# Phase 13E Position-Cap / State Root-Cause Diagnosis

The repaired replay was read without changing Strategy V2 or generic paper-engine code. It produced 112 comparison rows, 30 exact matches and 82 mismatches; risk produced 2021 decisions, 58 rejections, all 58 for maximum open positions, and 0 insufficient-cash rejections.

The last exact sampled state is SMV2-0019; the first sampled state divergence is SMV2-0020. At SMV2-0020 the research simulator values holdings at the current execution open when computing pretrade equity, while the repaired adapter uses Portfolio equity marked at the previous observable close. That explains the first two one-share quantity differences. Subsequent differences are state cascades: the replay skips retained-position resizing and does not implement the complete signal-time fallback sequence. It evaluates target BUYs while the engine reports nine open positions, producing the 58 cap rejections and later quantity/state differences.

`Portfolio.positions` retains zero-quantity objects, but `Portfolio.open_positions` filters them out and RiskManager counts open positions plus pending keys. Generic engine behavior is therefore not the identified root cause.

The 2pp retained resize is **NOT_IMPLEMENTED** in the repaired replay. The complete frozen fallback sequence is **PARTIALLY_IMPLEMENTED** (selected target names only). These are the smallest future Phase13F adapter fixes; no fixes were applied in Phase13E.

No performance statistic or post-2026-09-17 data was inspected.
