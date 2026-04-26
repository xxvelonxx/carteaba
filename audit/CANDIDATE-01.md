# CANDIDATE-01: `sol_big_mod_exp` Syscall Unimplemented in Firedancer

## Executive Summary

Firedancer does not register the `sol_big_mod_exp` syscall. When the `enable_big_mod_exp_syscall` feature is active on mainnet, any program invoking this syscall will **fail on Firedancer** (`ProgramFailedToComplete`) but **succeed on Agave** (computing the modular exponentiation). This produces different account states between validators → **bank hash mismatch → consensus failure**.

---

## Five-Filter Assessment

| Filter | Status | Reasoning |
|--------|--------|-----------|
| 1. Bank hash mismatch outcome | **PASS** | tx fails in FD, succeeds in Agave → different account states |
| 2. Present in HEAD | **PASS** | Line 142 of `fd_vm_syscall.c` is commented out in current HEAD |
| 3. Not in known issues #9154–#9178 | **PASS** | No known issue mentions `sol_big_mod_exp` or `enable_big_mod_exp_syscall` |
| 4. Feature likely active on mainnet | **PASS** | Feature introduced in PR #28503 (Solana ~1.16 era, 2023); surrounding features in Agave's FEATURE_NAMES list are `cleaned_up` in FD; not marked `reverted` in FD; solfuzz labels it "NOT impl in fd" (gap, not "pending feature") |
| 5. Not inactive-feature-only | **PASS** | Same as filter 4 |

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
// Line 301:
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

**`/root/firedancer/src/flamenco/features/feature_map.json`**, entry:

```json
{"name":"enable_big_mod_exp_syscall","pubkey":"EBq48m8irRKuE7ZnMTLvLg2UuGSqhe8s8oMqnmja1fJw"}
```

- **No `"reverted":1`** (compare: `remaining_compute_units_syscall_enabled` IS marked `"reverted":1` and its syscall is correctly excluded from FD — this is the proper pattern for a truly inactive feature)
- **No `"cleaned_up":1`** — FD hasn't cleaned it up because it hasn't implemented it
- Neighboring entries `update_hashes_per_tick` (line 139) and `disable_builtin_loader_ownership_chains` (line 141) both have `"cleaned_up":1,"hardcode_for_fuzzing":1`, placing the `enable_big_mod_exp_syscall` feature squarely in an era of mainnet-activated features that FD has otherwise fully cleaned up

**`/root/solfuzz-agave/src/lib.rs`**, line 301:

```rust
// enable_big_mod_exp_syscall, // NOT impl in fd
```

The comment says "NOT impl in fd" — this is the solfuzz team acknowledging a FD implementation gap, not a note that the feature is pending. Features that are pending activation use different comment patterns (e.g., line 328: `// raise_cpi_nesting_limit_to_8, // will enable soon after stricter abi constraints feature is active`).

---

## Divergence Scenario

1. `enable_big_mod_exp_syscall` is active on mainnet (feature account set on-chain)
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

Implement `fd_vm_syscall_sol_big_mod_exp` (a function stub `fd_vm_syscall_sol_big_mod_exp` is referenced in the commented-out REGISTER line, suggesting a placeholder exists or was planned) and add the feature-gated registration:

```c
if( enable_big_mod_exp_syscall )
    REGISTER( "sol_big_mod_exp", fd_vm_syscall_sol_big_mod_exp );
```

where `enable_big_mod_exp_syscall = FD_FEATURE_ACTIVE( slot, features, enable_big_mod_exp_syscall )`.
