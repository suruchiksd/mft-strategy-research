import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256

PROJECT = Path(__file__).resolve().parents[1]


def artifact(phase, manifest_path, name):
    special = {
        (5, "historical_nse_daily.parquet"): PROJECT / "data/derived/historical_nse_daily.parquet",
        (5, "phase5_point_in_time_csrs.md"): PROJECT / "reports/phase5_point_in_time_csrs.md",
        (6, "sector_research_mapping.parquet"): PROJECT / "data/derived/sector_research_mapping.parquet",
        (6, "phase6_sector_foundation.md"): PROJECT / "reports/phase6_sector_foundation.md",
        (7, "sector_momentum_factor_panel.parquet"): PROJECT / "data/derived/sector_momentum_factor_panel.parquet",
        (7, "phase7_sector_relative_momentum.md"): PROJECT / "reports/phase7_sector_relative_momentum.md",
    }
    return special.get((phase, name), manifest_path.parent / name)


def test_phase5_phase6_phase7_accepted_artifacts_unchanged():
    manifests = ((5, PROJECT / "reports/csrs/point_in_time/phase5_build_manifest.json"),
                 (6, PROJECT / "reports/sector_momentum/foundation/phase6_build_manifest.json"),
                 (7, PROJECT / "reports/sector_momentum/research/phase7_build_manifest.json"))
    for phase, path in manifests:
        manifest = json.loads(path.read_text())
        for name, digest in manifest["output_sha256"].items():
            assert sha256(artifact(phase, path, name)) == digest


def test_phase8_outputs_acceptance_and_deterministic_proof():
    root = PROJECT / "reports/volume_momentum/foundation"
    manifest = json.loads((root / "phase8_build_manifest.json").read_text())
    proof = json.loads((root / "phase8_rebuild_verification.json").read_text())
    acceptance = json.loads((root / "phase8_acceptance.json").read_text())
    assert proof["byte_identical"] and proof["build_id"] == manifest["build_id"]
    assert all(item["passed"] for item in acceptance)
    for name, digest in manifest["output_sha256"].items():
        path = (PROJECT / "data/derived/volume_momentum_foundation.parquet" if name.endswith(".parquet") else
                PROJECT / "reports/phase8_volume_momentum_foundation.md" if name.endswith(".md") else root / name)
        assert sha256(path) == digest


def test_foundation_schema_is_outcome_blind_and_universes_preserved():
    path = PROJECT / "data/derived/volume_momentum_foundation.parquet"
    panel = pd.read_parquet(path)
    required = {"price_return_5", "price_return_20", "volume_mean_20_prior", "volume_mean_60_prior",
                "volume_median_20_prior", "volume_median_60_prior", "volume_ratio_20", "volume_ratio_60",
                "volume_median_ratio_20", "volume_median_ratio_60", "log_volume_surprise_20",
                "log_volume_surprise_60", "universe_broad_eq", "universe_basic_liquid",
                "universe_moderate_liquid", "universe_strict_sensitivity"}
    assert required.issubset(panel.columns)
    forbidden = ("future_", "outcome", "portfolio", "pnl", "sharpe", "trading_return", "sector_momentum", "csrs")
    assert not any(token in column.lower() for column in panel.columns for token in forbidden)


def test_registry_coverage_and_source_contracts_are_frozen():
    root = PROJECT / "reports/volume_momentum/foundation"
    registry = pd.read_csv(root / "candidate_factor_registry.csv")
    assert registry.candidate_id.tolist() == ["VM01", "VM02", "VM03", "VM04", "VM05", "VM06", "VM07"]
    assert registry.formula.is_unique and set(registry.role) == {"CONTROL_PRICE", "CONTROL_VOLUME", "INTERACTION"}
    assert registry.primary_universe.eq("BASIC_LIQUID").all()
    assert registry.sensitivity_universe.eq("MODERATE_LIQUID").all()
    audit = pd.read_csv(root / "volume_source_audit.csv")
    assert set(audit.source_format) == {"OLD", "NEW"} and audit.volume_unit.eq("shares").all()
    coverage = pd.read_csv(root / "feature_coverage.csv")
    assert set(coverage.universe) == {"BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY"}
