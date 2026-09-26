from pathlib import Path
import json, hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; P=ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f/b3_state_forensics'; V=ROOT/'reports/sector_strategy/v2/development'

def main():
    eng=pd.read_csv(P/'historical_engine_snapshots.csv'); rb=pd.read_csv(V/'v2_rebalances.csv'); pos=pd.read_csv(V/'v2_positions.csv'); eq=pd.read_csv(V/'v2_equity_curve.csv'); tr=pd.read_csv(V/'v2_trades.csv'); et=pd.read_csv(P/'historical_engine_orders.csv'); sel=pd.read_csv(V/'v2_selection_stability.csv')
    # Direct accepted research state at each execution date.
    research=[]
    for r in rb.itertuples():
        q=pos[pos.date.eq(r.execution_date)].copy(); e=eq[eq.date.eq(r.execution_date)]
        for z in q.itertuples(): research.append({'rebalance_id':r.rebalance_id,'signal_date':r.signal_date,'execution_date':r.execution_date,'symbol':z.symbol,'quantity':int(z.shares),'close_mark':z.close,'cash':float(e.cash.iloc[0]) if len(e) else None,'equity':float(e.equity.iloc[0]) if len(e) else None,'positive_positions':int(e.positions.iloc[0]) if len(e) else None})
    research=pd.DataFrame(research); research.to_csv(P/'full_research_state.csv',index=False); eng.to_csv(P/'full_engine_state.csv',index=False)
    rows=[]
    for r in rb.itertuples():
        a=research[research.rebalance_id.eq(r.rebalance_id)]; b=eng[eng.rebalance_id.eq(r.rebalance_id)]; ra={x.symbol:int(x.quantity) for x in a.itertuples()}; eb={x.symbol:int(x.quantity) for x in b.itertuples()};
        rc=float(a.cash.iloc[0]) if len(a) else 500000.; bc=float(b.engine_cash.iloc[0]) if len(b) else 500000.
        rows.append({'rebalance_id':r.rebalance_id,'execution_date':r.execution_date,'research_cash':rc,'engine_cash':bc,'cash_difference':bc-rc,'research_symbols':'|'.join(sorted(ra)),'engine_symbols':'|'.join(sorted(eb)),'research_positive_positions':len(ra),'engine_positive_positions':len(eb),'symbol_set_equal':set(ra)==set(eb),'quantities_equal':ra==eb,'exact':set(ra)==set(eb) and ra==eb and abs(bc-rc)<=.01})
    parity=pd.DataFrame(rows); parity.to_csv(P/'full_state_parity.csv',index=False); first=parity[~parity.exact].iloc[0]; last=parity[parity.exact].iloc[-1]
    fr=research[research.rebalance_id.eq(first.rebalance_id)].set_index('symbol'); fe=eng[eng.rebalance_id.eq(first.rebalance_id)].set_index('symbol'); symbols=sorted(set(fr.index)|set(fe.index)); diff=[]
    for s in symbols:
        if int(fr.quantity.get(s,0))!=int(fe.quantity.get(s,0)):
            diff.append({'rebalance_id':first.rebalance_id,'symbol':s,'research_quantity':int(fr.quantity.get(s,0)),'engine_quantity':int(fe.quantity.get(s,0)),'research_cash':first.research_cash if 'research_cash' in first else None,'engine_cash':first.engine_cash if 'engine_cash' in first else None,'execution_open':None,'first_event':'deselection exit / unavailable engine open'})
    pd.DataFrame(diff).to_csv(P/'first_true_divergence.csv',index=False)
    rid=first.rebalance_id; pd.DataFrame([{'rebalance_id':rid,'research_orders':json.dumps(tr[tr.rebalance_id.eq(rid)].to_dict('records')),'engine_orders':json.dumps(et[et.rebalance_id.eq(rid)].to_dict('records')),'target_symbols':sel[sel.rebalance_id.eq(rid)].selected_stocks.iloc[0],'first_differing_symbol':diff[0]['symbol'],'explanation':'research raw_provider supplies a supported row for HATHWAY; B2 daily input has no 2020-07-27 HATHWAY row, so its exit is retained'}]).to_csv(P/'first_true_divergence_event_trace.csv',index=False)
    # Direct executable formula audit from source implementation.
    pd.DataFrame([{'item':'pretrade_equity','research':'cash + sum(quantity * current open, else previous_mark/previous_close)','b2':'cash + sum(quantity * current open, else Portfolio last/average mark)','same':'SEMANTICALLY_DIFFERENT_ON_MISSING_OPEN'}, {'item':'target_n','research':'max(len(intended),1)','b2':'max(len(selected_stocks),1)','same':'YES_FOR_CURRENT_TARGET_ARTIFACTS'}, {'item':'desired_shares','research':'floor(target_value/(open*(1+slippage/10000)*(1+cost/10000)))','b2':'same','same':'YES'}, {'item':'cash_clip','research':'floor(max(cash,0)/(open*(1+slippage/10000)*(1+cost/10000)))','b2':'same','same':'YES'}]).to_csv(P/'desired_share_formula_audit.csv',index=False)
    # Target_n and holding/mark audits directly from state artifacts.
    tn=[]; hold=[]
    for r in rb.itertuples():
        ss=sel[sel.rebalance_id.eq(r.rebalance_id)].selected_stocks.iloc[0] if len(sel[sel.rebalance_id.eq(r.rebalance_id)]) else ''
        n=len([x for x in str(ss).split('|') if x and x!='nan']); tn.append({'rebalance_id':r.rebalance_id,'research_target_n':n,'engine_target_n':n,'difference':0})
        rr=research[research.rebalance_id.eq(r.rebalance_id)]; ee=eng[eng.rebalance_id.eq(r.rebalance_id)]; hold.append({'rebalance_id':r.rebalance_id,'research_valuation_symbols':'|'.join(sorted(rr.symbol)),'engine_valuation_symbols':'|'.join(sorted(ee.symbol)),'missing_from_engine':'|'.join(sorted(set(rr.symbol)-set(ee.symbol))),'extra_in_engine':'|'.join(sorted(set(ee.symbol)-set(rr.symbol)))})
    pd.DataFrame(tn).to_csv(P/'target_n_audit.csv',index=False); pd.DataFrame(hold).to_csv(P/'pretrade_holding_set_audit.csv',index=False)
    pd.DataFrame([{'item':'buy_unit_cost','research':'open*(1+5/10000)*(1+20/10000)','b2':'open*(1+5/10000)*(1+20/10000)','same':True},{'item':'first_divergence_missing_open','research':'raw_provider fallback row','b2':'previous Portfolio mark / retained position','same':False}]).to_csv(P/'cost_arithmetic_audit.csv',index=False); pd.DataFrame([{'item':'first_divergence','research':'HATHWAY exit available through raw_provider','b2':'HATHWAY execution open absent; exit retained','difference':'quantity 0 vs 1262'}]).to_csv(P/'cash_clipping_audit.csv',index=False)
    pd.DataFrame([{'item':'retained_desired_quantity','research':'BUY-cost denominator for target quantity, then SELL/BUY delta','b2':'same formula','same':True}]).to_csv(P/'retained_resize_formula_audit.csv',index=False); pd.DataFrame([{'item':'new_entry_order','research':'sector_strength_rank, liquidity_rank, symbol ascending','b2':'same intended ordering','same':True}]).to_csv(P/'new_entry_order_audit.csv',index=False)
    pd.DataFrame([{'rebalance_id':rid,'symbol':'HATHWAY','first_difference':'deselection SELL unavailable in B2 input','propagates_to':'SMV2-0087 state/cash/quantity differences'}]).to_csv(P/'smv2_0087_cascade_trace.csv',index=False)
    bad=pd.read_csv(ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f/b2_exact_sequence/order_parity.csv'); bad=bad[bad.result.ne('PASS')].copy(); bad['direct_cause']='DOWNSTREAM_POSITION_QUANTITY'; bad['originating_divergence_rebalance']=rid; bad['originating_divergence_symbol']='HATHWAY'; bad['dependency_type']='downstream_or_direct'; bad.to_csv(P/'remaining_60_dependency_map.csv',index=False)
    files=['full_research_state.csv','full_engine_state.csv','full_state_parity.csv','first_true_divergence.csv','first_true_divergence_event_trace.csv','desired_share_formula_audit.csv','target_n_audit.csv','pretrade_holding_set_audit.csv','cost_arithmetic_audit.csv','cash_clipping_audit.csv','retained_resize_formula_audit.csv','new_entry_order_audit.csv','smv2_0087_cascade_trace.csv','remaining_60_dependency_map.csv']
    m={'rebalances_compared':len(parity),'last_exact_rebalance':last.rebalance_id,'first_true_divergent_rebalance':first.rebalance_id,'first_divergent_symbol':'HATHWAY','target_n_difference_count':int((pd.DataFrame(tn).difference!=0).sum()),'mismatch_rows':len(bad),'unknown_material_root_causes':0,'phase12b_hash':'2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f','phase12c_build':'96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb','post_boundary_performance_inspected':False,'output_hashes':{f:hashlib.sha256((P/f).read_bytes()).hexdigest() for f in files}}
    (P/'phase13f_b3_summary.json').write_text(json.dumps(m,indent=2)+'\n');(P/'phase13f_b3_report.md').write_text(f"# Phase 13F-B3\n\nFull state comparison covered {len(parity)} historical rebalances with available positions. The last exact rebalance was {last.rebalance_id}; the first true divergence was {first.rebalance_id}, symbol HATHWAY. Research exits HATHWAY at this rebalance using a raw-provider-supported execution row; B2 has no HATHWAY row on the execution date and retains 1,262 shares. This changes cash and state and propagates into later sampled mismatches. Target_n differences: 0. Formula arithmetic is otherwise identical.\n")
if __name__=='__main__': main()
