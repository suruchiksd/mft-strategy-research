"""Trading-session interval validity for formation and outcome observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


BLOCKING_IMPACTS = {"MATERIAL_UNRESOLVED_EVENT", "UNKNOWN_OR_AMBIGUOUS"}


@dataclass(frozen=True)
class IntervalResult:
    value: float
    valid: bool
    reason: str
    endpoint_date: date | None


def blocking_events(ledger: pd.DataFrame, impacts: set[str] = BLOCKING_IMPACTS) -> dict[str, np.ndarray]:
    selected = ledger[
        ledger.affects_current_universe
        & ledger.series.eq("EQ")
        & ledger.research_impact.isin(impacts)
    ]
    return {
        symbol: np.array(sorted({pd.Timestamp(d).toordinal() for d in rows.date}), dtype=np.int64)
        for symbol, rows in selected.groupby("symbol", sort=True)
    }


def crosses_event(events: np.ndarray, start: date, end: date) -> bool:
    """True for a recorded source event in (start, end]."""
    if len(events) == 0:
        return False
    a, b = start.toordinal(), end.toordinal()
    return np.searchsorted(events, b, side="right") > np.searchsorted(events, a, side="right")


def _reason_string(reasons: list[str]) -> str:
    return "|".join(dict.fromkeys(reasons))


def _row_reason_is_identity(value: str) -> bool:
    return "PRELISTING_IDENTITY_CONTAMINATION" in (value or "")


def evaluate_symbol_intervals(
    rows: pd.DataFrame,
    calendar_dates: list[date],
    formation_horizons: tuple[int, ...],
    future_horizons: tuple[int, ...],
    events: np.ndarray,
    coverage_end: date,
) -> pd.DataFrame:
    """Evaluate intervals against the uncompressed observed-market calendar."""
    rows = rows.sort_values("date").copy()
    date_to_pos = {day: i for i, day in enumerate(calendar_dates)}
    n_dates = len(calendar_dates)
    cutoff_position = max(i for i, day in enumerate(calendar_dates) if day <= coverage_end)
    exists = np.zeros(n_dates, dtype=bool)
    eligible = np.zeros(n_dates, dtype=bool)
    identity = np.zeros(n_dates, dtype=bool)
    close = np.full(n_dates, np.nan)
    row_by_pos: dict[int, pd.Series] = {}
    for _, row in rows.iterrows():
        pos = date_to_pos[row.date]
        exists[pos] = True
        eligible[pos] = bool(row.research_eligible)
        identity[pos] = _row_reason_is_identity(row.exclusion_reason)
        close[pos] = row.close
        row_by_pos[pos] = row
    missing_prefix = np.concatenate(([0], np.cumsum(~exists)))
    unsafe_prefix = np.concatenate(([0], np.cumsum(exists & ~eligible)))
    identity_prefix = np.concatenate(([0], np.cumsum(identity)))

    def interval_count(prefix: np.ndarray, left: int, right: int) -> int:
        return int(prefix[right + 1] - prefix[left])

    output = rows[["date", "symbol", "close", "research_eligible"]].copy()
    positions = np.array([date_to_pos[d] for d in output.date], dtype=np.int64)

    for horizon in formation_horizons:
        values, valids, reasons, endpoints = [], [], [], []
        for pos in positions:
            current = row_by_pos[pos]
            endpoint = pos - horizon
            why: list[str] = []
            endpoint_date = calendar_dates[endpoint] if endpoint >= 0 else None
            if not current.research_eligible:
                why.append("SIGNAL_ROW_INELIGIBLE")
            if _row_reason_is_identity(current.exclusion_reason):
                why.append("IDENTITY_CONTAMINATION")
            if endpoint < 0:
                why.append("INSUFFICIENT_HISTORY")
            else:
                if not exists[endpoint]:
                    why.append("INSUFFICIENT_HISTORY" if endpoint < positions.min() else "UNAVAILABLE_ENDPOINT")
                elif not eligible[endpoint]:
                    why.append("LOOKBACK_ENDPOINT_INELIGIBLE")
                if interval_count(missing_prefix, endpoint, pos):
                    why.append("MISSING_UNSAFE_SESSION_INTERVAL")
                if interval_count(unsafe_prefix, endpoint, pos):
                    why.append("UNSAFE_SESSION_INTERVAL")
                if interval_count(identity_prefix, endpoint, pos):
                    why.append("IDENTITY_CONTAMINATION")
                if crosses_event(events, endpoint_date, current.date):
                    why.append("UNRESOLVED_CORPORATE_ACTION_INTERVAL")
            # The signal date is the lookback interval's certification end.
            # Record cutoff failure even when another interval defect coexists.
            if pos > cutoff_position:
                why.append("CORPORATE_ACTION_COVERAGE_UNCERTIFIED")
            valid = not why
            values.append(float(current.close / close[endpoint] - 1) if valid else np.nan)
            valids.append(valid)
            reasons.append(_reason_string(why))
            endpoints.append(endpoint_date)
        output[f"ret_{horizon}"] = values
        output[f"valid_ret_{horizon}"] = valids
        output[f"ret_{horizon}_invalid_reason"] = reasons
        output[f"ret_{horizon}_endpoint_date"] = endpoints

    for horizon in future_horizons:
        values, valids, reasons, endpoints = [], [], [], []
        for pos in positions:
            current = row_by_pos[pos]
            endpoint = pos + horizon
            why: list[str] = []
            endpoint_date = calendar_dates[endpoint] if endpoint < n_dates else None
            if not current.research_eligible:
                why.append("SIGNAL_ROW_INELIGIBLE")
            if _row_reason_is_identity(current.exclusion_reason):
                why.append("IDENTITY_CONTAMINATION")
            if endpoint >= n_dates:
                why.append("UNAVAILABLE_ENDPOINT")
            else:
                if not exists[endpoint]:
                    why.append("UNAVAILABLE_ENDPOINT")
                elif not eligible[endpoint]:
                    why.append("TARGET_ENDPOINT_INELIGIBLE")
                if interval_count(missing_prefix, pos, endpoint):
                    why.append("MISSING_UNSAFE_SESSION_INTERVAL")
                if interval_count(unsafe_prefix, pos, endpoint):
                    why.append("UNSAFE_SESSION_INTERVAL")
                if interval_count(identity_prefix, pos, endpoint):
                    why.append("IDENTITY_CONTAMINATION")
                if crosses_event(events, current.date, endpoint_date):
                    why.append("UNRESOLVED_CORPORATE_ACTION_INTERVAL")
            # The intended target position determines certification. This also
            # flags late unavailable targets whose endpoint is beyond the data.
            if endpoint > cutoff_position:
                why.append("CORPORATE_ACTION_COVERAGE_UNCERTIFIED")
            valid = not why
            values.append(float(close[endpoint] / current.close - 1) if valid else np.nan)
            valids.append(valid)
            reasons.append(_reason_string(why))
            endpoints.append(endpoint_date)
        output[f"future_ret_{horizon}"] = values
        output[f"valid_future_{horizon}"] = valids
        output[f"future_invalid_reason_{horizon}"] = reasons
        output[f"future_{horizon}_endpoint_date"] = endpoints
    return output


def build_interval_panel(
    daily: pd.DataFrame,
    ledger: pd.DataFrame,
    calendar: pd.DataFrame,
    formation_horizons: tuple[int, ...],
    future_horizons: tuple[int, ...],
    coverage_end: date,
) -> pd.DataFrame:
    dates = sorted(calendar.date.tolist())
    if len(dates) != len(set(dates)) or not set(daily.date).issubset(dates):
        raise ValueError("Invalid Phase-2 observed-session calendar")
    events = blocking_events(ledger)
    panels = []
    for symbol, rows in daily.groupby("symbol", sort=True):
        panels.append(evaluate_symbol_intervals(rows, dates, formation_horizons, future_horizons,
                                                events.get(symbol, np.array([], dtype=np.int64)), coverage_end))
    return pd.concat(panels, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
