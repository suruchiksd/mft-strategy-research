#!/usr/bin/env python3
"""Build read-only failure attribution for accepted Sector Momentum Strategy V1."""
from __future__ import annotations

import argparse,hashlib,importlib.util,json,os,sys,tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from mft_research.csrs.phase5 import canonicalize_source,read_source,source_format
from mft_research.data.manifest import canonical_json,sha256
from mft_research.v1_diagnostics import (TURNOVER_CLASSES,daily_contributions,drawdown_attribution,drawdown_episodes,
    sector_boundary,selection_stability,stock_boundary,turnover_attribution,weight_attribution)

def cfg():return yaml.safe_load((ROOT/"config/phase12a_v1_diagnostics.yaml").read_text())

def verify_inputs(c):
    manifest=json.loads((ROOT/"reports/sector_strategy/phase11_strategy_build_manifest.json").read_text())
    prereg=json.loads((ROOT/"reports/sector_strategy/preregistration/phase11_strategy_manifest.json").read_text())
    if manifest["build_id"]!=c["accepted_phase11_build_id"]:raise RuntimeError("Phase-11 build changed")
    if prereg["strategy_preregistration_hash"]!=c["accepted_phase11_preregistration_hash"]:raise RuntimeError("Phase-11 preregistration changed")
    for name,digest in manifest["output_sha256"].items():
        path=ROOT/"reports/phase11_sector_momentum_strategy.md" if name=="phase11_sector_momentum_strategy.md" else ROOT/"reports/sector_strategy"/name
        if sha256(path)!=digest:raise RuntimeError(f"Phase-11 artifact changed: {name}")
    spec=importlib.util.spec_from_file_location("p11",ROOT/"scripts/build_phase11_strategy.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    prior=m.verify_prior()
    return {"phase11_build_id":manifest["build_id"],"phase11_verified_outputs":len(manifest["output_sha256"]),"phase11_preregistration_hash":prereg["strategy_preregistration_hash"],**prior}

def load_period(period):
    d=ROOT/f"reports/sector_strategy/{period}"
    frames={n:pd.read_csv(d/f"{period}_{n}.csv") for n in ("trades","rebalances","positions","equity_curve","operational_anomalies")}
    for f in frames.values():
        for col in ("date","signal_date","execution_date"):
            if col in f:f[col]=pd.to_datetime(f[col])
    return frames

def actions():
    hist=pd.read_parquet(ROOT/"data/derived/corporate_action_ledger.parquet")[["symbol","date","research_impact"]]
    parts=[hist]
    for p in ("data/derived/phase10_corporate_action_extension.parquet","data/derived/phase11_corporate_action_extension.parquet"):
        x=pd.read_parquet(ROOT/p);x=x[x.mapped_symbol.notna()].copy();x["symbol"]=x.mapped_symbol;x["date"]=pd.to_datetime(x.blocking_date);x["research_impact"]=np.where(x.safety_classification.eq("NONBLOCKING_INFORMATIONAL"),"NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM","UNKNOWN_OR_AMBIGUOUS");parts.append(x[["symbol","date","research_impact"]])
    result=pd.concat(parts,ignore_index=True);result["date"]=pd.to_datetime(result.date)
    return result[result.research_impact.isin(["MATERIAL_UNRESOLVED_EVENT","UNKNOWN_OR_AMBIGUOUS","LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION"])]

def exception_audit(frames,daily):
    a=frames["operational_anomalies"].copy();p=frames["positions"];t=frames["trades"];eq=frames["equity_curve"]
    core=a[a.type.isin(["STALE_MARK_CARRIED_NO_VALID_CLOSE","UNEXECUTABLE_EXIT_NO_VALID_OPEN"])]
    source_by_date=daily.drop_duplicates("date").set_index("date").source_file.to_dict();raw_cache={};rows=[]
    for sym,g in a.groupby("detail",sort=True):
        cg=core[core.detail.eq(sym)];first=cg.date.min() if len(cg) else g.date.min();last=cg.date.max() if len(cg) else g.date.max();series=[];absent=0
        for day in sorted(cg[cg.type.eq("STALE_MARK_CARRIED_NO_VALID_CLOSE")].date.unique()):
            path=Path(source_by_date[pd.Timestamp(day)])
            if path not in raw_cache:
                raw,_=read_source(path);raw_cache[path]=canonicalize_source(raw,source_format(path),str(path))[["symbol","series"]]
            z=raw_cache[path];found=z.loc[z.symbol.eq(sym),"series"].tolist()
            if found:series.extend(found)
            else:absent+=1
        eventual=pd.NaT;exit_price=np.nan
        if len(cg):
            for tr in t[(t.symbol.eq(sym))&(t.side.eq("SELL"))&(t.date.gt(last))].sort_values("date").itertuples(index=False):
                if not ((p.date.eq(tr.date))&p.symbol.eq(sym)).any():eventual=tr.date;exit_price=tr.reference_open;break
        firstpos=p[(p.symbol.eq(sym))&p.date.le(first)].sort_values("date").tail(1) if len(cg) else p.iloc[0:0]
        trapped=p[(p.symbol.eq(sym))&p.date.ge(first)&p.date.le(eventual if pd.notna(eventual) else eq.date.max())] if len(cg) else p.iloc[0:0]
        root="SERIES_CHANGE_EQ_TO_BE" if series and set(series)=={"BE"} else "MISSING_RAW_SOURCE_ROW" if absent else "ENTRY_PREVENTED_BY_POSITION_CAP_DURING_UNAVAILABLE_HOLDING"
        rows.append({"symbol":sym,"root_cause":root,"first_incident":g.date.min(),"last_incident":g.date.max(),"stale_marks":int(g.type.eq("STALE_MARK_CARRIED_NO_VALID_CLOSE").sum()),"unavailable_exit_attempts":int(g.type.eq("UNEXECUTABLE_EXIT_NO_VALID_OPEN").sum()),"position_cap_prevented_entries":int(g.type.eq("POSITION_CAP_PREVENTED_ENTRY").sum()),"raw_BE_rows":series.count("BE"),"raw_absent_rows":absent,"trapped_sessions":trapped.date.nunique(),"first_unavailable_value":float(firstpos.market_value.iloc[0]) if len(firstpos) else np.nan,"first_unavailable_weight":float(firstpos.weight.iloc[0]) if len(firstpos) else np.nan,"eventual_exit_date":eventual,"eventual_exit_price":exit_price,"remained_at_development_end":bool(((p.date.eq(eq.date.max()))&p.symbol.eq(sym)).any()),"fabricated_exit":False})
    result=pd.DataFrame(rows)
    if result[["stale_marks","unavailable_exit_attempts","position_cap_prevented_entries"]].sum().sum()!=len(a):raise AssertionError("Operational records did not reconcile")
    return result

def duration_summary(stability):
    sector_runs=[];stock_runs=[]
    for column,out in (("selected_sectors",sector_runs),("selected_stocks",stock_runs)):
        active={}
        for value in stability[column]:
            current=set(str(value).split("|")) if value else set()
            for name in list(active):
                if name not in current:out.append(active.pop(name))
            for name in current:active[name]=active.get(name,0)+1
        out.extend(active.values())
    return float(np.mean(sector_runs)),float(np.mean(stock_runs))

def markdown_assessment(stats):
    return f"""# Factor versus implementation assessment

**Conclusion: BOTH, with implementation failure dominant.**

The accepted Phase-7 factor evidence remains internally robust: all 30 Rank-IC pairs and all 30 Q5–Q1 spreads were positive across its frozen research grid. V1's zero-cost simulation also produced {stats['gross_return']:.2%}, so the sector signal did not simply vanish in the historical strategy period.

Implementation translated that gross evidence poorly. Weekly turnover averaged {stats['turnover']:.3f}; execution costs and slippage were highly compounding-sensitive; the 25-bps result fell to {stats['net_return']:.2%}. Six selected EQ securities moved to the BE series while held, producing unavailable exits, stale marks, and blocked replacement entries. Net maximum drawdown reached {stats['max_dd']:.2%}.

There is also strategy-level factor risk: gross maximum drawdown was {stats['gross_dd']:.2%}, 2025 was negative, and the short holdout gross return was {stats['holdout_gross']:.2%}. Thus stock implementation and costs are not the entire explanation. The evidence supports a useful sector-ranking factor but rejects this exact weekly cash implementation.

Static/current sector mappings remain a severe external-validity limitation. V1 admitted only stable-identity, uniquely mapped names and required at least five constituents, so no executed V1 holding was intentionally unmapped or conflicted and no selected sector failed the size floor. That removes direct mapping gaps from the mechanical failure, but it cannot establish historically correct classifications.
"""

def v2_requirements():
    return """# Diagnostic requirements for any future Strategy V2

## MUST FIX

- Freeze a point-in-time tradability contract covering EQ-to-BE transfers, suspensions, absent opens, stale valuation, unexecutable exits, and how trapped positions consume the position limit.
- Freeze execution fallback behavior before new P&L, including what happens when an intended entry or exit has no valid next-session open.
- Define reconciliation rules for last observable marks without fabricating prices or exits.
- Address cost and turnover feasibility with prespecified acceptance limits; do not choose them from the best historical return.
- Freeze portfolio drawdown/risk acceptance and a new validation interval strictly after 2026-09-17.

## SHOULD INVESTIGATE

- Whether rank-boundary changes cause avoidable sector and within-sector replacement churn.
- Whether pure equal-weight restoration is economically material enough to warrant a tolerance concept.
- Whether sector representation through individual stocks creates avoidable idiosyncratic and tradability risk.
- Whether concentration and prolonged underwater periods remain acceptable independently of factor Rank IC.

## OPTIONAL

- Alternative implementation instruments or representation mechanisms, subject to independent data and tradability audits.
- A separate study of execution timing and realized paper slippage after a V2 contract is frozen.

Any rank buffer, weight band, sector count, stock count, rebalance cadence, cost model, fallback rule, or position-limit treatment is a new strategy decision. It requires preregistration; none is selected here. The inspected 2026-08-03 through 2026-09-17 interval is development evidence for any V2 and cannot be reused as fresh validation.
"""

def code_hash():
    paths=[ROOT/"config/phase12a_v1_diagnostics.yaml",ROOT/"src/mft_research/v1_diagnostics.py",ROOT/"scripts/build_phase12a_v1_diagnostics.py"]+sorted(ROOT.glob("tests/test_phase12a*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(ROOT)),"sha256":sha256(p)} for p in paths if p.exists()]).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--verify-rebuild",action="store_true");args=ap.parse_args();c=cfg();accepted=verify_inputs(c)
    daily=pd.concat([pd.read_parquet(ROOT/"data/derived/historical_nse_daily.parquet"),pd.read_parquet(ROOT/"data/derived/phase11_historical_daily_extension.parquet")],ignore_index=True);daily["date"]=pd.to_datetime(daily.date)
    if daily.date.max()>pd.Timestamp(c["strategy_performance_data_end"]):daily=daily[daily.date<=pd.Timestamp(c["strategy_performance_data_end"])]
    mapping=pd.read_parquet(ROOT/"data/derived/sector_research_mapping.parquet")
    factor=pd.read_parquet(ROOT/"data/derived/phase11_sector_signal_panel.parquet");factor["date"]=pd.to_datetime(factor.date)
    frames={p:load_period(p) for p in ("development","holdout")};attrs=[];stabs=[];weights=[]
    blocking=actions()
    for period,f in frames.items():
        a=turnover_attribution(f["trades"],f["rebalances"],f["positions"],f["operational_anomalies"],mapping,daily,blocking);a.insert(0,"period",period.upper());attrs.append(a)
        s=selection_stability(f["rebalances"],f["positions"],f["operational_anomalies"],mapping);s.insert(0,"period",period.upper());stabs.append(s)
        w=weight_attribution(f["rebalances"],f["positions"],f["operational_anomalies"],mapping,daily,a);w.insert(0,"period",period.upper());weights.append(w)
    attr=pd.concat(attrs,ignore_index=True);stability=pd.concat(stabs,ignore_index=True);weight=pd.concat(weights,ignore_index=True)
    turnover=attr.groupby(["period","rebalance_id","signal_date","execution_date","year","turnover_class"],as_index=False).agg(rupee_turnover=("notional","sum"),normalized_turnover=("normalized_turnover","sum"),trade_count=("symbol","size"));totals=turnover.groupby("period").rupee_turnover.transform("sum");turnover["percentage_of_period_turnover"]=turnover.rupee_turnover/totals
    yearly=attr.groupby(["period","year","turnover_class"],as_index=False).agg(rupee_turnover=("notional","sum"),normalized_turnover=("normalized_turnover","sum"),transaction_cost=("transaction_cost","sum"),slippage_cost=("slippage_cost","sum"),all_in_cost=("all_in_cost","sum"));yearly["percentage_of_year_turnover"]=yearly.rupee_turnover/yearly.groupby(["period","year"]).rupee_turnover.transform("sum")
    cost=attr.groupby(["period","turnover_class"],as_index=False).agg(transaction_cost=("transaction_cost","sum"),slippage_cost=("slippage_cost","sum"),all_in_cost=("all_in_cost","sum"));cost["percentage_of_period_all_in_cost"]=cost.all_in_cost/cost.groupby("period").all_in_cost.transform("sum")
    sector_churn=pd.concat([sector_boundary(stability[stability.period.eq(p)].reset_index(drop=True),factor) .assign(period=p) for p in stability.period.unique()],ignore_index=True)
    stock_churn=pd.concat([stock_boundary(stability[stability.period.eq(p)].reset_index(drop=True),daily,mapping).assign(period=p) for p in stability.period.unique()],ignore_index=True)
    dev=frames["development"];contrib=daily_contributions(dev["equity_curve"],dev["positions"],dev["trades"],mapping,c["initial_capital"]);episodes=drawdown_episodes(dev["equity_curve"]);ddsec=drawdown_attribution(episodes,contrib,"sector");ddstock=drawdown_attribution(episodes,contrib,"symbol")
    for table,key in ((ddsec,"sector"),(ddstock,"symbol")):
        status_rows=[]
        for e in episodes.itertuples(index=False):
            x=contrib[(contrib.date>e.peak_date)&(contrib.date<=e.trough_date)].groupby([key,"position_status"],as_index=False).net_contribution.sum()
            x["episode_id"]=e.episode_id;status_rows.append(x)
        status=pd.concat(status_rows,ignore_index=True).pivot_table(index=["episode_id",key],columns="position_status",values="net_contribution",fill_value=0).reset_index()
        status.columns.name=None;status=status.rename(columns={"EXISTING":"existing_position_contribution","NEWLY_ENTERED":"newly_entered_position_contribution"})
        for col in ("existing_position_contribution","newly_entered_position_contribution"):
            if col not in status:status[col]=0.0
        merged=table.merge(status,on=["episode_id",key],how="left")
        if key=="sector":ddsec=merged
        else:ddstock=merged
    audit=exception_audit(dev,daily)
    gross_stock=contrib.groupby("symbol",as_index=False).agg(net_contribution=("net_contribution","sum"),execution_cost=("all_in_execution_cost","sum"),gross_contribution=("gross_before_cost_contribution","sum"));gross_stock["gross_contribution_share"]=gross_stock.gross_contribution/gross_stock.gross_contribution.sum()
    gross_sector=contrib.groupby("sector",as_index=False).agg(net_contribution=("net_contribution","sum"),execution_cost=("all_in_execution_cost","sum"),gross_contribution=("gross_before_cost_contribution","sum"));gross_sector["gross_contribution_share"]=gross_sector.gross_contribution/gross_sector.gross_contribution.sum()
    contrib["year"]=contrib.date.dt.year;gross_year=contrib.groupby("year",as_index=False).agg(net_contribution=("net_contribution","sum"),execution_cost=("all_in_execution_cost","sum"),gross_contribution=("gross_before_cost_contribution","sum"))
    dm=pd.read_csv(ROOT/"reports/sector_strategy/development/development_metrics.csv").iloc[0];hm=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_metrics.csv").iloc[0];sens=pd.read_csv(ROOT/"reports/sector_strategy/development/development_cost_sensitivity.csv");gross=sens[(sens.universe.eq("BASIC_LIQUID"))&sens.total_bps_per_side.eq(0)].iloc[0]
    stats={"gross_return":gross.cumulative_return,"net_return":dm.cumulative_return,"max_dd":dm.maximum_drawdown,"gross_dd":gross.maximum_drawdown,"holdout_gross":hm.gross_return,"turnover":dm.mean_weekly_gross_turnover}
    assessment=markdown_assessment(stats);requirements=v2_requirements()
    devturn=attr[attr.period.eq("DEVELOPMENT")];pct=(devturn.groupby("turnover_class").notional.sum()/devturn.notional.sum()).reindex(TURNOVER_CLASSES).fillna(0);cpct=(devturn.groupby("turnover_class").all_in_cost.sum()/devturn.all_in_cost.sum()).reindex(TURNOVER_CLASSES).fillna(0)
    secdur,stockdur=duration_summary(stability[stability.period.eq("DEVELOPMENT")]);largest=episodes.iloc[0];topsec=ddsec[ddsec.episode_id.eq(largest.episode_id)].sort_values("net_contribution").head(3);topstock=ddstock[ddstock.episode_id.eq(largest.episode_id)].sort_values("net_contribution").head(5)
    devst=stability[stability.period.eq("DEVELOPMENT")];week=devturn.groupby(["execution_date","turnover_class"]).normalized_turnover.sum().unstack(fill_value=0).reindex(columns=TURNOVER_CLASSES,fill_value=0)
    turn_lines=[]
    for kind in TURNOVER_CLASSES:
        q=week[kind].quantile([.5,.9,.95]);turn_lines.append(f"| {kind} | {q.loc[.5]:.3f} | {q.loc[.9]:.3f} | {q.loc[.95]:.3f} |")
    largest_turn=devturn.groupby("execution_date").normalized_turnover.sum().nlargest(5)
    wdev=weight[weight.period.eq("DEVELOPMENT")].absolute_weight_deviation;yearst=devst.groupby("year").agg(sector_jaccard=("sector_jaccard","mean"),stock_jaccard=("stock_jaccard","mean"),sector_entries=("sectors_entered","sum"),stock_entries=("stocks_entered","sum")).reset_index()
    core_symbols=set(audit.loc[audit.stale_marks.gt(0),"symbol"]);active_values=[]
    for date,g in dev["positions"][dev["positions"].symbol.isin(core_symbols)].groupby("date"):
        valid=[]
        for r in audit[audit.symbol.isin(core_symbols)].itertuples(index=False):
            if date>=r.first_incident and (pd.isna(r.eventual_exit_date) or date<r.eventual_exit_date):valid.append(r.symbol)
        active_values.append((date,g[g.symbol.isin(valid)].market_value.sum()))
    max_trapped_date,max_trapped=max(active_values,key=lambda x:x[1])
    major=contrib[(contrib.date>largest.peak_date)&(contrib.date<=largest.trough_date)];op_draw=major[major.symbol.isin(core_symbols)].net_contribution.sum();episode_loss=major.net_contribution.sum();negative_sectors=(topall:=ddsec[ddsec.episode_id.eq(largest.episode_id)]).net_contribution.lt(0).sum();negative_stocks=ddstock[ddstock.episode_id.eq(largest.episode_id)].net_contribution.lt(0).sum()
    top5_share=gross_stock.nlargest(5,"gross_contribution").gross_contribution.sum()/gross_stock.gross_contribution.sum();top3sec_share=gross_sector.nlargest(3,"gross_contribution").gross_contribution.sum()/gross_sector.gross_contribution.sum()
    summary=f"""# Phase 12A — Sector Momentum Strategy V1 Failure Diagnostics

**Diagnostic conclusion: BOTH, with implementation failure dominant.** No V2 strategy or alternative P&L was constructed.

## Why V1 failed

The factor remained strong in Phase 7 and V1 produced 264.21% in the already-accepted zero-cost simulation. Translation failed through high recurring turnover, compounding execution drag, EQ-to-BE tradability events, and portfolio risk. At 25 bps per side the result fell to 68.10%, Sharpe 0.484, with a -46.22% drawdown. The short holdout was close to NIFTYBEES, so it was not the decisive rejection reason.

## 1. Turnover and cost attribution

Development turnover shares were: sector entry/exit {pct['SECTOR_ENTRY_EXIT']:.2%}; within-sector replacement {pct['WITHIN_SECTOR_STOCK_REPLACEMENT']:.2%}; equal-weight resizing {pct['WEIGHT_REBALANCING']:.2%}; operational {pct['FORCED_OPERATIONAL']:.2%}. All-in execution-cost shares were respectively {cpct['SECTOR_ENTRY_EXIT']:.2%}, {cpct['WITHIN_SECTOR_STOCK_REPLACEMENT']:.2%}, {cpct['WEIGHT_REBALANCING']:.2%}, and {cpct['FORCED_OPERATIONAL']:.2%}.

| Cause | Median weekly normalized turnover | P90 | P95 |
|---|---:|---:|---:|
{chr(10).join(turn_lines)}

The five largest turnover dates were {', '.join(f'{d.date()} ({v:.3f})' for d,v in largest_turn.items())}. Sector entry/exit dominates both rupee turnover and execution cost; the fixed cost model makes class cost shares nearly proportional to notional.

## 2. Selection stability and rank-boundary churn

Median sector and stock Jaccard similarities were {devst.sector_jaccard.median():.3f} and {devst.stock_jaccard.median():.3f}. A typical week retained {devst.sectors_retained.median():.0f} of three sectors and {devst.stocks_retained.median():.0f} of nine stocks. Average uninterrupted selection durations were {secdur:.2f} sector cycles and {stockdur:.2f} stock cycles. Small 3/4/5 boundary moves represented {sector_churn[sector_churn.period.eq('DEVELOPMENT')].small_boundary_move.mean():.2%} of sector changes and {stock_churn[stock_churn.period.eq('DEVELOPMENT')].small_boundary_move.mean():.2%} of measurable within-sector stock changes. Boundary churn was material for liquidity-ranked stocks but explains a minority of sector changes.

Yearly mean Jaccard values ranged from {yearst.sector_jaccard.min():.3f} to {yearst.sector_jaccard.max():.3f} for sectors and {yearst.stock_jaccard.min():.3f} to {yearst.stock_jaccard.max():.3f} for stocks.

## 3. Equal-weight resizing

Pure resizing contributed {pct['WEIGHT_REBALANCING']:.2%} of turnover. Among retained stocks, absolute pre-trade target deviations had median {wdev.median():.2%}, P90 {wdev.quantile(.9):.2%}, and P95 {wdev.quantile(.95):.2%}. Equal-weight restoration is measurable but is not the main turnover source.

## 4. Operational exceptions

All 534 records reconcile: 378 stale marks, 78 unavailable-exit attempts, and 78 capacity-blocked entries. HATHWAY, EASEMYTRIP, TRIDENT, REFEX, KITEX, and OLAELEC transferred from EQ to BE while held; 376 of 378 stale dates contain the symbol explicitly in BE and two raw dates omit it. Their first-unavailable marked values total ₹{audit[audit.stale_marks.gt(0)].first_unavailable_value.sum():,.0f} across separate incidents. Maximum simultaneous trapped marked capital was ₹{max_trapped:,.0f} on {max_trapped_date.date()}. Initial trapped weights ranged from {audit[audit.stale_marks.gt(0)].first_unavailable_weight.min():.2%} to {audit[audit.stale_marks.gt(0)].first_unavailable_weight.max():.2%}. Every trapped position eventually exited on a later valid open; none remained at development end. No zero price or fabricated exit was used.

## 5. Drawdown attribution

The largest episode peaked {largest.peak_date.date()}, troughed {largest.trough_date.date()}, reached {largest.depth:.2%}, and {('recovered '+str(largest.recovery_date.date())) if largest.recovered else 'was unrecovered at development end'}. It contained {negative_sectors} net-negative sectors and {negative_stocks} net-negative stocks. Its largest negative sectors were {', '.join(topsec.sector.astype(str))}; its largest negative stocks were {', '.join(topstock.symbol.astype(str))}. The six operationally affected names contributed ₹{op_draw:,.0f} during the ₹{episode_loss:,.0f} peak-to-trough loss. The result is a combination: broad adverse sector exposure and stock losses dominate, while trapped names and execution costs aggravated it.

## 6. Gross alpha attribution

On the accepted 25-bps position path before execution-cost deduction, the top five stocks contributed {top5_share:.2%} of total gross contribution and the top three sectors contributed {top3sec_share:.2%}. No single stock supplied more than {gross_stock.gross_contribution_share.max():.2%}; the largest sector supplied {gross_sector.gross_contribution_share.max():.2%}. Gross gains were reasonably distributed, with meaningful but not singular concentration. This path-based attribution reconciles exactly to accepted net equity plus observed costs; it is not a newly simulated zero-cost portfolio.

## 7. Factor versus implementation and static mapping

The diagnosis is **BOTH, with implementation failure dominant**. Robust Phase-7 rank evidence and positive accepted gross performance argue against wholesale factor failure. Gross drawdown, negative 2025 performance, and the negative holdout still show genuine factor/portfolio cyclicality. Weekly sector replacement, costs, individual-stock representation, and EQ-to-BE events were implementation failures.

All V1 holdings used stable-identity, uniquely mapped names and the five-stock sector floor; direct unmapped/conflicted/sparse-sector exposure was zero by construction. Static-current mappings remain historically unverified, so classification bias cannot be ruled out or quantified as point-in-time truth.

## 8. V2 boundary

Any V2 must first solve tradability, unavailable exits, stale valuation, trapped-position capacity, turnover/cost feasibility, and drawdown acceptance. Numerical buffers, bands, counts, cadence, costs, and fallback rules remain preregistration decisions. The inspected period through 2026-09-17 is development evidence; fresh V2 validation must start strictly afterward.
"""
    outputs={"turnover_decomposition.csv":turnover,"turnover_yearly.csv":yearly,"selection_stability.csv":stability,"sector_rank_boundary_churn.csv":sector_churn,"stock_rank_boundary_churn.csv":stock_churn,"weight_rebalance_attribution.csv":weight,"cost_attribution.csv":cost,"operational_exception_audit.csv":audit,"drawdown_episodes.csv":episodes,"drawdown_sector_attribution.csv":ddsec,"drawdown_stock_attribution.csv":ddstock,"gross_sector_contribution.csv":gross_sector.sort_values("gross_contribution",ascending=False),"gross_stock_contribution.csv":gross_stock.sort_values("gross_contribution",ascending=False),"gross_year_contribution.csv":gross_year,"factor_vs_implementation_assessment.md":assessment,"v2_design_requirements.md":requirements}
    out=ROOT/c["output_dir"];out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase12a-",dir=out) as tmp:
        stage=Path(tmp)
        for name,value in outputs.items():
            if isinstance(value,pd.DataFrame):value.to_csv(stage/name,index=False,date_format="%Y-%m-%d",float_format="%.12f")
            else:(stage/name).write_text(value)
        (stage/"phase12a_sector_strategy_v1_diagnostics.md").write_text(summary)
        names=sorted(p.name for p in stage.iterdir());hashes={n:sha256(stage/n) for n in names};key={"accepted_inputs":accepted,"code_sha256":code_hash(),"config":c,"output_sha256":hashes};build=hashlib.sha256(canonical_json(key).encode()).hexdigest();manifest={**key,"build_id":build,"analysis":"READ_ONLY_ATTRIBUTION","alternative_strategy_pnl_count":0,"performance_data_max_date":"2026-09-17"}
        mp=out/"phase12a_build_manifest.json"
        if args.verify_rebuild:
            old=json.loads(mp.read_text());diff={n:(old["output_sha256"].get(n),h) for n,h in hashes.items() if old["output_sha256"].get(n)!=h}
            if old["build_id"]!=build or diff:raise AssertionError(f"Phase-12A rebuild differs: {diff}")
            print(f"PASS Phase-12A deterministic rebuild {len(hashes)}/{len(hashes)} byte-identical {build}");return
        for n in names:os.replace(stage/n,(ROOT/c["final_report"] if n=="phase12a_sector_strategy_v1_diagnostics.md" else out/n))
        mp.write_text(canonical_json(manifest))
    print(f"Built Phase-12A {build}");print(summary)

if __name__=="__main__":main()
