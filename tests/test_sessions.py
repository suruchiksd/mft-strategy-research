from datetime import date

import pandas as pd
import pytest

from conftest import minutes
from mft_research.data.daily_bars import aggregate_minutes
from mft_research.data.sessions import classify, finalize_sessions


@pytest.mark.parametrize("day,start", [("2020-11-14", "18:15"), ("2021-11-04", "18:15"),
    ("2022-10-24", "18:15"), ("2023-11-12", "18:15"), ("2024-11-01", "18:00"), ("2025-10-21", "13:45")])
def test_muhurat_complete_grid(config, rules, day, start):
    daily, excluded = aggregate_minutes(minutes(day=day, start=start, periods=60), "ABB", rules, config)
    daily, _ = finalize_sessions(daily, rules)
    assert daily.session_quality.iloc[0] == "KNOWN_SPECIAL_COMPLETE"
    assert daily.missing_expected_minutes.iloc[0] == 0 and excluded.empty


@pytest.mark.parametrize("day", ["2024-03-02", "2024-05-18"])
def test_scheduled_break_is_not_missing(config, rules, day):
    frame = pd.concat([minutes(day=day, periods=45), minutes(day=day, start="11:30", periods=60)])
    daily, _ = aggregate_minutes(frame, "ABB", rules, config)
    daily, _ = finalize_sessions(daily, rules)
    assert daily.session_quality.iloc[0] == "KNOWN_SPECIAL_COMPLETE"
    assert daily.missing_expected_minutes.iloc[0] == 0
    partial, _ = aggregate_minutes(frame.iloc[:-1], "ABB", rules, config)
    partial, _ = finalize_sessions(partial, rules)
    assert partial.session_quality.iloc[0] == "PARTIAL_SYMBOL_SPECIFIC"


@pytest.mark.parametrize("day", ["2020-03-13", "2020-03-23", "2021-02-24"])
def test_unresolved_halting_dates_never_certified(rules, day):
    spec = rules.for_date(date.fromisoformat(day))
    assert spec.expected is None
    assert classify(spec, set(range(555, 930))) == "PARTIAL_SHARED_MARKET_EVENT"


def test_unknown_weekend_is_not_accepted_with_375_bars(rules):
    assert classify(rules.for_date(date(2024, 6, 23)), set(range(555, 930))) == "UNKNOWN_IRREGULAR"


def test_extra_bar_date_remains_unresolved(rules):
    assert classify(rules.for_date(date(2020, 4, 27)), set(range(555, 931))) == "UNKNOWN_IRREGULAR"


def test_shared_partial_uses_same_date_only(config, rules):
    a, _ = aggregate_minutes(minutes().iloc[:-1], "ABB", rules, config)
    b, _ = aggregate_minutes(minutes(symbol="ACC").iloc[:-1], "ACC", rules, config)
    initial, _ = finalize_sessions(pd.concat([a, b], ignore_index=True), rules)
    future, _ = aggregate_minutes(minutes(day="2024-06-26"), "ABB", rules, config)
    extended, _ = finalize_sessions(pd.concat([a, b, future], ignore_index=True), rules)
    assert initial.session_quality.eq("PARTIAL_SHARED_MARKET_EVENT").all()
    pd.testing.assert_frame_equal(initial, extended.iloc[:2].reset_index(drop=True))
