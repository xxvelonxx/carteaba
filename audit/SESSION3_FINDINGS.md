# SESSION 3 FINDINGS

Date: 2026-04-27
Auditor: Claude Code (claude-sonnet-4-6)
Environment: /root/firedancer (HEAD), /root/agave (v4.0.0-beta.7), /root/solfuzz-agave (HEAD)

---

## CANDIDATE-03 STATUS: ELIMINATED

Per user RPC verification:
- Feature account `sProgVaNWkYdP2eTRAy1CPrgb3b9p8yXCASrPEqo6VJ`: `value: null` (inactive)
- Source buffer `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv`: `value: null` (doesn't exist)
- SIMD-0204 is in "Idea" status — not even in Review
- FIXME comment in public repo = "consciously decided not to fix" per Immunefi scope clause
- **Filter 4 FAIL (inactive), Filter 5 FAIL, known-issue clause triggered**

---

## METHODOLOGY CORRECTION

Per user instruction: Phase 2 (mainnet RPC feature activation check) must precede Phase 3
(code divergence search). This session was conducted without RPC access, so findings below
are UNVERIFIED against mainnet activation status unless noted.

---

## AREAS INVESTIGATED (Session 3)

### SUPPORTED_FEATURES Systematic Pass (continued)

**`relax_programdata_account_check_migration`**: Parameter to Core BPF migrations that
relaxes programdata account existence checks. Changes when migrations FAIL but doesn't
independently write account state. No divergence in the happy path.

**`create_account_allow_prefund`**: FD has implementation at `fd_system_program.c:313`.
Behavior matches Agave system program. No divergence.

**`bls_pubkey_management_in_vote_account`**: FD implements in `fd_vote_program.c:1627`.
Instruction-level feature, correctly gated. No divergence found.

**`increase_cpi_account_info_limit`**: FD implements correctly:
- Without: max 128 account infos (`FD_CPI_MAX_ACCOUNT_INFOS = 128`)
- With: max 255 account infos (`FD_CPI_MAX_ACCOUNT_INFOS_SIMD_0339 = 255`)
- Matches Agave's `MAX_CPI_ACCOUNT_INFOS=128`, `MAX_CPI_ACCOUNT_INFOS_SIMD_0339=255`
- **No divergence**

**`poseidon_enforce_padding`**: Correctly gated in FD `fd_vm_syscall_crypto.c:374`. No divergence.

**`provide_instruction_data_offset_in_vm_r2`**: FD implements at `fd_bpf_loader_program.c:390`.
Sets r2 to instruction data offset. No divergence.

**`deprecate_rent_exemption_threshold`**: FD writes updated Rent sysvar with:
- `lamports_per_uint8_year = existing * exemption_threshold`
- `exemption_threshold = 1.0`
- `burn_percent` kept from bank (NOT explicitly set to DEFAULT_BURN_PERCENT)
Agave explicitly sets `burn_percent: DEFAULT_BURN_PERCENT (50)`. In practice, both will
be 50 since `pico_inflation`/`full_inflation` are HARDCODED and set burn_percent=50.
**No divergence in solfuzz context.**

**`enable_extend_program_checked`**: Correctly implemented in FD. No divergence.

**`enable_get_epoch_stake_syscall`**: FD implements correctly. Syscall is read-only
(no account writes). No bank hash impact.

---

## KEY FINDINGS: FEATURES NOT IN FD'S FEATURE_MAP

Found 14 features in Agave's FEATURE_NAMES that FD doesn't track. Most are pre-deployment
(placeholder pubkeys). Key ones with real pubkeys:

### `raise_cpi_nesting_limit_to_8` (SIMD-0268)

**Pubkey**: `6TkHkRmP7JZy1fdM6fg5uXn76wChQBWGokHBJzrLB3mj` (non-placeholder)

**FD behavior**: `FD_MAX_INSTRUCTION_STACK_DEPTH = 5` hardcoded in `fd_runtime_const.h:94`.
No feature gate check, no implementation of SIMD-0268.

**Agave behavior** (`execution_budget.rs`):
- Without feature: max stack depth 5 (`MAX_INSTRUCTION_STACK_DEPTH = 5`)
- With feature: max stack depth 9 (`MAX_INSTRUCTION_STACK_DEPTH_SIMD_0268 = 9`, allows 8 CPI levels)

**Impact if active on mainnet**: Transactions nesting CPI 5-8 levels deep would succeed
in Agave but fail in FD with "call stack depth exceeded" → different account states →
bank hash mismatch.

**Filter B**: FAIL — `raise_cpi_nesting_limit_to_8` is commented out in solfuzz
(`// raise_cpi_nesting_limit_to_8, // will enable soon after stricter abi constraints feature is active`)
Not testable via current solfuzz.

**Status**: NEEDS RPC VERIFICATION. Potentially high-severity if active on mainnet, but
fails Filter B as currently defined.

---

### `direct_account_pointers_in_program_input` (SIMD-0449)

**Pubkey**: `ptrXWLkSDMZZmZN8GAT6W5yW4EvYByfw6cRRHbXwQNS` (non-placeholder)

Changes how account data is mapped in VM input buffer (ABIv1). FD has NO implementation
(not in feature_map.json). Would change program serialization if active.

**Filter B**: FAIL — Not in solfuzz at all.

---

## GRADUATED IN FD BUT IN SOLFUZZ SUPPORTED_FEATURES

Features with `cleaned_up=1` in FD's feature_map.json that solfuzz places in SUPPORTED
(not HARDCODED), allowing tests with the feature OFF:

### `enable_secp256r1_precompile` (cleaned_up=1, hardcode_for_fuzzing=1 in FD)

**Pubkey**: `srremy31J5Y25FrAApwVb9kZcfXbusYMMsvTK9aWv5q`

**FD behavior** (cleaned_up=1):
- `fd_precompiles.c:423`: secp256r1 registered with `NO_ENABLE_FEATURE_ID` → always active
- `fd_executor.c:726`: always counts secp256r1 sigs for fee (no feature gate check)

**Agave behavior**:
- Precompile gated on feature: `Some(enable_secp256r1_precompile::id())`
- Fee: `u64::from(enable_secp256r1_precompile).wrapping_mul(num_secp256r1_signatures)`

**Divergence when feature is OFF in solfuzz**:
1. Instruction-level: different execution result (FD runs precompile, Agave fails) — Filter A FAIL (stateless, no account state change)
2. Block-level fee: FD always charges secp256r1 sig fees, Agave doesn't → fee payer different lamport balance → different bank hash

**Filter A**: PASS (via block harness)
**Filter B**: PASS — in solfuzz SUPPORTED_FEATURES (line 306), testable via block harness
**Filter C**: UNKNOWN (no GitHub access to check known issues)
**Filter D**: PASS — FD still has `NO_ENABLE_FEATURE_ID` in HEAD, fee always counts secp256r1 sigs

**RPC STATUS**: UNKNOWN — needs verification of `srremy31J5Y25FrAApwVb9kZcfXbusYMMsvTK9aWv5q`

**Note**: FD's feature_map.json marks this as `hardcode_for_fuzzing=1`, meaning FD INTENDS
this to be hardcoded (always active). Solfuzz has it as SUPPORTED (can be off). This
discrepancy in solfuzz configuration means the block harness CAN exercise the divergence
but only when the feature is set to OFF in the test input.

---

## SESSION 3 RULE-OUTS

| Feature | Reason |
|---------|--------|
| relax_programdata_account_check_migration | Modifier to migrations, not independent |
| create_account_allow_prefund | FD implementation correct |
| bls_pubkey_management_in_vote_account | Instruction-level, correctly gated |
| increase_cpi_account_info_limit | FD implementation matches Agave |
| poseidon_enforce_padding | Correctly gated |
| provide_instruction_data_offset_in_vm_r2 | Correctly implemented |
| deprecate_rent_exemption_threshold | burn_percent same value in practice |
| enable_extend_program_checked | Correctly implemented |
| enable_get_epoch_stake_syscall | Read-only syscall |
| commission_rate_in_basis_points | Placeholder pubkey, not on mainnet |
| block_revenue_sharing | Placeholder pubkey, not on mainnet |
| vote_account_initialize_v2 | Placeholder pubkey, not on mainnet |
| custom_commission_collector | Placeholder pubkey, not on mainnet |

---

## RPC VERIFICATION NEEDED

Priority queries for the next session with RPC access:

```bash
# 1. raise_cpi_nesting_limit_to_8 — critical if active, FD doesn't implement
curl -X POST https://api.mainnet-beta.solana.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getAccountInfo","params":["6TkHkRmP7JZy1fdM6fg5uXn76wChQBWGokHBJzrLB3mj",{"encoding":"base64","commitment":"finalized"}]}'

# 2. direct_account_pointers_in_program_input — no FD implementation  
curl -X POST https://api.mainnet-beta.solana.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"getAccountInfo","params":["ptrXWLkSDMZZmZN8GAT6W5yW4EvYByfw6cRRHbXwQNS",{"encoding":"base64","commitment":"finalized"}]}'

# 3. enable_secp256r1_precompile — FD graduated (cleaned_up=1) but in solfuzz SUPPORTED
curl -X POST https://api.mainnet-beta.solana.com -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"getAccountInfo","params":["srremy31J5Y25FrAApwVb9kZcfXbusYMMsvTK9aWv5q",{"encoding":"base64","commitment":"finalized"}]}'
```

If `raise_cpi_nesting_limit_to_8` is active: potentially Critical severity (all CPI-heavy
programs nesting > 4 levels would diverge) even though it fails Filter B.

If `enable_secp256r1_precompile` is INACTIVE: fee divergence becomes testable in solfuzz
block harness (potential High/Critical depending on scope).

If `enable_secp256r1_precompile` is ACTIVE: FD and Agave agree → no divergence.

---

## HARDCODED_FEATURES ANALYSIS

Checked HARDCODED_FEATURES graduation in FD:
- Most HARDCODED features are graduated (cleaned_up=1) in FD — correctly aligned
- `vote_state_v4`: OPEN (not graduated) in FD, HARDCODED in solfuzz — FD checks feature gate
  but it's always active, so no practical divergence from the gate check itself
- `enable_sbpf_v1_deployment_and_execution`, `enable_sbpf_v2_deployment_and_execution`: OPEN in FD,
  HARDCODED in solfuzz — same reasoning, gate always returns true in testing

---

## CONCLUSION

Session 3 did not find a new candidate passing all 5 filters. The most promising lead
(`enable_secp256r1_precompile` fee divergence) needs RPC verification to determine if
the feature is active on mainnet (which would mean FD and Agave always agree, no divergence)
or inactive (which would mean the divergence is testable via solfuzz block harness).

The approach must shift to Phase 2 first: obtain the list of mainnet-active features via
RPC, then search for divergences only in those active features.
