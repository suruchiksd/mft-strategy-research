import numpy as np
import pandas as pd

from mft_research.csrs.analysis import quantile_analysis, rank_ic, spearman_manual
from mft_research.csrs.factor import add_cross_sectional_ranks, assign_deciles


def ranked_fixture():
    return pd.DataFrame({"date": [pd.Timestamp("2024-01-01").date()] * 3 + [pd.Timestamp("2024-01-02").date()] * 2,
                         "symbol": ["B", "A", "C", "A", "B"], "ret_5": [0.2, 0.1, 0.3, 0.4, 0.2],
                         "valid_ret_5": True, "future_ret_1": [2., 1., 3., 2., 1.], "valid_future_1": True})


def test_ranking_same_date_and_strongest_highest_percentile():
    result = add_cross_sectional_ranks(ranked_fixture(), (5,))
    first = result[result.date == result.date.min()].set_index("symbol")
    assert first.loc["C", "csrs_rank_5"] == 3 and first.loc["C", "csrs_pct_5"] == 1
    assert first.loc["A", "csrs_pct_5"] == 0 and first.cross_section_count_5.eq(3).all()
    second = result[result.date == result.date.max()]
    assert second.cross_section_count_5.eq(2).all()


def test_tie_handling_is_symbol_deterministic():
    frame = ranked_fixture().iloc[:3].copy(); frame["ret_5"] = 1.0
    one = add_cross_sectional_ranks(frame, (5,)).set_index("symbol")
    two = add_cross_sectional_ranks(frame.sample(frac=1, random_state=2), (5,)).set_index("symbol")
    assert one.csrs_rank_5.to_dict() == two.csrs_rank_5.to_dict() == {"B": 2, "A": 1, "C": 3}


def test_quantiles_are_deterministic_and_d10_is_strongest():
    frame = pd.DataFrame({"csrs_rank_5": range(1, 21), "cross_section_count_5": 20})
    expected = assign_deciles(frame, "csrs_rank_5", "cross_section_count_5")
    shuffled = frame.sample(frac=1, random_state=4)
    actual = assign_deciles(shuffled, "csrs_rank_5", "cross_section_count_5").sort_index()
    pd.testing.assert_series_equal(expected, actual)
    assert expected.iloc[:2].eq(1).all() and expected.iloc[-2:].eq(10).all()


def test_rank_ic_matches_manual_examples():
    assert spearman_manual(pd.Series([1, 2, 3]), pd.Series([10, 20, 30])) == 1.0
    assert np.isclose(spearman_manual(pd.Series([1, 2, 3]), pd.Series([30, 10, 20])), -0.5)
    panel = add_cross_sectional_ranks(ranked_fixture(), (5,))
    daily, summary = rank_ic(panel, (5,), (1,))
    assert np.allclose(daily.rank_ic, 1) and np.isclose(summary.mean_ic.iloc[0], 1)


def test_no_combined_or_weighted_csrs_is_generated():
    result = add_cross_sectional_ranks(ranked_fixture(), (5,))
    forbidden = [c for c in result if "combined" in c.lower() or "weight" in c.lower() or c == "csrs_score"]
    assert forbidden == []
