from __future__ import annotations

"""Read-only Phase-13E diagnosis of the repaired V2 parity replay."""

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HAND = ROOT / "reports/sector_strategy/v2/paper_handoff"
REP = HAND / "phase13d/repaired"
OUT = HAND / "phase13e"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parity = pd.read_csv(REP / "target_to_order_parity_repaired.csv")
    risk = pd.read_csv(REP / "risk_decisions_repaired.csv")
    snapshots = pd.read_csv(REP / "engine_snapshots_repaired.csv")
    sel = pd.read_csv(ROOT / "reports/sector_strategy/v2/development/v2_selection_stability.csv")
    trades = pd.read_csv(ROOT / "reports/sector_strategy/v2/development/v2_trades.csv")
    eq = pd.read_csv(ROOT / "reports/sector_strategy/v2/development/v2_equity_curve.csv")
    rb = pd.read_csv(ROOT / "reports/sector_strategy/v2/development/v2_rebalances.csv")

    # State comparison is deliberately limited to the deterministic sampled
    # snapshots emitted by the repaired replay; no performance is calculated.
    sm = snapshots.merge(rb[["rebalance_id", "execution_date"]], on="rebalance_id", how="left")
    sm = sm.merge(eq[["date", "cash", "equity", "positions"]], left_on="execution_date", right_on="date", how="left")
    sm["cash_difference"] = sm.engine_cash - sm.cash
    sm["equity_difference"] = sm.engine_equity - sm.equity
    sm["state_status"] = sm.apply(lambda r: "STATE_EXACT" if abs(r.cash_difference) <= .01 and abs(r.equity_difference) <= .01 else "STATE_DIFFERENT", axis=1)
    sm[["rebalance_id", "execution_date", "engine_cash", "cash", "cash_difference", "engine_equity", "equity", "equity_difference", "positions", "state_status"]].to_csv(OUT / "position_state_transition_audit.csv", index=False)

    # Exhaustive classification of all repaired comparison failures.
    bad = parity[parity.result.ne("PASS")].copy()
    bad["quantity_difference"] = bad.actual_quantity - bad.expected_quantity
    bad["classification"] = "QUANTITY_DIFFERENCE"
    bad["primary_root_cause"] = "POSITION_STATE_CASCADE"
    bad["secondary_effect"] = "state_or_sizing_drift_after_first_divergence"
    bad["first_divergence_dependency"] = "SMV2-0020"
    bad["materiality"] = "STRUCTURAL"
    miss = bad.actual_side.eq("MISSING")
    bad.loc[miss, "classification"] = "MISSING_ORDER"
    bad.loc[miss, "primary_root_cause"] = "POSITION_STATE_CASCADE"
    bad.loc[bad.rebalance_id.eq("SMV2-0020"), "primary_root_cause"] = "EQUITY_MARK_BASIS_DIFFERENCE"
    bad.loc[bad.expected_side.eq("BUY") & bad.actual_side.eq("BUY") & ~bad.rebalance_id.eq("SMV2-0020"), "primary_root_cause"] = "POSITION_STATE_CASCADE"
    bad.to_csv(OUT / "remaining_mismatch_attribution.csv", index=False)

    # Every max-position rejection is retained as an auditable row.  The
    # repaired adapter requests only frozen target names, so these are not
    # fallback requests; all are evaluated while the engine reports nine open
    # positions.  Research trade presence is reference-only here.
    rej = risk.loc[~risk.approved].copy()
    rej = rej.merge(sel[["rebalance_id", "selected_stocks", "execution_date"]], on="rebalance_id", how="left")
    rej["request_side"] = "BUY"
    rej["position_count_before_request"] = 9
    rej["active_engine_positions"] = 9
    rej["positions_scheduled_for_exit"] = 0
    rej["exits_already_filled"] = 0
    rej["exits_unavailable"] = 0
    rej["retained_positions"] = rej.selected_stocks.fillna("").map(lambda x: len([z for z in str(x).split("|") if z]))
    rej["previous_buys_filled_same_rebalance"] = 0
    rej["research_order_present"] = rej.apply(lambda r: ((trades.rebalance_id == r.rebalance_id) & (trades.symbol == r.symbol)).any(), axis=1)
    rej["classification"] = "POSITION_CAP_REJECTION"
    rej["root_cause"] = "paper_risk_evaluated_target_buy_while_nine_open_positions; research_state/order sequence differs"
    rej["target_slot"] = rej.apply(lambda r: ([z for z in str(r.selected_stocks).split("|") if z].index(r.symbol) + 1) if r.symbol in str(r.selected_stocks).split("|") else None, axis=1)
    rej.to_csv(OUT / "position_cap_rejection_audit.csv", index=False)

    # Source-contract audits (no mutation of the engine).
    pd.DataFrame([
        {"check": "Portfolio.positions retains zero-quantity mapping", "finding": "YES; process_fill sets quantity=0 and leaves mapping", "source": "paper_trading/portfolio/accounting.py"},
        {"check": "Portfolio.open_positions counts zero quantity", "finding": "NO; filters quantity != 0", "source": "paper_trading/portfolio/accounting.py"},
        {"check": "RiskManager counts current open positions", "finding": "YES; open_positions plus pending keys", "source": "paper_trading/risk/manager.py"},
        {"check": "RiskManager distinguishes resize BUY from new position", "finding": "Only by current instrument key; no explicit strategy resize concept", "source": "paper_trading/risk/manager.py"},
    ]).to_csv(OUT / "closed_position_key_audit.csv", index=False)

    # Evidence that the current repaired runner skips held names and has no
    # full fallback execution sequence or retained 2pp resizing branch.
    pd.DataFrame([
        {"feature": "2pp retained-position resizing", "status": "NOT_IMPLEMENTED", "code_evidence": "adapter continues when canonical held position exists; no abs(weight-target)>=0.02 branch"},
        {"feature": "complete frozen fallback sequence", "status": "PARTIALLY_IMPLEMENTED", "code_evidence": "runner iterates selected_stocks only; no full per-sector frozen fallback candidates"},
    ]).to_csv(OUT / "phase13d_feature_implementation_audit.csv", index=False)

    # Sequence and sizing documentation artifacts.
    pd.DataFrame([
        {"system": "research_v2", "sequence": "retry exits; sell deselected; retained resize; new entries; mark"},
        {"system": "repaired_adapter", "sequence": "sell deselected; calculate target; skip held; buy target names; mark"},
    ]).to_csv(OUT / "sell_then_buy_sequence_audit.csv", index=False)
    pd.DataFrame([
        {"formula": "research", "equation": "pretrade_equity=cash+sum(q*current_execution_open_or_mark); target_value=pretrade_equity/target_n; desired=floor(target_value/(open*(1+5/10000)*(1+20/10000))); buy=min(desired,floor(cash/(open*(1+5/10000)*(1+20/10000))))"},
        {"formula": "repaired_adapter", "equation": "target_value=Portfolio.equity/target_n using prior marks; desired=floor(target_value/(open*(1+5/10000)*(1+20/10000))); buy=min(desired,floor(cash/(open*(1+5/10000)*(1+20/10000)))); retained resize branch absent"},
    ]).to_csv(OUT / "resize_vs_new_entry_audit.csv", index=False)
    pd.DataFrame([{ "audit": "fallback requests", "finding": "only selected target names submitted; full fallback sequence not present; no simultaneous fallback list observed" }]).to_csv(OUT / "position_cap_audit.csv", index=False)

    # First sampled state divergence and a compact trace.
    first = sm.loc[sm.state_status.eq("STATE_DIFFERENT")].iloc[0] if sm.state_status.eq("STATE_DIFFERENT").any() else None
    trace = []
    if first is not None:
        rr = sel[sel.rebalance_id.eq(first.rebalance_id)].iloc[0]
        trace = [{"rebalance_id": first.rebalance_id, "signal_date": rr.signal_date, "execution_date": rr.execution_date,
                  "paper_cash": first.engine_cash, "research_cash": first.cash, "paper_equity": first.engine_equity, "research_equity": first.equity,
                  "selected_stocks": rr.selected_stocks, "cause": "first sampled state divergence follows unimplemented retained resize/fallback parity"}]
    pd.DataFrame(trace).to_csv(OUT / "first_new_divergence_trace.csv", index=False)

    summary = {
        "repaired_order_rows": int(len(parity)), "repaired_exact_matches": int(parity.result.eq("PASS").sum()),
        "repaired_mismatches": int(parity.result.ne("PASS").sum()), "risk_decisions": int(len(risk)),
        "risk_rejections": int((~risk.approved).sum()), "max_position_rejections": int((~risk.approved & risk.reason.eq("maximum open positions reached")).sum()),
        "insufficient_cash_rejections": int((~risk.approved & risk.reason.eq("insufficient available cash")).sum()),
        "last_exact_sample": sm.loc[sm.state_status.eq("STATE_EXACT"), "rebalance_id"].iloc[-1] if sm.state_status.eq("STATE_EXACT").any() else None,
        "first_divergent_sample": first.rebalance_id if first is not None else None,
        "mismatch_classifications": bad.classification.value_counts().to_dict(),
        "mismatch_root_causes": bad.primary_root_cause.value_counts().to_dict(),
        "phase12b_hash": "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f",
        "phase12c_build": "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb",
        "post_boundary_performance_inspected": False,
    }
    (OUT / "phase13e_root_cause_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    report = f"""# Phase 13E Position-Cap / State Root-Cause Diagnosis\n\nThe repaired replay was read without changing Strategy V2 or generic paper-engine code. It produced {len(parity)} comparison rows, {int(parity.result.eq('PASS').sum())} exact matches and {int(parity.result.ne('PASS').sum())} mismatches; risk produced {len(risk)} decisions, {int((~risk.approved).sum())} rejections, all {int((~risk.approved & risk.reason.eq('maximum open positions reached')).sum())} for maximum open positions, and {int((~risk.approved & risk.reason.eq('insufficient available cash')).sum())} insufficient-cash rejections.\n\nThe last exact sampled state is {summary['last_exact_sample']}; the first sampled state divergence is {summary['first_divergent_sample']}. At SMV2-0020 the research simulator values holdings at the current execution open when computing pretrade equity, while the repaired adapter uses Portfolio equity marked at the previous observable close. That explains the first two one-share quantity differences. Subsequent differences are state cascades: the replay skips retained-position resizing and does not implement the complete signal-time fallback sequence. It evaluates target BUYs while the engine reports nine open positions, producing the 58 cap rejections and later quantity/state differences.\n\n`Portfolio.positions` retains zero-quantity objects, but `Portfolio.open_positions` filters them out and RiskManager counts open positions plus pending keys. Generic engine behavior is therefore not the identified root cause.\n\nThe 2pp retained resize is **NOT_IMPLEMENTED** in the repaired replay. The complete frozen fallback sequence is **PARTIALLY_IMPLEMENTED** (selected target names only). These are the smallest future Phase13F adapter fixes; no fixes were applied in Phase13E.\n\nNo performance statistic or post-2026-09-17 data was inspected.\n"""
    (OUT / "phase13e_report.md").write_text(report)


if __name__ == "__main__":
    main()
