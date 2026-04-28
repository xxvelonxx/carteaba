# AMM-Specific — Raydium v4, Phoenix, Meteora, Lifinity

CLMM is one AMM family. There are several others on Solana, each with distinct math and bug surfaces:

- **Constant-product (CPMM)**: Raydium AMM v4, Token-Swap, Saber stableswap. Math: `x × y = k`.
- **Orderbook**: Phoenix, OpenBook v2. Not really AMM, but a DEX. Bugs are about matching engine, not pool math.
- **DLMM (Discrete Liquidity Market Maker)**: Meteora. Uses bins instead of ticks. Different math from CLMM.
- **Oracle-AMM hybrid**: Lifinity, GooseFX. Uses external oracle to set price, AMM for execution.
- **Stableswap**: Saber, Mercurial. Uses curve formula optimized for stable assets.

This file documents the bug surfaces specific to each.

---

## Constant-product AMM (Raydium v4, Token-Swap)

The math:
```
x × y = k  (constant)
```

Swap: user adds Δx of A, gets Δy of B such that:
```
(x + Δx) × (y - Δy) = k
Δy = y - k/(x + Δx) = (y × Δx) / (x + Δx)
```

With fee:
```
Δx_after_fee = Δx × (1 - fee_rate)
Δy = (y × Δx_after_fee) / (x + Δx_after_fee)
```

### Common CPMM bugs

#### A. Fee applied wrong direction

Fee should reduce the user's effective input (favors LPs):
```rust
// Correct
let amount_in_after_fee = amount_in * (10000 - fee_bps) / 10000;
let amount_out = (reserve_out * amount_in_after_fee) / (reserve_in + amount_in_after_fee);
```

If fee is applied to output instead, user gets more output for same input. Free dust per swap.

#### B. Reserves read after CPI without reload

```rust
let reserve_a = ctx.accounts.token_vault_a.amount;
let reserve_b = ctx.accounts.token_vault_b.amount;

token::transfer(ctx, amount_in)?;  // reserve_a updated by CPI

// reserve_a still has old value
let amount_out = compute(reserve_a, reserve_b, amount_in);  // ← uses stale state
```

Fix: reload before reading, or compute amount_out FIRST (before any CPI), THEN do transfers.

Standard CPMM pattern: compute → check slippage → transfer in → transfer out → update LP. Don't reorder.

#### C. K invariant not enforced after swap

```rust
// VULNERABLE — pre-swap k vs post-swap k not compared
let amount_out = ...;
transfer(amount_in to vault);
transfer(amount_out from vault);
// k may have decreased due to rounding — protocol loses
```

```rust
// CORRECT
let k_before = reserve_a × reserve_b;
// ... do swap ...
let k_after = (reserve_a + amount_in_after_fee) × (reserve_b - amount_out);
require!(k_after >= k_before, KViolated);
```

The `k_after >= k_before` check catches rounding errors that favor the user.

**Audit pattern:** does the protocol enforce `k_after >= k_before`? Many don't, relying on the formula being "correct by construction". But integer math always loses 1 wei somewhere; if it loses on the protocol side, repeated swaps drain.

#### D. Initial liquidity / first deposit

Same as vault inflation attack:
```rust
if total_lp_supply == 0 {
    lp_amount = sqrt(amount_a × amount_b);  // first deposit
} else {
    lp_amount = min(
        amount_a × total_lp_supply / reserve_a,
        amount_b × total_lp_supply / reserve_b,
    );
}
```

The `min(...)` is to prevent ratio manipulation. The `sqrt(amount_a × amount_b)` for first deposit is the inflation point.

**Defense:** Uniswap V2's `MINIMUM_LIQUIDITY = 1000` LP tokens permanently locked at deployment. Most Solana CPMMs port this; verify.

#### E. Two assets accidentally same mint

If a CPMM allows pool with `mint_a == mint_b`, the math breaks (k = x²). Verify init handler rejects.

```rust
// VULNERABLE
require!(mint_a != mint_b, SameMint);
// missing  ← bug
```

#### F. LP token has freeze authority

If the protocol allows arbitrary LP mints, attacker creates a pool with an LP token whose mint authority can freeze accounts. Then attacker freezes other users' LP, blocking withdrawal.

Defense: protocol creates the LP mint (no freeze authority), not user-supplied.

---

## Stableswap (Saber, Mercurial)

Stableswap optimizes for assets that should trade close to 1:1 (USDC/USDT, etc.). Uses a curve that's closer to constant-sum near the equilibrium and constant-product far from it.

The formula (StableSwap by Curve, ported to Solana):
```
A × n^n × Σx_i + D = A × D × n^n + D^(n+1) / (n^n × Π x_i)
```

Where:
- A: amplification coefficient (higher = closer to constant-sum)
- n: number of assets (typically 2 or 3)
- x_i: reserves of each asset
- D: invariant (a function of reserves and A)

Solving for D requires Newton's method (iterative). The implementation does ~20 iterations.

### Stableswap-specific bugs

#### A. D iteration doesn't converge

If reserves are extreme (one asset tiny, another huge), the iteration may not converge in 20 steps. Solana programs that hit this fail with arithmetic error → DoS.

**Audit:** check the iteration's exit condition. If it's `|D_new - D| < epsilon`, what if `epsilon` is never reached? Is there a max iteration cap?

#### B. A coefficient changes mid-trade

If admin changes A (amplification), the curve shape changes. Mid-tx, this could allow attacker to swap on the OLD curve and arbitrage on the NEW curve.

**Defense:** A changes are time-locked (linear ramp over hours). Verify implementation.

#### C. Stable-asset depeg amplifies losses

If USDC depegs to 0.95 (real event in March 2023), the stableswap absorbs the price impact. LPs lose. Not a bug per se, but a known risk.

If the protocol auto-rebalances, the rebalancer may face arbitrage exploitation.

#### D. Fee asymmetry between deposits and withdraws

Stableswap fees include "imbalance fee" charged when adding/removing liquidity in non-equal proportions:
```
imbalance_fee = base_fee × abs(deposit_ratio - pool_ratio)
```

If this fee is charged on deposits but not withdrawals, attacker deposits balanced (no fee), withdraws unbalanced (no fee), repeats to drain.

**Audit:** verify fee logic is symmetric.

---

## DLMM — Meteora's Discrete Liquidity Market Maker

DLMM uses bins instead of CLMM ticks. Each bin holds liquidity at a specific price. Active bin is the bin where current trades execute.

Layout:
```
Bin
├── id: i32 (bin index)
├── price: u64 (Q64.0)
├── liquidity_x: u64 (token X reserve in this bin)
├── liquidity_y: u64 (token Y reserve)
└── fee_rate
```

Swap:
- Find active bin
- Trade against its liquidity until exhausted
- Move to next bin (price level)
- Repeat until amount_in is consumed

### DLMM-specific bugs

#### A. Bin transition doesn't update active_id

If the swap exhausts active bin's liquidity and continues to next bin, but `active_id` is updated only at end of swap, future swaps within the same tx start from the OLD active_id.

Audit: is `active_id` updated per-bin-cross or per-swap-end?

#### B. Bin reserve = 0 after swap, but active_id stays

If active bin has X = 100, Y = 0 (depleted), next swap from Y to X reads active bin, computes amount_out, but Y = 0 → divide by zero or amount_out = 0 → user pays input but gets nothing.

Audit: bin-empty check before computation. Move active_id to next non-empty bin.

#### C. Bin price ladder gaps

DLMM bins are at prices `base × (1 + bin_step)^id`. If bin_step is small, many bins; if large, few bins.

If a swap crosses multiple bins, each bin's price is slightly different. Attacker can exploit if the ordering of bin updates is wrong.

#### D. Adding liquidity to wrong bin

Liquidity providers specify which bin to add to. If they specify a bin index outside the protocol's range, allocation is wrong or zero.

Audit: bin index range check on add liquidity.

#### E. Fee distribution per bin

DLMM distributes fees per-bin (bins that were swapped through earn fees). If bin tracking is off, fees are misallocated.

Same fee_growth_outside / fee_growth_inside pattern as CLMM, but per-bin instead of per-tick. KyberSwap-class bugs apply.

---

## Lifinity / oracle-AMM hybrid

Lifinity uses an oracle (Pyth) to set the AMM's price. The AMM "rebalances" toward the oracle price.

```
ideal_x_per_y = oracle_price
```

The pool aims to maintain reserves at the ideal ratio. If reserves diverge, internal "rebalancing" trades occur.

### Lifinity-specific bugs

#### A. Oracle staleness during rebalance

If the oracle price is stale, the rebalance trades at a wrong price. Attacker triggers rebalance with stale oracle (no fresh update), arbitrages against the stale-priced AMM.

Audit: oracle staleness checked before every rebalance call.

#### B. Pyth confidence interval not bounded

Pyth provides `(price, conf)`. If `conf > 5%` of price, the price is unreliable. Lifinity should reject.

Audit: verify `conf < threshold × price` check.

#### C. AMM divergence allowance

If the AMM allows reserves to diverge from oracle by X%, attacker takes advantage of the divergence. Smaller X = more rebalancing (gas cost), larger X = more arbitrage opportunity.

The X is a config parameter. Verify it's bounded.

#### D. Single-block rebalance manipulation

Attacker triggers a swap that pushes reserves to maximum divergence, then triggers rebalance, then swaps back. If the rebalance is at a spot price (manipulable), profit.

**Defense:** rebalance uses TWAP, or rate-limited.

---

## Phoenix orderbook DEX

Phoenix is a CLOB (Central Limit Order Book), not an AMM. Bugs are about:
- Order matching logic
- Fee tier assignment
- Self-trade prevention
- Cancel/place atomicity

### Phoenix-specific bugs

#### A. Self-trade exploitation

If a user can place a buy and a sell at the same price, they "trade with themselves" — which usually has lower fees than trading externally. Used for fee farming if the program rewards trade volume.

Defense: detect self-trade and treat as a no-op or apply special fee.

#### B. Order ID collision

If order IDs are predictable (e.g., counter), attacker predicts and front-runs.

Defense: cryptographically secure random or hash-based IDs.

#### C. Maker/taker fee tier abuse

If the protocol gives makers a rebate (negative fee), attacker spam-places maker orders, capturing rebates.

Defense: minimum order size, rate limits, requires capital lockup.

#### D. Fill-or-kill vs partial fill semantics

If an order is FOK (fill-or-kill), the entire order must execute or revert. If partial fill is permitted but the protocol assumes FOK, slippage can occur.

Audit: verify the order type semantics match what the protocol assumes.

#### E. Slippage at orderbook empty

If an order is "market buy", and orderbook is empty, the order should fail (no liquidity), not silently succeed at any price.

If protocol has fallback to AMM at unfavorable price, that's a slippage trap.

---

## Common AMM bugs that span families

### A. Same vault for multiple pools

If one vault account is shared between two pools (rare but happens via init bug), trades on one pool affect the other's accounting.

Audit: verify each pool's vault has unique address derivation including pool ID in seeds.

### B. Vault belongs to wrong pool

If vault constraint is missing (`address = pool.token_vault_a`), attacker passes vault from another pool. Trades drain that pool.

Audit: every CPI vault parameter has constraint to validated pool field.

### C. Trade direction confused

In `swap_a_to_b`, the input is A and output is B. If accounts are swapped (b_input, a_output), math is wrong direction. Usually fails on token mismatch but if both pools share asset structure, may succeed.

Audit: direction is encoded in `a_to_b: bool` parameter. Verify all uses.

### D. Slippage check after CPI

```rust
// VULNERABLE
let amount_out = compute_output(...);
transfer_in(amount_in);
transfer_out(amount_out);
require!(amount_out >= min_output, Slippage);  // ← too late, transfer happened
```

```rust
// CORRECT
let amount_out = compute_output(...);
require!(amount_out >= min_output, Slippage);
transfer_in(amount_in);
transfer_out(amount_out);
```

The slippage check must happen BEFORE state changes.

### E. Init pool with imbalanced reserves

If the first depositor sets reserves at 1 wei A and 1M wei B, the price is heavily skewed. Subsequent deposits at "fair" market price are punished.

Defense: minimum initial liquidity in both directions. OR: arbitrageurs quickly correct (within a block), so the loss is bounded.

### F. Pool with token-2022 fee mint

If the pool accepts a token mint with transfer fee, the pool's `vault.amount` after a deposit is less than `accounted_underlying_amount`.

Defense: every transfer in/out adjusts accounting for the fee.

---

## Audit checklist for AMM protocols

```
[ ] Fee applied to input, not output (reduces user's effective input)
[ ] K invariant: post-swap k >= pre-swap k (catch rounding errors)
[ ] Reserves reloaded after any CPI before further math
[ ] First deposit dead-shares pattern (1000 LP locked at init)
[ ] mint_a != mint_b enforced at pool init
[ ] LP mint is created by protocol, not user-supplied (no freeze auth)
[ ] Slippage check BEFORE transfers, not after
[ ] Each pool has unique vault accounts (seeds include pool ID)
[ ] Vault constraint to pool.token_vault_a/b on every handler
[ ] Trade direction correctly encoded and verified
[ ] CPMM-specific: K check post-swap
[ ] Stableswap-specific: D iteration converges, A change time-locked
[ ] DLMM-specific: bin transitions update active_id consistently
[ ] DLMM-specific: empty-bin handling
[ ] Lifinity-specific: oracle freshness + confidence bound
[ ] Lifinity-specific: divergence allowance is bounded config
[ ] Phoenix-specific: self-trade detection
[ ] Phoenix-specific: order types respected
[ ] Token-2022 mints with fees handled in vault accounting
[ ] Token-2022 mints with hooks gated for reentrancy
```
