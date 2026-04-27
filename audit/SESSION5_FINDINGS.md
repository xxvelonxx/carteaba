# SESSION 5 FINDINGS

Date: 2026-04-27
Auditor: Claude Code (claude-sonnet-4-6)
Environment: /root/firedancer (HEAD), /root/agave (v4.0.0-beta.7), /root/solfuzz-agave (HEAD)

---

## AREAS INVESTIGATED

### 4 Features Absent from Solfuzz

From Session 4, 4 features were identified as absent from both SUPPORTED_FEATURES and HARDCODED_FEATURES in solfuzz-agave. These were investigated here.

#### virtual_address_space_adjustments (7VgiehxNxu53KdxgLspGQY8myE6f7UokaWa4jsGcaSz)

When ACTIVE in Agave:
- `enable_stack_frame_gaps = false` → stack gaps disabled
- `aligned_memory_mapping = false` → UnalignedMemoryMapping (binary search)

FD: always uses upper-bits region lookup (equivalent to AlignedMemoryMapping).
Stack frame gap logic: controlled by `FD_VM_SBPF_STACK_FRAME_GAPS(sbpf_version) && !virtual_address_space_adjustments` — equivalent to Agave.

For standard 4/5 memory regions at fixed vaddrs (0x0, 0x100000000, 0x200000000, 0x300000000, 0x400000000), AlignedMemoryMapping and UnalignedMemoryMapping produce identical results. No divergence for any standard program.

**Verdict**: No confirmed divergence. Filter B FAILS (not in solfuzz). Not reportable.

#### syscall_parameter_address_restrictions (EDGMC5kxFxGk4ixsNkGt8bW7QL5hDMXnbwaZvYMwNfzF)

Agave (`syscalls/src/sysvar.rs:21-27`): when active AND `var_addr >= MM_INPUT_START` → return `InvalidPointer`.
FD (`fd_vm_syscall_runtime.c:98-101`): when active AND `out_vaddr >= FD_VM_MEM_MAP_INPUT_REGION_START` → return `FD_VM_ERR_INVAL`.

Equivalent. Both reject sysvar write destinations in the input region.

**Verdict**: No divergence. Filter B FAILS (not in solfuzz). Not reportable.

#### enable_sha512_syscall (s512oDwgx8hjMnaQjXfqqrZroVj4HvC6TkN3iSSWXCh)

FD (`fd_vm_syscall.c:96-97`): registers `sol_sha512` syscall when feature active.
Agave v4.0.0-beta.7: NO sha512 implementation at all — `sol_sha512` is not registered under any feature.

Feature pubkey was placeholder `ToDo111...` until April 15, 2026 (commit `8d530f9`). Only 12 days ago. Almost certainly INACTIVE on mainnet.

If active on mainnet:
- FD: any program calling `sol_sha512` succeeds (computes SHA-512)
- Agave: fails with unknown syscall → different transaction outcome → bank hash divergence

**Verdict**: Potential divergence IF active on mainnet. Filter B FAILS (not in solfuzz). Needs RPC verification. Very likely inactive given feature pubkey just assigned 12 days ago.

#### devnet_and_testnet (DT4n6ABDqs6w4bnfwrXT9rsprcPf6cdDga1egctaPkLC)

Used in `get_inflation_start_slot()` (`fd_rewards.c:49-55`) to determine the epoch from which inflation counting begins. Naming suggests testnet/devnet-only use.

**Verdict**: Low priority. Likely inactive on mainnet. Filter B FAILS. Not investigated further.

---

### Syscall Registration Comparison

Full comparison of FD vs Agave syscall registration:

| Syscall | FD gating | Agave gating |
|---------|-----------|-------------|
| sol_sha256 | unconditional | unconditional |
| sol_keccak256 | unconditional | unconditional |
| sol_blake3 | `blake3_syscall_enabled` | `blake3_syscall_enabled` |
| sol_sha512 | `enable_sha512_syscall` | **NOT REGISTERED** |
| sol_curve_{validate_point,group_op,multiscalar_mul} | unconditional | `curve25519_syscall_enabled` |
| sol_alt_bn128_{group_op,compression} | unconditional | `enable_alt_bn128_syscall`, `enable_alt_bn128_compression_syscall` |
| sol_poseidon | unconditional | `enable_poseidon_syscall` |
| sol_curve_{decompress,pairing_map} | `enable_bls12_381_syscall` | `enable_bls12_381_syscall` |

The curve25519, alt_bn128, and poseidon "mismatch" (FD unconditional vs Agave feature-gated) is not a divergence because those features are in solfuzz's HARDCODED_FEATURES (always active). FD and Agave agree in all test scenarios and on mainnet (features are already active).

The sha512 "mismatch" (FD feature-gated, Agave not registered) is a genuine implementation difference, but Filter B fails.

---

### Epoch Reward Partitioning

FD (`fd_stake_rewards.c:272-277`):
```c
fd_siphash13_t * hasher = fd_siphash13_init( sip, 0UL, 0UL );
fd_siphash13_append( hasher, parent_blockhash.hash, 32 );
fd_siphash13_append( hasher, pubkey->uc, 32 );
ulong hash64 = fd_siphash13_fini( hasher );
ulong partition_index = (ulong)((uint128)partition_cnt * (uint128)hash64 / ((uint128)ULONG_MAX + 1));
```

Agave (`epoch-rewards-hasher-3.1.0/src/lib.rs`):
```rust
let mut hasher = SipHasher13::new();  // k0=k1=0
hasher.write(seed.as_ref());  // 32 bytes of blockhash
// per pubkey:
hasher.clone().write(address.as_ref());  // 32 bytes
hash64 = hasher.finish();
(partitions as u128) * u128::from(hash64) / (u64::MAX as u128 + 1)
```

Both: SipHash-1-3 with k0=k1=0, feeding 32B blockhash then 32B pubkey. Same formula. **Equivalent.**

---

### Stake Points Calculation

FD (`fd_rewards.c:126-173`) vs Agave (`inflation_rewards/points.rs:126-227`):

Both implement the same 3-case logic:
1. `credits_in_stake < initial_epoch_credits`: earned = `final - initial`
2. `credits_in_stake < final_epoch_credits`: earned = `final - new_credits_observed`
3. else: earned = 0

`new_credits_observed = max(new_credits_observed, final_epoch_credits)` in both.
FD early-exits when `final_epoch_credits <= credits_in_stake` (optimization; identical result to Agave's no-skip).

**Verdict**: Equivalent. No divergence.

---

### CPI Restructure (Commit 4ad0b1b, April 24)

Restructured `fd_vm_syscall_cpi_common.c` to match Agave v4.0.0-beta.7 behavior.
Key change: All accounts are now pushed to `translated_accounts` (not just writable ones).
`update_caller_account_region = is_writable || update_caller` matches Agave's logic exactly.

New code verified correct against Agave's `translate_accounts_common` (`program-runtime/src/cpi.rs:1049-1193`).

---

### Recent Commits (Filter D — Within 60 Days)

| Commit | Date | Bug | Verdict |
|--------|------|-----|---------|
| a793e37 | Apr 23 | Clock ts signed overflow | Within 60 days → FAILS |
| 3f8167e | Apr 21 | Vote variant 0 error code | Within 60 days → FAILS |
| 4ad0b1b | Apr 24 | CPI restructure (fix) | Correct match of Agave now |
| 9ea4e56 | Apr 22 | Sysvar syscall alignment | Within 60 days → FAILS |
| 87ef4c3 | Apr 22 | CPI ACC_INFO_DATA_VADDR | Within 60 days → FAILS |
| 8d530f9 | Apr 15 | sha512 feature pubkey | Pubkey placeholder replaced |

All recent bug fixes are within the 60-day Filter D window.

---

### Other SUPPORTED_FEATURES Checked

| Feature | Verdict |
|---------|---------|
| blake3_syscall_enabled | Equivalent (sha implementation matches) |
| increase_cpi_account_info_limit | Equivalent (same 3-tier limit logic) |
| require_static_nonce_account | Equivalent (same ALT index check) |
| provide_instruction_data_offset_in_vm_r2 | Equivalent (r2_initial_value = instruction_data_offset when active) |
| poseidon_enforce_padding | Both gate on same feature; padding implementation differences require test harness |
| bls_pubkey_management_in_vote_account | Has dedicated backtest coverage; implementation verified |
| upgrade_bpf_stake_program_to_v5 | Migration path; has backtest coverage |

---

## RPC VERIFICATION NEEDED

The following 4 pubkeys need mainnet status verification:

| Feature | Pubkey |
|---------|--------|
| devnet_and_testnet | DT4n6ABDqs6w4bnfwrXT9rsprcPf6cdDga1egctaPkLC |
| syscall_parameter_address_restrictions | EDGMC5kxFxGk4ixsNkGt8bW7QL5hDMXnbwaZvYMwNfzF |
| virtual_address_space_adjustments | 7VgiehxNxu53KdxgLspGQY8myE6f7UokaWa4jsGcaSz |
| enable_sha512_syscall | s512oDwgx8hjMnaQjXfqqrZroVj4HvC6TkN3iSSWXCh |

---

## CONCLUSIONS

Session 5 investigated: 4 features absent from solfuzz, syscall registration, epoch reward partitioning, stake points calculation, and CPI restructure.

**No new candidates found.** The only genuine code divergence is `enable_sha512_syscall` (FD registers sha512, Agave doesn't), but Filter B fails and the feature pubkey was only assigned 12 days ago (almost certainly inactive on mainnet).

---

## TOTAL COUNTS ACROSS ALL SESSIONS

| Metric | Count |
|--------|-------|
| SUPPORTED_FEATURES investigated | 36 (all) |
| Features absent from solfuzz investigated | 4 |
| Confirmed candidates passing all 5 filters | 0 |
| Mainnet-active features with divergence | 0 confirmed |
| Features needing RPC verification | 4 (new batch) |

---

## AREAS STILL UNINVESTIGATED

1. **sBPF v3 ELF loading divergences** — stricter header validation, lower_rodata_vaddr edge cases in verifier
2. **poseidon_enforce_padding** — padding implementation comparison requires running solfuzz tests
3. **account_data_direct_mapping** — commented out in solfuzz; potential complex divergences
4. **ZK ElGamal proof program** — complex crypto; requires test execution
5. **Core BPF migrations** — stake v5, spl_token→p_token; complex account state changes
