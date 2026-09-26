# Execution sequence comparison

Research V2 retries pending exits, executes deselection sells, updates cash, conditionally resizes retained positions outside the 2pp band, then opens signal-frozen entries with cash clipping, and finally marks closes.

Phase13B computed exits and processed them before buys, but retained-position detection used the wrong portfolio key. It consequently treated retained target names as absent, submitted new full-size BUY requests, and relied on RiskManager rejection rather than research-style cash clipping. This is the first structural divergence; generic OrderManager, PaperBroker, and Portfolio sequencing was not the cause.
