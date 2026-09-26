import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from conftest import PROJECT
from mft_research.csrs import FORMATION_HORIZONS, FUTURE_HORIZONS
from mft_research.data.manifest import sha256


pytestmark = pytest.mark.integration


def test_csrs_panel_contract_and_determinism_evidence():
    path = PROJECT / "data/derived/csrs_factor_panel.parquet"
    panel = pq.ParquetFile(path).read().to_pandas()
    manifest = json.loads((PROJECT / "reports/csrs/csrs_build_manifest.json").read_text())
    assert len(panel) == 188451 and sha256(path) == manifest["panel_sha256"]
    for horizon in FORMATION_HORIZONS:
        for prefix in ("ret", "valid_ret", "csrs_rank", "csrs_pct", "cross_section_count"):
            assert f"{prefix}_{horizon}" in panel
    for horizon in FUTURE_HORIZONS:
        assert {f"future_ret_{horizon}", f"valid_future_{horizon}", f"future_invalid_reason_{horizon}"} <= set(panel)
    assert not any("combined" in c.lower() or "weighted" in c.lower() or c == "csrs_score" for c in panel)
    proof = json.loads((PROJECT / "reports/csrs/csrs_rebuild_verification.json").read_text())
    assert proof["build_id"] == manifest["build_id"] and proof["byte_identical"]
