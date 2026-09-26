from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml

from mft_research.volume_momentum import (CANDIDATE_IDS, PRICE_HORIZONS, UNIVERSES,
    VOLUME_BASELINES, _rank, _winsor_same_date, assert_outcome_blind, build_foundation,
    candidate_registry)


def config():
    return yaml.safe_load(open("config/phase8_volume_momentum.yaml"))


def synthetic(symbols=("A", "B"), sessions=90):
    days = pd.bdate_range("2024-01-02", periods=sessions).date
    rows = []
    for sidx, symbol in enumerate(symbols):
        for i, day in enumerate(days):
            rows.append({"date": day, "symbol": symbol, "source_format": "OLD", "source_file": "x",
                "session_position": i, "first_observed_date": days[0], "history_sessions": i + 1,
                "close": 100 + i * (sidx + 1), "volume": 1 + i + 100 * sidx,
                "turnover_rupees": (1 + i + 100 * sidx) * (100 + i * (sidx + 1)),
                "research_quality_status": "VALID_REPORTED_EQ_ROW", "corporate_action_status": "NO_RECORDED_EVENT",
                "corporate_action_coverage_status": "NO_RECORDED_EVENT_NOT_COMPLETENESS_PROOF",
                "universe_broad_eq": True, "universe_basic_liquid": True,
                "universe_moderate_liquid": True, "universe_strict_sensitivity": True})
    return pd.DataFrame(rows).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def actions(day=None, impact="UNKNOWN_OR_AMBIGUOUS"):
    if day is None:
        return pd.DataFrame(columns=["symbol", "date", "series", "research_impact"])
    return pd.DataFrame({"symbol": ["A"], "date": [day], "series": ["EQ"], "research_impact": [impact]})


def test_frozen_horizons_and_universes():
    assert VOLUME_BASELINES == (20, 60)
    assert PRICE_HORIZONS == (5, 20)
    assert UNIVERSES == ("BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY")


def test_prior_20_baseline_is_exact_and_excludes_today():
    panel = build_foundation(synthetic(("A",), 70), actions(), config())
    row = panel[panel.symbol.eq("A")].sort_values("date").iloc[20]
    assert row.volume == 21 and row.volume_mean_20_prior == 10.5
    assert np.isclose(row.volume_ratio_20, 2.0)


def test_prior_60_baseline_is_exact_and_excludes_today():
    panel = build_foundation(synthetic(("A",), 70), actions(), config())
    row = panel[panel.symbol.eq("A")].sort_values("date").iloc[60]
    assert row.volume == 61 and row.volume_mean_60_prior == 30.5
    assert np.isclose(row.volume_median_60_prior, 30.5)


def test_trading_sessions_not_calendar_days_and_insufficient_history_invalid():
    panel = build_foundation(synthetic(("A",), 30), actions(), config()).sort_values("date")
    assert (panel.date.iloc[20] - panel.date.iloc[19]).days in (1, 3)
    assert panel.iloc[:20].valid_volume_baseline_20.eq(False).all()
    assert panel.iloc[19].volume_baseline_20_invalid_reason == "INSUFFICIENT_HISTORY"
    assert panel.iloc[20].valid_volume_baseline_20


def test_price_returns_are_exact():
    panel = build_foundation(synthetic(("A",), 30), actions(), config()).sort_values("date")
    assert np.isclose(panel.iloc[5].price_return_5, 105 / 100 - 1)
    assert np.isclose(panel.iloc[20].price_return_20, 120 / 100 - 1)


def test_corporate_action_crossing_invalidates_volume_and_price_intervals():
    raw = synthetic(("A",), 40); day = sorted(raw.date.unique())[10]
    panel = build_foundation(raw, actions(day), config()).sort_values("date")
    assert not panel.iloc[20].valid_volume_baseline_20
    assert panel.iloc[20].volume_baseline_20_invalid_reason == "CORPORATE_ACTION_INTERVAL"
    assert not panel.iloc[20].valid_price_return_20


def test_nonblocking_action_does_not_invalidate():
    raw = synthetic(("A",), 40); day = sorted(raw.date.unique())[10]
    panel = build_foundation(raw, actions(day, "NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM"), config()).sort_values("date")
    assert panel.iloc[20].valid_volume_baseline_20 and panel.iloc[20].valid_price_return_20


def test_zero_and_negative_volume_are_explicit():
    raw = synthetic(("A",), 30); raw.loc[raw.history_sessions.eq(21), "volume"] = 0
    panel = build_foundation(raw, actions(), config()).sort_values("date")
    assert panel.iloc[20].zero_volume_observation and panel.iloc[20].volume_ratio_20 == 0
    raw.loc[raw.history_sessions.eq(22), "volume"] = -1
    panel = build_foundation(raw, actions(), config()).sort_values("date")
    assert panel.iloc[21].negative_volume_observation and not panel.iloc[21].valid_volume_baseline_20
    assert panel.iloc[21].volume_baseline_20_invalid_reason == "NEGATIVE_VOLUME"


def test_ranking_is_same_date_and_strongest_is_highest_with_deterministic_ties():
    frame = pd.DataFrame({"date": [date(2024, 1, 1)] * 3 + [date(2024, 1, 2)] * 2,
                          "symbol": ["B", "A", "C", "A", "B"], "x": [2, 2, 1, 10, 20]})
    rank, pct, count = _rank(frame, "x", pd.Series(True, index=frame.index))
    assert rank.tolist() == [3, 2, 1, 1, 2]
    assert pct.tolist() == [1, .5, 0, 0, 1]
    assert count.tolist() == [3, 3, 3, 2, 2]


def test_winsorization_is_same_date_only():
    frame = pd.DataFrame({"date": [date(2024, 1, 1)] * 100 + [date(2024, 1, 2)] * 100,
                          "symbol": [f"A{i}" for i in range(100)] + [f"B{i}" for i in range(100)],
                          "x": list(range(100)) + list(range(1000, 1100))})
    result = _winsor_same_date(frame, "x", pd.Series(True, index=frame.index), .01, .99)
    assert result.iloc[:100].max() < 100 and result.iloc[100:].min() > 999


def test_future_rows_cannot_change_past_features():
    raw = synthetic(("A",), 70); base = build_foundation(raw, actions(), config())
    last = raw.iloc[-1].copy(); last["date"] = pd.bdate_range(raw.date.max(), periods=2).date[-1]
    last["session_position"] += 1; last["history_sessions"] += 1; last["volume"] = 999999999
    extended = build_foundation(pd.concat([raw, last.to_frame().T], ignore_index=True), actions(), config())
    columns = ["volume_ratio_20", "log_volume_surprise_60", "price_return_5", "candidate_vm01"]
    pd.testing.assert_frame_equal(base[columns], extended.iloc[:len(base)][columns], check_dtype=False)


def test_new_listing_history_is_not_backfilled():
    raw = synthetic(("A",), 70); late = synthetic(("B",), 30)
    late["date"] = sorted(raw.date.unique())[40:70]; late["session_position"] = range(40, 70)
    late["first_observed_date"] = late.date.min(); late["history_sessions"] = range(1, 31)
    panel = build_foundation(pd.concat([raw, late], ignore_index=True), actions(), config())
    b = panel[panel.symbol.eq("B")].sort_values("date")
    assert b.iloc[:20].volume_ratio_20.isna().all() and pd.notna(b.iloc[20].volume_ratio_20)


def test_registry_is_compact_unique_and_roles_valid():
    registry = candidate_registry()
    assert len(registry) == 7 and set(registry.candidate_id) == set(CANDIDATE_IDS)
    assert registry.formula.is_unique
    assert set(registry.role) == {"CONTROL_PRICE", "CONTROL_VOLUME", "INTERACTION"}


def test_no_future_other_factor_or_trading_columns():
    panel = build_foundation(synthetic(("A",), 70), actions(), config())
    assert_outcome_blind(panel)
    forbidden = ("future_", "sector_momentum", "csrs", "portfolio", "pnl", "trading_return")
    assert not any(token in column.lower() for column in panel.columns for token in forbidden)
