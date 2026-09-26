#!/usr/bin/env python3
"""Build rigorous predictive evidence for the seven frozen Factor-3 candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/"src"))

from mft_research.data.manifest import canonical_json,sha256
from mft_research.volume_momentum_research import (CANDIDATES,FUTURES,INTERACTIONS,ROLES,analyze,
    build_panel,classify_candidates,signal_decay,validate_config)


def local(value:str)->Path:
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT): raise ValueError("Phase-9 path escaped project")
    return path


def load_config()->dict:
    return yaml.safe_load((PROJECT/"config/phase9_volume_momentum_research.yaml").read_text())


def artifact_path(phase:int,manifest_path:Path,name:str)->Path:
    special={
      (5,"historical_nse_daily.parquet"):PROJECT/"data/derived/historical_nse_daily.parquet",
      (5,"phase5_point_in_time_csrs.md"):PROJECT/"reports/phase5_point_in_time_csrs.md",
      (6,"sector_research_mapping.parquet"):PROJECT/"data/derived/sector_research_mapping.parquet",
      (6,"phase6_sector_foundation.md"):PROJECT/"reports/phase6_sector_foundation.md",
      (7,"sector_momentum_factor_panel.parquet"):PROJECT/"data/derived/sector_momentum_factor_panel.parquet",
      (7,"phase7_sector_relative_momentum.md"):PROJECT/"reports/phase7_sector_relative_momentum.md",
      (8,"volume_momentum_foundation.parquet"):PROJECT/"data/derived/volume_momentum_foundation.parquet",
      (8,"phase8_volume_momentum_foundation.md"):PROJECT/"reports/phase8_volume_momentum_foundation.md"}
    return special.get((phase,name),manifest_path.parent/name)


def verify_inputs(config:dict)->dict:
    accepted={}
    manifests=((5,"phase5_manifest"),(6,"phase6_manifest"),(7,"phase7_manifest"),(8,"phase8_manifest"))
    for phase,key in manifests:
        path=local(config[key]); manifest=json.loads(path.read_text())
        if phase==8 and manifest["build_id"]!=config["phase8_required_build_id"]: raise RuntimeError("Phase-8 build ID changed")
        for name,digest in manifest["output_sha256"].items():
            if sha256(artifact_path(phase,path,name))!=digest: raise RuntimeError(f"Accepted Phase-{phase} artifact changed: {name}")
        accepted[f"phase{phase}_build_id"]=manifest["build_id"]
        accepted[f"phase{phase}_verified_outputs"]=len(manifest["output_sha256"])
    return accepted


def code_fingerprint()->str:
    paths=[PROJECT/"config/phase9_volume_momentum_research.yaml",PROJECT/"scripts/build_phase9_volume_momentum_research.py",
           PROJECT/"src/mft_research/volume_momentum_research.py"]+sorted(PROJECT.glob("tests/test_phase9*.py"))
    records=[{"path":str(path.relative_to(PROJECT)),"sha256":sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def rss_mib()->float:
    try:
        for line in open(f"/proc/{os.getpid()}/status"):
            if line.startswith("VmRSS:"): return int(line.split()[1])/1024
    except OSError: pass
    return float("nan")


def stage(name:str)->None:
    print(f"STAGE {name} rss_mib={rss_mib():.1f}",flush=True)


def table(frame:pd.DataFrame,decimals:int=6)->str:
    def value(x):
        if pd.isna(x): return ""
        return f"{x:.{decimals}f}" if isinstance(x,float) else str(x)
    return "\n".join(["| "+" | ".join(frame.columns)+" |","| "+" | ".join(["---"]*len(frame.columns))+" |"]+
                     ["| "+" | ".join(value(x) for x in row)+" |" for row in frame.itertuples(index=False,name=None)])


def render_report(outputs:dict[str,pd.DataFrame],classification:pd.DataFrame,config:dict)->tuple[str,str]:
    summary=outputs["candidate_rank_ic_summary.csv"]; fixed=outputs["fixed_period_results.csv"]
    non=outputs["nonoverlap_results.csv"].drop_duplicates(["candidate_id","future_horizon"])
    uncertainty=outputs["uncertainty_intervals.csv"].query("statistic == 'MEAN_RANK_IC'")
    testing=outputs["multiple_testing.csv"]; incremental=outputs["interaction_incremental_ic.csv"]
    increment_test=outputs["interaction_incremental_uncertainty.csv"]
    universe=outputs["universe_sensitivity.csv"]; source=outputs["source_era_sensitivity.csv"]
    proximity=outputs["corporate_action_proximity_sensitivity.csv"]; redundancy=outputs["predictive_redundancy.csv"]
    rows=[]
    for candidate in CANDIDATES:
        s=summary[summary.candidate_id.eq(candidate)]; hold=fixed[(fixed.candidate_id.eq(candidate))&fixed.period.eq("HOLDOUT")]
        n=non[non.candidate_id.eq(candidate)]; ci=uncertainty[uncertainty.candidate_id.eq(candidate)]; mt=testing[testing.candidate_id.eq(candidate)]
        rows.append({"candidate":candidate,"role":ROLES[candidate],"mean_ic":s.mean_ic.mean(),"positive_pairs":int(s.mean_ic.gt(0).sum()),
                     "mean_d10_d1":s.mean_d10_d1_spread.mean(),"holdout_mean_ic":hold.mean_ic.mean(),
                     "positive_holdout":int(hold.mean_ic.gt(0).sum()),"nonoverlap_mean_ic":n.offset_mean_ic.mean(),
                     "positive_ic_intervals":int(ci.ci_lower.gt(0).sum()),"negative_ic_intervals":int(ci.ci_upper.lt(0).sum()),
                     "bh_rejections":int(mt["benjamini_hochberg_reject_0.05"].sum()),
                     "holm_rejections":int(mt["holm_reject_0.05"].sum())})
    evidence=pd.DataFrame(rows)
    inc_table=(incremental.groupby("candidate_id",as_index=False).agg(mean_incremental_ic=("mean_incremental_ic","mean"),
        positive_pairs=("mean_incremental_ic",lambda x:int(x.gt(0).sum())),holdout_mean_incremental_ic=("holdout_mean_incremental_ic","mean"),
        positive_holdout_pairs=("holdout_mean_incremental_ic",lambda x:int(x.gt(0).sum()))).merge(
        increment_test.groupby("candidate_id",as_index=False).agg(positive_95pct_intervals=("ci_lower",lambda x:int(x.gt(0).sum())),
        negative_95pct_intervals=("ci_upper",lambda x:int(x.lt(0).sum())),bh_rejections=("benjamini_hochberg_reject_0.05","sum"),
        holm_rejections=("holm_reject_0.05","sum")),on="candidate_id"))
    moderate=universe[universe.universe.eq("MODERATE_LIQUID")].groupby("candidate_id",as_index=False).agg(
        moderate_mean_ic=("mean_ic","mean"),moderate_positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())))
    era=source.groupby(["candidate_id","source_era"],as_index=False).mean_ic.mean().pivot(index="candidate_id",columns="source_era",values="mean_ic").reset_index()
    era.columns.name=None
    action=proximity.groupby("candidate_id",as_index=False).agg(mean_abs_ic_change=("mean_ic_change_vs_all",lambda x:x.abs().mean()),
                                                                 max_abs_ic_change=("mean_ic_change_vs_all",lambda x:x.abs().max()))
    max_redundancy=redundancy.loc[redundancy.daily_ic_pearson.abs().idxmax()]
    robust_interactions=set(classification.query("role == 'INTERACTION' and classification == 'ROBUST POSITIVE'").candidate_id)
    promising=set(classification.query("role == 'INTERACTION' and classification == 'PROMISING POSITIVE'").candidate_id)
    plausible=set(incremental.groupby("candidate_id").mean_incremental_ic.apply(lambda x:int(x.gt(0).sum())).loc[lambda x:x>=3].index)
    if robust_interactions: decision="PASS FOR NEXT RESEARCH STAGE"
    elif promising: decision="CONDITIONAL PASS"
    elif plausible: decision="RESEARCH FURTHER"
    else: decision="FAIL"
    lines=["# Phase 9 — Volume + Momentum Predictive Research","",
      "**Factor research only. No portfolio, trading rule, factor combination, or execution result was created.**","",
      f"**Overall Factor-3 decision: {decision}**","","## 1. Acceptance and frozen design","",
      "Phase 9 verified the accepted Phase-8 build and tested exactly seven frozen candidates against exactly 1/2/3/5/10/20-session outcomes. BASIC_LIQUID is primary; MODERATE_LIQUID is the only universe sensitivity. Forward labels use certified Phase-5 interval safety through 2026-07-17.","",
      "## 2. Controls and raw interaction evidence","",table(evidence),"",
      "Positive IC means higher frozen candidate values precede higher returns; negative IC is reported as reversal-like and is never sign-flipped.","",
      "## 3. Incremental interaction evidence","",table(inc_table),"",
      "Each interaction rank was residualized on its two frozen component-control ranks within the same date. Outcomes did not enter residualization. These 18 tests form a separate multiple-testing family.","",
      "## 4. Chronology, dependence, and sensitivities","",table(moderate),"",table(era),"",table(action),"",
      f"The largest absolute correlation between two candidate daily-IC series is {abs(max_redundancy.daily_ic_pearson):.6f} for {max_redundancy.candidate_left}/{max_redundancy.candidate_right} at the {int(max_redundancy.future_horizon)}-session outcome. OLD/NEW comparisons are source-era/time-era sensitivity, not a clean format experiment.","",
      "All outcome horizons use all non-overlap offsets. Confidence intervals use 2,000 deterministic circular block-bootstrap replications with block length max(10,2H). BH and Holm corrections cover the 42 primary tests; incremental corrections cover a separate 18-test family.","",
      "## 5. Candidate classifications","",table(classification),"",
      "Interaction candidates cannot receive ROBUST POSITIVE without satisfying the preregistered incremental-information rule.","",
      "## 6. Direct answers","",
      f"1. Phase 9 completed successfully under the frozen registry and interval-safety contract.",
      f"2. VM01 is classified {classification.set_index('candidate_id').loc['VM01','classification']}.",
      f"3. VM02 is classified {classification.set_index('candidate_id').loc['VM02','classification']}.",
      f"4. VM03/VM04 classifications are {classification.set_index('candidate_id').loc['VM03','classification']} and {classification.set_index('candidate_id').loc['VM04','classification']}; their detailed direction and uncertainty are disclosed above.",
      f"5. The stronger volume-only mean IC is {evidence[evidence.candidate.isin(['VM03','VM04'])].sort_values('mean_ic',ascending=False).iloc[0].candidate}; no horizon was selected for deployment.",
      f"6. VM05 incremental classification is {classification.set_index('candidate_id').loc['VM05','classification']}.",
      f"7. VM06 incremental classification is {classification.set_index('candidate_id').loc['VM06','classification']}.",
      f"8. VM07 incremental classification is {classification.set_index('candidate_id').loc['VM07','classification']}.",
      "9. Interaction directions, including mixed or negative relationships, are shown without reorientation in the evidence and incremental tables.",
      "10. Holdout signs for all candidates are shown in the primary evidence table.",
      "11. Non-overlap evidence is shown by candidate and all offsets in `nonoverlap_results.csv`.",
      "12. Confidence-interval exclusions are counted in the evidence tables and fully disclosed in the uncertainty CSVs.",
      "13. BH/Holm results are shown above and fully disclosed with direction labels.",
      "14. Every year and all 42 cells are disclosed in `yearly_analysis.csv`; negative and sparse years are retained.",
      "15. MODERATE_LIQUID results are disclosed without replacing BASIC_LIQUID as primary.",
      "16. OLD/NEW source-era signs are disclosed as time-era sensitivity, not format equivalence proof.",
      "17. Excluding already-valid observations within ±5 sessions of recorded actions produces the changes summarized above; rejected crossing intervals were never restored.",
      f"18. The most similar predictive pair is {max_redundancy.candidate_left}/{max_redundancy.candidate_right}; no candidate was removed.",
      "19. Retention follows the preregistered classification table; raw interaction IC alone is insufficient.",
      f"20. The Factor-3 decision is {decision} because the interaction incremental criteria, rather than control performance alone, determine the gate.","",
      "## 7. Exact next-stage recommendation","",
      ("If separately authorized, the next stage should preserve only candidates retained by the classification gate and conduct an untouched forward robustness study before any factor combination. It must keep Factor 2 separate, freeze any later combination rule before outcomes, and defer portfolio construction, costs, execution, and capital sizing to a subsequent authorization."
       if decision!="FAIL" else
       "Do not carry Volume + Momentum into factor-combination or trading-rule research. Preserve any control or reversal findings as separate hypotheses only; a new untouched sample would be required before revisiting an interaction."),"",
      "The current/static sector limitation is irrelevant to Factor 3, but accepted corporate-action coverage and source-era limitations remain. No Factor 1B optimization or Factor-2/Factor-3 combination was performed.",""]
    return "\n".join(lines),decision


def acceptance(outputs:dict[str,pd.DataFrame],panel:pd.DataFrame,registry:pd.DataFrame,config:dict)->list[dict]:
    expected={(candidate,h) for candidate in CANDIDATES for h in FUTURES}
    checks={"exact seven candidates":tuple(registry.candidate_id)==CANDIDATES,
      "future horizons frozen":tuple(config["future_horizons"])==FUTURES,
      "all 42 primary cells":set(zip(outputs["candidate_rank_ic_summary.csv"].candidate_id,outputs["candidate_rank_ic_summary.csv"].future_horizon))==expected,
      "primary test family 42":len(outputs["multiple_testing.csv"])==42,
      "incremental family 18":len(outputs["interaction_incremental_uncertainty.csv"])==18,
      "interaction map frozen":config["interaction_controls"]=={key:list(value) for key,value in INTERACTIONS.items()},
      "all nonoverlap offsets":all(set(group.offset)==set(range(h)) for (_,h),group in outputs["nonoverlap_results.csv"].groupby(["candidate_id","future_horizon"])),
      "nonoverlap spacing":outputs["nonoverlap_results.csv"].spacing_valid.all(),
      "primary universe frozen":config["primary_universe"]=="BASIC_LIQUID",
      "only moderate sensitivity":set(outputs["universe_sensitivity.csv"].universe)=={"BASIC_LIQUID","MODERATE_LIQUID"},
      "certified cutoff enforced":panel.loc[panel.date.gt(pd.Timestamp("2026-07-17").date()),[f"valid_future_{h}" for h in FUTURES]].to_numpy().sum()==0,
      "no combined strategy":not any("combined" in c.lower() for frame in [panel,*outputs.values()] for c in frame.columns),
      "no portfolio or pnl":not any(any(token in c.lower() for token in ("portfolio","pnl","trading_return","position_size")) for frame in [panel,*outputs.values()] for c in frame.columns)}
    return [{"check":key,"passed":bool(value)} for key,value in checks.items()]


def build(config:dict):
    stage("LOAD_FOUNDATION")
    registry=pd.read_csv(local(config["phase8_registry"])); validate_config(config,registry)
    foundation=pd.read_parquet(local(config["phase8_foundation"])); identity=pd.read_csv(local(config["historical_identity"]))
    actions=pd.read_parquet(local(config["corporate_action_ledger"]))
    print(f"FOUNDATION rows={len(foundation):,} columns={len(foundation.columns)} memory_mib={foundation.memory_usage(index=True,deep=True).sum()/1024**2:.1f}",flush=True)
    print("EXPECTED_WORKING_COLUMNS date,symbol,source_format,session_position,close,research_quality_status,universe flags,component validity/reasons,VM01..VM07 source values",flush=True)
    stage("PANEL")
    panel=build_panel(foundation,identity,actions,registry,config)
    del foundation
    stage("PANEL_COMPLETE")
    analysis,_=analyze(panel,registry,config)
    outputs={f"{key}.csv":value for key,value in analysis.items()}
    outputs["signal_decay.csv"]=signal_decay(analysis["candidate_rank_ic_summary"])
    classification=classify_candidates(analysis,config); outputs["candidate_classification.csv"]=classification
    report,decision=render_report(outputs,classification,config)
    metadata={"decision":decision,"panel_rows":len(panel),"candidate_count":len(registry),"primary_hypotheses":42,"incremental_hypotheses":18}
    return outputs,panel,report,metadata,registry


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify-rebuild",action="store_true"); args=parser.parse_args()
    stage("START")
    config=load_config(); accepted=verify_inputs(config); outputs,panel,report,metadata,registry=build(config)
    checks=acceptance(outputs,panel,registry,config)
    if not all(x["passed"] for x in checks): raise AssertionError([x for x in checks if not x["passed"]])
    report_dir=local(config["report_dir"]); report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase9-staging-",dir=report_dir) as temporary:
      stage("SERIALIZE")
      staging_dir=Path(temporary)
      for name,frame in outputs.items(): frame.round(12).to_csv(staging_dir/name,index=False,float_format="%.12g")
      panel.to_parquet(staging_dir/"volume_momentum_factor_panel.parquet",index=False,compression="zstd")
      (staging_dir/"phase9_volume_momentum_research.md").write_text(report)
      (staging_dir/"phase9_acceptance.json").write_text(canonical_json(checks))
      names=list(outputs)+["volume_momentum_factor_panel.parquet","phase9_volume_momentum_research.md","phase9_acceptance.json"]
      hashes={name:sha256(staging_dir/name) for name in names}
      key={"accepted_inputs":accepted,"code_sha256":code_fingerprint(),"config":config,"registry_sha256":sha256(local(config["phase8_registry"])),"output_sha256":hashes}
      build_id=hashlib.sha256(canonical_json(key).encode()).hexdigest(); manifest_path=report_dir/"phase9_build_manifest.json"
      destinations={name:report_dir/name for name in outputs}; destinations.update({"volume_momentum_factor_panel.parquet":local(config["factor_panel_output"]),
        "phase9_volume_momentum_research.md":local(config["final_report"]),"phase9_acceptance.json":report_dir/"phase9_acceptance.json"})
      if args.verify_rebuild:
        prior=json.loads(manifest_path.read_text())
        if prior["build_id"]!=build_id or prior["output_sha256"]!=hashes:
            differences={name:{"accepted":prior["output_sha256"].get(name),"rebuilt":digest} for name,digest in hashes.items() if prior["output_sha256"].get(name)!=digest}
            raise AssertionError(f"Phase-9 rebuild differs: {differences}")
        for name,digest in hashes.items():
            if sha256(destinations[name])!=digest: raise AssertionError(f"Published Phase-9 output differs: {name}")
        proof={"build_id":build_id,"byte_identical":True,"output_count":len(hashes),"command":".venv/bin/python scripts/build_phase9_volume_momentum_research.py --verify-rebuild"}
        (report_dir/"phase9_rebuild_verification.json").write_text(canonical_json(proof)); print(f"PASS deterministic Phase-9 rebuild: {len(hashes)} outputs; build {build_id}"); return
      for name,destination in destinations.items(): destination.parent.mkdir(parents=True,exist_ok=True); os.replace(staging_dir/name,destination)
      manifest={**key,"build_id":build_id,"build_timestamp_utc":datetime.now(timezone.utc).isoformat(),**metadata}
      manifest_path.write_text(canonical_json(manifest))
      print(f"Built Phase 9: {len(panel):,} rows; 42 primary + 18 incremental hypotheses")
      print(outputs["candidate_classification.csv"].to_string(index=False)); print(f"Overall Factor-3 decision: {metadata['decision']}")


if __name__=="__main__": main()
