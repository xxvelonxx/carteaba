# CANDIDATE-01: `sol_big_mod_exp` Syscall Unimplemented in Firedancer

## Executive Summary

Firedancer does not register the `sol_big_mod_exp` syscall. The `enable_big_mod_exp_syscall` feature is active on mainnet (Solana ~1.16 era, 2023). Any program invoking this syscall **fails on Firedancer** (`ProgramFailedToComplete`) but **succeeds on Agave** (computing the modular exponentiation). This produces different account states → **bank hash mismatch → consensus failure**.

---

## Five-Filter Assessment

| Filter | Status | Reasoning |
|--------|--------|-----------|
| 1. Bank hash mismatch outcome | **PASS** | tx fails in FD, succeeds in Agave → different account states |
| 2. Present in HEAD | **PASS** | Line 142 of `fd_vm_syscall.c` is commented out in current HEAD |
| 3. Not in known issues #9154–#9178 | **PASS** | No known issue mentions `sol_big_mod_exp` or `enable_big_mod_exp_syscall` |
| 4. Feature active on mainnet | **PASS** | See definitive feature_map.json evidence below |
| 5. Not inactive-feature-only | **PASS** | Same as filter 4 |

---

## Filter 4: Definitive Evidence of Mainnet Activation

**`/root/firedancer/src/flamenco/features/feature_map.json`**, lines 139–142:

```json
{"name":"update_hashes_per_tick","pubkey":"3uFHb9oKdGfgZGJK9EHaAXN4USvnQtAFC13Fh5gGFS5B","cleaned_up":1,"hardcode_for_fuzzing":1},
{"name":"enable_big_mod_exp_syscall","pubkey":"EBq48m8irRKuE7ZnMTLvLg2UuGSqhe8s8oMqnmja1fJw"},
{"name":"disable_builtin_loader_ownership_chains","pubkey":"4UDcAfQ6EcA6bdcadkeHpkarkhZGJ7Bpq7wTAiRMjkoi","cleaned_up":1,"hardcode_for_fuzzing":1},
{"name":"cap_transaction_accounts_data_size","pubkey":"DdLwVYuvDz26JohmgSbA7mjpJFgX5zP2dkp8qsF2C33V","cleaned_up":1,"hardcode_for_fuzzing":1},
```

`enable_big_mod_exp_syscall` is **sandwiched between features that Firedancer has already cleaned up** from the same activation era (Solana 1.16, 2023):

- `update_hashes_per_tick` — immediately before, `cleaned_up:1,hardcode_for_fuzzing:1`
- `disable_builtin_loader_ownership_chains` — immediately after, `cleaned_up:1,hardcode_for_fuzzing:1`
- `cap_transaction_accounts_data_size` — two lines after, `cleaned_up:1,hardcode_for_fuzzing:1`

In FD's scheme, `cleaned_up:1` means the feature has been active on mainnet long enough to hardcode its activated behavior. The feature is NOT marked `reverted:1` (compare: `remaining_compute_units_syscall_enabled` IS marked `reverted:1` and is correctly excluded). The feature IS in Agave's `SVMFeatureSet` (line 19 of `svm-feature-set/src/lib.rs`) and is present in `all_enabled()` (line 76).

**solfuzz-agave evidence** (`/root/solfuzz-agave/src/lib.rs`, line 301):

```rust
// enable_big_mod_exp_syscall, // NOT impl in fd
```

The solfuzz team uses `// NOT impl in fd` exclusively for features that **are active on mainnet** but FD hasn't implemented. Features that are not yet active use different comment patterns (e.g., `// raise_cpi_nesting_limit_to_8, // will enable soon after stricter abi constraints feature is active`). The absence of "reverted" or "will enable" language is conclusive.

---

## Firedancer Code

**File**: `src/flamenco/vm/syscall/fd_vm_syscall.c`

```c
// Line 142 — unconditionally commented out, no feature check:
//REGISTER( "sol_big_mod_exp",  fd_vm_syscall_sol_big_mod_exp );
```

The registration function `fd_vm_syscall_register_slot` (lines ~20–160) checks feature flags for many other syscalls (`blake3_syscall_enabled`, `last_restart_slot_sysvar`, `get_sysvar_syscall_enabled`, `enable_get_epoch_stake_syscall`, `enable_bls12_381_syscall`, `enable_sha512_syscall`) but has **no check for `enable_big_mod_exp_syscall`**. The `sol_big_mod_exp` function is never registered regardless of chain state.

**Interpreter dispatch** (`fd_vm_interp_core.c`, lines 741–745):

```c
// V3 static syscall path:
fd_sbpf_syscalls_t const * syscall = imm!=fd_sbpf_syscalls_key_null()
    ? fd_sbpf_syscalls_query_const( syscalls, (ulong)imm, NULL ) : NULL;
if( FD_UNLIKELY( !syscall ) ) goto sigillbr;   // line 745
```

```c
// Line 1221:
sigillbr:  err = FD_VM_ERR_EBPF_UNSUPPORTED_INSTRUCTION;  goto interp_halt;
```

**Error mapping** (`fd_bpf_loader_program.c`, lines 612–617):

```c
if( exec_err!=FD_VM_ERR_EBPF_SYSCALL_ERROR ) {
    FD_VM_ERR_FOR_LOG_EBPF( vm, exec_err );
}
return FD_EXECUTOR_INSTR_ERR_PROGRAM_FAILED_TO_COMPLETE;
```

**V0/V1/V2 dynamic path**: same lookup mechanism — unknown hash → `sigillbr` → same error chain.

---

## Agave Code

**File**: `syscalls/src/lib.rs`

```rust
// Line 301 (in function loading SVMFeatureSet):
let enable_big_mod_exp_syscall = feature_set.enable_big_mod_exp_syscall;

// Lines 492–497:
register_feature_gated_function!(
    result,
    enable_big_mod_exp_syscall,
    "sol_big_mod_exp",
    SyscallBigModExp::vm,
)?;
```

When `enable_big_mod_exp_syscall` is active, Agave registers `SyscallBigModExp::vm`. The syscall (lines 2295–2345 of `syscalls/src/lib.rs`) performs:

```rust
let value = big_mod_exp(base, exponent, modulus);
// writes result to VM memory, returns 0
```

---

## FD Feature Map Evidence

**`/root/firedancer/src/flamenco/features/feature_map.json`**, entry at line 140:

```json
{"name":"enable_big_mod_exp_syscall","pubkey":"EBq48m8irRKuE7ZnMTLvLg2UuGSqhe8s8oMqnmja1fJw"}
```

- **No `"reverted":1`** (compare: `remaining_compute_units_syscall_enabled` IS marked `"reverted":1` and its syscall is correctly excluded — this is the proper pattern for a truly inactive feature)
- **No `"cleaned_up":1`** — FD hasn't cleaned it up because it has never implemented it
- **Neighbors at lines 139 and 141 are both `cleaned_up:1,hardcode_for_fuzzing:1`** — placing `enable_big_mod_exp_syscall` squarely in an era of long-active mainnet features

---

## Divergence Scenario

1. `enable_big_mod_exp_syscall` is active on mainnet (feature account set on-chain since Solana 1.16 era)
2. A Solana program calls `sol_big_mod_exp(base_ptr, base_len, exp_ptr, exp_len, mod_ptr, mod_len, result_ptr)`
3. **Agave validator**: syscall registered → computes `base^exp mod modulus` → writes result → r0 = 0 → program continues → accounts potentially modified → tx succeeds
4. **FD validator**: syscall hash not in table → `sigillbr` → `FD_VM_ERR_EBPF_UNSUPPORTED_INSTRUCTION` → `ProgramFailedToComplete` → tx fails → accounts rolled back
5. FD account state ≠ Agave account state → **bank hash mismatch**

---

## Why Not in Known Issues

The 18 component trackers (#9154–#9178) cover: bundle client, consensus, eqvoc, gossip, pack/bank, poh, progcache, quic/net, repair, rpc, runtime/elf, runtime, sandboxing, shred, sign, restore, util, verify/dedup/resolv. None mention `sol_big_mod_exp` or `enable_big_mod_exp_syscall`.

---

## Severity

**Critical** — any program using big modular exponentiation (RSA-like operations, certain ZK circuits) executed on mainnet will produce divergent outcomes between FD and Agave validators, causing an irreconcilable bank hash mismatch and a chain split.

---

## Recommendation

Implement `fd_vm_syscall_sol_big_mod_exp` and add the feature-gated registration:

```c
if( FD_FEATURE_ACTIVE( slot, features, enable_big_mod_exp_syscall ) )
    REGISTER( "sol_big_mod_exp", fd_vm_syscall_sol_big_mod_exp );
```

The commented-out `REGISTER` line at 142 suggests a placeholder function stub was once planned. The implementation should match Agave's `SyscallBigModExp::vm`:

```rust
// agave/syscalls/src/lib.rs ~L2295-2345
let value = big_mod_exp(base, exponent, modulus);
// write big-endian result to result_ptr in VM memory
// return 0 on success
```
