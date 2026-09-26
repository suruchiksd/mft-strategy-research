import pandas as pd
import pytest

from conftest import minutes
from mft_research.data.daily_bars import aggregate_minutes
from mft_research.data.sessions import finalize_sessions


def test_normal_daily_and_known_values(config, rules):
    frame = minutes()
    frame.loc[0, "open"] = 101.0
    frame.loc[100, "high"] = 110.0
    frame.loc[200, "low"] = 90.0
    frame.loc[374, "close"] = 100.5
    daily, excluded = aggregate_minutes(frame, "ABB", rules, config)
    row = daily.iloc[0]
    assert (row.open, row.high, row.low, row.close, row.volume) == (101, 110, 90, 100.5, 3750)
    assert row.missing_expected_minutes == 0 and row.open_is_scheduled_first_minute
    assert excluded.empty
    assert row.bar_available_at == pd.Timestamp("2024-06-24 15:30", tz="Asia/Kolkata")


def test_invalid_open_removed_from_ohlcv_and_recorded(config, rules):
    frame = minutes(day="2024-06-25")
    frame.loc[0, "open"] = 200
    frame.loc[0, "volume"] = 123456
    daily, excluded = aggregate_minutes(frame, "ABB", rules, config)
    daily, _ = finalize_sessions(daily, rules)
    row = daily.iloc[0]
    assert row.open == 100 and row.high == 103 and row.volume == 3740
    assert row.invalid_ohlc_minutes == 1 and row.excluded_minutes == 1
    assert not row.open_is_first_observed_minute and not row.open_is_scheduled_first_minute
    assert row.session_quality == "DATA_QUALITY_ISSUE"
    assert excluded.iloc[0].open == 200 and excluded.iloc[0].volume == 123456
    assert excluded.iloc[0].exclusion_reason == "INVALID_OHLC"


def test_irfc_prelisting_has_no_valid_aggregation(config, rules):
    daily, excluded = aggregate_minutes(minutes(day="2020-01-03", symbol="IRFC"), "IRFC", rules, config)
    assert daily.valid_bars.iloc[0] == 0 and pd.isna(daily.open.iloc[0])
    assert len(excluded) == 375
    assert excluded.exclusion_reason.eq("PRELISTING_IDENTITY_CONTAMINATION").all()


def test_duplicate_copies_all_excluded_order_independent(config, rules):
    frame = pd.concat([minutes(), minutes().iloc[[0]]], ignore_index=True)
    daily, excluded = aggregate_minutes(frame, "ABB", rules, config)
    shuffled, _ = aggregate_minutes(frame.sample(frac=1, random_state=8), "ABB", rules, config)
    pd.testing.assert_frame_equal(daily, shuffled)
    assert daily.duplicate_minutes.iloc[0] == 2 and len(excluded) == 2
    assert daily.valid_bars.iloc[0] == 374


def test_375_wrong_timestamps_is_not_complete(config, rules):
    daily, excluded = aggregate_minutes(minutes(start="09:16"), "ABB", rules, config)
    daily, _ = finalize_sessions(daily, rules)
    assert daily.observed_bars.iloc[0] == 375
    assert daily.missing_expected_minutes.iloc[0] == 1
    assert daily.unexpected_minutes.iloc[0] == 1
    assert daily.session_quality.iloc[0] == "UNKNOWN_IRREGULAR"


def test_zero_volume_retained_negative_volume_excluded(config, rules):
    frame = minutes()
    frame.loc[0, "volume"] = 0
    frame.loc[1, "volume"] = -10
    daily, excluded = aggregate_minutes(frame, "ABB", rules, config)
    assert daily.zero_volume_minutes.iloc[0] == 1 and daily.valid_bars.iloc[0] == 374
    assert len(excluded) == 1 and daily.volume.iloc[0] == 3730


def test_naive_timestamp_rejected(config, rules):
    frame = minutes()
    frame["timestamp"] = frame.timestamp.dt.tz_localize(None)
    with pytest.raises(ValueError, match="Asia/Kolkata"):
        aggregate_minutes(frame, "ABB", rules, config)


def test_future_append_and_modification_do_not_change_past(config, rules):
    old = minutes()
    future = minutes(day="2024-06-26")
    base, _ = aggregate_minutes(old, "ABB", rules, config)
    for high in [103.0, 100000.0]:
        future["high"] = high
        combined, _ = aggregate_minutes(pd.concat([old, future], ignore_index=True), "ABB", rules, config)
        pd.testing.assert_frame_equal(base, combined.iloc[:1].reset_index(drop=True))


def test_missing_close_not_filled_and_availability_waits_for_close(config, rules):
    daily, _ = aggregate_minutes(minutes().iloc[:-1], "ABB", rules, config)
    assert daily.valid_bars.iloc[0] == 374
    assert not daily.close_is_scheduled_last_minute.iloc[0]
    assert daily.bar_available_at.iloc[0] == pd.Timestamp("2024-06-24 15:30", tz="Asia/Kolkata")
