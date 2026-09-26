from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml

from mft_research.csrs.phase4 import moving_block_bootstrap
from mft_research.sector_momentum import (FORMATIONS, FUTURES, MAPPING_TIERS, PRIMARY_SIZE,
    SIZE_THRESHOLDS, aggregate_sector_daily, build_factor_panel, daily_pair_statistics,
    multiple_testing, pair_work, stock_daily_returns)


def phase5_config():
    return yaml.safe_load(open("config/phase5_point_in_time.yaml"))


def mapping(symbols, sectors=None):
    sectors=sectors or ["one"]*len(symbols)
    return pd.DataFrame({"symbol":symbols,"sector":sectors,"sector_code":[s.upper()[:2] for s in sectors],
        "mapping_status":["STATIC_CURRENT_UNIQUE"]*len(symbols),"identity_ambiguous":[False]*len(symbols)})


def stock_frame(symbols=("A","B","C"), days=8):
    rows=[]; calendar=[date(2020,1,9)+timedelta(days=i) for i in range(days)]
    for s_i,symbol in enumerate(symbols):
        for position,day in enumerate(calendar):
            rows.append({"date":day,"symbol":symbol,"close":100+s_i*10+position,
                "session_position":position,"research_quality_status":"VALID_REPORTED_EQ_ROW",
                "universe_basic_liquid":True,"universe_broad_eq":True,"universe_moderate_liquid":True})
    return pd.DataFrame(rows)


def test_stock_return_uses_adjacent_safe_trading_sessions_and_future_row_does_not_change_past():
    empty=pd.DataFrame(columns=["symbol","date","series","research_impact"])
    base=stock_daily_returns(stock_frame(days=5),empty,phase5_config())
    extended=stock_daily_returns(stock_frame(days=6),empty,phase5_config())
    matched=base[["symbol","date","stock_daily_return"]].merge(
        extended[["symbol","date","stock_daily_return"]],on=["symbol","date"],suffixes=("_base","_extended"))
    pd.testing.assert_series_equal(matched.stock_daily_return_base,matched.stock_daily_return_extended,check_names=False)
    row=base[(base.symbol.eq("A"))&base.session_position.eq(1)].iloc[0]
    assert np.isclose(row.stock_daily_return,101/100-1)


def test_daily_sector_return_is_equal_weight_same_day_and_thresholded():
    frame=stock_frame(days=3); empty=pd.DataFrame(columns=["symbol","date","series","research_impact"])
    frame=stock_daily_returns(frame,empty,phase5_config())
    # Exclude C only on the final date; earlier membership remains unchanged.
    frame.loc[(frame.symbol.eq("C"))&frame.session_position.eq(2),"universe_basic_liquid"]=False
    spec={"universe_column":"universe_basic_liquid","require_unique_mapping":True,"require_stable_identity":True}
    result=aggregate_sector_daily(frame,mapping(["A","B","C"]),spec,"X",2)
    final=result[result.session_position.eq(2)].iloc[0]
    prior=result[result.session_position.eq(1)].iloc[0]
    expected=np.mean([102/101-1,112/111-1])
    assert final.constituent_count==2 and np.isclose(final.sector_daily_return,expected)
    assert prior.constituent_count==3  # Date-T membership was not backfilled to the prior date.
    strict=aggregate_sector_daily(frame,mapping(["A","B","C"]),spec,"X",3)
    assert not strict.loc[strict.session_position.eq(2),"valid_sector_daily_return"].iloc[0]


def sector_series(returns, positions=None, sector="alpha", code="AA"):
    positions=positions or list(range(len(returns)))
    return pd.DataFrame({"date":[date(2020,1,1)+timedelta(days=i) for i in positions],
        "session_position":positions,"sector":[sector]*len(returns),"sector_code":[code]*len(returns),
        "eligible_constituent_count":[5]*len(returns),"constituent_count":[5]*len(returns),
        "sector_daily_return":returns,"invalid_constituent_count":[0]*len(returns),
        "valid_sector_daily_return":[True]*len(returns),"sector_daily_invalid_reason":[""]*len(returns),
        "research_tier":["X"]*len(returns),"minimum_sector_size":[5]*len(returns),
        "mapping_provenance":["STATIC_CURRENT_NO_EFFECTIVE_DATES"]*len(returns)})


def test_formation_compounds_sessions_and_future_starts_after_signal():
    returns=[.01,.02,.03,.04,.05,.06]
    panel=build_factor_panel(sector_series(returns),formations=(5,),futures=(1,2))
    row=panel[panel.session_position.eq(4)].iloc[0]
    assert np.isclose(row.sector_ret_5,np.prod(1+np.array(returns[:5]))-1)
    assert np.isclose(row.future_sector_ret_1,returns[5])
    assert not np.isclose(row.future_sector_ret_1,returns[4])
    extended=build_factor_panel(sector_series(returns+[.50]),formations=(5,),futures=(1,2))
    original=panel.loc[panel.session_position.le(4),["session_position","sector_ret_5"]].reset_index(drop=True)
    later=extended.loc[extended.session_position.le(4),["session_position","sector_ret_5"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(original,later)


def test_missing_exchange_session_invalidates_compound_interval():
    panel=build_factor_panel(sector_series([.01]*5,positions=[0,1,2,4,5]),formations=(5,),futures=(1,))
    assert not panel.valid_sector_ret_5.any()


def test_ranking_same_date_strongest_percentile_and_ties_deterministic():
    pieces=[]
    for sector,code,last in (("alpha","AA",.05),("beta","BB",.05),("gamma","CC",-.01)):
        pieces.append(sector_series([.01,.01,.01,.01,last],sector=sector,code=code))
    panel=build_factor_panel(pd.concat(pieces,ignore_index=True),formations=(5,),futures=(1,))
    day=panel[panel.session_position.eq(4)].sort_values("sector_code")
    assert day.set_index("sector_code").loc["BB","sector_rank_5"] > day.set_index("sector_code").loc["AA","sector_rank_5"]
    assert day.loc[day.sector_rank_5.idxmax(),"sector_pct_5"]==1


def test_quintiles_only_when_at_least_15_and_q5_is_strongest():
    rows=[]
    for i in range(15):
        rows.append({"date":date(2020,1,1),"session_position":0,"sector":str(i),"sector_code":str(i),
                     "factor":i,"rank":i+1,"percentile":i/14,"eligible_sector_count":15,"outcome":i})
    work=pd.DataFrame(rows); count=work.eligible_sector_count
    work["quintile"]=np.where(count.ge(15),((work["rank"]-1)*5//count)+1,0).astype(int)
    for label in ("top20","bottom20","top3","bottom3"): work[label]=False
    daily=daily_pair_statistics(work)
    assert daily.quantile_available.iloc[0] and daily.q5_mean.iloc[0] > daily.q1_mean.iloc[0]
    work=work.iloc[:14].copy(); work["eligible_sector_count"]=14; work["quintile"]=0
    assert not daily_pair_statistics(work).quantile_available.iloc[0]


def test_frozen_grids_tiers_and_sizes():
    assert FORMATIONS==(5,10,20,40,60) and FUTURES==(1,2,3,5,10,20)
    assert len({(f,h) for f in FORMATIONS for h in FUTURES})==30
    assert SIZE_THRESHOLDS==(3,5,10) and PRIMARY_SIZE==5
    assert MAPPING_TIERS==("STABLE_IDENTITY_BASIC_LIQUID","STABLE_IDENTITY_MODERATE_LIQUID",
                           "STABLE_IDENTITY_BROAD","STATIC_UNIQUE_BROAD")


def test_bootstrap_is_deterministic():
    values=np.linspace(-.1,.1,100)
    assert moving_block_bootstrap(values,10,50,123,.95)==moving_block_bootstrap(values,10,50,123,.95)


def test_multiple_testing_family_is_exactly_30():
    rows=[{"formation_horizon":f,"future_horizon":h,"statistic":"MEAN_RANK_IC","estimate":.01,
           "ci_lower":-.01,"ci_upper":.02,"raw_p_value":.1,"block_length_sessions":10,
           "replications":10,"seed":1,"method":"x","valid_dates":10} for f in FORMATIONS for h in FUTURES]
    result=multiple_testing(pd.DataFrame(rows),.05)
    assert len(result)==30 and result.test_family.eq("30_PRIMARY_RANK_IC_HYPOTHESES").all()


def test_no_combined_weighted_or_portfolio_fields():
    panel=build_factor_panel(sector_series([.01]*7),formations=(5,),futures=(1,))
    assert not any(token in column.lower() for column in panel.columns for token in
                   ("combined","weighted_factor","portfolio","pnl","trading_return"))
