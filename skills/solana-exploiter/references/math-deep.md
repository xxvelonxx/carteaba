# Math — Q64.64, U256, Rounding, CLMM

Solana DeFi math is dominated by fixed-point: prices in Q64.64, liquidity in u128, fees in u16 with 1e6 denominator. Every fixed-point operation has a rounding direction. Every wrong direction is a one-wei leak per call. At scale, that's a draining position.

## Q64.64 fixed-point

Q64.64 is a 128-bit integer interpreted as `value × 2^64`. Range: `[0, 2^64) × 2^-64 = [0, 2^64) Q-format`, but practically:
- Integer part: 64 bits → range [0, 2^64)
- Fractional part: 64 bits → resolution 2^-64 ≈ 5.42 × 10^-20

Conversions:
```
to_q64(x) = x << 64        // u64 → u128 Q64.64
from_q64_floor(q) = q >> 64
from_q64_ceil(q)  = (q + ((1<<64)-1)) >> 64
```

The expression `(q >> 64) as u64` is `from_q64_floor`. **It silently truncates the fractional part — that's correct as long as you intend floor.** If you intend ceil but used `>> 64`, you under-report by up to 1 wei.

## sqrt_price encoding

Whirlpool, Raydium CLMM, Uniswap V3 all encode price as `sqrt(price) × 2^64`:
```
sqrt_price_x64 = u128 representing sqrt(B/A) × 2^64
```

Why sqrt: a swap that moves `Δ` tokens of A vs B has linear effect on `sqrt_price`, not on `price`:
```
Δa = L × (1/sqrt_price_lower - 1/sqrt_price_upper)
Δb = L × (sqrt_price_upper - sqrt_price_lower)
```

These come from the constant-product invariant `x × y = k` rewritten in terms of `L = √k`.

Bounds:
- `MIN_SQRT_PRICE_X64 = 4295048016` (≈ tick = -443636)
- `MAX_SQRT_PRICE_X64 = 79226673515401279992447579055` (≈ tick = 443636)

Tick to sqrt_price:
```
sqrt_price(tick) = (1.0001^(tick/2)) × 2^64
```

Computed via incremental multiplication using a precomputed table (see Whirlpools `tick_math.rs::sqrt_price_from_tick_index`). The implementation is a port of Uniswap V3's; the magic constants are 28 hex values for powers of `1.0001^(2^k)`.

**Exploit class:** if the tick→sqrt_price function rounds in the wrong direction at a tick boundary, swaps that span the boundary either over- or under-charge by one wei. Compounded over many swaps, drains the pool.

## Rounding direction theory

Given any computation `output = f(input)`:
- Round in the direction that **favors the protocol** for both input and output.
- Input from user: round UP (user pays more)
- Output to user: round DOWN (user receives less)

For LP operations:
- Increase liquidity (user deposits): round UP for both deltas (user deposits MORE than the math says)
- Decrease liquidity (user withdraws): round DOWN for both deltas (user receives LESS than the math says)

**Test pattern:** for every arithmetic in a financial flow, mentally annotate rounding direction. If two adjacent operations have opposite directions (one floors, the other ceils), the user gets free dust per call.

## CLMM bit_math primitives (Whirlpool/Uniswap V3)

```rust
fn checked_mul_div_round_up_if(n0: u128, n1: u128, d: u128, round_up: bool) -> Result<u128>
fn checked_mul_shift_right_round_up_if(n0: u128, n1: u128, round_up: bool) -> Result<u64>
fn div_round_up_if(n: u128, d: u128, round_up: bool) -> Result<u128>
```

Internal:
```rust
let p = n0.checked_mul(n1)?;        // u128 × u128 → u128, fails on overflow
let n = p / d;                       // floor division
if round_up && p % d > 0 { n + 1 } else { n }
```

Note `checked_mul` is `u128.checked_mul(u128) -> Option<u128>`. **Two u128s overflow easily.** For values that need full precision, use U256:

```rust
fn mul_u256(a: u128, b: u128) -> U256Muldiv;  // never overflows
```

`U256Muldiv` is a 256-bit integer represented as `(u128_hi, u128_lo)`. Division returns `(quotient, remainder)`.

**Exploit pattern:** code uses `checked_mul` where U256 is needed. Inputs are bounded such that overflow doesn't happen "in practice" — but attacker finds an edge case (max liquidity × max sqrt_price) that overflows. `checked_mul` returns `None`, function returns error → DoS, not theft. UNLESS the error path leaves state mid-mutated.

## get_amount_delta_a / get_amount_delta_b

The two CLMM math primitives:

```
Δa = L × (sqrt_upper - sqrt_lower) / (sqrt_lower × sqrt_upper)        // shifted by Q64
Δb = L × (sqrt_upper - sqrt_lower)                                     // shifted by Q64
```

Implementation in Whirlpools (`token_math.rs`):

```rust
pub fn try_get_amount_delta_a(
    sqrt_price_lower: u128,
    sqrt_price_upper: u128,
    liquidity: u128,
    round_up: bool,
) -> Result<AmountDeltaU64> {
    let sqrt_price_diff = sqrt_price_upper - sqrt_price_lower;
    let numerator = mul_u256(liquidity, sqrt_price_diff)
        .checked_shift_word_left()  // << 64 in U256
        .ok_or(...)?;
    let denominator = mul_u256(sqrt_price_upper, sqrt_price_lower);
    let (quotient, remainder) = numerator.div(denominator, round_up);
    // quotient + (1 if round_up && remainder>0)
    ...
}
```

```rust
pub fn try_get_amount_delta_b(...) -> Result<AmountDeltaU64> {
    let p = liquidity.checked_mul(sqrt_price_diff)?;     // u128 × u128 in u128 — can overflow
    let result = (p >> 64) as u64;                        // floor truncation
    let should_round = round_up && (p & Q64_MASK > 0);
    ...
}
```

**Asymmetry:** Δa uses U256 (correct, can never overflow), Δb uses u128 with `checked_mul` (overflow returns error). For very large liquidity × very large sqrt_price_diff, Δb path fails. Δa path always succeeds. Asymmetric behavior between the two paths can leak.

**Specific exploit pattern:** in a swap that should fail (large size, large price impact), one direction fails cleanly while the other succeeds with a wraparound or a partial result. Attacker chooses the direction that succeeds.

## get_next_sqrt_price functions

Two variants:
```
get_next_sqrt_price_from_a_round_up(sqrt_price, L, amount, is_input)
get_next_sqrt_price_from_b_round_down(sqrt_price, L, amount, is_input)
```

Why one rounds up and the other down:

If we're adding A (price decreases), we want price-after to be **higher** than mathematically true (round up sqrt_price). Higher price = less A pulled in for the same L change = user can add LESS. Conservative.

If we're adding B (price increases), we want price-after to be **lower** than mathematically true (round down sqrt_price). Lower price = less B used for the same L change = user can add LESS. Conservative.

**Exploit class:** if the rounding direction is inverted, the user gets a price more favorable to them (more output, less input). Compounded.

`get_next_sqrt_price_from_b`:
```rust
let amount_x64 = (amount as u128) << 64;   // Q64.0 → Q64.64
let delta = div_round_up_if(amount_x64, liquidity, !amount_specified_is_input)?;
// is_input=true (adding B, increasing price): round_up=false → floor → smaller delta → smaller price increase = conservative
// is_input=false (removing B, decreasing price): round_up=true → ceil → bigger delta → bigger price decrease = conservative

if is_input { sqrt_price + delta } else { sqrt_price - delta }
```

The boolean inversion is subtle. When auditing CLMM math, **draw the table**:

| is_input | direction | want delta to be | round_up |
|---|---|---|---|
| true (add B) | + | floor (smaller delta) | false |
| false (remove B) | − | ceil (bigger delta, makes price drop more) | true |

Wait — that's confusing. Re-derive:

If we're guaranteeing the user receives at least `amount` of B (output, is_input=false), then `sqrt_price` must drop by at least `delta`. We want `delta` to be CEIL (round up) — i.e., the price drops MORE than mathematically minimal. The user gets at least `amount` (round up the price drop guarantees).

But the function says `round_up = !amount_specified_is_input`. When `is_input=false`, `round_up=true` → CEIL of delta → price drops MORE. ✓ Correct.

When `is_input=true` (user provides at most `amount` of B input), price increases by `delta`. We want delta to be FLOOR — price increases LESS than mathematically max. User's input goes a shorter distance. Conservative for protocol. `round_up=false` → FLOOR. ✓ Correct.

**Audit pattern:** for every rounding direction, write out the 4 cases (input/output × a/b) and verify each independently. Don't trust the variable names.

## Liquidity overflow / underflow

```rust
pub fn add_liquidity_delta(liquidity: u128, delta: i128) -> Result<u128> {
    if delta == 0 { return Ok(liquidity); }
    if delta > 0 {
        liquidity.checked_add(delta as u128).ok_or(...)
    } else {
        liquidity.checked_sub(delta.unsigned_abs()).ok_or(...)
    }
}
```

`delta.unsigned_abs()` for `delta = i128::MIN` returns `i128::MAX as u128 + 1 = 2^127`. So `unsigned_abs(i128::MIN)` = 2^127, doesn't panic.

**But:**
```rust
pub fn convert_to_liquidity_delta(amount: u128, positive: bool) -> Result<i128> {
    if amount > i128::MAX as u128 { return Err(LiquidityTooHigh); }  // ← guard
    Ok(if positive { amount as i128 } else { -(amount as i128) })
}
```

If the guard is missing, `-(amount as i128)` for `amount = 2^127` is `-(i128::MIN)` which IS UB (overflow). Verify the guard.

## Integer comparison pitfalls

**Signed vs unsigned:**
```rust
let a: i32 = -5;
let b: u32 = 10;
if a < b as i32 { ... }   // -5 < 10 → true
if (a as u32) < b { ... } // 4294967291 < 10 → false  ← bug
```

**Multiplication signed overflow:**
```rust
let a: i32 = i32::MAX;
let b: i32 = 2;
a * b  // ← panics in debug, wraps in release: result is -2
```

Use `checked_mul` always for signed.

**`% (modulo) of negative numbers:**
```rust
-5 % 3 = -2   // Rust uses sign of dividend
```

Tick alignment check: `tick_index % tick_spacing == 0` works for negative tick_index because both `0 % 3 = 0` and `-3 % 3 = 0`. But `tick_index % tick_spacing` for non-multiples returns a signed remainder; comparison `== 0` is fine for any sign.

## Bit shifts beyond type width

```rust
let x: u128 = 1u128 << n;  // panics if n >= 128
```

If `n` is user-controllable (e.g., reward_index used as shift), this is a vulnerability. Mitigation: check `n < 128` before shift.

## Truncation in `as` casts

```rust
let q: u128 = ...;
let result = (q >> 64) as u64;
```

If `q >> 64 > u64::MAX`, this truncates silently (no panic, no error). Specifically: `(q >> 64) as u64` = `(q >> 64) & u64::MAX`.

Check whether `q >> 64` can exceed `u64::MAX`. If `q = u128::MAX` and shift is 64, `q >> 64 = u64::MAX`, fits. If shift is < 64, can exceed.

Whirlpools handles this in `checked_mul_shift_right_round_up_if`:
```rust
let result = (p >> 64) as u64;
let should_round = round_up && (p & Q64_MASK > 0);
if should_round && result == u64::MAX {
    return Err(MultiplicationOverflow);  // catch the wraparound
}
```

The `result == u64::MAX` guard catches the case where rounding up would wrap. Without this guard, attacker crafts inputs to land exactly at `u64::MAX` post-shift, triggering wrap on +1.

## Common math bug patterns to grep for

```bash
# Unchecked arithmetic on u64 / u128
grep -rn "as u64\|as u128\|+ \|- \|* \|/ " --include='*.rs' src/math/ | grep -v "checked_\|wrapping_\|saturating_"

# Wrapping arithmetic where checked is needed
grep -rn "wrapping_" --include='*.rs' src/

# Bit shifts with non-constant operand
grep -rn ">> \|<< " --include='*.rs' src/ | grep -v "<<.\?[0-9]\|>>.\?[0-9]"

# i128::MIN / i32::MIN handling
grep -rn "i128::MIN\|i32::MIN\|i64::MIN" --include='*.rs' src/

# Division
grep -rn " / \|.div(" --include='*.rs' src/math/ | grep -v "checked_"
```

For each hit, ask: "can attacker control inputs such that this overflows / wraps / truncates?"

## Validate_constants pattern

Mature codebases (Whirlpools is an example) include `validate_constants` functions that explicitly enforce input ranges to prevent overflow at compute time:

```rust
pub fn validate_constants(...) -> Result<()> {
    if max_volatility_accumulator * tick_group_size > i32::MAX as u32 {
        return Err(InvalidAdaptiveFeeConstants);
    }
    ...
}
```

When a target has these, the team has anticipated overflow attacks. Look for **what they didn't validate**, not what they did. Common misses:
- New code path that bypasses validate_constants (e.g., `set_X` admin function that doesn't re-validate)
- Edge case where validate passes but combined with another field overflows
- Validation only on `set` but not on init defaults

## Production exploit reference: KyberSwap CLMM ($48M, Nov 2023)

Root cause: `swap` function had two paths for crossing a tick — a "normal" path and an edge case for "tick exactly at boundary". The edge case had a different fee_growth_outside update than the normal path. By crafting a swap that triggered the edge case, the attacker double-counted fee growth on a tick they owned, then collected fees that were never paid.

Pattern: **two paths to the same state mutation, with subtly different invariants on each**. Audit pattern: any `if`/`else` in a swap or liquidity flow where both branches mutate the same accounting field — verify the post-conditions are identical.

Whirlpools-equivalent location: `swap_manager::swap` lines 157–234 (initialized vs uninitialized tick paths). The Whirlpools team specifically guarded against this — both branches go through `calculate_fees` and `calculate_update` with identical logic.
