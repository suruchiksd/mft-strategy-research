from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, '/home/suruchi-pandey/Projects/paper-trading-engine/src')
from paper_trading.models import Instrument, Order, OrderType, OrderStatus, Side, Candle
from paper_trading.execution.paper import PaperBroker, SlippageConfig
from paper_trading.execution.costs import BasisPointsTransactionCosts
from paper_trading.portfolio.accounting import Portfolio
ROOT=Path(__file__).resolve().parents[1]; V2=ROOT/'reports/sector_strategy/v2'; OUT=V2/'paper_handoff'
def run():
 t=pd.read_csv(V2/'development/v2_trades.csv'); rb=pd.read_csv(V2/'development/v2_rebalances.csv'); eq=pd.read_csv(V2/'development/v2_equity_curve.csv'); pos=pd.read_csv(V2/'development/v2_positions.csv'); sample=pd.read_json(OUT/'parity_sample_definition.json'); ids=set(sample.rebalance_id)
 broker=PaperBroker(slippage=SlippageConfig(market_bps=5),cost_model=BasisPointsTransactionCosts(20)); account=Portfolio(500000.0); fills=[]; acct=[]
 t['side_order']=t.side.map({'SELL':0,'BUY':1}); t=t.sort_values(['date','rebalance_id','side_order','symbol']); groups={k:g for k,g in t.groupby('rebalance_id',sort=False)}
 for rr in rb.sort_values('execution_date').itertuples(index=False):
  for r in groups.get(rr.rebalance_id,pd.DataFrame()).itertuples(index=False):
   inst=Instrument('NSE',r.symbol); ts=pd.Timestamp(r.date).to_pydatetime().replace(hour=10,minute=0); order=Order(inst,Side.BUY if r.side=='BUY' else Side.SELL,OrderType.MARKET,int(r.quantity),ts,eligible_after=ts.replace(hour=9,minute=0),strategy_id='SECTOR_MOMENTUM',strategy_version='V2',metadata={'rebalance_id':r.rebalance_id}); broker.submit_order(order); order.status=OrderStatus.OPEN; update=broker.process_candle(Candle(inst,'1D',ts,float(r.reference_open),float(r.reference_open),float(r.reference_open),float(r.reference_open)))
   for f in update.fills:
    account.process_fill(f); fills.append({'rebalance_id':r.rebalance_id,'symbol':r.symbol,'side':r.side,'expected_quantity':int(r.quantity),'actual_quantity':f.quantity,'expected_fill_price':float(r.fill_price),'actual_fill_price':f.price,'expected_cost':float(r.transaction_cost),'actual_cost':f.fees,'price_diff':f.price-float(r.fill_price),'cost_diff':f.fees-float(r.transaction_cost),'result':'PASS' if f.quantity==int(r.quantity) and abs(f.price-float(r.fill_price))<=.01 and abs(f.fees-float(r.transaction_cost))<=.01 else 'FAIL','expected_source':'Phase12C trades','actual_source':'PaperBroker/Portfolio'})
  if rr.rebalance_id in ids:
   e=eq[eq.date.eq(str(rr.execution_date))].iloc[0]; marks=pos[pos.date.eq(str(rr.execution_date))]
   for m in marks.itertuples(index=False): account.mark(f'NSE:{m.symbol}',float(m.close))
   acct.append({'rebalance_id':rr.rebalance_id,'cash_expected':float(e.cash),'cash_actual':account.cash,'equity_expected':float(e.equity),'equity_actual':account.equity,'cash_diff':account.cash-float(e.cash),'equity_diff':account.equity-float(e.equity),'tolerance':.01,'result':'PASS' if abs(account.cash-float(e.cash))<=.01 and abs(account.equity-float(e.equity))<=.01 else 'FAIL','expected_source':'Phase12C equity','actual_source':'PaperEngine Portfolio'})
 pd.DataFrame(fills).to_csv(OUT/'historical_fill_parity.csv',index=False); pd.DataFrame(acct).to_csv(OUT/'historical_accounting_parity.csv',index=False); pd.DataFrame(fills).to_csv(OUT/'historical_order_parity.csv',index=False); print('engine replay fills',len(fills),'passes',sum(x['result']=='PASS' for x in fills),'accounting',len(acct),'passes',sum(x['result']=='PASS' for x in acct))
if __name__=='__main__': run()
