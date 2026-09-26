# Phase 10B — Confirmation Classification Blocker

**Status: UNACCEPTED — preregistration taxonomy is not exhaustive for the observed REV05 evidence.**

The official-NSE corporate-action extension passed its frozen gate as `CONDITIONAL PASS FOR REVERSAL CONFIRMATION`. It covers admitted endpoints through 2026-09-11 and was frozen before confirmation outcomes were inspected.

The untouched confirmation calculation then produced an outcome state that the frozen candidate taxonomy does not classify:

- REV05 has positive BASIC_LIQUID mean Rank IC for 4/6 outcome horizons, positive MODERATE_LIQUID mean Rank IC for 4/6, and positive non-overlap horizon means for 4/6.
- REV05 nevertheless fails the full directional-retention rule because leave-one-date removal flips the weakly positive 5-session outcome sign.
- The preregistration assigns `SUPPORTIVE BUT SHORT SAMPLE` only when every directional rule passes, `MIXED` only with 2–3 positive primary horizons, and `CONTRADICTORY` only with 0–1 positive primary horizons.
- Therefore REV05's 4-positive-horizon state with a failed influence condition is outside every frozen classification branch.

REV20 has positive BASIC_LIQUID mean Rank IC for 1/6 horizons and fits `CONTRADICTORY`, but an overall Phase-10 decision cannot be accepted while REV05 is unclassified.

The provisional calculation is preserved under `reports/reversal/confirmation_unaccepted/` and `data/derived/reversal_confirmation_panel.unaccepted.parquet` for audit. It is not an accepted publication. The production builder now fails closed if this state occurs.

Resolving the gap requires an explicit post-outcome methodology decision. Any amendment must be labeled post-outcome and cannot retroactively make this confirmation a pristine preregistered classification. The scientifically clean option is to treat the current sample as evidence that exposed the rule gap, freeze a complete decision table, and apply it only to additional untouched certified dates.
