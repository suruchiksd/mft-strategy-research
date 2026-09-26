# Phase 10B — Corporate-Action Extension Safety Layer

**Decision: CONDITIONAL PASS FOR REVERSAL CONFIRMATION**

Official NSE structured corporate-action JSON was preserved for 2026-01-01 through 2026-07-17 overlap and 2026-07-18 through 2026-09-11 extension. The immutable build ID is recorded in `phase10_ca_extension_manifest.json`.

## Overlap reconciliation

The official ex-date matched 646/647 accepted rows and 60/61 accepted blocking rows exactly by symbol, series, and date. It recovered all 39 split/bonus rows, all 18 rights rows, and three of four demergers. GUJGASLTD on 2026-07-02 is the sole accepted blocking false negative; the symbol has no accepted price row on or after that date, so endpoint safety independently prevents an interval crossing it. Official-only rows are retained conservatively.

## Frozen safety rules

The blocking date is official ex-date. Split/face-value change, bonus, rights, demerger/spin-off, merger/amalgamation, capital reduction, scheme/arrangement, NCRPS, distributions, and entitlements block price-return intervals. Dividends and buybacks are nonblocking because the accepted overlap classified 565/565 dividends and 21/21 buybacks that way for source-as-stored price momentum. Unknown purposes and exact-symbol ISIN conflicts are REVIEW_REQUIRED_BLOCKED. Mapping uses exact symbols only; no company-name fuzzy matching occurs.

Extension safety counts: {'NONBLOCKING_INFORMATIONAL': 558, 'REVIEW_REQUIRED_BLOCKED': 146, 'BLOCK_PRICE_RETURN_INTERVAL': 45}. Action types: {'DIVIDEND': 689, 'SCHEME_OR_SPECIAL_DISTRIBUTION': 26, 'SPLIT_OR_FACE_VALUE_CHANGE': 8, 'RIGHTS': 8, 'BONUS': 6, 'OTHER_OR_UNKNOWN': 5, 'DEMERGER_OR_SPINOFF': 4, 'BUYBACK': 3}.

## Coverage and conditions

The extension contains 749 events, from 2026-07-20 through 2026-09-11. Certification cannot exceed 2026-09-11. Confirmation must use the frozen raw hashes, exact endpoint/session checks, accepted identity safety, and both historical and extension blocking ledgers.

The conditional decision reflects the single overlap false negative and widespread official/Bhavcopy ISIN-version differences. Both are conservatively contained by endpoint validity and blocked ISIN-conflict events. No reversal outcome was inspected while building this layer.
