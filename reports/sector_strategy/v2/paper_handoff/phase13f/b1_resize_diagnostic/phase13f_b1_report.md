# Phase 13F-B1

The frozen A/B evidence was compared without rerunning or changing either stage. A had 62 cap rejections and B had 66; the exact rejection-set differential is 60 new B rows and 56 A rows resolved.

Runtime instrumentation shows all 66 B cap rejections were NEW_ENTRY requests with nine positive positions and zero free slots. No rejected BUY was an existing positive position, so the nine-position retained-BUY case is not the observed cause. Instrument keys and Portfolio keys match (`NSE:CIPLA`), and RiskManager exempts an existing instrument because its cap branch requires `current_quantity == 0`.

The first B mismatch cluster is SMV2-0087. The remaining 60 rows split into 30 resize quantity differences and 30 new-entry quantity differences, downstream of the retained-resize orchestration.

The 2pp behavior test is explicit: 0.0199 generates no order; 0.0200 and 0.0201 generate resize deltas. The nine-position retained BUY test is accepted when identity matches; the nine-position retained SELL remains accepted and leaves the position count at nine.

No fallback work, strategy change, generic engine change, or post-boundary performance inspection occurred.
