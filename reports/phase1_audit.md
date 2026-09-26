# Phase-1 read-only audit — 13 September 2026

No strategy, factor, adjusted-price dataset, daily-bar dataset, or integration was implemented. No upstream source or execution project was modified. Only audit reports were created in this project's reports directory. Inline analysis calculated price changes solely to detect discontinuities; these are not CSRS factors or research labels.

## 1. Executive summary

The source contains exactly **120 symbols, 816 Parquet files, 70,318,959 minute rows**, occupying 1,218,150,613 bytes. All symbols end on 2026-07-31 at 15:29 IST. 109 begin on 2020-01-01 at 09:15 IST.

**Do not apply the corporate-action CSV factors.** Stored prices strongly suggest existing split/bonus adjustment, while demerger treatment is inconsistent or unresolved. The corporate-action files lack provenance, explicit ex-dates, action descriptions, and identity history. A confirmed TVSMOTOR preference-share distribution is represented by an unsafe equity-style factor. IRFC contains pre-equity-listing data. These are blockers to valid CSRS research.

Sector coverage is 117/120; ADANIGREEN conflicts and three symbols are unmapped. A static current universe is objectively identifiable, but it is not a point-in-time historical tradable universe.

## 2. OHLCV inventory

All 816 files have the same physical schema: timestamp[us, tz=Asia/Kolkata]; open/high/low/close float64; volume/instrument_token int64; symbol large_string. Symbol is physically stored as well as encoded in the directory. Year is a partition attribute, not a physical column. Footer timestamp statistics can be presented in UTC by PyArrow; the declared field timezone is Asia/Kolkata. No symbol/year partition mismatch was found. Each symbol has one non-null token and all 120 tokens are distinct; this does not prove historical token identity.

Year partition counts: 2020=112; 2021=114; 2022=115; 2023=117; 2024=118; 2025=120; 2026=120. Years are contiguous within each symbol's observed range. The exact 120 names, first/last timestamps, years, counts and tokens are in ohlcv_inventory.csv and Appendix A. File paths, rows, bytes and row-group counts are in parquet_inventory.csv.

Short histories: TMCV 178 observed sessions, TATACAP 198, HYUNDAI 440, JIOFIN 731, MANKIND 803. Other later starts are LICI, ETERNAL, LODHA, MAXHEALTH and MAZDOCK. No minimum-history exclusion is selected: adequacy depends on the eventual lookbacks, horizons and validation design.

IRFC's apparent 2020 start is invalid as equity-history evidence: 31 bars on four dates precede its 2021-01-29 NSE equity listing, with prices around 750–800 under token 519425. Its next observed date is 2021-01-29. NSE confirms the [listing date](https://www.nseindia.com/static/event-details-listing-ceremony-indian-railway-finance-corporation-limited). Token reuse or vendor identity contamination is a hypothesis, not established causation.

Against the union of 1,635 observed dates, no symbol except IRFC misses an entire peer-observed date between its own first and last dates. IRFC has 265 such absences, all before listing. This does not detect dates absent from the entire dataset and is not exchange-calendar certification.

The partition names exactly match config/universe.toml's 120-symbol list. Thus “all available equity partitions” defines the current storage snapshot unambiguously. No historical membership, delisted-security coverage, stable security IDs, or historical eligibility contract establishes it as a survivorship-free universe. The current symbol labels must not automatically be interpreted as historical labels.

## 3. Data quality

Full row scan results:

- Duplicate symbol/timestamp rows: **0**, including across year files within each symbol.
- Invalid OHLC: **21**, all at 2024-06-25 09:15 IST, matching the upstream invalid-OHLC log. The violated constraints are high below open or low above open. The writer deliberately retains these rows.
- Zero/negative OHLC prices: **0 / 0**. Negative volume: **0**. Null cells: **0**. Nonfinite prices: **0**. Off-minute timestamps: **0**.
- Zero-volume bars: **279,439**. Largest counts: SOLARINDS 66,741; BAJAJHLDNG 45,007; CGPOWER 21,662. A zero-volume candle is not evidence of executable liquidity, and volume adjustment status is unknown.
- 188,451 observed symbol-sessions: 183,862 have 375 bars; 4,538 have fewer; 51 have 376. Exactly 183,861 match the complete 09:15–15:29 grid with no outside bars. There are 35,002 outside-regular-window bars across 633 symbol-sessions.
- 2,039 symbol-sessions lack regular minutes on dates whose cross-symbol median is 375, totalling 26,627 missing regular slots. This includes four invalid prelisting IRFC dates and is a diagnostic, not a final exclusion rule.

Ordinary-grid shortfalls are concentrated in SOLARINDS (484 peer-normal dates), BAJAJHLDNG (254), CGPOWER (209), ADANIENSOL (136), TATACOMM (130), OFSS (127), ABB/HAL (90 each), and PERSISTENT (86). SOLARINDS has just 197 bars on 2020-05-27. Absent minutes may reflect no trading or missing vendor records; trade-level or independent exchange evidence is needed to distinguish them.

Special/irregular dates are fully listed in irregular_dates.csv. Examples:

- Six annual 60-minute sessions: 2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12, 2024-11-01, 2025-10-21. The first five are evening sessions; 2025 is 13:45–14:44. Do not discard dates simply because they are weekends or outside normal hours.
- 2024-03-02 and 2024-05-18 have 105-minute modal sessions with a scheduled break; the former has one 104-bar symbol. A standard 375-bar requirement would misclassify them.
- 2020-03-13 and 2020-03-23 have 316/317 modal bars, requiring halt-aware schedules.
- **2021-02-24:** 106 symbols stop at 11:41–11:43; six extend to 16:59 with 223/224 bars. The extended market session is documented in the [SEBI order](https://www.sebi.gov.in/sebi_data/attachdocs/jun-2023/1687270559560.pdf). The source is materially inconsistent across symbols on this date.
- 2020-04-27 has 15:30 bars for 52 symbols; 51 have 376 total bars. Inclusion needs a verified bar timestamp/session convention.
- Shared holes include 2023-07-12 14:57, 2023-07-24 12:49–12:51, and 2023-08-07 15:23 (all symbols short on those dates; exact slots sampled in SBIN). Other common shortfalls are recorded in irregular_dates.csv. Their root causes remain unverified.

A disclosed **15% absolute overnight OR consecutive-observed-close change screen** flagged 204 symbol-dates; 14 have overnight changes of at least 15%. This is an audit threshold, not a trading/model parameter or proof of erroneous prices. price_discontinuities.csv preserves dates, prior dates and prices. It includes genuine market-move candidates, action effects, and IRFC's spurious -96.69% close change across its invalid history. SIEMENS 2025-04-07 opens -34.43%; VEDL 2026-04-30 closes -32.68%; TMPV 2025-10-14 opens +22.86%. No automatic outlier deletion is justified.

## 4. Sector mapping

Exactly 40 headerless single-column CSV files; read with header=None, otherwise the first stock is lost. Symbols are uppercase exchange-style strings, including punctuation such as ampersands and hyphens. Infer the code from the final underscore suffix, and the sector label from everything preceding it; construction_supplies_CS is a useful example. This recovers curated labels, not an official taxonomy.

2,636 CSV records include one blank row; 2,635 nonblank entries represent 2,565 distinct symbols. Duplicate records: BOROLTD in construction_supplies_CS.csv; DHAMPURSUG in sugar_SU.csv. chemicals_CM.csv has the blank record. No other malformed one-column symbol records were detected. **67 symbols occur in multiple distinct sector files**, listed in sector_conflicts.csv (which also includes the same-file-only BOROLTD duplicate).

Current OHLCV coverage: **117 mapped (97.5%), 116 uniquely mapped**, ADANIGREEN in miscellaneous_MS.csv and power_PW.csv. Unmapped: **ADANIENSOL, ADANIPOWER, LTM**. No mappings were inferred. 29 sectors are represented in this universe; memberships total 118 because of the conflict. Some represented sectors contain only one stock, so peer-relative sector research needs a defined comparison universe and self-inclusion policy.

All filenames and full/universe counts are in sector_inventory.csv and Appendix B. The map is not usable unchanged as a unique, historical sector classification: fix the local read layer's formatting defects, resolve curated conflicts, and establish taxonomy/effective-date policy before Sector Relative Momentum. This is not itself a prerequisite for sector-agnostic CSRS.

## 5. Corporate actions

Seven files, CM_corpActions_2020.csv through CM_corpActions_2026.csv, contain **9,752 rows**. Schema: DATE, SYMBOL, SERIES, FACE VALUE, adj_factor, dividend, valid, demerger, merger, buyback. DATE is an integer YYYYMMDD; all parse successfully. No named ex-date, record-date, announcement timestamp, payment date, ISIN, old/new symbol, action description, source event ID, currency/unit contract or revision history exists. Do not assume DATE means ex-date globally because some verified examples match it.

Labels: dividend 8,772; adj_factor_nonan 537; rights_issue 228; buyback 142; demerger 73. SERIES includes EQ 9,563, IV 120, RR 68 and DR 1: the files are not equity-only. No merger=1 events and no symbol-change events are represented. Absence is not proof those actions never happened.

No exact duplicate rows or malformed-width records; **60 rows share 30 symbol/series/date keys**, typically distinct simultaneous actions. Do not keep-last on these keys. Rights rows have missing factor AND dividend (228 each); 142 buyback rows have factor zero; one face value is missing. The action flags are null on 9,537 rows. No negative numeric values were found. BRITANNIA 2021-05-25 is adj_factor_nonan with factor=1 and dividend=0, alongside a separate dividend row: the label does not identify an equity split/bonus reliably.

Annual coverage is enumerated in Appendix C. There are no absent annual files within 2020–2026, but event completeness cannot be certified from file names or counts. The 2026 file ends **2026-07-17**, whereas OHLCV ends 2026-07-31; later events are unverified, and neither source extends to the audit date. Historical aliases and acquisition/disposal events can be missing despite annual files existing.

Examples and handling:

| Event | Evidence and implication |
| --- | --- |
| Equity split | TATASTEEL 2022-07-28 factor .1; issuer confirms [10-to-1 face-value subdivision](https://www.tatasteel.com/newsroom/press-releases/india/2022/tata-steel-stock-split-of-equity-shares/). Neutralize unit changes if they remain in the prices. |
| Equity bonus | HDFCBANK 2025-08-26 factor .5; NSE confirms [1:1 bonus](https://www.nseindia.com/companies-listing/corporate-filings-actions?symbol=HDFCBANK&tabIndex=equity). Same unit-continuity requirement. |
| Rights | RELIANCE 2020-05-13; BHARTIARTL 2021-09-27; factors missing. Need entitlement ratio, subscription price, payment terms and ex-date. |
| Dividend | RITES 2020-01-09 dividend=6; TCS 2020-01-23 dividend=5. Ordinary price return can exclude distributions by definition; total shareholder return must include them consistently. Special distributions require explicit treatment. |
| Demerger | RELIANCE 2023-07-20, ITC 2025-01-06, SIEMENS 2025-04-07, TMPV 2025-10-14, HINDUNILVR 2025-12-05, VEDL 2026-04-30, MOTHERSON 2022-01-14. Flags and factor=1 do not describe distributed value, entitlements or successor identities. |
| Merger / symbol change | No positive merger flags or identity-transition fields: no usable event examples can be extracted from these files. |
| Buyback | COFORGE 2020-03-11 and TCS 2023-11-24. factor=0 is an event sentinel, not a price multiplier. A buyback does not automatically require proportional adjustment for a continuing non-participating holder. |
| Other distribution | TVSMOTOR 2025-08-25 factor=.2. Issuer filing specifies [four bonus preference shares per equity share](https://nsearchives.nseindia.com/corporate/TVSMOTOR_12082025191823_TVSMSEintimationEffectiveDate12082025SD.pdf). It is not a five-for-one equity split/bonus; a .2 equity-price multiplier is unjustified. |

**Existing adjustment evidence:** all 42 universe events with a positive non-unit factor and observed adjacent data have event-open/prior-close ratios near one (0.9948–1.0629), not the listed factors. TATASTEEL 90.34→92.35; HDFCBANK 984.60→979.50; EICHERMOT 2177.50→2199.45. Strong evidence of previous price adjustment for conventional splits/bonuses, not proof every file/action is correct. TVSMOTOR demonstrates that the factor list itself is also fallible. demerger_evidence.csv documents mixed behaviour; volume adjustment, cash-dividend adjustment and vendor revision/as-of basis remain unknown. Local platform code has no corporate-action adjustment routine; vendor-side adjustment can still exist.

Suggested methodology, not implemented: establish an event ledger with verified security identity, ex-date, original terms, source and known-at/version information. Reconcile stored prices with independent unadjusted exchange prices before applying anything. For verified unadjusted equity splits/bonuses, multiply pre-ex-date OHLC by the verified price factor and inversely scale historical share volume only where that volume convention is intended and verified. Use theoretical rights value with actual subscription terms, and event-specific distribution/merger treatment. Keep cash distributions separately; do not double-count them in adjusted returns. Do not force demergers into unexplained close-to-open smoothing. NSE's [methodology](https://archives.nseindia.com/content/indices/Method_NIFTY_Equity_Indices.pdf) distinguishes split/bonus, rights, distributions and demergers; its index policies are context, not an automatically adopted CSRS rule.

For strict as-of reconstruction, apply only effective actions through each observation's as-of date and retain source availability/revision timestamps. A later pure multiplicative split factor can cancel in within-symbol returns, but that does not validate adjusted absolute prices, volume, cash-dividend arithmetic, historical eligibility or execution. **The supplied files alone are insufficient to build safely point-in-time adjusted prices or reliably reconstruct raw execution prices.**

## 6. Existing infrastructure observations

Market-data platform: Kite historical API ingestion labels vendor rows with the requested current symbol/token; config starts 2020-01-01. The writer normalizes numeric types and Asia/Kolkata timestamps, requires exact minutes and nonnegative values, deduplicates (symbol,timestamp) keeping last, sorts, and atomically writes ZSTD yearly Parquet. Existing+incoming merge lets incoming rows win; migration merge prefers canonical over legacy rows. It logs invalid OHLC but retains it. Gap checks only measure gaps within returned dates. There is no exchange-calendar filtering, authoritative whole-day completeness check, or corporate-action adjustment routine in inspected source/notebooks. Request ranges use 09:15 start/15:29 final end, which is not equivalent to session-aware filtering. Empty responses can be checkpointed completed; all 5,265 equity chunk records say completed, not necessarily complete market coverage.

Paper engine: ParquetHistoricalCandleRepository.load_candles(Instrument,start_date,end_date) is an existing read-only contract using the same eight columns. HistoricalReplayFeed sorts CandleEvents by timestamp and instrument key. MarketDataFeed and HistoricalCandleRepository protocols, Instrument/Candle/Signal/OrderRequest models, and TradingEngine.replay are useful future boundaries. Do not copy their implementations.

Limits relevant to later integration: yearly files and all replay events are loaded into memory; missing requested partitions raise. Default quality policies error on duplicates, invalid OHLC and intra-day gaps, including legitimate scheduled breaks. No full exchange calendar is present. replay invokes session hooks at overall range endpoints, not every trading day; cross-sectional synchronization needs explicit handling. Completed bars are labelled by their start timestamps: an adapter must represent their availability and synchronize the cross-section before making decisions.

Execution processes existing eligible orders before exposing the candle to strategy; eligibility is strictly later than order creation/eligible_after. Market fills use next candle open, limits/stops use candle ranges, OCO ambiguity is configurable (conservative by default). Full fills have no participation/queue/liquidity constraints; STOP_LIMIT is not implemented. YAML sets market slippage 2 bps, stop slippage 3 bps, transaction costs 0 bps; class defaults are zero slippage/no costs. These are not a realistic-cost calibration.

Portfolio uses signed quantities, average entry, realized/unrealized P&L, fees, and cash plus marked market value; it can account for shorts but does not establish borrow availability, settlement/margin realism or corporate-action accounting. Risk checks positions, exposure, pending orders and cash. Its named daily-loss check uses P&L since portfolio starting capital, not an independently reset day-start baseline. Signals are collected as events; automatic signal-to-order orchestration is not complete (run is unimplemented). SQLite persistence and CSV exports cover summary/orders/fills/trades/positions/risk/events, not a complete factor-validation report. Existing capital/position-count configuration must not become research assumptions.

## 7. Recommended daily research dataset

Recommendation only: use a versioned exchange/security session schedule. For each valid session aggregate first open, maximum high, minimum low, last close and summed minute volume across eligible segments. The standard equity window is [09:15–15:30](https://www.nseindia.com/static/market-data/market-timings), normally minute-start labels 09:15–15:29. Exchange official close is not necessarily the last minute candle close; label the latter precisely and reconcile against bhavcopy.

Preserve observed summaries and quality flags; do not forward-fill missing sessions, fabricate volume or repair OHLC silently. Measure completeness against actual eligible minutes (including scheduled breaks, halts, listing/special-preopen times and special sessions). Separate presence, boundary completeness, internal missing slots and provenance. Flag uncertain dates/identities/actions; agree eligibility policy before factor computation. Carry short/special sessions in the dataset with their true duration; whether they enter research windows requires an explicit policy.

Keep vendor-as-stored fields distinct from verified raw prices and derived adjusted prices. The current source must not be called raw without verification. Raw execution OHLC may initially be unavailable. Keep split/share-volume factors separate from distribution/return adjustments and mark their as-of anchor. Never multiply uncertain factors into the source.

Proposed fields: stable security_id, observed symbol, exchange, series, token, session_date; session_open/close and bar_available_at with timezone; session_type/calendar_version; observed/expected bars, first/last bar timestamps, missing/internal-gap counts, zero-volume/invalid-row counts and quality reasons; vendor OHLCV; verified raw OHLCV where available; adjusted OHLC, separate volume factor/adjusted volume if justified; price basis, adjustment_as_of, action status/event IDs; membership/eligibility flags; source file/version/hash and processing version. Sector mapping and action ledgers can be separate keyed tables rather than repeated into every row.

Minimal later repository: README.md, pyproject.toml, config/ for source references and agreed policies, src/mft_research/ for small read/validation/daily-data modules, tests/ for meaningful data-contract checks, notebooks/ for research, reports/ for audits, data/derived/ for reproducible outputs only. No service framework, execution-engine clone, database or factor implementation is needed now. Only reports/ has been created.

## 8. Critical blockers

1. Unverified existing adjustment basis; applying factors can double-adjust prices, while ignoring unresolved distributions can manufacture momentum.
2. Corporate-action semantic defects, missing rights/distribution terms, generic dates, absent announcement/revision history and incomplete late-July coverage.
3. Invalid IRFC prelisting identity, current-symbol labelling and no historical security/eligibility ledger.
4. Calendar-blind session construction, shared holes and the materially incomplete 2021-02-24 closing data.
5. Survivorship/selection bias if this current 120-symbol snapshot is claimed to represent the historical tradable universe.
6. For portfolio conclusions later: unknown genuine raw execution prices, liquidity/short availability and realistic costs/accounting. Predictive short-side research is distinct from executable overnight short portfolios.

The 21 invalid candles need explicit local treatment before affected observations are trusted. Sector conflicts block later sector research but do not independently invalidate sector-free CSRS. Unrestricted lookback/horizon/weight/split search without a preregistered validation policy would create research-selection bias; no such parameters were chosen here.

## 9. Decisions needed before implementation

Only research-policy decisions, not questions the data should answer:

- Is the initial estimand conditional on today's 120-symbol snapshot, with a disclosed survivorship limitation, or must it represent point-in-time historical tradability with membership reconstruction?
- Should CSRS and its outcome labels target price momentum, total shareholder return, or explicitly compare both as prespecified analyses?
- Once objectively classified, should special/partial sessions and unresolved corporate-action windows be excluded, retained with restrictions, or evaluated in prespecified sensitivity datasets? No tolerance has been selected.
- For reorganizations, is continuity of the retained parent business the intended object, or the shareholder's full entitlement basket? This determines targets across demergers and cannot be inferred from a single price flag.

Corporate-action truth, vendor adjustment conventions, IRFC identity and missing-date causes are verification work, not modelling choices for the user to guess. Sector assignment policy can wait until sector research. No decision about direction, holding horizon, CSRS weights, top-N, capital, regimes or train/test dates is requested in Phase 1.

## 10. Exact proposed Phase-2 work

Subject to discussion; **not started**:

1. Record the agreed universe/return/continuity policies and freeze a reproducible source manifest locally.
2. Resolve identity and provenance: IRFC prelisting records, renamed securities, listing dates and historical membership scope; document verified effective intervals.
3. Reconcile corporate-action descriptions and dates with primary sources; verify vendor adjustment and volume conventions using independent exchange data; validate all relevant nontrivial actions, same-day multi-actions and missing coverage. Produce a reviewed event ledger and unresolved-event list before adjustment code.
4. Assemble/version the exchange calendar and special/halt segments; investigate shared missing-minute dates and the February 2021 extended session; reconcile daily endpoints with independent daily data.
5. After these blockers and policies are resolved, implement only local read-only adapters, contract validation and daily vendor/raw/adjusted dataset construction, with provenance and meaningful tests. Preserve upstream data and the execution project.
6. Review the resulting dataset and acceptance report before authorizing CSRS definitions, research targets and validation experiments. Do not include sector/volume factors, strategy execution or portfolio optimization in this data-foundation phase.

## Audit scope and evidence notes

All 816 footers and all 70.3 million rows were inspected; quality checks require values beyond footer extrema. Processing was bounded to one symbol at a time. Targeted event-date and common-hole reads supplemented the scan. Session metrics use a diagnostic 375-slot normal grid, not a fabricated holiday calendar. Calendar certification, exchange-wide absent dates, full vendor adjustment reconstruction and every event's primary-source reconciliation remain unresolved as stated above. No upstream application commands, downloaders, migrations or tests were executed; upstream Python was used only as an installed interpreter with pandas/PyArrow. No source code from upstream was imported for execution.

Audit CSVs are descriptive reports, not daily OHLCV products. session_quality.csv first/last are minutes since local midnight; missing_regular is absent slots in 09:15–15:29 and outside_regular counts other minutes. A 375-row count alone is not a completeness certificate. price_discontinuities.csv uses the immediately preceding observed date, explicitly stored, and therefore can span a long gap. Footer inventory is not a cryptographically frozen snapshot: hashes and source-vintage control are proposed for Phase 2.

## Appendix A — exact symbol inventory

| symbol | first | last | years | rows | sessions | tokens |
| --- | --- | --- | --- | --- | --- | --- |
| ABB | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609858 | 1635 | 3329 |
| ACC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 5633 |
| ADANIENSOL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609190 | 1635 | 2615553 |
| ADANIENT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 6401 |
| ADANIGREEN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610309 | 1635 | 912129 |
| ADANIPORTS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 3861249 |
| ADANIPOWER | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610304 | 1635 | 4451329 |
| AMBUJACEM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 325121 |
| APOLLOHOSP | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 40193 |
| ASHOKLEY | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 54273 |
| ASIANPAINT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 60417 |
| AXISBANK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 1510401 |
| BAJAJ-AUTO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610322 | 1635 | 4267265 |
| BAJAJFINSV | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 4268801 |
| BAJAJHLDNG | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609404 | 1635 | 78081 |
| BAJFINANCE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 81153 |
| BANKBARODA | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 1195009 |
| BEL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 98049 |
| BERGEPAINT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 103425 |
| BHARTIARTL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610325 | 1635 | 2714625 |
| BPCL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 134657 |
| BRITANNIA | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610322 | 1635 | 140033 |
| CANBK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 2763265 |
| CGPOWER | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 606583 | 1635 | 194561 |
| CHOLAFIN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 175361 |
| CIPLA | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 177665 |
| COALINDIA | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 5215745 |
| COFORGE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 2955009 |
| CUMMINSIND | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 486657 |
| DABUR | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610314 | 1635 | 197633 |
| DIVISLAB | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 2800641 |
| DIXON | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610293 | 1635 | 5552641 |
| DLF | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 3771393 |
| DMART | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610314 | 1635 | 5097729 |
| DRREDDY | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 225537 |
| EICHERMOT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 232961 |
| ETERNAL | 2021-07-23 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2021,2022,2023,2024,2025,2026 | 465070 | 1246 | 1304833 |
| GAIL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610391 | 1635 | 1207553 |
| GODREJCP | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 2585345 |
| GRASIM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 315393 |
| HAL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609148 | 1635 | 589569 |
| HAVELLS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610316 | 1635 | 2513665 |
| HCLTECH | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 1850625 |
| HDFCAMC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610316 | 1635 | 1086465 |
| HDFCBANK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 341249 |
| HDFCLIFE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 119553 |
| HEROMOTOCO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 345089 |
| HINDALCO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 348929 |
| HINDUNILVR | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610289 | 1635 | 356865 |
| HINDZINC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610299 | 1635 | 364545 |
| HYUNDAI | 2024-10-22 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2024,2025,2026 | 164336 | 440 | 6616065 |
| ICICIBANK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 1270529 |
| ICICIGI | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610316 | 1635 | 5573121 |
| ICICIPRULI | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610314 | 1635 | 4774913 |
| INDHOTEL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610288 | 1635 | 387073 |
| INDIGO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 2865921 |
| INDUSINDBK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 1346049 |
| INDUSTOWER | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 7458561 |
| INFY | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 408065 |
| IOC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 415745 |
| IRFC | 2020-01-03 12:56:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 509198 | 1368 | 519425 |
| ITC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610296 | 1635 | 424961 |
| JINDALSTEL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610322 | 1635 | 1723649 |
| JIOFIN | 2023-08-21 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2023,2024,2025,2026 | 272596 | 731 | 4644609 |
| JSWENERGY | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610085 | 1635 | 4574465 |
| JSWSTEEL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 3001089 |
| KOTAKBANK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 492033 |
| LICI | 2022-05-17 09:44:00+05:30 | 2026-07-31 15:29:00+05:30 | 2022,2023,2024,2025,2026 | 390033 | 1045 | 2426881 |
| LODHA | 2021-04-19 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2021,2022,2023,2024,2025,2026 | 489673 | 1312 | 824321 |
| LT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 2939649 |
| LTM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610305 | 1635 | 4561409 |
| LUPIN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610320 | 1635 | 2672641 |
| M&M | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610325 | 1635 | 519937 |
| MANKIND | 2023-05-09 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2023,2024,2025,2026 | 299599 | 803 | 3937281 |
| MARICO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610322 | 1635 | 1041153 |
| MARUTI | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 2815745 |
| MAXHEALTH | 2020-08-21 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 550251 | 1475 | 5728513 |
| MAZDOCK | 2020-10-12 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 537137 | 1440 | 130305 |
| MOTHERSON | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610292 | 1635 | 1076225 |
| MPHASIS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610244 | 1635 | 1152769 |
| MUTHOOTFIN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610322 | 1635 | 6054401 |
| NESTLEIND | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610397 | 1635 | 4598529 |
| NTPC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 2977281 |
| OFSS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609513 | 1635 | 2748929 |
| ONGC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 633601 |
| PERSISTENT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609502 | 1635 | 4701441 |
| PFC | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 3660545 |
| PIDILITIND | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 681985 |
| PNB | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 2730497 |
| POLYCAB | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 2455041 |
| POWERGRID | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610324 | 1635 | 3834113 |
| RECLTD | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 3930881 |
| RELIANCE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610274 | 1635 | 738561 |
| SBILIFE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610320 | 1635 | 5582849 |
| SBIN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 779521 |
| SHREECEM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610311 | 1635 | 794369 |
| SHRIRAMFIN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 1102337 |
| SIEMENS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610297 | 1635 | 806401 |
| SOLARINDS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 596350 | 1635 | 3412993 |
| SUNPHARMA | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610317 | 1635 | 857857 |
| TATACAP | 2025-10-13 10:00:00+05:30 | 2026-07-31 15:29:00+05:30 | 2025,2026 | 73886 | 198 | 194371841 |
| TATACOMM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 609295 | 1635 | 952577 |
| TATACONSUM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 878593 |
| TATAPOWER | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610320 | 1635 | 877057 |
| TATASTEEL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610321 | 1635 | 895745 |
| TCS | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610319 | 1635 | 2953217 |
| TECHM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610393 | 1635 | 3465729 |
| TITAN | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610320 | 1635 | 897537 |
| TMCV | 2025-11-12 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2025,2026 | 66710 | 178 | 194504193 |
| TMPV | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610286 | 1635 | 884737 |
| TORNTPHARM | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610311 | 1635 | 900609 |
| TRENT | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610302 | 1635 | 502785 |
| TVSMOTOR | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 2170625 |
| ULTRACEMCO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610394 | 1635 | 2952193 |
| UNIONBANK | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610386 | 1635 | 2752769 |
| UNITDSPR | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610320 | 1635 | 2674433 |
| VBL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610228 | 1635 | 4843777 |
| VEDL | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610294 | 1635 | 784129 |
| WIPRO | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610318 | 1635 | 969473 |
| ZYDUSLIFE | 2020-01-01 09:15:00+05:30 | 2026-07-31 15:29:00+05:30 | 2020,2021,2022,2023,2024,2025,2026 | 610323 | 1635 | 2029825 |

## Appendix B — exact sector files and counts

| file | sector | code | records | unique_symbols | ohlcv_symbols | duplicates | malformed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agriculture_AG.csv | agriculture | AG | 84 | 84 | 1 | 0 | [] |
| alcohol_AL.csv | alcohol | AL | 15 | 15 | 1 | 0 | [] |
| automobile_AT.csv | automobile | AT | 145 | 145 | 12 | 0 | [] |
| aviation_AV.csv | aviation | AV | 11 | 11 | 3 | 0 | [] |
| banks_BN.csv | banks | BN | 41 | 41 | 10 | 0 | [] |
| capGoods_CG.csv | capGoods | CG | 140 | 140 | 3 | 0 | [] |
| chemicals_CM.csv | chemicals | CM | 183 | 182 | 4 | 0 | [[]] |
| construction_supplies_CS.csv | construction_supplies | CS | 100 | 99 | 4 | 1 | [] |
| containers_packaging_CP.csv | containers_packaging | CP | 12 | 12 | 0 | 0 | [] |
| diamond_jewellery_DJ.csv | diamond_jewellery | DJ | 25 | 25 | 1 | 0 | [] |
| diversified_DV.csv | diversified | DV | 29 | 29 | 2 | 0 | [] |
| durables_DR.csv | durables | DR | 41 | 41 | 1 | 0 | [] |
| electricals_EL.csv | electricals | EL | 61 | 61 | 2 | 0 | [] |
| etf_ET.csv | etf | ET | 3 | 3 | 0 | 0 | [] |
| fertilisers_FR.csv | fertilisers | FR | 22 | 22 | 0 | 0 | [] |
| finance_FN.csv | finance | FN | 198 | 198 | 12 | 0 | [] |
| fmcg_FG.csv | fmcg | FG | 65 | 65 | 7 | 0 | [] |
| footwear_FW.csv | footwear | FW | 10 | 10 | 0 | 0 | [] |
| gases_fuels_GF.csv | gases_fuels | GF | 8 | 8 | 1 | 0 | [] |
| healthcare_HC.csv | healthcare | HC | 167 | 167 | 10 | 0 | [] |
| hospitality_HP.csv | hospitality | HP | 47 | 47 | 1 | 0 | [] |
| infrastructure_IF.csv | infrastructure | IF | 85 | 85 | 2 | 0 | [] |
| insurance_IN.csv | insurance | IN | 9 | 9 | 5 | 0 | [] |
| logistics_LG.csv | logistics | LG | 70 | 70 | 0 | 0 | [] |
| manufacturing_MF.csv | manufacturing | MF | 24 | 24 | 0 | 0 | [] |
| media_entertainment_ME.csv | media_entertainment | ME | 50 | 50 | 0 | 0 | [] |
| metals_Mining_MM.csv | metals_Mining | MM | 131 | 131 | 7 | 0 | [] |
| miscellaneous_MS.csv | miscellaneous | MS | 160 | 160 | 2 | 0 | [] |
| oil_gas_OG.csv | oil_gas | OG | 25 | 25 | 4 | 0 | [] |
| paper_PA.csv | paper | PA | 23 | 23 | 0 | 0 | [] |
| plastic_products_PP.csv | plastic_products | PP | 42 | 42 | 0 | 0 | [] |
| power_PW.csv | power | PW | 51 | 51 | 5 | 0 | [] |
| real_estate_RE.csv | real_estate | RE | 74 | 74 | 2 | 0 | [] |
| retailing_RT.csv | retailing | RT | 30 | 30 | 2 | 0 | [] |
| ship_building_SB.csv | ship_building | SB | 4 | 4 | 1 | 0 | [] |
| software_SW.csv | software | SW | 197 | 197 | 9 | 0 | [] |
| sugar_SU.csv | sugar | SU | 32 | 31 | 0 | 1 | [] |
| telecom_TC.csv | telecom | TC | 32 | 32 | 3 | 0 | [] |
| textiles_TX.csv | textiles | TX | 152 | 152 | 0 | 0 | [] |
| trading_TR.csv | trading | TR | 38 | 38 | 1 | 0 | [] |

## Appendix C — annual corporate-action inventory

| file | rows | first_date | last_date | dividend | factor_label | rights | demerger | buyback | malformed_width | duplicate_rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CM_corpActions_2020.csv | 1074 | 20200109 | 20201231 | 1013 | 23 | 20 | 11 | 7 | 0 | 0 |
| CM_corpActions_2021.csv | 1328 | 20210105 | 20211231 | 1229 | 58 | 26 | 3 | 12 | 0 | 0 |
| CM_corpActions_2022.csv | 1521 | 20220106 | 20221230 | 1361 | 104 | 22 | 13 | 21 | 0 | 0 |
| CM_corpActions_2023.csv | 1622 | 20230103 | 20231229 | 1460 | 87 | 32 | 13 | 30 | 0 | 0 |
| CM_corpActions_2024.csv | 1751 | 20240102 | 20241230 | 1524 | 122 | 56 | 11 | 38 | 0 | 0 |
| CM_corpActions_2025.csv | 1809 | 20250101 | 20251226 | 1620 | 104 | 54 | 18 | 13 | 0 | 0 |
| CM_corpActions_2026.csv | 647 | 20260102 | 20260717 | 565 | 39 | 18 | 4 | 21 | 0 | 0 |
