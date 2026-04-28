# Severity Maximization

> The severity assigned to your finding determines whether you cash $5K or $500K. The technical bug is the same. The argumentation is everything.

This document is about legitimately maximizing severity through correct application of Immunefi VRC v2.3, not about gaming the system. Triagers are sophisticated; they detect inflation. But they also under-rate findings when the submitter doesn't make the full case.

## The four severity levers

Every Solana finding can be argued along four axes. Maximize each.

### Lever 1: Funds at risk (TVL angle)

**Weak framing:** "Bug exists in handler X."

**Strong framing:** "Bug allows attacker to drain $X (current TVL) by calling Y with crafted input Z. Demonstrated in PoC at <link>. Funds at risk in single transaction: $X. Funds at risk over 24 hours of exploitation: $Y (limited by liquidity replenishment rate)."

**Concrete number sources:**
- Defillama TVL for the protocol (current snapshot, not historical max)
- On-chain vault balance: `solana account <vault> | grep amount`
- Per-instruction limit if there's a cap

**If TVL fluctuates,** quote the TVL at submission time and explicitly note the bug doesn't depend on TVL — it scales.

### Lever 2: Likelihood of exploitation

**Weak framing:** "If conditions X, Y, Z hold..."

**Strong framing:** "Conditions X, Y, Z are present in mainnet state at slot N (https://explorer.solana.com/...). The bug is exploitable from any wallet without privileges, in a single transaction."

**Likelihood factors that raise severity:**
- No special preconditions (any user can trigger)
- No price/state preconditions (not waiting for market move)
- No coordination required (single attacker, single tx)
- Exploit completes in one tx (no front-runnable windows)
- No off-chain state required (no specific signed messages, no oracle update timing)

**Likelihood factors that lower severity (acknowledge them):**
- Requires specific market conditions
- Requires victim action
- Race-conditional (front-runnable by good citizens)
- Requires fork or upgrade that hasn't happened

If your bug has lowering factors, **acknowledge them up front** — triagers respect honesty and penalize hidden conditionals.

### Lever 3: Composability multiplier

A bug that drains protocol A is High. A bug that drains A + breaks every protocol that integrates A is Critical.

**How to argue composability:**
- Identify protocols that CPI into the target. Common: Jupiter (aggregates everything), Kamino (lending uses LSTs), Sanctum (vouches for stake pool prices).
- Show that those protocols would also break if the bug is exploited. E.g., if a vault's share price can be manipulated, every lending protocol accepting that LST as collateral can be liquidation-exploited.
- Argue total exposure: TVL of target + TVL of integrators using target's state.

**Concrete check:** Open Jupiter API, see if target's pools/vaults are routed. If yes, you have composability angle.

### Lever 4: Persistence

**One-shot bug:** Drains $X, then permission expires or state shifts.

**Persistent bug:** Continues draining indefinitely until protocol is paused.

**Persistent + irreversible:** Drains and corrupts state such that even after pause, recovery is impossible without manual intervention.

Persistent bugs always rank higher.

## VRC v2.3 reference

Immunefi's Vulnerability Risk Classification system v2.3 (current as of Apr 2026). Memorize the categories.

### Critical

> *"Manipulation of governance voting result deviating from voted outcome and resulting in a direct change from intended effect of original results"*
> *"Direct theft of any user funds, whether at-rest or in-motion, other than unclaimed yield"*
> *"Permanent freezing of funds (fix requires hardfork)"*
> *"Protocol insolvency"*
> *"Theft of unclaimed royalties"* (NFT)

For DeFi:
- **Direct theft from contract / users** — drain
- **Permanent freezing** — funds stuck forever
- **Protocol insolvency** — bad debt unrecoverable
- **Governance hijack** — voting result manipulation

### High

> *"Theft of unclaimed yield"*
> *"Permanent freezing of unclaimed yield"*
> *"Temporary freezing of funds for at least 1 hour"*
> *"Smart contract unable to operate due to lack of token funds"*

For DeFi:
- **Theft of unclaimed yield** (rewards, fees not yet claimed)
- **Long-term freezing** (>1h, may persist until governance action)
- **DoS that requires admin to fix**

### Medium

> *"Smart contract unable to operate due to lack of token funds"*
> *"Block stuffing"*
> *"Griefing (e.g. no profit motive for an attacker, but damage to the users or the protocol)"*
> *"Theft of gas"*
> *"Unbounded gas consumption"*

For DeFi:
- **Griefing without theft** (attacker damages protocol or users without gain)
- **Theft of gas / forced transactions costing victims gas**
- **DoS on specific paths** (some functions break, others work)

### Low

> *"Contract fails to deliver promised returns, but doesn't lose value"*

- Promised behaviors not delivered
- Bug that doesn't cause loss but is incorrect

### Informational

- Code quality issues, missing events, comment bugs
- Theoretical bugs not exploitable on deployed bytecode

## How triagers actually classify

The published categories are a starting point. Triagers consider:

1. **PoC quality.** A working PoC pinning down dollar amounts is far stronger than a description.
2. **Replicability.** Can the triager run the PoC in 10 minutes and see the result?
3. **Code path clarity.** Can the triager verify which lines of code are buggy without re-reading the entire codebase?
4. **Severity argument.** Did the submitter argue why their classification is correct? Triagers respect well-reasoned arguments and may upgrade severity in response.
5. **Reasonableness.** A submitter claiming Critical for what's clearly Medium loses credibility. Future submissions get scrutinized harder.

## Categories triagers most often downgrade

In order of frequency:

### "Centralization risk" / Admin compromise

If your bug only matters if admin/multisig is compromised, **OOS** typically. Even if you can prove the multisig is single-signer or has weak threshold, this is OOS unless explicitly in scope.

**How to argue around it:** If admin has a *path* to actions they shouldn't have access to (privilege escalation), that's in scope. If admin has the access by design and you object to that design, OOS.

### "Theoretical" / Not exploitable on deployed bytecode

If the bug is in an unreleased branch, OOS. Always validate against `solana program show`.

**How to argue around it:** If the bug is in deployed bytecode but requires specific state that doesn't exist yet (e.g., a feature not yet enabled), argue the state can be brought into existence by anyone for cheap.

### "Known issue"

If the bug is in the project's own known issues list, audit reports, or test repo issues, OOS.

**How to argue around it:** If your bug is similar but distinct from a known issue, distinguish it explicitly.

### "Griefing without funds at risk"

Often downgraded from Medium to Informational. To raise severity:
- Argue the griefing is monetizable (e.g., short-and-grief)
- Argue the griefing creates conditions for a separate bug
- Show concrete user damage (locked funds, even if temporary)

### "Out of scope per scope file"

The Immunefi scope file is authoritative. Read it carefully. Common OOS:
- Specific instructions deemed safe by the project
- Specific account types not in scope
- Frontend-only issues
- Off-chain components

## Tactics that raise severity legitimately

### Tactic 1: Quantify in dollars

Instead of:
> "Attacker can drain liquidity from the pool."

Write:
> "Attacker can drain 100% of the pool's USDC balance ($X.XX at TVL of $Y, current as of slot Z) in a single transaction. PoC drains $X test-USDC equivalent in fork environment."

### Tactic 2: Demonstrate the upper bound

If your bug drains 1% of TVL per call but is repeatable, show:
- One-call drain: $X
- Per-block drain: $Y (slot pace × repeat factor)
- Practical 24h drain: $Z (limited by replenishment / detection)

### Tactic 3: Composability framing

> "Pool X is integrated by Jupiter, Kamino, and Sanctum. Drain of pool X also corrupts Kamino's collateral valuation for users of LST Y, exposing $Z additional TVL across integrating protocols."

(Cite explorer links to integrations.)

### Tactic 4: Race-resistance

> "Bug is not race-conditional — single transaction, atomic. Front-running by other actors does not prevent or interrupt the exploit."

This counters one of the common triager downgrades ("temporary, since others can MEV around it").

### Tactic 5: Persistence framing

> "Bug is exploitable indefinitely. Each exploitation drains $X. The protocol cannot self-recover; admin must pause and patch."

Counters the "one-shot fluke" downgrade.

### Tactic 6: Cite VRC by section number

Triagers respect submitters who quote VRC. Instead of "this is Critical", write:

> "Per VRC v2.3 'Smart Contracts/Blockchain', this finding qualifies as Critical under category 'Direct theft of any user funds, whether at-rest or in-motion, other than unclaimed yield' because the funds are user-deposited principal (not unclaimed yield), and theft is at-rest from the vault."

### Tactic 7: Cite previous resolved bounties

> "A similar root cause was paid as Critical on protocol X (https://immunefi.com/...). The mechanism here is analogous."

Triagers don't always remember every prior payout; reminders help. But cite real ones — fake citations destroy credibility.

## Severity downgrade response template

If a triager downgrades unfairly:

```
Hi <triager>,

Thank you for the review. I'd like to discuss the severity classification.

The current classification: <X>
My proposed: <Y>

The reason for my classification:
1. Funds at risk: <quantified>
2. Likelihood: <single-tx, no preconditions>
3. Persistence: <indefinite vs one-shot>
4. Composability: <integrators affected>

Per VRC v2.3 <section>: <quoted text>. This finding matches because <argument>.

I want to clarify a possible misreading of the PoC: <if there is one>.

Open to discussion. Happy to provide additional artifacts (extended PoC, mainnet fork demonstration, etc.).
```

Don't escalate emotionally. Don't claim conspiracy. Make the argument and let it stand.

## Severity escalation pattern matching

| If triager says | Counter (when valid) |
|---|---|
| "Theoretical only" | Show mainnet state matches preconditions; cite slot |
| "Admin compromise required" | Show non-admin path |
| "Already known" | Distinguish from cited known issue |
| "Griefing only" | Show monetization path |
| "Limited TVL impact" | Quantify with current TVL |
| "Race-conditional" | Show single-tx atomicity |
| "Requires victim action" | Show victim-less exploit (if exists) |
| "Should be Medium not High" | Quote VRC category that fits High |
| "Should be High not Critical" | Quote "direct theft of funds" with PoC value |

## Cap negotiation

Some bounty programs cap payouts at protocol-stated maximums (e.g., "Critical: up to $500K"). Some cap at percentage of impact (e.g., "10% of funds at risk, capped at $1M"). Read the bounty program page carefully.

If the cap is percentage-of-impact, your "funds at risk" number directly becomes the floor of your payout. So Tactic 1 (quantify) becomes Tactic 1 (maximize-but-honestly-quantify).

**Per Immunefi rules:** Triagers cannot pay above the cap. They can pay below. Argue for the cap if your finding qualifies; don't ask for above-cap (you'll lose credibility).

## When you have multiple findings

Submit separately. Each finding gets evaluated independently. Bundling reduces total payout.

**Exception:** If two findings are required to demonstrate one exploit, submit as one finding with both as causal links. Otherwise the triager might mark either one alone as not exploitable.

## Pre-submission checklist for severity

- [ ] Have I quantified TVL at risk in dollars?
- [ ] Have I cited which VRC category this fits and why?
- [ ] Have I argued composability impact (integrators affected)?
- [ ] Have I argued persistence (one-shot vs indefinite)?
- [ ] Have I shown the PoC reproduces with concrete numbers?
- [ ] Have I acknowledged any limiting conditions up front?
- [ ] Have I checked the project's known issues list?
- [ ] Have I confirmed the bug is in deployed bytecode, not just repo HEAD?

If you can't honestly check all eight, the submission is not ready.

## Closing

Severity isn't subjective — it's argued. Triagers bring judgment but they respond to evidence and well-formed arguments. The technical work to find the bug is 60% of the bounty. The remaining 40% is making the case for what it's worth. Don't shortchange the second half.
