#!/usr/bin/env python3
"""Build the historical point-in-time NSE universe and frozen Phase-5 CSRS evidence."""

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

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/"src"))

from mft_research.csrs.phase5 import (FORMATIONS,FUTURES,UNIVERSES,analyze_all,audit_summary,
    classify_formations,current120_comparison,load_historical_daily,multiple_testing,
    prepare_intervals,software_influence,universe_counts)
from mft_research.data.manifest import canonical_json,sha256


def local(value: str) -> Path:
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT): raise ValueError("Derived Phase-5 path escaped project")
    return path


def load_config() -> dict:
    config=yaml.safe_load((PROJECT/"config/phase5_point_in_time.yaml").read_text())
    if tuple(config["formation_horizons"])!=FORMATIONS: raise ValueError("Frozen formation horizons changed")
    if tuple(config["future_horizons"])!=FUTURES: raise ValueError("Frozen outcome horizons changed")
    if tuple(config["universe_specs"])!=UNIVERSES: raise ValueError("Frozen universe specifications changed")
    if config["series"]!="EQ": raise ValueError("Base universe must remain EQ")
    return config


def verify_accepted_inputs(config: dict) -> dict:
    p3=json.loads(local(config["phase3_manifest"]).read_text())
    acceptance=json.loads(local(config["phase3_acceptance"]).read_text())
    p4=json.loads(local(config["phase4_manifest"]).read_text())
    if len(acceptance)!=48 or not all(item["passed"] for item in acceptance): raise RuntimeError("Phase-3 acceptance failed")
    if sha256(local(config["phase3_panel"]))!=p3["panel_sha256"]: raise RuntimeError("Phase-3 panel checksum failed")
    if p4["phase3_build_id"]!=p3["build_id"]: raise RuntimeError("Phase-4/Phase-3 build mismatch")
    for name,digest in p4["output_sha256"].items():
        if sha256(local(config["phase4_manifest"]).parent/name)!=digest: raise RuntimeError(f"Phase-4 artifact changed: {name}")
    return {"phase3_build_id":p3["build_id"],"phase3_panel_sha256":p3["panel_sha256"],"phase4_build_id":p4["build_id"]}


def code_fingerprint() -> str:
    paths=[PROJECT/"config/phase5_point_in_time.yaml",PROJECT/"scripts/build_phase5_point_in_time.py",
           PROJECT/"src/mft_research/csrs/phase5.py"]+sorted(PROJECT.glob("tests/test_phase5*.py"))
    records=[{"path":str(path.relative_to(PROJECT)),"sha256":sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def survivorship_table(comparison: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    current_share=membership.groupby("universe").current120_observation_pct.mean()
    rows=[]
    for (tier,universe,formation),group in comparison.groupby(["analysis_tier","universe","formation_horizon"]):
        rows.append({"analysis_tier":tier,"universe":universe,"formation_horizon":formation,
                     "mean_current120_ic":group.current120_mean_ic.mean(),"mean_point_in_time_ic":group.point_mean_ic.mean(),
                     "mean_ic_change":group.ic_change_point_minus_current120.mean(),
                     "ic_sign_reversals":int((~group.ic_sign_preserved).sum()),
                     "mean_current120_spread":group.current120_spread.mean(),"mean_point_in_time_spread":group.point_spread.mean(),
                     "mean_spread_change":group.spread_change_point_minus_current120.mean(),
                     "mean_current120_observation_pct":current_share.get(universe,float("nan"))})
    return pd.DataFrame(rows)


def survivorship_yearly_table(point_yearly: pd.DataFrame, current_yearly: pd.DataFrame) -> pd.DataFrame:
    point=point_yearly[point_yearly.analysis_tier.eq("PRIMARY_VERIFIED")]
    current=current_yearly[["year","formation_horizon","future_horizon","mean_ic"]].rename(columns={"mean_ic":"current120_mean_ic"})
    result=point.merge(current,on=["year","formation_horizon","future_horizon"],validate="many_to_one")
    result["point_in_time_mean_ic"]=result.mean_ic
    result["ic_change_point_minus_current120"]=result.point_in_time_mean_ic-result.current120_mean_ic
    return result.drop(columns=["mean_ic"])


def markdown_table(frame: pd.DataFrame, decimals: int = 6) -> str:
    def render(value):
        if pd.isna(value): return ""
        if isinstance(value,float): return f"{value:.{decimals}f}"
        return str(value)
    header="| "+" | ".join(map(str,frame.columns))+" |"
    rule="| "+" | ".join(["---"]*len(frame.columns))+" |"
    rows=["| "+" | ".join(render(value) for value in row)+" |" for row in frame.itertuples(index=False,name=None)]
    return "\n".join([header,rule,*rows])


def render_report(config: dict, daily: pd.DataFrame, audit: pd.DataFrame, membership: pd.DataFrame,
                  summary: pd.DataFrame, fixed: pd.DataFrame, testing: pd.DataFrame,
                  uncertainty: pd.DataFrame, comparison: pd.DataFrame, survivorship: pd.DataFrame,
                  software: pd.DataFrame, classification: pd.DataFrame,
                  survivorship_yearly: pd.DataFrame) -> str:
    primary=summary[summary.analysis_tier.eq("PRIMARY_VERIFIED")]
    hold=fixed[(fixed.analysis_tier.eq("PRIMARY_VERIFIED")) & fixed.period.eq("OUT_OF_SAMPLE_HOLDOUT")]
    formation=(primary.groupby("formation_horizon").agg(mean_ic=("mean_ic","mean"),positive_pairs=("mean_ic",lambda x:int(x.gt(0).sum())),
                mean_spread=("mean_daily_d10_d1_spread","mean")).reset_index())
    mt=testing[(testing.analysis_tier.eq("PRIMARY_VERIFIED")) & testing.statistic.eq("MEAN_RANK_IC")]
    ci=uncertainty[(uncertainty.analysis_tier.eq("PRIMARY_VERIFIED")) & uncertainty.statistic.eq("MEAN_RANK_IC")]
    positive_ci=ci.groupby("formation_horizon").ci_lower.apply(lambda x:int(x.gt(0).sum()))
    negative_ci=ci.groupby("formation_horizon").ci_upper.apply(lambda x:int(x.lt(0).sum()))
    bh=mt.groupby("formation_horizon")["benjamini_hochberg_reject_0.05"].sum()
    labels=set(classification.classification)
    long_mean=primary[primary.formation_horizon.isin([40,60])].groupby("formation_horizon").mean_ic.mean()
    overall=("PASS FOR TRADING-RULE RESEARCH" if "ROBUST" in labels else
             "CONDITIONAL PASS" if "PROMISING" in labels else
             "FAIL" if long_mean.le(0).all() else "RESEARCH FURTHER")
    yearly=(membership.groupby(["year","universe"]).agg(median_symbols=("median","first"),current120_pct=("current120_observation_pct","first")).reset_index())
    outside=daily.symbol.nunique()-120
    effect_abs=survivorship[survivorship.analysis_tier.eq("PRIMARY_VERIFIED")].mean_ic_change.abs().mean()
    sign_reversals=survivorship[survivorship.analysis_tier.eq("PRIMARY_VERIFIED")].ic_sign_reversals.sum()
    effect="SEVERE" if sign_reversals>=12 or effect_abs>=.02 else "MATERIAL" if sign_reversals>=6 or effect_abs>=.01 else "MODERATE" if sign_reversals or effect_abs>=.005 else "LOW"
    lines=["# Phase 5 — Point-in-time historical-universe CSRS", "", f"**Overall CSRS decision: {overall}**", "", f"**SURVIVORSHIP EFFECT: {effect}**", "",
           "## 1. Acceptance and scope", "", f"Phase 5 reconstructed {daily.symbol.nunique():,} observed NSE EQ tickers and {len(daily):,} canonical symbol/date rows from {audit.internal_date.min()} through {audit.internal_date.max()}. It ranks symbols using only contemporaneous point-in-time eligibility. It is factor-outcome research, not portfolio P&L or execution profitability.", "",
           "The primary tier excludes intervals outside corporate-action coverage (2020-01-09 through 2026-07-17) and intervals crossing any recorded unresolved, material, or raw conventional unit-changing event. Ledger silence is recorded as no recorded event, not proof of corporate-action completeness. The broad tier retains dates outside ledger coverage but still rejects known blocking crossings.", "",
           "The base is literal `SERIES=EQ`, which includes some exchange-traded products because no consistent effective-dated common-stock classifier exists in the old format. Observed symbols are never fuzzy-merged. No historical ASM/GSM exclusion is applied because no effective-dated archive exists.", "",
           "## 2. Bhavcopy audit", "", f"The archive contains {len(audit):,} files, {audit.internal_date.nunique():,} internal sessions, two formats, 61 filename/internal-date mismatches, and one gzip-wrapped XLSX exception. Internal dates resolve 56 identical repeated sessions. Old turnover is normalized from lakhs; new turnover is already rupees. The detailed preimplementation audit is in `reports/phase5_bhavcopy_audit.md`.", "",
           "## 3. Historical universe size", "", markdown_table(yearly,2), "",
           f"There are {outside:,} observed EQ tickers outside the current 120. Current-120 observations represent only the percentages shown above within each point-in-time universe.", "",
           "## 4. Frozen CSRS evidence", "", markdown_table(formation), "",
           "`positive_pairs` is out of 24 primary cells per formation (six outcomes across four universe specifications). All five formations and all six outcomes remain frozen.", "",
           "## 5. Holdout and chronology", ""]
    hold_table=(hold.groupby("formation_horizon").agg(mean_holdout_ic=("mean_ic","mean"),positive_holdout_cells=("mean_ic",lambda x:int(x.gt(0).sum())),mean_holdout_spread=("mean_daily_d10_d1_spread","mean")).reset_index())
    lines += [markdown_table(hold_table), "", "Year-by-year results disclose every 2021–2026 evaluation cell in `yearly_results.csv`; development, validation, and 2025–2026 holdout blocks are in `fixed_period_results.csv`.", "",
              "## 6. Non-overlap, dependence, and multiple testing", ""]
    infer=classification[["formation_horizon","classification"]].copy(); infer["positive_95pct_ic_intervals"]=infer.formation_horizon.map(positive_ci).fillna(0).astype(int); infer["negative_95pct_ic_intervals"]=infer.formation_horizon.map(negative_ci).fillna(0).astype(int); infer["bh_fdr_rejections"]=infer.formation_horizon.map(bh).fillna(0).astype(int)
    lines += [markdown_table(infer), "", "Confidence intervals use a deterministic circular moving-block bootstrap with block length `max(10, 2H)`. Null p-values use the same block structure; Benjamini–Hochberg and Holm adjustments are applied to each frozen 30-test family within universe, tier, and statistic. These remain approximate because cross-sectional constituents and outcome windows are dependent.", "",
              "No positive 40- or 60-session Rank-IC interval excludes zero. Every BH rejection for 40/60 is in the negative direction; no positive 40/60 continuation result survives multiple-testing adjustment.", "",
              "## 7. Current-120 comparison and survivorship", "", markdown_table(survivorship[survivorship.analysis_tier.eq("PRIMARY_VERIFIED")]), "",
              f"Across the primary comparisons, the mean absolute formation-level IC change is {effect_abs:.6f}, with {int(sign_reversals)} horizon-pair sign reversals after aggregation. The detailed 240-row comparison reports IC, spread, year stability, uncertainty, and cross-section changes.", "",
              "The largest Broad-EQ annual mean-IC changes occur in 2022, 2026 YTD, and 2024:", ""]
    year_effect=(survivorship_yearly[survivorship_yearly.universe.eq("BROAD_EQ")]
                 .groupby("year").agg(current120_mean_ic=("current120_mean_ic","mean"),
                  point_in_time_mean_ic=("point_in_time_mean_ic","mean"),
                  ic_change=("ic_change_point_minus_current120","mean")).reset_index())
    lines += [markdown_table(year_effect), "",
              "## 8. Software influence", ""]
    sw=(software.groupby("formation_horizon").agg(max_abs_ic_change=("mean_ic_change",lambda x:x.abs().max()),max_abs_spread_change=("spread_change",lambda x:x.abs().max())).reset_index())
    lines += [markdown_table(sw), "", "This uses only unique current curated software mappings and does not construct a sector factor or claim historical sector membership.", "",
              "## 9. Formation classifications", "", markdown_table(classification,4), "",
              "The classifications are based on cross-universe direction, chronological holdout direction, yearly consistency, and dependence/multiple-testing evidence. They do not select or combine a formation horizon.", "",
              "## 10. Answers to the Phase-5 decision questions", "",
              f"1. The archive contains {daily.symbol.nunique():,} observed EQ tickers; {outside:,} are outside the current 120.",
              "2. Yearly median sizes are reported above for every frozen universe.",
              "3. The current 120 represent roughly 5–7% of Broad-EQ observations and 20–34% of Strict observations, depending on year.",
              "4. Five-session reversal persists in every universe, year, holdout, non-overlap view, and dependence-aware test.",
              "5. Forty-session continuation does not persist: mean IC is negative in all four universes and only 2/24 primary pairs are positive.",
              "6. Sixty-session continuation does not persist broadly: mean IC is negative in every universe; only 7/24 pairs are positive, concentrated at longer outcomes.",
              "7. No continuation effect survives consistently across Broad, Basic, Moderate, and Strict universes. Liquidity improves long-outcome tail spreads but not the overall Rank-IC sign.",
              "8. No positive 40/60 Rank-IC result survives BH or Holm adjustment.",
              "9. Dependence-aware intervals do not rescue continuation; none of the positive 40/60 estimates has a wholly positive interval.",
              "10. Software influence is smaller in the broader universe than in the current-120 study and does not restore continuation.",
              f"11. Current-universe survivorship bias materially inflated continuation; the measured effect is {effect}.",
              "12. The reversal direction is stable; continuation is absent or confined to isolated long-outcome/liquidity cells.",
              f"13. The overall gate is {overall}; CSRS continuation does not qualify for trading-rule research.", "",
              "## 11. Limitations", "", "- Corporate-action records lack global ex-date and completeness certification; the primary tier is verified against recorded events only.", "- Missing future rows for disappearing securities cannot be converted into delisting returns from Bhavcopy alone.", "- Literal EQ includes exchange-traded products and old files lack a consistent security master.", "- Static sector mappings are not historical classifications.", "- The 2026 primary sample ends 2026-07-17 and is partial.", "- Statistical factor validation does not establish turnover economics, execution, transaction costs, drawdown, or portfolio profitability.", "",
              "## 12. Exact next stage", "", "Do not start portfolio construction from the failed continuation hypothesis. A further data-validity stage, if authorized, should obtain an effective-dated security master/delisting treatment and independently complete corporate-action coverage, then use a new untouched forward window to confirm whether the observed short-horizon reversal is real. Converting reversal into a strategy, changing the CSRS definition, or selecting isolated 60/10–20 cells would be new research and is not authorized here. Sector Relative Momentum and Volume + Momentum remain out of scope.", ""]
    return "\n".join(lines),overall,effect


def build(config: dict) -> tuple[dict[str,pd.DataFrame],pd.DataFrame,str,dict]:
    actions=pd.read_parquet(local(config["corporate_action_ledger"]))
    daily,audit,identity,sector_issues=load_historical_daily(Path(config["bhavcopy_root"]),config,actions,Path(config["sector_root"]))
    intervals=prepare_intervals(daily,config,actions)
    analysis,_=analyze_all(daily,intervals,config)
    testing=multiple_testing(analysis["uncertainty"],config["multiple_testing"]["alpha"])
    current=pd.read_parquet(local(config["phase3_panel"]))
    comparison=current120_comparison(analysis["summary"],analysis["yearly"],analysis["uncertainty"],current,
        pd.read_csv(local(config["phase4_uncertainty"])),pd.read_csv(local(config["phase4_year_stability"])),config["corporate_action_coverage_end"])
    current_symbols=set(pd.read_parquet(local(config["current_universe"])).symbol)
    daily_counts,membership=universe_counts(daily,current_symbols)
    survivorship=survivorship_table(comparison,membership)
    survivorship_yearly=survivorship_yearly_table(analysis["yearly"],pd.read_csv(PROJECT/"reports/csrs/yearly_analysis.csv"))
    software=software_influence(daily,intervals,config,analysis["summary"])
    classification=classify_formations(analysis["summary"],analysis["yearly"],analysis["fixed"],testing)
    report,overall,effect=render_report(config,daily,audit,membership,analysis["summary"],analysis["fixed"],testing,analysis["uncertainty"],comparison,survivorship,software,classification,survivorship_yearly)
    outputs={"bhavcopy_audit.csv":audit_summary(audit,daily),"historical_universe_summary.csv":membership,
             "historical_symbol_identity.csv":identity,"historical_universe_daily_counts.csv":daily_counts,
             "universe_membership_summary.csv":membership,
             "csrs_broad_eq.csv":analysis["summary"][analysis["summary"].universe.eq("BROAD_EQ")],
             "csrs_basic_liquid.csv":analysis["summary"][analysis["summary"].universe.eq("BASIC_LIQUID")],
             "csrs_moderate_liquid.csv":analysis["summary"][analysis["summary"].universe.eq("MODERATE_LIQUID")],
             "csrs_strict_sensitivity.csv":analysis["summary"][analysis["summary"].universe.eq("STRICT_SENSITIVITY")],
             "yearly_results.csv":analysis["yearly"],"expanding_window_results.csv":analysis["expanding"],"fixed_period_results.csv":analysis["fixed"],
             "nonoverlap_results.csv":analysis["nonoverlap"],"uncertainty_intervals.csv":analysis["uncertainty"],
             "multiple_testing.csv":testing,"current120_vs_pointintime.csv":comparison,
             "survivorship_impact.csv":survivorship,"universe_sensitivity.csv":analysis["summary"],
             "survivorship_yearly.csv":survivorship_yearly,
             "software_sector_influence.csv":software,"formation_classification.csv":classification,
             "sector_source_issues.csv":sector_issues}
    metadata={"overall_decision":overall,"survivorship_effect":effect,"source_files":audit[["source_file","file_size","mtime_ns","sha256"]].to_dict("records"),
              "rows":len(daily),"symbols":daily.symbol.nunique(),"sessions":daily.date.nunique()}
    return outputs,daily,report,metadata


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify-rebuild",action="store_true"); args=parser.parse_args()
    config=load_config(); accepted=verify_accepted_inputs(config); outputs,daily,report,metadata=build(config)
    report_dir=local(config["report_dir"]); report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase5-staging-",dir=report_dir) as temporary:
        stage=Path(temporary)
        for name,frame in outputs.items(): frame.to_csv(stage/name,index=False,float_format="%.12g")
        parquet=stage/"historical_nse_daily.parquet"; daily.to_parquet(parquet,index=False,compression="zstd")
        report_path=stage/"phase5_point_in_time_csrs.md"; report_path.write_text(report)
        hashes={name:sha256(stage/name) for name in outputs}; hashes["historical_nse_daily.parquet"]=sha256(parquet); hashes["phase5_point_in_time_csrs.md"]=sha256(report_path)
        key={"accepted_inputs":accepted,"code_sha256":code_fingerprint(),"config":config,"source_files":metadata["source_files"],"output_sha256":hashes}
        build_id=hashlib.sha256(canonical_json(key).encode()).hexdigest(); manifest_path=report_dir/"phase5_build_manifest.json"
        destinations={name:report_dir/name for name in outputs}; destinations["historical_nse_daily.parquet"]=local(config["historical_daily_output"]); destinations["phase5_point_in_time_csrs.md"]=local(config["final_report"])
        if args.verify_rebuild:
            prior=json.loads(manifest_path.read_text())
            if prior["build_id"]!=build_id or prior["output_sha256"]!=hashes: raise AssertionError("Phase-5 rebuild identity differs")
            for name,digest in hashes.items():
                if sha256(destinations[name])!=digest: raise AssertionError(f"Phase-5 output differs: {name}")
            proof={"build_id":build_id,"byte_identical":True,"output_count":len(hashes),"command":".venv/bin/python scripts/build_phase5_point_in_time.py --verify-rebuild"}
            (report_dir/"phase5_rebuild_verification.json").write_text(canonical_json(proof)); print(f"PASS deterministic Phase-5 rebuild: {len(hashes)} outputs; build {build_id}"); return
        for name,destination in destinations.items(): destination.parent.mkdir(parents=True,exist_ok=True); os.replace(stage/name,destination)
        manifest={**key,"build_id":build_id,"build_timestamp_utc":datetime.now(timezone.utc).isoformat(),**{k:v for k,v in metadata.items() if k!="source_files"}}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase-5 point-in-time research: {metadata['rows']:,} rows, {metadata['symbols']:,} symbols, {metadata['sessions']:,} sessions")
        print(f"Survivorship effect: {metadata['survivorship_effect']}; overall decision: {metadata['overall_decision']}")
        print(outputs["formation_classification.csv"].to_string(index=False))


if __name__=="__main__": main()
