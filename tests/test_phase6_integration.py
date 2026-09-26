import hashlib
import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256

PROJECT = Path(__file__).resolve().parents[1]


def test_phase6_outputs_acceptance_and_deterministic_proof():
    root = PROJECT / "reports/sector_momentum/foundation"
    manifest = json.loads((root / "phase6_build_manifest.json").read_text())
    proof = json.loads((root / "phase6_rebuild_verification.json").read_text())
    acceptance = json.loads((root / "phase6_acceptance.json").read_text())
    assert proof["byte_identical"] and proof["build_id"] == manifest["build_id"]
    assert all(item["passed"] for item in acceptance)
    for name, digest in manifest["output_sha256"].items():
        path = (PROJECT / "data/derived/sector_research_mapping.parquet" if name.endswith(".parquet") else
                PROJECT / "reports/phase6_sector_foundation.md" if name.endswith(".md") else root / name)
        assert sha256(path) == digest


def test_upstream_sector_files_and_phase5_are_unchanged():
    manifest = json.loads((PROJECT / "reports/sector_momentum/foundation/phase6_build_manifest.json").read_text())
    for item in manifest["source_files"]:
        assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"]
    phase5 = json.loads((PROJECT / "reports/csrs/point_in_time/phase5_build_manifest.json").read_text())
    assert manifest["accepted_input"]["phase5_build_id"] == phase5["build_id"]
    for name, digest in phase5["output_sha256"].items():
        path = (PROJECT / "data/derived/historical_nse_daily.parquet" if name == "historical_nse_daily.parquet" else
                PROJECT / "reports/phase5_point_in_time_csrs.md" if name == "phase5_point_in_time_csrs.md" else
                PROJECT / "reports/csrs/point_in_time" / name)
        assert sha256(path) == digest


def test_mapping_contract_has_no_fabricated_history_or_conflict_resolution():
    mapping = pd.read_parquet(PROJECT / "data/derived/sector_research_mapping.parquet")
    assert len(mapping) == mapping.symbol.nunique() == 3381
    assert not mapping.historically_verified.any()
    assert mapping.loc[mapping.mapping_status.eq("UNMAPPED"), "sector"].isna().all()
    assert mapping.loc[mapping.mapping_status.eq("STATIC_CURRENT_CONFLICT"), "sector"].isna().all()
    assert mapping.loc[mapping.identity_ambiguous, "canonical_identity"].isna().all()


def test_all_universes_thresholds_and_no_factor_or_pnl_outputs():
    root = PROJECT / "reports/sector_momentum/foundation"
    coverage = pd.read_csv(root / "historical_sector_coverage.csv")
    viability = pd.read_csv(root / "sector_viability_by_year.csv")
    assert set(coverage.universe) == {"BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY"}
    assert set(viability.threshold) == {3, 5, 10}
    for path in root.glob("*.csv"):
        columns = pd.read_csv(path, nrows=0).columns
        assert not any(token in column.lower() for column in columns for token in
                       ("sector_momentum", "sector_return", "sector_rank", "portfolio", "pnl", "trading_return"))
