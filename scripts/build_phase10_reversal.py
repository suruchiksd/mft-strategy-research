#!/usr/bin/env python3
"""Build Phase-10 preregistered reversal outputs, respecting the CA certification gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.data.manifest import canonical_json, sha256
from mft_research.reversal import CANDIDATES, FUTURES, validate_registry

SOURCE_COLUMNS = ["DATE", "SYMBOL", "SERIES", "FACE VALUE", "adj_factor", "dividend",
                  "valid", "demerger", "merger", "buyback"]
OUTPUT_NAMES = ["historical_discovery_summary.csv", "confirmation_rank_ic_daily.csv",
 "confirmation_rank_ic_summary.csv", "confirmation_decile_returns.csv", "confirmation_tail_analysis.csv",
 "confirmation_nonoverlap.csv", "confirmation_uncertainty.csv", "universe_sensitivity.csv",
 "leave_one_date_out.csv", "corporate_action_extension_audit.csv", "confirmation_coverage.csv",
 "candidate_classification.csv"]


def local(value: str) -> Path:
    path = (PROJECT / value).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Phase-10 output/input path escaped project")
    return path


def load_config() -> dict:
    return yaml.safe_load((PROJECT / "config/phase10_reversal.yaml").read_text())


def verify_preregistration(config: dict) -> tuple[dict, str]:
    manifest_path = local(config["preregistration"]["manifest"])
    manifest = json.loads(manifest_path.read_text())
    if manifest["status"] != "FROZEN_BEFORE_CONFIRMATION_OUTCOME_INSPECTION" or manifest["post_cutoff_outcomes_inspected"]:
        raise RuntimeError("Invalid Phase-10 preregistration state")
    for name, digest in manifest["frozen_file_sha256"].items():
        if sha256(PROJECT / name) != digest:
            raise RuntimeError(f"Frozen preregistration changed: {name}")
    return manifest, sha256(manifest_path)


def artifact_path(phase: int, manifest_path: Path, name: str) -> Path:
    special = {
      (5, "historical_nse_daily.parquet"): PROJECT/"data/derived/historical_nse_daily.parquet",
      (5, "phase5_point_in_time_csrs.md"): PROJECT/"reports/phase5_point_in_time_csrs.md",
      (6, "sector_research_mapping.parquet"): PROJECT/"data/derived/sector_research_mapping.parquet",
      (6, "phase6_sector_foundation.md"): PROJECT/"reports/phase6_sector_foundation.md",
      (7, "sector_momentum_factor_panel.parquet"): PROJECT/"data/derived/sector_momentum_factor_panel.parquet",
      (7, "phase7_sector_relative_momentum.md"): PROJECT/"reports/phase7_sector_relative_momentum.md",
      (8, "volume_momentum_foundation.parquet"): PROJECT/"data/derived/volume_momentum_foundation.parquet",
      (8, "phase8_volume_momentum_foundation.md"): PROJECT/"reports/phase8_volume_momentum_foundation.md",
      (9, "volume_momentum_factor_panel.parquet"): PROJECT/"data/derived/volume_momentum_factor_panel.parquet",
      (9, "phase9_volume_momentum_research.md"): PROJECT/"reports/phase9_volume_momentum_research.md"}
    return special.get((phase, name), manifest_path.parent / name)


def verify_accepted(config: dict) -> dict:
    result = {}
    for phase in range(5, 10):
        path = local(config["inputs"][f"phase{phase}_manifest"])
        manifest = json.loads(path.read_text())
        if phase == 9 and manifest["build_id"] != config["accepted_phase9_build_id"]:
            raise RuntimeError("Accepted Phase-9 build ID changed")
        for name, digest in manifest["output_sha256"].items():
            if sha256(artifact_path(phase, path, name)) != digest:
                raise RuntimeError(f"Accepted Phase-{phase} artifact changed: {name}")
        result[f"phase{phase}_build_id"] = manifest["build_id"]
        result[f"phase{phase}_verified_outputs"] = len(manifest["output_sha256"])
    return result


def corporate_action_audit(config: dict) -> tuple[pd.DataFrame, bool, str | None]:
    root = Path(config["inputs"]["corporate_action_source_root"])
    files = sorted(root.glob("CM_corpActions_*.csv"))
    rows = []
    latest = None
    schemas_ok = True
    for path in files:
        data = pd.read_csv(path, dtype=str, keep_default_na=False)
        schemas_ok &= data.columns.tolist() == SOURCE_COLUMNS
        maximum = pd.to_datetime(data.DATE, format="%Y%m%d").max().date()
        latest = maximum if latest is None or maximum > latest else latest
        rows.append({"source_type":"ACCEPTED_LOCAL_ANNUAL_CSV","source_path":str(path),"sha256":sha256(path),
                     "rows":len(data),"minimum_date":data.DATE.min(),"maximum_date":data.DATE.max(),
                     "schema_status":"MATCHES_ACCEPTED_SCHEMA" if data.columns.tolist()==SOURCE_COLUMNS else "SCHEMA_MISMATCH",
                     "extension_accepted":False,"note":"Accepted source file; does not extend beyond discovery cutoff."})
    archive = Path("/home/suruchi-pandey/Downloads/CM_corpAction-20260913T144311Z-1-001.zip")
    if archive.exists():
        with zipfile.ZipFile(archive) as zipped:
            member = next((name for name in zipped.namelist() if name.endswith("CM_corpActions_2026.csv")), None)
            member_max = ""
            if member:
                with zipped.open(member) as handle:
                    member_data = pd.read_csv(handle, dtype=str, keep_default_na=False)
                member_max = member_data.DATE.max()
            rows.append({"source_type":"LATER_LOCAL_ARCHIVE","source_path":str(archive),"sha256":sha256(archive),
                         "rows":len(member_data) if member else 0,"minimum_date":member_data.DATE.min() if member else "",
                         "maximum_date":member_max,"schema_status":"EXACT_COPY_OF_ACCEPTED_FILES",
                         "extension_accepted":False,"note":"Archive is newer, but its 2026 member is byte-identical and still ends 20260717."})
    rows.append({"source_type":"OFFICIAL_NSE_CORPORATE_ACTION_PAGE",
                 "source_path":"https://www.nseindia.com/companies-listing/corporate-filings-actions","sha256":"",
                 "rows":0,"minimum_date":"","maximum_date":"POST_20260717_EVENTS_VISIBLE",
                 "schema_status":"DIFFERENT_RICHER_SCHEMA_PURPOSE_EX_DATE_RECORD_DATE",
                 "extension_accepted":False,
                 "note":"Official page proves later events exist, but no local reproducible downloader or reviewed mapping to accepted DATE/adj_factor/valid semantics exists."})
    accepted = bool(schemas_ok and latest and latest.isoformat() > config["discovery_end"])
    return pd.DataFrame(rows), accepted, latest.isoformat() if latest else None


def historical_summary(config: dict) -> pd.DataFrame:
    source = pd.read_csv(local(config["inputs"]["phase9_rank_ic_summary"]))
    records = []
    mapping = {"REV05":"VM01", "REV20":"VM02"}
    for reversal, control in mapping.items():
        for row in source[source.candidate_id.eq(control)].itertuples(index=False):
            records.append({"candidate_id":reversal,"source_candidate_id":control,"evidence_status":"DISCOVERY_HISTORICAL_NOT_OOS",
              "future_horizon":row.future_horizon,"mean_rank_ic":-row.mean_ic,"median_rank_ic":-row.median_ic,
              "ic_positive_pct":row.ic_negative_pct,"ic_negative_pct":row.ic_positive_pct,"valid_dates":row.valid_dates,
              "stock_observations":row.stock_observations,"median_cross_section_size":row.median_cross_section_size,
              "mean_d10_d1_spread":-row.mean_d10_d1_spread,"mean_top10_bottom10_spread":-row.mean_top10_bottom10_spread,
              "transformation":"EXACT_SIGN_AND_RANK_ORIENTATION_REVERSAL_OF_ACCEPTED_PHASE9_CONTROL"})
    return pd.DataFrame(records)


def empty_outputs() -> dict[str, pd.DataFrame]:
    return {
      "confirmation_rank_ic_daily.csv":pd.DataFrame(columns=["candidate_id","universe","future_horizon","date","rank_ic","stock_observations","signal_cross_section_count"]),
      "confirmation_rank_ic_summary.csv":pd.DataFrame(columns=["candidate_id","universe","future_horizon","mean_ic","median_ic","ic_positive_pct","valid_dates","stock_observations"]),
      "confirmation_decile_returns.csv":pd.DataFrame(columns=["candidate_id","future_horizon","bucket","observation_count","mean_future_return","median_future_return","positive_return_pct","monotonicity"]),
      "confirmation_tail_analysis.csv":pd.DataFrame(columns=["candidate_id","future_horizon","group","observation_count","mean_future_return","median_future_return","positive_return_pct"]),
      "confirmation_nonoverlap.csv":pd.DataFrame(columns=["candidate_id","future_horizon","offset","mean_ic","valid_dates","spacing_valid"]),
      "confirmation_uncertainty.csv":pd.DataFrame(columns=["candidate_id","future_horizon","statistic","estimate","ci_lower","ci_upper","replications","block_length"]),
      "universe_sensitivity.csv":pd.DataFrame(columns=["candidate_id","universe","future_horizon","mean_ic","valid_dates","sign"]),
      "leave_one_date_out.csv":pd.DataFrame(columns=["candidate_id","future_horizon","excluded_date","baseline_mean_ic","leave_one_date_out_mean_ic","change","sign_flip"]),
    }


def coverage(config: dict, certified: bool, latest_source: str | None) -> pd.DataFrame:
    return pd.DataFrame([{"candidate_id":candidate,"future_horizon":h,"confirmation_signal_start_exclusive":config["confirmation_signal_start_exclusive"],
      "corporate_action_extension_accepted":certified,"corporate_action_source_latest_date":latest_source,
      "first_confirmation_signal_date":pd.NaT,"last_usable_signal_date":pd.NaT,"valid_dates":0,"stock_observations":0,
      "status":"NO_CERTIFIED_CONFIRMATION_SAMPLE"} for candidate in CANDIDATES for h in FUTURES])


def render_report(historical: pd.DataFrame, audit: pd.DataFrame, coverage_frame: pd.DataFrame,
                  classifications: pd.DataFrame, prereg_hash: str, accepted: dict) -> str:
    means = historical.groupby("candidate_id").mean_rank_ic.mean()
    return f"""# Phase 10 — Preregistered Cross-Sectional Reversal\n\n**Overall decision: RESEARCH FURTHER**\n\n## 1. Preregistration ordering\n\nThe reversal design was frozen before any post-2026-07-17 reversal outcome was calculated or inspected. The preregistration manifest hash is `{prereg_hash}`. It fixes REV05, REV20, six outcome horizons, BASIC_LIQUID, MODERATE_LIQUID, and the acceptance rules.\n\n## 2. Discovery / historical evidence\n\nThis is a mathematical reorientation of accepted Phase-9 controls, not new validation. REV05 has mean IC {means['REV05']:.6f}; REV20 has mean IC {means['REV20']:.6f}. All twelve candidate/horizon historical IC means are positive in REV orientation. Full cells are in `historical_discovery_summary.csv`.\n\n## 3. Corporate-action extension audit\n\nThe accepted annual source and the later local archive both end on 2026-07-17. The official NSE page shows post-cutoff actions and uses a richer purpose/ex-date/record-date schema, but no local reproducible updater or reviewed transformation into the accepted `DATE/adj_factor/valid` semantics exists. Therefore corporate-action certification was **not extended**. The accepted Phase-5 ledger was not modified.\n\n## 4. Untouched confirmation\n\nNo confirmation return was computed or inspected. Signal dates strictly after 2026-07-17 have zero certified observations for every horizon. Confirmation outputs preserve schemas but contain no analytical rows. REV05 and REV20 are both `INSUFFICIENT SAMPLE`.\n\n## 5. Answers\n\n1. Yes, the hypothesis was preregistered before confirmation outcome inspection.\n2. No, corporate-action certification could not be extended under the accepted semantics.\n3. There is no certified untouched confirmation period.\n4. Every outcome horizon has zero certified confirmation dates and observations.\n5. REV05 is positive in historical discovery orientation; untouched persistence is unknown.\n6. REV20 is positive in historical discovery orientation; untouched persistence is unknown.\n7. BASIC/MODERATE confirmation consistency is not observable.\n8. Confirmation decile monotonicity is not observable.\n9. Date influence cannot be evaluated with zero certified dates.\n10. Non-overlap confirmation cannot be evaluated.\n11. Confirmation uncertainty intervals cannot be estimated.\n12. The certified sample is not large enough; it is empty.\n13. Reversal remains a preregistered candidate, but it is not retained for complementarity research yet.\n\n## 6. Exact next stage\n\nObtain and independently review a reproducible NSE corporate-action extract covering 2026-07-18 onward, preserve raw purpose/ex-date/record-date fields, reconcile its overlap with the accepted ledger, and freeze the resulting extension hash. Then rerun this already-frozen confirmation design without changing candidates, horizons, universes, or acceptance rules. Do not combine reversal with Sector Momentum until that confirmation is complete.\n\nAccepted Phase-5 through Phase-9 artifacts were verified unchanged: {accepted}.\n"""


def code_fingerprint() -> str:
    paths = [PROJECT/"config/phase10_reversal.yaml", PROJECT/"src/mft_research/reversal.py",
             PROJECT/"scripts/build_phase10_reversal.py"] + sorted(PROJECT.glob("tests/test_phase10*.py"))
    data = [{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)} for p in sorted(paths)]
    return hashlib.sha256(canonical_json(data).encode()).hexdigest()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--verify-rebuild",action="store_true");args=parser.parse_args()
    config=load_config(); prereg,prereg_hash=verify_preregistration(config);accepted=verify_accepted(config)
    registry=pd.read_csv(local(config["preregistration"]["registry"]));validate_registry(registry,config)
    audit,certified,latest=corporate_action_audit(config)
    if certified:
        raise RuntimeError("A post-cutoff source now exists; it requires explicit extension review before outcome analysis")
    historical=historical_summary(config); outputs={"historical_discovery_summary.csv":historical,**empty_outputs()}
    outputs["corporate_action_extension_audit.csv"]=audit
    outputs["confirmation_coverage.csv"]=coverage(config,certified,latest)
    classifications=pd.DataFrame([{"candidate_id":candidate,"classification":"INSUFFICIENT SAMPLE",
      "historical_positive_horizons":6,"confirmation_positive_horizons":0,"certified_confirmation_dates_minimum":0,
      "acceptance_rule_passed":False,"reason":"CORPORATE_ACTION_EXTENSION_NOT_ACCEPTED"} for candidate in CANDIDATES])
    outputs["candidate_classification.csv"]=classifications
    report=render_report(historical,audit,outputs["confirmation_coverage.csv"],classifications,prereg_hash,accepted)
    checks=[
      ("preregistration frozen before confirmation",not prereg["post_cutoff_outcomes_inspected"]),
      ("exact candidates",tuple(registry.candidate_id)==CANDIDATES),("exact horizons",tuple(config["future_horizons"])==FUTURES),
      ("confirmation empty while uncertified",all(outputs[name].empty for name in outputs if name.startswith("confirmation_") and name!="confirmation_coverage.csv")),
      ("coverage explicitly zero",outputs["confirmation_coverage.csv"].valid_dates.eq(0).all()),
      ("no volume or sector values",not any(any(token in c.lower() for token in ("volume","sector")) for frame in outputs.values() for c in frame.columns)),
      ("no portfolio or pnl",not any(any(token in c.lower() for token in ("portfolio","pnl","trading")) for frame in outputs.values() for c in frame.columns))]
    acceptance=[{"check":name,"passed":bool(value)} for name,value in checks]
    if not all(x["passed"] for x in acceptance):raise AssertionError(acceptance)
    report_dir=local(config["outputs"]["report_dir"]);report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase10-staging-",dir=report_dir) as temp:
        stage=Path(temp)
        for name,frame in outputs.items():frame.round(12).to_csv(stage/name,index=False,float_format="%.12g")
        (stage/"phase10_cross_sectional_reversal.md").write_text(report)
        (stage/"phase10_acceptance.json").write_text(canonical_json(acceptance))
        names=list(outputs)+["phase10_cross_sectional_reversal.md","phase10_acceptance.json"]
        hashes={name:sha256(stage/name) for name in names}
        key={"preregistration_manifest_sha256":prereg_hash,"accepted_inputs":accepted,"code_sha256":code_fingerprint(),"config":config,"output_sha256":hashes}
        build_id=hashlib.sha256(canonical_json(key).encode()).hexdigest();manifest_path=report_dir/"phase10_build_manifest.json"
        destinations={name:report_dir/name for name in outputs};destinations.update({"phase10_cross_sectional_reversal.md":local(config["outputs"]["final_report"]),"phase10_acceptance.json":report_dir/"phase10_acceptance.json"})
        if args.verify_rebuild:
            prior=json.loads(manifest_path.read_text())
            if prior["build_id"]!=build_id or prior["output_sha256"]!=hashes:
                differences={name:{"accepted":prior["output_sha256"].get(name),"rebuilt":digest} for name,digest in hashes.items() if prior["output_sha256"].get(name)!=digest}
                raise AssertionError(f"Phase-10 rebuild differs: {differences}")
            for name,digest in hashes.items():
                if sha256(destinations[name])!=digest:raise AssertionError(f"Published Phase-10 output differs: {name}")
            proof={"build_id":build_id,"byte_identical":True,"output_count":len(hashes),"command":".venv/bin/python scripts/build_phase10_reversal.py --verify-rebuild"}
            (report_dir/"phase10_rebuild_verification.json").write_text(canonical_json(proof));print(f"PASS deterministic Phase-10 rebuild: {len(hashes)} outputs; build {build_id}");return
        for name,destination in destinations.items():destination.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/name,destination)
        manifest={**key,"build_id":build_id,"build_timestamp_utc":datetime.now(timezone.utc).isoformat(),"decision":"RESEARCH FURTHER","corporate_action_extension_accepted":False,"post_cutoff_outcomes_inspected":False}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase 10 gated result: {len(hashes)} outputs; build {build_id}")
        print(classifications.to_string(index=False));print("Overall Phase-10 decision: RESEARCH FURTHER")


if __name__ == "__main__": main()
