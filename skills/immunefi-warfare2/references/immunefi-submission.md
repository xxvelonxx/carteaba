# Immunefi Submission — VRC v2.3, Severity Rules, Auto-Rejections

This file encodes the bounty submission process: what counts, what doesn't, how to write the report, how to handle triage. Calibrated to Immunefi's Vulnerability Rating Categorization (VRC) v2.3 as of 2026.

If your finding is rejected, it's almost always because of one of the rules in this file.

---

## VRC v2.3 — Severity Definitions

### Critical
- **Direct theft of any user funds**, on-chain, with no further conditions
- Direct loss of governance / control of the protocol
- Permanent freezing of funds (no recovery path)
- Insolvency: protocol's outstanding obligations exceed its reserves

**Example:** A swap handler that lets attacker set `min_amount_out = 0` and the math has a path that returns less than 0.99% of fair output → drains all liquidity providers proportionally.

**Bounty cap typical:** 5–10% of TVL, capped at the program's max (e.g., $500K for Whirlpools, $1M for Kamino, $2.5M for some larger protocols).

### High
- Theft of yield (fees, rewards) only, not principal
- Temporary freezing of funds (recovery requires admin action)
- Theft requiring a specific market condition (e.g., user must do X first)
- Block-stuffing or rate-limiting an essential function (e.g., liquidations) for a meaningful duration

**Bounty cap typical:** $50K–$200K depending on TVL and program.

### Medium
- Griefing: protocol functions slow / fail / produce sub-optimal results, no funds stolen
- Theft of dust amounts (< 1% of any user's holdings)
- DoS of non-essential functions

**Bounty cap typical:** $5K–$25K.

### Low
- Optimization issues
- Code clarity that could lead to future bugs
- Issues that require unrealistic preconditions

**Bounty cap typical:** $500–$5K.

### Informational
- Notes for the team that don't constitute a current vulnerability
- Patterns that should be improved but aren't currently exploitable

**Bounty cap typical:** $0–$500.

---

## What gets auto-rejected (memorize this)

These are reasons Immunefi triagers close findings without engaging the team:

### A. No proof of concept

**Rule:** Submissions without a working PoC that demonstrates the exploit on the actual deployed code are auto-rejected.

A PoC must:
- Run against the actual mainnet program ID (or a fresh deployment of the same bytecode hash)
- Show the actual unauthorized state change (token balance moved, account modified, mint without backing, etc.)
- Be reproducible by the triager (provide all account addresses, transaction signatures, or test code)

**Not a PoC:**
- "Looking at the code, attacker could do X"
- A snippet of code with comments explaining the bug
- A diff showing the proposed fix
- A theoretical analysis of how the bug could be exploited
- An exploit on a different version / branch / unrelated program

**Is a PoC:**
- A `litesvm` or `solana-program-test` test that initializes the protocol from scratch, executes the attack, and asserts the unauthorized state change
- A devnet transaction signature showing the attack working
- (Rare and risky) a mainnet transaction — only if you're sure it's not actually exploiting users; bug bounty programs explicitly prohibit mainnet exploits

### B. Out-of-scope code

**Rule:** Programs not listed in the bounty scope, or commits/branches not deployed to mainnet, are out-of-scope.

The bounty scope is on the Immunefi page for that program. Read it before submitting:
- Specific program IDs covered
- Specific commits / tags covered
- Specific networks (mainnet only? devnet too?)
- Specific assets covered (might exclude wrapped tokens, governance tokens, etc.)

If you find a bug in a `feat/new-feature` branch that hasn't been deployed, it's OOS regardless of severity.

### C. Known issues

**Rule:** Issues already reported, already known to the team, or fixed in a deployed version are OOS.

Sources of "known":
- The protocol's own GitHub issues
- Public disclosure on Twitter, Discord, audit reports
- Existing Immunefi reports (if duplicated, only the earliest gets paid; you may not even know about earlier reports)
- The program's own test suite — if a test exists for the case, the team knows
- Discussion in the project's docs

**Audit pattern:** before submitting, search:
```bash
# Project's GitHub
gh issue list --search "<bug keyword>" --repo <project>

# Project's audit reports (Sec3, OtterSec, Neodyme, Halborn, Trail of Bits)
# Usually linked from project README or website

# Twitter for "[ProjectName] vulnerability"
# Discord announcements channel

# Existing test cases
rg "<bug pattern>" --include='*.rs' tests/
```

### D. Admin-key abuse / centralization issues

**Rule:** "If admin is malicious, X happens" is OOS unless the action is unintended.

Examples:
- "Admin can change fee_rate to 100%" → OOS (intended)
- "Admin can change fee_rate to 100% via a non-fee-related function" → in scope (unintended capability)
- "Admin can rugpull by removing all liquidity" → OOS (governance / intended)
- "Multisig threshold is 2-of-3" → OOS (centralization)

**Border cases:**
- Admin can do X via Y when Y was supposed to only allow Z → in scope
- Admin can lock funds permanently with no recovery → in scope (unintended)
- Admin can read encrypted user data when access was supposed to require user signature → in scope

### E. Theoretical bugs without funds-at-risk

**Rule:** A bug is exploitable IFF funds can be lost / locked / stolen TODAY on the deployed program with current state.

Examples:
- "If admin sets max_volatility = 0, swaps fail" → admin issue, OOS
- "If a config is set to X (not the current value), Y becomes possible" → not exploitable today, Informational at best
- "After 100 years of fee accrual, fee_growth_global will overflow" → time-bounded, may be Low or Informational
- "If two specific keys are reused across protocols (which is unlikely), Z" → preconditional, depends on plausibility

The standard: "What unauthorized state change happens when I run this PoC against the live program right now?" If "nothing", the bug is theoretical.

### F. Front-running / MEV (without specific protocol design issue)

**Rule:** Generic MEV (sandwich attacks, arbitrage, JIT liquidity) on AMMs is OOS — they're a market reality, not a vulnerability.

In scope:
- Mev that exploits a SPECIFIC bug (e.g., a sandwich that triggers an oracle race condition)
- Mev that bypasses a stated MEV protection (e.g., the protocol claims to prevent sandwich, but a specific path doesn't)
- JIT liquidity that exploits a fee accounting bug

OOS:
- "Attacker can sandwich large swaps" (any AMM is sandwichable)
- "Liquidity providers can be front-run" (without specific bug)
- "MEV searchers profit from this protocol" (yes, that's MEV)

### G. Governance / DAO actions

If the protocol is governed by a DAO and the DAO can vote to do X, that's intended. Even if X harms users.

Exception: if the DAO mechanism itself has a bug (vote counting wrong, quorum bypassable, etc.).

### H. Issues in dependencies

If the bug is in `anchor-lang` itself, or `solana-program`, or any dependency, report to that project, not via the target's bounty.

Exception: if the target uses the dependency in a way that introduces the bug (e.g., calls a deprecated function with known vulnerability).

---

## Severity downgrade rules

Triagers will downgrade severity if any of these apply:

### Feasibility limitations downgrade

A Critical bug that requires:
- 10+ on-chain transactions in sequence with very specific timing → Medium / High
- Privileged signer (e.g., need to be a delegate of the position) → depends on how easy to become that signer
- Rate-limited execution (max 1/block) → may downgrade if attack requires many iterations
- Specific market state (e.g., volatility above threshold) → depends on frequency of that state

Document the feasibility honestly. Inflated severity gets called out and damages your reputation.

### Funds-at-risk bound

A bug where the maximum loss is X% of TVL might downgrade based on X:
- Drains 100% → Critical
- Drains specific positions only (e.g., requires victim to interact) → varies
- Drains 0.1% per call but rate-limited → adds up to limited amount, may be Medium

### Pre-condition difficulty

If the attack requires the attacker to first deposit a large amount (locking capital):
- Capital locked < $10K → no downgrade
- Capital locked $10K–$1M → may downgrade by one tier if recovery isn't guaranteed
- Capital locked > $1M → significant downgrade unless attack is repeatable

---

## What makes a Critical findings actually paid

Beyond severity, triagers check:
1. **Did the protocol implement Immunefi's safe-disclosure process?** Yes — payment likely.
2. **Is the team responsive?** Some teams take 30+ days to respond.
3. **Was the bug fixed quickly?** If yes, payment usually within 30 days of fix.
4. **Are there competing reports?** Earliest timestamp wins.
5. **Did you exploit on mainnet first?** Disqualifies — bounty programs require disclosure before exploitation.

---

## Prior art via hash + sign + timestamp

For findings on code that's structural (not currently exploitable but will be once a config change happens), use prior art:

1. Compute SHA256 of the finding write-up
2. Sign the hash with your wallet's keypair
3. Submit the hash + timestamp to a public chain (commit a tx with the hash in memo)
4. Keep the original write-up private

If the bug becomes exploitable later (e.g., config changes), you can prove you knew about it first by:
- Showing the original write-up
- Showing the on-chain hash that matches
- Showing the timestamp predates the deployment

This protects you from "we already knew" disputes.

**Whirlpools/Kamino specific:** prior art is a legitimate strategy for structural bugs in code paths that aren't currently active (e.g., a feature behind a flag that's not yet enabled). Don't submit immediately; wait for the deployment, then submit with prior art.

---

## Submission template

Use exactly this structure:

```markdown
# Title: <one-line description, technical>

## Summary
<2-3 sentence explanation of the bug, no preamble>

## Severity
Critical | High | Medium | Low | Informational

Justification: [VRC v2.3 category and why]

## Scope
- Program ID: <mainnet program ID>
- Branch / Commit: <git SHA>
- Bytecode hash: <output of `cargo build-sbf` deployed binary hash>

## Vulnerability Details

### Root cause
<1-2 paragraphs explaining the exact bug, with file:line references>

### Attack flow
1. Attacker prepares: <what state must hold before attack>
2. Attacker calls: <instruction with specific arguments>
3. The handler does: <what code path triggers>
4. Result: <unauthorized state change>

### Code reference
[link to specific file:line in the deployed commit]

```rust
// vulnerable code, with comments showing where the bug is
```

## Impact

Maximum loss: <specific amount in USD or % of TVL>
Affected users: <specific or all>
Recovery possible: <yes / no / partial>

## Proof of Concept

[link to PoC repo or inline test code]

```rust
// litesvm or solana-program-test code that demonstrates the attack
```

Output:
```
[expected output showing the attack succeeds]
```

## Recommended Fix

<specific code change, ideally as a diff>

```diff
- vulnerable line
+ fixed line
```

## References

- [link to similar past exploit if applicable]
- [link to relevant audit report if relevant]

```

This format is what triagers expect. Deviation = friction, friction = delays.

---

## Communication with triagers

- Be technical, not adversarial. Triagers see hundreds of submissions; rude ones get less attention.
- Respond to questions within 24h if possible. Slow responses signal disengagement, which can lead to the report being closed.
- Do NOT publicly disclose before payment / fix. Even subtle hints on Twitter can void the bounty.
- If you disagree with a severity downgrade, push back ONCE with new evidence. Don't repeat the same argument; it's not persuasive.
- If the team disputes the bug, ask them specifically what part of the PoC they think is wrong. Often there's a misunderstanding about state preconditions.

---

## Building credibility

Bug bounty hunting compounds. After 3-5 paid findings on Immunefi, your reputation tier increases:
- Triagers look at your reports faster
- You get private invitations to closed bounties (often 2-5x payouts)
- Teams may consult you on architectural questions (paid)

Reputation damage:
- Submitting AI-generated reports without verification → fastest way to lose credibility
- Submitting low-quality "code smell" reports as Critical → trustworthiness drops
- Public criticism of the protocol after a finding is paid → you'll be blacklisted

---

## Specific Solana bounty programs (typical caps as of 2026)

| Protocol | Program | Critical Cap | KYC Required |
|---|---|---|---|
| Whirlpools (Orca) | whirLb... | $500K | No |
| Orca xORCA | StaKE... | $500K | No |
| Kamino Lending | KLend... | $1M | Yes (>$50K) |
| MarginFi | MFv2h... | $500K | Yes |
| Drift | dRiftyHA... | $500K | Yes |
| Jito | (multiple) | $1M+ | Yes (>$50K) |
| Light Protocol | (multiple) | $50K | No |
| Sanctum | SP... | $500K | Yes |
| Marinade | MarBmsS... | $250K | Yes |
| Pyth | (multiple) | $500K | Yes |
| Solend | So1end... | $500K | Yes |
| Save (formerly Solend) | (same) | $500K | Yes |
| Phoenix | PhoeNix... | $250K | No |

KYC implications: if KYC is required, you cannot submit anonymously. Some hunters maintain KYC'd and non-KYC'd identities.

Always check the actual Immunefi page for current caps and rules; this list ages.

---

## Solana-specific submission tips

1. **Include the program ID and bytecode hash explicitly.** Solana programs have addresses and bytecode hashes; not including these makes verification harder.
2. **Specify the cluster.** Mainnet-beta only, devnet, testnet — they're separate deployments.
3. **Provide RPC endpoint or block range** for any on-chain proof. Triagers may not have access to your private RPC.
4. **For PoC: prefer litesvm**. It's the standard test framework now (replaced solana-program-test in many projects). Ensure your PoC is one `cargo test` away from running.
5. **Include compute unit usage.** Solana has CU limits per transaction (1.4M); if your attack requires more CU, it may not be feasible.
6. **Account size constraints.** Solana account sizes are bounded; some attacks that work for "any size" actually fail at the 10MB limit.

---

## When to NOT submit

- The bug requires an attacker to lose money first (e.g., griefing themselves)
- The exploitation cost > the gain (high-CU attack on low-TVL pool)
- Already widely known (recent audit report mentioned it)
- The bug is in dead code (unused branch, deprecated function not called by any handler)
- The bug is a code smell, not a behavior change (refactoring suggestion, not a vulnerability)

If the report would be Informational or Low and the program's bounty for those is $0–$500, the time investment may not be worth it. Focus on Medium+.

Exception: if you're new to bug bounty, even Informational reports build relationships with teams and demonstrate competence to triagers.
