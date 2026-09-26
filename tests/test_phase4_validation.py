from datetime import date, timedelta

import numpy as np
import pandas as pd

from mft_research.csrs.phase4 import (deletion_statistics, expanding_window,
    fixed_periods, leave_one_year_out, moving_block_bootstrap, nonoverlap)


def cache_fixture():
    dates = [date(2020, 12, 31), date(2021, 1, 4), date(2022, 1, 3), date(2023, 1, 2)]
    daily = pd.DataFrame({"date": dates, "ic": [-.1, .1, .2, .3],
                          "daily_spread": [-.01, .01, .02, .03], "observations": 20,
                          "cross_section_count": 20})
    for q in range(1, 11):
        daily[f"q{q}_sum"] = q / 100
        daily[f"q{q}_count"] = 1
    return {(f, h): daily.copy() for f in (5, 10, 20, 40, 60) for h in (1, 2, 3, 5, 10, 20)}


def test_expanding_folds_use_only_prior_history_and_preserve_30_pairs():
    result = expanding_window(cache_fixture(), (2021,))
    assert len(result) == 30
    assert result.history_end_year.eq(2020).all()
    assert result.history_valid_dates.eq(1).all() and result.evaluation_valid_dates.eq(1).all()


def test_fixed_period_boundaries_are_locked_and_preserve_pairs():
    periods = [{"name": "DEV", "start": "2020-01-01", "end": "2022-12-31"}]
    result = fixed_periods(cache_fixture(), periods)
    assert len(result) == 30
    assert result.calendar_start.eq(date(2020, 1, 1)).all()
    assert result.calendar_end.eq(date(2022, 12, 31)).all()
    assert result.actual_last_date.eq(date(2022, 1, 3)).all()


def test_leave_one_year_removes_only_that_year():
    result = leave_one_year_out(cache_fixture(), (2021,))
    assert len(result) == 30 and result.valid_dates.eq(3).all()
    assert np.allclose(result.mean_ic, (-.1 + .2 + .3) / 3)


def test_nonoverlap_evaluates_all_offsets_and_spacing():
    start = date(2024, 1, 1)
    dates = [start + timedelta(days=i) for i in range(12)]
    cache = cache_fixture(); daily = next(iter(cache.values())).iloc[:0].copy()
    daily = pd.DataFrame({"date": dates, "ic": range(12), "daily_spread": range(12),
                          "observations": 10, "cross_section_count": 10})
    for q in range(1, 11): daily[f"q{q}_sum"], daily[f"q{q}_count"] = q, 1
    result = nonoverlap({(5, 3): daily}, dates, (3,))
    assert set(result.offset) == {0, 1, 2}
    for offset in range(3):
        chosen = [dates.index(day) for day in daily.date if dates.index(day) % 3 == offset]
        assert all(b - a >= 3 for a, b in zip(chosen, chosen[1:]))


def test_moving_block_bootstrap_is_deterministic():
    values = np.arange(50, dtype=float)
    assert moving_block_bootstrap(values, 10, 100, 7, .95) == moving_block_bootstrap(values, 10, 100, 7, .95)


def test_delete_one_statistics_matches_manual_spearman_and_removes_one():
    group = pd.DataFrame({"rank": [1, 2, 3, 4], "outcome": [4., 1., 2., 3.]})
    ic, _ = deletion_statistics(group, "rank", "outcome")
    for i in range(4):
        kept = group.drop(i)
        expected = kept["rank"].rank().corr(kept.outcome.rank())
        assert np.isclose(ic[i], expected)
