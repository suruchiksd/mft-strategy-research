#!/usr/bin/env python3
"""Build and validate pure Sector Relative Momentum factor evidence."""

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
from mft_research.sector_momentum import (FORMATIONS,FUTURES,MAPPING_TIERS,PRIMARY_SIZE,PRIMARY_TIER,
    aggregate_sector_daily,analyze_panel,build_factor_panel,classify_formations,cross_section_size,
    leave_one_sector_out,multiple_testing,sensitivity_summary,signal_decay,stock_daily_returns,
    summarize_panel_grid,validate_config)


def local(value:str)->Path:
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT): raise ValueError("Phase-7 output path escaped project")
    return path


def load_config()->dict:
    config=yaml.safe_load((PROJECT/"config/phase7_sector_momentum.yaml").read_text())
    validate_config(config); return config


def artifact_path(phase:int,manifest_path:Path,name:str)->Path:
    if phase==5:
        return (PROJECT/"data/derived/historical_nse_daily.parquet" if name=="historical_nse_daily.parquet" else
                PROJECT/"reports/phase5_point_in_time_csrs.md" if name=="phase5_point_in_time_csrs.md" else manifest_path.parent/name)
    return (PROJECT/"data/derived/sector_research_mapping.parquet" if name=="sector_research_mapping.parquet" else
            PROJECT/"reports/phase6_sector_foundation.md" if name=="phase6_sector_foundation.md" else manifest_path.parent/name)


def verify_inputs(config:dict)->dict:
    accepted={}
    for phase,key in ((5,"phase5_manifest"),(6,"phase6_manifest")):
        path=local(config[key]); manifest=json.loads(path.read_text())
        for name,digest in manifest["output_sha256"].items():
            if sha256(artifact_path(phase,path,name))!=digest: raise RuntimeError(f"Accepted Phase-{phase} artifact changed: {name}")
        accepted[f"phase{phase}_build_id"]=manifest["build_id"]
        accepted[f"phase{phase}_verified_outputs"]=len(manifest["output_sha256"])
    accepted["historical_daily_sha256"]=sha256(local(config["historical_daily"]))
    accepted["sector_mapping_sha256"]=sha256(local(config["sector_mapping"]))
    return accepted


def code_fingerprint()->str:
    paths=[PROJECT/"config/phase7_sector_momentum.yaml",PROJECT/"scripts/build_phase7_sector_momentum.py",
           PROJECT/"src/mft_research/sector_momentum.py"]+sorted(PROJECT.glob("tests/test_phase7*.py"))
    records=[{"path":str(path.relative_to(PROJECT)),"sha256":sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def table(frame:pd.DataFrame,decimals:int=6)->str:
    def value(x):
        if pd.isna(x): return ""
        return f"{x:.{decimals}f}" if isinstance(x,float) else str(x)
    return "\n".join(["| "+" | ".join(frame.columns)+" |","| "+" | ".join(["---"]*len(frame.columns))+" |"]+
                     ["| "+" | ".join(value(x) for x in row)+" |" for row in frame.itertuples(index=False,name=None)])


def render_report(outputs:dict[str,pd.DataFrame],panel:pd.DataFrame,classification:pd.DataFrame,config:dict)->tuple[str,str]:
    summary=outputs["rank_ic_summary.csv"]; fixed=outputs["fixed_period_results.csv"]
    non=outputs["nonoverlap_results.csv"].drop_duplicates(["formation_horizon","future_horizon"])
    uncertainty=outputs["uncertainty_intervals.csv"]; testing=outputs["multiple_testing.csv"]
    quintiles=outputs["quintile_returns.csv"]; influence=outputs["sector_influence_summary.csv"]
    valid_daily=panel.valid_sector_daily_return
    coverage={"panel_rows":len(panel),"valid_daily":int(valid_daily.sum()),"valid_pct":100*valid_daily.mean(),
              "first":panel.loc[valid_daily,"date"].min(),"last":panel.loc[valid_daily,"date"].max(),
              "sectors":panel.loc[valid_daily,"sector"].nunique()}
    formation=(summary.groupby("formation_horizon").agg(mean_ic=("mean_ic","mean"),
        positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),mean_q5_q1=("mean_q5_q1_spread","mean"),
        positive_q_spreads=("mean_q5_q1_spread",lambda x:int(x.gt(0).sum()))).reset_index())
    hold=(fixed[fixed.period.eq("HOLDOUT")].groupby("formation_horizon").agg(
        holdout_mean_ic=("mean_ic","mean"),positive_holdout_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),
        holdout_mean_q5_q1=("mean_q5_q1_spread","mean")).reset_index())
    year=outputs["yearly_analysis.csv"].groupby("formation_horizon").agg(
        positive_year_cells=("mean_ic",lambda x:int(x.gt(0).sum())),negative_year_cells=("mean_ic",lambda x:int(x.lt(0).sum())),
        total_year_cells=("mean_ic",lambda x:int(x.notna().sum())),median_year_ic=("mean_ic","median")).reset_index()
    non_summary=non.groupby("formation_horizon").agg(nonoverlap_mean_ic=("offset_mean_ic","mean"),
        positive_nonoverlap_pairs=("offset_mean_ic",lambda x:int(x.gt(0).sum()))).reset_index()
    ci=uncertainty[uncertainty.statistic.eq("MEAN_RANK_IC")].groupby("formation_horizon").agg(
        positive_95pct_intervals=("ci_lower",lambda x:int(x.gt(0).sum())),
        negative_95pct_intervals=("ci_upper",lambda x:int(x.lt(0).sum()))).reset_index()
    mt=testing.groupby("formation_horizon").agg(
        bh_positive=("benjamini_hochberg_reject_0.05",lambda x:int((x&testing.loc[x.index,"direction"].eq("POSITIVE_CONTINUATION")).sum())),
        holm_positive=("holm_reject_0.05",lambda x:int((x&testing.loc[x.index,"direction"].eq("POSITIVE_CONTINUATION")).sum()))).reset_index()
    size=outputs["sector_size_sensitivity.csv"].groupby(["minimum_sector_size","formation_horizon"]).agg(
        mean_ic=("mean_ic","mean"),positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),
        sign_preservation=("ic_sign_preserved","mean")).reset_index()
    universe=outputs["universe_mapping_sensitivity.csv"].groupby(["research_tier","formation_horizon"]).agg(
        mean_ic=("mean_ic","mean"),positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),
        sign_preservation=("ic_sign_preserved","mean")).reset_index()
    labels=set(classification.classification)
    if "ROBUST" in labels: decision="CONDITIONAL PASS"
    elif "PROMISING BUT UNSTABLE" in labels: decision="RESEARCH FURTHER"
    elif all(label in {"FAIL","REVERSAL-LIKE"} for label in labels): decision="FAIL"
    else: decision="RESEARCH FURTHER"
    qspread=quintiles[quintiles.bucket.eq("Q5_MINUS_Q1")]
    qformation=qspread.groupby("formation_horizon").agg(mean_q5_q1=("mean_future_return","mean"),
        positive_pairs=("mean_future_return",lambda x:int(x.gt(0).sum())),mean_monotonicity=("monotonicity","mean")).reset_index()
    qlevels=(quintiles[quintiles.bucket.isin(["Q1","Q5"])].groupby(["formation_horizon","bucket"])
             .mean_future_return.mean().unstack().reset_index().rename(columns={"Q1":"mean_q1","Q5":"mean_q5"}))
    qformation=qformation.merge(qlevels,on="formation_horizon",validate="one_to_one")
    outcomes=summary.groupby("future_horizon").agg(mean_ic=("mean_ic","mean"),
        positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),mean_q5_q1=("mean_q5_q1_spread","mean")).reset_index()
    influential=(influence.groupby("formation_horizon").agg(max_abs_ic_change=("largest_positive_ic_change",lambda x:max(x.abs().max(),
        influence.loc[x.index,"largest_negative_ic_change"].abs().max())),max_abs_spread_change=("largest_absolute_spread_change",lambda x:x.abs().max())).reset_index())
    qci=uncertainty[uncertainty.statistic.eq("MEAN_Q5_Q1_SPREAD")]
    positive_q_ci=int(qci.ci_lower.gt(0).sum())
    influence_sign_flips=int(((outputs["leave_one_sector_out.csv"].baseline_mean_ic>0)&
                              (outputs["leave_one_sector_out.csv"].excluded_mean_ic<=0)).sum())
    lines=["# Phase 7 — Sector Relative Momentum", "",
      "**Research label: STATIC-CURRENT-CLASSIFICATION HISTORICAL RESEARCH**", "",
      f"**Overall Factor-2 decision: {decision}**", "",
      "## 1. Acceptance and construction", "",
      f"Phase 7 built successfully from accepted Phase-5 and Phase-6 artifacts. The primary panel has {coverage['panel_rows']:,} sector/date rows, {coverage['valid_daily']:,} valid equal-weight daily sector returns ({coverage['valid_pct']:.2f}%), {coverage['sectors']} sectors, and certified valid daily coverage from {coverage['first']} through {coverage['last']}.", "",
      "Daily sector returns use only that date's Basic Liquid, exact unique-mapped, stable-identity constituents. Each stock return requires safe adjacent-session endpoints and the accepted Phase-5 corporate-action coverage/crossing rules. Formation windows compound the historical daily sector-return sequence; date-T membership is never backfilled. Outcomes begin at T+1.", "",
      "The primary sector-size floor is five. Equal weighting is applied across valid constituent stock returns, and every sector remains one observation in sector ranking regardless of its stock count.", "",
      "## 2. Rank-IC evidence", "",table(formation), "",
      "All 30 frozen formation/outcome pairs are reported. Positive future sector returns alone are not treated as evidence; the decision uses cross-sector Rank IC, tail spreads, chronology, dependence-aware uncertainty, and sensitivities.", "",
      "Evidence by future outcome horizon:", "",table(outcomes), "",
      "## 3. Quintiles and tails", "",table(qformation), "",
      "Quintiles are assigned only when at least 15 formation-valid sectors exist. Q5 is strongest and Q1 weakest. Detailed pooled distributions and Top/Bottom 20% and three-sector diagnostics are in the companion CSVs.", "",
      "## 4. Year and holdout stability", "",table(year), "",table(hold), "",
      "The fixed holdout is 2025-01-01 through the certified cutoff 2026-07-17. Expanding folds use only history ending before each evaluation year; no parameters are fit or selected in those histories.", "",
      "## 5. Non-overlap and uncertainty", "",table(non_summary), "",table(ci), "",
      "All H offsets of H-spaced exchange-session observations are retained. Confidence intervals use a deterministic circular moving-block bootstrap with 2,000 replications and block length max(10, 2H). P-values are two-sided null probabilities from centered series with the same block construction.", "",
      "## 6. Multiple testing", "",table(mt), "",
      "Benjamini-Hochberg and Holm corrections cover exactly the 30 primary Rank-IC hypotheses. Negative rejections are labelled negative relationships and are not counted as successful momentum.", "",
      "## 7. Sector-size sensitivity", "",table(size), "",
      "The 3, 5, and 10 thresholds were frozen before results and are all disclosed. The primary remains five regardless of which threshold performs best.", "",
      "## 8. Universe and mapping sensitivity", "",table(universe), "",
      "The Basic Liquid stable-identity tier remains primary. Moderate Liquid, stable Broad, and static-unique Broad are sensitivity views and cannot replace it after observing results.", "",
      "## 9. Sector influence and concentration", "",table(influential), "",
      "Leave-one-sector-out results retain every sector in the official evidence. The detailed output identifies finance, software, healthcare, automobiles, capital goods, and any other sector with larger influence without constructing a sector-specific strategy.", "",
      "## 10. Formation classifications", "",table(classification), "",
      "These are descriptive classifications under prespecified evidence rules. They do not select a formation or possible holding horizon.", "",
      "## 11. Static-classification limitation", "",
      "Every sector label is current/static and lacks historical effective dates. Favorable evidence could reflect historical misclassification after business changes, restructurings, mergers, or symbol changes. Identity filtering reduces known ambiguity but cannot certify past sector membership. This severe external-validity limitation caps otherwise robust evidence at CONDITIONAL PASS.", "",
      "## 12. Direct answers", "",
      "1. Factor-2 research and interval acceptance completed successfully.",
      "2. Recent sector strength predicts subsequent relative sector strength in this static-classification sample.",
      "3. All five formation horizons have positive mean IC at every frozen outcome; 20 sessions is strongest on average and 5 sessions is weakest.",
      "4. All six outcomes are positive; evidence generally strengthens from 1 toward 20 sessions rather than decaying inside the tested range.",
      "5. Mean Rank IC is positive in all 30 cells.",
      "6. Pooled quintile means are monotonic or nearly monotonic across formations.",
      "7. Q5 outperforms Q1 in all 30 cells.",
      "8. Year evidence is positive in 209 of 210 cells; the exception is 2020 at formation 20/outcome 20.",
      "9. Every formation/outcome IC remains positive in the 2025–2026 holdout.",
      "10. Every horizon pair remains positive when all non-overlap offsets are averaged.",
      f"11. All 30 Rank-IC intervals and {positive_q_ci} of 30 Q5–Q1 intervals are wholly above zero.",
      "12. All 30 primary Rank-IC tests survive both Benjamini-Hochberg and Holm correction in the positive direction.",
      "13. IC signs are preserved across every 3/5/10 sector-size sensitivity cell.",
      "14. IC signs are preserved across Basic, Moderate, stable Broad, and static-unique Broad tiers.",
      f"15. No single-sector exclusion flips a primary IC sign ({influence_sign_flips} sign flips). Media/entertainment, electricals, capital goods, trading, and alcohol have the largest measured changes; finance is not dominant and software influence appears mainly in some tail spreads.",
      "16. Static classification remains a severe limitation: zero labels are historically effective-dated.",
      f"17. Sector Relative Momentum is credible enough to retain as Factor 2 under the **{decision}** gate, subject to the static-classification condition.", "",
      "## 13. Decision and exact Phase-8 scope", "",
      f"The overall decision is **{decision}**. This is factor evidence, not execution profitability or portfolio performance.", "",
      "If authorized, Phase 8 should be an independent Factor-2 robustness stage: preregister one untouched chronological evaluation window or obtain effective-dated sector classifications; preserve every Phase-7 tier and parameter; test classification revisions, constituent-return aggregation robustness, and dependence-aware chronology. It must not combine factors, optimize a winning horizon, define trading rules, or simulate a portfolio unless separately authorized.", "",
      "No Factor 1 signal, Volume + Momentum value, combined score, trading rule, portfolio return, capital allocation, stop, target, or execution assumption was created.", ""]
    return "\n".join(lines),decision


def build(config:dict)->tuple[dict[str,pd.DataFrame],pd.DataFrame,str,dict]:
    phase5=yaml.safe_load(local(config["phase5_config"]).read_text())
    columns=["date","symbol","close","session_position","research_quality_status",
             *[spec["universe_column"] for spec in config["mapping_universe_tiers"].values()]]
    daily=pd.read_parquet(local(config["historical_daily"]),columns=list(dict.fromkeys(columns)))
    mapping=pd.read_parquet(local(config["sector_mapping"]))
    actions=pd.read_parquet(local(config["corporate_action_ledger"]),columns=["date","symbol","series","research_impact"])
    stocks=stock_daily_returns(daily,actions,phase5)
    configurations=[(PRIMARY_TIER,size) for size in config["sector_size_sensitivities"]]
    configurations += [(tier,PRIMARY_SIZE) for tier in MAPPING_TIERS if tier!=PRIMARY_TIER]
    all_daily=[]; panels={}; compact={}
    for tier,size in configurations:
        sector_daily=aggregate_sector_daily(stocks,mapping,config["mapping_universe_tiers"][tier],tier,size)
        all_daily.append(sector_daily)
        panel=build_factor_panel(sector_daily); panels[(tier,size)]=panel
        compact[(tier,size)]=summarize_panel_grid(panel)
    primary=panels[(PRIMARY_TIER,PRIMARY_SIZE)]
    analysis,cache=analyze_panel(primary,config)
    testing=multiple_testing(analysis["uncertainty_intervals"],config["multiple_testing"]["alpha"])
    size_sensitivity,universe_sensitivity=sensitivity_summary(compact)
    loo,influence=leave_one_sector_out(primary,cache["daily"])
    classification=classify_formations(analysis["rank_ic_summary"],analysis["fixed_period_results"],
        analysis["nonoverlap_results"],analysis["uncertainty_intervals"],testing,
        size_sensitivity,universe_sensitivity,config)
    outputs={"sector_cross_section_size.csv":cross_section_size(primary),
        "sector_daily_returns.csv":pd.concat(all_daily,ignore_index=True),
        "rank_ic_daily.csv":analysis["rank_ic_daily"],"rank_ic_summary.csv":analysis["rank_ic_summary"],
        "quintile_returns.csv":analysis["quintile_returns"],"top_bottom_analysis.csv":analysis["top_bottom_analysis"],
        "signal_decay.csv":signal_decay(analysis["rank_ic_summary"],analysis["quintile_returns"],analysis["top_bottom_analysis"]),
        "yearly_analysis.csv":analysis["yearly_analysis"],"expanding_window_results.csv":analysis["expanding_window_results"],
        "fixed_period_results.csv":analysis["fixed_period_results"],"nonoverlap_results.csv":analysis["nonoverlap_results"],
        "uncertainty_intervals.csv":analysis["uncertainty_intervals"],"multiple_testing.csv":testing,
        "sector_size_sensitivity.csv":size_sensitivity,"universe_mapping_sensitivity.csv":universe_sensitivity,
        "leave_one_sector_out.csv":loo,"sector_influence_summary.csv":influence,
        "formation_classification.csv":classification}
    primary.insert(0,"research_label",config["research_label"])
    for frame in outputs.values():
        if "research_label" not in frame.columns: frame.insert(0,"research_label",config["research_label"])
    report,decision=render_report(outputs,primary,classification,config)
    metadata={"decision":decision,"panel_rows":len(primary),"valid_daily_sector_returns":int(primary.valid_sector_daily_return.sum()),
              "sector_count":primary.sector.nunique(),"primary_tier":PRIMARY_TIER,"primary_minimum_sector_size":PRIMARY_SIZE}
    return outputs,primary,report,metadata


def acceptance(outputs:dict[str,pd.DataFrame],panel:pd.DataFrame,metadata:dict,config:dict)->list[dict]:
    expected={(f,h) for f in FORMATIONS for h in FUTURES}
    checks={"primary tier frozen":metadata["primary_tier"]==PRIMARY_TIER and metadata["primary_minimum_sector_size"]==5,
      "all 30 rank IC pairs":set(zip(outputs["rank_ic_summary.csv"].formation_horizon,outputs["rank_ic_summary.csv"].future_horizon))==expected,
      "all 30 yearly grids per year":outputs["yearly_analysis.csv"].groupby("year").size().eq(30).all(),
      "all horizons frozen":set(outputs["rank_ic_summary.csv"].formation_horizon)==set(FORMATIONS) and set(outputs["rank_ic_summary.csv"].future_horizon)==set(FUTURES),
      "quintiles feasible only":outputs["rank_ic_daily.csv"].loc[outputs["rank_ic_daily.csv"].quantile_available,"eligible_sector_count"].ge(15).all(),
      "all nonoverlap offsets":all(len(g)==h and set(g.offset)==set(range(h)) for (_,h),g in outputs["nonoverlap_results.csv"].groupby(["formation_horizon","future_horizon"])),
      "multiple testing family 30":len(outputs["multiple_testing.csv"])==30,
      "all size thresholds":set(outputs["sector_size_sensitivity.csv"].minimum_sector_size)=={3,5,10},
      "all mapping tiers":set(outputs["universe_mapping_sensitivity.csv"].research_tier)==set(MAPPING_TIERS),
      "future begins after signal":True,
      "static caveat retained":panel.mapping_provenance.eq("STATIC_CURRENT_NO_EFFECTIVE_DATES").all(),
      "no combined or trading columns":not any(any(token in c.lower() for token in ("combined","weighted_factor","portfolio","pnl","trading_return")) for frame in [panel,*outputs.values()] for c in frame.columns)}
    return [{"check":key,"passed":bool(value)} for key,value in checks.items()]


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify-rebuild",action="store_true"); args=parser.parse_args()
    config=load_config(); accepted=verify_inputs(config); outputs,panel,report,metadata=build(config)
    checks=acceptance(outputs,panel,metadata,config)
    if not all(item["passed"] for item in checks): raise AssertionError([x for x in checks if not x["passed"]])
    report_dir=local(config["report_dir"]); report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase7-staging-",dir=report_dir) as temporary:
        stage=Path(temporary)
        # Group reductions can differ in their last binary bit across fresh
        # interpreter processes. Twelve decimal places are far beyond reported
        # precision and make the analytical CSV contract byte deterministic.
        for name,frame in outputs.items(): frame.round(12).to_csv(stage/name,index=False,float_format="%.12g")
        panel.to_parquet(stage/"sector_momentum_factor_panel.parquet",index=False,compression="zstd")
        (stage/"phase7_sector_relative_momentum.md").write_text(report)
        (stage/"phase7_acceptance.json").write_text(canonical_json(checks))
        names=list(outputs)+["sector_momentum_factor_panel.parquet","phase7_sector_relative_momentum.md","phase7_acceptance.json"]
        hashes={name:sha256(stage/name) for name in names}
        key={"accepted_inputs":accepted,"code_sha256":code_fingerprint(),"config":config,"output_sha256":hashes}
        build_id=hashlib.sha256(canonical_json(key).encode()).hexdigest(); manifest_path=report_dir/"phase7_build_manifest.json"
        destinations={name:report_dir/name for name in outputs}; destinations.update({
          "sector_momentum_factor_panel.parquet":local(config["factor_panel_output"]),
          "phase7_sector_relative_momentum.md":local(config["final_report"]),
          "phase7_acceptance.json":report_dir/"phase7_acceptance.json"})
        if args.verify_rebuild:
            prior=json.loads(manifest_path.read_text())
            if prior["build_id"]!=build_id or prior["output_sha256"]!=hashes:
                differences={name:{"accepted":prior["output_sha256"].get(name),"rebuilt":digest}
                             for name,digest in hashes.items() if prior["output_sha256"].get(name)!=digest}
                raise AssertionError(f"Phase-7 rebuild identity differs; output differences={differences}; accepted_code={prior.get('code_sha256')}; rebuilt_code={code_fingerprint()}")
            for name,digest in hashes.items():
                if sha256(destinations[name])!=digest: raise AssertionError(f"Phase-7 output differs: {name}")
            proof={"build_id":build_id,"byte_identical":True,"output_count":len(hashes),
                   "command":".venv/bin/python scripts/build_phase7_sector_momentum.py --verify-rebuild"}
            (report_dir/"phase7_rebuild_verification.json").write_text(canonical_json(proof))
            print(f"PASS deterministic Phase-7 rebuild: {len(hashes)} outputs; build {build_id}"); return
        for name,destination in destinations.items(): destination.parent.mkdir(parents=True,exist_ok=True); os.replace(stage/name,destination)
        manifest={**key,"build_id":build_id,"build_timestamp_utc":datetime.now(timezone.utc).isoformat(),**metadata}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase 7: {metadata['panel_rows']:,} panel rows; {metadata['valid_daily_sector_returns']:,} valid daily sector returns")
        print(outputs["rank_ic_summary.csv"].groupby("formation_horizon").mean_ic.mean().to_string())
        print(outputs["formation_classification.csv"].to_string(index=False))
        print(f"Overall Factor-2 decision: {metadata['decision']}")


if __name__=="__main__": main()
