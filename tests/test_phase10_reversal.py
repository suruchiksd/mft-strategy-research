from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from mft_research.reversal import (CANDIDATES, FORMULAS, FUTURES, UNIVERSES,
                                   attach_outcomes_after_ranking, leave_one_date_out,
                                   rank_signal, reversal_values, validate_registry)


def config():
    return yaml.safe_load(open("config/phase10_reversal.yaml"))


def registry():
    return pd.read_csv("reports/reversal/preregistration/reversal_candidate_registry.csv")


def signals():
    return pd.DataFrame({"date":[date(2026,7,20)]*4+[date(2026,7,21)]*4,
      "symbol":["A","B","C","D"]*2,"price_return_5":[.1,-.2,0,.3,.2,-.1,.4,0],
      "price_return_20":[.3,-.1,.2,0,.4,-.2,.1,0],"signal_valid":[True]*8})


def test_exactly_two_primary_candidates():
    assert CANDIDATES == ("REV05","REV20")
    assert tuple(registry().candidate_id) == CANDIDATES


def test_formulas_are_negative_phase9_controls():
    frame=signals()
    pd.testing.assert_series_equal(reversal_values(frame,"REV05"),-frame.price_return_5,check_names=False)
    pd.testing.assert_series_equal(reversal_values(frame,"REV20"),-frame.price_return_20,check_names=False)
    assert FORMULAS == {"REV05":("price_return_5",-1.0),"REV20":("price_return_20",-1.0)}


def test_registry_and_config_validate():
    validate_registry(registry(),config())


def test_future_horizons_frozen():
    assert FUTURES == (1,2,3,5,10,20)


def test_universes_frozen():
    assert UNIVERSES == ("BASIC_LIQUID","MODERATE_LIQUID")


def test_ranking_is_same_date_and_strongest_reversal_highest():
    frame=signals();frame["rev"]=-frame.price_return_5
    ranked=rank_signal(frame,"rev",frame.signal_valid)
    for _,group in ranked.groupby("date"):
        assert group.loc[group.rev.idxmax(),"percentile"]==1
        assert group.cross_section_count.eq(4).all()


def test_ties_are_deterministic_by_symbol():
    frame=pd.DataFrame({"date":[date(2026,7,20)]*3,"symbol":["C","A","B"],"rev":[1.,1.,1.]})
    ranked=rank_signal(frame,"rev",pd.Series(True,index=frame.index)).sort_values("rank")
    assert ranked.symbol.tolist()==["A","B","C"]


def test_future_missingness_does_not_change_signal_rank():
    frame=signals().iloc[:4].copy();frame["rev"]=-frame.price_return_5
    ranked=rank_signal(frame,"rev",frame.signal_valid)
    outcomes=pd.DataFrame({"valid_future_1":[True,False,True,True],"future_return_1":[.1,.2,.3,.4]},index=frame.index)
    kept=attach_outcomes_after_ranking(ranked,outcomes,"valid_future_1","future_return_1")
    assert kept.cross_section_count.eq(4).all()
    assert kept.loc[kept.symbol.eq("B"),"rank"].empty
    assert ranked.loc[ranked.symbol.eq("B"),"rank"].iloc[0]==4


def test_confirmation_boundary_is_strict():
    assert config()["confirmation_signal_start_exclusive"]=="2026-07-17"


def test_discovery_and_confirmation_boundaries_do_not_overlap():
    c=config();assert c["discovery_end"]==c["confirmation_signal_start_exclusive"]


def test_acceptance_rules_frozen_before_outcomes():
    c=config();assert c["acceptance_rules"]["confirmation_positive_horizons_required"]==4
    assert c["confirmation_evaluability"]["minimum_daily_ic_dates_per_horizon"]==20


def test_no_new_candidates_can_validate():
    changed=registry().copy();changed.loc[len(changed)]={column:"REV10" for column in changed.columns}
    with pytest.raises(ValueError):validate_registry(changed,config())


def test_leave_one_date_out_removes_only_one_date():
    daily=pd.DataFrame({"date":[date(2026,7,20),date(2026,7,21),date(2026,7,22)],"ic":[.1,.2,-.1]})
    result=leave_one_date_out(daily)
    assert len(result)==3
    assert np.isclose(result.loc[result.excluded_date.eq(date(2026,7,21)),"leave_one_date_out_mean_ic"].iloc[0],0)


def test_price_only_registry():
    text=" ".join(registry().astype(str).to_numpy().ravel()).lower()
    assert "volume" not in text and "sector" not in text


def test_no_factor_combination_or_trading_contract():
    columns=" ".join(registry().columns).lower()
    assert not any(token in columns for token in ("weight","portfolio","pnl","position","sector"))


def test_corporate_action_gate_is_mandatory():
    assert config()["corporate_action_certification_required"] is True

