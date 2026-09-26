"""Explicit minute grids, never infer completeness from row count alone."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


def minute(value: str) -> int:
    hour, minutes = map(int, value.split(":"))
    if not 0 <= hour < 24 or not 0 <= minutes < 60:
        raise ValueError(value)
    return hour * 60 + minutes


def grid(intervals: list[list[str]]) -> frozenset[int]:
    result: set[int] = set()
    for start, end in intervals:
        a, b = minute(start), minute(end)
        if a >= b or result.intersection(range(a, b)):
            raise ValueError("Session intervals must be ordered, disjoint and same-day")
        result.update(range(a, b))
    return frozenset(result)


@dataclass(frozen=True)
class SessionSpec:
    session_type: str
    expected: frozenset[int] | None
    force_ineligible: bool = False
    evidence_status: str = "NORMAL_GRID_ON_OBSERVED_WEEKDAY"
    evidence: str = "https://www.nseindia.com/static/market-data/market-timings"
    notes: str = "Observed-date calendar; exchange-wide absent dates not certified"


class SessionRules:
    def __init__(self, config: dict, project: Path):
        self.normal = grid(config["normal_intervals"])
        self.overrides = {}
        data = pd.read_csv(project / config["session_overrides_file"], keep_default_na=False)
        if data.date.duplicated().any():
            raise ValueError("Duplicate calendar override date")
        for row in data.itertuples(index=False):
            intervals = [part.split("-") for part in row.intervals.split("|")] if row.intervals else []
            self.overrides[date.fromisoformat(row.date)] = SessionSpec(
                row.session_type, grid(intervals) if intervals else None,
                str(row.force_ineligible).lower() == "true", row.evidence_status, row.evidence, row.notes)

    def for_date(self, day: date) -> SessionSpec:
        if day in self.overrides:
            return self.overrides[day]
        if day.weekday() >= 5:
            return SessionSpec("UNKNOWN_IRREGULAR", None, True, "UNVERIFIED_WEEKEND", "",
                               "No schedule invented for an unrecognized weekend")
        return SessionSpec("NORMAL", self.normal)


def classify(spec: SessionSpec, observed: set[int], invalid: bool = False,
             shared_partial: bool = False) -> str:
    if invalid:
        return "DATA_QUALITY_ISSUE"
    if spec.expected is None:
        return "PARTIAL_SHARED_MARKET_EVENT" if spec.session_type == "HALT_OR_EXTENDED_UNRESOLVED" else "UNKNOWN_IRREGULAR"
    if spec.force_ineligible or observed - spec.expected:
        return "UNKNOWN_IRREGULAR"
    if spec.expected - observed:
        return "PARTIAL_SHARED_MARKET_EVENT" if shared_partial else "PARTIAL_SYMBOL_SPECIFIC"
    return "NORMAL_COMPLETE" if spec.session_type == "NORMAL" else "KNOWN_SPECIAL_COMPLETE"


def finalize_sessions(daily: pd.DataFrame, rules: SessionRules) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = daily.copy()
    calendars = []
    qualities = pd.Series(index=daily.index, dtype="str")
    for day, rows in daily.groupby("date", sort=True):
        spec = rules.for_date(day)
        short = rows.missing_expected_minutes.fillna(0).gt(0)
        shared = int(short.sum()) >= 2  # descriptive: at least two symbols, not an acceptance threshold
        for idx, row in rows.iterrows():
            invalid = row.invalid_ohlc_minutes > 0 or row.other_invalid_minutes > 0 or row.duplicate_minutes > 0
            if invalid:
                quality = "DATA_QUALITY_ISSUE"
            elif spec.expected is None:
                quality = "PARTIAL_SHARED_MARKET_EVENT" if spec.session_type == "HALT_OR_EXTENDED_UNRESOLVED" else "UNKNOWN_IRREGULAR"
            elif spec.force_ineligible or row.unexpected_minutes > 0:
                quality = "UNKNOWN_IRREGULAR"
            elif row.missing_expected_minutes > 0:
                quality = "PARTIAL_SHARED_MARKET_EVENT" if shared else "PARTIAL_SYMBOL_SPECIFIC"
            else:
                quality = "NORMAL_COMPLETE" if spec.session_type == "NORMAL" else "KNOWN_SPECIAL_COMPLETE"
            qualities.loc[idx] = quality
        expected = sorted(spec.expected) if spec.expected is not None else []
        calendars.append({"date": day, "session_type": spec.session_type,
                          "expected_minutes": len(expected) if expected else None,
                          "expected_minute_labels": ",".join(map(str, expected)),
                          "scheduled_open": pd.Timestamp(day, tz="Asia/Kolkata") + pd.Timedelta(minutes=expected[0]) if expected else pd.NaT,
                          "scheduled_close": pd.Timestamp(day, tz="Asia/Kolkata") + pd.Timedelta(minutes=expected[-1] + 1) if expected else pd.NaT,
                          "observed_symbols": len(rows), "partial_symbols": int(short.sum()),
                          "shared_partial_observed": shared, "force_ineligible": spec.force_ineligible,
                          "evidence_status": spec.evidence_status, "evidence": spec.evidence,
                          "calendar_scope": "observed_dates_only", "notes": spec.notes})
    daily["session_quality"] = qualities
    calendar = pd.DataFrame(calendars)
    calendar["expected_minutes"] = calendar.expected_minutes.astype("Int64")
    return daily, calendar
