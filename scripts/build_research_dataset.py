#!/usr/bin/env python3
"""Build local Phase-2 artifacts, or independently reproduce and compare them."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.data.corporate_actions import attach_actions, build_ledger
from mft_research.data.daily_bars import build_daily
from mft_research.data.manifest import canonical_json, load_config, make_manifest, save_manifest, sha256, verify_sources
from mft_research.data.sectors import read_sectors
from mft_research.data.sessions import SessionRules, finalize_sessions
from mft_research.data.universe import apply_eligibility, build_universe, discover_symbols
from mft_research.data.validation import ARTIFACTS, validate_frames, write_acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/research_data.yaml")
    parser.add_argument("--verify-rebuild", action="store_true", help="Full independent rebuild and byte comparison; do not replace artifacts")
    args = parser.parse_args()
    config_path = (PROJECT / args.config).resolve()
    if not config_path.is_relative_to(PROJECT):
        raise ValueError("Config must be inside project")
    config = load_config(PROJECT, config_path)
    output, reports = PROJECT / config["output_dir"], PROJECT / config["report_dir"]
    output.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    with (output / ".build.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        symbols = discover_symbols(Path(config["sources"]["ohlcv"]), config["expected_symbols"])
        print("Fingerprinting all source files (SHA-256, size, mtime, Parquet row counts)", flush=True)
        manifest = make_manifest(PROJECT, config_path, config, symbols)
        rules = SessionRules(config, PROJECT)
        sectors, sector_issues = read_sectors(Path(config["sources"]["sectors"]), symbols)
        ledger = build_ledger(Path(config["sources"]["corporate_actions"]), symbols,
                              PROJECT / config["conventional_action_evidence_file"])
        daily, exclusions = build_daily(manifest["files"], rules, config)
        print("Classifying observed sessions and attaching event exclusions", flush=True)
        daily, calendar = finalize_sessions(daily, rules)
        daily, ledger = attach_actions(daily, ledger, calendar, config["corporate_actions"])
        daily = apply_eligibility(daily)
        daily = daily.merge(sectors, on="symbol", how="left", validate="many_to_one")
        universe = build_universe(daily, sectors, config)
        checks = validate_frames(universe, daily, ledger, calendar, exclusions, config)
        print("Rechecking source fingerprints before publication", flush=True)
        verify_sources(manifest)
        for item in manifest["code_files"] + manifest["evidence_files"]:
            if sha256(PROJECT / item["path"]) != item["sha256"]:
                raise RuntimeError(f"Code/evidence changed during build: {item['path']}")
        frames = [universe, daily, ledger, calendar, exclusions]
        # A complete staging directory is validated before publication. Manifest published last.
        # A crash during replacements is detected by artifact hashes; rerunning repairs local output.
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=output) as temporary:
            staging = Path(temporary)
            for name, frame in zip(ARTIFACTS, frames, strict=True):
                frame.to_parquet(staging / name, engine="pyarrow", compression="zstd", index=False)
            manifest["artifact_sha256"] = {name: sha256(staging / name) for name in ARTIFACTS}
            if args.verify_rebuild:
                previous = json.loads((output / "source_manifest.json").read_text())
                if previous["build_id"] != manifest["build_id"]:
                    raise RuntimeError("Inputs/code/runtime changed; this is not the same build")
                for name in ARTIFACTS:
                    if sha256(output / name) != manifest["artifact_sha256"][name] or previous["artifact_sha256"][name] != manifest["artifact_sha256"][name]:
                        raise AssertionError(f"Non-deterministic or modified artifact: {name}")
                (reports / "phase2_rebuild_verification.json").write_text(canonical_json({
                    "build_id": manifest["build_id"], "all_artifacts_byte_identical": True,
                    "artifact_sha256": manifest["artifact_sha256"], "source_hashes_sizes_mtimes_unchanged": True,
                    "command": ".venv/bin/python scripts/build_research_dataset.py --verify-rebuild"}))
                print("PASS: full rebuild; all five Parquet artifacts byte-identical; sources unchanged", flush=True)
            else:
                manifest = save_manifest(output, manifest)
                (staging / "source_manifest.json").write_text(canonical_json(manifest))
                for name in ARTIFACTS + ["source_manifest.json"]:
                    os.replace(staging / name, output / name)
                sector_issues.to_csv(reports / "phase2_sector_source_issues.csv", index=False)
                checks["source_hashes_sizes_mtimes_unchanged"] = "PASS"
                print(write_acceptance(PROJECT, config, checks), flush=True)


if __name__ == "__main__":
    main()
