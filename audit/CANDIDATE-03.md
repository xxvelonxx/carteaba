# CANDIDATE-03: Wrong Verified Build Hash for Slashing Program Migration

**Feature**: `enshrine_slashing_program`  
**Pubkey**: `sProgVaNWkYdP2eTRAy1CPrgb3b9p8yXCASrPEqo6VJ`  
**Program**: `S1ashing11111111111111111111111111111111111`  
**Source buffer**: `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv`  

---

## Summary

When `enshrine_slashing_program` activates, Agave migrates the slashing program from a
stateless builtin to a Core BPF program. This migration is gated on a SHA256 hash check
of the source buffer's program binary. FD has a **different hash** from Agave, causing
FD's migration to fail while Agave's succeeds. The result: different account states →
bank hash mismatch.

---

## The Divergence

**FD** (`src/flamenco/runtime/program/fd_builtin_programs.c:41-44`):
```c
/* FIXME: update to correct hash when slashing program is finalized */
/* 9260b9ac8dfa1a6ed1022380a713bec7b75979ae136e91f9a86795b51c6c489f */
#define SLASHING_PROG_HASH_SIMD_204 0x92,0x60,0xb9,0xac,...
```

**Agave** (`builtins/src/lib.rs:141-147`):
```rust
// 192ed727334abe822d5accba8b886e25f88b03c76973c2e7290cfb55b9e1115f
const HASH_BYTES: [u8; 32] = [
    0x19, 0x2e, 0xd7, 0x27, 0x33, 0x4a, 0xbe, 0x82, 0x2d, 0x5a, 0xcc, 0xba, 0x8b, 0x88,
    0x6e, 0x25, 0xf8, 0x8b, 0x03, 0xc7, 0x69, 0x73, 0xc2, 0xe7, 0x29, 0x0c, 0xfb, 0x55,
    0xb9, 0xe1, 0x11, 0x5f,
];
```

The hashes are completely different:
- FD: `9260b9ac8dfa1a6ed1022380a713bec7b75979ae136e91f9a86795b51c6c489f`
- Agave: `192ed727334abe822d5accba8b886e25f88b03c76973c2e7290cfb55b9e1115f`

---

## Execution Path

Both use the same source buffer address: `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv`.

At the epoch boundary when `enshrine_slashing_program` first activates:

**Agave** (`runtime/src/bank/builtins/core_bpf_migration/source_buffer.rs:53-74`):
1. Reads source buffer account
2. Strips trailing zero bytes from program data
3. Computes SHA256 of stripped data
4. Checks against `192ed727...` — IF ON-CHAIN BUFFER MATCHES → migration proceeds:
   - Creates slashing program account at `S1ashing111...`
   - Creates program data account
   - Clears source buffer account (sets to `AccountSharedData::default()`)

**FD** (`src/flamenco/runtime/fd_core_bpf_migration.c:456-472`):
1. Reads source buffer account
2. Strips trailing zeros, computes SHA256
3. Checks against `9260b9ac...` — MISMATCH → returns early, migration skipped

---

## Account State Divergence

When on-chain source buffer SHA256 == `192ed727...` (Agave's expected hash):

| Account | Agave state | FD state |
|---------|------------|---------|
| `S1ashing111...` (program) | Created, BPF program account | Not created |
| program data account | Created | Not created |
| `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv` (buffer) | Cleared (0 lamports, 0 data) | Unchanged |

Three accounts differ → accounts delta hash differs → bank hash mismatch.

---

## Filter Analysis

**Filter A (bank hash mismatch)**: PASS — Agave creates 2 new accounts and clears 1,
FD leaves all unchanged. Different account states in the slot → different accounts delta
hash → different bank hash.

**Filter B (reachable via solfuzz)**: PASS — `enshrine_slashing_program` is in
`solfuzz-agave/src/lib.rs` SUPPORTED_FEATURES (line 316). A solfuzz test case can
include the source buffer account with binary data D where SHA256(strip_trailing_zeros(D))
== `192ed727...`, then activate `enshrine_slashing_program` at an epoch boundary.

**Filter C (not in known issues #9154-#9178)**: UNCERTAIN — The FIXME comment in FD's
code (`FIXME: update to correct hash when slashing program is finalized`) indicates the
FD team is aware this needs updating. Whether it is tracked as an Immunefi issue in
#9154-#9178 requires GitHub access to verify.

**Filter D (not fixed in last 60 days)**: PASS — Last commit to
`src/flamenco/runtime/program/fd_builtin_programs.c` was `7660344` (April 20, 2026),
which was a type refactoring only. The hash FIXME is still present in HEAD.

**Filter E (severity)**: 
- If `enshrine_slashing_program` is active on mainnet → **Critical** (actively causing
  divergence on every epoch boundary after activation)
- If not yet active → **High** (will cause divergence on activation)
- Requires RPC query to `sProgVaNWkYdP2eTRAy1CPrgb3b9p8yXCASrPEqo6VJ` to determine

---

## RPC Verification Needed

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getAccountInfo","params":["sProgVaNWkYdP2eTRAy1CPrgb3b9p8yXCASrPEqo6VJ",{"encoding":"base64","commitment":"finalized"}]}' \
  https://api.mainnet-beta.solana.com
```

If non-null: `enshrine_slashing_program` is active on mainnet → **Critical**.

Also check the source buffer:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getAccountInfo","params":["S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv",{"encoding":"base64","commitment":"finalized"}]}' \
  https://api.mainnet-beta.solana.com
```

If the buffer data (stripped of trailing zeros) SHA256 == `192ed727...`, Agave migrates
and FD doesn't. If SHA256 == `9260b9ac...`, FD migrates and Agave doesn't. Either way
is a mismatch.

---

## solfuzz Proof-of-Concept Sketch

To demonstrate via solfuzz:
1. Construct binary blob `D` such that SHA256(D) = `192ed727334abe822d5accba8b886e25f88b03c76973c2e7290cfb55b9e1115f`
   (Agave's expected hash). This is the program binary for the slashing program.
2. Create account `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv` owned by
   `BPFLoaderUpgradeab1e11111111111111111111111` with buffer state containing `D`.
3. Set epoch context with `enshrine_slashing_program` feature active.
4. Run epoch boundary processing.

**Expected**: Agave creates slashing program account; FD does not. Bank hashes differ.

---

## Notes

- The FIXME comment explicitly says "update to correct hash when slashing program is
  finalized", confirming FD has a placeholder/outdated hash.
- Agave's hash (`192ed727...`) appears to be the finalized hash as it was committed
  without a FIXME.
- Source buffer address matches between FD and Agave (both: `S1asHs4je6wPb2kWiHqNNdpNRiDaBEDQyfyCThhsrgv`).
- Program ID matches between FD and Agave (both: `S1ashing11111111111111111111111111111111111`).

---

## Verdict

**CANDIDATE** — pending Filter C verification and RPC activation check.

Severity: High (prospective) to Critical (if active on mainnet).
