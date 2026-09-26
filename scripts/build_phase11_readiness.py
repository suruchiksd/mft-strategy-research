#!/usr/bin/env python3
"""Build additive Phase-11 data extensions and a pre-P&L feasibility audit."""

from __future__ import annotations

import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path

import pandas as pd
import yaml

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/"src"))
from mft_research.data.manifest import canonical_json,sha256
from mft_research.sector_strategy import (action_contract,canonical_new_daily,extend_daily,extension_actions,
  extended_sector_panel,feasibility,weekly_signal_dates)

def local(v):
 p=(PROJECT/v).resolve()
 if not p.is_relative_to(PROJECT):raise ValueError("path escaped project")
 return p
def config():return yaml.safe_load((PROJECT/"config/phase11_data_readiness.yaml").read_text())

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--verify-rebuild",action="store_true");args=parser.parse_args();c=config()
 accepted=pd.read_parquet(local(c["accepted_daily"]));mapping=pd.read_parquet(local(c["sector_mapping"]));historical=pd.read_parquet(local(c["historical_actions"]));p10=pd.read_parquet(local(c["phase10_actions"]))
 paths=[local(c["raw_bhavcopy_dir"])/f"BhavCopy_NSE_CM_0_0_0_{d.replace('-','')}_F_0000.csv" for d in c["price_extension_dates"]]
 new=canonical_new_daily(paths);combined_identity=pd.concat([accepted[["symbol","isin"]],new[["symbol","isin"]]],ignore_index=True)
 raw_ca=local(c["raw_ca"]);endpoint="https://www.nseindia.com/api/corporates-corporateActions"
 p11=extension_actions(raw_ca,endpoint,c["retrieval_timestamp_utc"],sha256(raw_ca),combined_identity)
 actions=action_contract(historical,[p10,p11]);phase5=yaml.safe_load(local(c["phase5_config"]).read_text());phase7=yaml.safe_load(local(c["phase7_config"]).read_text())
 rebuilt,daily_extension=extend_daily(accepted,new,phase5,actions,mapping)
 sector_panel=extended_sector_panel(rebuilt,mapping,actions,phase5,phase7)
 accepted_panel=pd.read_parquet(local(c["accepted_sector_panel"]));calendar=sorted(rebuilt.date.unique())
 signals=weekly_signal_dates(calendar,c["development_end"]);selected,summary=feasibility(signals,accepted_panel,accepted,mapping)
 source_manifest={"retrieval_timestamp_utc":c["retrieval_timestamp_utc"],"price_files":[{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p),"rows":len(pd.read_csv(p))} for p in paths],
   "corporate_action_request":{"endpoint":endpoint,"parameters":{"index":"equities","from_date":"12-09-2026","to_date":"17-09-2026"},"path":c["raw_ca"],"sha256":sha256(raw_ca),"rows":len(pd.read_json(raw_ca))},
   "holiday":{"date":"2026-09-14","reason":"Ganesh Chaturthi","source":"https://www.nseindia.com/resources/exchange-communication-holidays"}}
 audit=pd.DataFrame([{"item":"accepted_historical_daily","latest_date":accepted.date.max(),"status":"UNCHANGED"},
   {"item":"local_bhavcopy_archive","latest_date":"2026-09-17","status":"COMPLETE_THROUGH_TARGET_WITH_2026_09_14_HOLIDAY"},
   {"item":"accepted_ca_extension","latest_date":"2026-09-11","status":"UNCHANGED"},
   {"item":"phase11_ca_extension","latest_date":p11.ex_date.max(),"status":"ADDITIVE_CERTIFICATION_THROUGH_TARGET"},
   {"item":"sector_mapping","latest_date":"STATIC_CURRENT_NO_EFFECTIVE_DATES","status":"CONDITIONAL_LIMITATION"}])
 feasibility_summary=pd.DataFrame([{"development_signal_dates":len(summary),"usable_sector_min":summary.usable_sectors.min(),"usable_sector_median":summary.usable_sectors.median(),
   "usable_sector_max":summary.usable_sectors.max(),"selected_sector_dates_below_3_stocks":summary.selected_sectors_below_3_stocks.sum(),
   "expected_positions_min":summary.expected_positions.min(),"expected_positions_median":summary.expected_positions.median(),"expected_positions_max":summary.expected_positions.max(),
   "maximum_sector_weight":summary.maximum_sector_weight.max(),"calendar_rule":"FINAL_NSE_SESSION_OF_ISO_WEEK_SIGNAL_NEXT_SESSION_OPEN"}])
 outputs={"data_readiness_audit.csv":audit,"feasibility_by_rebalance.csv":summary,"feasibility_selected_targets.csv":selected,"feasibility_summary.csv":feasibility_summary}
 report_dir=local(c["report_dir"]);report_dir.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix=".phase11-readiness-",dir=report_dir) as tmp:
  stage=Path(tmp)
  for n,f in outputs.items():f.to_csv(stage/n,index=False,date_format="%Y-%m-%d",float_format="%.12g")
  daily_extension.to_parquet(stage/"phase11_historical_daily_extension.parquet",index=False,compression="zstd");p11.to_parquet(stage/"phase11_corporate_action_extension.parquet",index=False,compression="zstd");sector_panel.to_parquet(stage/"phase11_sector_signal_panel.parquet",index=False,compression="zstd")
  (stage/"phase11_source_manifest.json").write_text(canonical_json(source_manifest))
  names=list(outputs)+["phase11_historical_daily_extension.parquet","phase11_corporate_action_extension.parquet","phase11_sector_signal_panel.parquet","phase11_source_manifest.json"]
  hashes={n:sha256(stage/n) for n in names};key={"config":c,"output_sha256":hashes,"source_manifest":source_manifest};build=hashlib.sha256(canonical_json(key).encode()).hexdigest()
  manifest={**key,"build_id":build,"holdout_strategy_pnl_inspected":False,"latest_certified_date":"2026-09-17"}
  manifest_path=report_dir/"phase11_readiness_manifest.json";dest={n:report_dir/n for n in outputs};dest.update({"phase11_historical_daily_extension.parquet":local(c["daily_extension"]),"phase11_corporate_action_extension.parquet":local(c["ca_extension"]),"phase11_sector_signal_panel.parquet":local(c["extended_sector_panel"]),"phase11_source_manifest.json":report_dir/"phase11_source_manifest.json"})
  if args.verify_rebuild:
   prior=json.loads(manifest_path.read_text())
   if prior!=manifest:raise AssertionError("readiness rebuild differs")
   for n,d in hashes.items():
    if sha256(dest[n])!=d:raise AssertionError(f"published readiness differs: {n}")
   print(f"PASS readiness rebuild {len(names)} outputs {build}");return
  for n,p in dest.items():p.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/n,p)
  manifest_path.write_text(canonical_json(manifest));print(f"Built Phase-11 readiness {build}");print(feasibility_summary.to_string(index=False))
if __name__=="__main__":main()
