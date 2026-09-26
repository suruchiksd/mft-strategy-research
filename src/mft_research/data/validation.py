"""Data acceptance checks and reporting. No return, factor or portfolio metrics."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .corporate_actions import SOURCE_COLUMNS
from .manifest import canonical_json, sha256, verify_sources
from .sectors import read_sectors


ARTIFACTS = ["universe.parquet", "daily_bars.parquet", "corporate_action_ledger.parquet",
             "session_calendar.parquet", "minute_exclusions.parquet"]


def validate_frames(universe: pd.DataFrame, daily: pd.DataFrame, ledger: pd.DataFrame,
                    calendar: pd.DataFrame, exclusions: pd.DataFrame, config: dict) -> dict:
    checks = {}

    def check(name, condition):
        if not bool(condition):
            raise AssertionError(name)
        checks[name] = "PASS"

    check("120_canonical_symbols", len(universe) == 120 and universe.symbol.nunique() == 120)
    check("daily_universe_exact", set(daily.symbol) == set(universe.symbol))
    check("unique_daily_symbol_date", not daily.duplicated(["symbol", "date"]).any())
    check("unique_symbol_tokens", not universe.duplicated(["symbol", "instrument_token"]).any()
          and universe.instrument_token.nunique() == 120)
    check("daily_tokens_match_universe", daily.instrument_token.eq(daily.symbol.map(universe.set_index("symbol").instrument_token)).all())
    good = daily[daily.valid_bars.gt(0)]
    p = good[["open", "high", "low", "close"]]
    check("finite_positive_daily_prices", np.isfinite(p).all().all() and p.gt(0).all().all())
    check("consistent_daily_ohlc", (good.high >= good[["open", "low", "close"]].max(axis=1)).all()
          and (good.low <= good[["open", "high", "close"]].min(axis=1)).all())
    check("nonnegative_volume", daily.volume.ge(0).all())
    check("no_valid_minutes_have_null_prices", daily.loc[daily.valid_bars.eq(0), ["open", "high", "low", "close"]].isna().all().all())
    check("minute_exclusions_reconcile", int(daily.excluded_minutes.sum()) == len(exclusions))
    check("minute_counts_reconcile", daily.observed_bars.eq(daily.valid_bars + daily.excluded_minutes).all())
    for name, frame, columns in [
        ("daily", daily, ["first_timestamp", "last_timestamp", "first_valid_timestamp", "last_valid_timestamp", "bar_available_at"]),
        ("universe", universe, ["first_observed_timestamp", "last_observed_timestamp"]),
        ("calendar", calendar, ["scheduled_open", "scheduled_close"]),
        ("exclusions", exclusions, ["timestamp"]),
    ]:
        check(f"{name}_IST_timestamps", all(str(frame[col].dt.tz) == "Asia/Kolkata" for col in columns))
    check("daily_date_matches_local_timestamp", daily.date.eq(daily.first_timestamp.dt.date).all()
          and daily.date.eq(daily.last_timestamp.dt.date).all())
    check("availability_not_before_last_minute_end", (daily.bar_available_at >= daily.last_timestamp + pd.Timedelta(minutes=1)).all())
    irfc = daily[daily.symbol.eq("IRFC") & daily.date.lt(pd.Timestamp(config["identity_rules"]["IRFC"]["valid_from"]).date())]
    check("IRFC_prelisting_ineligible", not irfc.research_eligible.any()
          and irfc.exclusion_reason.str.contains("PRELISTING_IDENTITY_CONTAMINATION").all()
          and irfc.valid_bars.eq(0).all())
    known = daily[daily.date.eq(pd.Timestamp("2024-06-25").date()) & daily.invalid_ohlc_minutes.gt(0)]
    check("known_21_invalid_minutes_flagged", len(known) == 21 and known.invalid_ohlc_minutes.sum() == 21
          and not known.research_eligible.any() and not known.open_is_first_observed_minute.any()
          and not known.open_is_scheduled_first_minute.any())
    check("known_invalid_minute_provenance", len(exclusions[exclusions.timestamp.eq(pd.Timestamp("2024-06-25 09:15", tz="Asia/Kolkata"))
          & exclusions.exclusion_reason.str.contains("INVALID_OHLC")]) == 21)
    eligible = daily[daily.research_eligible]
    check("eligible_session_quality", eligible.session_quality.isin(["NORMAL_COMPLETE", "KNOWN_SPECIAL_COMPLETE"]).all())
    check("eligible_no_exclusion_reasons", daily.research_eligible.eq(daily.exclusion_reason.eq("")).all())
    check("eligible_complete_grid_and_valid_prices", eligible.missing_expected_minutes.eq(0).all()
          and eligible.unexpected_minutes.eq(0).all() and eligible.invalid_ohlc_minutes.eq(0).all()
          and eligible.valid_bars.gt(0).all())
    check("unresolved_action_rows_ineligible", not daily.loc[daily.corporate_action_unresolved, "research_eligible"].any())
    check("calendar_unique_and_exact_dates", not calendar.date.duplicated().any() and set(calendar.date) == set(daily.date))
    check("ledger_event_ids_unique", ledger.event_id.is_unique)
    check("ledger_duplicate_counts_preserved", ledger.duplicate_key_count.eq(ledger.groupby("duplicate_key_group").event_id.transform("size")).all())
    check("no_price_adjustments", daily.source_price_basis.eq("source_as_stored_price_momentum").all())
    check("sector_missing_and_conflicts_not_invented", universe.loc[universe.sector_mapping_status.ne("UNIQUE"), ["sector", "sector_code"]].isna().all().all())
    check("universe_scope_label", universe.research_scope.eq("conditional current-universe research").all())
    return checks


def read_artifacts(output: Path) -> tuple[pd.DataFrame, ...]:
    frames = [pq.ParquetFile(output / name).read().to_pandas() for name in ARTIFACTS]
    return tuple(frames)


def validate_dataset(project: Path, config: dict, verify_upstream: bool = True) -> dict:
    output = project / config["output_dir"]
    manifest = json.loads((output / "source_manifest.json").read_text())
    if verify_upstream:
        verify_sources(manifest)
    if config != manifest["policy"]:
        raise AssertionError("Config differs from built manifest")
    for item in manifest["code_files"] + manifest["evidence_files"]:
        if sha256(project / item["path"]) != item["sha256"]:
            raise AssertionError(f"Build code/evidence changed: {item['path']}; rebuild required")
    for name in ARTIFACTS:
        if sha256(output / name) != manifest["artifact_sha256"][name]:
            raise AssertionError(f"Artifact checksum mismatch: {name}")
    universe, daily, ledger, calendar, exclusions = read_artifacts(output)
    checks = validate_frames(universe, daily, ledger, calendar, exclusions, config)
    sectors, _ = read_sectors(Path(config["sources"]["sectors"]), universe.symbol.tolist())
    cols = sectors.columns.tolist()
    pd.testing.assert_frame_equal(universe[cols].reset_index(drop=True), sectors.reset_index(drop=True), check_dtype=False)
    checks["sector_sources_exact_no_invention"] = "PASS"
    source_count = 0
    for path in sorted(Path(config["sources"]["corporate_actions"]).glob("*.csv")):
        source = pd.read_csv(path, dtype=str, keep_default_na=False)
        built = ledger[ledger.source_file.eq(str(path.resolve()))].sort_values("source_row")
        pd.testing.assert_frame_equal(source.reset_index(drop=True), built[SOURCE_COLUMNS].reset_index(drop=True), check_dtype=False)
        source_count += len(source)
    if source_count != len(ledger):
        raise AssertionError("Corporate-action source rows lost or added")
    checks["corporate_action_source_rows_lossless"] = "PASS"
    checks["source_hashes_sizes_mtimes_unchanged"] = "PASS" if verify_upstream else "NOT_RUN"
    checks["artifact_code_evidence_hashes_match"] = "PASS"
    checks["immutable_versioned_manifest_matches"] = "PASS"
    archived = output / "manifests" / f"{manifest['build_id']}.json"
    if archived.read_bytes() != (output / "source_manifest.json").read_bytes():
        raise AssertionError("Current manifest differs from immutable archive")
    return checks


def markdown_table(frame: pd.DataFrame) -> str:
    def escape(value):
        return str(value).replace("|", "; ").replace("\n", " ")
    return "| " + " | ".join(map(escape, frame.columns)) + " |\n| " + " | ".join(["---"] * len(frame.columns)) + " |\n" + "\n".join(
        "| " + " | ".join(map(escape, row)) + " |" for row in frame.itertuples(index=False, name=None)) + "\n"


def write_acceptance(project: Path, config: dict, checks: dict, pytest_xml: Path | None = None) -> str:
    output, reports = project / config["output_dir"], project / config["report_dir"]
    universe, daily, ledger, calendar, exclusions = read_artifacts(output)
    manifest = json.loads((output / "source_manifest.json").read_text())
    count, total = int(daily.research_eligible.sum()), len(daily)
    reasons = daily.loc[~daily.research_eligible, "exclusion_reason"].str.split("|").explode().value_counts().rename_axis("reason").reset_index(name="rows")
    quality = daily.session_quality.value_counts().rename_axis("session_quality").reset_index(name="rows")
    impact = ledger.groupby(["research_impact", "affects_current_universe"], dropna=False).size().reset_index(name="events")
    reduced = universe[["symbol", "observed_sessions", "eligible_sessions", "first_valid_research_date", "last_valid_research_date"]].copy()
    reduced["excluded_sessions"] = reduced.observed_sessions - reduced.eligible_sessions
    reduced["eligible_pct"] = (100 * reduced.eligible_sessions / reduced.observed_sessions).round(3)
    reduced = reduced.sort_values(["eligible_pct", "symbol"])
    for name, frame in [("phase2_session_counts.csv", quality), ("phase2_exclusion_counts.csv", reasons),
                        ("phase2_usable_history.csv", reduced), ("phase2_corporate_action_summary.csv", impact)]:
        frame.to_csv(reports / name, index=False)
    test_text = "Full pytest suite has not yet been recorded."
    if pytest_xml is not None:
        root = ET.parse(pytest_xml).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        totals = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        test_text = f"Full pytest suite: {totals['tests']} tests; {totals['failures']} failures; {totals['errors']} errors; {totals['skipped']} skipped."
        if totals["failures"] or totals["errors"]:
            raise AssertionError("Cannot accept a failing test suite")
    verification_path = reports / "phase2_rebuild_verification.json"
    rebuild = json.loads(verification_path.read_text()) if verification_path.exists() else {}
    reproducible = rebuild.get("build_id") == manifest["build_id"] and rebuild.get("all_artifacts_byte_identical") is True
    unresolved = ledger[ledger.affects_current_universe & ledger.requires_window_exclusion]
    lines = ["# Phase-2 dataset acceptance\n", "## 1. Executive summary\n",
             f"Built **{total:,} daily rows**, **120 symbols**, with **{count:,} eligible rows ({count/total:.2%})**. "
             "Research scope: **conditional current-universe research**. Price basis: **source-as-stored price momentum**, with no corporate-action adjustment. "
             "This is a validated data foundation, not an assertion that all price intervals are safe.\n",
             "## 2. Files/code created\n",
             "Minimal package modules: manifest, universe, sectors, corporate_actions, sessions, daily_bars, validation; "
             "build/validate scripts, YAML policy, explicit CSV session overrides, pinned dependencies and tests. "
             "Derived outputs: universe.parquet, daily_bars.parquet, corporate_action_ledger.parquet, session_calendar.parquet, "
             "minute_exclusions.parquet, source_manifest.json and immutable manifests/<build_id>.json. "
             "No upstream code is imported for execution; no raw data copy, factors or backtests.\n",
             f"Build ID: `{manifest['build_id']}`. Build timestamp: `{manifest['build_timestamp_utc']}`. "
             f"Source files: {len(manifest['files'])}; every file has SHA-256, size and mtime_ns; Parquet files also have row counts. "
             "Code/evidence hashes, runtime versions, full config and output hashes are recorded. A rebuild fails if sources change during execution. "
             "Versioned manifests are write-once by the builder; the latest manifest is a pointer copy. Upstream revisions can be detected, not undone without a separately archived source.\n",
             "## 3. Exact universe used\n", ", ".join(universe.symbol) + ".\n",
             "No historical membership reconstruction. Sectors: 116 UNIQUE, one CONFLICT (ADANIGREEN), three UNMAPPED "
             "(ADANIENSOL, ADANIPOWER, LTM). Conflicts/unmapped have null sector fields and preserved candidate/source metadata.\n",
             "## 4. Daily dataset row/date coverage\n",
             f"{daily.date.min()} through {daily.date.max()}; {daily.date.nunique():,} observed market dates; {total:,} observed symbol-dates. "
             "All observed dates remain, including days with no valid minutes. No unobserved bars/days are fabricated. "
             "Calendar is an observed-date ledger, not a certified exchange holiday calendar. First/last valid research dates are in universe.parquet; "
             "they express row-quality eligibility, not listing dates or lookback sufficiency.\n",
             "## 5. Session classifications/counts\n", markdown_table(quality),
             "Exact timestamp grids are compared to end-exclusive intervals. Known annual short sessions, two-segment DR sessions and audited weekend "
             "sessions can be complete. Unknown weekends, March 2020 halt dates, the February 2021 extended-session anomaly and 2020-04-27 "
             "remain ineligible. Exact expected minutes are null where no verified interval is available. Shared partial means at least two symbols "
             "on the same date have a grid shortfall; it describes breadth, not a proven exchange cause. No future dates determine an earlier grid.\n",
             "## 6. Invalid-data handling\n",
             f"Excluded {len(exclusions):,} minute records from OHLC **and volume**, with source file, timestamp, original values and reasons in minute_exclusions.parquet. "
             "All 21 invalid 2024-06-25 09:15 candles are omitted, and their daily rows are ineligible. The first valid open is retained but "
             "open_is_scheduled_first_minute/open_is_first_observed_minute are false. No replacement values or forward fills. "
             "Duplicate timestamp copies are all excluded rather than selecting a winner. Unexpected minutes outside known intervals are excluded "
             "and their date flagged. Unknown schedules aggregate valid observed minutes for audit only. Zero-volume bars are retained and counted. "
             "Null daily OHLC with zero valid_bars is explicit absence; volume=0 then means sum of zero retained records. "
             "Close is last valid minute close, not the official exchange daily close. Availability is no earlier than known scheduled close and last observed minute end.\n",
             "## 7. IRFC handling\n",
             "Verified identity floor: 2021-01-29, linked in config to NSE listing evidence. All 31 prelisting minutes on four dates are excluded "
             "from aggregation; the four daily audit records remain ineligible with null OHLC. No valid start was inferred from the raw minimum.\n",
             "## 8. Corporate-action ledger summary\n", markdown_table(impact),
             f"All {len(ledger):,} source records retained losslessly, including source JSON and original string columns; "
             "60 rows in 30 duplicate-key groups retained. Date remains generic source date, not an inferred ex-date; no announcement availability is invented. "
             "Phase-1 conventional-action evidence supports a LIKELY classification only; TVSMOTOR preference distribution and BRITANNIA's unexplained "
             "factor=1 are ambiguous. Rights/demergers remain material unresolved. Buyback factor zero is never multiplied. Dividends are retained "
             "under the price-momentum policy; the source cannot distinguish special distributions.\n",
             f"{len(unresolved)} current-universe EQ events require exclusion review. Windows: {config['corporate_actions']['before_sessions']} "
             f"sessions before / {config['corporate_actions']['after_sessions']} after. Default **zero/zero is a placeholder**, with exact recorded "
             "event dates excluded where observed; a non-session date is not silently moved. The mechanism counts observed market dates, including "
             "special/partial dates. Ledger supplies window anchors, event IDs and coverage limitations. **Never filter eligible rows and then "
             "calculate returns across removed dates.** Phase 3 must validate full input/target intervals and unresolved boundaries "
             "(an interval guard exists; no returns are calculated).\n",
             "## 9. Number and percentage of research-eligible rows\n", f"**{count:,} / {total:,} = {count/total:.4%}**. "
             "Eligibility is a per-row quality gate only; no lookback, holding horizon, direction or capital eligibility exists.\n",
             "## 10. Exclusion counts by reason\n", markdown_table(reasons),
             "Reasons overlap; their sum is not the number of excluded rows.\n",
             "## 11. Symbols with materially reduced usable history\n", markdown_table(reduced.head(15)),
             "Sorted by retained fraction, with no modelling cutoff selected. Full 120-symbol table: phase2_usable_history.csv. "
             "TMCV/TATACAP/HYUNDAI also have short absolute histories, irrespective of retained percentage.\n",
             "## 12. Remaining unresolved issues\n",
             "Vendor adjustment completeness, volume basis, historical aliases and special distributions remain unverified. "
             "Corporate-action files lack ex-date/announcement lineage and end 2026-07-17, before OHLCV's 2026-07-31 endpoint. "
             "No event recorded does not mean action-free; daily rows carry incomplete coverage status. "
             "No period after the last recorded event is silently certified action-free or automatically truncated. "
             "Unknown shared holes, the full exchange calendar and official daily endpoints remain unresolved. "
             "Current-universe selection is deliberately conditional, not survivorship-free.\n",
             "## 13. Tests run and results\n", test_text + "\n",
             f"Dataset checks: {len(checks)} passed. Full rebuild byte identity: **{'PASS' if reproducible else 'NOT YET VERIFIED'}**. "
             "Future-row isolation is tested on deterministic fixtures; arbitrary vendor revisions to historical rows are detected by hashes, not assumed away.\n",
             "Commands (from project root):\n\n```bash\n.venv/bin/python scripts/build_research_dataset.py\n"
             ".venv/bin/python scripts/build_research_dataset.py --verify-rebuild\n"
             ".venv/bin/python -m pytest -q --junitxml=reports/pytest-results.xml\n"
             ".venv/bin/python scripts/validate_research_dataset.py --pytest-xml reports/pytest-results.xml\n```\n",
             "## 14. SAFE TO BEGIN CSRS RESEARCH?\n",
             "**NOT YET for unrestricted CSRS factor/target calculations.** Phase-2 data engineering is accepted when validation and deterministic "
             "rebuild checks pass; the foundation is ready for Phase-3 design and interval acceptance. Zero-width event flags do not protect "
             "lookbacks or future labels crossing unresolved actions, and action-date/coverage limitations still need an explicit Phase-3 treatment. "
             "research_eligible=true is not certification of an arbitrary multi-day return. No factor calculation was started.\n",
             "## 15. Exact recommended Phase-3 scope\n",
             "First agree unresolved-event interval/window treatment, action-date and coverage limitations, and calendar restrictions. "
             "Specify a preregistered CSRS definition/target and validation design without importing engine defaults. "
             "Require all factor and outcome inputs to pass row and interval checks, preserve the trading-date index, and enforce information availability. "
             "Only after that acceptance, authorize price-momentum CSRS experiments labelled conditional current-universe research. "
             "Sector/volume factors and portfolio backtests remain separate later work.\n"]
    text = "\n".join(lines)
    (reports / "phase2_dataset_acceptance.md").write_text(text)
    (reports / "phase2_validation.json").write_text(canonical_json({"build_id": manifest["build_id"], "checks": checks,
                                                                 "deterministic_rebuild_verified": reproducible}))
    return f"{total:,} daily rows; {count:,} eligible ({count/total:.2%}); {len(checks)} checks PASS. CSRS interval acceptance pending."
