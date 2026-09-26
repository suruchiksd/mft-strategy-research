import json
from datetime import date

import pandas as pd
import pyarrow.parquet as pq
import pytest

from conftest import PROJECT
from mft_research.data.manifest import sha256
from mft_research.data.validation import ARTIFACTS, read_artifacts, validate_dataset


pytestmark = pytest.mark.integration


def test_full_source_and_dataset_contract(config):
    checks = validate_dataset(PROJECT, config)
    assert all(value == "PASS" for value in checks.values())


def test_independent_aggregation_for_known_bad_open_and_normal_day(config):
    daily = pq.ParquetFile(PROJECT / config["output_dir"] / "daily_bars.parquet").read().to_pandas()
    for symbol, day in [("HDFCBANK", "2024-06-25"), ("SBIN", "2024-06-24")]:
        path = PROJECT / config["sources"]["ohlcv"] / f"symbol={symbol}/year=2024/candles.parquet"
        source = pq.ParquetFile(path).read().to_pandas()
        frame = source[source.timestamp.dt.date == date.fromisoformat(day)].sort_values("timestamp")
        valid = frame[(frame.high >= frame[["open", "low", "close"]].max(axis=1))
                      & (frame.low <= frame[["open", "high", "close"]].min(axis=1))]
        row = daily[daily.symbol.eq(symbol) & daily.date.eq(date.fromisoformat(day))].iloc[0]
        assert row.open == valid.open.iloc[0] and row.close == valid.close.iloc[-1]
        assert row.high == valid.high.max() and row.low == valid.low.min()
        assert row.volume == valid.volume.sum()


def test_rebuild_has_byte_identical_evidence(config):
    output = PROJECT / config["output_dir"]
    manifest = json.loads((output / "source_manifest.json").read_text())
    proof = json.loads((PROJECT / "reports/phase2_rebuild_verification.json").read_text())
    assert proof["build_id"] == manifest["build_id"] and proof["all_artifacts_byte_identical"]
    for name in ARTIFACTS:
        assert sha256(output / name) == proof["artifact_sha256"][name]


def test_actual_known_events_and_identity(config):
    universe, daily, ledger, calendar, exclusions = read_artifacts(PROJECT / config["output_dir"])
    assert len(ledger) == 9752
    assert (ledger.duplicate_key_count > 1).sum() == 60
    assert daily.loc[daily.symbol.eq("IRFC") & daily.date.lt(date(2021, 1, 29)), "prelisting_minutes"].sum() == 31
    tvs = ledger[ledger.symbol.eq("TVSMOTOR") & ledger.date.eq(date(2025, 8, 25))]
    assert tvs.requires_window_exclusion.all()
    assert not daily.loc[daily.symbol.eq("TVSMOTOR") & daily.date.eq(date(2025, 8, 25)), "research_eligible"].any()
    assert set(universe[universe.sector_mapping_status.eq("UNMAPPED")].symbol) == {"ADANIENSOL", "ADANIPOWER", "LTM"}
