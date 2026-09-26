import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; P=ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f/b3_state_forensics'

def test_full_history_and_first_divergence():
    s=json.loads((P/'phase13f_b3_summary.json').read_text())
    assert s['rebalances_compared']==350
    assert s['last_exact_rebalance']=='SMV2-0029'
    assert s['first_true_divergent_rebalance']=='SMV2-0030'
    assert s['first_divergent_symbol']=='HATHWAY'

def test_target_n_and_dependency_coverage():
    s=json.loads((P/'phase13f_b3_summary.json').read_text()); assert s['target_n_difference_count']==0
    x=pd.read_csv(P/'remaining_60_dependency_map.csv'); assert len(x)==60 and x.direct_cause.notna().all()

def test_b2_hashes_and_boundary():
    s=json.loads((P/'phase13f_b3_summary.json').read_text())
    assert s['phase12b_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'
    assert s['phase12c_build']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'
    assert s['post_boundary_performance_inspected'] is False
