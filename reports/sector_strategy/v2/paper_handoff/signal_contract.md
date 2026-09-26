# Sector Momentum V2 paper signal contract

Schema version: `SECTOR_MOMENTUM_V2_SIGNAL_V1`. Research emits target state and frozen replacement order only. The paper engine owns orders, fills, risk, positions, cash, costs, P&L, and reconciliation. Signals are eligible only at the next valid session open; no same-close execution or post-signal reranking is permitted.

No prospective performance is calculated by this handoff.
