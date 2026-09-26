"""Read-only attribution helpers for accepted Sector Momentum Strategy V1."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


TURNOVER_CLASSES=("SECTOR_ENTRY_EXIT","WITHIN_SECTOR_STOCK_REPLACEMENT","WEIGHT_REBALANCING","FORCED_OPERATIONAL")


def intended_holdings(execution_date, positions, anomalies):
    post=set(positions.loc[positions.date.eq(execution_date),"symbol"])
    day=anomalies[anomalies.date.eq(execution_date)]
    trapped=set(day.loc[day.type.eq("UNEXECUTABLE_EXIT_NO_VALID_OPEN"),"detail"])
    prevented=set(day.loc[day.type.eq("POSITION_CAP_PREVENTED_ENTRY"),"detail"])
    return (post-trapped)|prevented


def position_snapshots(rebalances,positions,anomalies,mapping):
    sector=mapping.set_index("symbol").sector.to_dict();rows=[];prior=set()
    for r in rebalances.sort_values("execution_date").itertuples(index=False):
        current=intended_holdings(r.execution_date,positions,anomalies)
        prior_sectors={sector.get(s,"UNMAPPED") for s in prior};current_sectors={sector.get(s,"UNMAPPED") for s in current}
        rows.append({"rebalance_id":r.rebalance_id,"signal_date":r.signal_date,"execution_date":r.execution_date,
          "prior_stocks":prior,"current_stocks":current,"prior_sectors":prior_sectors,"current_sectors":current_sectors})
        prior=current
    return rows


def turnover_attribution(trades,rebalances,positions,anomalies,mapping,daily,blocking_actions):
    sector=mapping.set_index("symbol").sector.to_dict();reb=rebalances.set_index("rebalance_id");snap={x["rebalance_id"]:x for x in position_snapshots(rebalances,positions,anomalies,mapping)}
    signal_dates=set(rebalances.signal_date);eligibility=daily[daily.date.isin(signal_dates)].set_index(["date","symbol"]).universe_basic_liquid.to_dict()
    core=anomalies[anomalies.type.str.contains("UNEXECUTABLE_EXIT|STALE_MARK")];operational_exits=set()
    for sym,last in core.groupby("detail").date.max().items():
        candidates=trades[(trades.symbol.eq(sym))&trades.side.eq("SELL")&trades.date.gt(last)].sort_values("date")
        for candidate in candidates.itertuples(index=False):
            if not ((positions.date.eq(candidate.date))&positions.symbol.eq(sym)).any():
                operational_exits.add((sym,candidate.date));break
    rows=[]
    for t in trades.itertuples(index=False):
        s=snap[t.rebalance_id];sym=t.symbol;sec=sector.get(sym,"UNMAPPED");retained=sym in s["prior_stocks"] and sym in s["current_stocks"]
        row=reb.loc[t.rebalance_id];signal=row.signal_date
        eligibility_loss=(signal,sym) in eligibility and not bool(eligibility[(signal,sym)])
        prior_signal=rebalances.loc[rebalances.execution_date.lt(t.date),"signal_date"].max()
        ca=blocking_actions[(blocking_actions.symbol.eq(sym))&blocking_actions.date.gt(prior_signal if pd.notna(prior_signal) else pd.Timestamp("1900-01-01"))&blocking_actions.date.le(t.date)]
        post_exception=(sym,t.date) in operational_exits
        if post_exception or eligibility_loss or len(ca):kind="FORCED_OPERATIONAL"
        elif retained:kind="WEIGHT_REBALANCING"
        elif (t.side=="BUY" and sec not in s["prior_sectors"]) or (t.side=="SELL" and sec not in s["current_sectors"]):kind="SECTOR_ENTRY_EXIT"
        else:kind="WITHIN_SECTOR_STOCK_REPLACEMENT"
        slip=abs(t.fill_price-t.reference_open)*t.quantity
        rows.append({"rebalance_id":t.rebalance_id,"signal_date":row.signal_date,"execution_date":t.date,"year":t.date.year,
          "symbol":sym,"sector":sec,"side":t.side,"turnover_class":kind,"notional":t.notional,
          "normalized_turnover":t.notional/row.pretrade_equity,"transaction_cost":t.transaction_cost,
          "slippage_cost":slip,"all_in_cost":t.transaction_cost+slip,"retained_stock":retained,
          "eligibility_loss":eligibility_loss,"post_operational_exception":post_exception,"blocking_action":bool(len(ca))})
    return pd.DataFrame(rows)


def selection_stability(rebalances,positions,anomalies,mapping):
    rows=[];sector_runs=defaultdict(int);stock_runs=defaultdict(int)
    for i,s in enumerate(position_snapshots(rebalances,positions,anomalies,mapping)):
        ps,cs=s["prior_sectors"],s["current_sectors"];pst,cst=s["prior_stocks"],s["current_stocks"]
        retained_s=ps&cs;retained_st=pst&cst
        for x in sorted(cs):sector_runs[x]=sector_runs[x]+1 if x in ps else 1
        for x in sorted(cst):stock_runs[x]=stock_runs[x]+1 if x in pst else 1
        rows.append({"rebalance_id":s["rebalance_id"],"signal_date":s["signal_date"],"execution_date":s["execution_date"],"year":s["execution_date"].year,
          "selected_sectors":"|".join(sorted(cs)),"sectors_retained":len(retained_s),"sectors_entered":len(cs-ps),"sectors_exited":len(ps-cs),
          "sector_jaccard":len(ps&cs)/len(ps|cs) if ps|cs else np.nan,"mean_active_sector_duration_cycles":np.mean([sector_runs[x] for x in cs]) if cs else np.nan,
          "selected_stocks":"|".join(sorted(cst)),"stocks_retained":len(retained_st),"stocks_entered":len(cst-pst),"stocks_exited":len(pst-cst),
          "stock_jaccard":len(pst&cst)/len(pst|cst) if pst|cst else np.nan,"within_sector_stock_replacements":sum(1 for x in cst-pst if mapping.set_index("symbol").sector.to_dict().get(x) in ps&cs),
          "mean_active_stock_duration_cycles":np.mean([stock_runs[x] for x in cst]) if cst else np.nan})
    return pd.DataFrame(rows)


def sector_boundary(stability,factor):
    factor=factor.copy();factor["strength_rank"]=(factor.eligible_sector_count_20-factor.sector_rank_20+1).astype("Int64")
    lookup=factor.set_index(["date","sector"])["strength_rank"].to_dict();rows=[]
    for i in range(1,len(stability)):
        prev=set(str(stability.iloc[i-1].selected_sectors).split("|"));cur=set(str(stability.iloc[i].selected_sectors).split("|"))
        pdte=stability.iloc[i-1].signal_date;cdte=stability.iloc[i].signal_date
        for direction,names in (("ENTER",cur-prev),("EXIT",prev-cur)):
            for sector in sorted(names):
                pr=lookup.get((pdte,sector));cr=lookup.get((cdte,sector));move=f"{pr}->{cr}"
                rows.append({"rebalance_id":stability.iloc[i].rebalance_id,"signal_date":cdte,"sector":sector,"direction":direction,"previous_strength_rank":pr,"current_strength_rank":cr,"rank_move":move,"small_boundary_move":move in {"3->4","4->3","3->5","5->3"}})
    return pd.DataFrame(rows)


def stock_boundary(stability,daily,mapping):
    sec=mapping.set_index("symbol").sector.to_dict();rows=[];signal_dates=set(stability.signal_date)
    relevant=daily[daily.date.isin(signal_dates)&daily.universe_basic_liquid.fillna(False)].copy();relevant["sector"]=relevant.symbol.map(sec)
    daily_groups={date:g for date,g in relevant.groupby("date",sort=False)}
    for i in range(1,len(stability)):
        prev=set(str(stability.iloc[i-1].selected_stocks).split("|"));cur=set(str(stability.iloc[i].selected_stocks).split("|"));retsec=set(str(stability.iloc[i-1].selected_sectors).split("|"))&set(str(stability.iloc[i].selected_sectors).split("|"))
        pdte=stability.iloc[i-1].signal_date;cdte=stability.iloc[i].signal_date
        ranks={}
        for date in (pdte,cdte):
            x=daily_groups.get(date,pd.DataFrame(columns=["sector","avg_turnover_20","symbol"])).copy()
            x=x[x.sector.isin(retsec)].sort_values(["sector","avg_turnover_20","symbol"],ascending=[True,False,True],kind="stable")
            x["liquidity_rank"]=x.groupby("sector").cumcount()+1
            ranks.update({(date,r.symbol):int(r.liquidity_rank) for r in x.itertuples()})
        for direction,names in (("ENTER",cur-prev),("EXIT",prev-cur)):
            for sym in sorted(names):
                if sec.get(sym) not in retsec:continue
                pr=ranks.get((pdte,sym));cr=ranks.get((cdte,sym));move=f"{pr}->{cr}"
                rows.append({"rebalance_id":stability.iloc[i].rebalance_id,"signal_date":cdte,"sector":sec.get(sym),"symbol":sym,"direction":direction,"previous_liquidity_rank":pr,"current_liquidity_rank":cr,"rank_move":move,"small_boundary_move":move in {"3->4","4->3","3->5","5->3"}})
    return pd.DataFrame(rows)


def weight_attribution(rebalances,positions,anomalies,mapping,daily,trade_attr):
    rows=[];snap=position_snapshots(rebalances,positions,anomalies,mapping);pos=positions.set_index(["date","symbol"]);sector=mapping.set_index("symbol").sector.to_dict()
    execution_dates=set(rebalances.execution_date);opens=daily[daily.date.isin(execution_dates)].set_index(["date","symbol"]).open.to_dict()
    dates=sorted(positions.date.unique())
    for s in snap:
        exec_date=s["execution_date"];previous=max((d for d in dates if d<exec_date),default=None);target=1/len(s["current_stocks"]) if s["current_stocks"] else np.nan
        for sym in sorted(s["prior_stocks"]&s["current_stocks"]):
            if previous is None or (previous,sym) not in pos.index:continue
            q=pos.loc[(previous,sym)].shares;price=opens.get((exec_date,sym))
            mark=float(price) if pd.notna(price) and price>0 else float(pos.loc[(previous,sym)].close)
            prevalue=q*mark;preweight=prevalue/rebalances.set_index("rebalance_id").loc[s["rebalance_id"]].pretrade_equity
            trades=trade_attr[(trade_attr.rebalance_id.eq(s["rebalance_id"]))&trade_attr.symbol.eq(sym)&trade_attr.turnover_class.eq("WEIGHT_REBALANCING")]
            rows.append({"rebalance_id":s["rebalance_id"],"signal_date":s["signal_date"],"execution_date":exec_date,"symbol":sym,"sector":sector.get(sym),"pre_rebalance_weight":preweight,"target_weight":target,"absolute_weight_deviation":abs(target-preweight),"weight_restoration_notional":trades.notional.sum(),"normalized_weight_restoration_turnover":trades.normalized_turnover.sum()})
    return pd.DataFrame(rows)


def daily_contributions(equity,positions,trades,mapping,initial_capital=500000):
    sector=mapping.set_index("symbol").sector.to_dict();dates=list(equity.date);prior={};rows=[]
    for date in dates:
        current=positions[positions.date.eq(date)].set_index("symbol").market_value.to_dict();daytrades=trades[trades.date.eq(date)]
        symbols=set(prior)|set(current)|set(daytrades.symbol)
        for sym in sorted(symbols):
            t=daytrades[daytrades.symbol.eq(sym)];buys=t[t.side.eq("BUY")];sells=t[t.side.eq("SELL")]
            investment=(buys.notional+buys.transaction_cost).sum()-(sells.notional-sells.transaction_cost).sum()
            pnl=current.get(sym,0)-prior.get(sym,0)-investment
            slip=(abs(t.fill_price-t.reference_open)*t.quantity).sum();cost=t.transaction_cost.sum()+slip
            rows.append({"date":date,"symbol":sym,"sector":sector.get(sym,"UNMAPPED"),"net_contribution":pnl,"all_in_execution_cost":cost,"gross_before_cost_contribution":pnl+cost,"position_status":"EXISTING" if sym in prior else "NEWLY_ENTERED"})
        prior=current
    result=pd.DataFrame(rows)
    expected=equity.equity.iloc[-1]-initial_capital
    if abs(result.net_contribution.sum()-expected)>1e-5:raise AssertionError("Contribution reconciliation failed")
    return result


def drawdown_episodes(equity):
    x=equity.sort_values("date").reset_index(drop=True);peak_i=0;episodes=[];under=False;start=None;trough=None
    for i,row in x.iterrows():
        if row.equity>=x.loc[peak_i,"equity"]:
            if under:
                episodes.append((start,peak_i,trough,i));under=False
            peak_i=i
        elif not under:under=True;start=i;trough=i
        elif row.equity<x.loc[trough,"equity"]:trough=i
    if under:episodes.append((start,peak_i,trough,None))
    records=[]
    for n,(start,peak,trough,recovery) in enumerate(episodes,1):
        records.append({"episode_source_id":n,"peak_date":x.loc[peak,"date"],"underwater_start":x.loc[start,"date"],"trough_date":x.loc[trough,"date"],"recovery_date":x.loc[recovery,"date"] if recovery is not None else pd.NaT,"depth":x.loc[trough,"equity"]/x.loc[peak,"equity"]-1,"peak_to_trough_sessions":trough-peak,"recovery_duration_sessions":recovery-peak if recovery is not None else np.nan,"recovered":recovery is not None})
    result=pd.DataFrame(records).sort_values("depth").head(10).reset_index(drop=True);result.insert(0,"episode_id",range(1,len(result)+1));return result


def drawdown_attribution(episodes,contrib,group):
    rows=[]
    for e in episodes.itertuples(index=False):
        x=contrib[(contrib.date>e.peak_date)&(contrib.date<=e.trough_date)]
        g=x.groupby(group,as_index=False).net_contribution.sum();den=g.net_contribution.abs().sum()
        g["absolute_contribution_share"]=g.net_contribution.abs()/den if den else np.nan;g.insert(0,"episode_id",e.episode_id);rows.append(g)
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=["episode_id",group,"net_contribution","absolute_contribution_share"])
