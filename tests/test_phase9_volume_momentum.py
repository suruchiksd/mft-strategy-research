from datetime import date

import numpy as np
import pandas as pd
import yaml

from mft_research.volume_momentum_research import (CANDIDATES, FUTURES, INTERACTIONS, ROLES,
    adjust_family, build_panel, daily_statistics, pair_work, rank_same_date, residualize_same_date,
    uncertainty, validate_config)


def config():
    return yaml.safe_load(open("config/phase9_volume_momentum_research.yaml"))


def registry():
    return pd.read_csv("reports/volume_momentum/foundation/candidate_factor_registry.csv")


def synthetic(sessions=90, symbols=("A", "B"), start="2024-01-02"):
    days=pd.bdate_range(start,periods=sessions).date; rows=[]
    for j,symbol in enumerate(symbols):
      for i,day in enumerate(days):
        row={"date":day,"symbol":symbol,"source_format":"OLD","session_position":i,"close":100+i*(j+1),
             "research_quality_status":"VALID_REPORTED_EQ_ROW","universe_basic_liquid":True,"universe_moderate_liquid":True,
             "valid_price_return_5":i>=5,"price_return_5_invalid_reason":"" if i>=5 else "INSUFFICIENT_HISTORY",
             "valid_price_return_20":i>=20,"price_return_20_invalid_reason":"" if i>=20 else "INSUFFICIENT_HISTORY",
             "valid_volume_baseline_20":i>=20,"volume_baseline_20_invalid_reason":"" if i>=20 else "INSUFFICIENT_HISTORY",
             "valid_volume_baseline_60":i>=60,"volume_baseline_60_invalid_reason":"" if i>=60 else "INSUFFICIENT_HISTORY"}
        values={"vm01":i/100+j/1000,"vm02":i/50+j/1000,"vm03":i/200+j/1000,"vm04":i/300+j/1000,
                "vm05":i/400+j/1000,"vm06":i/500+j/1000,"vm07":i/600+j/1000}
        for key,value in values.items():
          row[f"candidate_{key}"]=value
          if int(key[-2:])>=5:
            row.pop(f"candidate_{key}"); row[f"candidate_{key}_basic_liquid"]=value; row[f"candidate_{key}_moderate_liquid"]=value
        rows.append(row)
    return pd.DataFrame(rows)


def identity(symbols=("A","B")):
    return pd.DataFrame({"symbol":list(symbols),"identity_ambiguity":False})


def actions(day=None):
    if day is None: return pd.DataFrame(columns=["symbol","date","series","research_impact"])
    return pd.DataFrame({"symbol":["A"],"date":[day],"series":["EQ"],"research_impact":["UNKNOWN_OR_AMBIGUOUS"]})


def test_registry_candidates_roles_horizons_and_maps_frozen():
    validate_config(config(),registry())
    assert CANDIDATES==("VM01","VM02","VM03","VM04","VM05","VM06","VM07")
    assert FUTURES==(1,2,3,5,10,20)
    assert INTERACTIONS=={"VM05":("VM01","VM03"),"VM06":("VM02","VM03"),"VM07":("VM02","VM04")}
    assert ROLES["VM01"]=="CONTROL_PRICE" and ROLES["VM03"]=="CONTROL_VOLUME" and ROLES["VM05"]=="INTERACTION"


def test_future_returns_begin_after_t_and_spacing_is_exact():
    p=build_panel(synthetic(),identity(),actions(),registry(),config()); a=p[p.symbol.eq("A")].sort_values("date").reset_index(drop=True)
    assert np.isclose(a.loc[20,"future_return_1"],121/120-1)
    assert np.isclose(a.loc[20,"future_return_5"],125/120-1)
    assert a.loc[20+5,"session_position"]-a.loc[20,"session_position"]==5


def test_blocked_action_crossing_invalidates_outcome():
    raw=synthetic(); day=sorted(raw.date.unique())[22]
    p=build_panel(raw,identity(),actions(day),registry(),config()); a=p[p.symbol.eq("A")].sort_values("date").reset_index(drop=True)
    assert not a.loc[20,"valid_future_5"]
    assert a.loc[20,"future_invalid_reason_5"]=="CORPORATE_ACTION_INTERVAL_BLOCKED"


def test_certified_cutoff_enforced():
    raw=synthetic(30,start="2026-07-01"); p=build_panel(raw,identity(),actions(),registry(),config())
    after=p.date.gt(date(2026,7,17)); assert not p.loc[after,[f"valid_future_{h}" for h in FUTURES]].to_numpy().any()


def test_same_date_ranking_ties_and_highest_percentile():
    frame=pd.DataFrame({"date":[date(2024,1,1)]*3+[date(2024,1,2)]*2,"symbol":["B","A","C","A","B"],"x":[2,2,1,10,20]})
    rank,pct,count=rank_same_date(frame,"x",pd.Series(True,index=frame.index))
    assert rank.tolist()==[3,2,1,1,2] and pct.tolist()==[1,.5,0,0,1] and count.tolist()==[3,3,3,2,2]


def test_residualization_uses_same_date_factor_information_only():
    panel=pd.DataFrame({"date":[date(2024,1,1)]*4+[date(2024,1,2)]*4,
      "vm05_pct_basic_liquid":[0,.2,.7,1,.1,.3,.8,.9],"vm01_pct_basic_liquid":[0,.3,.6,1,0,.4,.7,1],
      "vm03_pct_basic_liquid":[.1,.2,.8,.9,.2,.3,.7,.8],"future_return_1":np.arange(8)})
    first=residualize_same_date(panel,"VM05",("VM01","VM03"),"basic_liquid")
    panel["future_return_1"]=-999
    second=residualize_same_date(panel,"VM05",("VM01","VM03"),"basic_liquid")
    pd.testing.assert_series_equal(first,second)


def test_decile_d10_is_strongest_and_d1_weakest():
    rows=[]
    for i in range(20): rows.append({"date":date(2024,1,1),"symbol":f"S{i:02}","session_position":0,"source_format":"OLD",
      "vm01_raw_basic_liquid":i,"valid_vm01_basic_liquid":True,"vm01_rank_basic_liquid":i+1,
      "vm01_pct_basic_liquid":i/19,"vm01_count_basic_liquid":20,"valid_future_1":True,"future_return_1":i/100,
      "near_recorded_action_5_sessions":False})
    work=pair_work(pd.DataFrame(rows),"VM01",1,"BASIC_LIQUID")
    assert work.loc[work.decile.eq(10),"factor"].min()>work.loc[work.decile.eq(1),"factor"].max()
    assert daily_statistics(work).iloc[0].d10_d1_spread>0


def test_future_availability_does_not_change_factor_ranks():
    rows=[]
    for i in range(20): rows.append({"date":date(2024,1,1),"symbol":f"S{i:02}","session_position":0,"source_format":"OLD",
      "vm01_raw_basic_liquid":i,"valid_vm01_basic_liquid":True,"vm01_rank_basic_liquid":i+1,
      "vm01_pct_basic_liquid":i/19,"vm01_count_basic_liquid":20,"valid_future_1":i!=10,"future_return_1":i/100,
      "near_recorded_action_5_sessions":False})
    work=pair_work(pd.DataFrame(rows),"VM01",1,"BASIC_LIQUID")
    assert work.cross_section_count.eq(20).all()
    assert work.loc[work.symbol.eq("S19"),"rank"].iloc[0]==20


def test_bootstrap_and_adjustment_are_deterministic_and_separate():
    values=pd.Series(np.linspace(-.1,.2,200)); a=uncertainty(values,5,123,config()); b=uncertainty(values,5,123,config())
    assert a==b
    primary=pd.DataFrame({"raw_p_value":[.01]*42,"estimate":[.1]*42})
    incremental=pd.DataFrame({"raw_p_value":[.02]*18,"estimate":[-.1]*18})
    assert len(adjust_family(primary,"42_PRIMARY",.05))==42
    assert len(adjust_family(incremental,"18_INCREMENTAL",.05))==18


def test_no_other_factor_combination_or_trading_contract():
    p=build_panel(synthetic(),identity(),actions(),registry(),config())
    forbidden=("sector_momentum","csrs","reversal_factor","combined","portfolio","pnl","trading_return","position_size")
    assert not any(token in column.lower() for column in p.columns for token in forbidden)
