#!/usr/bin/env python3
"""Run the frozen Phase-10 reversal confirmation after the accepted CA gate."""

from __future__ import annotations

import argparse, hashlib, importlib.util, json, os, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/"src"))
from mft_research.data.manifest import canonical_json,sha256
from mft_research.reversal import CANDIDATES,FUTURES
from mft_research.reversal_confirmation import analyze,build_panel,classify


def local(value):
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT):raise ValueError("Path escaped project")
    return path


def load_config():return yaml.safe_load((PROJECT/"config/phase10_reversal_confirmation.yaml").read_text())


def _module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def verify_inputs(c):
    prereg=local(c["inputs"]["preregistration_manifest"])
    if sha256(prereg)!=c["preregistration_sha256"]:raise RuntimeError("Preregistration hash changed")
    prereg_data=json.loads(prereg.read_text())
    if prereg_data["post_cutoff_outcomes_inspected"] is not False:raise RuntimeError("Preregistration ordering invalid")
    extension_path=local(c["inputs"]["extension_manifest"]);extension=json.loads(extension_path.read_text())
    acceptance=json.loads(local(c["inputs"]["extension_acceptance"]).read_text())
    if extension["build_id"]!=c["extension_build_id"]:raise RuntimeError("CA extension build changed")
    if acceptance["decision"] not in ("PASS FOR REVERSAL CONFIRMATION","CONDITIONAL PASS FOR REVERSAL CONFIRMATION"):raise RuntimeError("CA extension not accepted")
    # The accepted Phase-10 verifier supplies the established Phase-5..9 path mapping.
    old=_module(PROJECT/"scripts/build_phase10_reversal.py","accepted_phase10_verifier")
    accepted=old.verify_accepted(old.load_config())
    gated_path=local(c["inputs"]["gated_phase10_manifest"]);gated=json.loads(gated_path.read_text())
    for name,digest in gated["output_sha256"].items():
        path=(PROJECT/"reports/phase10_cross_sectional_reversal.md" if name=="phase10_cross_sectional_reversal.md" else gated_path.parent/name)
        if sha256(path)!=digest:raise RuntimeError(f"Gated Phase-10 artifact changed: {name}")
    ext_special={"phase10_corporate_action_extension.parquet":PROJECT/"data/derived/phase10_corporate_action_extension.parquet",
                 "phase10_corporate_action_extension.md":PROJECT/"reports/phase10_corporate_action_extension.md"}
    for name,digest in extension["output_sha256"].items():
        path=ext_special.get(name,extension_path.parent/name)
        if sha256(path)!=digest:raise RuntimeError(f"CA extension artifact changed: {name}")
    return {**accepted,"preregistration_sha256":sha256(prereg),"gated_phase10_build_id":gated["build_id"],
            "extension_build_id":extension["build_id"],"extension_verified_outputs":len(extension["output_sha256"])}


def code_hash():
    paths=[PROJECT/"config/phase10_reversal_confirmation.yaml",PROJECT/"src/mft_research/reversal_confirmation.py",
           PROJECT/"scripts/build_phase10_reversal_confirmation.py"]+sorted(PROJECT.glob("tests/test_phase10_confirmation*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)} for p in sorted(paths)]).encode()).hexdigest()


def render_report(outputs,classification,overall,c,build_id):
    s=outputs["confirmation_rank_ic_summary.csv"];cov=outputs["confirmation_coverage.csv"]
    primary=s[s.universe.eq("BASIC_LIQUID")];moderate=s[s.universe.eq("MODERATE_LIQUID")]
    unc=outputs["confirmation_uncertainty.csv"].query("statistic == 'MEAN_RANK_IC'")
    non=outputs["confirmation_nonoverlap.csv"].drop_duplicates(["candidate_id","future_horizon"])
    def row(candidate):
        p=primary[primary.candidate_id.eq(candidate)];m=moderate[moderate.candidate_id.eq(candidate)];u=unc[unc.candidate_id.eq(candidate)];n=non[non.candidate_id.eq(candidate)]
        return (f"- **{candidate}**: mean IC across horizons {p.mean_ic.mean():.6f}; positive primary {p.mean_ic.gt(0).sum()}/6; "
                f"positive MODERATE {m.mean_ic.gt(0).sum()}/6; positive non-overlap means {n.offset_mean_ic.gt(0).sum()}/6; "
                f"95% IC intervals above zero {u.ci_lower.gt(0).sum()}/6; classification **{classification.set_index('candidate_id').loc[candidate,'classification']}**.")
    ranges=cov[cov.universe.eq("BASIC_LIQUID")][["candidate_id","future_horizon","first_confirmation_signal_date","last_usable_signal_date","valid_dates","stock_observations"]]
    def markdown(frame):
        values=[["" if pd.isna(value) else str(value) for value in row]
                for row in frame.itertuples(index=False,name=None)]
        return "\n".join(["| "+" | ".join(frame.columns)+" |",
                           "| "+" | ".join(["---"]*len(frame.columns))+" |"]+
                          ["| "+" | ".join(row)+" |" for row in values])
    table=markdown(ranges)
    ext=json.loads((PROJECT/"reports/reversal/corporate_action_extension/extension_acceptance.json").read_text())
    return f"""# Phase 10B — Preregistered Cross-Sectional Reversal Confirmation

**Overall Phase-10 decision: {overall}**

This report separates historical discovery evidence from the untouched post-2026-07-17 confirmation. It remains factor research; no factor combination, trading rule, or portfolio was created.

## A. Corporate-action extension

The frozen official-NSE extension received **{ext['decision']}**. It preserves structured official responses through 2026-09-11, uses official ex-date as the blocking date, maps symbols exactly without fuzzy matching, and blocks splits, bonuses, rights, reorganizations, unknown purposes, and identifier conflicts. Overlap recovered {ext['accepted_blocking_exact_matches']}/{ext['accepted_blocking_rows']} accepted blocking events. GUJGASLTD was the sole false negative, and its price series ended before the missed event. Extension build `{c['extension_build_id']}` was frozen before this confirmation inspected outcomes.

## B. Discovery evidence

The accepted Phase-9 controls were reoriented mathematically before confirmation: REV05 and REV20 each had positive historical Rank IC at all six outcomes. These 2020-01-01 through 2026-07-17 results are discovery evidence, not out-of-sample evidence.

## C. Untouched confirmation coverage

Signal dates begin strictly after 2026-07-17. Every admitted outcome ends by the certified price/corporate-action boundary of 2026-09-11.

{table}

## D. Confirmation evidence

{row('REV05')}
{row('REV20')}

Complete deciles, tails, every non-overlap offset, deterministic circular-block intervals, universe sensitivity, and leave-one-date influence are in the companion CSVs. A factor rank is fixed from signal-valid stocks before outcome availability is applied.

## E. Interpretation

The preregistered evaluability floor is 20 daily IC dates for every horizon and the `SUPPORTED` threshold is 60. These thresholds were not changed. The classifications reflect direction, BASIC/MODERATE consistency, non-overlap results, and whether dropping one date flips a supporting sign. Confidence intervals are descriptive in this short untouched sample.

The exact next stage is to follow the frozen classification gate. If Phase 10 does not pass, collect more genuinely untouched certified dates under the same definitions. If it passes conditionally, a separately authorized complementarity study may test reversal alongside Sector Relative Momentum with its design frozen first. Phase 11 was not started.

Build ID: `{build_id}`.
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--verify-rebuild",action="store_true");args=parser.parse_args();c=load_config();accepted=verify_inputs(c)
    daily=pd.read_parquet(local(c["inputs"]["historical_daily"]));identity=pd.read_csv(local(c["inputs"]["historical_identity"]));historical_actions=pd.read_parquet(local(c["inputs"]["historical_actions"]));extension=pd.read_parquet(local(c["inputs"]["extension_actions"]))
    panel=build_panel(daily,identity,historical_actions,extension,c);del daily
    outputs,caches=analyze(panel,c);historical=pd.read_csv(local(c["inputs"]["historical_discovery"]));outputs["historical_discovery_summary.csv"]=historical
    classification,overall=classify(outputs,historical,c);outputs["candidate_classification.csv"]=classification
    if classification.classification.eq("PREREGISTRATION_RULE_GAP").any():
        affected=classification.loc[classification.classification.eq("PREREGISTRATION_RULE_GAP"),"candidate_id"].tolist()
        raise RuntimeError(
          "Frozen Phase-10 classification taxonomy is not exhaustive for observed evidence: "
          f"{affected} has >=4 positive primary horizons but fails another directional rule. "
          "The preregistration defines MIXED only for 2-3 positives and CONTRADICTORY only for 0-1; "
          "no accepted classification can be assigned without a post-outcome rule amendment.")
    checks={"preregistration immutable":sha256(local(c["inputs"]["preregistration_manifest"]))==c["preregistration_sha256"],
      "exact candidates":tuple(classification.candidate_id)==CANDIDATES,"exact futures":tuple(c["future_horizons"])==FUTURES,
      "signals strictly post cutoff":panel.date.min()>pd.Timestamp(c["confirmation_signal_start_exclusive"]).date(),
      "no uncertified valid endpoint":all(outputs["confirmation_coverage.csv"].last_usable_signal_date.notna()),
      "all offsets":all(set(g.offset)==set(range(h)) for (_,h),g in outputs["confirmation_nonoverlap.csv"].groupby(["candidate_id","future_horizon"])),
      "no forbidden columns":not any(any(x in col.lower() for x in ("volume","sector","portfolio","pnl","weight")) for col in panel.columns)}
    if not all(checks.values()):raise AssertionError(checks)
    acceptance=[{"check":k,"passed":bool(v)} for k,v in checks.items()]
    report_dir=local(c["outputs"]["report_dir"]);report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase10-confirmation-stage-",dir=report_dir) as tmp:
      stage=Path(tmp)
      for name,frame in outputs.items():frame.round(12).to_csv(stage/name,index=False,float_format="%.12g",date_format="%Y-%m-%d")
      panel.to_parquet(stage/"reversal_confirmation_panel.parquet",index=False,compression="zstd")
      (stage/"phase10_confirmation_acceptance.json").write_text(canonical_json(acceptance))
      preliminary={"accepted_inputs":accepted,"config":c,"code_sha256":code_hash(),"analytical_output_sha256":{name:sha256(stage/name) for name in outputs},
                   "panel_sha256":sha256(stage/"reversal_confirmation_panel.parquet"),"decision":overall}
      build_id=hashlib.sha256(canonical_json(preliminary).encode()).hexdigest()
      (stage/"phase10b_reversal_confirmation.md").write_text(render_report(outputs,classification,overall,c,build_id))
      names=list(outputs)+["reversal_confirmation_panel.parquet","phase10_confirmation_acceptance.json","phase10b_reversal_confirmation.md"]
      hashes={name:sha256(stage/name) for name in names}
      key={"accepted_inputs":accepted,"config":c,"code_sha256":code_hash(),"output_sha256":hashes,"decision":overall}
      final_id=hashlib.sha256(canonical_json(key).encode()).hexdigest()
      # The report records a stable analytical ID; the manifest ID additionally commits to the report bytes.
      manifest={**key,"build_id":final_id,"analytical_build_id":build_id,"post_cutoff_outcomes_inspected":True,
                "confirmation_signal_start_exclusive":c["confirmation_signal_start_exclusive"],"certified_end":c["certified_end"]}
      manifest_path=report_dir/"phase10_confirmation_manifest.json"
      destinations={name:report_dir/name for name in outputs};destinations.update({"reversal_confirmation_panel.parquet":local(c["outputs"]["factor_panel"]),
        "phase10_confirmation_acceptance.json":report_dir/"phase10_confirmation_acceptance.json","phase10b_reversal_confirmation.md":local(c["outputs"]["final_report"])})
      if args.verify_rebuild:
        prior=json.loads(manifest_path.read_text())
        if prior["build_id"]!=final_id or prior["output_sha256"]!=hashes:
          diff={n:{"accepted":prior["output_sha256"].get(n),"rebuilt":d} for n,d in hashes.items() if prior["output_sha256"].get(n)!=d};raise AssertionError(f"Confirmation rebuild differs: {diff}")
        for name,digest in hashes.items():
          if sha256(destinations[name])!=digest:raise AssertionError(f"Published confirmation differs: {name}")
        proof={"build_id":final_id,"byte_identical":True,"output_count":len(hashes)};(report_dir/"phase10_confirmation_rebuild_verification.json").write_text(canonical_json(proof));print(f"PASS confirmation rebuild: {len(hashes)} outputs; {final_id}");return
      for name,path in destinations.items():path.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/name,path)
      manifest["build_timestamp_utc"]=datetime.now(timezone.utc).isoformat();manifest_path.write_text(canonical_json(manifest))
      print(f"Built Phase-10 confirmation: {len(hashes)} outputs; {final_id}");print(classification.to_string(index=False));print(f"Overall Phase-10 decision: {overall}")


if __name__=="__main__":main()
