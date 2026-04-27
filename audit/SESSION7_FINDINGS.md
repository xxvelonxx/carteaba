# SESSION 7 FINDINGS

Date: 2026-04-27
Auditor: Claude Code (claude-sonnet-4-6)
Environment: /root/firedancer (HEAD), /root/agave (v4.0.0-beta.7), /root/solfuzz-agave (HEAD)

---

## AREAS INVESTIGATED

### Remaining SUPPORTED_FEATURES (6 unchecked)

#### validate_chained_block_id

Used in `blockstore_processor.rs:2401` and `window_service.rs:121` to validate that a child block's
chained merkle root matches the parent's block ID. Purely a blockstore/shred-level network
validation; no effect on account state or bank hash.

**Verdict**: Filter A FAIL. Shred-level check only. No bank hash divergence possible.

---

#### increase_tx_account_lock_limit

FD (`fd_executor.c:335`): `fd_ulong_if(feature_active, MAX_TX_ACCOUNT_LOCKS, 64UL)` where
`MAX_TX_ACCOUNT_LOCKS = 128` (`fd_txn.h:116`).

Agave (`bank.rs:3228-3230`): same logic; `MAX_TX_ACCOUNT_LOCKS = 128` (`sanitized.rs:21`).

Both: when active → 128 account lock limit; when inactive → 64.

**Verdict**: Equivalent. No divergence.

---

#### enable_get_epoch_stake_syscall

FD (`fd_vm_syscall_runtime.c:371-415`):
- `var_addr == 0`: CU = `syscall_base_cost`; returns `bank->f.total_epoch_stake`
- `var_addr != 0`: CU = `mem_op_base_cost + syscall_base_cost` (omits `32/250 = 0` term); returns stake from `top_votes` (VAT active) or `vote_stakes` (VAT inactive)

Agave (`syscalls/src/lib.rs:2620-2675`):
- `var_addr == 0`: CU = `syscall_base_cost`; returns `bank.get_current_epoch_total_stake()`
- `var_addr != 0`: CU = `syscall_base_cost + floor(32/250) + mem_op_base = syscall_base + 0 + mem_op_base`; returns `get_current_epoch_vote_accounts().get(addr).map(|(stake,_)| *stake).unwrap_or(0)`

CU cost is identical (FD comment at line 392-394 confirms `32/250 = 0` omission is intentional).
Data values are equivalent given VAT analysis in Session 4.

**Verdict**: Equivalent. No divergence.

---

#### enable_extend_program_checked

FD (`fd_bpf_loader_program.c:2003-2027`):
- `EXTEND_PROGRAM` + feature active → `InvalidInstructionData` ("superseded" message)
- `EXTEND_PROGRAM_CHECKED` + feature inactive → `InvalidInstructionData`
- Normal paths: `common_extend_program(..., 0)` vs `common_extend_program(..., 1)`

Agave (`bpf_loader/src/lib.rs:749-770`): identical logic.

**Verdict**: Equivalent. No divergence.

---

#### enable_bls12_381_syscall

FD (`fd_vm_syscall_curve.c:19-33`, `94-108`): when feature inactive AND curve_id is any BLS12-381
variant → `SyscallError::InvalidAttribute`.

Agave (`syscalls/src/lib.rs:1000-1002`): `if !enable_bls12_381_syscall` → same error.

Feature gating is equivalent. Arithmetic correctness relies on underlying `fd_bls12_381` library
matching Agave's `agave_bls12_381` — not verified at source level (requires test execution).

**Verdict**: Feature gating equivalent. Arithmetic not independently verified.

---

#### enable_alt_bn128_g2_syscalls

FD (`fd_vm_syscall_crypto.c:35-48`): when feature inactive AND `group_op` is any G2 variant →
`SyscallError::InvalidAttribute`.

Agave (`syscalls/src/lib.rs:2119-2129`): identical check for G2_ADD_BE/LE and G2_MUL_BE/LE.

**Verdict**: Equivalent. No divergence.

---

#### reenable_zk_elgamal_proof_program

FD (`fd_zk_elgamal_proof_program.c:314`): `if( !FD_FEATURE_ACTIVE(..., reenable_zk_elgamal_proof_program) )` → disabled.

Agave (`zk-elgamal-proof/src/lib.rs:175-187`): `if disable && !reenable` → disabled.

**Apparent divergence**: FD ignores `disable_zk_elgamal_proof_program` — it disables the program
whenever `reenable` is inactive, regardless of `disable`. Agave only disables when `disable` is
ALSO active.

**Resolution**: `disable_zk_elgamal_proof_program` is in solfuzz HARDCODED_FEATURES (always active).
Therefore, in all testable scenarios (and on mainnet where `disable` is already activated), the two
conditions are equivalent:
- FD: `!reenable → disabled`
- Agave: `disable && !reenable → disabled` (when `disable` is always true: `!reenable → disabled`)

**Verdict**: No divergence on mainnet or in solfuzz. Filter B FAIL for the divergent case (disable
inactive) since solfuzz hardcodes disable=true.

---

### HARDCODED_FEATURES Spot-Checks

#### static_instruction_limit

Agave: when active, rejects transactions with `> MAX_INSTRUCTION_TRACE_LENGTH (64)` instructions.
FD: `FD_TXN_INSTR_MAX = 64` enforced at parse time (`fd_txn_parse.c:122`). Both limit to 64.

**Verdict**: Equivalent.

---

#### mask_out_rent_epoch_in_vm_serialization

FD (`fd_bpf_loader_serialization.c:396`, `664`): `FD_STORE(ulong, serialized_params, ULONG_MAX)` — always writes max.

Agave (`serialization.rs:386-387`, `554-555`): `let rent_epoch = u64::MAX; s.write::<u64>(...)` — always writes max.

Both already unconditionally mask rent_epoch to `u64::MAX`. Feature gate is effectively cleaned up.

**Verdict**: Equivalent.

---

#### sBPF Version Selection

FD (`fd_prog_load.c:65-83`):
```c
v.min_sbpf_version = enable_v0 ? FD_SBPF_V0 : FD_SBPF_V3;
if( enable_v3 )      v.max_sbpf_version = FD_SBPF_V3;
else if( enable_v2 ) v.max_sbpf_version = FD_SBPF_V2;
else if( enable_v1 ) v.max_sbpf_version = FD_SBPF_V1;
else                 v.max_sbpf_version = FD_SBPF_V0;
```

Agave (`syscalls/src/lib.rs:314-328`): identical logic.

**Verdict**: Equivalent.

---

### Partitioned Reward Recalculation from Snapshot

`fd_rewards_recalculate_partitioned_rewards()` (`fd_rewards.c:959-1070`) handles the case where
a node loads from a snapshot while partitioned rewards are in progress. It:
1. Populates `vote_ele_map` from snapshot's `epoch_credits` array
2. When `delay_commission_updates` active, overlays t-3 commission from `snapshot_commission_t_3`
3. Reads `epoch_rewards_sysvar`; if active, calls `calculate_stake_vote_rewards` and `setup_stake_partitions`

This path is NOT exercisable by solfuzz's block harness (solfuzz doesn't do snapshot loading).
Code references Agave `v2.2.14` sources. Filter B FAIL.

**Verdict**: Not testable via solfuzz. Not investigated in depth.

---

### Recent Commits (Filter D Review)

All commits to `src/flamenco/` within the 60-day window since 2026-02-27 that have not been
previously categorized:

| Commit | Date | Description | Status |
|--------|------|-------------|--------|
| 1a69752 | Apr 24 | CPI: remove borrow from fd_vm_prepare_instruction | Refactoring; equivalent behavior; within 60 days |
| 41b3a0b | Apr 23 | sysvar: simplify recent blockhashes decode | Decode simplification; within 60 days |
| 1561b45 | Apr 20 | remove unneeded BLS guard on non-vat top_votes | Correctness fix (was excluding non-BLS validators from top_votes in no_vat path); within 60 days |
| 3f8167e | Apr 21 | vote: return UninitializedAccount for variant 0 | Error code divergence fix; within 60 days |

All within the 60-day Filter D window.

**Note on commit 1561b45**: Before this fix, in the `no_vat` path, FD only inserted V4+BLS validators
into `top_votes_t_1`. This was a genuine divergence from Agave when both (a) VAT is inactive and (b)
`sol_get_epoch_stake` is called for a non-V4/BLS account. However, Filter D FAIL (within 60 days).

---

## CONCLUSIONS

Session 7 completed the final 6 SUPPORTED_FEATURES and spot-checked key HARDCODED_FEATURES.

**No new candidates found.** All 36 SUPPORTED_FEATURES are now fully analyzed across Sessions 1-7.

The complete set of investigated areas now covers:
- All 36 SUPPORTED_FEATURES in solfuzz-agave
- All 61 OPEN features from feature_map.json (Sessions 1-5)
- All HARDCODED_FEATURES with bank-hash-relevant behavior
- All flamenco commits within the 60-day window
- Epoch rewards, stake points, reward partitioning, CPI, sysvar syscalls, ELF loading, VM opcodes

---

## FINAL TOTAL COUNTS ACROSS ALL SESSIONS

| Metric | Count |
|--------|-------|
| SUPPORTED_FEATURES investigated | 36 / 36 (complete) |
| OPEN features from feature_map.json investigated | 61 / 61 (complete) |
| HARDCODED_FEATURES spot-checked | 10+ |
| Confirmed candidates passing all 5 filters | **0** |
| Mainnet-active features with confirmed divergence | **0** |
| Bugs fixed within 60-day window (Filter D) | 6+ |

---

## AREAS NOT INVESTIGATED (would require runtime/test execution)

1. **BLS12-381 arithmetic correctness** — feature gating is equivalent; actual G1/G2/pairing
   computation would need solfuzz test vectors or manual comparison
2. **poseidon_enforce_padding** — hash implementation verified by test vector; padding-acceptance
   boundary at 1-31 bytes would need solfuzz fuzzing to confirm
3. **stricter_abi_and_runtime_constraints** — commented out in solfuzz ("fuzz in 4.0+")
4. **account_data_direct_mapping** — commented out in solfuzz ("fuzz in 4.0+")
5. **ZK ElGamal proof correctness** — individual proof verification logic not analyzed;
   requires crypto test vectors
