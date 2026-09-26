import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; P=ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f/b4_execution_data_repair'

def test_b3_unchanged_and_b4_hashes():
    s=json.loads((P/'b4_integrity_manifest.json').read_text()); assert s['phase12b_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'; assert s['phase12c_build']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'

def test_hathway_gate_and_replacement():
    x=pd.read_csv(P/'hathway_regression_gate.csv'); assert set(x.status)=={'PASS'}; assert x.loc[x.symbol.eq('HATHWAY'),'ending_quantity_engine'].iloc[0]==0; assert x.loc[x.symbol.eq('TATACOMM'),'engine_entry_quantity'].iloc[0]==95

def test_quote_contract_and_next_divergence():
    q=pd.read_csv(P/'execution_quote_resolution_audit.csv'); h=q[(q.symbol=='HATHWAY')&(q.date=='2020-07-27')]; assert len(h)>0 and (h.source_used=='raw_provider').any() and (h.series=='BE').any()
    d=pd.read_csv(P/'first_remaining_divergence.csv'); assert d.symbol.iloc[0]=='EASEMYTRIP'; assert d.rebalance_id.iloc[0]=='SMV2-0094'

def test_no_post_boundary():
    assert json.loads((P/'b4_integrity_manifest.json').read_text())['post_boundary_performance_inspected'] is False
