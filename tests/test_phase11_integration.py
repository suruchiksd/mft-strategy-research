import json
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def test_holdout_costs_are_adverse_and_all_frozen_cost_scenarios_exist():
    x=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_cost_sensitivity.csv")
    assert set(x.total_bps_per_side)=={0,10,25,50}
    for _,g in x.groupby("universe"):
        assert g.sort_values("total_bps_per_side").cumulative_return.is_monotonic_decreasing

def test_static_sector_caveat_and_rejection_are_explicit():
    text=(ROOT/"reports/phase11_sector_momentum_strategy.md").read_text()
    acceptance=json.loads((ROOT/"reports/sector_strategy/phase11_strategy_acceptance.json").read_text())
    assert "current/static" in text and acceptance["decision"]=="REJECT STRATEGY V1"
    assert not (ROOT/"reports/sector_strategy/paper_handoff/paper_engine_contract.md").exists()

def test_no_negative_cash_no_leverage_and_integer_shares():
    for period in ("development","holdout"):
        curve=pd.read_csv(ROOT/f"reports/sector_strategy/{period}/{period}_equity_curve.csv")
        positions=pd.read_csv(ROOT/f"reports/sector_strategy/{period}/{period}_positions.csv")
        assert curve.cash.min()>=-1e-7 and curve.market_value.le(curve.equity+1e-7).all()
        assert (positions.shares>0).all() and (positions.shares%1==0).all() and positions.weight.max()<0.2

def test_corporate_action_safety_and_frozen_universe_sensitivity():
    targets=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_signal_targets.csv")
    sensitivity=pd.read_csv(ROOT/"reports/sector_strategy/development/development_cost_sensitivity.csv")
    assert targets.corporate_action_safe.all()
    assert set(sensitivity.universe)=={"BASIC_LIQUID","MODERATE_LIQUID"}
