"""Phase-11 sector-momentum strategy readiness and deterministic selection helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mft_research.ca_extension import attach_identity, parse_official
from mft_research.csrs.phase5 import add_point_in_time_fields, canonicalize_source, read_source
from mft_research.sector_momentum import aggregate_sector_daily, build_factor_panel, stock_daily_returns


def canonical_new_daily(paths: list[Path]) -> pd.DataFrame:
    frames=[]
    for path in sorted(paths):
        raw,_=read_source(path)
        frames.append(canonicalize_source(raw,"NEW",str(path)))
    result=pd.concat(frames,ignore_index=True)
    return result[result.series.eq("EQ")].sort_values(["date","symbol"],kind="stable").reset_index(drop=True)


def extension_actions(raw_path: Path, endpoint: str, retrieval: str, digest: str,
                      identity: pd.DataFrame) -> pd.DataFrame:
    parsed=parse_official(raw_path,endpoint,retrieval,digest,"PHASE11_V1")
    return attach_identity(parsed,identity[["symbol","isin"]].drop_duplicates())


def action_contract(historical: pd.DataFrame, extensions: list[pd.DataFrame]) -> pd.DataFrame:
    base=historical[["symbol","series","date","research_impact"]].copy()
    frames=[base]
    for ledger in extensions:
        mapped=ledger[ledger.mapped_symbol.notna()].copy()
        mapped["research_impact"]=np.where(mapped.safety_classification.eq("NONBLOCKING_INFORMATIONAL"),
          "NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM","UNKNOWN_OR_AMBIGUOUS")
        frames.append(mapped.rename(columns={"mapped_symbol":"symbol","blocking_date":"date"})[["symbol","series","date","research_impact"]])
    result=pd.concat(frames,ignore_index=True);result["date"]=pd.to_datetime(result.date).dt.date
    return result.drop_duplicates().sort_values(["date","symbol"],kind="stable").reset_index(drop=True)


def extend_daily(accepted: pd.DataFrame, new_rows: pd.DataFrame, phase5: dict,
                 actions: pd.DataFrame, mapping: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    base_columns=["date","symbol","series","open","high","low","close","volume","turnover_rupees","isin",
                  "instrument_id","security_name","source_format","source_file"]
    combined=pd.concat([accepted[base_columns],new_rows[base_columns]],ignore_index=True)
    if combined.duplicated(["symbol","date"]).any():raise ValueError("Phase-11 extension duplicates symbol/date")
    sectors=mapping[["symbol","sector","sector_code","mapping_status"]].rename(columns={"mapping_status":"sector_mapping_status"})
    cfg=dict(phase5);cfg["corporate_action_coverage_end"]="2026-09-17"
    recalculated=add_point_in_time_fields(combined,cfg,actions,sectors)
    extension_dates=set(new_rows.date)
    extension=recalculated[recalculated.date.isin(extension_dates)].copy()
    # Phase-5 rows are immutable inputs. Recalculation supplies only additive rows;
    # historical membership and quality fields remain byte/semantically accepted.
    rebuilt=pd.concat([accepted,extension[accepted.columns]],ignore_index=True).sort_values(
        ["symbol","date"],kind="stable").reset_index(drop=True)
    return rebuilt,extension.sort_values(["date","symbol"],kind="stable").reset_index(drop=True)


def extended_sector_panel(daily: pd.DataFrame, mapping: pd.DataFrame, actions: pd.DataFrame,
                          phase5: dict, phase7: dict,
                          tier: str = "STABLE_IDENTITY_BASIC_LIQUID") -> pd.DataFrame:
    cfg=dict(phase5);cfg["corporate_action_coverage_end"]="2026-09-17"
    spec=phase7["mapping_universe_tiers"][tier]
    columns=["date","symbol","close","session_position","research_quality_status",spec["universe_column"]]
    returns=stock_daily_returns(daily[columns].copy(),actions,cfg)
    # Phase-7 excludes unmapped identities. Pre-filtering keeps the accepted
    # boolean identity dtype when newly listed, unmapped symbols appear.
    returns=returns[returns.symbol.isin(mapping.symbol)].copy()
    sector_daily=aggregate_sector_daily(returns,mapping,spec,tier,5)
    return build_factor_panel(sector_daily,formations=(20,),futures=())


def weekly_signal_dates(calendar: list, end_date) -> pd.DataFrame:
    dates=pd.Series(sorted(pd.to_datetime(calendar).date),name="signal_date")
    frame=pd.DataFrame({"signal_date":dates});timestamps=pd.to_datetime(frame.signal_date)
    frame["week_key"]=timestamps.dt.strftime("%G-W%V")
    signals=frame.groupby("week_key",sort=True).signal_date.max().reset_index()
    position={day:i for i,day in enumerate(sorted(dates))};ordered=sorted(dates)
    signals["execution_date"]=signals.signal_date.map(lambda day:ordered[position[day]+1] if position[day]+1<len(ordered) else pd.NaT)
    return signals[signals.signal_date<=pd.Timestamp(end_date).date()].reset_index(drop=True)


def select_targets(signal_date, sector_panel: pd.DataFrame, daily: pd.DataFrame,
                   mapping: pd.DataFrame, sector_count=3, stocks_per_sector=3) -> pd.DataFrame:
    sectors=sector_panel[(sector_panel.date==signal_date)&sector_panel.valid_sector_ret_20].copy()
    sectors=sectors.sort_values(["sector_ret_20","sector_code"],ascending=[False,True],kind="stable").head(sector_count)
    member_columns=["date","symbol","avg_turnover_20","universe_basic_liquid","research_quality_status"]
    members=daily.loc[(daily.date==signal_date)&daily.universe_basic_liquid.fillna(False)&
                  daily.research_quality_status.eq("VALID_REPORTED_EQ_ROW"),member_columns].merge(
      mapping[["symbol","sector","sector_code","mapping_status","identity_ambiguous"]],on="symbol",how="left",validate="many_to_one")
    members=members[members.mapping_status.eq("STATIC_CURRENT_UNIQUE")&~members.identity_ambiguous.fillna(True)]
    records=[]
    for sector_rank,row in enumerate(sectors.itertuples(index=False),start=1):
        eligible=members[members.sector_code.eq(row.sector_code)].sort_values(["avg_turnover_20","symbol"],ascending=[False,True],kind="stable")
        chosen=eligible.head(stocks_per_sector)
        for liquidity_rank,stock in enumerate(chosen.itertuples(index=False),start=1):
            records.append({"signal_date":signal_date,"sector":row.sector,"sector_code":row.sector_code,
              "sector_rank":sector_rank,"sector_formation_return":row.sector_ret_20,"eligible_stocks_in_sector":len(eligible),
              "symbol":stock.symbol,"liquidity_rank":liquidity_rank,"avg_turnover_20":stock.avg_turnover_20})
    result=pd.DataFrame(records)
    if not result.empty:result["target_weight"]=1/len(result)
    return result


def feasibility(signals: pd.DataFrame, sector_panel: pd.DataFrame, daily: pd.DataFrame,
                mapping: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    selected=[];summary=[]
    for row in signals.itertuples(index=False):
        targets=select_targets(row.signal_date,sector_panel,daily,mapping)
        if not targets.empty:
            targets["execution_date"]=row.execution_date;selected.append(targets)
        sector_counts=targets.groupby("sector_code").eligible_stocks_in_sector.first() if not targets.empty else pd.Series(dtype=float)
        usable=sector_panel[(sector_panel.date==row.signal_date)&sector_panel.valid_sector_ret_20]
        summary.append({"signal_date":row.signal_date,"execution_date":row.execution_date,"usable_sectors":len(usable),
          "selected_sectors":targets.sector_code.nunique() if not targets.empty else 0,"expected_positions":len(targets),
          "selected_sectors_below_3_stocks":int(sector_counts.lt(3).sum()),
          "maximum_sector_weight":targets.groupby("sector_code").target_weight.sum().max() if not targets.empty else np.nan})
    return (pd.concat(selected,ignore_index=True) if selected else pd.DataFrame(),pd.DataFrame(summary))


def blocking_map(actions: pd.DataFrame, blocking_impacts: list[str]) -> dict[str, np.ndarray]:
    selected=actions[actions.series.eq("EQ") & actions.research_impact.isin(blocking_impacts)]
    return {symbol:np.array(sorted(pd.Timestamp(day).to_datetime64() for day in group.date.unique()))
            for symbol,group in selected.groupby("symbol",sort=False)}


def generate_rebalances(calendar: list, start, end, sector_panel: pd.DataFrame, daily: pd.DataFrame,
                        mapping: pd.DataFrame, universe_column: str, actions: pd.DataFrame,
                        blocking_impacts: list[str]) -> pd.DataFrame:
    """Generate frozen selections without using returns after a signal date."""
    schedules=weekly_signal_dates(calendar,end)
    start=pd.Timestamp(start).date();end=pd.Timestamp(end).date()
    schedules=schedules[pd.to_datetime(schedules.execution_date).dt.date.between(start,end)].copy()
    schedules=schedules.dropna(subset=["execution_date"]).reset_index(drop=True)
    if schedules.empty:return pd.DataFrame()
    execution_dates=schedules.execution_date.tolist()
    next_execution={row.signal_date:(execution_dates[i+1] if i+1<len(execution_dates) else end)
                    for i,row in enumerate(schedules.itertuples(index=False))}
    signal_dates=set(schedules.signal_date);member_columns=["date","symbol","avg_turnover_20",universe_column,"research_quality_status"]
    members=daily.loc[daily.date.isin(signal_dates),member_columns].merge(
      mapping[["symbol","sector","sector_code","mapping_status","identity_ambiguous"]],on="symbol",how="left",validate="many_to_one")
    members=members[members[universe_column].fillna(False)&members.research_quality_status.eq("VALID_REPORTED_EQ_ROW")&
                    members.mapping_status.eq("STATIC_CURRENT_UNIQUE")&~members.identity_ambiguous.fillna(True)]
    member_groups={day:g for day,g in members.groupby("date",sort=False)}
    factor_groups={day:g for day,g in sector_panel[sector_panel.date.isin(signal_dates)].groupby("date",sort=False)}
    events=blocking_map(actions,blocking_impacts);records=[]
    for number,row in enumerate(schedules.itertuples(index=False),start=1):
        factors=factor_groups.get(row.signal_date,pd.DataFrame())
        if factors.empty:continue
        sectors=factors[factors.valid_sector_ret_20].sort_values(["sector_ret_20","sector_code"],ascending=[False,True],kind="stable").head(3)
        current=member_groups.get(row.signal_date,pd.DataFrame())
        chosen=[]
        for sector_rank,sector in enumerate(sectors.itertuples(index=False),start=1):
            eligible=current[current.sector_code.eq(sector.sector_code)].sort_values(["avg_turnover_20","symbol"],ascending=[False,True],kind="stable")
            liquidity_rank=0
            for stock in eligible.itertuples(index=False):
                liquidity_rank+=1;dates=events.get(stock.symbol,np.array([],dtype="datetime64[ns]"))
                crosses=bool(((dates>np.datetime64(row.signal_date))&(dates<=np.datetime64(next_execution[row.signal_date]))).any())
                if crosses:continue
                chosen.append({"rebalance_id":f"SMV1-{number:04d}","signal_date":row.signal_date,"execution_date":row.execution_date,
                  "sector":sector.sector,"sector_code":sector.sector_code,"sector_rank":sector_rank,
                  "sector_formation_return":sector.sector_ret_20,"symbol":stock.symbol,"liquidity_rank":liquidity_rank,
                  "avg_turnover_20":stock.avg_turnover_20,"corporate_action_safe":True})
                if sum(x["sector_code"]==sector.sector_code for x in chosen)>=3:break
        if chosen:
            weight=1/len(chosen)
            for item in chosen:item["target_weight"]=weight;records.append(item)
    return pd.DataFrame(records)


def simulate(daily: pd.DataFrame, targets: pd.DataFrame, start, end, initial_capital: float,
             transaction_cost_bps: float, slippage_bps: float) -> dict[str,pd.DataFrame]:
    start=pd.Timestamp(start).date();end=pd.Timestamp(end).date();calendar=sorted(day for day in daily.date.unique() if start<=day<=end)
    by_date={day:g.set_index("symbol") for day,g in daily[daily.date.isin(calendar)].groupby("date",sort=False)}
    target_groups={day:g for day,g in targets.groupby("execution_date",sort=False)} if not targets.empty else {}
    cash=float(initial_capital);positions={};position_sector={};previous_close={};entry_index={};holding_lengths=[]
    equity_rows=[];trade_rows=[];position_rows=[];contribution=[];rebalance_rows=[];anomalies=[]
    started=False
    for session_index,day in enumerate(calendar):
        prices=by_date[day];today_contrib={};today_sector=dict(position_sector);today_cost=0.;today_turnover=0.;pretrade_equity=np.nan
        if day in target_groups:
            target=target_groups[day].drop_duplicates("symbol").sort_values("symbol",kind="stable");selected=set(target.symbol)
            if not started:started=True
            valid_open={s for s in set(positions)|selected if s in prices.index and pd.notna(prices.loc[s,"open"]) and prices.loc[s,"open"]>0}
            pretrade_equity=cash+sum(q*(float(prices.loc[s,"open"]) if s in valid_open else previous_close[s]) for s,q in positions.items())
            n=len(selected);target_value=pretrade_equity/n if n else 0
            desired={s:int(np.floor(target_value/(float(prices.loc[s,"open"])*(1+slippage_bps/10000)*(1+transaction_cost_bps/10000)))) for s in selected if s in valid_open}
            for s in sorted(selected-valid_open):anomalies.append({"date":day,"type":"UNEXECUTABLE_ENTRY_NO_VALID_OPEN","detail":s})
            # Existing-position overnight gaps accrue before open execution.
            for s,q in positions.items():
                if s in valid_open:today_contrib[s]=today_contrib.get(s,0)+q*(float(prices.loc[s,"open"])-previous_close[s])
            for s in sorted(set(positions)|selected):
                current=positions.get(s,0);want=desired.get(s,0)
                if current<=want:continue
                if s not in valid_open:
                    anomalies.append({"date":day,"type":"UNEXECUTABLE_EXIT_NO_VALID_OPEN","detail":s});continue
                qty=current-want;open_price=float(prices.loc[s,"open"]);fill=open_price*(1-slippage_bps/10000);notional=qty*fill;fee=notional*transaction_cost_bps/10000
                cash+=notional-fee;today_cost+=fee;today_turnover+=notional
                today_contrib[s]=today_contrib.get(s,0)+qty*(fill-open_price)-fee
                positions[s]=want
                trade_rows.append({"date":day,"rebalance_id":target.rebalance_id.iloc[0],"symbol":s,"side":"SELL","quantity":qty,"reference_open":open_price,"fill_price":fill,"notional":notional,"transaction_cost":fee,"slippage_bps":slippage_bps})
                if want==0:
                    positions.pop(s,None);position_sector.pop(s,None);holding_lengths.append(session_index-entry_index.pop(s));previous_close.pop(s,None)
            for s in sorted(selected):
                if s not in desired:continue
                current=positions.get(s,0);want=desired[s]
                if want<=current:continue
                if current==0 and len(positions)>=9:
                    anomalies.append({"date":day,"type":"POSITION_CAP_PREVENTED_ENTRY","detail":s});continue
                open_price=float(prices.loc[s,"open"]);fill=open_price*(1+slippage_bps/10000);per_share=fill*(1+transaction_cost_bps/10000)
                qty=min(want-current,int(np.floor(max(cash,0)/per_share)))
                if qty<=0:continue
                notional=qty*fill;fee=notional*transaction_cost_bps/10000;cash-=notional+fee;today_cost+=fee;today_turnover+=notional
                today_contrib[s]=today_contrib.get(s,0)+qty*(open_price-fill)-fee
                if current==0:entry_index[s]=session_index
                positions[s]=current+qty;position_sector[s]=target.set_index("symbol").loc[s,"sector"]
                today_sector[s]=position_sector[s]
                trade_rows.append({"date":day,"rebalance_id":target.rebalance_id.iloc[0],"symbol":s,"side":"BUY","quantity":qty,"reference_open":open_price,"fill_price":fill,"notional":notional,"transaction_cost":fee,"slippage_bps":slippage_bps})
            rebalance_rows.append({"rebalance_id":target.rebalance_id.iloc[0],"signal_date":target.signal_date.iloc[0],"execution_date":day,
              "selected_positions":len(selected),"actual_positions":len(positions),"pretrade_equity":pretrade_equity,"gross_turnover":today_turnover/pretrade_equity if pretrade_equity else np.nan,"costs":today_cost})
        if not started:continue
        for s,q in positions.items():
            valid_close=s in prices.index and pd.notna(prices.loc[s,"close"]) and prices.loc[s,"close"]>0
            if not valid_close:
                anomalies.append({"date":day,"type":"STALE_MARK_CARRIED_NO_VALID_CLOSE","detail":s});continue
            close=float(prices.loc[s,"close"]);base=float(prices.loc[s,"open"]) if day in target_groups and s in valid_open else previous_close[s]
            today_contrib[s]=today_contrib.get(s,0)+q*(close-base);previous_close[s]=close
        equity=cash+sum(q*previous_close[s] for s,q in positions.items())
        equity_rows.append({"date":day,"cash":cash,"market_value":equity-cash,"equity":equity,"nav":equity/initial_capital,"positions":len(positions),"costs":today_cost,"turnover":today_turnover/equity if equity else np.nan})
        for s,value in today_contrib.items():contribution.append({"date":day,"symbol":s,"sector":today_sector.get(s,"UNMAPPED"),"contribution_rupees":value})
        for s,q in sorted(positions.items()):
            value=q*previous_close[s];position_rows.append({"date":day,"symbol":s,"sector":position_sector[s],"shares":q,"close":previous_close[s],"market_value":value,"weight":value/equity if equity else np.nan})
        if cash < -1e-7:anomalies.append({"date":day,"type":"NEGATIVE_CASH","detail":str(cash)})
        if len(positions)>9:anomalies.append({"date":day,"type":"POSITION_LIMIT_BREACH","detail":str(len(positions))})
    if calendar:
        for s in positions:holding_lengths.append(len(calendar)-1-entry_index[s])
    return {"equity":pd.DataFrame(equity_rows),"trades":pd.DataFrame(trade_rows),"positions":pd.DataFrame(position_rows),
      "contribution":pd.DataFrame(contribution),"rebalances":pd.DataFrame(rebalance_rows),"anomalies":pd.DataFrame(anomalies,columns=["date","type","detail"]),
      "holding_lengths":pd.DataFrame({"holding_sessions":holding_lengths})}


def performance_metrics(result: dict[str,pd.DataFrame], initial_capital: float) -> dict:
    curve=result["equity"].copy();returns=curve.equity.pct_change().dropna();n=len(returns)
    cumulative=curve.equity.iloc[-1]/initial_capital-1 if len(curve) else np.nan
    cagr=(1+cumulative)**(252/n)-1 if n and cumulative>-1 else np.nan
    vol=returns.std(ddof=1)*np.sqrt(252) if n>1 else np.nan;sharpe=returns.mean()/returns.std(ddof=1)*np.sqrt(252) if n>1 and returns.std(ddof=1)>0 else np.nan
    downside=returns[returns<0];sortino=returns.mean()/downside.std(ddof=1)*np.sqrt(252) if len(downside)>1 and downside.std(ddof=1)>0 else np.nan
    dd=curve.equity/curve.equity.cummax()-1;mdd=dd.min() if len(dd) else np.nan
    duration=0;maximum=0
    for value in dd:
        duration=duration+1 if value<0 else 0;maximum=max(maximum,duration)
    rebalances=result["rebalances"]
    return {"start_date":curve.date.min() if len(curve) else pd.NaT,"end_date":curve.date.max() if len(curve) else pd.NaT,
      "observations":n,"cumulative_return":cumulative,"CAGR":cagr,"annualized_volatility":vol,"Sharpe":sharpe,"Sortino":sortino,
      "maximum_drawdown":mdd,"Calmar":cagr/abs(mdd) if mdd<0 else np.nan,"maximum_drawdown_duration_sessions":maximum,
      "positive_daily_periods":int(returns.gt(0).sum()),"negative_daily_periods":int(returns.lt(0).sum()),
      "total_turnover":rebalances.gross_turnover.sum() if len(rebalances) else 0,"mean_weekly_gross_turnover":rebalances.gross_turnover.mean() if len(rebalances) else np.nan,
      "costs_rupees":result["trades"].transaction_cost.sum() if len(result["trades"]) else 0,"trade_count":len(result["trades"]),
      "rebalance_count":len(rebalances),"average_holding_sessions":result["holding_lengths"].holding_sessions.mean() if len(result["holding_lengths"]) else np.nan,
      "mean_positions":curve.positions.mean() if len(curve) else np.nan,"mean_cash_utilization":((curve.equity-curve.cash)/curve.equity).mean() if len(curve) else np.nan,
      "operational_anomalies":len(result["anomalies"])}
