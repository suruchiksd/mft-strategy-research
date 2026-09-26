import hashlib
import json
from pathlib import Path

import pandas as pd

from mft_research.sector_strategy_v2 import (
    MAX_POSITIONS,
    SECTOR_ENTRY_MAX_RANK,
    SECTOR_RETENTION_MAX_RANK,
    STOCK_ENTRY_MAX_RANK,
    STOCK_RETENTION_MAX_RANK,
    WEIGHT_TOLERANCE,
    execution_state,
    select_sectors,
    stock_plan,
)


ROOT = Path(__file__).parents[1]
OUT = ROOT / "reports/sector_strategy/v2/preregistration"


def artifacts():
    return json.loads((OUT / "phase12b_sector_strategy_v2_manifest.json").read_text())


def test_authoritative_phase12a_and_incident_are_separate():
    m = artifacts()
    assert m["accepted_inputs"]["phase12a_build_id"] == "9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5"
    assert "phase12a_integrity_incident.md" not in m["accepted_inputs"]
    assert m["accepted_inputs"]["phase12a_verified_outputs"] == 17


def test_exact_factor_and_no_new_alpha():
    c = yaml_config()
    assert c["alpha"] == {
        "sole_factor": "SECTOR_RELATIVE_MOMENTUM",
        "accepted_definition": "PHASE7_EQUAL_WEIGHT_SECTOR_DAILY_RETURNS_COMPOUNDED_20_SESSIONS",
        "formation_sessions": 20,
        "minimum_sector_size": 5,
        "mapping_tier": "STABLE_IDENTITY_BASIC_LIQUID",
    }
    assert c["forbidden"] == ["REV05", "REV20", "VOLUME_MOMENTUM", "STOCK_MOMENTUM_ALPHA", "MARKET_REGIME", "VOLATILITY_ALPHA", "STOP_LOSS", "PROFIT_TARGET", "ATR_RULE", "MACHINE_LEARNING", "COMBINED_SCORE"]


def yaml_config():
    import yaml

    return yaml.safe_load((ROOT / "config/phase12b_sector_strategy_v2.yaml").read_text())


def test_frozen_rank_constants_and_position_cap():
    assert (SECTOR_ENTRY_MAX_RANK, SECTOR_RETENTION_MAX_RANK) == (3, 5)
    assert (STOCK_ENTRY_MAX_RANK, STOCK_RETENTION_MAX_RANK) == (3, 5)
    assert MAX_POSITIONS == 9
    assert WEIGHT_TOLERANCE == 0.02


def test_sector_retention_and_entry_rules():
    today = pd.DataFrame({
        "sector_code": ["A", "B", "C", "D", "E"],
        "sector_ret_20": [0.50, 0.40, 0.30, 0.20, 0.10],
        "valid_sector_ret_20": [True] * 5,
    })
    selected = select_sectors(today, {"D"})
    assert set(selected.sector_code) == {"A", "B", "D"}
    retained = select_sectors(today, {"B", "D"})
    assert set(retained.sector_code) == {"A", "B", "D"}


def stock_inputs():
    today = pd.DataFrame({
        "symbol": ["A1", "A2", "A3", "A4"],
        "universe_basic_liquid": [True] * 4,
        "research_quality_status": ["VALID_REPORTED_EQ_ROW"] * 4,
        "close": [10.0] * 4,
        "avg_turnover_20": [40.0, 30.0, 20.0, 10.0],
        "recent_presence_20": [True] * 4,
    })
    mapping = pd.DataFrame({
        "symbol": ["A1", "A2", "A3", "A4"],
        "sector": ["alpha"] * 4,
        "sector_code": ["A"] * 4,
        "mapping_status": ["STATIC_CURRENT_UNIQUE"] * 4,
        "identity_ambiguous": [False] * 4,
    })
    sectors = pd.DataFrame({"sector_code": ["A"], "strength_rank": [1]})
    return today, mapping, sectors


def test_stock_entry_and_retention_are_liquidity_only():
    today, mapping, sectors = stock_inputs()
    intended, ranked = stock_plan(today, mapping, sectors, {"A1": "A"})
    assert list(ranked.liquidity_rank) == [1, 2, 3, 4]
    assert set(intended.symbol) == {"A1", "A2", "A3"}
    assert all(intended.selection_status.isin(["RETAINED", "NEW_ENTRY"]))


def test_new_BE_entry_is_forbidden():
    intended = pd.DataFrame([{"symbol": "X", "sector_code": "A", "sector_strength_rank": 1, "selection_status": "NEW_ENTRY"}])
    replacement = pd.DataFrame([{"symbol": "X", "sector_code": "A", "new_entry_eligible": True, "liquidity_rank": 1}])
    quotes = pd.DataFrame([{"symbol": "X", "series": "BE", "open": 10.0}])
    state, events = execution_state({}, intended, replacement, quotes)
    assert state == {}
    assert events[0]["event"] == "ENTRY_SKIPPED_NO_EQ_OPEN"


def test_unavailable_exit_is_retained_without_fabrication():
    intended = pd.DataFrame(columns=["symbol", "sector_code", "selection_status"])
    replacement = pd.DataFrame(columns=["symbol", "sector_code", "new_entry_eligible", "liquidity_rank"])
    state, events = execution_state({"X": "A"}, intended, replacement, pd.DataFrame())
    assert state == {"X": "A"}
    assert events[0]["event"] == "TRAPPED_RETRY"


def test_trapped_positions_count_toward_position_cap_and_no_PnL_columns():
    s = json.loads((OUT / "phase12b_feasibility_summary.json").read_text())
    assert s["summary"]["maximum_positions_observed"] <= MAX_POSITIONS
    assert s["summary"]["pnl_columns_created"] == 0
    assert s["v2_pnl_inspected"] is False
    assert s["post_2026_09_17_v2_performance_inspected"] is False


def test_signal_time_replacement_lists_are_frozen():
    s = json.loads((OUT / "phase12b_feasibility_summary.json").read_text())["summary"]
    assert s["replacement_lists_frozen"] == s["signal_dates"]
    assert s["distinct_replacement_list_hashes"] > 0


def test_period_boundary_and_cost_contract():
    c = yaml_config()
    assert c["periods"]["development_end"] == "2026-09-17"
    assert c["periods"]["fresh_validation_start_exclusive"] == "2026-09-17"
    assert c["periods"]["post_boundary_performance_read_in_phase12b"] is False
    assert c["costs"]["primary_total_bps_per_side"] == 25
    assert c["costs"]["primary_components"] == {"transaction_cost_bps": 20, "adverse_slippage_bps": 5}
    assert c["costs"]["sensitivity_total_bps_per_side"] == [0, 10, 25, 50]


def test_acceptance_rules_are_frozen():
    rules = json.loads((OUT / "phase12b_v2_acceptance_rules.json").read_text())
    gates = rules["shared_required_gates"]
    assert gates["mean_weekly_gross_turnover_max"] == 0.65
    assert gates["cost_retention_ratio_min"] == 0.40
    assert gates["single_stock_absolute_contribution_share_max"] == 0.50
    assert gates["single_sector_absolute_contribution_share_max"] == 0.60
    assert rules["real_money_authorized"] is False
    assert rules["automatic_paper_trade_authorized"] is False


def test_preregistration_outputs_match_manifest():
    m = artifacts()
    for name, expected in m["frozen_artifact_sha256"].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == expected


def test_state_audit_has_no_returns_or_cash_columns():
    t = pd.read_csv(OUT / "phase12b_state_transition_audit.csv")
    forbidden = {"shares", "cash", "nav", "return", "pnl", "transaction_cost", "sharpe", "drawdown"}
    assert not any(any(token in c.lower() for token in forbidden) for c in t.columns)


def test_BE_audit_is_fail_closed():
    b = pd.read_csv(OUT / "phase12b_be_series_audit.csv")
    assert (b.absent_rows >= 0).all()
    assert (b.policy_when_absent == "RETAIN_AND_RETRY_NO_FABRICATED_EXIT").all()
    assert (b.observed_BE_open_supports_exit_simulation == (b.BE_rows.gt(0) & b.positive_BE_open_rows.eq(b.BE_rows))).all()


def test_manifest_is_frozen_before_PnL():
    m = artifacts()
    assert m["status"] == "FROZEN_BEFORE_V2_PNL"
    assert m["v2_pnl_inspected"] is False
    assert m["post_2026_09_17_v2_performance_inspected"] is False
    assert m["fresh_validation_start_exclusive"] == "2026-09-17"
