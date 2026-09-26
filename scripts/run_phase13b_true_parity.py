from __future__ import annotations
import sys
import os
import time
from pathlib import Path
import pandas as pd
sys.path.insert(0,'/home/suruchi-pandey/Projects/paper-trading-engine/src')
from paper_trading.models import Instrument, OrderRequest, OrderType, Side, Candle, TradeIntent
from paper_trading.execution.paper import PaperBroker, SlippageConfig
from paper_trading.execution.costs import BasisPointsTransactionCosts
from paper_trading.execution.manager import OrderManager
from paper_trading.portfolio.accounting import Portfolio
from paper_trading.risk.manager import RiskManager,RiskLimits
ROOT=Path(__file__).resolve().parents[1]; V2=ROOT/'reports/sector_strategy/v2'; OUT=Path(os.environ.get('PARITY_OUT', str(V2/'paper_handoff')))
sys.path.insert(0,str(ROOT/'src'))
from mft_research.csrs.phase5 import read_source, canonicalize_source, source_format
def main():
 sel=pd.read_csv(V2/'development/v2_selection_stability.csv'); rb=sel; eq=pd.read_csv(V2/'development/v2_equity_curve.csv'); pos=pd.read_csv(V2/'development/v2_positions.csv'); sample=set(pd.read_json(OUT/'parity_sample_definition.json').rebalance_id)
 started=time.perf_counter(); progress_path=os.environ.get('PROGRESS_LOG'); timing={'daily_load_seconds':0.0,'raw_read_seconds':0.0,'canonicalize_seconds':0.0}
 t0=time.perf_counter(); daily=pd.concat([pd.read_parquet(ROOT/'data/derived/historical_nse_daily.parquet'),pd.read_parquet(ROOT/'data/derived/phase11_historical_daily_extension.parquet')],ignore_index=True); daily.date=pd.to_datetime(daily.date).dt.strftime('%Y-%m-%d'); daily=daily[daily.date<='2026-09-17'].drop_duplicates(['date','symbol']); opens={(str(r.date),r.symbol):float(r.open) for r in daily.itertuples() if pd.notna(r.open) and r.open>0}; closes={(str(r.date),r.symbol):float(r.close) for r in daily.itertuples() if pd.notna(r.close) and r.close>0}; raw_paths=daily.drop_duplicates('date').set_index('date').source_file.to_dict(); raw_cache={}; quote_audit=[]; quote_cache={}; normalized_rows={(str(r.date),str(r.symbol)):(float(r.open),str(r.series),r.source_file) for r in daily.itertuples() if pd.notna(r.open) and r.open>0}; timing['daily_load_seconds']=time.perf_counter()-t0
 resolver_stats={'cache_hits':0,'cache_misses':0,'raw_reads':0,'canonicalize_calls':0}
 mark_audit=[]
 def resolve_execution_quote(day,sym,purpose,held=False):
  cache_key=(day,sym,purpose,held)
  if cache_key in quote_cache:
   resolver_stats['cache_hits']+=1
   return quote_cache[cache_key]
  resolver_stats['cache_misses']+=1
  if (day,sym) in opens:
   op,series,_src=normalized_rows[(day,sym)]; quote_audit.append({'date':day,'symbol':sym,'purpose':purpose,'source_used':'normalized_daily','series':series,'open':op,'resolution_status':'USED','fallback_used':False,'reason':'normalized execution row available'}); quote_cache[cache_key]=(op,series); return quote_cache[cache_key]
  path=raw_paths.get(day)
  if path and path not in raw_cache:
   resolver_stats['raw_reads']+=1
   t_raw=time.perf_counter(); raw,_=read_source(Path(path)); timing['raw_read_seconds']+=time.perf_counter()-t_raw
   t_can=time.perf_counter(); raw_cache[path]=canonicalize_source(raw,source_format(Path(path)),str(path)); timing['canonicalize_seconds']+=time.perf_counter()-t_can
   resolver_stats['canonicalize_calls']+=1
  raw=raw_cache.get(path)
  if raw is not None:
   z=raw[(raw.symbol.astype(str).eq(sym))&raw.open.notna()&raw.open.gt(0)&raw.series.isin(['EQ','BE'])]
   if len(z):
    row=z.iloc[0]
    if purpose=='entry' and str(row.series)!='EQ': quote_audit.append({'date':day,'symbol':sym,'purpose':purpose,'source_used':'raw_provider','series':row.series,'open':float(row.open),'resolution_status':'ENTRY_SKIPPED_NON_EQ','fallback_used':True,'reason':'new entries are EQ-only'}); quote_cache[cache_key]=(None,None); return quote_cache[cache_key]
    quote_audit.append({'date':day,'symbol':sym,'purpose':purpose,'source_used':'raw_provider','series':row.series,'open':float(row.open),'resolution_status':'USED','fallback_used':True,'reason':'normalized row absent; raw provider row available'}); quote_cache[cache_key]=(float(row.open),str(row.series)); return quote_cache[cache_key]
  quote_audit.append({'date':day,'symbol':sym,'purpose':purpose,'source_used':'none','series':'','open':None,'resolution_status':'MISSING_AND_RETAINED' if held else 'ENTRY_SKIPPED_NO_EQ','fallback_used':False,'reason':'normalized and raw-provider rows unavailable'}); quote_cache[cache_key]=(None,None); return quote_cache[cache_key]
 def resolve_end_of_day_mark(day,sym,previous):
  """Phase12C marking contract: normalized close, raw close fallback, then carry."""
  cp=closes.get((day,sym))
  if cp is not None:
   mark_audit.append({'date':day,'symbol':sym,'source_used':'normalized_daily','series':'','close':cp,'status':'USED'})
   return cp
  path=raw_paths.get(day)
  if path and path not in raw_cache:
   resolver_stats['raw_reads']+=1
   t_raw=time.perf_counter(); raw,_=read_source(Path(path)); timing['raw_read_seconds']+=time.perf_counter()-t_raw
   t_can=time.perf_counter(); raw_cache[path]=canonicalize_source(raw,source_format(Path(path)),str(path)); timing['canonicalize_seconds']+=time.perf_counter()-t_can
   resolver_stats['canonicalize_calls']+=1
  raw=raw_cache.get(path)
  if raw is not None:
   z=raw[(raw.symbol.astype(str).eq(sym))&raw.close.notna()&raw.close.gt(0)&raw.series.isin(['EQ','BE'])]
   if len(z):
    row=z.iloc[0]; cp=float(row.close)
    mark_audit.append({'date':day,'symbol':sym,'source_used':'raw_provider','series':str(row.series),'close':cp,'status':'USED'})
    return cp
  mark_audit.append({'date':day,'symbol':sym,'source_used':'previous_mark','series':'','close':previous,'status':'CARRIED'})
  return previous
 broker=PaperBroker(slippage=SlippageConfig(market_bps=5),cost_model=BasisPointsTransactionCosts(20)); om=OrderManager(broker,order_id_factory=iter(range(1000000)).__next__); account=Portfolio(500000); risk=RiskManager(RiskLimits(9,100,100)); actual=[]; riskrows=[]; snapshots=[]
 # Generate orders from target state + engine state. Reference trades are intentionally not loaded.
 for rr in rb.sort_values('execution_date').itertuples(index=False):
  if os.environ.get('MAX_REBALANCE') and int(str(rr.rebalance_id).split('-')[-1]) > int(os.environ['MAX_REBALANCE']): break
  target=[s for s in str(rr.selected_stocks).split('|') if s and s!='nan']; day=str(rr.execution_date); held={k.split(':')[-1]:v.quantity for k,v in account.positions.items() if v.quantity}
  # Phase12C freezes pretrade equity from the beginning-of-rebalance
  # holdings at supported execution opens; scheduled sells then release cash
  # but do not change this sizing basis.
  valid_marks={}
  for s in account.positions:
   if not account.positions[s].quantity:
    continue
   quote=resolve_execution_quote(day,s.split(':')[-1],'valuation',held=True)
   if quote[0] is not None:
    valid_marks[s]=quote[0]
  pretrade_equity = account.cash + sum(account.positions[s].quantity * valid_marks.get(s, account.positions[s].last_price or account.positions[s].average_price) for s in account.positions if account.positions[s].quantity)
  # deterministic exits then entries; quantities derive from actual portfolio/cash and target weights.
  for sym in sorted(set(held)-set(target)):
   op,series=resolve_execution_quote(day,sym,'exit',held=True)
   if not op: continue
   req=OrderRequest(Instrument('NSE',sym),Side.SELL,OrderType.MARKET,max(1,int(held[sym])),pd.Timestamp(day).to_pydatetime(),eligible_after=pd.Timestamp(day).to_pydatetime().replace(hour=9,minute=0),reference_price=op,strategy_id='SECTOR_MOMENTUM',strategy_version='V2',intent=TradeIntent.SWING)
   dec=risk.evaluate(req,account); riskrows.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':'SELL','requested_quantity':req.quantity,'approved_quantity':dec.approved_quantity,'approved':dec.approved,'reason':dec.reason,'engine_open_positions_before':len(account.open_positions),'positive_quantity_positions_before':sum(1 for p in account.positions.values() if p.quantity>0),'zero_quantity_position_objects':sum(1 for p in account.positions.values() if p.quantity==0),'pending_orders_before':0,'is_existing_positive_position':True,'positions_scheduled_for_exit':1,'successful_exits_already_processed':0,'buys_filled_same_rebalance':0,'free_slots_before':max(0,9-len(account.open_positions))});
   if dec.approved:
    order=om.submit(req); fills=om.process_candle(Candle(req.instrument,'1D',req.timestamp.replace(hour=10),op,op,op,op));
    for f in fills: account.process_fill(f); actual.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':'SELL','quantity':f.quantity,'price':f.price,'fee':f.fees,'source':'ENGINE_ADAPTER'})
  # Phase12C valuation contract: after scheduled sells, value each held
  # quantity at the supported execution open for this session.  This is a
  # V2 orchestration calculation and deliberately does not mutate Portfolio
  # marks.
  free_target=max(len(target),1); target_value=pretrade_equity/free_target
  # Phase13F-B: retained positions are resized only outside the frozen 2pp
  # band.  These orders remain existing-instrument orders for RiskManager.
  for sym in sorted(target):
   if os.environ.get('ENABLE_RESIZE', '1') != '1': break
   key=f'NSE:{sym}'
   if key not in account.positions or account.positions[key].quantity <= 0: continue
   op,series=resolve_execution_quote(day,sym,'retained_resize',held=True)
   if not op: continue
   qty0=int(account.positions[key].quantity); deviation=abs((qty0*op/pretrade_equity if pretrade_equity else 0)-1/free_target)
   if deviation < 0.02: continue
   desired=max(0,int(target_value/(op*(1+5/10000)*(1+20/10000)))); delta=desired-qty0
   if delta == 0: continue
   side=Side.BUY if delta>0 else Side.SELL; q=abs(delta)
   if side is Side.BUY: q=min(q,max(0,int(account.cash/(op*(1+5/10000)*(1+20/10000)))))
   if q<=0: continue
   req=OrderRequest(Instrument('NSE',sym),side,OrderType.MARKET,q,pd.Timestamp(day).to_pydatetime(),eligible_after=pd.Timestamp(day).to_pydatetime().replace(hour=9,minute=0),reference_price=op,strategy_id='SECTOR_MOMENTUM',strategy_version='V2',intent=TradeIntent.SWING)
   dec=risk.evaluate(req,account); riskrows.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':side.value,'requested_quantity':q,'approved_quantity':dec.approved_quantity,'approved':dec.approved,'reason':dec.reason,'engine_open_positions_before':len(account.open_positions),'positive_quantity_positions_before':sum(1 for p in account.positions.values() if p.quantity>0),'zero_quantity_position_objects':sum(1 for p in account.positions.values() if p.quantity==0),'pending_orders_before':0,'is_existing_positive_position':True,'positions_scheduled_for_exit':0,'successful_exits_already_processed':0,'buys_filled_same_rebalance':0,'free_slots_before':max(0,9-len(account.open_positions))})
   if dec.approved:
    om.submit(req); fills=om.process_candle(Candle(req.instrument,'1D',pd.Timestamp(day).to_pydatetime().replace(hour=10),op,op,op,op))
    for f in fills: account.process_fill(f); actual.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':side.value,'quantity':f.quantity,'price':f.price,'fee':f.fees,'source':'ENGINE_ADAPTER'})
  for sym in target:
   if f'NSE:{sym}' in account.positions and account.positions[f'NSE:{sym}'].quantity: continue
   op,series=resolve_execution_quote(day,sym,'entry',held=False)
   if not op: continue
   desired=max(0,int(target_value/(op*(1+5/10000)*(1+20/10000)))); affordable=max(0,int(account.cash/(op*(1+5/10000)*(1+20/10000)))); q=min(desired,affordable)
   if q<=0: continue
   req=OrderRequest(Instrument('NSE',sym),Side.BUY,OrderType.MARKET,q,pd.Timestamp(day).to_pydatetime(),eligible_after=pd.Timestamp(day).to_pydatetime().replace(hour=9,minute=0),reference_price=op,strategy_id='SECTOR_MOMENTUM',strategy_version='V2',intent=TradeIntent.SWING)
   dec=risk.evaluate(req,account); riskrows.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':'BUY','requested_quantity':q,'approved_quantity':dec.approved_quantity,'approved':dec.approved,'reason':dec.reason,'engine_open_positions_before':len(account.open_positions),'positive_quantity_positions_before':sum(1 for p in account.positions.values() if p.quantity>0),'zero_quantity_position_objects':sum(1 for p in account.positions.values() if p.quantity==0),'pending_orders_before':0,'is_existing_positive_position':bool(account.positions.get(f'NSE:{sym}') and account.positions[f'NSE:{sym}'].quantity>0),'positions_scheduled_for_exit':0,'successful_exits_already_processed':0,'buys_filled_same_rebalance':0,'free_slots_before':max(0,9-len(account.open_positions))});
   if dec.approved:
    order=om.submit(req); fills=om.process_candle(Candle(req.instrument,'1D',pd.Timestamp(day).to_pydatetime().replace(hour=10),op,op,op,op));
    for f in fills: account.process_fill(f); actual.append({'rebalance_id':rr.rebalance_id,'symbol':sym,'side':'BUY','quantity':f.quantity,'price':f.price,'fee':f.fees,'source':'ENGINE_ADAPTER'})
  for sym in list(account.positions):
   s=sym.split(':')[-1]
   previous=account.positions[sym].last_price or account.positions[sym].average_price
   cp=resolve_end_of_day_mark(day,s,previous)
   if cp: account.mark(sym,cp)
  if progress_path and (len(snapshots) == 0 or int(str(rr.rebalance_id).split('-')[-1]) % 20 == 0):
   line=f"rebalance_id={rr.rebalance_id} execution_date={day} elapsed_seconds={time.perf_counter()-started:.3f} orders={len(actual)} risk_decisions={len(riskrows)} quote_resolutions={len(quote_audit)} raw_source_files_loaded={len(raw_cache)} quote_cache_size={len(quote_cache)} cache_hits={resolver_stats['cache_hits']} cache_misses={resolver_stats['cache_misses']} raw_reads={resolver_stats['raw_reads']} canonicalize_calls={resolver_stats['canonicalize_calls']} daily_load_seconds={timing['daily_load_seconds']:.3f} raw_read_seconds={timing['raw_read_seconds']:.3f} canonicalize_seconds={timing['canonicalize_seconds']:.3f}"
   print(line,flush=True); open(progress_path,'a').write(line+'\n')
  if rr.rebalance_id in sample or os.environ.get('FULL_SNAPSHOTS') == '1':
   if os.environ.get('FULL_SNAPSHOTS') == '1':
    for k,p in account.positions.items():
     if p.quantity: snapshots.append({'rebalance_id':rr.rebalance_id,'signal_date':rr.signal_date,'execution_date':day,'symbol':k.split(':')[-1],'quantity':int(p.quantity),'average_price':p.average_price,'last_mark':p.last_price,'engine_cash':account.cash,'engine_equity':account.equity,'positive_positions':len(account.open_positions)})
   else: snapshots.append({'rebalance_id':rr.rebalance_id,'engine_cash':account.cash,'engine_equity':account.equity})
 # Compare only now to accepted reference trades.
 ref=pd.read_csv(V2/'development/v2_trades.csv'); ref=ref[ref.rebalance_id.isin(sample)]; a=pd.DataFrame(actual,columns=['rebalance_id','symbol','side','quantity','price','fee']); rows=[]
 for key,g in ref.groupby(['rebalance_id','symbol']):
  r=g.iloc[0]; z=a[(a.rebalance_id==key[0])&(a.symbol==key[1])];
  if len(z): q=z.iloc[0]; rows.append({'rebalance_id':key[0],'symbol':key[1],'expected_side':r.side,'actual_side':q.side,'expected_quantity':int(r.quantity),'actual_quantity':int(q.quantity),'result':'PASS' if r.side==q.side and int(r.quantity)==int(q.quantity) else 'FAIL'})
  else: rows.append({'rebalance_id':key[0],'symbol':key[1],'expected_side':r.side,'actual_side':'MISSING','expected_quantity':int(r.quantity),'actual_quantity':0,'result':'FAIL'})
 for _,q in a[a.rebalance_id.isin(sample)].iterrows():
  if not ((ref.rebalance_id==q.rebalance_id)&(ref.symbol==q.symbol)).any(): rows.append({'rebalance_id':q.rebalance_id,'symbol':q.symbol,'expected_side':'NONE','actual_side':q.side,'expected_quantity':0,'actual_quantity':int(q.quantity),'result':'FAIL'})
 pd.DataFrame(rows).to_csv(OUT/'historical_target_to_order_parity.csv',index=False); pd.DataFrame(riskrows).to_csv(OUT/'historical_risk_parity.csv',index=False); pd.DataFrame(actual).to_csv(OUT/'historical_engine_orders.csv',index=False); pd.DataFrame(snapshots).to_csv(OUT/'historical_engine_snapshots.csv',index=False); pd.DataFrame(quote_audit).to_csv(OUT/'execution_quote_resolution_audit.csv',index=False); pd.DataFrame(mark_audit).to_csv(OUT/'end_of_day_mark_audit.csv',index=False)
 print('true engine orders',len(a),'parity',sum(x['result']=='PASS' for x in rows),'/',len(rows),'risk',len(riskrows),'approved',sum(bool(x['approved']) for x in riskrows))
if __name__=='__main__': main()
