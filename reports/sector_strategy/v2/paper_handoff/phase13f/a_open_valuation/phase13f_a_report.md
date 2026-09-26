# Phase 13F-A — Execution-open valuation

The V2-specific orchestration was changed only for the Phase12C execution-open valuation basis. Generic paper-engine code and Strategy V2 were unchanged.

SMV2-0020 now reconciles completely. Sample parity improved from 30/112 exact in the Phase13D repaired replay to 47/112 exact, with 65 remaining mismatches. The execution-open correction did not create an earlier divergence. Risk produced 2,025 evaluations and 62 maximum-position rejections; no insufficient-cash rejection occurred.

This gate is frozen as the input to 13F-B. No fallback implementation was started and no post-2026-09-17 performance was inspected.
