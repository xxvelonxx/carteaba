# Assumption-Breaker Playbook

"overflow safe because checked_add" → find wrapping_sub/unchecked
"authority-gated" → find CPI caller bypass
"tick validated" → find uninitialized sparse array
"fee_growth_checkpoint prevents double-claim" → find skip path
"position liquidity can't go negative" → find two-instruction race

METHOD: Extract "safe because X", attack X
