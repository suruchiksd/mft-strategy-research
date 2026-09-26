# Phase 10 Cross-Sectional Reversal Preregistration

This document freezes Factor 1B before any return after 2026-07-17 is inspected for reversal performance.

## Discovery boundary and status

The discovery period is 2020-01-01 through 2026-07-17. Phase-5 short/medium formation evidence and the Phase-9 VM01/VM02 controls generated the reversal hypothesis. Reexpressing those accepted results with the opposite sign is historical discovery evidence, not out-of-sample validation.

REV05 and REV20 are new hypothesis identifiers. The sign is frozen now: `REV05 = -1 * price_return_5` and `REV20 = -1 * price_return_20`. Higher values identify weaker recent performers. The previously observed 10-session reversal remains a historical diagnostic and is not a confirmation candidate.

## Frozen design

- Primary universe: BASIC_LIQUID.
- Sole universe sensitivity: MODERATE_LIQUID.
- Future outcomes: exactly 1, 2, 3, 5, 10, and 20 exchange sessions.
- Signal dates: strictly after 2026-07-17.
- Same-date ranks use all signal-valid members before outcome availability is applied.
- Outcomes must start after the signal date and pass the accepted Phase-5 identity, exact-session, endpoint, and corporate-action interval rules.
- No volume, sector, regime, volatility, weighting, trading, portfolio, or execution input is permitted.

## Corporate-action gate

No post-cutoff outcome may be inspected until a new Phase-10 corporate-action extension is accepted. The extension must preserve the accepted source schema and semantics, record provenance and hashes, cover every outcome endpoint admitted, and retain conservative blocking of material, ambiguous, and conventional unit-changing events. Ledger silence alone cannot extend certification.

## Frozen analysis

For each candidate and horizon: daily Spearman Rank IC, summary IC statistics, signal cross-section size, deciles D1 through D10, D10-D1, monotonicity, top/bottom 5/10/20 percent, all non-overlap offsets, deterministic circular-block bootstrap with 2,000 replications and block length `max(10, 2H)`, BASIC/MODERATE sensitivity, and leave-one-date-out influence.

## Frozen acceptance and classification

A candidate satisfies the directional retention rule only when: all six historical REV-oriented discovery ICs are positive; at least four of six confirmation mean ICs are positive; BASIC and MODERATE average ICs are both positive with at least four positive MODERATE horizons; at least four non-overlap horizon summaries are positive; and dropping any one date does not reverse the supporting horizon signs.

An evaluable horizon requires at least 20 daily IC dates. `SUPPORTED` additionally requires at least 60 dates for every horizon. A directionally qualifying candidate with 20–59 dates in any horizon is `SUPPORTIVE BUT SHORT SAMPLE`. With an accepted extension and adequate dates, two or three positive primary horizons is `MIXED`; zero or one is `CONTRADICTORY`. Missing corporate-action certification or fewer than 20 dates for any horizon is `INSUFFICIENT SAMPLE`.

Overall: both candidates `SUPPORTED` gives `PASS FOR COMPLEMENTARITY RESEARCH`; at least one `SUPPORTED`, or both `SUPPORTIVE BUT SHORT SAMPLE`, gives `CONDITIONAL PASS`; plausible/mixed/insufficient evidence gives `RESEARCH FURTHER`; both candidates `CONTRADICTORY` on evaluable certified data gives `FAIL`.

These rules are fixed before confirmation outcomes. They may not be weakened after seeing results.
