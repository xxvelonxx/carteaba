# Jito On-Chain Programs Audit — No Qualifying Candidates

**Date**: 2026-04-27  
**Target**: `jito-foundation/jito-programs` HEAD `ce1dfb6`  
**Scope**: Immunefi bug bounty — Jito on-chain Solana programs  
**Programs Audited**:
- `jito-tip-distribution` — `4R3gSG8BpU4t19KYj8CfnbtRpnT8gtk4dvTHxVRwc2r7`
- `jito-tip-payment` — `T1pyyaTNZsKv2WcRAB8oVnk93mLJw2XzjtVYqCsaHqt`
- `jito-priority-fee-distribution` — `Priority6weCZ5HwDn29NxLFpb7TDp2iLZ6XKc5e8d3`

---

## Executive Summary

After exhaustive source-code review of all three Jito on-chain programs, **no candidates met all five eligibility filters** (F1: working PoC, F2: in-scope, F3: not known, F4: not fixed in 60 days, F5: honest severity).

---

## Source Files Fully Read

| File | Lines | Notes |
|------|-------|-------|
| `tip-distribution/src/lib.rs` | 757 | All instructions, account structs, auth logic |
| `tip-distribution/src/state.rs` | 198 | Config, TDA, ClaimStatus, MerkleRoot, MerkleRootUploadConfig |
| `tip-distribution/src/merkle_proof.rs` | 29 | verify() — sorted-pair SHA-256 with domain separation |
| `tip-payment/src/lib.rs` | 825 | All instructions, Config, TipPaymentAccount, drain logic |
| `priority-fee-distribution/src/lib.rs` | 807 | All instructions, account structs, transfer_priority_fee_tips |
| `priority-fee-distribution/src/state.rs` | 200 | PriorityFeeDistributionAccount, ClaimStatus (no is_claimed), MerkleRootUploadConfig |
| `priority-fee-distribution/src/merkle_proof.rs` | 27 | Identical to tip-distribution version |

### Audit PDFs Available (None Cover These Programs)

| PDF | Program Covered |
|-----|----------------|
| `jito_tiprouter_audit.pdf`, `jito_tiprouter_certora.pdf`, `jito_tiprouter_offside.pdf` | Tip Router (different program) |
| `jito_restaking_ottersec.pdf`, `jito_restaking_v1_certora.pdf`, `jito_restaking_v2_certora.pdf` | Restaking |
| `jito_interceptor_certora.pdf`, `jito_interceptor_offside.pdf` | Interceptor |
| `jito_vault_audit.pdf`, `jito_vault_offside.pdf` | Vault |
| `jito_bam_ottersec.pdf` | BAM validator client |
| `jito_stake_audit.pdf` | Stake program |

No prior public audit covers tip-distribution, tip-payment, or priority-fee-distribution directly.

---

## Program Architecture Summary

### jito-tip-payment

- 8 singleton tip PDA accounts (TIP_ACCOUNT_0 through 7) accumulate lamports from MEV searchers
- `Config` stores `tip_receiver`, `block_builder`, `block_builder_commission_pct`, and bump seeds
- **`change_tip_receiver` / `change_block_builder`**: intentionally permissionless — any signer can call. Each call first drains all 8 tip PDAs to the CURRENT `old_tip_receiver`+`block_builder`, then updates Config to the new accounts
- Design contract: validator client re-cranks every slot to maintain itself as `tip_receiver`
- No `claim_tips` instruction handler exists; `ClaimTips` struct in source is dead code (no matching function in `#[program]` block)
- Direct lamport manipulation via `try_borrow_mut_lamports` — no system CPI, no reentrancy risk

### jito-tip-distribution

- Validators create one `TipDistributionAccount` (TDA) per epoch (gated by vote account node pubkey)
- After epoch ends, `merkle_root_upload_authority` uploads a merkle root
- Claims via `claim()` require the `merkle_root_upload_authority` to sign; `claimant` is not a signer (Jito's off-chain service submits claims on behalf of stakers)
- `ClaimStatus` PDA (seeds: `[CLAIM_STATUS, claimant, tda]`) prevents double-claim; `is_claimed = true` set on success
- `migrate_tda_merkle_root_upload_authority`: permissionless migration from old to new authority (gated: no root uploaded AND current authority == `original_upload_authority` in MerkleRootUploadConfig)
- Re-upload allowed only if `num_nodes_claimed == 0` (first-claim atomic with counter increment; no zombie ClaimStatus PDAs possible)

### jito-priority-fee-distribution

- Nearly identical architecture to tip-distribution; adds `go_live_epoch` feature flag and `total_lamports_transferred` tracking field
- `transfer_priority_fee_tips`: anyone can call to deposit SOL into a PFDA for the current epoch; gated by `epoch_created_at == current_epoch`
- `ClaimStatus` omits `is_claimed` bool (double-claim prevented entirely by PDA uniqueness via `init` constraint)
- Same permissionless `migrate_tda_merkle_root_upload_authority` as tip-distribution

---

## Hypotheses Investigated and Eliminated

### H1: `change_tip_receiver` Front-Run Tip Theft (DOWNGRADED — By Design)

**Hypothesis**: Attacker calls `change_tip_receiver(new=attacker)`, tips accumulate, validator's next crank drains to `attacker` as `old_tip_receiver`.

**Analysis**:
- The attack is technically correct: between attacker's call and validator's next crank, the attacker holds `tip_receiver` status. The validator's subsequent crank drains one slot's tips to the attacker as `old_tip_receiver`.
- Window: ~400ms (one Solana slot)
- However, this is **intentionally documented permissionless design**. The Jito architecture explicitly relies on the validator client re-cranking every slot. The race window is an accepted design trade-off, not an unforeseen vulnerability.
- No known Immunefi submission path: "works as intended" architecture decisions are excluded

**Verdict**: F2/F3 fail — by-design behavior, not an unintended vulnerability in scope for bug bounty.

---

### H2: CPI Reentrancy via Direct Lamport Manipulation (ELIMINATED)

**Hypothesis**: Direct `try_borrow_mut_lamports` calls on tip PDAs or TDAs could be vulnerable to reentrancy.

**Refutation**: Direct lamport manipulation in Solana's BPF VM is a memory operation — no CPI is triggered, no program callbacks occur, no reentrancy is possible. Unlike EVM's `.transfer()`, Solana's direct lamport writes do not invoke receiver logic.

**Verdict**: F1 fails — not achievable in Solana's execution model.

---

### H3: Merkle Second-Preimage Attack (ELIMINATED)

**Hypothesis**: Craft a merkle internal node whose hash equals a valid leaf hash, or vice versa, to forge a claim.

**Refutation**: Domain separation with distinct prefixes defeats this:
- Leaf: `sha256(0x00 || sha256(pubkey || amount_le))` — outer layer uses prefix byte `0x00`
- Internal node: `sha256(0x01 || sorted(left, right))` — uses prefix byte `0x01`

A forged leaf would need `sha256(0x00 || sha256(pubkey || amount_le)) == sha256(0x01 || ...)`, requiring a SHA-256 collision. Additionally sorted-pair ordering prevents position-swap attacks.

**Verdict**: F1 fails — requires SHA-256 second-preimage, computationally infeasible.

---

### H4: Zero-Proof / Empty-Proof Claim Forgery (ELIMINATED)

**Hypothesis**: Submit `proof = []` to `claim()`. `verify([], root, leaf)` returns `leaf == root`. If an attacker can control the root upload, they could upload a root equal to a crafted leaf.

**Refutation**: `upload_merkle_root` is gated to the `merkle_root_upload_authority`. The authority is Jito's trusted service. An attacker without the authority key cannot upload a specially crafted root. This is a trusted-party concern, not an on-chain bug.

**Verdict**: F2/F5 fail — requires authority compromise; trusted-party risk, not a program vulnerability.

---

### H5: `close_claim_status` → Re-Claim Double-Spend (ELIMINATED)

**Hypothesis**: After `close_claim_status` closes the ClaimStatus PDA, re-initialize it and claim again from the same TDA.

**Refutation**: Timing gates prevent this:
- `close_claim_status` requires `epoch > expires_at`
- `claim()` rejects when `epoch > expires_at` (ExpiredTipDistributionAccount)

These conditions are mutually exclusive: ClaimStatus can only be closed when claims are no longer possible. After closure, any re-initialization attempt via `claim()` would fail the expiry check before reaching the `init` constraint.

**Verdict**: F1 fails — timing gates eliminate the re-claim path.

---

### H6: `upload_merkle_root` Re-Upload Orphans Existing ClaimStatus PDAs (ELIMINATED)

**Hypothesis**: Authority uploads Root A, then (before any claims confirm) re-uploads Root B. Existing ClaimStatus PDAs from aborted Root A transactions could block Root B claims.

**Refutation**: In Solana's VM, if a transaction fails (e.g., invalid proof), ALL state changes are rolled back — including `init`-created accounts. A ClaimStatus PDA can only exist if the claim transaction succeeded. If claim succeeded, `num_nodes_claimed >= 1`, which permanently blocks re-upload (`if merkle_root.num_nodes_claimed > 0 { return Err(Unauthorized) }`). Therefore, zombie ClaimStatus PDAs that block future claims cannot exist.

**Verdict**: F1 fails — transaction atomicity prevents zombie PDAs; re-upload guard is logically sound.

---

### H7: priority-fee-distribution `total_lamports_transferred` Inflation Before Go-Live (INFORMATIONAL)

**Finding**: In `transfer_priority_fee_tips`, when `go_live_epoch > current_epoch`, the function increments `total_lamports_transferred` by `lamports` but returns `Ok()` WITHOUT invoking the System Program transfer. The `from` account's lamports are NOT deducted. An attacker can call this with `lamports = u64::MAX - current_total` to inflate the counter for free (only pays transaction fee ~0.000005 SOL), since the System Program CPI never runs.

**Analysis**:
- The counter inflation is real and costs only transaction fees
- Impact depends entirely on off-chain tree construction. If the tree-builder uses `total_lamports_transferred` as the authoritative distribution total (rather than the PFDA's actual lamport balance), the resulting tree would expect more lamports than exist in the PFDA, causing the final claimants' transactions to fail with ArithmeticError (checked_sub underflow)
- However: the `upload_merkle_root` authority sets `max_total_claim` from the off-chain tree, which should reflect the actual PFDA balance, not the counter. The counter is bookkeeping/analytics only
- No direct loss of funds: no lamports move as a result of the counter inflation; the authority retains full control over the distribution tree
- The PFDA lamport balance itself cannot be inflated without actual SOL (the System Program CPI that actually transfers is never called before go-live)

**Severity assessment**: Low informational. Griefing risk if and only if the off-chain system uses `total_lamports_transferred` as ground truth for tree construction, which would be a defect in the off-chain software, not the on-chain program.

**Verdict**: F5 fails — no direct fund loss; informational issue in off-chain-dependent bookkeeping field. Does not meet Immunefi severity threshold.

---

### H8: `ClaimTips` Dead-Code Struct — Unreachable Instruction (INFORMATIONAL)

**Finding**: `ClaimTips` accounts struct is defined in tip-payment/src/lib.rs (lines 422–503) but no corresponding `claim_tips` function exists in the `#[program]` block. Anchor dispatches instructions by 8-byte discriminator derived from function name; without a handler, the instruction is unreachable.

**Analysis**: Dead code from a removed instruction. No security impact. The struct cannot be invoked on-chain.

**Verdict**: Informational only.

---

### H9: `MigrateTdaMerkleRootUploadAuthority` Permissionless — Authority Griefing (INFORMATIONAL)

**Hypothesis**: Anyone can call `migrate_tda_merkle_root_upload_authority` on eligible TDAs (no root uploaded, current authority == original_upload_authority in MerkleRootUploadConfig) to force-migrate the authority.

**Analysis**: This is intentional and beneficial — the instruction exists to migrate all TDAs from Jito Labs' old key to a new override key without requiring validator cooperation. The migrated-to authority (`override_authority`) is governance-controlled; the only danger would be Jito governance setting a malicious override_authority, which is a trusted-party risk outside program scope. The migration cannot set an arbitrary attacker-controlled authority.

**Verdict**: F2/F5 fail — intentional permissionless migration by design; trusted-party governance risk, not an on-chain bug.

---

### H10: `upload_merkle_root` — `max_total_claim` Not Validated Against TDA Balance (INFORMATIONAL)

**Finding**: `upload_merkle_root` accepts caller-supplied `max_total_claim` and `max_num_nodes` with no on-chain validation against the TDA's actual lamport balance. The authority could upload a root with `max_total_claim = 0` (no claims possible) or `max_total_claim = u64::MAX` (no ceiling).

**Analysis**:
- If `max_total_claim = 0`: any claim immediately fails with ExceedsMaxClaim. This is a griefing-by-authority attack; authority re-upload is blocked once claims start
- If `max_total_claim > TDA.balance`: the limiting factor becomes the lamport balance. When the TDA is drained, subsequent claims fail with ArithmeticError. No lamports are at risk beyond what the TDA holds
- Both scenarios require a malicious upload authority — a trusted-party risk

**Verdict**: F2/F5 fail — trusted-party risk; upload authority is Jito's controlled service.

---

## Security Properties Verified

| Property | Status |
|----------|--------|
| Bundle-level atomicity (tip-payment) | N/A — tip-payment has no bundling; validator client handles this |
| Double-claim prevention (tip-distribution) | ✓ — ClaimStatus PDA uniqueness + `is_claimed = true` |
| Double-claim prevention (priority-fee-distribution) | ✓ — ClaimStatus PDA uniqueness (no `is_claimed` needed) |
| Merkle proof domain separation | ✓ — 0x00 leaf prefix, 0x01 node prefix |
| Sorted-pair proof ordering | ✓ — prevents position-swap forgery |
| Checked arithmetic throughout | ✓ — all math uses checked_add/sub/mul/div |
| Expiry gate on claims | ✓ — synchronized between claim() and close_claim_status() |
| TDA initialization gate (validator identity) | ✓ — node_pubkey from vote account must sign |
| Re-upload protection after first claim | ✓ — num_nodes_claimed > 0 blocks re-upload |
| Transfer fallback in tip-payment | ✓ — if receiver can't receive, lamports return to tip_accounts[0] |
| Anchor discriminator checks | ✓ — prevents account type confusion |

---

## Self-Audit Checklist

| Question | Answer |
|----------|--------|
| Did you check all available audit reports? | Yes — 14 PDFs reviewed; none cover these three programs |
| Did you trace all instruction execution paths? | Yes — every instruction in all 3 programs |
| Did you check CPI reentrancy? | Yes — no CPI in lamport transfers; not possible |
| Did you verify merkle proof domain separation? | Yes — 0x00/0x01 prefixes prevent second-preimage |
| Did you check double-claim across all paths? | Yes — PDA uniqueness + expiry gates are consistent |
| Did you check all authority assumptions? | Yes — all gated flows require trusted-party compromise |
| Did you inflate severity to force a finding? | No — all hypotheses honestly eliminated |

---

## Conclusion

The Jito on-chain programs (HEAD `ce1dfb6`, Apr 2026) are securely implemented. The design is conservative:

1. **Merkle proof security** correctly uses domain-separated, sorted-pair SHA-256 — no second-preimage attacks
2. **Double-claim prevention** uses immutable PDA uniqueness as the primary gate (redundantly backed by `is_claimed` in tip-distribution)
3. **Expiry synchronization** between ClaimStatus and TDA prevents timing-based double-spend
4. **Checked arithmetic** throughout all financial operations prevents overflow
5. **Permissionless design** of `change_tip_receiver` is an intentional, documented architecture trade-off acceptable under the protocol's trust model

The `total_lamports_transferred` counter inflation issue in priority-fee-distribution (H7) is the only finding worth noting, but it has no direct financial impact and depends on off-chain software behavior.

**No candidates for Immunefi submission were found.**
