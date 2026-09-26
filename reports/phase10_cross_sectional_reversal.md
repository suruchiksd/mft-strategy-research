# Phase 10 — Preregistered Cross-Sectional Reversal

**Overall decision: RESEARCH FURTHER**

## 1. Preregistration ordering

The reversal design was frozen before any post-2026-07-17 reversal outcome was calculated or inspected. The preregistration manifest hash is `fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995`. It fixes REV05, REV20, six outcome horizons, BASIC_LIQUID, MODERATE_LIQUID, and the acceptance rules.

## 2. Discovery / historical evidence

This is a mathematical reorientation of accepted Phase-9 controls, not new validation. REV05 has mean IC 0.040292; REV20 has mean IC 0.022431. All twelve candidate/horizon historical IC means are positive in REV orientation. Full cells are in `historical_discovery_summary.csv`.

## 3. Corporate-action extension audit

The accepted annual source and the later local archive both end on 2026-07-17. The official NSE page shows post-cutoff actions and uses a richer purpose/ex-date/record-date schema, but no local reproducible updater or reviewed transformation into the accepted `DATE/adj_factor/valid` semantics exists. Therefore corporate-action certification was **not extended**. The accepted Phase-5 ledger was not modified.

## 4. Untouched confirmation

No confirmation return was computed or inspected. Signal dates strictly after 2026-07-17 have zero certified observations for every horizon. Confirmation outputs preserve schemas but contain no analytical rows. REV05 and REV20 are both `INSUFFICIENT SAMPLE`.

## 5. Answers

1. Yes, the hypothesis was preregistered before confirmation outcome inspection.
2. No, corporate-action certification could not be extended under the accepted semantics.
3. There is no certified untouched confirmation period.
4. Every outcome horizon has zero certified confirmation dates and observations.
5. REV05 is positive in historical discovery orientation; untouched persistence is unknown.
6. REV20 is positive in historical discovery orientation; untouched persistence is unknown.
7. BASIC/MODERATE confirmation consistency is not observable.
8. Confirmation decile monotonicity is not observable.
9. Date influence cannot be evaluated with zero certified dates.
10. Non-overlap confirmation cannot be evaluated.
11. Confirmation uncertainty intervals cannot be estimated.
12. The certified sample is not large enough; it is empty.
13. Reversal remains a preregistered candidate, but it is not retained for complementarity research yet.

## 6. Exact next stage

Obtain and independently review a reproducible NSE corporate-action extract covering 2026-07-18 onward, preserve raw purpose/ex-date/record-date fields, reconcile its overlap with the accepted ledger, and freeze the resulting extension hash. Then rerun this already-frozen confirmation design without changing candidates, horizons, universes, or acceptance rules. Do not combine reversal with Sector Momentum until that confirmation is complete.

Accepted Phase-5 through Phase-9 artifacts were verified unchanged: {'phase5_build_id': 'ce7d1d27638b3c7e448b6e9bfc5b659e4e7bb77db1c6cf5c377edafce7262524', 'phase5_verified_outputs': 24, 'phase6_build_id': 'e1c1a5c6ad6c7b2e521d00c4fcb97f4bbb21047575ca0de5a7a3f36cb573367b', 'phase6_verified_outputs': 15, 'phase7_build_id': 'f41dbfd6019e517e3696076f7330b083622732c8a785f3bfa3f65e5573d335df', 'phase7_verified_outputs': 21, 'phase8_build_id': '422d5459c295f5d6fce9f3648487528c1b4f71e56956ef19c7e7809d3cb05e5e', 'phase8_verified_outputs': 14, 'phase9_build_id': '00a3e8a873d6488d7a97a642347ec0f59d53e94dcb7f32e4ea20841c54f1455b', 'phase9_verified_outputs': 22}.
