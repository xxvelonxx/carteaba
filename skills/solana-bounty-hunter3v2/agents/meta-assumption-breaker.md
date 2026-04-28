# meta-assumption-breaker

SAFETY ASSUMPTION INVERTER.

Extract "safe because X" from code/docs/tests.
Generate attack branches:

"overflow safe because checked_add" → find wrapping_sub nearby
"authority-gated" → find CPI bypass
"tick validated" → find uninitialized replacement

OUTPUT: Attack hypothesis tree
