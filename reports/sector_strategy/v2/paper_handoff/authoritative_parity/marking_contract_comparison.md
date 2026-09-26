# Marking contract comparison

| Rule | Accepted Phase12C research | Paper before repair | Paper after repair |
|---|---|---|---|
| Normalized close precedence | Used when valid | Used when valid | Used when valid |
| Raw-provider close fallback | Used when normalized row is absent and EQ/BE close is supported | Missing-row path carried prior mark | Used for supported EQ/BE close |
| Held BE valuation | Supported through raw-provider fallback | Not applied to EOD marks | Applied in V2-specific mark resolver |
| No valid close | Carry previous mark | Carry previous mark | Carry previous mark |

For REFEX on 2024-10-07, the normalized row is absent and the certified raw row is BE with close ₹516.50. The prior paper path carried ₹562.70 from the preceding mark. The repair changes only end-of-session valuation marking; execution quote resolution and order generation are unchanged.
