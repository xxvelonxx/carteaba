# SESSION 4 FINDINGS

Date: 2026-04-27
Auditor: Claude Code (claude-sonnet-4-6)
Environment: /root/firedancer (HEAD), /root/agave (v4.0.0-beta.7), /root/solfuzz-agave (HEAD)

---

## AREAS INVESTIGATED

### validator_admission_ticket — VAT Filter (fd_stakes.c:402-820)

**FD filtering criteria** (`fd_refresh_vote_accounts_vat`, `fd_stakes.c:486-506`):
1. Account accessible
2. `fd_vsv_is_correct_size_owner_and_init`: correct size, owner, initialized
3. `fd_vote_account_is_v4_with_bls_pubkey`: V4 format with BLS pubkey present
4. Lamports >= `fd_rent_exempt_minimum_balance(FD_VOTE_STATE_V4_SZ)`

**Agave filtering criteria** (`clone_and_filter_for_vat`, `vote_account.rs:176-231`):
1. `has_bls = vote_state_view().bls_pubkey_compressed().is_some()` — BLS pubkey present
2. `has_stake != 0`
3. Lamports >= `minimum_vote_account_balance` (= rent-exempt for VoteStateV4)

**Truncation behavior** (top-2000):
- Agave: `select_nth_unstable_by` to find floor_stake, then `retain(stake > floor_stake)` — removes ALL ties at boundary
- FD (`fd_top_votes_insert`, `fd_top_votes.c:186-223`): min-heap, when full finds min_stake, removes ALL at min_stake, sets `min_stake_wmark`, future inserts at or below wmark rejected

FD's comment at line 186: "This matches Agave's retain(stake > floor_stake) behavior"

**Verdict**: Logically equivalent. No divergence.

---

### delay_commission_updates — Commission Epoch Selection

**Initial analysis (incorrect)**: Appeared FD uses E-2 commission as highest priority while Agave uses E-1.

**Corrected analysis** (using fd_ssmsg.h:482-485 epoch_stakes documentation):

FD's fd_ssmsg.h explicitly documents Agave's epoch_stakes indexing is offset by 1:
- `epoch_stakes(E-1)` = "represents stakes at beginning of epoch E-2" (captured at E-3/E-2 boundary)
- `epoch_stakes(E)` = "represents stakes at beginning of epoch E-1" (captured at E-2/E-1 boundary)

At the E-1/E boundary (computing rewards for epoch E-1):
- FD `commission_t_3` from `vote_stakes_query_t_2(E-1_fork)` = commission at E-3/E-2 boundary
- Agave `snapshot_epoch_vote_accounts` = `epoch_stakes(E-1)` = commission at E-3/E-2 boundary
- **MATCH**

- FD `commission_t_2` from `vote_stakes_query_t_1(E-1_fork)` = commission at E-2/E-1 boundary
- Agave `rewarded_epoch_vote_accounts` = `epoch_stakes(E)` = commission at E-2/E-1 boundary
- **MATCH**

Priority order is identical: oldest (E-3/E-2) > middle (E-2/E-1) > current.

**Verdict**: Equivalent. No divergence.

---

### deprecate_legacy_vote_ixs

FD (`fd_vote_program.c:1875,1939,2009`): Vote, VoteSwitch, UpdateVoteState, CompactUpdateVoteState instructions return `FD_EXECUTOR_INSTR_ERR_INVALID_INSTR_DATA` when feature active.

Agave (`vote_processor.rs:204,225,242`): Same instructions return `InstructionError::InvalidInstructionData`.

Both fail the transaction with the same error. No account state changes. No bank hash divergence.

**Verdict**: Equivalent. No divergence.

---

### limit_instruction_accounts (SIMD-0406)

- FD (`fd_executor.c:382-389`): Checks `txn->instr[i].acct_cnt > FD_BPF_INSTR_ACCT_MAX` (= 255)
- Agave (`sdk_transactions.rs:93-98`): Checks `instr.accounts.len() > MAX_ACCOUNTS_PER_INSTRUCTION` (= 255, defined in `transaction-context/src/lib.rs:17`)

Same limit (255) in both. Both return `TransactionError::SanitizeFailure`.

**Verdict**: Equivalent. No divergence.

---

### raise_account_cu_limit / remove_simple_vote_from_cost_model

Both features affect cost model (block/account CU limits and vote transaction scheduling). These determine which transactions are INCLUDED in blocks, not how they EXECUTE. No impact on account state or bank hash.

**Verdict**: Cost model features. Filter A FAIL. No divergence.

---

### stake_raise_minimum_delegation_to_1_sol

No runtime implementation in either FD or Agave. Both have it defined in feature_set but no code references it in reward calculation. `stake_minimum_delegation_for_rewards` (the related feature that Agave does check) is commented out of solfuzz as "reverted in fd."

**Verdict**: No-op in both. Filter B FAIL (relevant variant not in solfuzz). No divergence.

---

### Rent Collection (TARGET 5)

`disable_rent_fees_collection` is in solfuzz HARDCODED_FEATURES (always ON). Epoch-level rent sweeps are disabled. Per-transaction rent collection is handled in `load_transaction_account` (`fd_executor.c:420-466`). No epoch rent sweep path exercisable via solfuzz.

**Verdict**: Not testable via solfuzz. No investigation needed.

---

### deprecate_legacy_vote_ixs / sBPF v3 / raise_block_limits_to_100m

- `deprecate_legacy_vote_ixs`: Covered above — equivalent.
- sBPF v3 (`enable_sbpf_v3_deployment_and_execution`): FD implements JMP32, static syscalls, callx_uses_dst_reg correctly gated by sbpf_version in `fd_vm_interp_core.c`. No obvious divergence without running tests.
- `raise_block_limits_to_100m`: Block CU limit change. Not a bank hash concern.

---

## RECENTLY FIXED BUGS (Filter D fails)

| Commit | Date | Description |
|--------|------|-------------|
| 9ea4e56 | April 22 | `is_deprecated` check for sysvar syscalls — fixed (within 60 days) |
| 87ef4c3 | April 22 | VM_SYSCALL_CPI_ACC_INFO_DATA_VADDR check fix — fixed (within 60 days) |

Both bugs were fixed within the last 60 days. Filter D FAIL for both.

---

## SELF-AUDIT CHECKLIST

1. Did I run actual RPC queries against mainnet for every feature candidate? **NO** — RPC blocked
2. Did I verify activated_at fields? **NO** — RPC blocked
3. Did I check ALL 18 known issue trackers (#9154-#9178)? **NO** — GitHub access not available
4. Did I check last 60 days of commits for all investigated areas? **YES**
5. Can I produce a protobuf fixture demonstrating a bug? **NO** — no confirmed active bug
6. Did I avoid inferring activation from feature_map flags or solfuzz comments? **YES**
7. Did I avoid "Critical/High" without scope-aligned reasoning? **YES**
8. Did I verify epoch semantics carefully before claiming commission divergence? **YES** (corrected using fd_ssmsg.h)

---

## CONCLUSIONS

Session 4 investigated: validator_admission_ticket VAT filter, delay_commission_updates commission epoch selection, deprecate_legacy_vote_ixs, limit_instruction_accounts, raise_account_cu_limit, remove_simple_vote_from_cost_model, stake_raise_minimum_delegation_to_1_sol, and Rent Collection.

**No new candidates found.** Commission selection appeared divergent but corrected analysis using FD's own fd_ssmsg.h epoch documentation confirmed FD and Agave use identical epoch snapshots with the same priority order.

---

## AREAS STILL UNINVESTIGATED

If additional sessions are feasible, the following should be examined:

1. **sBPF v3 instruction execution divergences** — detailed comparison of JMP32, static syscall dispatch, lower_rodata_vaddr edge cases. Requires running solfuzz tests.
2. **Account data direct mapping** (`account_data_direct_mapping`) — commented out in solfuzz as "fuzz in 4.0+", may have divergences when enabled
3. **stricter_abi_and_runtime_constraints** — also "fuzz in 4.0+", similar situation
4. **Epoch reward distribution order** — are rewards applied in deterministic order in FD matching Agave? Only testable via solfuzz block harness with many stake accounts.
5. **Partitioned reward recalculation from snapshot** — the fd_rewards.c:960-1012 path that reconstructs rewards after loading from a snapshot may have edge cases

---

## TOTAL COUNTS ACROSS ALL SESSIONS

| Metric | Count |
|--------|-------|
| SUPPORTED_FEATURES investigated | 36 (all) |
| Confirmed candidates passing all 5 filters | 0 |
| Candidates eliminated (all sessions) | 3 (CANDIDATE-01, CANDIDATE-02, CANDIDATE-03) |
| Known bugs (within 60-day window) | 2 (9ea4e56, 87ef4c3) |
| Features needing RPC verification | 5+ (all from Session 3) |
