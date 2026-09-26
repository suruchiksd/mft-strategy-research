# Phase 13C root-cause attribution

Decision: **PARITY ROOT CAUSE IDENTIFIED**.

All 101 mismatches are classified: 53 REPLAY BUG, 27 POSITION-STATE DIFFERENCE, and 21 CASH / SIZING DIFFERENCE. The first rebalance, SMV2-0018, matched; divergence begins at SMV2-0019 on 2020-05-11 when retained holdings were looked up with plain symbols against `NSE:symbol` Portfolio keys. This caused repeated BUY requests for held names, cash exhaustion, and cascading state differences.

RiskManager `RiskLimits(9,100,100)` means maximum 9 open positions, maximum daily loss of 100% of starting capital, and maximum single-position exposure of 100% of current equity. It does not implement V2 target sizing or cash clipping. Of 3,657 rejections, 3,656 were insufficient cash and one was the maximum-position cap. These are replay/adapter artifacts under the submitted request stream.

No engine or strategy source was modified and no post-boundary performance was inspected.
