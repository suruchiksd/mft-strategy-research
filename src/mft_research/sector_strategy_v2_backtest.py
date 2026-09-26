"""Frozen Phase-12B V2 stateful backtest helpers."""
from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd

from mft_research.data.manifest import canonical_json


def weekly_signals(calendar, end_date):
    dates = sorted(pd.to_datetime(calendar).date)
    x = pd.DataFrame({"signal_date": dates})
    x["week"] = pd.to_datetime(x.signal_date).dt.strftime("%G-W%V")
    x = x.groupby("week", sort=True).signal_date.max().reset_index(drop=True)
    dates = list(dates)
    pos = {d: i for i, d in enumerate(dates)}
    return pd.DataFrame({
        "signal_date": x,
        "execution_date": [dates[pos[d] + 1] if pos[d] + 1 < len(dates) else pd.NaT for d in x],
    }).query("signal_date <= @end_date and execution_date == execution_date").reset_index(drop=True)


def action_dates(actions, blocking_impacts):
    x = actions[actions.research_impact.isin(blocking_impacts)].copy()
    return {s: set(pd.to_datetime(g.date).dt.date) for s, g in x.groupby("symbol", sort=True)}


def frozen_sector_selection(factor, date, active):
    x = factor[(factor.date == date) & factor.valid_sector_ret_20].copy()
    x = x.sort_values(["sector_ret_20", "sector_code"], ascending=[False, True], kind="stable").reset_index(drop=True)
    x["strength_rank"] = np.arange(1, len(x) + 1)
    by = x.set_index("sector_code")
    retained = [s for s in sorted(active) if s in by.index and int(by.loc[s, "strength_rank"]) <= 5]
    retained = sorted(retained, key=lambda s: (int(by.loc[s, "strength_rank"]), s))[:3]
    selected = list(retained)
    for r in x.itertuples(index=False):
        if len(selected) >= 3:
            break
        if r.sector_code not in active and int(r.strength_rank) <= 3:
            selected.append(r.sector_code)
    return x[x.sector_code.isin(selected)].sort_values(["strength_rank", "sector_code"], kind="stable").reset_index(drop=True)


def frozen_stock_plan(daily, mapping, sectors, holdings, held_sectors, blocked, signal_date, execution_date):
    cols = ["symbol", "universe_basic_liquid", "research_quality_status",
            "close", "avg_turnover_20", "recent_presence_20", "series"]
    source = daily[daily.date.eq(signal_date)][cols]
    if source.empty:
        return pd.DataFrame(columns=["symbol", "sector", "sector_code", "sector_strength_rank", "liquidity_rank", "selection_status"]), pd.DataFrame(columns=["symbol", "sector_code", "liquidity_rank", "new_entry_eligible"])
    x = source.merge(
        mapping[["symbol", "sector", "sector_code", "mapping_status", "identity_ambiguous"]],
        on="symbol", how="left", suffixes=("", "_map"), validate="many_to_one")
    x = x[x.universe_basic_liquid.fillna(False)
          & x.research_quality_status.eq("VALID_REPORTED_EQ_ROW")
          & x.close.gt(0) & x.avg_turnover_20.gt(0)
          & x.recent_presence_20.fillna(False)
          & x.series.eq("EQ") & x.mapping_status.eq("STATIC_CURRENT_UNIQUE")
          & ~x.identity_ambiguous.fillna(True)].copy()
    if x.empty:
        return pd.DataFrame(columns=["symbol", "sector", "sector_code", "sector_strength_rank", "liquidity_rank", "selection_status"]), pd.DataFrame(columns=["symbol", "sector_code", "liquidity_rank", "new_entry_eligible"])
    # A known blocking event crossing the next execution interval makes a new
    # candidate unsafe; this does not synthesize adjustments.
    x["ca_safe"] = [not any(signal_date < d <= execution_date for d in blocked.get(s, set())) for s in x.symbol]
    x = x[x.ca_safe].copy()
    if "sector_code" not in x.columns:
        raise RuntimeError(f"sector_code missing after mapping merge: source={source.columns.tolist()} source_rows={len(source)} x={x.columns.tolist()} x_rows={len(x)} signal={signal_date} mapping={mapping.columns.tolist()}")
    x = x.sort_values(["sector_code", "avg_turnover_20", "symbol"], ascending=[True, False, True], kind="stable")
    x["liquidity_rank"] = x.groupby("sector_code", sort=False).cumcount() + 1
    x["new_entry_eligible"] = x.liquidity_rank.le(3)
    strength = sectors.set_index("sector_code").strength_rank.to_dict()
    x["sector_strength_rank"] = x.sector_code.map(strength)
    intended = []
    for code in sectors.sort_values(["strength_rank", "sector_code"]).sector_code:
        g = x[x.sector_code.eq(code)].copy()
        held = [s for s in holdings if held_sectors.get(s) == code and s in set(g.loc[g.liquidity_rank.le(5), "symbol"])]
        held = sorted(held, key=lambda s: (int(g.set_index("symbol").loc[s, "liquidity_rank"]), s))[:3]
        chosen = list(held)
        for r in g[g.new_entry_eligible].itertuples(index=False):
            if len(chosen) >= 3:
                break
            if r.symbol not in holdings and r.symbol not in chosen:
                chosen.append(r.symbol)
        for s in chosen:
            r = g[g.symbol.eq(s)].iloc[0]
            intended.append({"symbol": s, "sector": r.sector, "sector_code": code,
                             "sector_strength_rank": int(strength[code]),
                             "liquidity_rank": int(r.liquidity_rank),
                             "selection_status": "RETAINED" if s in holdings else "NEW_ENTRY"})
    intended = pd.DataFrame(intended)
    if intended.empty:
        intended = pd.DataFrame(columns=["symbol", "sector", "sector_code", "sector_strength_rank", "liquidity_rank", "selection_status"])
    if not intended.empty:
        intended = intended.sort_values(["sector_strength_rank", "liquidity_rank", "symbol"], kind="stable").reset_index(drop=True)
    frozen = x.sort_values(["sector_strength_rank", "liquidity_rank", "symbol"], kind="stable").reset_index(drop=True)
    return intended, frozen


def list_hash(frame):
    rows = frame[["symbol", "sector_code", "liquidity_rank", "new_entry_eligible"]].to_dict("records") if len(frame) else []
    return hashlib.sha256(canonical_json(rows).encode()).hexdigest()


def _quote(day, symbol, quotes):
    if day not in quotes.index or symbol not in quotes.loc[day].index:
        return None
    x = quotes.loc[day, symbol]
    return x


def simulate_v2(daily, factor, mapping, actions, start, end, capital, transaction_cost_bps, slippage_bps, raw_provider=None):
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    d = daily[daily.date.between(start, end)].copy().sort_values(["date", "symbol"], kind="stable")
    calendar = sorted(d.date.unique())
    signals = weekly_signals(calendar, end)
    signal_lookup = signals.set_index("execution_date").to_dict("index")
    factor = factor.copy(); factor.date = pd.to_datetime(factor.date).dt.date
    blocked = action_dates(actions, {"MATERIAL_UNRESOLVED_EVENT", "UNKNOWN_OR_AMBIGUOUS", "LIKELY_ALREADY_ADJUSTED_CONVENTIONAL_ACTION"})
    day_rows = {day: g.set_index("symbol") for day, g in d.groupby("date", sort=False)}
    holdings, sectors_active, desired = {}, set(), set()
    pending = {}
    cash = float(capital); previous_close = {}; previous_mark = {}
    equity, trades, positions, contributions, rebalance_rows, anomalies, selection_rows = [], [], [], [], [], [], []
    daily_sector = {}; holding_start = {}; holding_lengths = []
    for i, day in enumerate(calendar):
        prices = day_rows[day].copy()
        if raw_provider is not None:
            raw = raw_provider(day)
            if len(raw):
                extra = raw[~raw.symbol.isin(prices.index) & raw.series.isin(["EQ", "BE"])].set_index("symbol")
                if len(extra):
                    prices = pd.concat([prices, extra], axis=0)
        # Retry previously unexecutable exits before scheduled orders.
        for s in sorted(list(pending)):
            if s not in holdings:
                pending.pop(s, None); continue
            if s in prices.index and prices.loc[s, "series"] in ("EQ", "BE") and pd.notna(prices.loc[s, "open"]) and prices.loc[s, "open"] > 0:
                q = holdings.pop(s); op = float(prices.loc[s, "open"]); fill = op * (1 - slippage_bps / 10000); notional = q * fill; fee = notional * transaction_cost_bps / 10000
                cash += notional - fee; trades.append({"date": day, "rebalance_id": "RETRY", "symbol": s, "side": "SELL", "quantity": q, "reference_open": op, "fill_price": fill, "notional": notional, "transaction_cost": fee, "slippage_bps": slippage_bps, "trade_class": "FORCED_OPERATIONAL", "series": prices.loc[s, "series"]})
                contributions.append({"date": day, "symbol": s, "sector": daily_sector.get(s, "UNMAPPED"), "contribution_rupees": -fee})
                holding_lengths.append(i - holding_start.pop(s, i)); previous_close.pop(s, None); previous_mark.pop(s, None); pending.pop(s, None)
                anomalies.append({"date": day, "type": "RETRY_EXIT", "detail": s, "series": prices.loc[s, "series"]})
        sig = signal_lookup.get(day)
        if sig is not None:
            sd = pd.Timestamp(sig["signal_date"]).date(); ex = day
            previous_active = set(sectors_active)
            sectors = frozen_sector_selection(factor, sd, sectors_active)
            intended, frozen = frozen_stock_plan(d, mapping, sectors, holdings, daily_sector, blocked, sd, ex)
            new_desired = set(intended.symbol) if len(intended) else set()
            for s in sorted(set(holdings) - new_desired): pending[s] = True
            sectors_active = set(sectors.sector_code)
            selection_rows.append({"rebalance_id": f"SMV2-{len(selection_rows)+1:04d}", "signal_date": sd, "execution_date": ex,
                                   "selected_sectors": "|".join(sectors.sector_code), "selected_stocks": "|".join(intended.symbol) if len(intended) else "",
                                   "sectors_retained": int(sectors.sector_status.eq("RETAINED").sum()) if "sector_status" in sectors else 0,
                                   "stocks_retained": int(intended.selection_status.eq("RETAINED").sum()) if len(intended) else 0,
                                   "frozen_replacement_list_sha256": list_hash(frozen), "frozen_replacement_candidates": len(frozen)})
            desired = new_desired
            target_n = max(len(intended), 1)
            valid_open = {s for s in set(holdings) | set(intended.symbol if len(intended) else []) if s in prices.index and prices.loc[s, "series"] in ("EQ", "BE") and pd.notna(prices.loc[s, "open"]) and prices.loc[s, "open"] > 0}
            pretrade = cash + sum(q * (float(prices.loc[s, "open"]) if s in valid_open else previous_mark.get(s, previous_close.get(s, 0.0))) for s, q in holdings.items())
            target_value = pretrade / target_n
            planned = set(intended.symbol) if len(intended) else set()
            # First sell deselected positions, retaining any without supported open.
            for s in sorted(set(holdings) - planned):
                if s not in valid_open:
                    pending[s] = True; anomalies.append({"date": day, "type": "UNEXECUTABLE_EXIT_NO_VALID_OPEN", "detail": s, "series": "UNKNOWN"}); continue
                q = holdings.pop(s); op = float(prices.loc[s, "open"]); fill = op * (1 - slippage_bps / 10000); notional = q * fill; fee = notional * transaction_cost_bps / 10000
                cash += notional - fee; trades.append({"date": day, "rebalance_id": selection_rows[-1]["rebalance_id"], "symbol": s, "side": "SELL", "quantity": q, "reference_open": op, "fill_price": fill, "notional": notional, "transaction_cost": fee, "slippage_bps": slippage_bps, "trade_class": "SECTOR_ENTRY_EXIT" if daily_sector.get(s) not in previous_active else "WITHIN_SECTOR_STOCK_REPLACEMENT", "series": prices.loc[s, "series"]})
                contributions.append({"date": day, "symbol": s, "sector": daily_sector.get(s, "UNMAPPED"), "contribution_rupees": -fee}); holding_lengths.append(i - holding_start.pop(s, i)); previous_close.pop(s, None); previous_mark.pop(s, None); pending.pop(s, None)
            # Resize/exchange retained positions only outside the frozen 2pp band.
            for s in sorted(set(holdings) & planned):
                if s not in valid_open: continue
                op = float(prices.loc[s, "open"]); preweight = holdings[s] * op / pretrade if pretrade else 0
                if abs(preweight - 1 / target_n) < 0.02: continue
                want = int(np.floor(target_value / (op * (1 + slippage_bps / 10000) * (1 + transaction_cost_bps / 10000))))
                if want < holdings[s]:
                    q = holdings[s] - want; fill = op * (1 - slippage_bps / 10000); notional = q * fill; fee = notional * transaction_cost_bps / 10000; cash += notional - fee; holdings[s] = want; side = "SELL"
                else:
                    q = min(want - holdings[s], int(np.floor(max(cash, 0) / (op * (1 + slippage_bps / 10000) * (1 + transaction_cost_bps / 10000))))); fill = op * (1 + slippage_bps / 10000); notional = q * fill; fee = notional * transaction_cost_bps / 10000; cash -= notional + fee; holdings[s] += q; side = "BUY"
                if q > 0: trades.append({"date": day, "rebalance_id": selection_rows[-1]["rebalance_id"], "symbol": s, "side": side, "quantity": q, "reference_open": op, "fill_price": fill, "notional": notional, "transaction_cost": fee, "slippage_bps": slippage_bps, "trade_class": "WEIGHT_REBALANCING", "series": prices.loc[s, "series"]}); contributions.append({"date": day, "symbol": s, "sector": daily_sector.get(s, "UNMAPPED"), "contribution_rupees": -fee})
            # New entries use only the frozen top-three eligible sequence.
            for r in intended.sort_values(["sector_strength_rank", "liquidity_rank", "symbol"]).itertuples(index=False):
                if r.symbol in holdings or r.symbol not in valid_open or len(holdings) >= 9: continue
                op = float(prices.loc[r.symbol, "open"]); want = int(np.floor(target_value / (op * (1 + slippage_bps / 10000) * (1 + transaction_cost_bps / 10000)))); q = min(want, int(np.floor(max(cash, 0) / (op * (1 + slippage_bps / 10000) * (1 + transaction_cost_bps / 10000))))); fill = op * (1 + slippage_bps / 10000); notional = q * fill; fee = notional * transaction_cost_bps / 10000
                if q <= 0: anomalies.append({"date": day, "type": "UNAVAILABLE_ENTRY_OR_ZERO_SHARES", "detail": r.symbol, "series": "EQ"}); continue
                cash -= notional + fee; holdings[r.symbol] = q; holding_start[r.symbol] = i; daily_sector[r.symbol] = r.sector_code; trades.append({"date": day, "rebalance_id": selection_rows[-1]["rebalance_id"], "symbol": r.symbol, "side": "BUY", "quantity": q, "reference_open": op, "fill_price": fill, "notional": notional, "transaction_cost": fee, "slippage_bps": slippage_bps, "trade_class": "SECTOR_ENTRY_EXIT" if r.sector_code not in previous_active else "WITHIN_SECTOR_STOCK_REPLACEMENT", "series": "EQ"}); contributions.append({"date": day, "symbol": r.symbol, "sector": r.sector_code, "contribution_rupees": -fee})
            rebalance_rows.append({"rebalance_id": selection_rows[-1]["rebalance_id"], "signal_date": sd, "execution_date": day, "selected_positions": len(planned), "actual_positions": len(holdings), "pretrade_equity": pretrade, "gross_turnover": sum(t["notional"] for t in trades if t["date"] == day) / pretrade if pretrade else 0, "costs": sum(t["transaction_cost"] for t in trades if t["date"] == day)})
        if not holdings and not equity:
            continue
        today_contrib = defaultdict(float)
        for s, q in list(holdings.items()):
            if s not in prices.index or pd.isna(prices.loc[s, "close"]) or prices.loc[s, "close"] <= 0:
                anomalies.append({"date": day, "type": "STALE_MARK_CARRIED_NO_VALID_CLOSE", "detail": s, "series": "UNKNOWN"}); previous_mark[s] = previous_mark.get(s, previous_close.get(s, 0.0)); continue
            close = float(prices.loc[s, "close"]); base = previous_close.get(s, close); today_contrib[s] += q * (close - base); previous_close[s] = close; previous_mark[s] = close
        nav = cash + sum(q * previous_mark.get(s, 0.0) for s, q in holdings.items())
        equity.append({"date": day, "cash": cash, "market_value": nav - cash, "equity": nav, "nav": nav / capital, "positions": len(holdings), "turnover": rebalance_rows[-1]["gross_turnover"] if rebalance_rows and rebalance_rows[-1]["execution_date"] == day else 0.0, "costs": rebalance_rows[-1]["costs"] if rebalance_rows and rebalance_rows[-1]["execution_date"] == day else 0.0})
        for s, v in today_contrib.items(): contributions.append({"date": day, "symbol": s, "sector": daily_sector.get(s, "UNMAPPED"), "contribution_rupees": v})
        for s, q in sorted(holdings.items()): positions.append({"date": day, "symbol": s, "sector": daily_sector.get(s, "UNMAPPED"), "shares": q, "close": previous_mark.get(s, 0.0), "market_value": q * previous_mark.get(s, 0.0), "weight": q * previous_mark.get(s, 0.0) / nav if nav else 0.0})
    for s in holdings: holding_lengths.append(len(calendar) - 1 - holding_start.get(s, 0))
    return {"equity": pd.DataFrame(equity), "trades": pd.DataFrame(trades), "positions": pd.DataFrame(positions), "contribution": pd.DataFrame(contributions), "rebalances": pd.DataFrame(rebalance_rows), "anomalies": pd.DataFrame(anomalies), "selection": pd.DataFrame(selection_rows), "holding_lengths": pd.DataFrame({"holding_sessions": holding_lengths})}


def metrics(result, initial):
    c = result["equity"].copy()
    if c.empty:
        return {"cumulative_return": np.nan, "CAGR": np.nan, "Sharpe": np.nan, "maximum_drawdown": np.nan}
    r = c.equity.pct_change().dropna(); n = len(r); cum = c.equity.iloc[-1] / initial - 1
    cagr = (1 + cum) ** (252 / n) - 1 if n and cum > -1 else np.nan
    vol = r.std(ddof=1) * np.sqrt(252) if len(r) > 1 else np.nan
    sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252) if len(r) > 1 and r.std(ddof=1) > 0 else np.nan
    dd = c.equity / c.equity.cummax() - 1
    duration = 0; maxduration = 0
    for x in dd: duration = duration + 1 if x < 0 else 0; maxduration = max(maxduration, duration)
    return {"start_date": c.date.min(), "end_date": c.date.max(), "observations": n, "cumulative_return": cum, "CAGR": cagr, "annualized_volatility": vol, "Sharpe": sharpe, "Sortino": np.nan, "maximum_drawdown": dd.min(), "Calmar": cagr / abs(dd.min()) if dd.min() < 0 else np.nan, "maximum_drawdown_duration_sessions": maxduration, "positive_daily_periods": int(r.gt(0).sum()), "negative_daily_periods": int(r.lt(0).sum()), "total_turnover": result["rebalances"].gross_turnover.sum() if len(result["rebalances"]) else 0, "mean_weekly_gross_turnover": result["rebalances"].gross_turnover.mean() if len(result["rebalances"]) else np.nan, "costs_rupees": result["trades"].transaction_cost.sum() if len(result["trades"]) else 0, "trade_count": len(result["trades"]), "rebalance_count": len(result["rebalances"]), "average_holding_sessions": result["holding_lengths"].holding_sessions.mean() if len(result["holding_lengths"]) else np.nan, "mean_positions": c.positions.mean(), "mean_cash_utilization": ((c.equity - c.cash) / c.equity).mean(), "operational_anomalies": len(result["anomalies"])}
