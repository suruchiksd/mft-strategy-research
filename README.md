# MFT research data — Phase 2

Scope: **conditional current-universe research**, using the fixed current 120-symbol equity partition universe. This is not a historically unbiased NSE universe. This project currently contains data preparation and validation only: no CSRS, sector/volume factors, targets, portfolio simulation or modelling parameters.

## Reproduce

From this project directory (Python 3.11+; the acceptance build records its exact runtime):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/build_research_dataset.py
.venv/bin/python scripts/build_research_dataset.py --verify-rebuild
.venv/bin/python -m pytest -q --junitxml=reports/pytest-results.xml
.venv/bin/python scripts/validate_research_dataset.py --pytest-xml reports/pytest-results.xml
```

Sources are read-only and configured in `config/research_data.yaml`. All outputs and test temporary files stay within this project. The build opens Parquet through PyArrow directly, without importing or invoking upstream applications. It hashes every input before and after processing, validates outputs, stages them locally, and publishes the manifest last. No raw dataset is copied. Do not run upstream downloaders, migrations or engine commands here.

The content-addressed manifest includes source SHA-256, size, nanosecond mtime, Parquet row counts, all symbols, complete YAML policy, code/evidence hashes and runtime versions. Versioned `data/derived/manifests/<build_id>.json` files are never overwritten by the builder; identical reruns reuse the original build timestamp. `source_manifest.json` points to the latest build via an identical copy. Outputs are overwritten locally only after validation. A full `--verify-rebuild` computes everything again and compares all five Parquet files byte-for-byte without replacing them. A manifest detects upstream changes; it cannot recover an old upstream file that was subsequently replaced. No retrospective source vintage is claimed.

## Artifacts and contracts


- `universe.parquet`: current symbol/token, observed coverage, quality-eligible date range, IRFC identity rule and current curated sector metadata. Missing/conflicting sectors stay null.
- `daily_bars.parquet`: every observed symbol-date; source-as-stored valid-minute OHLCV, timestamp boundaries, minute counts, quality and action flags, explicit eligibility/reasons. Date is Arrow date32; timestamps retain Asia/Kolkata.
- `session_calendar.parquet`: **observed dates only**, expected minute grids where known, schedule evidence and same-date partial-session diagnostics. It is not an official complete holiday calendar.
- `corporate_action_ledger.parquet`: all annual CSV rows, including exact original string columns and JSON, source record numbers, duplicate-key groups, classifications and placeholder exclusion windows. No action factor is applied.
- `minute_exclusions.parquet`: compact provenance of each rejected minute, with original OHLCV and reasons. No giant intermediate minute dataset.
- `reports/phase2_dataset_acceptance.md`: coverage, eligibility, limitations and validation evidence. Full per-symbol summaries accompany it.

## Minute and session policies

OHLC is first valid open, maximum valid high, minimum valid low, last valid close. Volume sums the **same valid records**. Exclude invalid OHLC, nonpositive/nonfinite prices, invalid volume/timestamps, all duplicate timestamp copies, IRFC prelisting rows, and minutes outside known schedules. Record every exclusion. The 21 invalid opening candles on 2024-06-25 produce a later observed open, explicitly flagged, and make those daily rows ineligible. All-invalid days retain null OHLC and zero retained bars; their volume=0 is the empty sum, not a fabricated trading record. Zero-volume valid candles are retained; they do not establish liquidity.

Exact timestamp membership, not just 375 bars, determines completeness. Session overrides are transparent CSV interval records with end-exclusive times and Phase-1 provenance. Annual short sessions and two-segment DR sessions can pass their exact grids. March 2020 halt dates, the 2021-02-24 anomaly, and 2020-04-27 remain quarantined. Unknown schedules retain observed valid minutes for audit only and have null expected-minute counts. Shared partial means multiple symbols short on that same date; it is not proof of an exchange halt. Unknown weekend dates are never inferred to be legitimate. No tolerance for unresolved partial sessions is silently selected.

`first_timestamp`/`last_timestamp` describe observed input. `first_valid_timestamp`/`last_valid_timestamp` describe retained data. `open_is_scheduled_first_minute`, `open_is_first_observed_minute`, `close_is_scheduled_last_minute` and `open_quality` prevent confusing a later open or early close with the exchange boundary. `bar_available_at` waits at least until known scheduled close and last observed minute end; it is a logical data-completion bound, **not** a recovered vendor publication timestamp. Daily close is not claimed to be the official exchange closing price.

IRFC: all timestamps before **2021-01-29** are excluded using the verified NSE listing evidence linked in configuration. Its four contaminated daily records remain for audit. Other current labels are not claimed to represent historical security names or membership. No lookback-history gate is implemented.

## Corporate-action limitations and future interval safety

Preserve source prices; never multiply the annual CSV factors. Phase-1 price-continuity evidence supports `LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION` for matching events, excluding the known TVSMOTOR preference-share defect. Rights/demergers are material unresolved; TVSMOTOR, BRITANNIA's unexplained factor=1, and unverified factor events remain ambiguous. Dividends/buybacks use the approved price-momentum scope, without asserting the source identifies every special distribution.

Source `DATE` is **not globally verified as ex-date**. No historical announcement timestamp is invented. The ledger preserves all simultaneous and exact duplicate events; it does not keep-last. Factors and flags are retained as original strings to prevent silent reinterpretation. Classification does not prove vendor adjustment completeness or point-in-time availability.

`before_sessions=0` / `after_sessions=0` is the approved placeholder: exclude unresolved event dates where observed, but do not choose a research window. Configurable positive counts use strictly earlier/later **observed market dates**, including special and partial dates; a non-session source date is not moved to a guessed ex-date. Larger before-windows are retrospective exclusions, not historically known trading signals.

**Never drop ineligible rows and then compute returns across the remaining rows.** `research_eligible` is a row-quality flag, not permission to span an action or missing session. Phase 3 must validate the entire factor/target interval and enforce unresolved-event boundaries. `interval_crosses_unresolved_event` supplies only a boundary guard; it calculates no factors or returns. Every daily row carries `return_interval_validation_required=true` and incomplete action-coverage status. Zero-width exclusions are not a completed window policy.

The action source ends 2026-07-17 while price data ends 2026-07-31. Historical aliases, missing events, date semantics, special distributions, and vendor adjustment conventions remain limitations. No-recorded-event does not certify action-free. The acceptance report states whether these unresolved conditions permit moving beyond design into CSRS calculations.
