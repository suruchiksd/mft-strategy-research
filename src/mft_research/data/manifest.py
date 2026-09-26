"""Content-addressed source snapshots; upstream is opened only for reading."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
import yaml


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(project: Path, value: str) -> Path:
    path = (project / value).resolve()
    if not path.is_relative_to(project.resolve()):
        raise ValueError(f"Local path escapes project: {path}")
    return path


def load_config(project: Path, path: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    if config["universe_mode"] != "fixed_current_120" or config["expected_symbols"] != 120:
        raise ValueError("Only the approved fixed current 120-symbol study is supported")
    if config["corporate_actions"]["apply_adjustments"]:
        raise ValueError("Price adjustment is prohibited in Phase 2")
    if config["timezone"] != "Asia/Kolkata":
        raise ValueError("Expected Asia/Kolkata")
    supported = {
        "invalid_minute_policy": "exclude_from_all_ohlcv_and_mark_day_ineligible",
        "partial_session_policy": "retain_ineligible",
        "unexpected_minute_policy": "exclude_outside_known_schedule_and_mark_day_ineligible",
        "zero_volume_policy": "retain_and_flag",
        "source_price_basis": "source_as_stored_price_momentum",
        "calendar_scope": "observed_dates_only_not_certified_exchange_calendar",
    }
    for key, expected in supported.items():
        if config[key] != expected:
            raise ValueError(f"Unsupported policy {key}: {config[key]}")
    for key in ("before_sessions", "after_sessions"):
        n = config["corporate_actions"][key]
        if type(n) is not int or n < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    for key in ("output_dir", "report_dir", "session_overrides_file",
                "conventional_action_evidence_file", "phase1_evidence_file"):
        local_path(project, config[key])
    for key in ("output_dir", "report_dir"):
        target = local_path(project, config[key])
        if any(target.is_relative_to(Path(root).resolve()) for root in config["sources"].values()):
            raise ValueError("Output overlaps an upstream source")
    return config


def source_paths(config: dict) -> list[tuple[str, Path]]:
    result = []
    for kind, root_string in sorted(config["sources"].items()):
        root = Path(root_string)
        pattern = "symbol=*/year=*/candles.parquet" if kind == "ohlcv" else "*.csv"
        paths = sorted(root.glob(pattern))
        if not paths:
            raise ValueError(f"No source files: {root}")
        if kind == "ohlcv" and set(root.rglob("*.parquet")) != set(paths):
            raise ValueError("Unexpected Parquet layout")
        result.extend((kind, path) for path in paths)
    return result


def fingerprint(kind: str, path: Path) -> dict:
    before = path.stat()
    result = {"kind": kind, "path": str(path.resolve()), "size_bytes": before.st_size,
              "mtime_ns": before.st_mtime_ns, "sha256": sha256(path)}
    if kind == "ohlcv":
        result["rows"] = pq.ParquetFile(path).metadata.num_rows
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"Source changed while fingerprinting: {path}")
    return result


def make_manifest(project: Path, config_path: Path, config: dict, symbols: list[str]) -> dict:
    files = [fingerprint(kind, path) for kind, path in source_paths(config)]
    code_paths = sorted(set(project.glob("src/**/*.py")) | set(project.glob("scripts/*.py"))
                        | set(project.glob("tests/*.py")) | {project / "pyproject.toml", project / "requirements.lock"})
    evidence_paths = [local_path(project, config[key]) for key in
                      ("session_overrides_file", "conventional_action_evidence_file", "phase1_evidence_file")]
    code = [{"path": str(p.relative_to(project)), "sha256": sha256(p)} for p in code_paths]
    evidence = [{"path": str(p.relative_to(project)), "sha256": sha256(p)} for p in evidence_paths]
    payload = {"manifest_version": 1, "sources": config["sources"], "files": files,
               "universe_symbols": symbols, "policy": config, "config_text": config_path.read_text(),
               "code_files": code, "evidence_files": evidence,
               "code_version": "0.2.0", "code_sha256": hashlib.sha256(canonical_json(code).encode()).hexdigest(),
               "runtime": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                            for name in ("pandas", "pyarrow", "numpy", "PyYAML")}}}
    payload["build_id"] = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    payload["build_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    return payload


def verify_sources(manifest: dict) -> None:
    actual = source_paths({"sources": manifest["sources"]})
    expected = {(f["kind"], f["path"]) for f in manifest["files"]}
    if {(kind, str(path.resolve())) for kind, path in actual} != expected:
        raise RuntimeError("Source file set changed")
    for record in manifest["files"]:
        if fingerprint(record["kind"], Path(record["path"])) != record:
            raise RuntimeError(f"Source changed: {record['path']}")


def save_manifest(output: Path, manifest: dict) -> dict:
    """Never overwrite a versioned manifest; reuse timestamp for identical build IDs."""
    directory = output / "manifests"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest['build_id']}.json"
    if path.exists():
        previous = json.loads(path.read_text())
        if {k: v for k, v in previous.items() if k != "build_timestamp_utc"} != {
            k: v for k, v in manifest.items() if k != "build_timestamp_utc"
        }:
            raise RuntimeError("Immutable manifest collision")
        return previous
    with path.open("x") as stream:
        stream.write(canonical_json(manifest))
    return manifest
