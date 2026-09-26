from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "reports/sector_strategy/v2"
OUT = V2 / "paper_handoff/authoritative_parity"
REF = V2 / "development"
TOL = 0.01


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pos_map(df: pd.DataFrame, date: str) -> dict[str, int]:
    z = df[df.date.eq(date)]
    return {str(r.symbol): int(r.shares) for r in z.itertuples() if int(r.shares) > 0}


def main() -> None:
    # Freeze and hash paper-side outputs before any accepted reference is loaded.
    paper_files = [
        "historical_engine_orders.csv",
        "historical_engine_snapshots.csv",
        "historical_risk_parity.csv",
        "execution_quote_resolution_audit.csv",
        "historical_target_to_order_parity.csv",
    ]
    paper_manifest = {
        "source": "authoritative_runner_existing_outputs",
        "files": {
            name: {"sha256": sha256(OUT / name), "bytes": (OUT / name).stat().st_size}
            for name in paper_files
        },
        "reference_loaded_after_paper_outputs": True,
    }
    (OUT / "authoritative_paper_output_manifest.json").write_text(
        json.dumps(paper_manifest, indent=2) + "\n"
    )

    # Independent paper-side output is now frozen in memory.
    paper_orders = pd.read_csv(OUT / "historical_engine_orders.csv")
    paper_snap = pd.read_csv(OUT / "historical_engine_snapshots.csv")
    paper_risk = pd.read_csv(OUT / "historical_risk_parity.csv")
    quotes = pd.read_csv(OUT / "execution_quote_resolution_audit.csv")

    # Only after paper-side loading, load accepted Phase12C reference artifacts.
    reb = pd.read_csv(REF / "v2_rebalances.csv")
    ref_trades = pd.read_csv(REF / "v2_trades.csv")
    ref_pos = pd.read_csv(REF / "v2_positions.csv")
    ref_eq = pd.read_csv(REF / "v2_equity_curve.csv")
    reb.execution_date = reb.execution_date.astype(str)
    ref_pos.date = ref_pos.date.astype(str)
    ref_eq.date = ref_eq.date.astype(str)
    exec_dates = dict(zip(reb.rebalance_id, reb.execution_date))

    # State parity after every rebalance.
    state_rows = []
    for rr in reb.itertuples(index=False):
        rid, day = rr.rebalance_id, rr.execution_date
        rp = pos_map(ref_pos, day)
        ps = paper_snap[paper_snap.rebalance_id.eq(rid)]
        pp = {str(r.symbol): int(r.quantity) for r in ps.itertuples() if int(r.quantity) > 0}
        research_cash_rows = ref_eq[ref_eq.date.eq(day)]
        research_cash = float(research_cash_rows.iloc[-1].cash) if len(research_cash_rows) else 500000.0
        research_mv = float(research_cash_rows.iloc[-1].market_value) if len(research_cash_rows) else 0.0
        research_equity = float(research_cash_rows.iloc[-1].equity) if len(research_cash_rows) else research_cash
        paper_cash = float(ps.iloc[0].engine_cash) if len(ps) else 500000.0
        paper_equity = float(ps.iloc[0].engine_equity) if len(ps) else paper_cash
        paper_mv = paper_equity - paper_cash
        symbols_exact = set(rp) == set(pp)
        quantities_exact = symbols_exact and all(rp[k] == pp[k] for k in rp)
        cash_exact = abs(research_cash - paper_cash) <= TOL
        equity_exact = abs(research_equity - paper_equity) <= TOL
        state_rows.append({
            "rebalance_id": rid, "execution_date": day,
            "research_cash": research_cash, "paper_cash": paper_cash,
            "cash_difference": paper_cash - research_cash,
            "research_position_count": len(rp), "paper_position_count": len(pp),
            "research_symbols": "|".join(sorted(rp)), "paper_symbols": "|".join(sorted(pp)),
            "symbol_set_exact": symbols_exact, "quantities_exact": quantities_exact,
            "cash_exact": cash_exact, "equity_exact": equity_exact,
            "research_market_value": research_mv, "paper_market_value": paper_mv,
            "research_equity": research_equity, "paper_equity": paper_equity,
            "state_exact": symbols_exact and quantities_exact and cash_exact and equity_exact,
        })
    state_df = pd.DataFrame(state_rows)
    state_df.to_csv(OUT / "full_state_parity.csv", index=False)

    # Order parity from independently generated paper orders.
    e = ref_trades.groupby(["rebalance_id", "symbol"], as_index=False).first()
    a = paper_orders.groupby(["rebalance_id", "symbol"], as_index=False).first()
    keys = sorted(set(zip(e.rebalance_id, e.symbol)) | set(zip(a.rebalance_id, a.symbol)))
    order_rows = []
    for rid, sym in keys:
        er = e[(e.rebalance_id == rid) & (e.symbol == sym)]
        ar = a[(a.rebalance_id == rid) & (a.symbol == sym)]
        if not len(er):
            order_rows.append({"rebalance_id": rid, "symbol": sym, "expected_presence": False, "actual_presence": True, "result": "EXTRA_PAPER_ORDER"})
            continue
        if not len(ar):
            order_rows.append({"rebalance_id": rid, "symbol": sym, "expected_presence": True, "actual_presence": False, "expected_side": er.iloc[0].side, "expected_quantity": int(er.iloc[0].quantity), "result": "MISSING_PAPER_ORDER"})
            continue
        x, y = er.iloc[0], ar.iloc[0]
        side_ok, qty_ok = str(x.side) == str(y.side), int(x.quantity) == int(y.quantity)
        result = "EXACT" if side_ok and qty_ok else ("SIDE_MISMATCH" if not side_ok else "QUANTITY_MISMATCH")
        order_rows.append({"rebalance_id": rid, "symbol": sym, "expected_presence": True, "actual_presence": True, "expected_side": x.side, "actual_side": y.side, "expected_quantity": int(x.quantity), "actual_quantity": int(y.quantity), "result": result})
    order_df = pd.DataFrame(order_rows)
    order_df.to_csv(OUT / "full_order_parity.csv", index=False)

    # Fill parity. Actual paper prices/fees come only from paper output; reference is comparison-only.
    quote_used = {}
    for q in quotes.itertuples(index=False):
        if q.resolution_status == "USED":
            quote_used[(str(q.date), str(q.symbol), str(q.purpose))] = q
    fill_rows = []
    for r in ref_trades.itertuples(index=False):
        ar = paper_orders[(paper_orders.rebalance_id == r.rebalance_id) & (paper_orders.symbol == r.symbol)]
        day = exec_dates[r.rebalance_id]
        purpose = "entry" if r.side == "BUY" else "exit"
        q = quote_used.get((day, r.symbol, purpose))
        if q is None:
            q = quote_used.get((day, r.symbol, "retained_resize"))
        if not len(ar) or q is None:
            fill_rows.append({"rebalance_id": r.rebalance_id, "symbol": r.symbol, "result": "MISSING"})
            continue
        arow = ar.iloc[0]
        open_ok = abs(float(q.open) - float(r.reference_open)) <= TOL
        price_ok = abs(float(arow.price) - float(r.fill_price)) <= TOL
        fee_ok = abs(float(arow.fee) - float(r.transaction_cost)) <= TOL
        fill_rows.append({"rebalance_id": r.rebalance_id, "symbol": r.symbol, "expected_quantity": int(r.quantity), "actual_quantity": int(arow.quantity), "expected_open": float(r.reference_open), "actual_open": float(q.open), "expected_fill_price": float(r.fill_price), "actual_fill_price": float(arow.price), "expected_fee": float(r.transaction_cost), "actual_fee": float(arow.fee), "result": "EXACT" if int(arow.quantity)==int(r.quantity) and open_ok and price_ok and fee_ok else "MISMATCH"})
    pd.DataFrame(fill_rows).to_csv(OUT / "full_fill_parity.csv", index=False)

    # Accounting view uses the state comparison values; no performance metrics are calculated.
    state_df[["rebalance_id", "execution_date", "research_cash", "paper_cash", "research_market_value", "paper_market_value", "research_equity", "paper_equity", "research_position_count", "paper_position_count", "state_exact"]].to_csv(OUT / "full_accounting_parity.csv", index=False)

    # Quote coverage and fallback rows from actual resolver output.
    def quote_class(r):
        if r.source_used == "normalized_daily": return "normalized_daily_used"
        if r.source_used == "raw_provider": return "raw_provider_fallback_used"
        if r.resolution_status == "MISSING_AND_RETAINED": return "missing_exit_retained"
        if r.resolution_status == "ENTRY_SKIPPED_NON_EQ": return "entry_skipped_non_EQ"
        return "other"
    quotes["category"] = quotes.apply(quote_class, axis=1)
    quotes["rebalance_id"] = quotes.date.astype(str).map({v: k for k, v in exec_dates.items()})
    quotes[quotes.source_used.eq("raw_provider")].to_csv(OUT / "raw_provider_fallback_rows.csv", index=False)
    quotes.groupby("category", as_index=False).size().rename(columns={"size": "count"}).to_csv(OUT / "quote_resolution_summary.csv", index=False)

    risk_summary = paper_risk.groupby(["approved", "reason"], dropna=False, as_index=False).size().rename(columns={"size": "count"})
    risk_summary.to_csv(OUT / "risk_summary.csv", index=False)

    # Actual HATHWAY/TATACOMM extraction.
    ho = paper_orders[(paper_orders.rebalance_id == "SMV2-0030") & paper_orders.symbol.isin(["HATHWAY", "TATACOMM"])]
    hs = paper_snap[(paper_snap.rebalance_id == "SMV2-0029") & (paper_snap.symbol == "HATHWAY")]
    he = paper_snap[(paper_snap.rebalance_id == "SMV2-0030") & (paper_snap.symbol == "HATHWAY")]
    hq = quotes[(quotes.date == exec_dates["SMV2-0030"]) & (quotes.symbol == "HATHWAY") & (quotes.purpose == "exit")]
    hathway = {"rebalance_id": "SMV2-0030", "symbol": "HATHWAY", "starting_quantity": int(hs.iloc[0].quantity) if len(hs) else 0, "quote_source": hq.iloc[0].source_used if len(hq) else "", "series": hq.iloc[0].series if len(hq) else "", "execution_open": float(hq.iloc[0].open) if len(hq) else None, "actual_sell_quantity": int(ho[ho.side == "SELL"].iloc[0].quantity) if len(ho[ho.side == "SELL"]) else 0, "ending_quantity": int(he.iloc[0].quantity) if len(he) else 0, "tatacomm_buy_quantity": int(ho[(ho.symbol == "TATACOMM") & (ho.side == "BUY")].iloc[0].quantity) if len(ho[(ho.symbol == "TATACOMM") & (ho.side == "BUY")]) else 0}
    pd.DataFrame([hathway]).to_csv(OUT / "hathway_regression.csv", index=False)

    # First divergence trace only if an actual mismatch exists.
    bad = state_df[~state_df.state_exact]
    first = bad.iloc[0] if len(bad) else None
    if first is None:
        pd.DataFrame(columns=["rebalance_id", "execution_date", "first_differing_event", "reason"]).to_csv(OUT / "first_divergence_trace.csv", index=False)
    else:
        pd.DataFrame([first.to_dict()]).to_csv(OUT / "first_divergence_trace.csv", index=False)

    manifest = {
        "phase12b_hash": "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f",
        "phase12c_build": "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb",
        "paper_output_manifest": "authoritative_paper_output_manifest.json",
        "rebalances_compared": int(len(state_df)),
        "state_exact": int(state_df.state_exact.sum()),
        "order_exact": int((order_df.result == "EXACT").sum()),
        "fill_exact": int((pd.read_csv(OUT / "full_fill_parity.csv").result == "EXACT").sum()),
        "post_boundary_performance_inspected": False,
        "reference_loaded_after_paper_generation": True,
    }
    (OUT / "authoritative_parity_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "authoritative_parity_report.md").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
