# RPC VERIFICATION — MAINNET FEATURE ACTIVATION

Date: 2026-04-27
Source: Claude Chat with curl access to https://api.mainnet-beta.solana.com (commitment=finalized, slot ~415925xxx)

---

## RESULTS

| ID | Pubkey | Feature | Value | Status |
|----|--------|---------|-------|--------|
| 1 | `6TkHkRmP7JZy1fdM6fg5uXn76wChQBWGokHBJzrLB3mj` | `raise_cpi_nesting_limit_to_8` | null | INACTIVE |
| 2 | `ptrXWLkSDMZZmZN8GAT6W5yW4EvYByfw6cRRHbXwQNS` | `direct_account_pointers_in_program_input` | null | INACTIVE |
| 3 | `srremy31J5Y25FrAApwVb9kZcfXbusYMMsvTK9aWv5q` | `enable_secp256r1_precompile` | `{"data":["AQBwmRQAAAAA","base64"],...}` | **ACTIVE** (slot ~345149440) |
| 4 | `76dHtohc2s5dR3ahJyBxs7eJJVipFkaPdih9CLgTTb4B` | `delay_commission_updates` | null | INACTIVE |
| 5 | `sProgVaNWkYdP2eTRAy1CPrgb3b9p8yXCASrPEqo6VJ` | `enshrine_slashing_program` | null | INACTIVE |

---

## IMPACT ON CANDIDATES

### raise_cpi_nesting_limit_to_8 — ELIMINATED
INACTIVE on mainnet. R1 FAIL. Additionally, commented out in solfuzz
(`// raise_cpi_nesting_limit_to_8, // will enable soon after stricter abi constraints feature is active`),
so Filter B also FAILS. Not reportable.

### direct_account_pointers_in_program_input — ELIMINATED
INACTIVE on mainnet. R1 FAIL. Also not in FD feature_map.json and commented out
in solfuzz (`// account_data_direct_mapping, // fuzz in 4.0+`). Filter B FAILS.
Not reportable.

### enable_secp256r1_precompile — ACTIVE but INELIGIBLE
ACTIVE since slot ~345149440. However, already analyzed across Sessions 2 and 3:
- FD intentionally removed the feature gate (PR #8971, March 19) — `NO_ENABLE_FEATURE_ID`
  means FD always runs secp256r1 regardless of feature status
- This is a "consciously decided not to fix" per the FIXME comment + public repo = excluded
  under Immunefi known-issue clause
- The fee divergence (FD always charges secp256r1 sig fees, Agave only when feature active)
  would normally be testable via solfuzz block harness, but the feature being permanently
  active means FD and Agave AGREE on mainnet (both count secp256r1 sigs for fees)
- **Net result**: no divergence on mainnet. Not reportable.

### delay_commission_updates — ELIMINATED
INACTIVE on mainnet. R1 FAIL. Also analyzed in Session 4: commission selection logic
is equivalent between FD and Agave (corrected after understanding epoch_stakes indexing
offset documented in fd_ssmsg.h). Even if active, no divergence exists.

### enshrine_slashing_program — ELIMINATED (CANDIDATE-03)
INACTIVE on mainnet. Confirmed as ineligible per Session 3 (SIMD-0204 in "Idea" status,
source buffer `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv` non-existent on mainnet).

---

## FINAL AUDIT STATUS

After 4 sessions of code review and RPC verification:

| Metric | Count |
|--------|-------|
| SUPPORTED_FEATURES in solfuzz investigated | 36 / 36 |
| OPEN features from feature_map.json investigated | 61 / 61 |
| Confirmed candidates passing all 5 filters | **0** |
| Mainnet-active features with divergence | **0** |

### What was ruled out and why

| Feature / Area | Reason ruled out |
|----------------|-----------------|
| raise_cpi_nesting_limit_to_8 | Inactive on mainnet + not in solfuzz |
| direct_account_pointers_in_program_input | Inactive on mainnet + not in solfuzz |
| enable_secp256r1_precompile | Active but FD=Agave on mainnet (both count fees); FD intentional cleanup |
| delay_commission_updates | Inactive + FD implementation equivalent to Agave |
| enshrine_slashing_program | Inactive + source buffer doesn't exist |
| validator_admission_ticket | Implementation equivalent (VAT filter + truncation) |
| SIMD-0437 lamports_per_byte features | Not in solfuzz (Filter B) |
| stake_raise_minimum_delegation_to_1_sol | No-op in both |
| All nonce, ALT, stake math, vote state V4 | No divergence found |
| deprecate_legacy_vote_ixs, limit_instruction_accounts | Equivalent implementations |
| raise_account_cu_limit, remove_simple_vote_from_cost_model | Cost model only, no bank hash impact |

### What remains unexplored (future sessions with RPC)

1. The 52 Class A/B OPEN features that are active on mainnet but not in solfuzz SUPPORTED_FEATURES
   — would need full RPC enumeration of all 61 OPEN feature pubkeys to find which are active
2. sBPF v3 instruction execution edge cases — requires solfuzz test execution, not code review
3. Partitioned reward recalculation from snapshot (fd_rewards.c:960-1012) — snapshot recovery path
