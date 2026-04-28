#!/bin/bash

cd references

# 1. VRC v2.3 archive
cat > vrc-v2-3-archive.md << 'EOF'
# VRC v2.3 Severity Classification (Immunefi)

CRITICAL:
- Direct theft of user funds
- Direct theft of protocol funds
- Permanent freezing of funds

HIGH:
- Theft requiring conditions (flash loan, oracle manipulation, etc.)
- Permanent freezing requiring conditions
- Protocol insolvency

MEDIUM:
- Griefing (no profit to attacker, DoS, etc.)
- Temporary freezing

LOW:
- Contract fails to deliver promised returns (yield farming, staking)

INFORMATIONAL:
- Theoretical bugs with no funds at risk today

KEY RULES:
- Admin/multisig abuse → OOS or Low (not Critical)
- Feasibility limits downgrade severity
- PoC required (no PoC = auto-reject)
EOF

# 2. Gate-7 detail
cat > gate-7-detail.md << 'EOF'
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
EOF

# 3. Known rejections
cat > known-rejections.md << 'EOF'
# Known Immunefi Rejections (User History)

KAST F1: [details]
KAST F2: [details]  
KAST F5: [details]
Adevar L02: Active manager redirect is by-design

PATTERN: Theoretical bugs without current TVL → rejected
LESSON: Mainnet state verification mandatory
EOF

# 4. Whirlpools active hypotheses
cat > whirlpools-active-hypotheses.md << 'EOF'
# Whirlpools Active Hypothesis Stack

TARGET: orca-so/whirlpools
PROGRAM: whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc  
TVL: $400M (Orca total)
BOUNTY: $500K max

TOP HYPOTHESES:
H1: fee_growth_checkpoint desync (KyberSwap pattern)
H2: tick array sparse swap uninitialized replacement
H3: adaptive fee skip volatility_reference stale
H4: two-hop vault shared state
H5: position reset_range orphaning

DEAD VECTORS: [9 adaptive fee vectors already checked]
EOF

# 5. Post-mortems to mine
cat > post-mortems-to-mine.md << 'EOF'
# Historical Solana Exploits for Pattern Matching

Wormhole ($325M): guardian_set not validated
Cashio ($52M): collateral_mint not validated
Crema ($9M): tick_array missing has_one
KyberSwap ($48M): fee_growth_checkpoint desync
Mango ($116M): oracle manipulation
Nirvana ($3.5M): precision loss in price calculation
OptiFi ($661K): close_account error ignored
Loopscale ($300K): PDA seed collision

[Full post-mortems in solana-exploits-forensics skill]
EOF

# 6. Mythos loop detail
cat > mythos-loop-detail.md << 'EOF'
# Anthropic Mythos Scaffold (April 2026)

SOURCE: red.anthropic.com/2026/mythos-preview

RECIPE:
1. Container with project source + run/debug
2. Minimal prompt: "Find a security vulnerability"
3. Loop: read → hypothesize → run → confirm/reject → iterate
4. Parallel runs (1000 runs for OpenBSD)
5. Per-file agent assignment
6. Bug-likelihood ranking

RESULTS:
- OpenBSD CVE-2024-XXXX (memory corruption)
- Cost: ~$20K (1000 runs × $20/run)
- False positive rate: <5%

WE ADD:
- Bandit (money-first)
- Assumption-breaker (invert safety claims)
- Gate-7 (filter before submit)
EOF

# 7. Assumption-breaker playbook
cat > assumption-breaker-playbook.md << 'EOF'
# Assumption-Breaker Playbook

"overflow safe because checked_add" → find wrapping_sub/unchecked
"authority-gated" → find CPI caller bypass
"tick validated" → find uninitialized sparse array
"fee_growth_checkpoint prevents double-claim" → find skip path
"position liquidity can't go negative" → find two-instruction race

METHOD: Extract "safe because X", attack X
EOF

# 8-12. Other references (shorter versions for space)
for ref in file-bug-likelihood-ranking learned-patterns output-format changelog; do
cat > $ref.md << EOF
# ${ref//-/ }

[Reference content for $ref]
EOF
done

echo "All references created"
