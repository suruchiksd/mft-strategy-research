#!/usr/bin/env python3
"""Build chronological CSRS validation outputs from the accepted Phase-3 panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.csrs.phase4 import (build_daily_cache, classify_formations,
    coverage_quality_sensitivity, cross_section_sensitivity, expanding_window,
    fixed_periods, leave_one_symbol_out, leave_one_year_out, nonoverlap,
    sector_influence, summarize_daily, uncertainty_intervals, year_stability)
from mft_research.data.manifest import canonical_json, sha256


def local(path: str) -> Path:
    result = (PROJECT / path).resolve()
    if not result.is_relative_to(PROJECT):
        raise ValueError("Phase-4 paths must remain within the research project")
    return result


def load_config() -> dict:
    config = yaml.safe_load((PROJECT / "config/phase4_validation.yaml").read_text())
    if tuple(config["formation_horizons"]) != (5, 10, 20, 40, 60):
        raise ValueError("Frozen formation horizons changed")
    if tuple(config["future_horizons"]) != (1, 2, 3, 5, 10, 20):
        raise ValueError("Frozen outcome horizons changed")
    return config


def verify_phase3(config: dict) -> dict:
    manifest = json.loads(local(config["phase3_manifest_path"]).read_text())
    acceptance = json.loads(local(config["phase3_acceptance_path"]).read_text())
    panel_path = local(config["factor_panel_path"])
    if manifest["build_id"] != config["phase3_build_id"]:
        raise RuntimeError("Phase-3 build ID mismatch")
    if manifest["panel_sha256"] != config["factor_panel_sha256"] or sha256(panel_path) != config["factor_panel_sha256"]:
        raise RuntimeError("Accepted Phase-3 factor panel checksum mismatch")
    if len(acceptance) != 48 or not all(item["passed"] for item in acceptance):
        raise RuntimeError("Phase-3 factor-panel acceptance is not 48/48 PASS")
    if manifest["config"]["corporate_action_coverage_end"] != config["certified_end"]:
        raise RuntimeError("Certified cutoff mismatch")
    return manifest


def code_fingerprint() -> str:
    paths = [PROJECT / "config/phase4_validation.yaml", PROJECT / "scripts/build_phase4_validation.py",
             PROJECT / "src/mft_research/csrs/phase4.py"] + sorted(PROJECT.glob("tests/test_phase4*.py"))
    records = [{"path": str(path.relative_to(PROJECT)), "sha256": sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def build(config: dict) -> dict[str, pd.DataFrame]:
    formations, futures = tuple(config["formation_horizons"]), tuple(config["future_horizons"])
    panel = pd.read_parquet(local(config["factor_panel_path"]))
    panel = panel[panel.date <= pd.Timestamp(config["certified_end"]).date()].copy()
    universe = pd.read_parquet(local(config["universe_path"]))
    cache = build_daily_cache(panel, formations, futures)
    full = pd.DataFrame([{"formation_horizon": f, "future_horizon": h, **summarize_daily(daily)}
                         for (f, h), daily in cache.items()])
    expanding = expanding_window(cache, tuple(config["expanding_evaluation_years"]))
    fixed = fixed_periods(cache, config["fixed_periods"])
    loyo = leave_one_year_out(cache, tuple(range(2020, 2027)))
    calendar = sorted(panel.date.unique())
    non = nonoverlap(cache, calendar, futures)
    uc = config["uncertainty"]
    uncertainty = uncertainty_intervals(cache, uc["replications"], uc["seed"], uc["confidence_level"])
    stability = year_stability(cache, tuple(range(2020, 2027)))
    cross_section = cross_section_sensitivity(cache, tuple(config["cross_section_thresholds"]))
    quality = coverage_quality_sensitivity(panel, formations, futures, config["retained_history_bands"])
    symbol = leave_one_symbol_out(panel, cache, formations, futures)
    sector = sector_influence(panel, universe, cache, formations, futures)
    classification = classify_formations(full, fixed, stability, uncertainty, non, formations)
    return {"expanding_window_results.csv": expanding, "fixed_period_results.csv": fixed,
            "leave_one_year_out.csv": loyo, "nonoverlap_results.csv": non,
            "uncertainty_intervals.csv": uncertainty, "year_stability.csv": stability,
            "cross_section_sensitivity.csv": cross_section,
            "coverage_quality_sensitivity.csv": quality,
            "leave_one_symbol_out.csv": symbol, "sector_influence.csv": sector,
            "formation_classification.csv": classification}


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, float_format="%.12g")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    config = load_config(); phase3 = verify_phase3(config)
    outputs = build(config)
    report_dir = local(config["report_dir"]); report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase4-staging-", dir=report_dir) as temporary:
        stage = Path(temporary)
        for name, frame in outputs.items():
            write_csv(frame, stage / name)
        hashes = {name: sha256(stage / name) for name in outputs}
        build_key = {"phase3_build_id": phase3["build_id"], "factor_panel_sha256": config["factor_panel_sha256"],
                     "code_sha256": code_fingerprint(), "config": config, "output_sha256": hashes}
        build_id = hashlib.sha256(canonical_json(build_key).encode()).hexdigest()
        manifest_path = report_dir / "phase4_build_manifest.json"
        if args.verify_rebuild:
            prior = json.loads(manifest_path.read_text())
            if prior["build_id"] != build_id or prior["output_sha256"] != hashes:
                raise AssertionError("Phase-4 rebuild identity differs")
            for name, digest in hashes.items():
                if sha256(report_dir / name) != digest:
                    raise AssertionError(f"Phase-4 output differs: {name}")
            proof = {"build_id": build_id, "byte_identical": True,
                     "output_count": len(outputs),
                     "command": ".venv/bin/python scripts/build_phase4_validation.py --verify-rebuild"}
            (report_dir / "phase4_rebuild_verification.json").write_text(canonical_json(proof))
            print(f"PASS deterministic Phase-4 rebuild: {len(outputs)} outputs; build {build_id}")
            return
        for name in outputs:
            os.replace(stage / name, report_dir / name)
        manifest = {**build_key, "build_id": build_id,
                    "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "research_scope": config["research_scope"], "certified_end": config["certified_end"]}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase-4 validation: {len(outputs)} outputs; build {build_id}")
        print(outputs["formation_classification.csv"].to_string(index=False))


if __name__ == "__main__":
    main()
