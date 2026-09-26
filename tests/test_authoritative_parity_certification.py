from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/sector_strategy/v2/paper_handoff/authoritative_parity"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authoritative_paper_outputs_are_present_and_manifested():
    names = [
        "historical_engine_orders.csv",
        "historical_engine_snapshots.csv",
        "historical_risk_parity.csv",
        "execution_quote_resolution_audit.csv",
    ]
    manifest = json.loads((OUT / "authoritative_paper_output_manifest.json").read_text())
    assert all((OUT / n).exists() for n in names)
    assert all(manifest["files"][n]["sha256"] == _sha(OUT / n) for n in names)


def test_authoritative_coverage_and_hathway_are_actual_outputs():
    state = pd.read_csv(OUT / "full_state_parity.csv")
    orders = pd.read_csv(OUT / "historical_engine_orders.csv")
    quotes = pd.read_csv(OUT / "execution_quote_resolution_audit.csv")
    hathway = pd.read_csv(OUT / "hathway_regression.csv").iloc[0]
    assert len(state) == 350
    assert len(orders) == 2096
    assert len(quotes) == 6994
    assert hathway.starting_quantity == 1262
    assert hathway.quote_source == "raw_provider"
    assert hathway.series == "BE"
    assert hathway.execution_open == 46.55
    assert hathway.actual_sell_quantity == 1262
    assert hathway.ending_quantity == 0
    assert hathway.tatacomm_buy_quantity == 95


def test_authoritative_comparison_loaded_reference_after_paper_generation():
    manifest = json.loads((OUT / "authoritative_parity_manifest.json").read_text())
    assert manifest["reference_loaded_after_paper_generation"] is True
    assert manifest["post_boundary_performance_inspected"] is False


def test_no_post_boundary_execution_dates_in_authoritative_outputs():
    reb = pd.read_csv(ROOT / "reports/sector_strategy/v2/development/v2_rebalances.csv")
    assert pd.to_datetime(reb.execution_date).max() <= pd.Timestamp("2026-09-17")


def test_refex_mark_and_full_reconciliation():
    marks = pd.read_csv(OUT / "end_of_day_mark_audit.csv")
    row = marks[(marks.date == "2024-10-07") & (marks.symbol == "REFEX")].iloc[0]
    assert row.source_used == "raw_provider"
    assert row.series == "BE"
    assert row.close == 516.50
    state = pd.read_csv(OUT / "full_state_parity.csv")
    accounting = pd.read_csv(OUT / "full_accounting_parity.csv")
    assert len(state) == 350 and int(state.state_exact.sum()) == 350
    assert len(accounting) == 350 and int(accounting.state_exact.sum()) == 350


def test_mark_only_repair_preserved_order_and_fill_hashes():
    assert _sha(OUT / "historical_engine_orders.csv") == "907ad3a85759a9d8a69e08b559228d404e5dd6b6cabbe13739f2807268ee77fa"
    assert _sha(OUT / "historical_risk_parity.csv") == "a7498d1e850d3ce9fe5d16379ae5e78bcfbd4c0de20a6d3e489da869da548ed4"
    assert _sha(OUT / "execution_quote_resolution_audit.csv") == "69c26ee6e335ed829ac97f9d19e7c50c25fbf6a38d54d819871a9b55f3d2b0df"
    fills = pd.read_csv(OUT / "full_fill_parity.csv")
    assert len(fills) == 2096 and int((fills.result == "EXACT").sum()) == 2096
