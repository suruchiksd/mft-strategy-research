from datetime import date, timedelta

import numpy as np
import pandas as pd

from mft_research.csrs.factor import add_cross_sectional_ranks
from mft_research.csrs.intervals import build_interval_panel


def fixture(symbol="AAA", prices=(100, 101, 102, 103, 104, 110), eligible=None, start=date(2024, 1, 1)):
    dates = [start + timedelta(days=2 * i) for i in range(len(prices))]
    if eligible is None:
        eligible = [True] * len(prices)
    daily = pd.DataFrame({"date": dates, "symbol": symbol, "close": prices,
                          "research_eligible": eligible,
                          "exclusion_reason": ["" if x else "PARTIAL_SESSION_UNRESOLVED" for x in eligible]})
    calendar = pd.DataFrame({"date": dates})
    ledger = pd.DataFrame(columns=["affects_current_universe", "series", "research_impact", "symbol", "date"])
    return daily, calendar, ledger


def panel(daily, calendar, ledger, formation=(5,), future=(1,), cutoff=date(2026, 7, 17)):
    return build_interval_panel(daily, ledger, calendar, formation, future, cutoff)


def event(symbol="AAA", day=date(2024, 1, 7), impact="MATERIAL_UNRESOLVED_EVENT"):
    return pd.DataFrame([{"affects_current_universe": True, "series": "EQ", "research_impact": impact,
                          "symbol": symbol, "date": day}])


def test_exact_momentum_and_trading_sessions_not_calendar_days():
    daily, calendar, ledger = fixture()
    result = panel(daily, calendar, ledger)
    row = result.iloc[-1]
    assert np.isclose(row.ret_5, 0.10) and row.valid_ret_5
    assert row.ret_5_endpoint_date == date(2024, 1, 1)


def test_exact_future_return():
    daily, calendar, ledger = fixture(prices=(100, 105))
    result = panel(daily, calendar, ledger, formation=(1,), future=(1,))
    assert np.isclose(result.iloc[0].future_ret_1, .05) and result.iloc[0].valid_future_1


def test_future_values_cannot_affect_factor_at_t():
    daily, calendar, ledger = fixture(prices=(100, 101, 102, 103, 104, 105, 106))
    base = panel(daily, calendar, ledger)
    changed = daily.copy(); changed.loc[changed.index[-1], "close"] = 99999
    revised = panel(changed, calendar, ledger)
    pd.testing.assert_series_equal(base.loc[:5, "ret_5"], revised.loc[:5, "ret_5"])


def test_modifying_rows_after_t_does_not_change_rank_at_t():
    a, calendar, ledger = fixture("AAA", (10, 10, 10, 10, 10, 11, 12))
    b, _, _ = fixture("BBB", (10, 10, 10, 10, 10, 12, 13))
    daily = pd.concat([a, b], ignore_index=True)
    base = add_cross_sectional_ranks(panel(daily, calendar, ledger), (5,))
    daily.loc[(daily.symbol == "AAA") & (daily.date == calendar.date.iloc[-1]), "close"] = 500
    revised = add_cross_sectional_ranks(panel(daily, calendar, ledger), (5,))
    day = calendar.date.iloc[-2]
    factor_columns = ["date", "symbol", "ret_5", "valid_ret_5", "ret_5_invalid_reason",
                      "csrs_rank_5", "csrs_pct_5", "cross_section_count_5"]
    pd.testing.assert_frame_equal(base.loc[base.date == day, factor_columns].reset_index(drop=True),
                                  revised.loc[revised.date == day, factor_columns].reset_index(drop=True))


def test_blocking_action_invalidates_lookback_and_future():
    daily, calendar, _ = fixture()
    result = panel(daily, calendar, event(day=calendar.date.iloc[3]))
    assert "UNRESOLVED_CORPORATE_ACTION_INTERVAL" in result.iloc[-1].ret_5_invalid_reason
    assert "UNRESOLVED_CORPORATE_ACTION_INTERVAL" in result.iloc[2].future_invalid_reason_1


def test_nonblocking_action_does_not_invalidate():
    daily, calendar, _ = fixture()
    ledger = event(day=calendar.date.iloc[3], impact="LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION")
    result = panel(daily, calendar, ledger)
    assert result.iloc[-1].valid_ret_5 and result.iloc[2].valid_future_1


def test_coverage_cutoff_rejects_factor_and_target():
    daily, calendar, ledger = fixture(start=date(2026, 7, 8))
    result = panel(daily, calendar, ledger, formation=(1,), future=(1,), cutoff=date(2026, 7, 17))
    after = result[result.date > date(2026, 7, 17)]
    assert (~after.valid_ret_1).all()
    assert after.ret_1_invalid_reason.str.contains("CORPORATE_ACTION_COVERAGE_UNCERTIFIED").all()
    crossing = result[result.future_1_endpoint_date > date(2026, 7, 17)]
    assert crossing.future_invalid_reason_1.str.contains("CORPORATE_ACTION_COVERAGE_UNCERTIFIED").all()


def test_identity_contamination_never_enters_interval():
    daily, calendar, ledger = fixture(eligible=[False, True, True, True, True, True])
    daily.loc[0, "exclusion_reason"] = "PRELISTING_IDENTITY_CONTAMINATION"
    result = panel(daily, calendar, ledger)
    assert not result.iloc[-1].valid_ret_5
    assert "IDENTITY_CONTAMINATION" in result.iloc[-1].ret_5_invalid_reason


def test_ineligible_endpoint_and_intervening_session_invalidate():
    daily, calendar, ledger = fixture(eligible=[True, False, True, True, True, True])
    result = panel(daily, calendar, ledger, formation=(5, 4), future=(1, 4))
    assert not result.iloc[-1].valid_ret_4
    assert "LOOKBACK_ENDPOINT_INELIGIBLE" in result.iloc[-1].ret_4_invalid_reason
    assert not result.iloc[0].valid_future_4
    assert "UNSAFE_SESSION_INTERVAL" in result.iloc[0].future_invalid_reason_4


def test_missing_endpoint_and_intervening_date_not_compressed():
    daily, calendar, ledger = fixture()
    daily = daily.drop(index=2)
    result = panel(daily, calendar, ledger, formation=(3,), future=(3,))
    last = result.iloc[-1]
    assert not last.valid_ret_3 and "UNAVAILABLE_ENDPOINT" in last.ret_3_invalid_reason
    assert not result.iloc[0].valid_future_3 and "MISSING_UNSAFE_SESSION_INTERVAL" in result.iloc[0].future_invalid_reason_3
