"""Lossless event ledger and configurable exclusion flags; never adjust prices."""

import bisect
import hashlib
import json
from pathlib import Path

import pandas as pd


NO_ADJUSTMENT = "NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM"
LIKELY_ADJUSTED = "LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION"
MATERIAL = "MATERIAL_UNRESOLVED_EVENT"
UNKNOWN = "UNKNOWN_OR_AMBIGUOUS"
SOURCE_COLUMNS = ["DATE", "SYMBOL", "SERIES", "FACE VALUE", "adj_factor", "dividend", "valid",
                  "demerger", "merger", "buyback"]


def event_classification(row: dict, conventional: set[tuple[str, str, float]]) -> tuple[str, str, bool, str]:
    symbol, day, label = row["SYMBOL"], row["DATE"], row["valid"]
    if symbol == "TVSMOTOR" and day == "20250825":
        return "PREFERENCE_SHARE_DISTRIBUTION", UNKNOWN, True, "PHASE1_TVSMOTOR_FACTOR_SEMANTIC_DEFECT"
    if label in {"rights_issue", "demerger", "merger"} or row["merger"] == "1.0" or row["merger"] == "1":
        return label.upper(), MATERIAL, True, "MISSING_ENTITLEMENT_TERMS_AND_UNVERIFIED_DATE_SEMANTICS"
    if label in {"dividend", "buyback"}:
        return label.upper(), NO_ADJUSTMENT, False, "SOURCE_LABEL_ONLY_SPECIAL_DISTRIBUTIONS_NOT_IDENTIFIABLE"
    if label == "adj_factor_nonan":
        try:
            key = (symbol, day, float(row["adj_factor"]))
        except ValueError:
            key = None
        if key in conventional:
            return "CONVENTIONAL_ACTION_SUPPORTED_BY_PHASE1", LIKELY_ADJUSTED, False, "PHASE1_CONTINUITY_EVIDENCE_NOT_VENDOR_CERTIFICATION"
        return "UNSPECIFIED_FACTOR_EVENT", UNKNOWN, True, "NO_VERIFIED_CONVENTIONAL_ACTION_EVIDENCE"
    return "UNCLASSIFIED", UNKNOWN, True, "UNRECOGNIZED_SOURCE_LABEL"


def build_ledger(root: Path, symbols: list[str], evidence_path: Path) -> pd.DataFrame:
    evidence = pd.read_csv(evidence_path)
    conventional = {(r.symbol, r.date.replace("-", ""), float(r.file_factor))
                    for r in evidence.itertuples(index=False)
                    if not (r.symbol == "TVSMOTOR" and r.date == "2025-08-25")}
    records = []
    for path in sorted(root.glob("*.csv")):
        source = pd.read_csv(path, dtype=str, keep_default_na=False)
        if source.columns.tolist() != SOURCE_COLUMNS:
            raise ValueError(f"Unexpected corporate action schema: {path}")
        for number, row in enumerate(source.to_dict("records"), start=2):
            day = pd.to_datetime(row["DATE"], format="%Y%m%d", errors="raise").date()
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
            event_id = hashlib.sha256(f"{path.name}:{number}:{encoded}".encode()).hexdigest()
            group = hashlib.sha256(f"{row['SYMBOL']}|{row['SERIES']}|{row['DATE']}".encode()).hexdigest()
            classification, impact, ambiguous, reason = event_classification(row, conventional)
            records.append({**row, "event_id": event_id, "source_file": str(path.resolve()),
                            "source_row": number, "source_record_json": encoded,
                            "date": day, "symbol": row["SYMBOL"], "series": row["SERIES"],
                            "action_classification": classification, "research_impact": impact,
                            "ambiguity_flag": ambiguous, "classification_reason": reason,
                            "date_semantics": "SOURCE_DATE_NOT_GLOBALLY_VERIFIED_EX_DATE",
                            "announcement_known_at": None,
                            "affects_current_universe": row["SYMBOL"] in symbols and row["SERIES"] == "EQ",
                            "duplicate_key_group": group,
                            "requires_window_exclusion": impact in {MATERIAL, UNKNOWN}})
    ledger = pd.DataFrame(records)
    ledger["duplicate_key_count"] = ledger.groupby("duplicate_key_group").event_id.transform("size")
    ledger["duplicate_key_ambiguity"] = ledger.duplicate_key_count.gt(1)
    # Distinct simultaneous actions are retained, each with independent impact classification.
    return ledger.sort_values(["date", "symbol", "series", "source_file", "source_row"]).reset_index(drop=True)


def exclusion_dates(event_date, calendar_dates: list, before: int, after: int) -> list:
    """Source-date exact match, plus N strictly earlier/later observed-market sessions.

    A non-session source date is NOT silently moved to a guessed ex-date.
    """
    if before < 0 or after < 0:
        raise ValueError("Negative event window")
    left = bisect.bisect_left(calendar_dates, event_date)
    right = bisect.bisect_right(calendar_dates, event_date)
    return calendar_dates[max(0, left - before):left] + calendar_dates[left:right] + calendar_dates[right:right + after]


def interval_crosses_unresolved_event(ledger: pd.DataFrame, symbol: str, start, end) -> bool:
    """Boundary guard only, not a return/factor calculation: start < event <= end."""
    if end < start:
        raise ValueError("Reversed interval")
    return bool((ledger.affects_current_universe & ledger.requires_window_exclusion & ledger.symbol.eq(symbol)
                 & ledger.date.gt(start) & ledger.date.le(end)).any())


def attach_actions(daily: pd.DataFrame, ledger: pd.DataFrame, calendar: pd.DataFrame,
                   policy: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, ledger = daily.copy(), ledger.copy()
    dates = sorted(calendar.date.tolist())
    keys = {(r.symbol, r.date): i for i, r in enumerate(daily.itertuples(index=False))}
    statuses, event_ids, blocked_ids = {}, {}, {}
    first_window, last_window, anchors = [], [], []
    for row in ledger.itertuples(index=False):
        window = exclusion_dates(row.date, dates, policy["before_sessions"], policy["after_sessions"])
        first_window.append(min(window) if window else None)
        last_window.append(max(window) if window else None)
        anchors.append("EXACT_OBSERVED_MARKET_DATE" if row.date in dates else "SOURCE_DATE_NOT_IN_OBSERVED_CALENDAR")
        if not row.affects_current_universe:
            continue
        key = (row.symbol, row.date)
        statuses.setdefault(key, set()).add(row.research_impact)
        event_ids.setdefault(key, []).append(row.event_id)
        if row.requires_window_exclusion:
            for day in window:
                blocked_ids.setdefault((row.symbol, day), []).append(row.event_id)
    ledger["exclusion_window_start"] = first_window
    ledger["exclusion_window_end"] = last_window
    ledger["window_anchor_status"] = anchors
    ledger["window_before_sessions"] = policy["before_sessions"]
    ledger["window_after_sessions"] = policy["after_sessions"]
    ledger["window_policy_status"] = policy["window_policy_status"]
    daily["corporate_action_status"] = ["|".join(sorted(statuses.get(key, {"NO_RECORDED_EVENT_NOT_CERTIFIED_ACTION_FREE"}))) for key in keys]
    daily["corporate_action_event_ids"] = ["|".join(sorted(event_ids.get(key, []))) for key in keys]
    daily["corporate_action_exclusion_event_ids"] = ["|".join(sorted(blocked_ids.get(key, []))) for key in keys]
    daily["corporate_action_unresolved"] = [key in blocked_ids for key in keys]
    daily["corporate_action_coverage_status"] = policy["coverage_status"]
    daily["return_interval_validation_required"] = True
    return daily, ledger
