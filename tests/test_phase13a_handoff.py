import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'reports/sector_strategy/v2/paper_handoff'
def test_integrity_and_contract():
    m=json.loads((OUT/'phase13a_handoff_manifest.json').read_text()); assert m['strategy_preregistration_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'; assert m['strategy_build_reference']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'; assert m['prospective_performance_inspected'] is False
def test_signal_schema_and_parity():
    s=pd.read_csv(OUT/'signals_v1_sample.csv'); assert s.strategy_version.eq('V2').all(); assert s.execution_earliest_date.gt(s.signal_date).all(); assert s[s.selection_status.isin(['ENTER','KEEP'])].groupby('rebalance_id').symbol.nunique().max() <= 9
    p=pd.read_csv(OUT/'historical_signal_parity.csv'); assert len(p)==15 and p.result.eq('PASS').all()
def test_order_and_accounting_parity():
    o=pd.read_csv(OUT/'historical_order_parity.csv'); a=pd.read_csv(OUT/'historical_accounting_parity.csv'); assert o.result.eq('PASS').all(); assert a.result.eq('PASS').all(); assert (o.expected_quantity==o.actual_quantity).all(); assert (a.equity_expected-a.equity_actual).abs().max()<=.01
def test_no_prospective_results():
    assert not (OUT/'prospective_returns.csv').exists(); assert 'do not calculate retrospective returns' in (OUT/'prospective_signal_generator_runbook.md').read_text().lower()
