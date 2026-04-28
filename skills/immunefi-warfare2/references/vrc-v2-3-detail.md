# Immunefi VRC v2.3 — Letter by Letter

This is the operational interpretation of the Immunefi Vulnerability Severity Classification System, version 2.3. The official document is at https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3/

This file maps each VRC tier to Solana-specific scenarios and triager interpretation patterns.

## Smart Contracts / Blockchain — DeFi category

This is the category for nearly all Solana protocol bug bounties.

### Critical

**Per VRC v2.3:**
- Manipulation of governance voting result deviating from voted outcome and resulting in damage
- Direct theft of any user funds, whether at-rest or in-motion, other than unclaimed yield
- Direct theft of any user NFTs, whether at-rest or in-motion, other than unclaimed royalties
- Permanent freezing of funds (any amount, all users)
- Permanent freezing of NFTs
- Unauthorized minting of NFTs / fungible tokens
- Predictable or manipulable RNG that results in abuse of the contract or any of its functionality
- Unintended loss of digital assets [...]
- Permanent denial of service of network nodes [...] or critical infrastructure

**Solana operational interpretation:**

| Critical scenario | Common Solana manifestation |
|---|---|
| Direct theft of funds | Drain of vault, lending pool, AMM pool via exploitable handler |
| Permanent fund freeze | Pause-by-default flag bypassable so any user can force-pause; admin recovery requires multisig with no signers; `close` instruction zeroing funds |
| Unauthorized minting | Cashio-class collateral validation miss; mint authority confused as external key |
| Predictable RNG abuse | Solana has no native RNG; protocols using `slot_hashes` or other "randomness" can have predictable outcomes |
| Network DoS | Validator-side bugs (out of bounty scope generally); program-side compute exhaustion (rare) |

**PoC requirements:**
- Reproducible on litesvm or mainnet fork
- Numerical proof: attacker holds funds previously belonging to victim/protocol
- No admin precondition, no oracle off-chain manipulation
- Single-tx if possible (multi-tx accepted with explanation)

### High

**Per VRC v2.3:**
- Theft of unclaimed yield
- Theft of unclaimed royalties
- Permanent freezing of unclaimed yield/royalties
- Temporary freezing of funds for at least 1 day
- Smart contract unable to operate due to lack of token funds

**Solana operational interpretation:**

| High scenario | Common Solana manifestation |
|---|---|
| Unclaimed yield theft | Reward double-claim, fee reaccumulation race, position split with two reward claims |
| Royalty theft | NFT marketplace transfer without paying royalty (where royalty is enforced) |
| Temporary freeze ≥ 1 day | Withdrawal queue manipulation, pause that can be set but not unset for ≥24h |
| Lack of funds DoS | Program drained but not by exploit (e.g., griefing that locks pool tokens) |

**PoC requirements:** same as Critical, with focus on the unclaimed-but-allocated nature of the funds.

### Medium

**Per VRC v2.3:**
- Smart contract unable to operate due to lack of token funds (where this is not a direct loss)
- Block stuffing for profit
- Theft of gas
- Unbounded gas consumption

**Solana operational interpretation:**

| Medium scenario | Common Solana manifestation |
|---|---|
| Smart contract unable to operate | DOS of critical handler (liquidations, withdrawals) without permanent damage |
| Block stuffing | Mostly EVM-specific; Solana has different congestion model |
| CU theft | Forcing protocol to spend CU on attacker behalf |
| Unbounded CU | Protocol's loop attacker can extend, draining transaction budget |

**PoC requirements:** show repeated griefing or measurable resource consumption.

### Low

**Per VRC v2.3:**
- Smart contract fails to deliver promised returns, but doesn't lose value

**Solana operational interpretation:**
- Yield miscalculation that's slow but recoverable.
- Fee bypass that doesn't affect protocol revenue at scale.
- Self-griefing patterns.

**Submission caution**: many programs have minimum thresholds where Low pays nothing or token amounts. Check bounty page before investing PoC effort on Lows.

### Informational

**Per VRC v2.3:**
- Code style, missing events, etc.
- Not exploitable

**Submission caution**: standalone Informational rarely paid. Bundle with higher findings.

---

## Smart Contracts / Blockchain — Bridges category

For Solana bridges (Wormhole, Allbridge, deBridge, Mayan, Portal):

### Critical (bridge-specific)

- Theft of bridged tokens (mint on dest without lock on source, or vice versa)
- Theft of governance tokens of the bridge
- Unauthorized message relay
- Permanent freeze of locked tokens

The Wormhole exploit was Critical: enabled minting of 120K wETH without ETH-side deposit.

### High (bridge-specific)

- Temporary freeze of bridged tokens
- Censorship of cross-chain messages
- Replay of cross-chain messages

---

## Smart Contracts / Blockchain — Wallets, Custodians category

Less relevant for Solana (most Solana wallets are non-custodial), but applies to:
- Squads / multisig as custodian
- Custodial staking platforms

### Critical

- Direct theft of custodied user funds.
- Loss of custody (user funds become unrecoverable).

---

## Differential triager interpretation

VRC is the spec. Triagers interpret. Common interpretive moves:

### Conservative interpretation patterns

Some triagers (notably for new programs or post-incident programs) interpret conservatively:
- "Direct theft" requires a direct fund movement to attacker; if attacker just gains a state advantage that they later exploit, downgraded.
- "Any amount" is interpreted with TVL filter; submitting Critical for a $10 extraction may be downgraded to Low by TVL-scaling.
- "Any user" is interpreted strictly; if attack works against only a subset of users, may downgrade.

### Liberal interpretation patterns

Some triagers (especially mature programs, high-bounty) interpret liberally:
- "Theft" includes value extraction even if not direct token transfer.
- "Permanent freeze" includes time horizons that exceed 24h even without provably permanent.
- "Unauthorized minting" includes token-equivalent value emission.

You can't predict which type you get. Argue your case clearly and let the triager's interpretation play out.

## Severity caps and TVL scaling

Many programs have severity caps based on TVL. These are stated on the bounty page.

Example pattern: "Critical capped at 10% of TVL". Translation:
- If TVL is $1M, max Critical payout is $100K.
- If TVL is $10M, max Critical payout is $1M.
- If TVL is $100M, max Critical payout is $10M (but typically capped further at the program's stated max, e.g., $500K-$2M).

If your finding extracts less than 10% of TVL, you may be capped to that fraction.

## Anti-VRC moves to avoid

Don't:
- Submit "Critical" for a bug that just slows performance — that's Medium at best.
- Submit "High" for a bug that requires admin compromise — that's OOS.
- Argue "Critical" with a PoC that admits hidden conditions — triager will spot, downgrade hard, your credibility takes hits.
- Spread one bug across multiple severity claims — pick one, defend it.

## Read-the-page-first principle

Before invoking VRC, read the project's bounty page in detail. Many programs override VRC defaults with their own definitions. Specifically check:
- Severity definitions (sometimes they redefine "Critical")
- Scope (sometimes they include items VRC excludes)
- Caps (often stated as "Critical capped at $X")
- KYC requirement (impacts whether anon submissions are accepted)
- Required PoC format (sometimes specific framework required)
- Excluded findings (read every line)

Each program is its own world within VRC's umbrella. Master the page before submitting.

## VRC compliance examples

### Good

```
SEVERITY: Critical
VRC ROW: "Direct theft of any user funds, whether at-rest or in-motion"
PoC EVIDENCE: PoC at /poc/main.rs extracts 1234 USDC from vault to attacker ATA
  in single tx. Stdout attached.
ATTACK PRECONDITIONS: attacker has 100 SOL for tx fees; no admin or oracle
  manipulation required.
FUNDS AT RISK: $X (exposed pool TVL of $X via DeFiLlama)
JUSTIFICATION: This bug allows any non-admin actor to drain the pool. PoC
  demonstrates extraction of arbitrary amounts up to pool TVL. No protocol-level
  safeguards block the attack on deployed bytecode (verified hash match).
```

### Bad

```
SEVERITY: Critical
PoC EVIDENCE: I think the attacker could probably extract value if oracle returns X
ATTACK PRECONDITIONS: attacker needs to be able to manipulate the oracle somehow
JUSTIFICATION: this seems really bad to me
```

The first one wins. The second one is rejected.
