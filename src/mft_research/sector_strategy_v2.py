"""Pure, return-free state rules for Sector Momentum Strategy V2 preregistration."""
from __future__ import annotations

import pandas as pd

SECTOR_ENTRY_MAX_RANK=3
SECTOR_RETENTION_MAX_RANK=5
STOCK_ENTRY_MAX_RANK=3
STOCK_RETENTION_MAX_RANK=5
MAX_POSITIONS=9
WEIGHT_TOLERANCE=0.02


def ranked_sectors(today: pd.DataFrame) -> pd.DataFrame:
    x=today[today.valid_sector_ret_20].sort_values(["sector_ret_20","sector_code"],ascending=[False,True],kind="stable").copy()
    x["strength_rank"]=range(1,len(x)+1)
    return x


def select_sectors(today: pd.DataFrame, existing: set[str]) -> pd.DataFrame:
    """Retain existing ranks <=5, then admit only new ranks <=3."""
    ranked=ranked_sectors(today);by_code=ranked.set_index("sector_code")
    retained=[code for code in existing if code in by_code.index and int(by_code.loc[code,"strength_rank"])<=SECTOR_RETENTION_MAX_RANK]
    retained=sorted(retained,key=lambda code:(int(by_code.loc[code,"strength_rank"]),code))
    selected=retained[:3]
    for row in ranked.itertuples(index=False):
        if len(selected)>=3:break
        if row.sector_code not in existing and row.strength_rank<=SECTOR_ENTRY_MAX_RANK:selected.append(row.sector_code)
    result=ranked[ranked.sector_code.isin(selected)].copy();result["sector_status"]=result.sector_code.map(lambda x:"RETAINED" if x in existing else "NEW_ENTRY")
    return result.sort_values(["strength_rank","sector_code"],kind="stable").reset_index(drop=True)


def eligible_stock_ranks(today: pd.DataFrame, mapping: pd.DataFrame, sector_codes: set[str]) -> pd.DataFrame:
    columns=["symbol","universe_basic_liquid","research_quality_status","close","avg_turnover_20","recent_presence_20"]
    x=today[columns].merge(mapping[["symbol","sector","sector_code","mapping_status","identity_ambiguous"]],on="symbol",how="left",validate="one_to_one")
    x=x[x.sector_code.isin(sector_codes)&x.universe_basic_liquid.fillna(False)&x.research_quality_status.eq("VALID_REPORTED_EQ_ROW")&x.close.gt(0)&x.avg_turnover_20.gt(0)&x.recent_presence_20.fillna(False)&x.mapping_status.eq("STATIC_CURRENT_UNIQUE")&~x.identity_ambiguous.fillna(True)].copy()
    x=x.sort_values(["sector_code","avg_turnover_20","symbol"],ascending=[True,False,True],kind="stable");x["liquidity_rank"]=x.groupby("sector_code").cumcount()+1
    x["signal_series"]="EQ";x["new_entry_eligible"]=x.liquidity_rank.le(STOCK_ENTRY_MAX_RANK)
    return x.reset_index(drop=True)


def stock_plan(today: pd.DataFrame, mapping: pd.DataFrame, selected_sectors: pd.DataFrame,
               holdings: dict[str,str]) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Return intended names and the fully frozen signal-time ranked lists."""
    codes=set(selected_sectors.sector_code);ranks=eligible_stock_ranks(today,mapping,codes);records=[]
    sector_strength=selected_sectors.set_index("sector_code").strength_rank.to_dict()
    for code in selected_sectors.sort_values(["strength_rank","sector_code"]).sector_code:
        group=ranks[ranks.sector_code.eq(code)]
        retained=[s for s,c in holdings.items() if c==code and s in set(group.loc[group.liquidity_rank.le(STOCK_RETENTION_MAX_RANK),"symbol"])]
        retained=sorted(retained,key=lambda s:(int(group.set_index("symbol").loc[s,"liquidity_rank"]),s))[:3]
        chosen=list(retained)
        for row in group[group.new_entry_eligible].itertuples(index=False):
            if len(chosen)>=3:break
            if row.symbol not in holdings and row.symbol not in chosen:chosen.append(row.symbol)
        for symbol in chosen:
            row=group.set_index("symbol").loc[symbol]
            records.append({"symbol":symbol,"sector":row.sector,"sector_code":code,"sector_strength_rank":sector_strength[code],"liquidity_rank":int(row.liquidity_rank),"selection_status":"RETAINED" if symbol in holdings else "NEW_ENTRY","signal_series":"EQ"})
    intended=pd.DataFrame(records,columns=["symbol","sector","sector_code","sector_strength_rank","liquidity_rank","selection_status","signal_series"])
    ranks["sector_strength_rank"]=ranks.sector_code.map(sector_strength)
    return intended.sort_values(["sector_strength_rank","liquidity_rank","symbol"],kind="stable").reset_index(drop=True),ranks.sort_values(["sector_strength_rank","liquidity_rank","symbol"],kind="stable").reset_index(drop=True)


def execution_state(holdings: dict[str,str],intended: pd.DataFrame,replacement_list: pd.DataFrame,
                    execution_quotes: pd.DataFrame) -> tuple[dict[str,str],list[dict]]:
    """Apply only observed opens; no prices, shares, cash, or returns are calculated."""
    state=dict(holdings);events=[];quotes=execution_quotes.set_index(["symbol","series"]) if len(execution_quotes) else pd.DataFrame()
    desired=set(intended.symbol)
    # Exit undesired holdings at an observed EQ or BE open; otherwise remain trapped.
    for symbol in sorted(set(state)-desired):
        candidates=[] if isinstance(quotes,pd.DataFrame) and quotes.empty else [(series,quotes.loc[(symbol,series),"open"]) for series in ("EQ","BE") if (symbol,series) in quotes.index]
        valid=[(series,float(open_)) for series,open_ in candidates if pd.notna(open_) and float(open_)>0]
        if valid:
            state.pop(symbol);events.append({"symbol":symbol,"event":"EXIT","series":valid[0][0],"observed_open_available":True})
        else:events.append({"symbol":symbol,"event":"TRAPPED_RETRY","series":"UNKNOWN","observed_open_available":False})
    # Retained intended positions need no execution.
    for symbol in sorted(desired&set(state)):events.append({"symbol":symbol,"event":"RETAIN","series":"HELD","observed_open_available":True})
    # New entries use only the signal-frozen top-three eligibility list and require EQ.
    intended_by_sector={code:g for code,g in intended.groupby("sector_code",sort=False)}
    for code,planned in sorted(intended_by_sector.items(),key=lambda x:(x[1].sector_strength_rank.min(),x[0])):
        desired_count=len(planned);already=sum(1 for _,c in state.items() if c==code)
        frozen=replacement_list[(replacement_list.sector_code.eq(code))&replacement_list.new_entry_eligible].sort_values(["liquidity_rank","symbol"])
        for row in frozen.itertuples(index=False):
            if already>=desired_count or len(state)>=MAX_POSITIONS:break
            if row.symbol in state:continue
            valid=(not (isinstance(quotes,pd.DataFrame) and quotes.empty) and (row.symbol,"EQ") in quotes.index and pd.notna(quotes.loc[(row.symbol,"EQ"),"open"]) and float(quotes.loc[(row.symbol,"EQ"),"open"])>0)
            if valid:
                state[row.symbol]=code;already+=1;events.append({"symbol":row.symbol,"event":"ENTRY","series":"EQ","observed_open_available":True})
            else:events.append({"symbol":row.symbol,"event":"ENTRY_SKIPPED_NO_EQ_OPEN","series":"EQ","observed_open_available":False})
    return state,events
