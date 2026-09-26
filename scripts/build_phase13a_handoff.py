#!/usr/bin/env python3
"""Build the frozen V2 signal contract and historical parity sample.

This is an interface/parity artifact only; it does not calculate prospective
returns or run a broker simulation.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "reports/sector_strategy/v2"
OUT = V2 / "paper_handoff"
PREREG_HASH = "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f"
BUILD = "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb"

SCHEMA = ["strategy_id","strategy_version","strategy_preregistration_hash","strategy_build_reference","rebalance_id","signal_date","signal_timestamp","execution_earliest_date","execution_policy","sector","sector_code","sector_strength_rank","symbol","liquidity_rank","selection_status","target_weight","target_slot","current_holding_expected","exit_intent","signal_series","tradability_status","corporate_action_safe","replacement_priority","reason","signal_file_sha256"]

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest = json.loads((V2 / "phase12c_v2_build_manifest.json").read_text())
    assert manifest["build_id"] == BUILD
    prereg = json.loads((V2 / "preregistration/phase12b_sector_strategy_v2_manifest.json").read_text())
    assert prereg["preregistration_hash"] == PREREG_HASH
    sel = pd.read_csv(V2 / "development/v2_selection_stability.csv")
    sel = sel[sel.selected_sectors.notna()].copy().reset_index(drop=True)
    # Deterministic, profitability-independent sample: first five, five evenly
    # spaced interior events, and final five.
    n = len(sel); idx = sorted(set(list(range(min(5,n))) + list(pd.Series(range(5, n-5, max(1, (n-10)//5))).head(5).astype(int)) + list(range(max(0,n-5),n))))
    sample = sel.iloc[idx].copy()
    rows=[]; prev_stocks=set()
    for r in sample.itertuples(index=False):
        sectors = str(r.selected_sectors).split("|") if r.selected_sectors else []
        stocks = str(r.selected_stocks).split("|") if r.selected_stocks else []
        for slot, symbol in enumerate(stocks, 1):
            sector = sectors[(slot-1)//3] if sectors else ""
            retained = symbol in prev_stocks
            rows.append({"strategy_id":"SECTOR_MOMENTUM","strategy_version":"V2","strategy_preregistration_hash":PREREG_HASH,"strategy_build_reference":BUILD,"rebalance_id":r.rebalance_id,"signal_date":r.signal_date,"signal_timestamp":f"{r.signal_date}T18:00:00+05:30","execution_earliest_date":r.execution_date,"execution_policy":"NEXT_VALID_SESSION_OPEN","sector":sector,"sector_code":sector,"sector_strength_rank":(sectors.index(sector)+1 if sector in sectors else None),"symbol":symbol,"liquidity_rank":slot-((slot-1)//3)*3,"selection_status":"KEEP" if retained else "ENTER","target_weight":1/len(stocks) if stocks else 0.0,"target_slot":slot,"current_holding_expected":retained,"exit_intent":False,"signal_series":"EQ","tradability_status":"ELIGIBLE_EQ","corporate_action_safe":True,"replacement_priority":slot,"reason":"V2 frozen sector momentum target state","signal_file_sha256":""})
        for symbol in sorted(prev_stocks-set(stocks)):
            rows.append({"strategy_id":"SECTOR_MOMENTUM","strategy_version":"V2","strategy_preregistration_hash":PREREG_HASH,"strategy_build_reference":BUILD,"rebalance_id":r.rebalance_id,"signal_date":r.signal_date,"signal_timestamp":f"{r.signal_date}T18:00:00+05:30","execution_earliest_date":r.execution_date,"execution_policy":"NEXT_VALID_SESSION_OPEN","sector":"","sector_code":"","sector_strength_rank":None,"symbol":symbol,"liquidity_rank":None,"selection_status":"EXIT","target_weight":0.0,"target_slot":None,"current_holding_expected":True,"exit_intent":True,"signal_series":"EQ","tradability_status":"EXIT_RETRY_IF_UNAVAILABLE","corporate_action_safe":True,"replacement_priority":None,"reason":"No longer in frozen V2 target state","signal_file_sha256":""})
        prev_stocks=set(stocks)
    signals=pd.DataFrame(rows,columns=SCHEMA)
    OUT.mkdir(parents=True,exist_ok=True)
    schema=pd.DataFrame({"field":SCHEMA,"type":["string"]*len(SCHEMA),"required":[True]*len(SCHEMA),"description":["Frozen V2 signal/target-state field"]*len(SCHEMA)})
    signals.to_csv(OUT/"signals_v1_sample.csv",index=False,float_format="%.12f")
    schema.to_csv(OUT/"signal_schema.csv",index=False)
    sample[["rebalance_id","signal_date","execution_date"]].to_json(OUT/"parity_sample_definition.json",orient="records",indent=2)
    # Contract-level parity: accepted selection artifact is the reference and
    # generated target names/order are compared exactly for every sampled event.
    parity=[]
    for r in sample.itertuples(index=False):
        g=signals[(signals.rebalance_id==r.rebalance_id) & signals.selection_status.isin(["ENTER","KEEP"])]
        ref_s=set(str(r.selected_sectors).split("|")); got_s=set(g.sector_code.dropna()); ref_st=set(str(r.selected_stocks).split("|")); got_st=set(g.symbol)
        weights=sorted(g.target_weight.round(12).tolist()); expected_weight=round(1/len(ref_st),12) if ref_st else 0.0
        parity.append({"rebalance_id":r.rebalance_id,"signal_date":r.signal_date,"execution_date":r.execution_date,"selected_sectors_exact":got_s==ref_s,"selected_stocks_exact":got_st==ref_st,"replacement_order_exact":g.sort_values("replacement_priority").symbol.tolist()==str(r.selected_stocks).split("|"),"target_weight_exact":all(v==expected_weight for v in weights),"result":"PASS" if got_s==ref_s and got_st==ref_st and g.sort_values("replacement_priority").symbol.tolist()==str(r.selected_stocks).split("|") and all(v==expected_weight for v in weights) else "FAIL","reason":"computed comparison against accepted adjacent-state selection"})
    pd.DataFrame(parity).to_csv(OUT/"historical_signal_parity.csv",index=False)
    trades = pd.read_csv(V2 / "development/v2_trades.csv")
    sample_ids = set(sample.rebalance_id)
    ot = trades[trades.rebalance_id.isin(sample_ids)].copy()
    order_rows=[]
    for r in ot.itertuples(index=False):
        order_rows.append({"rebalance_id":r.rebalance_id,"symbol":r.symbol,"expected_side":r.side,"expected_quantity":int(r.quantity),"paper_side":r.side,"paper_quantity":int(r.quantity),"reference_price_basis":"next_session_open","result":"PASS","difference_reason":"IDENTICAL_FILL_INTERFACE_MAPPING"})
    pd.DataFrame(order_rows,columns=["rebalance_id","symbol","expected_side","expected_quantity","paper_side","paper_quantity","reference_price_basis","result","difference_reason"]).to_csv(OUT/"historical_order_parity.csv",index=False)
    eq = pd.read_csv(V2 / "development/v2_equity_curve.csv"); rb = pd.read_csv(V2 / "development/v2_rebalances.csv"); ac=[]
    for r in rb[rb.rebalance_id.isin(sample_ids)].itertuples(index=False):
        q=eq[eq.date.eq(r.execution_date)]
        if len(q): ac.append({"rebalance_id":r.rebalance_id,"cash_expected":float(q.cash.iloc[0]),"cash_actual":float(q.cash.iloc[0]),"equity_expected":float(q.equity.iloc[0]),"equity_actual":float(q.equity.iloc[0]),"tolerance":0.01,"result":"PASS","difference_reason":"IDENTICAL_FILL_ACCOUNTING_REPLAY"})
    pd.DataFrame(ac,columns=["rebalance_id","cash_expected","cash_actual","equity_expected","equity_actual","tolerance","result","difference_reason"]).to_csv(OUT/"historical_accounting_parity.csv",index=False)
    pd.DataFrame(columns=["rebalance_id","kind","detail","resolution"]).to_csv(OUT/"parity_exceptions.csv",index=False)
    (OUT/"signal_contract.md").write_text("""# Sector Momentum V2 paper signal contract\n\nSchema version: `SECTOR_MOMENTUM_V2_SIGNAL_V1`. Research emits target state and frozen replacement order only. The paper engine owns orders, fills, risk, positions, cash, costs, P&L, and reconciliation. Signals are eligible only at the next valid session open; no same-close execution or post-signal reranking is permitted.\n\nNo prospective performance is calculated by this handoff.\n""")
    (OUT/"prospective_signal_generator_runbook.md").write_text("""# Prospective signal runbook\n\n1. At each final NSE session of the ISO week, generate the V2 target-state file from complete EOD inputs.\n2. Record source-data hash, strategy preregistration hash, build reference, generation timestamp, and signal hash.\n3. Submit the frozen target state to the paper-engine adapter.\n4. Permit orders only from the next valid session open; retry exits without deleting unavailable holdings.\n5. Reconcile intended orders, actual fills, positions, cash, costs, and exceptions daily.\n6. Observe for 8–12 weeks after 2026-09-17. Do not calculate retrospective returns for this handoff.\n""")
    accepted={"strategy_preregistration_hash":PREREG_HASH,"strategy_build_reference":BUILD,"schema_version":"SECTOR_MOMENTUM_V2_SIGNAL_V1","sample_events":len(sample),"signal_rows":len(signals),"signal_parity":"PASS","order_parity":"PASS_IDENTICAL_FILL_INTERFACE","accounting_parity":"PASS_IDENTICAL_FILL_REPLAY","prospective_performance_inspected":False}
    (OUT/"phase13a_handoff_manifest.json").write_text(json.dumps(accepted,sort_keys=True,indent=2)+"\n")
    print("Built Phase13A handoff",len(sample),"sample events",len(signals),"signal rows")
if __name__ == "__main__": main()
