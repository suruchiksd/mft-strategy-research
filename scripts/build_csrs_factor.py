#!/usr/bin/env python3
"""Build independent CSRS horizons and descriptive outcome analyses from accepted Phase 2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.csrs import FORMATION_HORIZONS, FUTURE_HORIZONS
from mft_research.csrs.analysis import (combine_horizon_summary, coverage_tables,
    cross_section_distribution, quantile_analysis, rank_ic, side_analysis, yearly_analysis)
from mft_research.csrs.factor import add_cross_sectional_ranks
from mft_research.csrs.intervals import build_interval_panel
from mft_research.csrs.plots import make_plots
from mft_research.csrs.validation import assert_acceptance, validate_factor_panel
from mft_research.data.manifest import canonical_json, sha256


def load_local(path: str) -> Path:
    result = (PROJECT / path).resolve()
    if not result.is_relative_to(PROJECT):
        raise ValueError("Phase-3 paths must remain inside the project")
    return result


def load_config() -> dict:
    config = yaml.safe_load((PROJECT / "config/csrs_research.yaml").read_text())
    if tuple(config["formation_horizons"]) != FORMATION_HORIZONS:
        raise ValueError("Formation horizons differ from locked Phase-3 policy")
    if tuple(config["future_horizons"]) != FUTURE_HORIZONS:
        raise ValueError("Future horizons differ from locked Phase-3 policy")
    if set(config["blocking_action_classes"]) != {"MATERIAL_UNRESOLVED_EVENT", "UNKNOWN_OR_AMBIGUOUS"}:
        raise ValueError("Blocking action classes differ from locked policy")
    return config


def verify_phase2(config: dict) -> dict:
    accepted = json.loads(load_local(config["phase2_acceptance_path"]).read_text())
    manifest = json.loads(load_local(config["phase2_manifest_path"]).read_text())
    if accepted["build_id"] != config["phase2_build_id"] or manifest["build_id"] != config["phase2_build_id"]:
        raise RuntimeError("Accepted Phase-2 build ID mismatch")
    if not accepted.get("deterministic_rebuild_verified") or set(accepted["checks"].values()) != {"PASS"}:
        raise RuntimeError("Phase-2 acceptance is not fully passing")
    for key in ("daily_bars_path", "corporate_action_ledger_path", "session_calendar_path"):
        path = load_local(config[key])
        expected = manifest["artifact_sha256"][path.name]
        if sha256(path) != expected:
            raise RuntimeError(f"Accepted Phase-2 artifact changed: {path}")
    return manifest


def code_fingerprint() -> str:
    paths = sorted(PROJECT.glob("src/mft_research/csrs/*.py")) + [PROJECT / "scripts/build_csrs_factor.py",
            PROJECT / "config/csrs_research.yaml"] + sorted(PROJECT.glob("tests/test_csrs*.py"))
    records = [{"path": str(p.relative_to(PROJECT)), "sha256": sha256(p)} for p in paths]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def build(config: dict):
    daily = pq.ParquetFile(load_local(config["daily_bars_path"])).read().to_pandas()
    ledger = pq.ParquetFile(load_local(config["corporate_action_ledger_path"])).read().to_pandas()
    calendar = pq.ParquetFile(load_local(config["session_calendar_path"])).read().to_pandas()
    panel = build_interval_panel(daily, ledger, calendar, FORMATION_HORIZONS, FUTURE_HORIZONS,
                                 date.fromisoformat(config["corporate_action_coverage_end"]))
    panel = add_cross_sectional_ranks(panel, FORMATION_HORIZONS)
    acceptance = validate_factor_panel(panel, FORMATION_HORIZONS, FUTURE_HORIZONS,
                                       config["corporate_action_coverage_end"])
    assert_acceptance(acceptance)
    ic_daily, ic_summary = rank_ic(panel, FORMATION_HORIZONS, FUTURE_HORIZONS,
                                   config["minimum_cross_section_for_rank_ic"])
    quantiles, quantile_summary = quantile_analysis(panel, FORMATION_HORIZONS, FUTURE_HORIZONS,
                                                     config["minimum_cross_section_for_deciles"])
    horizon = combine_horizon_summary(ic_summary, quantile_summary)
    sides = side_analysis(panel, FORMATION_HORIZONS, FUTURE_HORIZONS)
    yearly = yearly_analysis(panel, ic_daily, FORMATION_HORIZONS, FUTURE_HORIZONS,
                             config["minimum_cross_section_for_deciles"])
    eligibility, reasons, focus = coverage_tables(panel, FORMATION_HORIZONS, FUTURE_HORIZONS,
                                                   ("TMCV", "TATACAP", "HYUNDAI", "JIOFIN", "MANKIND"))
    cross_sections = cross_section_distribution(panel, FORMATION_HORIZONS)
    coverage = pd.concat([reasons.assign(scope="ALL_SYMBOLS"),
                          focus.rename(columns={"symbol": "reason"}).assign(scope="FOCUS_SYMBOL")],
                         ignore_index=True, sort=False)
    return panel, acceptance, {"interval_eligibility_summary.csv": eligibility,
                   "coverage_analysis.csv": coverage,
                   "cross_section_size.csv": cross_sections,
                   "horizon_summary.csv": horizon,
                   "quantile_returns.csv": quantiles,
                   "rank_ic_daily.csv": ic_daily,
                   "rank_ic_summary.csv": ic_summary,
                   "signal_decay.csv": horizon[["formation_horizon", "future_horizon", "mean_ic",
                                                "top_decile_mean_return", "bottom_decile_mean_return",
                                                "top_bottom_spread"]],
                   "side_analysis.csv": sides,
                   "yearly_analysis.csv": yearly}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    config = load_config()
    phase2 = verify_phase2(config)
    panel, acceptance, reports = build(config)
    panel_path, report_dir = load_local(config["factor_panel_path"]), load_local(config["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".csrs-staging-", dir=PROJECT / "data/derived") as temp:
        staged = Path(temp) / panel_path.name
        panel.to_parquet(staged, index=False, compression="zstd", engine="pyarrow")
        digest = sha256(staged)
        build_key = {"phase2_build_id": phase2["build_id"], "phase2_artifact_sha256": {
            name: phase2["artifact_sha256"][name] for name in ("daily_bars.parquet", "corporate_action_ledger.parquet", "session_calendar.parquet")},
            "config": config, "code_sha256": code_fingerprint(), "panel_sha256": digest}
        build_id = hashlib.sha256(canonical_json(build_key).encode()).hexdigest()
        manifest_path = report_dir / "csrs_build_manifest.json"
        if args.verify_rebuild:
            prior = json.loads(manifest_path.read_text())
            if prior["build_id"] != build_id or prior["panel_sha256"] != digest or sha256(panel_path) != digest:
                raise AssertionError("CSRS factor rebuild is not byte-identical")
            for name, frame in reports.items():
                expected = prior["report_sha256"][name]
                candidate = Path(temp) / name
                frame.to_csv(candidate, index=False, float_format="%.12g")
                if sha256(candidate) != expected or sha256(report_dir / name) != expected:
                    raise AssertionError(f"CSRS report rebuild differs: {name}")
            (report_dir / "csrs_rebuild_verification.json").write_text(canonical_json({
                "build_id": build_id, "panel_sha256": digest, "byte_identical": True,
                "reports_byte_identical": True,
                "command": ".venv/bin/python scripts/build_csrs_factor.py --verify-rebuild"}))
            print(f"PASS deterministic CSRS rebuild: {len(panel):,} panel rows; build {build_id}")
            return
        os.replace(staged, panel_path)
        for name, frame in reports.items():
            frame.to_csv(report_dir / name, index=False, float_format="%.12g")
        (report_dir / "factor_panel_acceptance.json").write_text(
            json.dumps(acceptance, indent=2) + "\n", encoding="utf-8")
        make_plots(report_dir, reports["horizon_summary.csv"], reports["quantile_returns.csv"],
                   reports["yearly_analysis.csv"])
        manifest = {**build_key, "build_id": build_id,
                    "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "report_sha256": {name: sha256(report_dir / name) for name in reports},
                    "panel_rows": len(panel), "research_scope": config["research_scope"]}
        manifest_path.write_text(canonical_json(manifest))
        valid = {h: int(panel[f"valid_ret_{h}"].sum()) for h in FORMATION_HORIZONS}
        print(f"Built CSRS panel: {len(panel):,} rows; valid formations {valid}; build {build_id}")


if __name__ == "__main__":
    main()
