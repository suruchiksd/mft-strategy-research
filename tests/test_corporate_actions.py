from datetime import date
import json

import pandas as pd

from mft_research.data.corporate_actions import (
    MATERIAL, UNKNOWN, LIKELY_ADJUSTED, NO_ADJUSTMENT, SOURCE_COLUMNS,
    build_ledger, event_classification, exclusion_dates, interval_crosses_unresolved_event, attach_actions,
)


def source_row(symbol="ABB", day="20240625", label="dividend", factor="1.0"):
    return {"DATE": day, "SYMBOL": symbol, "SERIES": "EQ", "FACE VALUE": "1.0",
            "adj_factor": factor, "dividend": "2.0", "valid": label,
            "demerger": "", "merger": "", "buyback": ""}


def test_material_and_semantic_defects():
    for label in ["rights_issue", "demerger", "merger"]:
        assert event_classification(source_row(label=label), set())[1] == MATERIAL
    assert event_classification(source_row("TVSMOTOR", "20250825", "adj_factor_nonan", ".2"), set())[1] == UNKNOWN
    assert event_classification(source_row("BRITANNIA", "20210525", "adj_factor_nonan"), set())[1] == UNKNOWN
    assert event_classification(source_row(label="buyback", factor="0.0"), set())[1] == NO_ADJUSTMENT


def test_likely_conventional_requires_matching_evidence():
    row = source_row("HDFCBANK", "20250826", "adj_factor_nonan", "0.5")
    assert event_classification(row, set())[1] == UNKNOWN
    assert event_classification(row, {("HDFCBANK", "20250826", .5)})[1] == LIKELY_ADJUSTED


def test_source_rows_and_same_date_actions_never_deduplicated(tmp_path):
    root = tmp_path / "actions"
    root.mkdir()
    rows = [source_row(), source_row(label="rights_issue", factor=""), source_row()]
    pd.DataFrame(rows).to_csv(root / "CM_corpActions_2024.csv", index=False)
    evidence = tmp_path / "evidence.csv"
    pd.DataFrame(columns=["symbol", "date", "file_factor"]).to_csv(evidence, index=False)
    ledger = build_ledger(root, ["ABB"], evidence)
    assert len(ledger) == 3 and ledger.event_id.is_unique
    assert ledger.duplicate_key_count.eq(3).all() and ledger.duplicate_key_ambiguity.all()
    assert [json.loads(s) for s in ledger.source_record_json] == rows
    pd.testing.assert_frame_equal(ledger[SOURCE_COLUMNS], pd.DataFrame(rows)[SOURCE_COLUMNS], check_dtype=False)


def test_zero_window_does_not_guess_non_session_exdate():
    days = [date(2024, 6, 21), date(2024, 6, 24), date(2024, 6, 25)]
    assert exclusion_dates(date(2024, 6, 22), days, 0, 0) == []
    assert exclusion_dates(date(2024, 6, 24), days, 0, 0) == [date(2024, 6, 24)]
    assert exclusion_dates(date(2024, 6, 22), days, 1, 1) == days[:2]
    assert exclusion_dates(date(2024, 6, 24), days, 1, 1) == days


def test_interval_guard_catches_event_even_when_event_row_removed():
    ledger = pd.DataFrame([{"symbol": "ABB", "date": date(2024, 6, 24),
                            "affects_current_universe": True, "requires_window_exclusion": True}])
    assert interval_crosses_unresolved_event(ledger, "ABB", date(2024, 6, 21), date(2024, 6, 25))
    assert not interval_crosses_unresolved_event(ledger, "ABB", date(2024, 6, 25), date(2024, 6, 26))


def test_future_events_do_not_change_historical_default_flags(config):
    dates = [date(2024, 6, 24), date(2024, 6, 25), date(2024, 6, 26)]
    daily = pd.DataFrame({"symbol": ["ABB"] * 3, "date": dates})
    calendar = pd.DataFrame({"date": dates})
    row = {"symbol": "ABB", "date": dates[1], "event_id": "event1", "research_impact": MATERIAL,
           "affects_current_universe": True, "requires_window_exclusion": True}
    base, _ = attach_actions(daily, pd.DataFrame([row]), calendar, config["corporate_actions"])
    extended, _ = attach_actions(daily, pd.DataFrame([row, {**row, "date": date(2027, 1, 1), "event_id": "future"}]),
                                  calendar, config["corporate_actions"])
    pd.testing.assert_frame_equal(base, extended)
    assert base.corporate_action_unresolved.tolist() == [False, True, False]
