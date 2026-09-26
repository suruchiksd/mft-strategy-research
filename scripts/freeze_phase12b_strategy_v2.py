#!/usr/bin/env python3
"""Audit state-only feasibility and freeze Sector Momentum Strategy V2 before P&L."""
from __future__ import annotations

import argparse,hashlib,importlib.util,json,os,sys,tempfile
from pathlib import Path

import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from mft_research.csrs.phase5 import canonicalize_source,read_source,source_format
from mft_research.data.manifest import canonical_json,sha256
from mft_research.sector_strategy_v2 import (MAX_POSITIONS,STOCK_ENTRY_MAX_RANK,STOCK_RETENTION_MAX_RANK,
    SECTOR_ENTRY_MAX_RANK,SECTOR_RETENTION_MAX_RANK,WEIGHT_TOLERANCE,execution_state,select_sectors,stock_plan)

CONFIG=ROOT/"config/phase12b_sector_strategy_v2.yaml";OUT=ROOT/"reports/sector_strategy/v2/preregistration"

def config():return yaml.safe_load(CONFIG.read_text())

def verify_accepted(c):
    p12=json.loads((ROOT/"reports/sector_strategy/v1_diagnostics/phase12a_build_manifest.json").read_text())
    if p12["build_id"]!="9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5":raise RuntimeError("Phase-12A changed")
    for name,digest in p12["output_sha256"].items():
        path=ROOT/"reports/phase12a_sector_strategy_v1_diagnostics.md" if name=="phase12a_sector_strategy_v1_diagnostics.md" else ROOT/"reports/sector_strategy/v1_diagnostics"/name
        if sha256(path)!=digest:raise RuntimeError(f"Phase-12A artifact changed: {name}")
    spec=importlib.util.spec_from_file_location("p12a",ROOT/"scripts/build_phase12a_v1_diagnostics.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);prior=m.verify_inputs(m.cfg())
    return {**prior,"phase12a_build_id":p12["build_id"],"phase12a_verified_outputs":len(p12["output_sha256"])}

def inputs():
    daily=pd.concat([pd.read_parquet(ROOT/"data/derived/historical_nse_daily.parquet"),pd.read_parquet(ROOT/"data/derived/phase11_historical_daily_extension.parquet")],ignore_index=True);daily["date"]=pd.to_datetime(daily.date);daily=daily[daily.date.le("2026-09-17")]
    factor=pd.read_parquet(ROOT/"data/derived/phase11_sector_signal_panel.parquet");factor["date"]=pd.to_datetime(factor.date);factor=factor[factor.date.le("2026-09-17")]
    mapping=pd.read_parquet(ROOT/"data/derived/sector_research_mapping.parquet")
    return daily,factor,mapping

class RawQuotes:
    def __init__(self,daily):
        self.files=daily.drop_duplicates("date").set_index("date").source_file.to_dict();self.cache={}
    def day(self,date):
        date=pd.Timestamp(date)
        if date not in self.cache:
            path=Path(self.files[date]);raw,_=read_source(path);x=canonicalize_source(raw,source_format(path),str(path));x["date"]=pd.to_datetime(x.date)
            self.cache[date]=x[["symbol","series","open","close","volume"]]
        return self.cache[date]

def signal_dates(calendar):
    x=pd.DataFrame({"date":calendar});x["week"]=x.date.dt.strftime("%G-W%V");return set(x.groupby("week").date.max())

def state_feasibility(daily,factor,mapping):
    calendar=sorted(daily.date.unique());signals=signal_dates(calendar);quotes=RawQuotes(daily);holdings={};active_sectors=set();desired=set();pending=None;records=[];events=[];list_hashes=[];max_positions=0
    dgroups={d:g for d,g in daily.groupby("date",sort=False)};fgroups={d:g for d,g in factor.groupby("date",sort=False)}
    for i,date in enumerate(calendar):
        raw=quotes.day(date)
        # Retry previously unavailable exits at each observed session open.
        for symbol in sorted(set(holdings)-desired):
            z=raw[(raw.symbol.eq(symbol))&raw.series.isin(["EQ","BE"])&raw.open.gt(0)]
            if len(z):events.append({"date":date,"signal_date":pd.NaT,"symbol":symbol,"event":"RETRY_EXIT","series":z.sort_values("series").series.iloc[0]});holdings.pop(symbol)
            else:events.append({"date":date,"signal_date":pd.NaT,"symbol":symbol,"event":"TRAPPED_RETRY","series":"UNKNOWN"})
        if pending is not None and pending["execution_date"]==date:
            holdings,new_events=execution_state(holdings,pending["intended"],pending["replacement"],raw)
            for event in new_events:event.update({"date":date,"signal_date":pending["signal_date"]});events.append(event)
            desired=set(pending["intended"].symbol);pending=None
        max_positions=max(max_positions,len(holdings))
        if date not in signals or date not in fgroups:continue
        sectors=select_sectors(fgroups[date],active_sectors);intended,replacement=stock_plan(dgroups[date],mapping,sectors,holdings);active_sectors=set(sectors.sector_code)
        execution=calendar[i+1] if i+1<len(calendar) else pd.NaT
        serial=replacement[["symbol","sector_code","liquidity_rank","new_entry_eligible"]].to_dict("records");digest=hashlib.sha256(canonical_json(serial).encode()).hexdigest();list_hashes.append(digest)
        records.append({"signal_date":date,"execution_date":execution,"eligible_sectors":int(fgroups[date].valid_sector_ret_20.sum()),"selected_sectors":len(sectors),"retained_sectors":int(sectors.sector_status.eq("RETAINED").sum()),"new_sectors":int(sectors.sector_status.eq("NEW_ENTRY").sum()),"intended_stocks":len(intended),"retained_stocks":int(intended.selection_status.eq("RETAINED").sum()) if len(intended) else 0,"new_stocks":int(intended.selection_status.eq("NEW_ENTRY").sum()) if len(intended) else 0,"frozen_replacement_candidates":len(replacement),"replacement_list_sha256":digest,"positions_before_execution":len(holdings)})
        if pd.notna(execution):pending={"signal_date":date,"execution_date":execution,"intended":intended,"replacement":replacement}
    transitions=pd.DataFrame(records);event_frame=pd.DataFrame(events)
    summary={"signal_dates":len(transitions),"fully_resolved_sector_signals":int(transitions.selected_sectors.eq(3).sum()),"signals_with_three_sectors":int(transitions.selected_sectors.eq(3).sum()),"maximum_positions_observed":max_positions,"maximum_intended_stocks":int(transitions.intended_stocks.max()),"replacement_lists_frozen":len(list_hashes),"distinct_replacement_list_hashes":len(set(list_hashes)),"trapped_retry_events":int(event_frame.event.eq("TRAPPED_RETRY").sum()),"be_exit_events":int(((event_frame.event.isin(["EXIT","RETRY_EXIT"]))&event_frame.series.eq("BE")).sum()),"entry_skips":int(event_frame.event.eq("ENTRY_SKIPPED_NO_EQ_OPEN").sum()),"pnl_columns_created":0,"performance_data_after_2026_09_17_read":False,"deterministic_state_contract":True}
    if max_positions>MAX_POSITIONS or transitions.selected_sectors.max()>3 or transitions.intended_stocks.max()>9:raise AssertionError("V2 state cap failed")
    return transitions,event_frame,summary

def be_audit(daily):
    anomalies=pd.read_csv(ROOT/"reports/sector_strategy/development/development_operational_anomalies.csv",parse_dates=["date"]);stale=anomalies[anomalies.type.eq("STALE_MARK_CARRIED_NO_VALID_CLOSE")];quotes=RawQuotes(daily);rows=[]
    for symbol,g in stale.groupby("detail"):
        total=be=positive_open=positive_close=positive_volume=absent=0
        for date in sorted(g.date.unique()):
            total+=1;x=quotes.day(date);z=x[(x.symbol.eq(symbol))&x.series.eq("BE")]
            if len(z):be+=1;positive_open+=int(z.open.gt(0).any());positive_close+=int(z.close.gt(0).any());positive_volume+=int(z.volume.gt(0).any())
            else:absent+=1
        rows.append({"symbol":symbol,"stale_dates":total,"BE_rows":be,"positive_BE_open_rows":positive_open,"positive_BE_close_rows":positive_close,"positive_BE_volume_rows":positive_volume,"absent_rows":absent,"observed_BE_open_supports_exit_simulation":be>0 and positive_open==be,"policy_when_absent":"RETAIN_AND_RETRY_NO_FABRICATED_EXIT"})
    return pd.DataFrame(rows)

def acceptance_rules():
    return {"version":"V2_FROZEN_BEFORE_PNL","evaluation_order":["REJECT_STRATEGY_V2","RESEARCH_FURTHER","CONDITIONAL_PROSPECTIVE_CANDIDATE","READY_FOR_PROSPECTIVE_VALIDATION"],
      "metric_definitions":{"mean_weekly_gross_turnover":"sum_absolute_executed_notional_divided_by_pretrade_equity_mean_across_rebalances","cost_retention_ratio":"(ending_NAV_25bps_minus_1)/(ending_NAV_0bps_minus_1); requires gross gain > 0","maximum_drawdown":"minimum_NAV_over_prior_peak_minus_1","absolute_contribution_share":"absolute_single_contribution divided by sum_absolute_contributions"},
      "shared_required_gates":{"no_fabricated_trade":True,"no_fabricated_price":True,"no_negative_cash":True,"no_leverage":True,"no_future_universe_leakage":True,"no_same_close_execution":True,"unavailable_exits_remain_positions":True,"trapped_positions_count_toward_cap":True,"mean_weekly_gross_turnover_max":0.65,"primary_25bps_net_cumulative_return_gt":0,"primary_25bps_CAGR_gt":0,"primary_25bps_Sharpe_gt":0,"cost_retention_ratio_min":0.40,"single_stock_absolute_contribution_share_max":0.50,"single_sector_absolute_contribution_share_max":0.60},
      "REJECT_STRATEGY_V2":{"if_any_hard_safety_invariant_fails":True,"or_primary_25bps_net_cumulative_return_lte":0,"or_maximum_drawdown_lte":-0.40},
      "RESEARCH_FURTHER":{"non_reject_but_one_or_more_shared_required_gates_fail":True},
      "CONDITIONAL_PROSPECTIVE_CANDIDATE":{"all_shared_required_gates_pass":True,"maximum_drawdown_gt":-0.40,"maximum_drawdown_lt":-0.35},
      "READY_FOR_PROSPECTIVE_VALIDATION":{"all_shared_required_gates_pass":True,"maximum_drawdown_gte":-0.35},
      "50bps_sensitivity":{"reported_not_required_positive":True},"real_money_authorized":False,"automatic_paper_trade_authorized":False}

def specification(c,summary,be):
    return f"""# Phase 12B — Sector Momentum Strategy V2 Specification

> **PREREGISTERED BEFORE V2 P&L**  
> `v2_pnl_inspected = false`  
> `post_2026_09_17_v2_performance_inspected = false`

## Unchanged alpha

V2 uses only the accepted Phase-7 equal-weight 20-session Sector Relative Momentum signal in `STABLE_IDENTITY_BASIC_LIQUID`, with a five-stock sector floor. It remains long-only NSE cash, three sectors, three stocks per sector, maximum nine positions, weekly final-session signals, next-valid-session-open execution, equal intended weights, whole shares, cash only, and no leverage. No reversal, volume, stock-momentum, regime, volatility, stop, target, ATR, machine-learning, or combined signal is permitted.

## Frozen retention rules

- New sectors require strength rank 1–3. Existing sectors remain through rank 5 and exit above rank 5. Vacancies admit only current ranks 1–3, tie-broken by sector code.
- New stocks require signal-time trailing-turnover rank 1–3 within the active sector. Existing stocks remain through rank 5 while all eligibility and tradability conditions pass; ties use symbol.
- The complete liquidity list is hashed at signal close for audit, while execution fallback candidates remain limited to names that were top-three eligible at that signal.
- A retained position is resized only when its absolute deviation from intended equal weight is at least exactly 2 percentage points.

## Tradability and execution

New entries require stable identity, unique mapping, BASIC_LIQUID membership, valid reported EQ row, positive close, positive trailing turnover, recent presence, no point-in-time-known blocked action, and EQ status at the signal. BE never receives a new entry.

At the next session open, ranks remain frozen. An unavailable intended entry is skipped; execution walks only the already-frozen top-three list, then leaves cash. An unavailable exit remains held at its last observable mark and is retried each session. A valid observed EQ or BE open may execute an exit. No missing row becomes a zero price. A trapped position consumes marked capital and one of nine slots.

The raw audit found {int(be.BE_rows.sum())} BE rows across {int(be.stale_dates.sum())} historical stale dates; all {int(be.positive_BE_open_rows.sum())} observed BE rows had positive opens. Missing rows remain fail-closed. The state-only replay processed {summary['signal_dates']} signals, never exceeded {summary['maximum_positions_observed']} positions, froze {summary['replacement_lists_frozen']} signal-time replacement lists, and created no P&L column.

## Costs and acceptance

Primary cost remains 25 bps per side (20 transaction-cost plus 5 adverse-slippage bps), with fixed 0/10/25/50 sensitivities. Mean weekly gross turnover must be no more than 0.65. The 25-bps net cumulative return, CAGR, and Sharpe must be positive. If the zero-cost cumulative gain is positive, the 25-bps cumulative wealth gain must retain at least 40% of that gain: `(NAV25_end - 1) / (NAV0_end - 1) >= 0.40`. Maximum drawdown at or below -40% rejects V2; passing all gates with drawdown from -40% to below -35% is conditional; drawdown at least -35% is required for ready status. Stock and sector absolute-contribution shares are capped at 50% and 60%.

## Boundary

All data through 2026-09-17 is development evidence. Fresh validation signals must be strictly after 2026-09-17. No post-boundary V2 performance was read. This specification authorizes neither a backtest in Phase 12B, automatic paper trading, nor real-money deployment.
"""

def code_hash():
    paths=[CONFIG,ROOT/"src/mft_research/sector_strategy_v2.py",ROOT/"scripts/freeze_phase12b_strategy_v2.py"]+sorted(ROOT.glob("tests/test_phase12b*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(ROOT)),"sha256":sha256(p)} for p in paths if p.exists()]).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--verify-rebuild",action="store_true");args=ap.parse_args();c=config();accepted=verify_accepted(c);daily,factor,mapping=inputs()
    if daily.date.max()>pd.Timestamp("2026-09-17"):raise RuntimeError("Post-boundary data entered design")
    be=be_audit(daily);transitions,events,summary=state_feasibility(daily,factor,mapping);rules=acceptance_rules();spec=specification(c,summary,be)
    feasibility={"status":"PASS_STATE_ONLY_FEASIBILITY","summary":summary,"be_semantics":{"observed_rows":int(be.BE_rows.sum()),"positive_open_rows":int(be.positive_BE_open_rows.sum()),"absent_rows":int(be.absent_rows.sum()),"new_BE_entries":0,"missing_row_policy":"FAIL_CLOSED_RETAIN_AND_RETRY"},"v2_pnl_inspected":False,"post_2026_09_17_v2_performance_inspected":False}
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase12b-",dir=OUT) as tmp:
        stage=Path(tmp);(stage/"phase12b_sector_strategy_v2_config.yaml").write_text(CONFIG.read_text());(stage/"phase12b_sector_strategy_v2_specification.md").write_text(spec);(stage/"phase12b_v2_acceptance_rules.json").write_text(canonical_json(rules));(stage/"phase12b_feasibility_summary.json").write_text(canonical_json(feasibility));be.to_csv(stage/"phase12b_be_series_audit.csv",index=False,float_format="%.12f");transitions.to_csv(stage/"phase12b_state_transition_audit.csv",index=False,date_format="%Y-%m-%d",float_format="%.12f")
        names=sorted(p.name for p in stage.iterdir());hashes={n:sha256(stage/n) for n in names};key={"accepted_inputs":accepted,"code_sha256":code_hash(),"frozen_artifact_sha256":hashes,"v2_pnl_inspected":False,"post_2026_09_17_v2_performance_inspected":False,"fresh_validation_start_exclusive":"2026-09-17"};prereg_hash=hashlib.sha256(canonical_json(key).encode()).hexdigest();manifest={**key,"preregistration_hash":prereg_hash,"status":"FROZEN_BEFORE_V2_PNL","state_transition_event_count":len(events)}
        (stage/"phase12b_sector_strategy_v2_manifest.json").write_text(canonical_json(manifest));all_names=names+["phase12b_sector_strategy_v2_manifest.json"]
        if args.verify_rebuild:
            for name in all_names:
                if sha256(OUT/name)!=sha256(stage/name):raise AssertionError(f"Phase-12B preregistration differs: {name}")
            print(f"PASS Phase-12B deterministic preregistration {len(all_names)}/{len(all_names)} {prereg_hash}");return
        for name in all_names:os.replace(stage/name,OUT/name)
    print(f"Frozen Phase-12B V2 {prereg_hash}");print(canonical_json(feasibility))

if __name__=="__main__":main()
