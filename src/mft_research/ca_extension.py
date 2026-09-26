"""Official-NSE corporate-action extension safety layer for Phase 10B."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RAW_COLUMNS = ("bcEndDate", "bcStartDate", "caBroadcastDate", "comp", "exDate", "faceVal",
               "ind", "isin", "ndEndDate", "ndStartDate", "recDate", "series", "subject", "symbol")


def classify_subject(subject: str) -> tuple[str, str, str]:
    normalized = re.sub(r"\s+", " ", str(subject).strip().upper())
    blocking = {
      "SPLIT_OR_FACE_VALUE_CHANGE": ("FACE VALUE", "SPLIT", "SUB-DIVISION", "CONSOLIDATION", "REVERSE SPLIT"),
      "BONUS": ("BONUS",), "RIGHTS": ("RIGHTS",), "DEMERGER_OR_SPINOFF": ("DEMERGER", "SPIN-OFF", "SPIN OFF"),
      "MERGER_OR_AMALGAMATION": ("MERGER", "AMALGAMATION"), "CAPITAL_REDUCTION": ("CAPITAL REDUCTION",),
      "SCHEME_OR_SPECIAL_DISTRIBUTION": ("SCHEME", "ARRANGEMENT", "NCRPS", "DISTRIBUTION", "ENTITLEMENT")}
    for action_type, terms in blocking.items():
        if any(term in normalized for term in terms):
            return action_type, "BLOCK_PRICE_RETURN_INTERVAL", f"OFFICIAL_PURPOSE_MATCH:{action_type}"
    if "BUY BACK" in normalized or "BUYBACK" in normalized:
        return "BUYBACK", "NONBLOCKING_INFORMATIONAL", "ACCEPTED_OVERLAP_BUYBACKS_NONBLOCKING_21_OF_21"
    if "DIVIDEND" in normalized:
        return "DIVIDEND", "NONBLOCKING_INFORMATIONAL", "ACCEPTED_OVERLAP_DIVIDENDS_NONBLOCKING_565_OF_565"
    return "OTHER_OR_UNKNOWN", "REVIEW_REQUIRED_BLOCKED", "UNRECOGNIZED_OFFICIAL_PURPOSE_CONSERVATIVELY_BLOCKED"


def parse_official(path: Path, source_endpoint: str, retrieval_timestamp: str, raw_sha256: str,
                   extension_version: str) -> pd.DataFrame:
    raw = pd.read_json(path)
    if tuple(raw.columns) != RAW_COLUMNS:
        raise ValueError(f"Official NSE schema changed: {tuple(raw.columns)}")
    records=[]
    for number,row in enumerate(raw.itertuples(index=False),start=1):
        action_type,safety,reason=classify_subject(row.subject)
        records.append({"source_row":number,"raw_symbol":row.symbol,"series":row.series,"isin":row.isin,
          "company_name":row.comp,"official_action_type":action_type,"purpose":row.subject,
          "announcement_date":pd.NaT if pd.isna(row.caBroadcastDate) else pd.to_datetime(row.caBroadcastDate).date(),
          "ex_date":pd.to_datetime(row.exDate,format="%d-%b-%Y").date(),
          "record_date":pd.NaT if row.recDate=="-" else pd.to_datetime(row.recDate,format="%d-%b-%Y").date(),
          "blocking_date":pd.to_datetime(row.exDate,format="%d-%b-%Y").date(),
          "safety_classification":safety,"classification_reason":reason,
          "source_endpoint":source_endpoint,"source_retrieval_timestamp":retrieval_timestamp,
          "raw_source_sha256":raw_sha256,"extension_version":extension_version})
    return pd.DataFrame(records)


def attach_identity(events: pd.DataFrame, daily_identity: pd.DataFrame) -> pd.DataFrame:
    """Map by exact symbol only; ISIN is an audit check, never a fuzzy join key."""
    events=events.copy(); observed=daily_identity.groupby("symbol").isin.agg(lambda x:set(x.dropna().astype(str)))
    mapped=[];statuses=[];final_safety=[];reasons=[]
    for row in events.itertuples(index=False):
        identifiers=observed.get(row.raw_symbol,set())
        if not identifiers:
            mapped.append(None);statuses.append("NOT_IN_RESEARCH_DATA");final_safety.append(row.safety_classification);reasons.append(row.classification_reason)
        elif row.isin in identifiers:
            mapped.append(row.raw_symbol);statuses.append("EXACT_SYMBOL_ISIN_OBSERVED");final_safety.append(row.safety_classification);reasons.append(row.classification_reason)
        else:
            mapped.append(row.raw_symbol);statuses.append("EXACT_SYMBOL_ISIN_CONFLICT");final_safety.append("REVIEW_REQUIRED_BLOCKED");reasons.append("EXACT_SYMBOL_MATCH_BUT_OFFICIAL_ISIN_NOT_OBSERVED_CONSERVATIVELY_BLOCKED")
    events["mapped_symbol"]=mapped;events["mapping_status"]=statuses
    events["safety_classification"]=final_safety;events["classification_reason"]=reasons
    return events


def blocking_event_map(extension: pd.DataFrame) -> dict[str, list]:
    selected=extension[extension.mapped_symbol.notna() & extension.safety_classification.isin(
        ["BLOCK_PRICE_RETURN_INTERVAL","REVIEW_REQUIRED_BLOCKED"])]
    return {symbol:sorted(group.blocking_date.unique()) for symbol,group in selected.groupby("mapped_symbol",sort=False)}
