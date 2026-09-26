# Exact sizing formulas

Research V2: `pretrade = cash + Σ(q_i × supported_open_i_or_last_mark_i)`; `target_n = max(len(intended), 1)`; `target_value = pretrade / target_n`; retained weight is `q_i × open_i / pretrade`; resize only when `abs(preweight - 1/target_n) >= 0.02`; desired shares are `floor(target_value / (open × (1 + 5/10000) × (1 + 20/10000)))`, then BUY quantity is clipped to available cash.

Phase13B replay: `target_value = paper_equity / len(target)`; new-entry shares are `floor(target_value / (open × 1.0025))`; retained-name detection used `symbol in account.positions` although portfolio keys are `NSE:symbol`; no independent retained-position 2pp resize path was implemented. Risk then rejected the full requested quantity rather than applying the research simulator cash clip.
