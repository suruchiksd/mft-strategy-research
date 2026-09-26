# Phase-2 dataset acceptance

## 1. Executive summary

Built **188,451 daily rows**, **120 symbols**, with **184,709 eligible rows (98.01%)**. Research scope: **conditional current-universe research**. Price basis: **source-as-stored price momentum**, with no corporate-action adjustment. This is a validated data foundation, not an assertion that all price intervals are safe.

## 2. Files/code created

Minimal package modules: manifest, universe, sectors, corporate_actions, sessions, daily_bars, validation; build/validate scripts, YAML policy, explicit CSV session overrides, pinned dependencies and tests. Derived outputs: universe.parquet, daily_bars.parquet, corporate_action_ledger.parquet, session_calendar.parquet, minute_exclusions.parquet, source_manifest.json and immutable manifests/<build_id>.json. No upstream code is imported for execution; no raw data copy, factors or backtests.

Build ID: `049f5a61be599b277f775105fe8935128c2015d98867bcf76dfbd98f07c80988`. Build timestamp: `2026-09-13T15:56:26.724661+00:00`. Source files: 863; every file has SHA-256, size and mtime_ns; Parquet files also have row counts. Code/evidence hashes, runtime versions, full config and output hashes are recorded. A rebuild fails if sources change during execution. Versioned manifests are write-once by the builder; the latest manifest is a pointer copy. Upstream revisions can be detected, not undone without a separately archived source.

## 3. Exact universe used

ABB, ACC, ADANIENSOL, ADANIENT, ADANIGREEN, ADANIPORTS, ADANIPOWER, AMBUJACEM, APOLLOHOSP, ASHOKLEY, ASIANPAINT, AXISBANK, BAJAJ-AUTO, BAJAJFINSV, BAJAJHLDNG, BAJFINANCE, BANKBARODA, BEL, BERGEPAINT, BHARTIARTL, BPCL, BRITANNIA, CANBK, CGPOWER, CHOLAFIN, CIPLA, COALINDIA, COFORGE, CUMMINSIND, DABUR, DIVISLAB, DIXON, DLF, DMART, DRREDDY, EICHERMOT, ETERNAL, GAIL, GODREJCP, GRASIM, HAL, HAVELLS, HCLTECH, HDFCAMC, HDFCBANK, HDFCLIFE, HEROMOTOCO, HINDALCO, HINDUNILVR, HINDZINC, HYUNDAI, ICICIBANK, ICICIGI, ICICIPRULI, INDHOTEL, INDIGO, INDUSINDBK, INDUSTOWER, INFY, IOC, IRFC, ITC, JINDALSTEL, JIOFIN, JSWENERGY, JSWSTEEL, KOTAKBANK, LICI, LODHA, LT, LTM, LUPIN, M&M, MANKIND, MARICO, MARUTI, MAXHEALTH, MAZDOCK, MOTHERSON, MPHASIS, MUTHOOTFIN, NESTLEIND, NTPC, OFSS, ONGC, PERSISTENT, PFC, PIDILITIND, PNB, POLYCAB, POWERGRID, RECLTD, RELIANCE, SBILIFE, SBIN, SHREECEM, SHRIRAMFIN, SIEMENS, SOLARINDS, SUNPHARMA, TATACAP, TATACOMM, TATACONSUM, TATAPOWER, TATASTEEL, TCS, TECHM, TITAN, TMCV, TMPV, TORNTPHARM, TRENT, TVSMOTOR, ULTRACEMCO, UNIONBANK, UNITDSPR, VBL, VEDL, WIPRO, ZYDUSLIFE.

No historical membership reconstruction. Sectors: 116 UNIQUE, one CONFLICT (ADANIGREEN), three UNMAPPED (ADANIENSOL, ADANIPOWER, LTM). Conflicts/unmapped have null sector fields and preserved candidate/source metadata.

## 4. Daily dataset row/date coverage

2020-01-01 through 2026-07-31; 1,635 observed market dates; 188,451 observed symbol-dates. All observed dates remain, including days with no valid minutes. No unobserved bars/days are fabricated. Calendar is an observed-date ledger, not a certified exchange holiday calendar. First/last valid research dates are in universe.parquet; they express row-quality eligibility, not listing dates or lookback sufficiency.

## 5. Session classifications/counts

| session_quality | rows |
| --- | --- |
| NORMAL_COMPLETE | 183340 |
| PARTIAL_SHARED_MARKET_EVENT | 3349 |
| KNOWN_SPECIAL_COMPLETE | 1378 |
| PARTIAL_SYMBOL_SPECIFIC | 254 |
| UNKNOWN_IRREGULAR | 109 |
| DATA_QUALITY_ISSUE | 21 |

Exact timestamp grids are compared to end-exclusive intervals. Known annual short sessions, two-segment DR sessions and audited weekend sessions can be complete. Unknown weekends, March 2020 halt dates, the February 2021 extended-session anomaly and 2020-04-27 remain ineligible. Exact expected minutes are null where no verified interval is available. Shared partial means at least two symbols on the same date have a grid shortfall; it describes breadth, not a proven exchange cause. No future dates determine an earlier grid.

## 6. Invalid-data handling

Excluded 104 minute records from OHLC **and volume**, with source file, timestamp, original values and reasons in minute_exclusions.parquet. All 21 invalid 2024-06-25 09:15 candles are omitted, and their daily rows are ineligible. The first valid open is retained but open_is_scheduled_first_minute/open_is_first_observed_minute are false. No replacement values or forward fills. Duplicate timestamp copies are all excluded rather than selecting a winner. Unexpected minutes outside known intervals are excluded and their date flagged. Unknown schedules aggregate valid observed minutes for audit only. Zero-volume bars are retained and counted. Null daily OHLC with zero valid_bars is explicit absence; volume=0 then means sum of zero retained records. Close is last valid minute close, not the official exchange daily close. Availability is no earlier than known scheduled close and last observed minute end.

## 7. IRFC handling

Verified identity floor: 2021-01-29, linked in config to NSE listing evidence. All 31 prelisting minutes on four dates are excluded from aggregation; the four daily audit records remain ineligible with null OHLC. No valid start was inferred from the raw minimum.

## 8. Corporate-action ledger summary

| research_impact | affects_current_universe | events |
| --- | --- | --- |
| LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION | True | 41 |
| MATERIAL_UNRESOLVED_EVENT | False | 287 |
| MATERIAL_UNRESOLVED_EVENT | True | 14 |
| NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM | False | 7843 |
| NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM | True | 1071 |
| UNKNOWN_OR_AMBIGUOUS | False | 494 |
| UNKNOWN_OR_AMBIGUOUS | True | 2 |

All 9,752 source records retained losslessly, including source JSON and original string columns; 60 rows in 30 duplicate-key groups retained. Date remains generic source date, not an inferred ex-date; no announcement availability is invented. Phase-1 conventional-action evidence supports a LIKELY classification only; TVSMOTOR preference distribution and BRITANNIA's unexplained factor=1 are ambiguous. Rights/demergers remain material unresolved. Buyback factor zero is never multiplied. Dividends are retained under the price-momentum policy; the source cannot distinguish special distributions.

16 current-universe EQ events require exclusion review. Windows: 0 sessions before / 0 after. Default **zero/zero is a placeholder**, with exact recorded event dates excluded where observed; a non-session date is not silently moved. The mechanism counts observed market dates, including special/partial dates. Ledger supplies window anchors, event IDs and coverage limitations. **Never filter eligible rows and then calculate returns across removed dates.** Phase 3 must validate full input/target intervals and unresolved boundaries (an interval guard exists; no returns are calculated).

## 9. Number and percentage of research-eligible rows

**184,709 / 188,451 = 98.0143%**. Eligibility is a per-row quality gate only; no lookback, holding horizon, direction or capital eligibility exists.

## 10. Exclusion counts by reason

| reason | rows |
| --- | --- |
| PARTIAL_SESSION_UNRESOLVED | 3603 |
| UNKNOWN_IRREGULAR_SESSION | 109 |
| UNEXPECTED_SESSION_MINUTES | 52 |
| INVALID_OHLC | 21 |
| CORPORATE_ACTION_UNRESOLVED | 16 |
| PRELISTING_IDENTITY_CONTAMINATION | 4 |
| NO_VALID_MINUTES | 4 |

Reasons overlap; their sum is not the number of excluded rows.

## 11. Symbols with materially reduced usable history

| symbol | observed_sessions | eligible_sessions | first_valid_research_date | last_valid_research_date | excluded_sessions | eligible_pct |
| --- | --- | --- | --- | --- | --- | --- |
| SOLARINDS | 1635 | 1137 | 2020-03-16 | 2026-07-31 | 498 | 69.541 |
| BAJAJHLDNG | 1635 | 1364 | 2020-01-13 | 2026-07-31 | 271 | 83.425 |
| CGPOWER | 1635 | 1411 | 2020-06-02 | 2026-07-31 | 224 | 86.3 |
| ADANIENSOL | 1635 | 1485 | 2020-01-03 | 2026-07-31 | 150 | 90.826 |
| TATACOMM | 1635 | 1490 | 2020-01-03 | 2026-07-31 | 145 | 91.131 |
| OFSS | 1635 | 1494 | 2020-01-08 | 2026-07-31 | 141 | 91.376 |
| HAL | 1635 | 1530 | 2020-01-03 | 2026-07-31 | 105 | 93.578 |
| ABB | 1635 | 1531 | 2020-01-10 | 2026-07-31 | 104 | 93.639 |
| PERSISTENT | 1635 | 1534 | 2020-01-01 | 2026-07-31 | 101 | 93.823 |
| LODHA | 1312 | 1242 | 2021-04-20 | 2026-07-31 | 70 | 94.665 |
| JSWENERGY | 1635 | 1556 | 2020-01-02 | 2026-07-31 | 79 | 95.168 |
| MAXHEALTH | 1475 | 1408 | 2020-08-24 | 2026-07-31 | 67 | 95.458 |
| MAZDOCK | 1440 | 1375 | 2020-10-13 | 2026-07-31 | 65 | 95.486 |
| VBL | 1635 | 1583 | 2020-01-03 | 2026-07-31 | 52 | 96.82 |
| MPHASIS | 1635 | 1592 | 2020-01-01 | 2026-07-31 | 43 | 97.37 |

Sorted by retained fraction, with no modelling cutoff selected. Full 120-symbol table: phase2_usable_history.csv. TMCV/TATACAP/HYUNDAI also have short absolute histories, irrespective of retained percentage.

## 12. Remaining unresolved issues

Vendor adjustment completeness, volume basis, historical aliases and special distributions remain unverified. Corporate-action files lack ex-date/announcement lineage and end 2026-07-17, before OHLCV's 2026-07-31 endpoint. No event recorded does not mean action-free; daily rows carry incomplete coverage status. No period after the last recorded event is silently certified action-free or automatically truncated. Unknown shared holes, the full exchange calendar and official daily endpoints remain unresolved. Current-universe selection is deliberately conditional, not survivorship-free.

## 13. Tests run and results

Full pytest suite: 37 tests; 0 failures; 0 errors; 0 skipped.

Dataset checks: 35 passed. Full rebuild byte identity: **PASS**. Future-row isolation is tested on deterministic fixtures; arbitrary vendor revisions to historical rows are detected by hashes, not assumed away.

Commands (from project root):

```bash
.venv/bin/python scripts/build_research_dataset.py
.venv/bin/python scripts/build_research_dataset.py --verify-rebuild
.venv/bin/python -m pytest -q --junitxml=reports/pytest-results.xml
.venv/bin/python scripts/validate_research_dataset.py --pytest-xml reports/pytest-results.xml
```

## 14. SAFE TO BEGIN CSRS RESEARCH?

**NOT YET for unrestricted CSRS factor/target calculations.** Phase-2 data engineering is accepted when validation and deterministic rebuild checks pass; the foundation is ready for Phase-3 design and interval acceptance. Zero-width event flags do not protect lookbacks or future labels crossing unresolved actions, and action-date/coverage limitations still need an explicit Phase-3 treatment. research_eligible=true is not certification of an arbitrary multi-day return. No factor calculation was started.

## 15. Exact recommended Phase-3 scope

First agree unresolved-event interval/window treatment, action-date and coverage limitations, and calendar restrictions. Specify a preregistered CSRS definition/target and validation design without importing engine defaults. Require all factor and outcome inputs to pass row and interval checks, preserve the trading-date index, and enforce information availability. Only after that acceptance, authorize price-momentum CSRS experiments labelled conditional current-universe research. Sector/volume factors and portfolio backtests remain separate later work.
