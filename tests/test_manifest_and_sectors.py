import json

import pandas as pd
import pytest

from mft_research.data.manifest import fingerprint, save_manifest, verify_sources, local_path
from mft_research.data.sectors import read_sectors


def test_manifest_is_write_once_and_timestamp_reused(tmp_path):
    original = {"build_id": "abc", "build_timestamp_utc": "first", "policy": {"a": 1}}
    save_manifest(tmp_path, original)
    again = save_manifest(tmp_path, {**original, "build_timestamp_utc": "later"})
    assert again == original
    with pytest.raises(RuntimeError, match="collision"):
        save_manifest(tmp_path, {**original, "policy": {"a": 2}})
    assert json.loads((tmp_path / "manifests/abc.json").read_text()) == original


def test_source_modification_or_addition_detected(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("A\n")
    manifest = {"sources": {"sectors": str(tmp_path)}, "files": [fingerprint("sectors", path)]}
    verify_sources(manifest)
    path.write_text("B\n")
    with pytest.raises(RuntimeError, match="changed"):
        verify_sources(manifest)
    manifest["files"] = [fingerprint("sectors", path)]
    (tmp_path / "new.csv").write_text("C\n")
    with pytest.raises(RuntimeError, match="file set changed"):
        verify_sources(manifest)


def test_output_path_cannot_escape_project(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        local_path(tmp_path, "../upstream")


def test_sector_headerless_no_guessing_duplicate_and_conflict(tmp_path):
    (tmp_path / "some_sector_A.csv").write_text("ABB\nABB\n\nADANIGREEN\n")
    (tmp_path / "power_B.csv").write_text("ADANIGREEN\n")
    data, issues = read_sectors(tmp_path, ["ABB", "ADANIGREEN", "UNKNOWN"])
    a, b, c = data.iloc[0], data.iloc[1], data.iloc[2]
    assert a.sector == "some_sector" and a.sector_mapping_status == "UNIQUE"
    assert pd.isna(b.sector) and b.sector_mapping_status == "CONFLICT"
    assert pd.isna(c.sector) and c.sector_mapping_status == "UNMAPPED"
    assert set(issues.issue) == {"BLANK_RECORD", "DUPLICATE_RECORD"}
