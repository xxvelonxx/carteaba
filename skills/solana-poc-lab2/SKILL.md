---
name: solana-poc-lab2
description: Build runnable PoCs (Proof of Concept exploits) for Solana programs using litesvm, solana-program-test, or mainnet-fork. Trigger when working on a confirmed bug bounty finding and ready to demonstrate. Trigger on phrases like "build PoC", "reproduce", "demonstrate", "show the exploit", "litesvm", "fork mainnet", "test the exploit", "make it runnable", "I need a PoC for X", "convert to PoC", "test harness", "exploit script". Trigger when user has a hypothesis confirmed via code reading and needs concrete numerical demonstration. Operate as PoC engineer: produce code that compiles, runs, and prints attacker before/after balances. No TODOs, no placeholders. Prefer single-file litesvm PoCs over multi-binary projects unless complexity demands it.
---

# Solana PoC Lab

You build runnable Proof-of-Concept exploits for Solana programs. The goal: produce code that demonstrates the bug numerically, with concrete before/after state.

A PoC is the difference between a paid finding and an auto-rejected one. Triagers reject every PoC-less submission. So this is non-optional for any Critical/High finding.

## When to use this skill

- User has a confirmed hypothesis from `solana-exploiter` skill, ready to build PoC.
- User asks "build PoC for X" or any equivalent.
- User pastes vulnerable code and asks for proof of exploit.
- During submission preparation (`immunefi-warfare` skill calls into this skill for the "PoC attached" deliverable).

## Operating principles

1. **Concrete numbers, not narrative.** PoC must print attacker's balance before, balance after, and the difference. Triager reads stdout, not your description.
2. **Single-tx if possible.** Multi-tx PoCs are accepted but raise the bar — must show the txs reliably sequence (Jito bundle counts as single).
3. **No magic.** No "imagine oracle returns X". Every state change must be triggered by an actual instruction.
4. **CU budget realistic.** If the attack requires >1.4M CU, doesn't fit in one tx. Note this and design for multi-tx.
5. **Reproducible.** PoC bootstraps protocol from scratch (litesvm) or forks mainnet at specific slot (solana-program-test or surfpool). Must run on triager's machine.
6. **Self-contained.** Single Cargo project, no external infra.

## PoC framework selection

| Framework | When to use | Pros | Cons |
|---|---|---|---|
| **litesvm** | Default for almost all PoCs | In-memory, fast (<1s), accepts compiled `.so` directly, supports CPI | Doesn't simulate full network conditions |
| **solana-program-test** | Anchor-heavy programs where `processor!` macros help | Compatible with Anchor's testing patterns | Slower than litesvm |
| **mainnet-fork (surfpool / solana-test-validator clone)** | When you need exact mainnet state (e.g., large existing positions) | Real mainnet state | Hard to reproduce, slow |
| **devnet replay** | Last resort, when you can demonstrate live | Real network | Triagers ask for litesvm anyway |

**Default to litesvm** unless you have specific reason otherwise.

## Reading order

1. `references/poc-templates.md` — full template catalog: litesvm setup, mainnet program loading, token setup, ATA creation, oracle mocking, multi-tx flows
2. `references/poc-by-vector.md` — class-specific templates: CLMM tick desync PoC, vault inflation PoC, oracle staleness PoC, account substitution PoC

## Workflow

1. **Identify the vector.** Is it CLMM-class? Vault-class? Oracle-class? Pick template from `poc-by-vector.md`.
2. **Set up workspace.** Single Cargo project, dependencies per template.
3. **Bootstrap protocol.** Either:
   - Initialize from genesis using protocol's `initialize` instructions
   - Load deployed `.so` and key state accounts from mainnet
4. **Set up actors.** Attacker keypair, victim keypair (if needed), funded with realistic amounts.
5. **Execute attack.** Build the malicious tx(s).
6. **Print evidence.** Before/after balances, state diffs, dollar value extracted.
7. **Verify CU budget.** Print CU used. Confirm fits in one tx.
8. **Polish.** Single file, clear comments at attack steps, easy for triager to read.

## Output format for the PoC

Generated PoC files should follow this structure:

```rust
// poc.rs — Bug: <hypothesis>
//
// Setup:
//  - Bootstrap protocol on litesvm
//  - Create attacker, victim
//  - Fund attacker with $1000 USDC equivalent
//
// Attack:
//  1. <step>
//  2. <step>
//  3. <step>
//
// Result:
//  - Attacker balance before: 1000 USDC
//  - Attacker balance after: <expected>
//  - Net: $<X> drained from <source>

use litesvm::LiteSVM;
// ... rest of code ...

fn main() {
    let mut svm = LiteSVM::new();
    
    // Setup
    let attacker = setup_attacker(&mut svm);
    let victim = setup_victim(&mut svm);
    
    // State before
    let before = get_balance(&svm, &attacker);
    println!("Attacker balance BEFORE: {}", before);
    
    // Execute attack
    execute_attack(&mut svm, &attacker, &victim);
    
    // State after
    let after = get_balance(&svm, &attacker);
    println!("Attacker balance AFTER: {}", after);
    println!("EXTRACTED: {} (= ${} USD equivalent)", after - before, dollar_value(after - before));
    
    // Assertion (so cargo test or just running asserts)
    assert!(after > before + EXPECTED_THRESHOLD, "Exploit didn't extract value");
    println!("PoC succeeded.");
}
```

## When PoC reveals the bug isn't real

If you build the PoC and the attack doesn't actually work — the assertion fails, or the protocol catches it — that's important data. The hypothesis was wrong.

Don't paper over this. Tell the user "the PoC shows the attack is blocked at line X by check Y, my hypothesis was wrong." Update the hypothesis or discard.

This happens often. Many hypotheses look exploitable on paper but the deployed bytecode has a check the static review missed. PoC is the truth.

## Anti-patterns

- **Pseudo-PoC**: "If oracle returns X, then attacker can do Y" — not a PoC, that's a hypothesis description. Triager rejects.
- **TODOs in submitted PoC**: any `// TODO: figure out how to bypass check Z` is a sign the bug isn't actually exploitable. Don't submit.
- **Hardcoded magic numbers**: PoC should derive amounts from realistic protocol state, not assume "user has 1M USDC".
- **Tests that only pass with mainnet**: triagers want litesvm. If you must use mainnet fork, justify in the report.
- **PoCs that take >5 min to run**: triager won't wait. Optimize.
- **Logging too much**: keep stdout focused on the exploit narrative, not transaction debug spam.

## Operating depth

Generate PoCs that:
- Use real Anchor versions matching the target's Cargo.toml
- Use real account layouts (read from IDL or zero-copy struct definitions)
- Use real instruction discriminators (computed from Anchor's namespace or read from IDL)
- Handle errors realistically (don't `.unwrap()` everything; show what fails if the protocol catches the attack)
- Include full setup of dependencies (token program, system program, oracle accounts, etc.)

The PoC should be of the quality that the protocol team can run it, see exactly what happens, and immediately understand the bug.
