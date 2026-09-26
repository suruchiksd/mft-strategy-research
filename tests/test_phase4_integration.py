import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256

PROJECT = Path(__file__).resolve().parents[1]


def test_phase4_outputs_integrity_and_no_trading_columns():
    root = PROJECT / "reports/csrs/validation"
    manifest = json.loads((root / "phase4_build_manifest.json").read_text())
    proof = json.loads((root / "phase4_rebuild_verification.json").read_text())
    assert proof["byte_identical"] and proof["build_id"] == manifest["build_id"]
    assert len(manifest["output_sha256"]) == 11
    for name, digest in manifest["output_sha256"].items():
        assert sha256(root / name) == digest
        columns = pd.read_csv(root / name, nrows=0).columns
        assert not any("portfolio" in c.lower() or "pnl" in c.lower() or "trading_return" in c.lower() for c in columns)


def test_all_outputs_preserve_frozen_horizon_grid():
    root = PROJECT / "reports/csrs/validation"
    expected = {(f, h) for f in (5, 10, 20, 40, 60) for h in (1, 2, 3, 5, 10, 20)}
    for name in ("fixed_period_results.csv", "leave_one_year_out.csv", "year_stability.csv",
                 "cross_section_sensitivity.csv", "leave_one_symbol_out.csv", "sector_influence.csv"):
        frame = pd.read_csv(root / name)
        assert set(zip(frame.formation_horizon, frame.future_horizon)) == expected


def test_sector_influence_uses_unique_mappings_only():
    result = pd.read_csv(PROJECT / "reports/csrs/validation/sector_influence.csv")
    universe = pd.read_parquet(PROJECT / "data/derived/universe.parquet")
    assert result.mapping_status_used.eq("UNIQUE_ONLY").all()
    assert set(result.excluded_sector) == set(universe.loc[universe.sector_mapping_status.eq("UNIQUE"), "sector"])
    assert not set(universe.loc[~universe.sector_mapping_status.eq("UNIQUE"), "symbol"]).intersection(
        "|".join(result.excluded_symbols).split("|"))


def test_cross_section_sensitivity_does_not_rerank_and_original_panel_unchanged():
    result = pd.read_csv(PROJECT / "reports/csrs/validation/cross_section_sensitivity.csv")
    assert not result.factor_reranked.any()
    config = __import__("yaml").safe_load((PROJECT / "config/phase4_validation.yaml").read_text())
    assert sha256(PROJECT / config["factor_panel_path"]) == config["factor_panel_sha256"]


def test_symbol_influence_removes_only_named_symbol_and_no_combined_score():
    result = pd.read_csv(PROJECT / "reports/csrs/validation/leave_one_symbol_out.csv")
    assert result.removed_only_intended_symbol.all() and result.excluded_symbol.nunique() == 120
    classification = pd.read_csv(PROJECT / "reports/csrs/validation/formation_classification.csv")
    assert classification.formation_horizon.tolist() == [5, 10, 20, 40, 60]
    assert not any("combined" in c.lower() or "weighted" in c.lower() for c in classification)
