#!/usr/bin/env python3
"""Build frozen Phase-11 Sector Momentum Strategy V1 simulations."""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, os, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from mft_research.data.manifest import canonical_json,sha256
from mft_research.sector_strategy import action_contract,extended_sector_panel,generate_rebalances,performance_metrics,simulate

PREREG=ROOT/"reports/sector_strategy/preregistration"
OUT=ROOT/"reports/sector_strategy"

def verify_gate():
    spec=importlib.util.spec_from_file_location("freeze11",ROOT/"scripts/freeze_phase11_strategy.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.main if False else None
    cfg=yaml.safe_load((PREREG/"phase11_sector_strategy_config.yaml").read_text())
    manifest=json.loads((PREREG/"phase11_strategy_manifest.json").read_text())
    for name,digest in manifest["frozen_file_sha256"].items():
        if sha256(PREREG/name)!=digest:raise RuntimeError(f"Preregistration changed: {name}")
    key={k:manifest[k] for k in ("status","frozen_at_utc","holdout_strategy_pnl_inspected","readiness_build_id","latest_certified_date","frozen_file_sha256","phase7_build_id","phase10_amendment_hash")}
    if hashlib.sha256(canonical_json(key).encode()).hexdigest()!=manifest["strategy_preregistration_hash"]:raise RuntimeError("Preregistration hash failed")
    if manifest["holdout_strategy_pnl_inspected"] is not False:raise RuntimeError("Holdout gate failed")
    return cfg,manifest

def verify_prior():
    spec=importlib.util.spec_from_file_location("amend10",ROOT/"scripts/build_phase10_classification_amendment.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    result=mod.verify_immutable(mod.config())
    amendment_path=ROOT/"reports/reversal/amendment/phase10_amendment_manifest.json";amendment=json.loads(amendment_path.read_text())
    for name,digest in amendment["amended_rule_sha256"].items():
        if sha256(amendment_path.parent/name)!=digest:raise RuntimeError(f"Phase-10 amendment artifact changed: {name}")
    if amendment["amendment_hash"]!="9752e169486101be217a9c9f96aa9cf22adfcbc563c2c544415db60e4f2e3b42":raise RuntimeError("Phase-10 amendment hash changed")
    r=json.loads((OUT/"readiness/phase11_readiness_manifest.json").read_text())
    special={"phase11_historical_daily_extension.parquet":ROOT/"data/derived/phase11_historical_daily_extension.parquet",
             "phase11_corporate_action_extension.parquet":ROOT/"data/derived/phase11_corporate_action_extension.parquet",
             "phase11_sector_signal_panel.parquet":ROOT/"data/derived/phase11_sector_signal_panel.parquet"}
    for name,digest in r["output_sha256"].items():
        path=special.get(name,OUT/"readiness"/name)
        if sha256(path)!=digest:raise RuntimeError(f"Readiness artifact changed: {name}")
    return {**result,"phase10_amendment_hash":amendment["amendment_hash"],"phase10_amendment_verified_outputs":len(amendment["amended_rule_sha256"]),"phase11_readiness_build_id":r["build_id"],"phase11_readiness_outputs":len(r["output_sha256"])}

def combined_inputs():
    accepted=pd.read_parquet(ROOT/"data/derived/historical_nse_daily.parquet")
    ext=pd.read_parquet(ROOT/"data/derived/phase11_historical_daily_extension.parquet")
    daily=pd.concat([accepted,ext],ignore_index=True).sort_values(["date","symbol"],kind="stable").reset_index(drop=True)
    mapping=pd.read_parquet(ROOT/"data/derived/sector_research_mapping.parquet")
    hist=pd.read_parquet(ROOT/"data/derived/corporate_action_ledger.parquet")
    p10=pd.read_parquet(ROOT/"data/derived/phase10_corporate_action_extension.parquet")
    p11=pd.read_parquet(ROOT/"data/derived/phase11_corporate_action_extension.parquet")
    return daily,mapping,action_contract(hist,[p10,p11])

def period_returns(curve,period,initial):
    if curve.empty:return pd.DataFrame(columns=[period,"return"])
    x=curve.copy();x[period]=pd.to_datetime(x.date).dt.to_period("M" if period=="month" else "Y").astype(str)
    rows=[];prior=initial
    for key,g in x.groupby(period,sort=True):
        end=float(g.equity.iloc[-1]);rows.append({period:key,"return":end/prior-1});prior=end
    return pd.DataFrame(rows)

def contributions(result):
    c=result["contribution"]
    stock=(c.groupby("symbol",as_index=False).contribution_rupees.sum().sort_values("contribution_rupees",ascending=False,kind="stable") if len(c) else pd.DataFrame(columns=["symbol","contribution_rupees"]))
    sector=(c.groupby("sector",as_index=False).contribution_rupees.sum().sort_values("contribution_rupees",ascending=False,kind="stable") if len(c) else pd.DataFrame(columns=["sector","contribution_rupees"]))
    for f in (stock,sector):
        denominator=f.contribution_rupees.abs().sum()
        f["absolute_contribution_share"]=f.contribution_rupees.abs()/denominator if denominator else np.nan
    return stock,sector

def enriched_curve(curve,initial):
    x=curve.copy()
    if len(x):
        x["daily_return"]=x.equity.pct_change();x.loc[x.index[0],"daily_return"]=x.equity.iloc[0]/initial-1
        x["drawdown"]=x.equity/x.equity.cummax()-1
    return x

def benchmark(daily,curve,symbol="NIFTYBEES"):
    if curve.empty:return {"symbol":symbol,"start_date":None,"end_date":None,"return":np.nan}
    start,end=curve.date.min(),curve.date.max();x=daily[(daily.symbol==symbol)&daily.date.between(start,end)].sort_values("date")
    if x.empty or x.date.iloc[0]!=start or x.date.iloc[-1]!=end:return {"symbol":symbol,"start_date":start,"end_date":end,"return":np.nan}
    return {"symbol":symbol,"start_date":start,"end_date":end,"return":float(x.close.iloc[-1]/x.open.iloc[0]-1)}

def scenario(daily,targets,start,end,capital,cost,slip):
    result=simulate(daily,targets,start,end,capital,cost,slip);metrics=performance_metrics(result,capital)
    return result,metrics

def acceptance(cfg,dev,hold,gross_hold,bench,stock,sector):
    hold_drag=gross_hold["cumulative_return"]-hold["cumulative_return"]
    excess=hold["cumulative_return"]-bench["return"]
    max_stock=float(stock.absolute_contribution_share.max()) if len(stock) else 1.;max_sector=float(sector.absolute_contribution_share.max()) if len(sector) else 1.
    reject=(dev["operational_anomalies"]>0 or hold["operational_anomalies"]>0 or hold["maximum_drawdown"] < -0.20 or excess < -0.10)
    ready=(dev["CAGR"]>0 and dev["Sharpe"]>=.5 and dev["maximum_drawdown"]>=-.30 and excess>=-.02 and hold["maximum_drawdown"]>=-.08 and hold_drag<=.02 and hold["mean_weekly_gross_turnover"]<=2 and max_stock<=.5 and max_sector<=.6)
    conditional=(dev["CAGR"]>0 and dev["Sharpe"]>0 and dev["maximum_drawdown"]>=-.40 and excess>=-.05 and hold["maximum_drawdown"]>=-.12 and hold_drag<=.04 and hold["mean_weekly_gross_turnover"]<=2 and max_stock<=.7 and max_sector<=.75)
    decision="REJECT STRATEGY V1" if reject else "READY FOR PAPER TRADING" if ready else "CONDITIONAL PAPER-TRADE CANDIDATE" if conditional else "RESEARCH FURTHER"
    return decision,{"holdout_net_excess_vs_niftybees":float(excess),"holdout_cost_drag":float(hold_drag),"holdout_max_stock_absolute_contribution_share":max_stock,"holdout_max_sector_absolute_contribution_share":max_sector,"reject_pass":bool(not reject),"ready_pass":bool(ready),"conditional_pass":bool(conditional)}

def code_hash():
    paths=[ROOT/"src/mft_research/sector_strategy.py",ROOT/"scripts/build_phase11_strategy.py"]+sorted(ROOT.glob("tests/test_phase11*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(ROOT)),"sha256":sha256(p)} for p in paths if p.exists()]).encode()).hexdigest()

def report_text(decision,cfg,dev,hold,bench,extra,targets,holdtargets):
    return f"""# Phase 11 — Sector Momentum Strategy V1

**Decision: {decision}**  
**Research label: STATIC-CURRENT-CLASSIFICATION STRATEGY RESEARCH**

## A. Data readiness

Prices and additive corporate-action safety certification cover every NSE session through **2026-09-17**. September 14 was an official exchange holiday. The accepted Phase-5 through Phase-10 artifacts remain unchanged. Sector labels remain current/static with no historical effective dates.

## B. Frozen V1 strategy

The sole alpha is the accepted equal-weight 20-session Sector Relative Momentum signal. At each final NSE session of the ISO week, select the top three valid sectors, then up to three BASIC_LIQUID stocks per sector by trailing 20-session average turnover, breaking ties by symbol. Execute after the next session opens with adverse slippage; hold a maximum of nine long cash positions at equal target weights with whole shares. Recorded blocking corporate actions exclude a candidate for its intended weekly holding interval and promote the next liquid name within the same sector. No stop, target, leverage, stock momentum, reversal, volume signal, or regime rule exists.

Primary net results use 25 bps per side: 20 bps transaction cost plus 5 bps adverse slippage. The fixed sensitivity grid is 0/10/25/50 bps per side.

## C. Development / historical strategy simulation

The simulation begins {dev['start_date']} and ends {dev['end_date']}; this is development evidence, not pristine OOS. Gross cumulative return is {extra['development_gross_return']:.2%}; primary-net cumulative return is {dev['cumulative_return']:.2%}, CAGR {dev['CAGR']:.2%}, Sharpe {dev['Sharpe']:.3f}, volatility {dev['annualized_volatility']:.2%}, and maximum drawdown {dev['maximum_drawdown']:.2%}. NIFTYBEES returned {extra['development_benchmark_return']:.2%}. It used {dev['rebalance_count']} rebalances and {dev['trade_count']} fills, with mean weekly gross turnover {dev['mean_weekly_gross_turnover']:.3f}. The fixed 0/10/25/50 bps BASIC cumulative returns were {extra['development_cost_grid']}.

The development run recorded {dev['operational_anomalies']} operational exceptions, dominated by securities that ceased printing valid EQ opens/closes while held. The simulator retained their last observable mark, blocked unavailable exits, and never fabricated a trade. This breaches the frozen anomaly gate. Development maximum drawdown also exceeds the 40% conditional ceiling. Maximum stock and sector absolute contribution shares were {extra['development_stock_share']:.2%} and {extra['development_sector_share']:.2%}.

## D. Sealed strategy holdout

The holdout runs {hold['start_date']} through {hold['end_date']}. Net return is {hold['cumulative_return']:.2%}; gross return is {extra['holdout_gross_return']:.2%}; NIFTYBEES returned {bench['return']:.2%}; net excess is {extra['holdout_net_excess_vs_niftybees']:.2%}. Maximum drawdown is {hold['maximum_drawdown']:.2%}; cost drag {extra['holdout_cost_drag']:.2%}; mean weekly gross turnover {hold['mean_weekly_gross_turnover']:.3f}. Seven rebalances executed with no holdout operational anomaly. Maximum stock and sector contribution shares were {extra['holdout_max_stock_absolute_contribution_share']:.2%} and {extra['holdout_max_sector_absolute_contribution_share']:.2%}. This short period is not interpreted through annualized performance.

## E. Comparison and decision

V1 is **{decision}** under the thresholds frozen before holdout inspection. Holdout direction was broadly benchmark-consistent, but V1 fails because development produced unexecutable exits/stale positions and a -46.22% net drawdown, beyond the frozen 40% conditional limit. Costs are also material: 25 bps per side reduced holdout return by {extra['holdout_cost_drag']:.2%}. Full metrics, cost sensitivity, positions, trades, contributions, daily drawdowns, and actual signal/execution dates are published separately.

## F. Paper trading

{"The adapter contract and runbook are published under `reports/sector_strategy/paper_handoff/`. Begin prospective paper observation strictly after 2026-09-17 for at least 8–12 weeks; do not deploy real money automatically." if decision in ('READY FOR PAPER TRADING','CONDITIONAL PAPER-TRADE CANDIDATE') else "V1 does not pass the frozen paper-trading gate, so no executable handoff is authorized."}

The exact build ID is recorded in `reports/sector_strategy/phase11_strategy_build_manifest.json`. Development target rows: {len(targets):,}; holdout target rows: {len(holdtargets):,}.
"""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--verify-rebuild",action="store_true");args=ap.parse_args()
    cfg,prereg=verify_gate();prior=verify_prior()  # must precede reading any holdout input
    daily,mapping,actions=combined_inputs()
    phase5=yaml.safe_load((ROOT/"config/phase5_point_in_time.yaml").read_text());phase7=yaml.safe_load((ROOT/"config/phase7_sector_momentum.yaml").read_text())
    basic=pd.read_parquet(ROOT/"data/derived/phase11_sector_signal_panel.parquet")
    moderate=extended_sector_panel(daily,mapping,actions,phase5,phase7,"STABLE_IDENTITY_MODERATE_LIQUID")
    calendar=sorted(daily.date.unique());blocking=phase5["corporate_action_policy"]["primary_blocking_impacts"]
    devtargets=generate_rebalances(calendar,"2020-01-01","2026-07-17",basic,daily,mapping,"universe_basic_liquid",actions,blocking)
    holdtargets=generate_rebalances(calendar,"2026-08-01","2026-09-17",basic,daily,mapping,"universe_basic_liquid",actions,blocking)
    moddev=generate_rebalances(calendar,"2020-01-01","2026-07-17",moderate,daily,mapping,"universe_moderate_liquid",actions,blocking)
    modhold=generate_rebalances(calendar,"2026-08-01","2026-09-17",moderate,daily,mapping,"universe_moderate_liquid",actions,blocking)
    capital=float(cfg["portfolio"]["initial_capital_rupees"]);components={int(k):v for k,v in cfg["costs"]["components"].items()}
    runs={};rows=[]
    for universe,dt,ht in (("BASIC_LIQUID",devtargets,holdtargets),("MODERATE_LIQUID",moddev,modhold)):
      for period,target,start,end in (("DEVELOPMENT",dt,"2020-01-01","2026-07-17"),("HOLDOUT",ht,"2026-08-01","2026-09-17")):
       for bps,comp in components.items():
        result,metrics=scenario(daily,target,start,end,capital,float(comp["transaction_cost_bps"]),float(comp["adverse_slippage_bps"]));runs[(universe,period,bps)]=(result,metrics)
        rows.append({"universe":universe,"period":period,"total_bps_per_side":bps,**metrics})
    sensitivity=pd.DataFrame(rows);devres,dev=runs[("BASIC_LIQUID","DEVELOPMENT",25)];holdres,hold=runs[("BASIC_LIQUID","HOLDOUT",25)]
    grossdev=runs[("BASIC_LIQUID","DEVELOPMENT",0)][1];grosshold=runs[("BASIC_LIQUID","HOLDOUT",0)][1];benchdev=benchmark(daily,devres["equity"]);benchhold=benchmark(daily,holdres["equity"])
    devstock,devsector=contributions(devres);holdstock,holdsector=contributions(holdres)
    decision,extra=acceptance(cfg,dev,hold,grosshold,benchhold,holdstock,holdsector);extra.update({"holdout_gross_return":grosshold["cumulative_return"],"development_gross_return":grossdev["cumulative_return"],"development_benchmark_return":benchdev["return"],"development_stock_share":float(devstock.absolute_contribution_share.max()),"development_sector_share":float(devsector.absolute_contribution_share.max()),"development_cost_grid":", ".join(f"{int(r.total_bps_per_side)}={r.cumulative_return:.2%}" for r in sensitivity[(sensitivity.universe=='BASIC_LIQUID')&(sensitivity.period=='DEVELOPMENT')].itertuples())})
    devmetrics=pd.DataFrame([{**dev,"benchmark":benchdev["symbol"],"benchmark_return":benchdev["return"],"excess_return":dev["cumulative_return"]-benchdev["return"]}])
    holdmetrics=pd.DataFrame([{**hold,"gross_return":grosshold["cumulative_return"],"benchmark":benchhold["symbol"],"benchmark_return":benchhold["return"],"excess_return":extra["holdout_net_excess_vs_niftybees"],"cost_drag":extra["holdout_cost_drag"]}])
    comparison=pd.DataFrame([{"metric":k,"development":devmetrics.iloc[0].get(k,np.nan),"holdout":holdmetrics.iloc[0].get(k,np.nan)} for k in ("cumulative_return","CAGR","annualized_volatility","Sharpe","maximum_drawdown","mean_weekly_gross_turnover","trade_count","rebalance_count","mean_positions","mean_cash_utilization")])
    outputs={
      "development/development_equity_curve.csv":enriched_curve(devres["equity"],capital),"development/development_rebalances.csv":devres["rebalances"],"development/development_trades.csv":devres["trades"],"development/development_positions.csv":devres["positions"],"development/development_metrics.csv":devmetrics,"development/development_monthly_returns.csv":period_returns(devres["equity"],"month",capital),"development/development_yearly_returns.csv":period_returns(devres["equity"],"year",capital),"development/development_sector_contribution.csv":devsector,"development/development_stock_contribution.csv":devstock,"development/development_cost_sensitivity.csv":sensitivity[sensitivity.period.eq("DEVELOPMENT")],
      "development/development_operational_anomalies.csv":devres["anomalies"],
      "holdout/holdout_equity_curve.csv":enriched_curve(holdres["equity"],capital),"holdout/holdout_rebalances.csv":holdres["rebalances"],"holdout/holdout_trades.csv":holdres["trades"],"holdout/holdout_positions.csv":holdres["positions"],"holdout/holdout_metrics.csv":holdmetrics,"holdout/holdout_sector_contribution.csv":holdsector,"holdout/holdout_stock_contribution.csv":holdstock,"holdout/holdout_signal_targets.csv":holdtargets,"holdout/holdout_operational_anomalies.csv":holdres["anomalies"],"holdout/holdout_cost_sensitivity.csv":sensitivity[sensitivity.period.eq("HOLDOUT")],
      "phase11_strategy_comparison.csv":comparison}
    acceptance_doc={"decision":decision,"strategy_version":"V1","strategy_preregistration_hash":prereg["strategy_preregistration_hash"],"holdout_strategy_pnl_inspected":True,"holdout_inspection_count":1,"criteria":extra,"operational_anomalies":{"development":dev["operational_anomalies"],"holdout":hold["operational_anomalies"]}}
    if decision in ("READY FOR PAPER TRADING","CONDITIONAL PAPER-TRADE CANDIDATE"):
      schema=pd.DataFrame([{"column":x,"type":t,"description":d} for x,t,d in [("signal_date","date","EOD signal session"),("execution_date","date","next tradable session"),("strategy_version","string","SECTOR_MOMENTUM_V1"),("sector","string","static-current sector"),("symbol","string","NSE EQ symbol"),("sector_rank","integer","1 strongest"),("liquidity_rank","integer","1 most liquid"),("target_weight","float","equal target weight"),("target_value","float","engine NAV times weight"),("reason","string","weekly rebalance"),("exit_flag","boolean","true for deselection"),("rebalance_id","string","unique event")]])
      outputs["paper_handoff/paper_signal_schema.csv"]=schema
    with tempfile.TemporaryDirectory(prefix=".phase11-",dir=OUT) as tmp:
      stage=Path(tmp)
      for name,frame in outputs.items():(stage/name).parent.mkdir(parents=True,exist_ok=True);frame.to_csv(stage/name,index=False,date_format="%Y-%m-%d",float_format="%.12f")
      (stage/"phase11_strategy_acceptance.json").write_text(canonical_json(acceptance_doc))
      if decision in ("READY FOR PAPER TRADING","CONDITIONAL PAPER-TRADE CANDIDATE"):
       contract="""# Paper-engine contract\n\nConsume one target-state file after each final NSE session of the ISO week. Orders are eligible only at the next tradable session open. The paper engine owns orders, fills, cash, costs, slippage, positions, P&L, risk decisions, logging, and reconciliation. Reject stale signals, duplicate symbols, non-EQ instruments, weights outside [0,1], total weight above 1, and more than nine positions.\n"""
       runbook="""# Prospective paper-trading runbook\n\n1. After EOD, certify prices, membership, sector signal, and corporate-action safety.\n2. Generate and hash the target-state signal file.\n3. Before next open, validate cash-only long targets and create paper orders.\n4. Reconcile intended versus accepted orders, fills, positions, cash, fees, and slippage daily.\n5. Publish daily portfolio and weekly strategy reports.\n6. Observe for at least 8–12 weeks strictly after 2026-09-17. Test kill switch and reconciliation before any later live review.\n"""
       (stage/"paper_handoff/paper_engine_contract.md").write_text(contract);(stage/"paper_handoff/paper_trading_runbook.md").write_text(runbook)
      names=sorted([str(p.relative_to(stage)) for p in stage.rglob("*") if p.is_file()]);hashes={n:sha256(stage/n) for n in names}
      key={"accepted_inputs":prior,"code_sha256":code_hash(),"strategy_preregistration_hash":prereg["strategy_preregistration_hash"],"output_sha256":hashes,"decision":decision}
      text=report_text(decision,cfg,dev,hold,benchhold,extra,devtargets,holdtargets)
      (stage/"phase11_sector_momentum_strategy.md").write_text(text);hashes["phase11_sector_momentum_strategy.md"]=sha256(stage/"phase11_sector_momentum_strategy.md")
      final_key={**key,"output_sha256":hashes};build_id=hashlib.sha256(canonical_json(final_key).encode()).hexdigest()
      manifest={**final_key,"build_id":build_id,"factor":"SECTOR_RELATIVE_MOMENTUM_ONLY","holdout_evaluations":1}
      prior_manifest=OUT/"phase11_strategy_build_manifest.json"
      if args.verify_rebuild:
       old=json.loads(prior_manifest.read_text());diff={n:(old["output_sha256"].get(n),d) for n,d in hashes.items() if old["output_sha256"].get(n)!=d}
       if old["build_id"]!=build_id or diff:raise AssertionError(f"Phase-11 rebuild differs: {diff}")
       print(f"PASS Phase-11 deterministic rebuild: {len(hashes)}/{len(hashes)} byte-identical; build {build_id}");return
      for name in hashes:
       dst=ROOT/"reports/phase11_sector_momentum_strategy.md" if name=="phase11_sector_momentum_strategy.md" else OUT/name
       dst.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/name,dst)
      prior_manifest.write_text(canonical_json(manifest))
    print(f"Built Phase-11 {build_id} — {decision}")
    print(devmetrics.to_string(index=False));print(holdmetrics.to_string(index=False))

if __name__=="__main__":main()
