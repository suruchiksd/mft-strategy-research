"""Exhaustive post-outcome classification amendment for future Phase-10 data."""

from __future__ import annotations

from itertools import product

import pandas as pd

CANDIDATE_CLASSES = (
    "INSUFFICIENT SAMPLE",
    "CONTRADICTORY",
    "MIXED",
    "DIRECTIONALLY POSITIVE BUT UNSTABLE",
    "SUPPORTIVE BUT SHORT SAMPLE",
    "SUPPORTED",
)

OVERALL_DECISIONS = (
    "PASS FOR COMPLEMENTARITY RESEARCH",
    "CONDITIONAL PASS",
    "RESEARCH FURTHER",
    "FAIL",
)


def directional_retention(primary: int, moderate: int, nonoverlap: int,
                          average_basic_positive: bool, average_moderate_positive: bool,
                          leave_one_date_sign_flip: bool) -> bool:
    return (primary >= 4 and moderate >= 4 and nonoverlap >= 4 and
            average_basic_positive and average_moderate_positive and
            not leave_one_date_sign_flip)


def classify_candidate(primary: int, moderate: int, nonoverlap: int,
                       average_basic_positive: bool, average_moderate_positive: bool,
                       leave_one_date_sign_flip: bool, minimum_date_band: str) -> str:
    if not all(isinstance(value, int) and 0 <= value <= 6 for value in (primary, moderate, nonoverlap)):
        raise ValueError("Horizon counts must be integers from zero through six")
    if minimum_date_band not in ("LT20", "20_TO_59", "GE60"):
        raise ValueError("Unknown minimum-date band")
    if minimum_date_band == "LT20":
        return "INSUFFICIENT SAMPLE"
    if primary <= 1:
        return "CONTRADICTORY"
    if primary <= 3:
        return "MIXED"
    stable = directional_retention(primary, moderate, nonoverlap,
                                   average_basic_positive, average_moderate_positive,
                                   leave_one_date_sign_flip)
    if not stable:
        return "DIRECTIONALLY POSITIVE BUT UNSTABLE"
    if minimum_date_band == "20_TO_59":
        return "SUPPORTIVE BUT SHORT SAMPLE"
    return "SUPPORTED"


def classify_overall(first: str, second: str) -> str:
    if first not in CANDIDATE_CLASSES or second not in CANDIDATE_CLASSES:
        raise ValueError("Unknown candidate classification")
    pair = (first, second)
    if pair == ("SUPPORTED", "SUPPORTED"):
        return "PASS FOR COMPLEMENTARITY RESEARCH"
    if "SUPPORTED" in pair or pair == ("SUPPORTIVE BUT SHORT SAMPLE",) * 2:
        return "CONDITIONAL PASS"
    if pair == ("CONTRADICTORY", "CONTRADICTORY"):
        return "FAIL"
    return "RESEARCH FURTHER"


def candidate_rule_table() -> pd.DataFrame:
    return pd.DataFrame([
      (1,"INSUFFICIENT SAMPLE","Any required horizon has fewer than 20 daily IC dates","Any","Not evaluated","Evaluation stops at first matching row"),
      (2,"CONTRADICTORY","Every required horizon has at least 20 dates","0 or 1 positive BASIC horizons","Not required","Adequate sample; primary sign count controls"),
      (3,"MIXED","Every required horizon has at least 20 dates","2 or 3 positive BASIC horizons","Not required","Adequate sample; primary sign count controls"),
      (4,"DIRECTIONALLY POSITIVE BUT UNSTABLE","Every required horizon has at least 20 dates","4, 5, or 6 positive BASIC horizons","At least one complete directional-retention requirement fails","Includes MODERATE, non-overlap, average-IC, or leave-one-date failure"),
      (5,"SUPPORTIVE BUT SHORT SAMPLE","Every required horizon has at least 20 dates and at least one has fewer than 60","4, 5, or 6 positive BASIC horizons","Every directional-retention requirement passes","Short evaluable sample"),
      (6,"SUPPORTED","Every required horizon has at least 60 dates","4, 5, or 6 positive BASIC horizons","Every directional-retention requirement passes","Full amended support threshold")],
      columns=["evaluation_order","classification","sample_condition","primary_horizon_condition","directional_condition","notes"])


def overall_decision_table() -> pd.DataFrame:
    rows=[]
    for first,second in product(CANDIDATE_CLASSES, repeat=2):
        rows.append({"REV05_classification":first,"REV20_classification":second,
                     "overall_decision":classify_overall(first,second)})
    return pd.DataFrame(rows)


def enumerate_candidate_states() -> pd.DataFrame:
    rows=[]
    for primary,moderate,nonoverlap,basic_avg,moderate_avg,flip,dates in product(
            range(7),range(7),range(7),(False,True),(False,True),(False,True),("LT20","20_TO_59","GE60")):
        rows.append({"positive_primary_horizons":primary,"positive_moderate_horizons":moderate,
          "positive_nonoverlap_horizons":nonoverlap,"average_basic_positive":basic_avg,
          "average_moderate_positive":moderate_avg,"leave_one_date_sign_flip":flip,
          "minimum_date_band":dates,"classification":classify_candidate(primary,moderate,nonoverlap,basic_avg,moderate_avg,flip,dates)})
    return pd.DataFrame(rows)
