#!/usr/bin/env python3
"""Freeze the exhaustive post-outcome Phase-10 classification amendment."""

from __future__ import annotations

import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path

import pandas as pd
import yaml

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/"src"))
from mft_research.data.manifest import canonical_json,sha256
from mft_research.reversal_amendment import (CANDIDATE_CLASSES,OVERALL_DECISIONS,
    candidate_rule_table,enumerate_candidate_states,overall_decision_table)


def local(value):
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT):raise ValueError("Amendment path escaped project")
    return path


def config():return yaml.safe_load((PROJECT/"config/phase10_classification_amendment.yaml").read_text())


def verify_immutable(c):
    prereg=local(c["inputs"]["preregistration_manifest"]);candidate=local(c["inputs"]["candidate_registry"])
    blocker=local(c["inputs"]["blocker_report"]);extension_path=local(c["inputs"]["extension_manifest"])
    if sha256(prereg)!=c["original_preregistration_sha256"]:raise RuntimeError("Original preregistration changed")
    prereg_data=json.loads(prereg.read_text())
    if sha256(candidate)!=prereg_data["frozen_file_sha256"]["reports/reversal/preregistration/reversal_candidate_registry.csv"]:raise RuntimeError("Original candidate registry changed")
    extension=json.loads(extension_path.read_text())
    if extension["build_id"]!=c["corporate_action_extension_build_id"]:raise RuntimeError("Phase-10B extension changed")
    # Reuse the established accepted-artifact verifier for Phases 5-9.
    import importlib.util
    path=PROJECT/"scripts/build_phase10_reversal.py";spec=importlib.util.spec_from_file_location("phase10_accepted",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    prior=module.verify_accepted(module.load_config())
    gated_path=PROJECT/"reports/reversal/research/phase10_build_manifest.json";gated=json.loads(gated_path.read_text())
    for name,digest in gated["output_sha256"].items():
        path=PROJECT/"reports/phase10_cross_sectional_reversal.md" if name=="phase10_cross_sectional_reversal.md" else gated_path.parent/name
        if sha256(path)!=digest:raise RuntimeError(f"Accepted gated Phase-10 artifact changed: {name}")
    special={"phase10_corporate_action_extension.parquet":PROJECT/"data/derived/phase10_corporate_action_extension.parquet",
             "phase10_corporate_action_extension.md":PROJECT/"reports/phase10_corporate_action_extension.md"}
    for name,digest in extension["output_sha256"].items():
        if sha256(special.get(name,extension_path.parent/name))!=digest:raise RuntimeError(f"Accepted extension artifact changed: {name}")
    return {**prior,"original_preregistration_sha256":sha256(prereg),"candidate_registry_sha256":sha256(candidate),
      "blocker_report_sha256":sha256(blocker),"gated_phase10_build_id":gated["build_id"],
      "gated_phase10_verified_outputs":len(gated["output_sha256"]),"extension_build_id":extension["build_id"],
      "extension_verified_outputs":len(extension["output_sha256"])}


def code_hash():
    paths=[PROJECT/"config/phase10_classification_amendment.yaml",PROJECT/"src/mft_research/reversal_amendment.py",
      PROJECT/"scripts/build_phase10_classification_amendment.py"]+sorted(PROJECT.glob("tests/test_phase10_amendment*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)} for p in sorted(paths)]).encode()).hexdigest()


def report(c,states,overall,immutable):
    counts=states.classification.value_counts().to_dict();decisions=overall.overall_decision.value_counts().to_dict()
    return f"""# Phase 10 — Exhaustive Classification Amendment

> **POST-OUTCOME AMENDMENT**  
> **CREATED AFTER THE 2026-07-20 THROUGH 2026-09-11 CONFIRMATION WAS OBSERVED**  
> **CANNOT RETROACTIVELY CONVERT THAT SAMPLE INTO PRISTINE VALIDATION**

Created: {c['amendment_created_at_utc']}  
Original preregistration SHA256: `{c['original_preregistration_sha256']}`  
Blocker report SHA256: `{immutable['blocker_report_sha256']}`  
Corporate-action extension build: `{c['corporate_action_extension_build_id']}`

## Purpose and untouched boundary

This amendment closes the classification gap without changing REV05, REV20, their signs, universes, outcomes, ranks, interval safety, bootstrap, non-overlap sampling, or leave-one-date method. It applies only to new signals strictly after **2026-09-11**, after corporate-action and price coverage are independently extended to every admitted endpoint.

## Candidate hierarchy

Evaluation is ordered: `INSUFFICIENT SAMPLE`; `CONTRADICTORY`; `MIXED`; `DIRECTIONALLY POSITIVE BUT UNSTABLE`; `SUPPORTIVE BUT SHORT SAMPLE`; `SUPPORTED`. The complete executable conditions are in `phase10_complete_classification_table.csv`.

The full enumerated state space contains {len(states):,} states. Every state maps once to one class. Class counts are {counts}. The historical discovery requirement remains fixed at six positive REV-oriented horizons for these two candidates.

## Overall decisions

All {len(overall)} ordered candidate-class pairs map exactly once. Pair counts are {decisions}. Both `SUPPORTED` gives `PASS FOR COMPLEMENTARITY RESEARCH`; at least one `SUPPORTED`, or both `SUPPORTIVE BUT SHORT SAMPLE`, gives `CONDITIONAL PASS`; both `CONTRADICTORY` gives `FAIL`; all remaining pairs give `RESEARCH FURTHER`.

## Retrospective descriptive mapping

This is **RETROSPECTIVE DESCRIPTIVE MAPPING ONLY — NOT NEW VALIDATION — NOT ACCEPTED OOS CLASSIFICATION**.

- REV05: `DIRECTIONALLY POSITIVE BUT UNSTABLE` equivalent.
- REV20: `CONTRADICTORY` equivalent.
- Accepted overall Phase-10 decision remains `RESEARCH FURTHER`.

## Requirements for the next untouched rerun

Use only signals after 2026-09-11. First extend and freeze official corporate-action certification and price coverage for every endpoint. Then run exactly REV05/REV20 in BASIC_LIQUID with MODERATE_LIQUID sensitivity and outcomes 1/2/3/5/10/20. Preserve signal ranks before outcome availability, all non-overlap offsets, the fixed bootstrap, and leave-one-date influence. Apply this amended hierarchy without further changes. No Phase 11, factor combination, or portfolio research is authorized by this amendment.
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--verify-rebuild",action="store_true");args=parser.parse_args();c=config();immutable=verify_immutable(c)
    rules=candidate_rule_table();overall=overall_decision_table();states=enumerate_candidate_states()
    if len(states)!=7*7*7*2*2*2*3 or states.classification.isna().any() or not set(states.classification)==set(CANDIDATE_CLASSES):raise AssertionError("Candidate state enumeration incomplete")
    if len(overall)!=36 or overall.duplicated(["REV05_classification","REV20_classification"]).any() or set(overall.overall_decision)!=set(OVERALL_DECISIONS):raise AssertionError("Overall table incomplete")
    report_dir=local(c["outputs"]["report_dir"]);report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase10-amendment-stage-",dir=report_dir) as tmp:
      stage=Path(tmp);rules.to_csv(stage/"phase10_complete_classification_table.csv",index=False);overall.to_csv(stage/"phase10_overall_decision_table.csv",index=False)
      (stage/"phase10_classification_amendment.md").write_text(report(c,states,overall,immutable))
      names=["phase10_classification_amendment.md","phase10_complete_classification_table.csv","phase10_overall_decision_table.csv"]
      hashes={name:sha256(stage/name) for name in names}
      key={"status":c["status"],"amendment_created_at_utc":c["amendment_created_at_utc"],"new_confirmation_signal_start_exclusive":c["new_confirmation_signal_start_exclusive"],
        "original_preregistration_sha256":c["original_preregistration_sha256"],"immutable_inputs":immutable,"config":c,
        "code_sha256":code_hash(),"amended_rule_sha256":hashes,"enumerated_candidate_states":len(states),"overall_class_pairs":len(overall)}
      amendment_hash=hashlib.sha256(canonical_json(key).encode()).hexdigest();manifest={**key,"amendment_hash":amendment_hash,
        "observed_sample_status":"RULE_GAP_AMENDMENT_DEVELOPMENT_EVIDENCE","retrospective_mapping":{"REV05":"DIRECTIONALLY POSITIVE BUT UNSTABLE","REV20":"CONTRADICTORY"},
        "accepted_overall_phase10_decision":"RESEARCH FURTHER","new_data_inspected":False}
      (stage/"phase10_amendment_manifest.json").write_text(canonical_json(manifest));manifest_path=local(c["outputs"]["manifest"])
      destinations={name:report_dir/name for name in names}
      if args.verify_rebuild:
        prior=json.loads(manifest_path.read_text())
        if prior!=manifest:raise AssertionError("Phase-10 amendment rebuild differs")
        for name,digest in hashes.items():
          if sha256(destinations[name])!=digest:raise AssertionError(f"Published amendment differs: {name}")
        print(f"PASS deterministic amendment rebuild: {len(names)+1}/4 outputs; {amendment_hash}");return
      for name,path in destinations.items():os.replace(stage/name,path)
      os.replace(stage/"phase10_amendment_manifest.json",manifest_path)
      print(f"Built Phase-10 amendment: {amendment_hash}");print(f"Candidate states: {len(states)}; overall pairs: {len(overall)}")


if __name__=="__main__":main()
