import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256

PROJECT=Path(__file__).resolve().parents[1]


def artifact(phase,path,name):
    special={(5,"historical_nse_daily.parquet"):PROJECT/"data/derived/historical_nse_daily.parquet",
      (5,"phase5_point_in_time_csrs.md"):PROJECT/"reports/phase5_point_in_time_csrs.md",
      (6,"sector_research_mapping.parquet"):PROJECT/"data/derived/sector_research_mapping.parquet",
      (6,"phase6_sector_foundation.md"):PROJECT/"reports/phase6_sector_foundation.md",
      (7,"sector_momentum_factor_panel.parquet"):PROJECT/"data/derived/sector_momentum_factor_panel.parquet",
      (7,"phase7_sector_relative_momentum.md"):PROJECT/"reports/phase7_sector_relative_momentum.md",
      (8,"volume_momentum_foundation.parquet"):PROJECT/"data/derived/volume_momentum_foundation.parquet",
      (8,"phase8_volume_momentum_foundation.md"):PROJECT/"reports/phase8_volume_momentum_foundation.md"}
    return special.get((phase,name),path.parent/name)


def test_phase5_through_phase8_artifacts_and_required_phase8_build_unchanged():
    paths={5:PROJECT/"reports/csrs/point_in_time/phase5_build_manifest.json",6:PROJECT/"reports/sector_momentum/foundation/phase6_build_manifest.json",
           7:PROJECT/"reports/sector_momentum/research/phase7_build_manifest.json",8:PROJECT/"reports/volume_momentum/foundation/phase8_build_manifest.json"}
    for phase,path in paths.items():
      manifest=json.loads(path.read_text())
      if phase==8: assert manifest["build_id"]=="422d5459c295f5d6fce9f3648487528c1b4f71e56956ef19c7e7809d3cb05e5e"
      for name,digest in manifest["output_sha256"].items(): assert sha256(artifact(phase,path,name))==digest


def test_registry_formulas_exactly_match_accepted_phase8_manifest():
    manifest=json.loads((PROJECT/"reports/volume_momentum/foundation/phase8_build_manifest.json").read_text())
    accepted=pd.DataFrame(manifest["candidate_registry"]).sort_values("candidate_id").reset_index(drop=True)
    current=pd.read_csv(PROJECT/"reports/volume_momentum/foundation/candidate_factor_registry.csv").sort_values("candidate_id").reset_index(drop=True)
    assert current.candidate_id.tolist()==["VM01","VM02","VM03","VM04","VM05","VM06","VM07"]
    assert current.formula.tolist()==accepted.formula.tolist()


def test_phase9_grid_families_universes_offsets_and_no_trading_outputs():
    root=PROJECT/"reports/volume_momentum/research"; expected={(c,h) for c in ["VM01","VM02","VM03","VM04","VM05","VM06","VM07"] for h in [1,2,3,5,10,20]}
    summary=pd.read_csv(root/"candidate_rank_ic_summary.csv"); assert set(zip(summary.candidate_id,summary.future_horizon))==expected
    assert len(pd.read_csv(root/"multiple_testing.csv"))==42
    assert len(pd.read_csv(root/"interaction_incremental_uncertainty.csv"))==18
    sensitivity=pd.read_csv(root/"universe_sensitivity.csv"); assert set(sensitivity.universe)=={"BASIC_LIQUID","MODERATE_LIQUID"}
    non=pd.read_csv(root/"nonoverlap_results.csv")
    assert all(set(group.offset)==set(range(h)) for (_,h),group in non.groupby(["candidate_id","future_horizon"]))
    assert non.spacing_valid.all()
    for path in [PROJECT/"data/derived/volume_momentum_factor_panel.parquet",*root.glob("*.csv")]:
      columns=pd.read_parquet(path).columns if path.suffix==".parquet" else pd.read_csv(path,nrows=0).columns
      assert not any(token in column.lower() for column in columns for token in ("combined","portfolio","pnl","trading_return","sector_momentum","csrs"))


def test_phase9_outputs_acceptance_and_deterministic_proof():
    root=PROJECT/"reports/volume_momentum/research"; manifest=json.loads((root/"phase9_build_manifest.json").read_text())
    proof=json.loads((root/"phase9_rebuild_verification.json").read_text()); acceptance=json.loads((root/"phase9_acceptance.json").read_text())
    assert proof["byte_identical"] and proof["build_id"]==manifest["build_id"] and all(x["passed"] for x in acceptance)
    for name,digest in manifest["output_sha256"].items():
      path=(PROJECT/"data/derived/volume_momentum_factor_panel.parquet" if name.endswith(".parquet") else
            PROJECT/"reports/phase9_volume_momentum_research.md" if name.endswith(".md") else root/name)
      assert sha256(path)==digest
