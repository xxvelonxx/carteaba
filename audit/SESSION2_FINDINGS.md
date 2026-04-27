# SESSION 2 ADDITIONAL INVESTIGATION

Date: 2026-04-27
Auditor: Claude Code (claude-sonnet-4-6)
Environment: /root/firedancer (HEAD), /root/agave (v4.0.0-beta.7), /root/solfuzz-agave (HEAD)

---

## Areas Investigated (Session 2)

### ZK ElGamal Proof Program (`reenable_zk_elgamal_proof_program`)

- **FD** (`fd_zk_elgamal_proof_program.c:314`):
  ```c
  if( FD_LIKELY( !FD_FEATURE_ACTIVE_BANK( ctx->bank, reenable_zk_elgamal_proof_program ) ) ) {
  ```
- **Agave** (`programs/zk-elgamal-proof/src/lib.rs:175-187`):
  ```rust
  if disable_zk_elgamal_proof_program && !reenable_zk_elgamal_proof_program { ... }
  ```
- **Analysis**: `disable_zk_elgamal_proof_program` is HARDCODED in solfuzz (always true). When
  `disable` is always true, FD's check `!reenable` is algebraically equivalent to Agave's
  `disable && !reenable`. **No divergence in solfuzz context.**

### alt_bn128 / BLS12-381 Syscalls

- `alt_bn128_little_endian`, `enable_alt_bn128_g2_syscalls`, `enable_bls12_381_syscall`
- All implemented in FD's `fd_vm_syscall_crypto.c` and `fd_vm_syscall_curve.c`
- Feature gate logic matches Agave exactly
- **No divergence.**

### secp256r1 Precompile Fee Calculation

- **FD** (`fd_executor.c:726-728`): Always counts secp256r1 signatures for fee regardless of
  `enable_secp256r1_precompile` feature status.
- **Agave** (`fee/src/lib.rs:81`): Only counts secp256r1 signatures when feature is active:
  `u64::from(enable_secp256r1_precompile).wrapping_mul(num_secp256r1_signatures)`
- **Divergence exists** at the transaction fee level when `enable_secp256r1_precompile` is OFF.
- **Not exploitable via instruction-level solfuzz harness** — fee calculation is transaction-level,
  not instruction-level. solfuzz only tests instruction execution, not full transaction fee path.
- `enable_secp256r1_precompile` is also in Agave's `deprecated_features()` list — it will not
  activate on mainnet.
- **Filter B: FAIL** (for instruction-level solfuzz). Not documented as a candidate.

### secp256r1 Precompile Always-On in FD

- **FD** (`fd_precompiles.c:424`): `{ &fd_solana_secp256r1_program_id, NO_ENABLE_FEATURE_ID, ... }`
- **Agave** (`precompiles/src/lib.rs:71`): Gated on `Some(enable_secp256r1_precompile::id())`
- When `enable_secp256r1_precompile` is NOT active and secp256r1 instruction is dispatched:
  - FD: runs secp256r1 precompile → success/failure based on signature
  - Agave solfuzz: `is_precompile()` returns false → `process_instruction` called → fails
  - **Different execution outcomes but same account state** (precompiles are stateless)
- **Filter A: FAIL** (no bank hash mismatch for single instruction — precompiles don't write state)

### p-Token Migration (`replace_spl_token_with_p_token`)

- Buffer address: FD `PTOKEN_PROG_BUFFER_ID` decodes to `ptok6rngomXrDbWf5v5Mkmu5CEbB51hzSCPDoj9DrvF`
- Agave `PTOKEN_PROGRAM_BUFFER` = `ptok6rngomXrDbWf5v5Mkmu5CEbB51hzSCPDoj9DrvF`
- **Addresses match.** `fd_upgrade_loader_v2_program_with_loader_v3_program` doesn't use
  verified build hash, so no hash mismatch issue analogous to CANDIDATE-03.
- **No divergence.**

### Stake Program v5 Upgrade (`upgrade_bpf_stake_program_to_v5`)

- FD uses `fd_upgrade_core_bpf_program` — buffer-to-program upgrade without verified hash check
- Agave uses `upgrade_core_bpf_program` — same approach
- Stake program is already a Core BPF program in both (native implementation not used)
- **No divergence.**

### remove_accounts_delta_hash (HARDCODED)

- FD's `fd_hashes_hash_bank` ALWAYS uses LtHash in bank hash computation (no delta hash)
- This matches the `remove_accounts_delta_hash` HARDCODED behavior in solfuzz
- **No divergence.**

### Core BPF Migration FIXMEs

- `fd_core_bpf_migration.c:622`: `FIXME call fd_directly_invoke_loader_v3_deploy`
- `fd_core_bpf_migration.c:640-641`: `FIXME "remove the built-in program from the bank's list of builtins"` / `"update account data size delta"`
- `fd_core_bpf_migration.c:735`: `FIXME "update account data size delta"`
- **Analysis**: "remove from builtins list" is in-memory, not account state. "update account data
  size delta" affects internal accounting but not account lamports/data used in bank hash.
  These FIXMEs do NOT cause bank hash divergence.

### CPI Restructure (commit 4ad0b1b, April 24, 2026)

- Major rewrite matching Agave v4.0.0-beta.7 control flow
- Key change: `translated_accounts[]` with `update_caller_account_info` and
  `update_caller_account_region` flags replacing separate index arrays
- Post-CPI update path reviewed: matches Agave's `cpi.rs#L942-L957` and `cpi.rs#L959-L973`
- **No divergence found** in the restructured code.

### stake_raise_minimum_delegation_to_1_sol

- In Agave's `deprecated_features()` list AND not used anywhere in runtime code
- FD also has no runtime reference (only in features_generated)
- **Both are no-ops. No divergence.**

### Upgrade Authority in Core BPF Migrations

- `fd_core_bpf_migration.c:440`: TODO "Set the upgrade authority properly"
- Agave's production configs for builtins: slashing program uses `upgrade_authority_address: None`
- All `Some(upgrade_authority::id())` entries are in `#[cfg(test)]` / `test_only` modules
- **FD setting None matches production Agave. No divergence on mainnet.**

---

## Summary

This session confirmed CANDIDATE-03 (wrong verified build hash for slashing program,
`fd_builtin_programs.c:41-44`) as the primary finding. No additional bank-hash-mismatch
candidates passing all 5 filters were found.

The secp256r1 fee divergence and precompile-always-on divergence both fail Filter B in the
context of solfuzz's instruction-level harness.

CANDIDATE-03 status: **CANDIDATE** — pending Filter C (known issues) and RPC activation check.
