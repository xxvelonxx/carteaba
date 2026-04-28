# CLMM-Specific — Whirlpools, Raydium CLMM, Crema, Cykura

CLMMs (Concentrated Liquidity Market Makers) are the highest-bounty Solana targets ($500K Whirlpools, similar for Raydium CLMM). They're also the most exploited category historically: KyberSwap ($48M), Crema ($8.8M), and many smaller incidents. The complexity of tick math + position accounting + fee distribution creates many surfaces.

## Architecture (universal across CLMMs)

```
Pool (Whirlpool)
├── tick_current_index, sqrt_price, liquidity (active)
├── fee_growth_global_a, fee_growth_global_b (cumulative)
├── reward_infos[3]
├── token_mint_a, token_mint_b, token_vault_a, token_vault_b
└── fee_rate, protocol_fee_rate, tick_spacing

TickArray (account, one per ~88 ticks)
├── start_tick_index
├── ticks[88]: each Tick has:
│   ├── initialized: bool
│   ├── liquidity_net: i128 (signed delta when crossed)
│   ├── liquidity_gross: u128 (sum of |delta|, for tracking active count)
│   ├── fee_growth_outside_a/b: u128 (snapshot at last cross)
│   └── reward_growths_outside[3]: u128

Position (account, NFT-bound)
├── whirlpool: Pubkey
├── position_mint: Pubkey  (NFT)
├── tick_lower_index, tick_upper_index
├── liquidity: u128
├── fee_growth_checkpoint_a/b: u128 (last fee_growth_inside seen)
├── fee_owed_a/b: u64
└── reward_infos[3]: { growth_inside_checkpoint, amount_owed }

PositionLockConfig (optional, for locked positions)
└── owner, position, lock_type
```

## The fee_growth invariant

This is the heart of CLMM correctness, and the most exploited area.

`fee_growth_global` is a monotonically-increasing counter of fees per unit of liquidity. When a swap pays fee `f` while pool liquidity is `L`, `fee_growth_global += f << 64 / L`.

`fee_growth_outside` of a tick captures `fee_growth_global at the time the tick was last crossed`. It represents fees accumulated on the OTHER side of the tick (above for upper, below for lower).

`fee_growth_inside(lower, upper)` = fees accumulated INSIDE the range `[lower, upper)`:
```
if current_tick >= lower:
    growth_below_lower = lower.fee_growth_outside
else:
    growth_below_lower = global - lower.fee_growth_outside

if current_tick < upper:
    growth_above_upper = upper.fee_growth_outside
else:
    growth_above_upper = global - upper.fee_growth_outside

fee_growth_inside = global - growth_below_lower - growth_above_upper
```

A position's accumulated fees:
```
fees_owed += position.liquidity × (fee_growth_inside_now - position.fee_growth_checkpoint)
position.fee_growth_checkpoint = fee_growth_inside_now
```

**Key invariant: `fee_growth_inside_now >= position.fee_growth_checkpoint` whenever position has liquidity.**

If the invariant breaks, `fee_growth_inside_now - checkpoint` underflows (it's u128). Solana programs use `wrapping_sub` here intentionally — Uniswap V3 does the same — because checkpoints can legitimately decrease across tick crosses, and the wraparound math works out IF every cross is symmetric.

**Exploit class: checkpoint desync**. If a position's checkpoint is updated WITHOUT updating liquidity (or vice versa), or if checkpoints from a previous range leak into a new range, the wraparound math breaks → fees materialize from nothing.

KyberSwap exploit was exactly this: a tick-crossing edge case updated `fee_growth_outside` differently than expected, breaking the checkpoint invariant for positions that touched the boundary.

**Audit pattern:** trace every write to `fee_growth_outside_a/b`, `fee_growth_global_a/b`, `position.fee_growth_checkpoint_a/b`. Verify:
1. Every cross of a tick during swap updates `fee_growth_outside` exactly once.
2. Every modify_liquidity (increase/decrease/reposition) updates `position.fee_growth_checkpoint` to the current `fee_growth_inside`.
3. There is NO path that resets `fee_growth_checkpoint` to 0 while `position.liquidity > 0`.
4. The two updates above are atomic — no path runs one without the other.

## Tick array layouts

Two formats: Fixed and Dynamic.

### FixedTickArray (legacy)
- 8 byte discriminator + 4 byte start_tick + 32 byte whirlpool + 88 × 113 = 9944 byte ticks
- Total: 9988 bytes
- Each tick stores its full data even if uninitialized. Wastes space but layout is fixed.
- Account address: `[b"tick_array", whirlpool, start_tick_index.to_string()]`

### DynamicTickArray (newer)
- 8 disc + 4 start_tick + 32 whirlpool + 16 byte bitmap + variable tick data
- Initialized tick: 113 bytes (1 tag + 112 data)
- Uninitialized tick: 1 byte (tag = 0)
- Bitmap: each bit indicates if corresponding tick is initialized
- byte_offset(tick_offset) = `(initialized_before × 113) + (uninitialized_before × 1)`
- Account is realloc'd up/down on each init/uninit (+112 / -112 bytes)
- Account address: same seeds as Fixed; distinguished by discriminator

**Discriminator must distinguish them.** Whirlpools' Anchor account macro generates different 8-byte hashes for `FixedTickArray` and `DynamicTickArray` types. Programs that load tick arrays must check both possibilities and dispatch.

### Sparse swap (recent feature)

Whirlpools' sparse swap allows the swap to provide tick arrays "by hint", where some hinted arrays may not be the canonical PDA. The hint is validated:

```rust
// pseudo: load_tick_array_for_swap
if discriminator(hinted) == DynamicTickArray && pda(seeds) == hinted.address {
    // fully validated
} else if discriminator(hinted) == FixedTickArray && pda(seeds) == hinted.address {
    // fully validated
} else if hinted.is_uninitialized_pda(seeds) {
    // VIRTUAL uninitialized array — treat as all ticks uninit
} else {
    return Err(InvalidTickArray);
}
```

**Exploit class:** the "virtual uninitialized" path. If the verification of the PDA seeds matches but the account is not actually owned by the program (e.g., uninit system-owned account), the swap proceeds as if the array has no initialized ticks. If the canonical array has initialized ticks but attacker provides a virtual uninit at the same seeds, the swap doesn't cross those initialized ticks → liquidity never updates → swap math runs against stale liquidity → incorrect output.

**Whirlpools defends** by requiring the PDA seeds to match exactly. Audit pattern: verify that the "virtual uninit" path requires `pda_owner == system_program` AND `data_len == 0` AND seed match. Any laxness opens the exploit.

## Position checkpoint update flow

The critical sequence in `modify_liquidity` (increase or decrease):

```rust
// Step 1: read current fee_growth_inside
let fee_growth_inside_a_now = compute_fee_growth_inside(
    pool.fee_growth_global_a,
    tick_lower.fee_growth_outside_a,
    tick_upper.fee_growth_outside_a,
    pool.tick_current_index,
    position.tick_lower_index,
    position.tick_upper_index,
);
let fee_growth_inside_b_now = ...;

// Step 2: settle the existing position's accrued fees BEFORE changing liquidity
let new_fee_owed_a = position.fee_owed_a + (
    position.liquidity *
    fee_growth_inside_a_now.wrapping_sub(position.fee_growth_checkpoint_a)
) >> 64;
let new_fee_owed_b = ...;

// Step 3: update position state
position.fee_owed_a = new_fee_owed_a;
position.fee_owed_b = new_fee_owed_b;
position.fee_growth_checkpoint_a = fee_growth_inside_a_now;
position.fee_growth_checkpoint_b = fee_growth_inside_b_now;
position.liquidity = add_delta(position.liquidity, delta);

// Step 4: update tick state (gross, net)
tick_lower.liquidity_gross += |delta|;
tick_lower.liquidity_net += delta;  // signed
tick_upper.liquidity_gross += |delta|;
tick_upper.liquidity_net -= delta;  // signed

// Step 5: if a tick's liquidity_gross transitions 0 → nonzero, initialize it
//         if a tick's liquidity_gross transitions nonzero → 0, uninitialize it
//         on init, set fee_growth_outside = global if current_tick >= tick, else 0
```

**Exploit-relevant invariants:**

A. **Checkpoint update is mandatory whenever liquidity is touched.** Any path that changes `position.liquidity` without first settling `fee_owed` and updating checkpoint is broken. Specifically check: any "fast path" or "lazy" code path.

B. **Tick init/uninit fee_growth_outside is conditional on `current_tick`.** If a tick is initialized while `current_tick >= tick`, set `fee_growth_outside = global`. Else set to 0. This ensures `fee_growth_inside` calculation is correct from the moment of init. **Inverting this logic is the classic CLMM bug.** Old Cykura had this bug.

C. **Tick uninit must reset fee_growth_outside to 0.** Otherwise next time the tick is initialized, the stale checkpoint pollutes `fee_growth_inside`.

D. **Reposition (decrease + increase to new range) must reset `position.fee_growth_checkpoint` to the NEW range's `fee_growth_inside`, not retain the old.** A reposition that preserves the old checkpoint allows the position to claim fees that were generated in the old range but not yet collected.

## reposition_liquidity_v2 specifics (Whirlpools)

Recently-added flow: decrease all → reset position range → increase. The atomic sequence:

```rust
// Step A: decrease, settle fees, set position.liquidity = 0
//         after this, position has no liquidity but retains fee_owed_a/b

// Step B: reset_position_range (modifies tick_lower_index, tick_upper_index)
//         keep_owed = true → fee_owed_a/b preserved
//         fee_growth_checkpoint_a/b reset to 0  ← CRITICAL

// Step C: increase to new range
//         settle starts: read fee_growth_inside_NEW_RANGE
//         since position.liquidity == 0, fee_owed delta = 0
//         set fee_growth_checkpoint = fee_growth_inside_NEW_RANGE
```

**Exploit hypothesis:** if Step B preserves `fee_growth_checkpoint` instead of resetting, then in Step C, `fee_growth_inside_NEW - old_checkpoint_FROM_OLD_RANGE` is meaningless. With `position.liquidity == 0` it's harmless. With a path that updates checkpoint without zeroing liquidity first → fee leak.

Audit pattern: ensure the reset in Step B happens, AND that the only way to mutate `fee_growth_checkpoint` is through `update_fees_and_rewards` (which always uses the current range).

## Locked positions

Whirlpools' `LockType::Permanent` and time-locked variants:

```rust
pub struct PositionLockConfig {
    pub position: Pubkey,        // bound to one position
    pub position_owner: Pubkey,
    pub whirlpool: Pubkey,
    pub locked_timestamp: u64,
    pub lock_type: LockType,
}
```

Locked positions cannot be:
- Decreased (handler checks `is_locked_position`)
- Closed (token is frozen via SPL freeze authority on the position mint)
- Liquidity reduced

But CAN be:
- Have fees collected (`collect_fees` doesn't check lock)
- Have rewards collected
- Be repositioned (?) — verify per-version
- Be transferred (`transfer_locked_position` flow)

**Exploit class:** any path that bypasses the lock check.
- `decrease_liquidity` checks lock — verify the v2 variant, the with_token_extensions variant, and the Pinocchio variant ALL check.
- `reposition_liquidity_v2` — does it block locked? If it allows reposition of a locked position, attacker locks → repositions to a low-liquidity range → unlocks → effectively bypassed lock semantics.
- `close_position` relies on SPL freeze — but if a token has no freeze_authority (an admin set it to None mid-flow?), close becomes possible.

## transfer_locked_position flow

```rust
// pseudo:
// 1. unfreeze old position NFT
// 2. transfer to destination
// 3. freeze again
// 4. update lock_config.position_owner = destination
```

**Exploit hypotheses (all DEAD on Whirlpools, but check on forks):**
- Reentry between unfreeze and freeze (DEAD: Solana txns are atomic, no async between instructions)
- Destination owner not validated (by-design: lock_config updates to new owner)
- Transfer to a non-token-account (DEAD: Token program rejects)
- Two simultaneous transfer_locked_position calls in one txn (would require two distinct old owners — DEAD)

## Adaptive fee (Whirlpools-specific)

A volatility-based dynamic fee. Per Oracle account:
```rust
pub struct Oracle {
    pub whirlpool: Pubkey,
    pub trade_enable_timestamp: u64,
    pub adaptive_fee_constants: AdaptiveFeeConstants {
        filter_period: u16,
        decay_period: u16,
        reduction_factor: u16,
        adaptive_fee_control_factor: u32,
        max_volatility_accumulator: u32,
        tick_group_size: u16,
        major_swap_threshold_ticks: u16,
    },
    pub adaptive_fee_variables: AdaptiveFeeVariables {
        last_reference_update_timestamp: u64,
        last_major_swap_timestamp: u64,
        volatility_reference: u32,
        tick_group_index_reference: i32,
        volatility_accumulator: u32,
    },
}
```

The fee at any moment:
```
adaptive_fee_rate = (volatility_accumulator * adaptive_fee_control_factor) >> 32
                    + base_fee_rate
                    [capped at FEE_RATE_HARD_LIMIT]
```

**Exploit hypotheses on adaptive fee:**

1. **Skip volatility update.** If `update_volatility_accumulator` can be skipped on a swap, the fee is stale and the attacker pays less.
2. **Reset volatility_reference at advantageous moment.** If admin set_constants resets variables, an admin can game by resetting before their own swaps.
3. **Volatility accumulator overflow.** `volatility_accumulator: u32` — if it can exceed 2^32, wraps to 0 → fee resets to base. Whirlpools caps at `max_volatility_accumulator` checked in `validate_constants`.
4. **trade_enable_timestamp bypass.** If a permission-less adaptive fee tier sets `trade_enable_timestamp = u64::MAX`, no one can trade. Or attacker sets it to past, enabling early trading.
5. **Oracle account uninitialized but fee logic assumes initialized.** Whirlpools handles this via `is_oracle_account_initialized` check.

## Two-hop swap

```
two_hop_swap(amount_in_or_out, ...):
  pool_a (token_X → token_Y)
  pool_b (token_Y → token_Z)
```

**Exploit hypotheses:**

1. **Same pool used for both hops.** If pool_a == pool_b, the swap is a no-op with fees collected twice → free fee revenue for LPs against the user. Or, if the pool's vault is read between hops, balance double-counting. Whirlpools blocks `pool_a.key() != pool_b.key()`.

2. **Same vault for both hops.** pool_a.vault_y and pool_b.vault_y are the SAME token Y vault if pools share a vault. Solana vaults aren't typically shared, but cross-protocol pools could. Verify each vault belongs to its claimed pool.

3. **Slippage check on intermediate.** No price guarantee on token_Y. Slippage check is end-to-end (X → Z). For exact_out variant, verify intermediate amounts honestly.

4. **Reentry via Token-2022 transfer hook.** If pool_a's mint_y has a transfer hook, after the first hop's CPI, the hook executes attacker code. Attacker calls another instruction that mutates pool_b state mid-flow. Whirlpools mitigates by reloading state after each hop.

## Liquidity griefing patterns

1. **Donate liquidity to make ticks initialized that the protocol expected to be uninit.** Adversarial init of edge ticks raises rent costs, and could bias `liquidity_gross` accounting if liquidity is donated exactly at boundaries.

2. **Initialize/uninitialize tick arrays adversarially.** If anyone can call `initialize_tick_array`, an attacker initializes arrays for never-traded price ranges, costing the project rent.

3. **JIT (Just-In-Time) liquidity sandwich.** Attacker watches mempool for large swap, adds tight liquidity right at the swap's path, captures most of the fees, removes liquidity. Solana doesn't have a public mempool but does have leader-slot priority. JIT is achievable via leader collaboration. Not a bug per se, but a fairness concern.

## CLMM bugs to specifically search for

When auditing a new CLMM, run through these:

```
[ ] Tick init: fee_growth_outside set conditional on current_tick >= tick
[ ] Tick uninit: fee_growth_outside reset (or stays as snapshot — verify intent)
[ ] Tick cross during swap: fee_growth_outside = global - fee_growth_outside (flip)
[ ] Position modify: settles fees BEFORE changing liquidity
[ ] Position modify: updates checkpoint AFTER computing fee_owed delta
[ ] Reposition: resets checkpoint when liquidity = 0
[ ] Same pool guard on two-hop
[ ] Same vault guard on two-hop
[ ] Token-2022 hook reentry guard on each CPI
[ ] Locked position blocks all liquidity-changing handlers (v1, v2, all variants)
[ ] Sparse swap virtual uninit requires PDA seed match AND system-owned
[ ] tick_array account ownership and discriminator on every load
[ ] tick_lower < tick_upper enforced on init AND on reposition AND on every range change
[ ] tick_lower / tick_upper alignment to tick_spacing
[ ] FullRangeOnlyPool tick_spacing rejects non-full-range positions
[ ] Adaptive fee: oracle account properly initialized and validated
[ ] Adaptive fee: volatility never overflows (validated by validate_constants)
[ ] Reward emissions: emissions_per_second_x64 × time_delta / liquidity uses U256 (Whirlpools uses checked_mul_div with unwrap_or(0) → fail-soft)
```

Each line is a hypothesis. Each absence in the target = LIVE finding.
