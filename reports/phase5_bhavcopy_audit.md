# Phase 5 — Read-only historical Bhavcopy audit

**Status: AUDIT COMPLETE; IMPLEMENTATION PAUSED FOR MATERIAL POLICY DECISIONS**

No Phase-5 research dataset, universe membership, CSRS factor, or analytical result was built. No upstream file was modified. This audit used the accepted Phase-2 corporate-action ledger and read the Bhavcopy and current-universe projects only.

## 1. Archive inventory and coverage

The archive root is `/home/suruchi-pandey/Projects/Bhavcopy-download-and-mail-code`, partitioned into year directories `2020` through `2026`.

- Old files: `YEAR/sec_bhavdata_full_DDMMYYYY.csv`, 1,176 files. Every file is gzip-compressed despite the `.csv` suffix. Coverage by internal trading date is 2020-01-01 through 2024-07-05.
- New files: `YEAR/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv`, 541 plain CSV files. Coverage is 2024-07-08 through 2026-09-11.
- Total: 1,717 source files and 1,660 distinct internal trading dates after deterministic duplicate-file removal.
- The transition is clean: no date contains both formats. The last old-format session is 2024-07-05 and the first new-format session is 2024-07-08.

The exact annual counts are in `reports/csrs/point_in_time/bhavcopy_audit.csv`. After duplicate-file removal, the archive contains 3,062,267 EQ symbol/date rows and 3,381 distinct observed EQ tickers. All current 120 tickers occur in the archive; 3,261 observed historical tickers are outside the current 120.

Compared with the accepted Phase-2 observed session calendar through 2026-07-31, Bhavcopy contains every ordinary accepted date and no extra date. It lacks five special sessions that exist in minute data: 2020-02-01, 2023-11-12, 2024-03-02, 2025-02-01, and 2026-02-01. These must remain absent rather than be fabricated. The comparison does not certify dates after the minute archive ends.

## 2. Schemas and field mapping

Old schema, present in all 1,176 old files:

`SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER`

Canonical mappings are `SYMBOL` to symbol, `SERIES` to series, `DATE1` to date, the named OHLC fields to OHLC, `TTL_TRD_QNTY` to volume, and `TURNOVER_LACS * 100000` to turnover in rupees. Old files have no ISIN, instrument identifier, or security name.

New schema, present in all 541 new files:

`TradDt, BizDt, Sgmt, Src, FinInstrmTp, FinInstrmId, ISIN, TckrSymb, SctySrs, XpryDt, FininstrmActlXpryDt, StrkPric, OptnTp, FinInstrmNm, OpnPric, HghPric, LwPric, ClsPric, LastPric, PrvsClsgPric, UndrlygPric, SttlmPric, OpnIntrst, ChngInOpnIntrst, TtlTradgVol, TtlTrfVal, TtlNbOfTxsExctd, SsnId, NewBrdLotQty, Rmks, Rsvd1, Rsvd2, Rsvd3, Rsvd4`

Canonical mappings are `TckrSymb` to symbol, `SctySrs` to series, `TradDt` to date, the named OHLC fields to OHLC, `TtlTradgVol` to volume, and `TtlTrfVal` directly to turnover in rupees. All new rows report `Sgmt=CM`, `Src=NSE`, and `FinInstrmTp=STK`.

Both formats contain multiple cash-market series rather than an EQ-only extract. `SERIES`/`SctySrs` explicitly identifies EQ. The files have the structure and breadth of full NSE cash-market daily reports; local inspection can establish that all reported series are retained, but cannot independently prove exchange-side completeness beyond comparison with the accepted session calendar.

## 3. Turnover units

The formats use different units. In the old format, `TURNOVER_LACS` is lakh rupees. For example, 20MICRONS on 2020-01-01 has average price ₹35.96 and volume 49,077, implying ₹1,764,809; the stored turnover is 17.65 lakhs. The canonical conversion is exactly `TURNOVER_LACS * 100000`.

In the new format, `TtlTrfVal` is already rupees. HDFCBANK on 2025-08-25 reports volume 8,759,022 and `TtlTrfVal=17231388424.40`, or ₹17.231 billion. Applying the old multiplier would be a five-order-of-magnitude error.

## 4. Duplicate dates, malformed files, and row quality

Filename dates are not reliable for old files. Sixty-one old files contain a different internal `DATE1`, generally because a downloader saved the preceding session again on an exchange holiday or other non-trading date. Examples include filename 2020-05-01 containing 2020-04-30 and filename 2020-11-16 containing the 2020-11-14 Muhurat session.

There are 56 duplicated internal dates represented by 113 files: 55 dates have two copies and one has three. Every duplicate group has one identical decompressed payload, so the files can be resolved without choosing between conflicting rows. Before source-file deduplication these copies create 96,988 duplicate EQ symbol/date rows; afterward there are none. A future loader must use the internal date and select a deterministic representative, preferably the file whose filename agrees with the internal date.

One file is malformed by packaging: `2022/sec_bhavdata_full_08082022.csv` is a gzip stream containing an XLSX workbook rather than CSV. It is recoverable without guessing and contains the standard 15-column old schema, 2,255 rows, 1,814 EQ rows, and internal date 2022-08-08.

Across all parsed files, the audit found:

- zero duplicate EQ symbol keys within a canonical session;
- zero inconsistent EQ OHLC rows;
- zero nonpositive EQ OHLC prices;
- zero negative EQ volume or turnover rows;
- zero zero-volume EQ rows.

These checks establish structural validity of the reported fields. They do not establish corporate-action continuity, common-stock identity, or completeness of suspended/nontrading securities.

## 5. Listing, disappearance, and identity

Row presence naturally shows first observation, last observation, entry, disappearance, and intermittent trading without conditioning on survival to 2026. This is sufficient to construct point-in-time observed membership. It is a listing-age proxy, not an authoritative listing/delisting registry.

Of 3,381 observed EQ tickers, 188 have at most 20 sessions, 308 at most 60, 459 at most 120, and 895 at most 350. This confirms that minimum-history rules materially change the universe. Requested newer names appear only when observed: MANKIND from 2023-05-09, JIOFIN from 2023-09-04, HYUNDAI from 2024-10-22, TATACAP from 2025-10-13, and TMCV from 2025-11-26.

The old format cannot objectively link renamed securities because it lacks ISIN. In the new period, 91 ISINs occur under more than one EQ ticker, providing objective alias evidence after 2024-07-08; examples include CENTURYTEX/ABREL, ZOMATO/ETERNAL, LTIM/LTM, and TATAMOTORS/TMPV. Conversely, 134 tickers have more than one ISIN in the new period, frequently around splits or face-value changes, so an ISIN change alone is not proof of a new company. Histories must remain separate by observed ticker unless a precise identity link is independently verified. Fuzzy stitching is unsafe.

`SERIES=EQ` is not a pure common-stock classifier. It also contains exchange-traded products such as GOLD360 and SILVER360, and the new format labels all of them `FinInstrmTp=STK`. The old format lacks a dependable security-name/type field that could apply a consistent exclusion from 2020 onward.

## 6. Price basis and corporate actions

Bhavcopy prices are demonstrably unadjusted across at least conventional unit-changing actions:

- TATASTEEL: 2022-07-27 close ₹959.40; 2022-07-28 open ₹98.10 after the recorded split.
- HDFCBANK: 2025-08-25 close ₹1,964.10; 2025-08-26 open ₹979.50 after the recorded 1:1 bonus.

The accepted corporate-action ledger contains 9,563 EQ records for 1,630 symbols from 2020-01-09 through 2026-07-17. Of these, 9,557 records and 1,628 symbols intersect the historical archive. For intersecting symbols it classifies 8,728 records as no price adjustment needed for price momentum, 493 as unknown/ambiguous, 295 as material unresolved, and 41 as likely already adjusted conventional actions.

The last label was derived from the adjusted-looking minute-data vendor and is contradicted by raw Bhavcopy around the examples above. It cannot be reused as a Bhavcopy price-safety conclusion. The accepted ledger's source `DATE` is also not globally verified as an ex-date and has no announcement-known-at timestamp.

There are 1,753 historical EQ tickers with no record in the action ledger. The ledger is an event list, not a symbol/date completeness registry; absence of a row cannot certify that a symbol had no action. Consequently, the available artifacts support a broad risk-flagged sensitivity tier, but they do not objectively define the requested `PRIMARY VERIFIED` tier for the entire historical universe.

Corporate-action coverage ends 2026-07-17 while Bhavcopy extends to 2026-09-11. Intervals extending after 2026-07-17 cannot enter a primary certified analysis under the established cutoff.

## 7. ASM/GSM and source-project observations

The inspected universe project contains only current `asm-latest.csv` and `gsm-latest.csv` outputs and downloader code for current NSE endpoints. No historical effective-dated ASM/GSM archive was found. Current ASM/GSM state must not be applied backward, so the Phase-5 historical variants cannot include that exclusion from these sources.

The existing universe project contains current ranking and research logic, but it does not provide a point-in-time membership archive. Its current filters cannot be imported as historical facts.

## 8. Sufficiency and blockers

The Bhavcopy fields are sufficient to build lookahead-safe observed EQ membership, daily OHLCV, normalized turnover, trailing history, trailing volume/turnover, and the four requested point-in-time liquidity flags. Filename duplication and the XLSX exception have deterministic technical resolutions.

Implementation is paused because three choices materially affect factor validity and are not objectively settled by the sources:

1. **Corporate-action primary tier.** Raw Bhavcopy contradicts the minute-vendor `LIKELY_ALREADY_ADJUSTED` label, and the ledger does not certify symbols with no event. A defensible conservative rule would invalidate intervals crossing every recorded unit-changing, unknown, material, rights, demerger, or preference-distribution event in `PRIMARY VERIFIED`, retain dividends/buybacks under the price-momentum policy, and place all other intervals in `BROAD SENSITIVITY` with explicit coverage status. This changes source-specific interval treatment and needs approval.
2. **EQ exchange-traded products.** Literal `SERIES=EQ` includes ETFs and similar products, while a consistent point-in-time common-stock classifier is absent for the old format. The choice is to keep the literal EQ universe or obtain an effective-dated security master before implementation.
3. **Strict-universe history.** Universe D specifies “sufficient history” but freezes no session count. A 350-session gate removes 895 observed tickers from eligibility until they mature and leaves no strict observations in early 2020. Choosing 120, 250, or 350 sessions after seeing results is unacceptable; the value or prespecified sensitivity grid must be fixed first.

Until these are decided, producing `historical_nse_daily.parquet` and rerunning CSRS would silently embed material modelling choices. Phase 5 therefore stops at the required audit gate.
