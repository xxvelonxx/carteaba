# Gate-7 Detailed Checks

CHECK 1 — Mainnet State Verification
WHY: VRC "no verifiable funds at risk" = Informational max
HOW: `solana account <addr>` CLI, verify config exists
FAIL: Config nonexistent → BLOCK

CHECK 2 — Numeric Verification  
WHY: Griefing-only = Medium max per VRC
HOW: profit = stolen - fees - gas - slippage
FAIL: profit <= 0 → BLOCK

CHECK 3 — Defense Red-Team
WHY: Known issue = auto-reject
HOW: Run test suite, check if catches bug
PASS: Test missing → real bug
FAIL: Test catches → explain prod difference or BLOCK

CHECK 4 — VRC Severity Calibration
WHY: Misclassified severity = triager friction
HOW: Apply VRC v2.3 honestly
ADJUST: Admin abuse → OOS, feasibility → downgrade

CHECK 5 — PoC Completeness
WHY: Immunefi requires PoC
HOW: Executable code + before/after balances
FAIL: Pseudocode → BLOCK

CHECK 6 — Known Issue Check
WHY: Duplicate = auto-reject
HOW: Search project repo + past audits
FAIL: Found in test suite → BLOCK

CHECK 7 — Submission Quality
WHY: Poor quality = triager waste
HOW: Clear title, no hedge-words, accurate impact
FAIL: AI language ("potential", "if confirmed") → BLOCK
