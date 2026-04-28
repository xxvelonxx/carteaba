# Tick Array Layouts — Bit-Level

This file documents Whirlpools-style tick array internals at the byte level. The same pattern applies to Raydium CLMM with minor variations. If your audit target uses a different layout, derive analogous attacks.

## DynamicTickArray byte layout

```
Offset   Size   Field
0        8      Discriminator (Anchor-generated SHA256 prefix of "account:DynamicTickArray")
8        4      start_tick_index: i32 little-endian
12       32     whirlpool: Pubkey
44       16     tick_bitmap: u128 little-endian (88 bits used + 40 padding)
60       N      tick_data — variable length based on initialization state
```

`N` ranges from 88 (all uninit, 1 byte each) to 9944 (all init, 113 bytes each).

So the account size ranges from 60 + 88 = **148** (MIN_LEN) to 60 + 9944 = **10004** (MAX_LEN).

In Whirlpools' implementation: `MAX_LEN` includes the discriminator: `MAX_LEN = 8 + 4 + 32 + 16 + 113*88 = 10004`.

The `DynamicTickArrayLoader` struct has signature `pub struct DynamicTickArrayLoader([u8; MAX_LEN])` but is usually constructed via `unsafe { &*(data.as_ptr() as *const DynamicTickArrayLoader) }` with `data` not necessarily being MAX_LEN bytes. **Reading past `data.len()` is UB.**

## Tick byte layout (when initialized)

113 bytes per tick:
```
Offset   Size   Field
0        1      tag = 1 (DynamicTick::Initialized variant tag)
1        16    liquidity_net: i128 little-endian
17       16    liquidity_gross: u128
33       16    fee_growth_outside_a: u128
49       16    fee_growth_outside_b: u128
65       16    reward_growth_outside[0]: u128
81       16    reward_growth_outside[1]: u128
97       16    reward_growth_outside[2]: u128
```

When uninitialized: 1 byte, value = 0.

## bitmap → byte_offset math

```rust
fn byte_offset(tick_offset: usize) -> usize {
    let bitmap = self.tick_bitmap();              // u128
    let mask = (1u128 << tick_offset) - 1;        // bits 0..tick_offset
    let initialized_before = (bitmap & mask).count_ones() as usize;
    let uninitialized_before = tick_offset - initialized_before;
    initialized_before * 113 + uninitialized_before * 1
}
```

Invariant: `byte_offset(K) + tick_size_at_K <= total_tick_data_size`.

Where:
- `tick_size_at_K = 113` if bit K of bitmap is set, else 1
- `total_tick_data_size = sum_init * 113 + sum_uninit * 1` where `sum_init = bitmap.count_ones(), sum_uninit = 88 - sum_init`

This means: **as long as the bitmap is consistent with the actual byte layout**, byte_offset never exceeds total_tick_data_size. Reads of `data[byte_offset .. byte_offset + 113]` are safe IF the tick at that offset is actually init (113 bytes available).

For uninitialized ticks, naive code reads `data[byte_offset .. byte_offset + 1]` (1 byte). But Whirlpools' anchor `get_tick` reads 113 bytes always:
```rust
let tick_data = &data[byte_offset..byte_offset + 113];
let tick = DynamicTick::deserialize(&mut tick_data)?;
```

If the byte at `byte_offset` is `0` (uninit tag), Borsh deserialize returns Uninitialized after reading 1 byte and **does not read the next 112 bytes**. Safe.

If the byte is `1` (init tag), Borsh reads 112 more bytes. If those bytes are within `data`, safe. If they're past `data.len()`, UB.

**The bitmap-byte_offset math guarantees** that `data[byte_offset+0]` is `1` only when `byte_offset+113 <= total_tick_data_size`. So Borsh's 112-byte read after reading tag=1 is always within bounds.

**But this assumes the bitmap and the bytes are CONSISTENT.** Code path that desyncs them is a bug. Audit pattern: trace every write to `tick_bitmap` and to bytes — they must always be atomic with each other.

## update_tick state-machine

`update_tick(tick_index, update)` has 4 branches:

```
existing tag    update.initialized   action
0 (uninit)      false                no-op (uninit → uninit, no change)
0 (uninit)      true                 INIT: rotate_right(112), set bytes, bitmap |= (1 << tick_offset)
1 (init)        false                UNINIT: rotate_left(112), set byte=0, bitmap &= !(1 << tick_offset)
1 (init)        true                 UPDATE: write 113 bytes in place
```

### INIT branch detail (uninit → init)

```rust
let data_mut = self.tick_data_mut();          // &mut [u8; remaining]
let shift_data = &mut data_mut[byte_offset..]; // slice from byte_offset to end
shift_data.rotate_right(112);
self.update_tick_bitmap(tick_offset, true);   // bitmap |= 1 << tick_offset
// then write 113 bytes at byte_offset
```

`rotate_right(112)`: moves the last 112 bytes of `shift_data` to the front. Since the account was just resized (+112 bytes appended as zeros), the last 112 bytes are zeros. After rotation, the front 112 bytes of `shift_data` are zero — those are what will be overwritten with the new tick data.

**Pre-condition: account is realloc'd to size `old_size + 112` BEFORE update_tick is called.**

If a handler does sync_modify_liquidity (calls update_tick) BEFORE update_tick_array_accounts (the realloc), the rotate_right tries to access bytes that don't exist. **In Solana**, `data_mut[byte_offset..]` is bounded by the account's allocated size; if account is still old size, the slice ends at `old_size`, and rotate_right reads/writes within that bound. The "zeros at the end" assumption breaks → garbage rotation.

### UNINIT branch detail (init → uninit)

```rust
let data_mut = self.tick_data_mut();
let shift_data = &mut data_mut[byte_offset..];
shift_data.rotate_left(112);  // first 112 bytes go to the end
self.update_tick_bitmap(tick_offset, false);
data_mut[byte_offset] = 0;
// after this, account will be realloc'd to size - 112
```

`rotate_left(112)`: first 112 bytes of `shift_data` move to the end. The 113-byte tick at `byte_offset` becomes:
- byte_offset + 0: was byte_offset + 112 (last data byte of the tick — gets overwritten with 0 next)
- byte_offset + 1 .. byte_offset + 113: was byte_offset + 113 .. byte_offset + 225 (the next tick's bytes, shifted into place)

Then `data_mut[byte_offset] = 0` sets the new tag to 0 (uninit).

**Pre-condition: account will be truncated by 112 bytes AFTER update_tick (in update_tick_array_accounts).**

The 112 bytes that "rotated to the end" become the truncated bytes — they're discarded.

### Increase vs decrease ordering

In Whirlpools' anchor v1:
```
INCREASE: calculate → update_tick_array_accounts (resize +112) → sync (update_tick) → transfer
DECREASE: calculate → sync (update_tick) → update_tick_array_accounts (resize -112) → transfer
```

The orders are different because:
- INCREASE adds a new tick: must allocate space first, then write into it
- DECREASE removes a tick: must compact first, then truncate

**Audit pattern:** look for handlers that mix the orders or skip one step. The Pinocchio variants must mirror the anchor variants. Versions v1 and v2 must mirror each other.

## Account confusion attack: Discriminator

If a program loads either FixedTickArray or DynamicTickArray based on discriminator:

```rust
if data[0..8] == FixedTickArray::DISCRIMINATOR {
    // load as fixed
} else if data[0..8] == DynamicTickArray::DISCRIMINATOR {
    // load as dynamic
}
```

**Hypothetical exploit:** if both can exist at the same PDA seeds (different discriminators but same address), attacker initializes one type, then the program later loads it as the other type → byte interpretation mismatch → arbitrary state.

**Whirlpools mitigates:** the PDA seeds are `[b"tick_array", whirlpool, start_tick_index_str]`, identical for both. Only one can exist at a time (since `system_program::create_account` fails if account already exists). The discriminator distinguishes which type was init'd. Once init'd, can only be loaded as that type. ✓

**But:** if a handler INITIALIZES the array (and there's no idempotency check) and the PDA is already init as the other type, the handler should error. Verify this. `initialize_dynamic_tick_array` has an `idempotent: bool` param — when true, it accepts already-initialized arrays of either type. If a caller path always passes `idempotent=true` and the program later assumes the array is dynamic but it's actually fixed, there's a confusion. Verify each loader checks the discriminator before treating the data.

## Sparse swap PDA validation

Sparse swap allows passing tick arrays not at the canonical PDA, plus virtual uninit arrays. The validation:

```rust
fn validate_sparse_tick_array(account: &AccountInfo, whirlpool: Pubkey, start_tick: i32) -> Result<...> {
    let expected_pda = Pubkey::find_program_address(
        &[b"tick_array", whirlpool.as_ref(), start_tick.to_string().as_bytes()],
        &program_id,
    ).0;

    if account.key != &expected_pda {
        return Err(InvalidTickArray);  // account isn't even at canonical PDA
    }

    if account.owner == system_program::ID && account.data_is_empty() {
        // Virtual uninit array — treat all 88 ticks as uninitialized
        return Ok(VirtualUninit);
    }

    if account.owner != program_id {
        return Err(AccountOwnedByWrongProgram);
    }

    let data = account.try_borrow_data()?;
    match disc_of(data) {
        FixedTickArray::DISCRIMINATOR => return Ok(load_fixed(data)),
        DynamicTickArray::DISCRIMINATOR => return Ok(load_dynamic(data)),
        _ => return Err(AccountDiscriminatorMismatch),
    }
}
```

**Bypass classes:**

1. PDA seed mismatch with no other check. If the program accepts `account.key` matching SOME tick array but not the one for THIS pool, attacker passes another pool's tick array. (Whirlpools defends: the seed includes the whirlpool address.)

2. Virtual uninit when canonical exists. If attacker can pass a non-canonical or partially-canonical address that the validator accepts as "virtual uninit" while the canonical one has init ticks, the swap doesn't see the canonical liquidity. **Whirlpools defends:** the validator requires `account.key == expected_pda`, so virtual uninit only succeeds at the exact canonical PDA. Attacker can't pass a different account.

3. Race condition: `is_uninitialized` checked, then state changes before tick reads happen. Solana txns are atomic — no race in practice.

## tick_offset math edge cases

```rust
fn tick_offset(tick_index: i32, tick_spacing: u16) -> isize {
    let start = self.start_tick_index();  // i32
    let offset = (tick_index - start) / tick_spacing as i32;
    offset as isize
}
```

For `tick_index = -443636, start = -443520, tick_spacing = 128`:
```
(-443636 - -443520) / 128 = -116 / 128 = 0 (integer div toward zero in Rust)
```

But `-443636` is OUT of the `start..start+88*spacing` range; check_in_array_bounds should reject it. Verify both paths exist.

`get_offset` in Whirlpools handles the negative case by:
```rust
let r = (tick_index - start) % tick_spacing;
let q = (tick_index - start) / tick_spacing;
if r < 0 { q - 1 } else { q }
```

For negative `r`, this rounds DOWN (more negative). Correct for tick alignment.

**Off-by-one to check:** at the upper boundary, `tick_index = start + 88*spacing` is OUT of range (range is half-open). Verify the check is `tick_index < start + 88*spacing`, not `<=`.

## tick_spacing validation

`tick_spacing` is part of the pool, set at init. It determines:
- Number of ticks per array: 88
- Range of an array: `88 × tick_spacing` ticks
- Valid tick indices: multiples of tick_spacing in `[MIN_TICK, MAX_TICK]`

Special case: `FULL_RANGE_ONLY_TICK_SPACING_THRESHOLD` (Whirlpools = 32768). When `tick_spacing >= threshold`, only full-range positions are allowed. This is enforced in `validate_tick_range_for_whirlpool`.

**Exploit hypothesis:** if a handler that creates positions doesn't call `validate_tick_range_for_whirlpool`, attacker creates a non-full-range position on a full-range-only pool. This bypasses the design intent — usually breaks the math elsewhere.

`check_is_usable_tick`:
```rust
fn check_is_usable_tick(tick_index: i32, tick_spacing: u16) -> bool {
    if tick_index < MIN_TICK_INDEX || tick_index > MAX_TICK_INDEX { return false; }
    tick_index % (tick_spacing as i32) == 0
}
```

For negative tick_index, `%` returns a same-sign result; `== 0` works for any sign. ✓

## Common bug patterns specific to tick arrays

```
[ ] update_tick_array_accounts called BEFORE sync in increase, AFTER sync in decrease (verify both)
[ ] rotate_right(112) and rotate_left(112) used; not rotate_right(113) which would corrupt
[ ] bitmap update is atomic with bytes update (no path that sets bitmap but not bytes)
[ ] PDA validation includes whirlpool seed (no cross-pool tick array confusion)
[ ] Same tick_array account passed twice (lower == upper) — handler must allow if positions span same array
[ ] Token-2022 reentry between sync and resize: if a CPI happens between, account state may be inconsistent (audit Anchor reentrancy guards)
[ ] Discriminator check on every load_tick_array call site (not just initialize)
[ ] FixedTickArray and DynamicTickArray cannot collide at same PDA (one or the other must succeed init, not both)
[ ] Virtual uninit array path requires PDA seeds match exactly (no false-virtual)
[ ] tick_offset > 87 rejected (out of array bounds)
[ ] check_in_array_bounds half-open: `tick_index < start + 88*spacing`, not `<=`
[ ] tick_spacing stored at pool init, never modifiable (otherwise byte_offset math breaks)
```
