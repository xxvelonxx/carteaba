---
name: solana-clmm-amm
description: Domain-specific exploit hunting for Solana concentrated-liquidity AMMs (CLMM) and constant-product AMMs. Trigger on Whirlpools, Orca, Raydium CLMM, Raydium AMM v4, Crema, Cykura, Phoenix, Meteora, Lifinity, Cropper, Saros, Fluxbeam, Pump.fun curves, or any code involving tick arrays, sqrt_price, fee_growth, position liquidity, swap math, Q64.64 fixed-point, U256 muldiv, tick spacing, tick crossing, fee tier, adaptive fee, oracle observation arrays, or constant-product k=xy curves. Trigger keywords: CLMM, AMM, Whirlpool, tick array, tick crossing, sqrt_price, fee_growth_inside, fee_growth_global, fee_growth_checkpoint, position, liquidity, increase_liquidity, decrease_liquidity, collect_fees, swap, swap_v2, pool, two-hop, JIT liquidity, sandwich, rounding direction, Q64.64, mul_div_round, sqrt_price_limit, tick_spacing, observation, TWAP. Companion to solana-exploiter-core for any AMM/CLMM target.
---

# Solana CLMM & AMM Exploit Hunting

Domain-specific deep dive for concentrated-liquidity and constant-product AMMs on Solana. Invoked from `solana-exploiter-core` when the target is any AMM family.

## When to use which reference

| Target | Read |
|---|---|
| Whirlpools, Raydium CLMM, Crema, Cykura, any concentrated liquidity | `references/clmm-specific.md` + `references/tick-array-layouts.md` + `references/math-deep.md` |
| Raydium AMM v4, Phoenix (orderbook hybrid), Meteora dynamic, Lifinity | `references/amm-specific.md` + `references/math-deep.md` |
| Pump.fun bonding curves, Saros, Cropper, exotic curves | `references/amm-specific.md` (curve section) + `references/math-deep.md` |
| Any pool that exposes its sqrt_price as oracle | `references/clmm-specific.md` "sqrt_price as oracle" section |
| Any swap with Token-2022 mints | Also invoke `solana-token-mev` for transfer hook semantics |

## High-EV bug classes (memorize)

CLMM specifically — these have paid out repeatedly across protocols:

1. **Tick crossing rounding asymmetry** — input rounds down, output rounds up at a tick boundary. Per swap, dust leaks to the swapper. At scale or via JIT, real money. KyberSwap pattern (~$48M).
2. **fee_growth_inside desync** — checkpoint snapshot vs actual fee_growth_global mismatch when position range changes mid-flow. KyberSwap, multiple smaller bugs.
3. **Tick array off-by-one** — start_tick_index validation lets attacker pass an array that doesn't cover the current tick. Crema $9M.
4. **Sparse swap with uninitialized tick array** — protocol allows passing 1-3 arrays for sparse swap; attacker passes uninitialized array that gets read as zero-fee.
5. **sqrt_price boundary** — `get_next_sqrt_price` at extreme prices (near MIN_SQRT_PRICE or MAX_SQRT_PRICE) hits overflow or rounds to invalid value.
6. **Position re-range with stale fees** — `reset_position_range` or `decrease_liquidity_v2` resets liquidity but keeps stale fee_growth_checkpoint, which now applies to the new range.
7. **Two-hop with shared vault** — a `swap_two_hop` where both hops share a pool/vault; the intermediate balance is read between hops and double-counts.
8. **fee_growth_global overflow handling** — `wrapping_sub` is correct CLMM standard (Uniswap V3 pattern), but if any path uses `checked_sub` it panics on wraparound and bricks the pool.

AMM (constant-product) — these have paid out:

9. **Constant-product invariant break under fee** — the protocol's `k_post >= k_pre` check is computed before fee is taken, allowing dust drain.
10. **Reserve sync vs balance mismatch** — `update_reserves()` reads token-account balances; donating to the vault between sync and swap creates favorable price.
11. **First-deposit share inflation** — also applies to AMM LP shares in many forks.
12. **Bonding curve reset** — Pump.fun-style curves where graduation/migration creates a brief window of stale state.

See `references/clmm-specific.md` and `references/amm-specific.md` for exact code patterns and grep candidates.

## Methodology for CLMM target

1. **Identify the math file.** Usually `swap_math.rs`, `tick_math.rs`, `liquidity_math.rs`. Highest-density reading target.
2. **For each math function, identify rounding direction.** Write down input direction, output direction. Mismatched directions on the same trade-side is a leak.
3. **For each tick-traversal function, identify boundary handling.** What happens at exactly `start_tick_index`? At `start_tick_index + tick_spacing × 87`? At empty tick arrays?
4. **For fee_growth, identify checkpoint timing.** When is `fee_growth_inside` recomputed? Before/after liquidity update? Before/after token transfer?
5. **For each instruction, identify whether it can be invoked mid-CPI (transfer hook).** If yes, all account state read after the CPI may be stale.

## Methodology for AMM target

1. **Identify the curve formula.** `k = x * y` or variations. What's the invariant?
2. **Find the post-trade check.** `assert!(k_post >= k_pre)`. Is fee already taken? Is rounding accounted for?
3. **Find the reserve sync.** From token account balance or stored state? If from balance, donations break it.
4. **Find the aggregator integration path.** Jupiter calls many AMMs — pre/post invariants in the AMM may not hold under aggregator-injected sequences.

## Output integration

Findings produced here use the format from `solana-exploiter-core` SKILL.md. Always:
- Tag the threat actor (most CLMM bugs are flash-loan or whale; some are dust).
- Tag fork-stacking candidates aggressively. CLMM bugs typically appear in 3+ forks.
- Estimate CU usage — CLMM swaps are CU-heavy (100–250K per swap); multi-hop attacks may not fit a single tx without ALTs/bundles.

## Fork stacking for CLMM (priority targets to check after a finding)

When you find a bug in any of these, immediately check the others:
- **Uniswap V3 lineage on Solana**: Whirlpools (Orca), Raydium CLMM, Crema, Cykura, Lifinity v2 concentrated.
- **Custom CLMM**: Phoenix (orderbook, partial overlap), Meteora DLMM (different but similar bugs apply to bin math).
- **Forks of Whirlpools specifically**: any project that copied Whirlpools math (search GitHub for `pub const TICK_ARRAY_SIZE: usize = 88`).

For AMM:
- **Raydium AMM v4 lineage**: Saros, Cropper, many smaller forks share core math.
- **Bonding curves**: Pump.fun, Moonshot, Bags, Nyan — share migration patterns.
