# CANDIDATE-02: SIMD-0437 `set_lamports_per_byte_to_*` Unimplemented in Firedancer

## Executive Summary

Firedancer has **zero implementation** of the five SIMD-0437 feature gates (`set_lamports_per_byte_to_6333/5080/2575/1322/696`). When any of these features activates on mainnet, Agave updates the Rent sysvar account by calling `update_rent()`, while Firedancer does nothing. This produces different Rent sysvar account hashes → **bank hash mismatch → consensus failure**.

---

## Five-Filter Assessment

| Filter | Status | Reasoning |
|--------|--------|-----------|
| 1. Bank hash mismatch outcome | **PASS** | Agave writes Rent sysvar at activation epoch, FD doesn't → different account states |
| 2. Present in HEAD | **PASS** | Agave v4.0 has full implementation, FD has zero lines of code for these features |
| 3. Not in known issues #9154–#9178 | **PASS** | No known issue mentions SIMD-0437 or `set_lamports_per_byte_to_*` |
| 4. Feature active on mainnet | **NEEDS RPC VERIFICATION** | See evidence below |
| 5. Not inactive-feature-only | **SAME AS FILTER 4** | Depends on activation status |

---

## Filter 4: RPC Verification Required

These five pubkeys must be checked via `getAccountInfo` with `commitment: finalized`:

| Feature | Pubkey |
|---------|--------|
| `set_lamports_per_byte_to_6333` | `4a6f7o7iTcA8hRDCrPLkSatnt5Ykxiu36wo5p1Tt12wC` |
| `set_lamports_per_byte_to_5080` | `61BtM7BkDEE8Yq5fskEVAQT9mYA8qCejJWoLe5apqg81` |
| `set_lamports_per_byte_to_2575` | `Ftxb3ZKq7aNqgxDBbP7EonvR2RszZk9ctjdsTX38kQaz` |
| `set_lamports_per_byte_to_1322` | `GsUBNYNDPdMLHPD37TToHzrzcNcjpC9w5n1EcJk5iTaM` |
| `set_lamports_per_byte_to_696` | `mZdnRh9T2EbDNvqKjkCR3bvo5c816tJaojtE9Xs7iuY` |

If ANY returns a non-null account with `activated_at` set, Filters 4 and 5 both pass.

**Current code-level evidence of activation status (indirect, not definitive):**
- solfuzz-agave commit `63c8f01` (April 17, 2026): "enable fuzzing remaining 4.0 features" added `relax_intrabatch_account_locks`, `relax_programdata_account_check_migration`, `remove_simple_vote_from_cost_model`, `create_account_allow_prefund`, `upgrade_bpf_stake_program_to_v5` — but **did NOT include any SIMD-0437 feature**, suggesting they may not yet be in the active 4.0 feature set
- The SIMD-0437 features are **completely absent** from FD's `feature_map.json` (FD hasn't even begun tracking them), whereas even unimplemented features like `enable_big_mod_exp_syscall` at least have an entry

---

## Code Divergence Evidence

### Firedancer — Zero Implementation

**`/root/firedancer/src/flamenco/features/feature_map.json`**: No entry for any `set_lamports_per_byte_to_*` feature.

**`/root/firedancer/src/flamenco/runtime/fd_runtime.c`** — `fd_compute_and_apply_new_feature_activations` (lines 565-615): handles:
- `deprecate_rent_exemption_threshold` ✓
- `vote_state_v4` ✓
- `replace_spl_token_with_p_token` ✓
- `upgrade_bpf_stake_program_to_v5` ✓
- **SIMD-0437 features: NOT PRESENT**

No code anywhere in FD reads or writes the new `lamports_per_byte_year` value when any SIMD-0437 feature activates.

### Agave — Full Implementation

**`/root/agave/runtime/src/bank.rs`**, lines 5672–5704:

```rust
// SIMD-0437 feature gates: all assume rent exemption threshold has been deprecated
// (SIMD-0194), so rent.lamports_per_byte_year can be set directly.
let rent_feature_gates = [
    (feature_set::set_lamports_per_byte_to_6333::id(), 6333u64),
    (feature_set::set_lamports_per_byte_to_5080::id(), 5080u64),
    (feature_set::set_lamports_per_byte_to_2575::id(), 2575u64),
    (feature_set::set_lamports_per_byte_to_1322::id(), 1322u64),
    (feature_set::set_lamports_per_byte_to_696::id(),  696u64),
];
for (feature_id, lamports_per_byte_year) in rent_feature_gates {
    if new_feature_activations.contains(&feature_id) {
        self.rent_collector.rent.lamports_per_byte_year = lamports_per_byte_year;
        self.update_rent();   // writes Rent sysvar account
    }
}
```

`update_rent()` (line 2434):
```rust
fn update_rent(&self) {
    self.update_sysvar_account(&sysvar::rent::id(), |account| {
        create_account(&self.rent_collector.rent, ...)
    });
}
```

This **writes the Rent sysvar account** with the new `lamports_per_byte_year`. This account is part of the bank hash.

---

## Divergence Scenario

1. One of the five SIMD-0437 features (e.g., `set_lamports_per_byte_to_6333`) activates on mainnet
2. Agave: at the epoch boundary, sets `rent_collector.rent.lamports_per_byte_year = 6333` and calls `update_rent()` → writes new Rent sysvar account to the accounts DB → contributes to bank hash
3. FD: at the same epoch boundary, does nothing → Rent sysvar account has old `lamports_per_byte_year` → contributes different hash
4. **Bank hash mismatch at that epoch** → FD diverges from Agave → consensus failure

---

## Agave Feature Definitions

**`/root/agave/feature-set/src/lib.rs`**, lines 1264–1292:

```rust
pub mod set_lamports_per_byte_to_6333 {
    solana_pubkey::declare_id!("4a6f7o7iTcA8hRDCrPLkSatnt5Ykxiu36wo5p1Tt12wC");
    pub const LAMPORTS_PER_BYTE: u64 = 6333;
}
pub mod set_lamports_per_byte_to_5080 {
    solana_pubkey::declare_id!("61BtM7BkDEE8Yq5fskEVAQT9mYA8qCejJWoLe5apqg81");
    pub const LAMPORTS_PER_BYTE: u64 = 5080;
}
// ... (3 more)
```

All five appear in `FEATURE_NAMES` (lines 2319–2336) and in `all_enabled()`.

---

## Why Not in Known Issues

The 18 component trackers (#9154–#9178) cover runtime, sandboxing, ELF, etc. None mention SIMD-0437, `set_lamports_per_byte_to_*`, or rent schedule changes.

---

## Severity

**Critical (conditional on Filter 4)** — At the activation epoch, the Rent sysvar account diverges. The Rent sysvar is read by ALL subsequent transactions to compute rent-exemption minimum balances. Both the sysvar hash divergence and the downstream rent calculation divergence would cause an irreconcilable bank hash mismatch.

---

## Recommendation

Implement SIMD-0437 handling in `fd_compute_and_apply_new_feature_activations`:

```c
/* SIMD-0437: lamports_per_byte_year schedule reduction */
static const struct {
  ulong feature_offset;
  ulong lamports_per_byte_year;
} simd_0437_gates[] = {
  { offsetof(fd_features_t, set_lamports_per_byte_to_6333), 6333UL },
  { offsetof(fd_features_t, set_lamports_per_byte_to_5080), 5080UL },
  { offsetof(fd_features_t, set_lamports_per_byte_to_2575), 2575UL },
  { offsetof(fd_features_t, set_lamports_per_byte_to_1322), 1322UL },
  { offsetof(fd_features_t, set_lamports_per_byte_to_696),  696UL  },
};
for( ulong i=0; i<5; i++ ) {
  if( FD_FEATURE_JUST_ACTIVATED_BANK_OFFSET( bank, simd_0437_gates[i].feature_offset ) ) {
    bank->f.rent.lamports_per_uint8_year = simd_0437_gates[i].lamports_per_byte_year;
    fd_sysvar_rent_write( bank, accdb, xid, capture_ctx, &bank->f.rent );
  }
}
```

Also add the five features to `feature_map.json` with their correct pubkeys.
