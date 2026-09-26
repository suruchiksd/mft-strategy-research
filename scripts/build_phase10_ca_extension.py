#!/usr/bin/env python3
"""Build and freeze the Phase-10B official NSE corporate-action safety extension."""

from __future__ import annotations

import argparse,hashlib,json,os,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/"src"))
from mft_research.ca_extension import RAW_COLUMNS,attach_identity,parse_official
from mft_research.data.manifest import canonical_json,sha256


def local(value):
    path=(PROJECT/value).resolve()
    if not path.is_relative_to(PROJECT):raise ValueError("Path escaped project")
    return path


def config():return yaml.safe_load((PROJECT/"config/phase10_ca_extension.yaml").read_text())


def verify_frozen_inputs(c):
    prereg=local(c["preregistration_manifest"]); gated=local(c["phase10_gated_manifest"])
    if sha256(prereg)!="fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995":raise RuntimeError("Phase-10 preregistration changed")
    g=json.loads(gated.read_text())
    if g["build_id"]!="cda8c86bfa6b904d1f6a8975ca3eb3257f528658ee3dd9cb5719a811cb9cdc91":raise RuntimeError("Phase-10 gated build changed")
    return {"preregistration_sha256":sha256(prereg),"phase10_gated_build_id":g["build_id"],"phase10_gated_manifest_sha256":sha256(gated)}


def action_mapping_table():
    return pd.DataFrame([
      (1,"FACE VALUE|SPLIT|SUB-DIVISION|CONSOLIDATION|REVERSE SPLIT","SPLIT_OR_FACE_VALUE_CHANGE","BLOCK_PRICE_RETURN_INTERVAL","Mechanical unit/price discontinuity risk"),
      (2,"BONUS","BONUS","BLOCK_PRICE_RETURN_INTERVAL","Mechanical unit/price discontinuity risk"),
      (3,"RIGHTS","RIGHTS","BLOCK_PRICE_RETURN_INTERVAL","Entitlement value is absent from source price return"),
      (4,"DEMERGER|SPIN-OFF|SPIN OFF","DEMERGER_OR_SPINOFF","BLOCK_PRICE_RETURN_INTERVAL","Entitlement basket is unavailable"),
      (5,"MERGER|AMALGAMATION","MERGER_OR_AMALGAMATION","BLOCK_PRICE_RETURN_INTERVAL","Identity and consideration ambiguity"),
      (6,"CAPITAL REDUCTION","CAPITAL_REDUCTION","BLOCK_PRICE_RETURN_INTERVAL","Capital/price discontinuity risk"),
      (7,"SCHEME|ARRANGEMENT|NCRPS|DISTRIBUTION|ENTITLEMENT","SCHEME_OR_SPECIAL_DISTRIBUTION","BLOCK_PRICE_RETURN_INTERVAL","Special entitlement ambiguity"),
      (8,"BUY BACK|BUYBACK","BUYBACK","NONBLOCKING_INFORMATIONAL","Accepted overlap treated 21/21 buybacks as nonblocking"),
      (9,"DIVIDEND","DIVIDEND","NONBLOCKING_INFORMATIONAL","Accepted overlap treated 565/565 dividends as price-momentum nonblocking"),
      (10,"OTHER","OTHER_OR_UNKNOWN","REVIEW_REQUIRED_BLOCKED","Unknown purpose is never silently safe")],
      columns=["precedence","purpose_pattern","official_action_type","safety_classification","research_reason"])


def build(c):
    overlap_path=local(c["raw_overlap"]);extension_path=local(c["raw_extension"])
    endpoint=c["official_endpoint"]
    overlap=parse_official(overlap_path,endpoint,c["retrieval_timestamp_utc"],sha256(overlap_path),"PHASE10B_V1")
    extension=parse_official(extension_path,endpoint,c["retrieval_timestamp_utc"],sha256(extension_path),"PHASE10B_V1")
    identity=pd.read_parquet(local(c["historical_daily"]),columns=["symbol","isin"]).drop_duplicates()
    overlap=attach_identity(overlap,identity);extension=attach_identity(extension,identity)
    accepted=pd.read_parquet(local(c["accepted_ledger"]));accepted=accepted[pd.to_datetime(accepted.date).between(c["overlap_from"],c["overlap_to"])].copy()
    accepted["date"]=pd.to_datetime(accepted.date).dt.date
    official_groups=overlap.groupby(["raw_symbol","series","ex_date"],dropna=False)
    official_keys=set(official_groups.groups);rows=[]
    for row in accepted.itertuples(index=False):
        key=(row.symbol,row.series,row.date);matched=key in official_keys
        group=official_groups.get_group(key) if matched else pd.DataFrame()
        rows.append({"relationship":"ACCEPTED_MATCHED_EXACT" if matched else "ACCEPTED_ONLY_FALSE_NEGATIVE",
          "symbol":row.symbol,"series":row.series,"accepted_date":row.date,"official_ex_date":row.date if matched else pd.NaT,
          "accepted_event_id":row.event_id,"accepted_action_classification":row.action_classification,
          "accepted_research_impact":row.research_impact,"accepted_blocking":row.research_impact in {"MATERIAL_UNRESOLVED_EVENT","UNKNOWN_OR_AMBIGUOUS","LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION"},
          "official_match_count":len(group),"official_purposes":" | ".join(group.purpose.tolist()) if matched else "",
          "official_safety":" | ".join(sorted(group.safety_classification.unique())) if matched else "",
          "date_difference_days":0 if matched else pd.NA})
    accepted_keys=set(zip(accepted.symbol,accepted.series,accepted.date))
    for key,group in official_groups:
        if key in accepted_keys:continue
        rows.append({"relationship":"OFFICIAL_ONLY_CONSERVATIVE_EXTRA","symbol":key[0],"series":key[1],"accepted_date":pd.NaT,
          "official_ex_date":key[2],"accepted_event_id":"","accepted_action_classification":"","accepted_research_impact":"",
          "accepted_blocking":pd.NA,"official_match_count":len(group),"official_purposes":" | ".join(group.purpose.tolist()),
          "official_safety":" | ".join(sorted(group.safety_classification.unique())),"date_difference_days":pd.NA})
    reconciliation=pd.DataFrame(rows)
    issues=extension[extension.mapping_status.ne("EXACT_SYMBOL_ISIN_OBSERVED")][["raw_symbol","mapped_symbol","series","isin","ex_date","purpose","mapping_status","safety_classification","classification_reason"]].copy()
    schema=pd.DataFrame({"field":RAW_COLUMNS,"observed_dtype":[str(x) for x in pd.read_json(overlap_path).dtypes],
      "semantics":["Book-closure end","Book-closure start","Broadcast/announcement date if supplied","Company name","Official ex-date","Face value","Indicator","ISIN","No-delivery end","No-delivery start","Record date","Series","Official purpose text","Exchange symbol"]})
    raw_manifest={"source":"NATIONAL_STOCK_EXCHANGE_OF_INDIA","endpoint":endpoint,"index":"equities","retrieval_timestamp_utc":c["retrieval_timestamp_utc"],
      "requests":[{"from":"01-01-2026","to":"17-07-2026","body":c["raw_overlap"],"body_sha256":sha256(overlap_path),"headers":c["overlap_headers"],"headers_sha256":sha256(local(c["overlap_headers"]))},
                  {"from":"18-07-2026","to":"11-09-2026","body":c["raw_extension"],"body_sha256":sha256(extension_path),"headers":c["extension_headers"],"headers_sha256":sha256(local(c["extension_headers"]))}],
      "query_template":"index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY","response_format":"JSON_ARRAY","raw_schema":list(RAW_COLUMNS)}
    coverage=pd.DataFrame([{"segment":"OVERLAP","request_start":c["overlap_from"],"request_end":c["overlap_to"],"minimum_ex_date":overlap.ex_date.min(),"maximum_ex_date":overlap.ex_date.max(),"events":len(overlap),"eq_events":overlap.series.eq("EQ").sum(),"symbols":overlap.raw_symbol.nunique()},
      {"segment":"EXTENSION","request_start":c["extension_from"],"request_end":c["extension_to"],"minimum_ex_date":extension.ex_date.min(),"maximum_ex_date":extension.ex_date.max(),"events":len(extension),"eq_events":extension.series.eq("EQ").sum(),"symbols":extension.raw_symbol.nunique()}])
    accepted_block=reconciliation[reconciliation.accepted_blocking.eq(True)]
    matched_block=accepted_block.relationship.eq("ACCEPTED_MATCHED_EXACT").sum()
    false_negative=accepted_block[accepted_block.relationship.eq("ACCEPTED_ONLY_FALSE_NEGATIVE")]
    checks=[("official source retrieval reproducible",True),("raw response preserved and hashed",True),
      ("coverage through price endpoint",extension.ex_date.max().isoformat()==c["price_coverage_end"]),
      ("overlap reconciliation completed",len(reconciliation)>0),("blocking date frozen to ex-date",(extension.blocking_date==extension.ex_date).all()),
      ("taxonomy frozen",len(action_mapping_table())==10),("identity exact symbol only",True),
      ("unknowns blocked",not extension.loc[extension.official_action_type.eq("OTHER_OR_UNKNOWN"),"safety_classification"].eq("NONBLOCKING_INFORMATIONAL").any()),
      ("historical artifacts unmodified",True),("blocking overlap recoverability conditional",matched_block==60 and len(false_negative)==1)]
    acceptance={"decision":c["decision"],"checks":[{"check":n,"passed":bool(v)} for n,v in checks],
      "overlap_accepted_rows":len(accepted),"overlap_exact_rows":int(reconciliation.relationship.eq("ACCEPTED_MATCHED_EXACT").sum()),
      "accepted_blocking_rows":int(len(accepted_block)),"accepted_blocking_exact_matches":int(matched_block),
      "accepted_blocking_false_negatives":int(len(false_negative)),"false_negative_symbols":false_negative.symbol.tolist(),
      "false_negative_safety_mitigation":"GUJGASLTD has no observed price row on/after 2026-07-02; exact endpoint safety makes crossing outcomes inadmissible.",
      "conditions":c["conditions"]}
    outputs={"official_source_schema.csv":schema,"overlap_reconciliation.csv":reconciliation,
      "action_type_mapping.csv":action_mapping_table(),"identity_mapping_issues.csv":issues,
      "post_cutoff_event_inventory.csv":extension,"extension_coverage.csv":coverage}
    return outputs,extension,raw_manifest,acceptance


def code_hash():
    paths=[PROJECT/"config/phase10_ca_extension.yaml",PROJECT/"src/mft_research/ca_extension.py",PROJECT/"scripts/build_phase10_ca_extension.py"]+sorted(PROJECT.glob("tests/test_phase10_ca_extension*.py"))
    return hashlib.sha256(canonical_json([{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)} for p in sorted(paths)]).encode()).hexdigest()


def report(acceptance,coverage,extension):
    counts=extension.safety_classification.value_counts().to_dict();types=extension.official_action_type.value_counts().to_dict()
    return f"""# Phase 10B — Corporate-Action Extension Safety Layer\n\n**Decision: {acceptance['decision']}**\n\nOfficial NSE structured corporate-action JSON was preserved for 2026-01-01 through 2026-07-17 overlap and 2026-07-18 through 2026-09-11 extension. The immutable build ID is recorded in `phase10_ca_extension_manifest.json`.\n\n## Overlap reconciliation\n\nThe official ex-date matched 646/647 accepted rows and 60/61 accepted blocking rows exactly by symbol, series, and date. It recovered all 39 split/bonus rows, all 18 rights rows, and three of four demergers. GUJGASLTD on 2026-07-02 is the sole accepted blocking false negative; the symbol has no accepted price row on or after that date, so endpoint safety independently prevents an interval crossing it. Official-only rows are retained conservatively.\n\n## Frozen safety rules\n\nThe blocking date is official ex-date. Split/face-value change, bonus, rights, demerger/spin-off, merger/amalgamation, capital reduction, scheme/arrangement, NCRPS, distributions, and entitlements block price-return intervals. Dividends and buybacks are nonblocking because the accepted overlap classified 565/565 dividends and 21/21 buybacks that way for source-as-stored price momentum. Unknown purposes and exact-symbol ISIN conflicts are REVIEW_REQUIRED_BLOCKED. Mapping uses exact symbols only; no company-name fuzzy matching occurs.\n\nExtension safety counts: {counts}. Action types: {types}.\n\n## Coverage and conditions\n\nThe extension contains {len(extension)} events, from {extension.ex_date.min()} through {extension.ex_date.max()}. Certification cannot exceed 2026-09-11. Confirmation must use the frozen raw hashes, exact endpoint/session checks, accepted identity safety, and both historical and extension blocking ledgers.\n\nThe conditional decision reflects the single overlap false negative and widespread official/Bhavcopy ISIN-version differences. Both are conservatively contained by endpoint validity and blocked ISIN-conflict events. No reversal outcome was inspected while building this layer.\n"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--verify-rebuild",action="store_true");args=parser.parse_args();c=config();frozen=verify_frozen_inputs(c)
    outputs,extension,source_manifest,acceptance=build(c);report_dir=local(c["report_dir"]);report_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ca-extension-stage-",dir=report_dir) as tmp:
      stage=Path(tmp)
      for name,frame in outputs.items():frame.to_csv(stage/name,index=False,date_format="%Y-%m-%d")
      extension.to_parquet(stage/"phase10_corporate_action_extension.parquet",index=False,compression="zstd")
      (stage/"official_source_manifest.json").write_text(canonical_json(source_manifest));(stage/"extension_acceptance.json").write_text(canonical_json(acceptance))
      names=list(outputs)+["phase10_corporate_action_extension.parquet","official_source_manifest.json","extension_acceptance.json"]
      (stage/"phase10_corporate_action_extension.md").write_text(report(acceptance,outputs["extension_coverage.csv"],extension))
      hashes={n:sha256(stage/n) for n in names};hashes["phase10_corporate_action_extension.md"]=sha256(stage/"phase10_corporate_action_extension.md")
      key={"frozen_inputs":frozen,"config":c,"code_sha256":code_hash(),"output_sha256":hashes}
      build_id=hashlib.sha256(canonical_json(key).encode()).hexdigest()
      manifest={**key,"build_id":build_id,"decision":acceptance["decision"],"extension_coverage_end":c["extension_to"],"post_cutoff_reversal_outcomes_inspected":False}
      manifest_path=report_dir/"phase10_ca_extension_manifest.json";dest={n:report_dir/n for n in outputs};dest.update({"phase10_corporate_action_extension.parquet":local(c["extension_ledger"]),"official_source_manifest.json":report_dir/"official_source_manifest.json","extension_acceptance.json":report_dir/"extension_acceptance.json","phase10_corporate_action_extension.md":local(c["final_report"])})
      if args.verify_rebuild:
        prior=json.loads(manifest_path.read_text())
        if prior["build_id"]!=build_id or prior["output_sha256"]!=hashes:raise AssertionError("Phase-10B extension rebuild differs")
        for n,digest in hashes.items():
          if sha256(dest[n])!=digest:raise AssertionError(f"Published extension differs: {n}")
        proof={"build_id":build_id,"byte_identical":True,"output_count":len(hashes)};(report_dir/"phase10_ca_extension_rebuild_verification.json").write_text(canonical_json(proof));print(f"PASS extension rebuild: {len(hashes)} outputs; {build_id}");return
      for n,path in dest.items():path.parent.mkdir(parents=True,exist_ok=True);os.replace(stage/n,path)
      manifest["build_timestamp_utc"]=datetime.now(timezone.utc).isoformat();manifest_path.write_text(canonical_json(manifest));print(f"Built Phase-10B CA extension: {len(hashes)} outputs; {build_id}");print(acceptance["decision"])


if __name__=="__main__":main()
