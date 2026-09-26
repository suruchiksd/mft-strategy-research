#!/usr/bin/env python3
"""Freeze Phase-11 V1 rules before holdout P&L inspection."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import yaml
PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/"src"))
from mft_research.data.manifest import canonical_json,sha256

def main():
 p=argparse.ArgumentParser();p.add_argument("--verify",action="store_true");a=p.parse_args();d=PROJECT/"reports/sector_strategy/preregistration";cfg=d/"phase11_sector_strategy_config.yaml";report=d/"phase11_sector_strategy_preregistration.md";readiness=PROJECT/"reports/sector_strategy/readiness/phase11_readiness_manifest.json"
 c=yaml.safe_load(cfg.read_text());r=json.loads(readiness.read_text())
 if c["holdout_strategy_pnl_inspected"] is not False or r["holdout_strategy_pnl_inspected"] is not False:raise RuntimeError("Holdout ordering gate failed")
 prereg_hashes={"phase11_sector_strategy_config.yaml":sha256(cfg),"phase11_sector_strategy_preregistration.md":sha256(report)}
 frozen={"status":"FROZEN_BEFORE_HOLDOUT_STRATEGY_PNL","frozen_at_utc":c["frozen_at_utc"],"holdout_strategy_pnl_inspected":False,
   "readiness_build_id":r["build_id"],"latest_certified_date":r["latest_certified_date"],"frozen_file_sha256":prereg_hashes,
   "phase7_build_id":json.loads((PROJECT/"reports/sector_momentum/research/phase7_build_manifest.json").read_text())["build_id"],
   "phase10_amendment_hash":json.loads((PROJECT/"reports/reversal/amendment/phase10_amendment_manifest.json").read_text())["amendment_hash"]}
 frozen["strategy_preregistration_hash"]=hashlib.sha256(canonical_json(frozen).encode()).hexdigest();path=d/"phase11_strategy_manifest.json"
 if a.verify:
  if json.loads(path.read_text())!=frozen:raise AssertionError("Phase-11 preregistration differs")
  print(f"PASS Phase-11 preregistration {frozen['strategy_preregistration_hash']}");return
 path.write_text(canonical_json(frozen));print(f"Frozen Phase-11 V1 {frozen['strategy_preregistration_hash']}")
if __name__=="__main__":main()
