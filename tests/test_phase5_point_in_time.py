from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml

from mft_research.csrs.phase5 import (FORMATIONS, FUTURES, UNIVERSES, add_point_in_time_fields,
    adjust_pvalues, canonicalize_source, daily_statistics, interval_crosses, multiple_testing,
    prepare_intervals, rank_factor)


def config():
    return yaml.safe_load(open("config/phase5_point_in_time.yaml"))


def old_row():
    return pd.DataFrame({"SYMBOL":["A"],"SERIES":["EQ"],"DATE1":["01-Jan-2020"],
        "OPEN_PRICE":["10"],"HIGH_PRICE":["12"],"LOW_PRICE":["9"],"CLOSE_PRICE":["11"],
        "TTL_TRD_QNTY":["100"],"TURNOVER_LACS":["0.011"],"PREV_CLOSE":["10"],
        "LAST_PRICE":["11"],"AVG_PRICE":["11"],"NO_OF_TRADES":["1"],"DELIV_QTY":["1"],"DELIV_PER":["1"]})


def new_row():
    return pd.DataFrame({"TradDt":["2024-07-08"],"TckrSymb":["A"],"SctySrs":["EQ"],
        "OpnPric":["10"],"HghPric":["12"],"LwPric":["9"],"ClsPric":["11"],
        "TtlTradgVol":["100"],"TtlTrfVal":["1100"],"ISIN":["I"],"FinInstrmId":["1"],"FinInstrmNm":["A LTD"]})


def test_turnover_units_normalize_old_and_new():
    assert canonicalize_source(old_row(),"OLD","x").turnover_rupees.iloc[0] == 1100
    assert canonicalize_source(new_row(),"NEW","y").turnover_rupees.iloc[0] == 1100


def test_base_filter_is_literal_eq_and_horizons_are_frozen():
    raw=pd.concat([old_row(),old_row().assign(SERIES="BE",SYMBOL="B")],ignore_index=True)
    normalized=canonicalize_source(raw,"OLD","x")
    assert normalized.loc[normalized.series.eq("EQ"),"symbol"].tolist()==["A"]
    assert FORMATIONS==(5,10,20,40,60) and FUTURES==(1,2,3,5,10,20)
    assert UNIVERSES==("BROAD_EQ","BASIC_LIQUID","MODERATE_LIQUID","STRICT_SENSITIVITY")


def synthetic_daily(extra_future=False):
    rows=[]
    days=[date(2020,1,1)+timedelta(days=i) for i in range(150)]
    for symbol,mult,start in (("A",1,0),("B",2,20)):
        for i,day in enumerate(days[start:]):
            rows.append({"date":day,"symbol":symbol,"series":"EQ","open":10+i*mult,"high":11+i*mult,
                "low":9+i*mult,"close":10+i*mult,"volume":1000+i,"turnover_rupees":2e8,
                "isin":pd.NA,"instrument_id":pd.NA,"security_name":pd.NA,"source_format":"OLD","source_file":"x"})
    if extra_future:
        rows.append({**rows[-1],"date":days[-1]+timedelta(days=1),"close":9999})
    return pd.DataFrame(rows)


def add_fields(frame):
    sectors=pd.DataFrame({"symbol":["A","B"],"sector":[None,None],"sector_code":[None,None],"sector_mapping_status":["UNMAPPED","UNMAPPED"]})
    actions=pd.DataFrame(columns=["symbol","date","series","research_impact"])
    return add_point_in_time_fields(frame,config(),actions,sectors)


def test_membership_and_rolling_fields_use_no_future_information():
    base=add_fields(synthetic_daily(False)); extended=add_fields(synthetic_daily(True))
    columns=["history_sessions","prior_history_sessions","avg_volume_20","avg_turnover_20",
             "universe_basic_liquid","universe_moderate_liquid"]
    left=base[base.symbol.eq("A")].iloc[:100][columns].reset_index(drop=True)
    right=extended[extended.symbol.eq("A")].iloc[:100][columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(left,right)
    assert not base.loc[base.symbol.eq("B"),"universe_basic_liquid"].iloc[:60].any()


def test_new_listing_and_disappearance_are_observation_based():
    frame=add_fields(synthetic_daily())
    assert frame.loc[frame.symbol.eq("B"),"first_observed_date"].iloc[0] == date(2020,1,21)
    assert frame.loc[frame.symbol.eq("A"),"history_sessions"].max()==150
    assert frame.loc[frame.symbol.eq("B"),"history_sessions"].max()==130


def test_interval_crossing_exact_symbol_and_dates_only():
    symbols=pd.Series(["A","A","B"]); starts=pd.Series([date(2020,1,1)]*3); ends=pd.Series([date(2020,1,5),date(2020,1,2),date(2020,1,5)])
    events={"A":np.array([np.datetime64("2020-01-03")])}
    assert interval_crosses(symbols,starts,ends,events).tolist()==[True,False,False]


def test_recorded_blocking_action_invalidates_factor_and_future_but_dividend_does_not():
    frame=add_fields(synthetic_daily().query("symbol == 'A'").iloc[:100].copy())
    blocking=pd.DataFrame({"symbol":["A"],"date":[date(2020,1,12)],"series":["EQ"],"research_impact":["UNKNOWN_OR_AMBIGUOUS"]})
    result=prepare_intervals(frame,config(),blocking)
    crossing=result.index[frame.date.eq(date(2020,1,15))][0]
    assert not result.loc[crossing,"valid_factor_primary_5"]
    start=result.index[frame.date.eq(date(2020,1,9))][0]
    assert not result.loc[start,"valid_future_primary_5"]
    dividend=blocking.assign(research_impact="NO_PRICE_ADJUSTMENT_NEEDED_FOR_PRICE_MOMENTUM")
    safe=prepare_intervals(frame,config(),dividend)
    assert safe.loc[crossing,"valid_factor_primary_5"]


def test_corporate_action_cutoff_blocks_primary_but_not_broad():
    raw=synthetic_daily().query("symbol == 'A'").copy()
    raw["date"]=[date(2026,7,1)+timedelta(days=i) for i in range(len(raw))]
    frame=add_fields(raw)
    empty=pd.DataFrame(columns=["symbol","date","series","research_impact"])
    result=prepare_intervals(frame,config(),empty)
    after=result.index[frame.date.gt(date(2026,7,17)) & result.ret_5.notna()][0]
    assert not result.loc[after,"valid_factor_primary_5"] and result.loc[after,"valid_factor_broad_5"]


def test_ranking_is_same_date_selected_universe_and_deterministic_ties():
    intervals=pd.DataFrame({"date":[date(2020,1,1)]*3+[date(2020,1,2)]*2,"symbol":["B","A","C","A","B"],
        "ret_5":[.2,.2,-.1,.1,.3],"valid_factor_primary_5":[True]*5})
    ranked=rank_factor(intervals,pd.Series([True,True,False,True,True]),5,"PRIMARY_VERIFIED")
    first=ranked[ranked.date.eq(date(2020,1,1))]
    assert first.sort_values("rank").symbol.tolist()==["A","B"]
    assert first.loc[first.symbol.eq("B"),"percentile"].iloc[0]==1
    assert ranked[ranked.date.eq(date(2020,1,2))].cross_section_count.eq(2).all()


def test_vector_daily_ic_and_deciles_match_known_example():
    work=pd.DataFrame({"date":[date(2024,1,1)]*10,"symbol":list("ABCDEFGHIJ"),
        "rank":range(1,11),"percentile":np.arange(10)/9,"cross_section_count":10,
        "outcome":[10,9,8,7,6,5,4,3,2,1]})
    result=daily_statistics(work).iloc[0]
    assert np.isclose(result.ic,-1)
    assert result.q1_count==1 and result.q10_count==1
    assert np.isclose(result.daily_spread,-9)


def test_multiple_testing_uses_each_30_test_family():
    rows=[]
    for f in FORMATIONS:
        for h in FUTURES:
            for stat in ("MEAN_RANK_IC","MEAN_DAILY_D10_D1_SPREAD"):
                rows.append({"analysis_tier":"PRIMARY_VERIFIED","universe":"BROAD_EQ","statistic":stat,
                             "formation_horizon":f,"future_horizon":h,"raw_p_value":.01})
    result=multiple_testing(pd.DataFrame(rows),.05)
    assert len(result)==60
    assert result.groupby("statistic").size().eq(30).all()
    assert result["benjamini_hochberg_p_value"].between(0,1).all()
    assert result["holm_p_value"].between(0,1).all()


def test_adjusted_pvalues_are_monotone_and_bounded():
    p=pd.Series([.001,.01,.2,.8])
    assert np.all(np.diff(adjust_pvalues(p,"BENJAMINI_HOCHBERG"))>=0)
    assert np.all((adjust_pvalues(p,"HOLM")>=0)&(adjust_pvalues(p,"HOLM")<=1))


def test_no_combined_weighted_or_portfolio_contract_in_phase5_module():
    columns=set(canonicalize_source(old_row(),"OLD","x").columns)
    assert not any(token in column.lower() for column in columns for token in ("combined","weighted","portfolio","pnl"))
