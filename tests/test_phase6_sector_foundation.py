from datetime import date
from pathlib import Path

import pandas as pd

from mft_research.sector_foundation import (audit_sector_files, build_mapping,
    historical_coverage, parse_sector_filename)


def identity(symbols):
    return pd.DataFrame({"symbol": symbols, "first_date": [date(2020, 1, 1)] * len(symbols),
        "last_date": [date(2020, 1, 2)] * len(symbols), "observed_sessions": [2] * len(symbols),
        "known_alias": [""] * len(symbols), "observed_isin_count": [0] * len(symbols),
        "continuity_status": ["OBSERVED_SYMBOL_HISTORY_NOT_STITCHED"] * len(symbols),
        "identity_ambiguity": [False] * len(symbols), "identity_policy": ["exact"] * len(symbols)})


def test_final_underscore_filename_parsing_is_deterministic():
    assert parse_sector_filename(Path("construction_supplies_CS.csv")) == ("construction_supplies", "CS")


def test_blank_duplicate_conflict_and_unmapped_are_preserved(tmp_path):
    (tmp_path / "alpha_AA.csv").write_text("A\nA\n\nB\n")
    (tmp_path / "beta_BB.csv").write_text("B\n")
    inventory, issues, conflicts, memberships = audit_sector_files(tmp_path)
    mapping = build_mapping(identity(["A", "B", "C"]), memberships)
    assert inventory.row_count.sum() == 5 and inventory.blank_rows.sum() == 1
    assert set(issues.issue) == {"BLANK_RECORD", "DUPLICATE_SYMBOL"}
    assert conflicts.symbol.tolist() == ["B"] and conflicts.resolution.eq("UNRESOLVED").all()
    assert mapping.set_index("symbol").loc["B", "mapping_status"] == "STATIC_CURRENT_CONFLICT"
    assert pd.isna(mapping.set_index("symbol").loc["B", "sector"])
    assert mapping.set_index("symbol").loc["C", "mapping_status"] == "UNMAPPED"
    assert pd.isna(mapping.set_index("symbol").loc["C", "sector"])


def test_identity_is_exact_only_and_static_is_not_historical():
    ids = identity(["OLD", "NEW"])
    ids.loc[0, "known_alias"] = "NEW"
    ids.loc[0, "identity_ambiguity"] = True
    memberships = {"NEW": [{"sector": "software", "sector_code": "SW", "source_file": "x", "source_row": 1}]}
    mapping = build_mapping(ids, memberships).set_index("symbol")
    assert mapping.loc["OLD", "mapping_status"] == "UNMAPPED"
    assert pd.isna(mapping.loc["OLD", "canonical_identity"])
    assert mapping.loc["NEW", "mapping_status"] == "STATIC_CURRENT_UNIQUE"
    assert not mapping.historically_verified.any()
    assert "NOT_EFFECTIVE_DATED" in mapping.loc["NEW", "historical_validity_status"]


def test_historical_coverage_uses_rowwise_point_in_time_universe_and_thresholds():
    ids = identity(["A", "B", "C"])
    memberships = {symbol: [{"sector": "s", "sector_code": "SS", "source_file": "x", "source_row": i}]
                   for i, symbol in enumerate(["A", "B", "C"], 1)}
    mapping = build_mapping(ids, memberships)
    daily = pd.DataFrame({"date": [date(2020, 1, 1)] * 3 + [date(2020, 1, 2)] * 3,
        "symbol": ["A", "B", "C"] * 2, "u": [True, True, False, True, True, True]})
    coverage, sizes, viability, _ = historical_coverage(daily, mapping, {"BROAD_EQ": "u"})
    assert coverage.eligible_observations.iloc[0] == 5
    assert sizes.stock_count.tolist() == [2, 3]
    v3 = viability[viability.threshold.eq(3)].iloc[0]
    assert v3.retained_sector_date_observations == 1
    assert v3.excluded_symbol_date_observations_small_sector == 2


def test_future_membership_rows_cannot_change_past_coverage():
    ids = identity(["A", "B"])
    memberships = {s: [{"sector": "s", "sector_code": "SS", "source_file": "x", "source_row": 1}] for s in ["A", "B"]}
    mapping = build_mapping(ids, memberships)
    base = pd.DataFrame({"date": [date(2020, 1, 1)], "symbol": ["A"], "u": [True]})
    future = pd.concat([base, pd.DataFrame({"date": [date(2021, 1, 1)], "symbol": ["B"], "u": [True]})])
    a = historical_coverage(base, mapping, {"BROAD_EQ": "u"})[0]
    b = historical_coverage(future, mapping, {"BROAD_EQ": "u"})[0]
    pd.testing.assert_frame_equal(a, b[b.year.eq(2020)].reset_index(drop=True))


def test_no_sector_factor_or_trading_contract_in_module():
    source = Path("src/mft_research/sector_foundation.py").read_text().lower()
    forbidden_definitions = ("def sector_return", "def sector_momentum", "def rank_sector", "portfolio_pnl")
    assert not any(token in source for token in forbidden_definitions)
