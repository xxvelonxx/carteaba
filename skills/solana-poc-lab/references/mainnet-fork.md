# Mainnet Fork — When You Need Real State

Sometimes a PoC requires real mainnet state — existing positions, real liquidity, real oracle data. Bootstrap-from-scratch (litesvm) doesn't capture this. Mainnet fork does.

This is a slower path. Use only when:
- The bug requires existing on-chain state that's hard to recreate (e.g., a specific position with specific history).
- The bug only manifests against deployed bytecode mismatched with repo HEAD.
- The triager specifically asks for mainnet fork demonstration.

For most bugs, litesvm is sufficient.

## Tool options

### Option 1 — Surfpool

Surfpool is a fork of `solana-test-validator` with mainnet-fork support built in. Setup:

```bash
# Install
cargo install --git https://github.com/txtx/surfpool

# Fork mainnet at latest slot
surfpool start --rpc-url https://api.mainnet-beta.solana.com

# Fork at specific slot
surfpool start --rpc-url <YOUR_RPC> --slot 250000000
```

This launches a local validator with mainnet state available on-demand (lazy-loaded via RPC).

### Option 2 — Solana test-validator with --clone

```bash
solana-test-validator \
  --url https://api.mainnet-beta.solana.com \
  --clone <PROGRAM_ID> \
  --clone <ACCOUNT_PUBKEY_1> \
  --clone <ACCOUNT_PUBKEY_2> \
  --reset
```

Each `--clone` pulls one account's state from mainnet.

This is slower and requires you to enumerate every account you'll touch. Surfpool handles this automatically.

### Option 3 — Anchor's localnet feature

```bash
anchor test --skip-deploy --skip-build --provider.cluster localnet
```

Combine with `solana-test-validator` running in another terminal with mainnet clones.

## Surfpool workflow

After surfpool starts (it serves RPC at `http://localhost:8899` by default):

```rust
use solana_client::rpc_client::RpcClient;
use solana_sdk::*;

fn main() {
    let client = RpcClient::new("http://localhost:8899".to_string());
    
    // Now you can interact with the fork as if it were mainnet
    let attacker = Keypair::new();
    
    // Airdrop SOL (surfpool allows this on the fork)
    client.request_airdrop(&attacker.pubkey(), 100_000_000_000).unwrap();
    
    // Read real mainnet state
    let pool_account = client.get_account(&KNOWN_POOL_PUBKEY).unwrap();
    println!("Pool data on fork: {:?}", pool_account.data);
    
    // Submit attack tx against forked state
    let attack_tx = build_attack_tx(&client, &attacker);
    let sig = client.send_and_confirm_transaction(&attack_tx).unwrap();
    println!("Attack tx: {}", sig);
    
    // Verify attack effect
    let post_pool = client.get_account(&KNOWN_POOL_PUBKEY).unwrap();
    assert!(state_changed(&pool_account, &post_pool));
}
```

## Pinning to a specific slot

For reproducibility, pin to a specific slot:

```bash
surfpool start --slot 250000000 --rpc-url <RPC>
```

Now the fork represents mainnet's state at slot 250M. Any attempt to read newer state fails. This guarantees PoC results are deterministic.

## Working with real positions

If the bug requires a victim with a specific position:

### Approach A: Use an existing real position

Find a real on-chain position via Solscan or RPC. Pin the fork to a slot where that position exists. Use the position's owner as the victim (you don't need their private key — you can mark accounts as not-needing-signature in your test framework, OR the bug doesn't need victim signature).

### Approach B: Create a position in the fork

Surfpool allows you to inject test wallets and create positions via normal tx flow. This is slower than litesvm but realistic.

```rust
// Setup victim with funds
let victim = Keypair::new();
client.request_airdrop(&victim.pubkey(), 100_000_000_000).unwrap();

// Bridge real USDC to victim (e.g., via temporary mint authority hack on fork)
// OR: use the fork's pre-existing accounts that hold USDC and impersonate

// Create position via the protocol's normal "deposit" tx
let deposit_ix = build_deposit_ix(&victim, ...);
let tx = Transaction::new_signed_with_payer(&[deposit_ix], Some(&victim.pubkey()), &[&victim], blockhash);
client.send_and_confirm_transaction(&tx).unwrap();

// Now victim has a real position on the fork
```

## Oracle price manipulation on fork

For Pyth-priced protocols, the fork inherits real Pyth state. To test stale-oracle scenarios:

### Option 1: Don't update oracle

After the fork starts, time advances on your local validator but the Pyth oracle account doesn't auto-update (the publishers don't connect to your fork). Oracle becomes stale naturally. Bump the local clock past the staleness threshold.

```rust
// Skip ahead 10 minutes (assuming 400ms slots, ~1500 slots)
client.warp_to_slot(current_slot + 1500); // requires test-validator

// Or use surfpool's time manipulation
```

### Option 2: Inject a custom oracle

Replace Pyth oracle account contents directly in the fork:

```rust
// Build a synthetic Pyth price account
let synthetic_pyth_account = build_pyth_price_account(/* price */, /* conf */, /* timestamp */);

// Replace the real oracle on the fork
client.set_account(&PYTH_ORACLE_PUBKEY, &synthetic_pyth_account); // requires fork support
```

This is supported by surfpool and by some test-validator configurations.

## Replay attack workflow (if mainnet attack already happened)

If you're forensically reproducing a past exploit:

```bash
# 1. Find the attack tx signature
ATTACK_TX=4xK...

# 2. Find the slot before the attack
solana confirm $ATTACK_TX -v
# Note: pre-state slot

# 3. Fork at slot before attack
surfpool start --slot <SLOT_BEFORE_ATTACK>

# 4. Replay the attack tx
solana confirm $ATTACK_TX --url http://localhost:8899
# This replays against the forked state
```

This produces the same effect locally. Useful for understanding past exploits (cross-reference with `solana-exploits-forensics` skill).

## Limitations of mainnet fork

1. **RPC dependency**: forking depends on your RPC provider's reliability and rate limits. Use a paid RPC (Triton, Helius) for production PoCs.
2. **Slow**: each tx takes ~400ms (real slot time) vs litesvm's ~2ms.
3. **Reproducibility**: if you don't pin a slot, the fork drifts. Always pin.
4. **Authority impersonation**: you can't sign as accounts you don't have keys for. Workarounds via test-validator's `--clone` and unsigned tx tricks are available but fragile.

## When the triager prefers fork PoC

Some bug bounty programs explicitly ask for fork PoCs because:
- Their team's review workflow is to replay your attack on their internal fork.
- Their protocol has complex state that's hard to recreate.

Read the bounty page for "PoC requirements" or "submission format". If they want fork, give them fork. If they're OK with litesvm, use litesvm.

## Hybrid approach

Often the cleanest PoC is:
1. **Litesvm** for the initial setup and core attack logic — fast iteration, deterministic.
2. **Mainnet fork** for the final demonstration — proves it works on real state.

Submit both, with litesvm as primary and fork as confirmation.

## Anti-patterns

- **Not pinning slot**: fork results vary based on when you ran. Hard to reproduce. Pin.
- **Depending on free RPC**: rate limits will bite. Use Triton/Helius for forks.
- **Ignoring fork-vs-mainnet timing**: if your attack relies on specific oracle state at a specific slot, you must pin BOTH the slot AND the oracle pubkey state.
- **Not testing against real bytecode**: if you build PoC against repo HEAD but deployment is at v1.2.3, fork the deployment. Use `solana program dump` to verify hash match.

## Output format expectations

PoC output should include:
- Slot pinned to.
- Programs loaded (their pubkeys + bytecode hashes).
- Accounts read from fork (with their pubkeys).
- Tx signatures of attack txs.
- Before/after state of relevant accounts.
- Numerical attack outcome.

Example:
```
Forked at slot 250123456 (Mar 15, 2025 14:23:00 UTC)
Loaded program <ID> bytecode hash 0xabc...
Read account <vault_pubkey> with 1234 USDC
Attack tx 1: 5xK...
Attack tx 2: 6yL...
Vault balance after: 0 USDC
Attacker balance after: 1234 USDC
PoC succeeded.
```

This is what makes it reproducible by the triager.
