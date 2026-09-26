# Accepted research resize sequence

`simulate_v2` freezes pretrade equity before scheduled sells, computes target value once, sells deselected holdings, processes retained resizes in sorted symbol order, applies cash clipping to retained BUYs, then processes new entries in sector strength/liquidity/symbol order. Retained resizing occurs before new-entry sizing.
