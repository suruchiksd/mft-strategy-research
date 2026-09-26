# Prospective signal runbook

1. At each final NSE session of the ISO week, generate the V2 target-state file from complete EOD inputs.
2. Record source-data hash, strategy preregistration hash, build reference, generation timestamp, and signal hash.
3. Submit the frozen target state to the paper-engine adapter.
4. Permit orders only from the next valid session open; retry exits without deleting unavailable holdings.
5. Reconcile intended orders, actual fills, positions, cash, costs, and exceptions daily.
6. Observe for 8–12 weeks after 2026-09-17. Do not calculate retrospective returns for this handoff.
