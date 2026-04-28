# Program by Program — Solana Bounty Reputation Notes

Operational notes on major Solana bug bounty programs as of early 2026. Each program has its own personality, response pattern, and triage style.

This information may go stale. Always check the live bounty page for current scope and rules. The notes here are about HOW the program operates, not the contractual terms.

---

## Top-tier programs ($500K+ Critical)

### Orca (Whirlpools, xORCA)

**Bounty range**: up to $500K Critical for Whirlpools.
**Response time**: typically 2-7 days for initial response.
**Triage style**: technical, asks for clean PoCs in litesvm.
**KYC**: required for payouts ≥ $10K typically.
**Reputation**: solid, pays out reasonably. Has had Whirlpools live since 2022 with active bounty.
**Scope**: Whirlpools program + xORCA + recent additions. Read scope carefully.
**Common rejection reasons**:
- "Already addressed in audit" — they've had multiple audits.
- "Out of scope" for related programs (e.g., Orca's older v1 AMM).
- Severity scaling on smaller pools.

### Drift Protocol

**Bounty range**: high (perps + spot lending).
**Response time**: fast for high-severity findings, slower for Medium/Low.
**Triage style**: highly technical team; expect deep technical pushback.
**Reputation**: respected. Known for good payout discipline.
**Common rejection reasons**: defensive about funding rate / liquidation findings; need very clear PoC.

### Solana Foundation / SPL programs

**Bounty range**: very high for core SPL.
**Response time**: slower (large team, formal process).
**Triage style**: formal, conservative.
**KYC**: usually required.
**Scope**: extremely narrow — only specific SPL programs. Read scope.

### Marinade

**Bounty range**: high (LST with significant TVL).
**Response time**: moderate.
**Triage style**: detail-oriented.
**Reputation**: pays.

### Jito (Restaking, JitoSOL)

**Bounty range**: high.
**Response time**: moderate.
**Triage style**: technical.
**Recent**: vault inflation defense + restaking-specific surface area.

---

## Mid-tier programs ($50K-$500K Critical)

### Kamino

**Bounty range**: significant (lending + LP vaults).
**Response time**: variable.
**Triage style**: detailed but pushes back on severity.
**Reputation**: pays but argues hard on severity. Expect downgrade pushback.

### MarginFi

**Bounty range**: medium-high.
**Response time**: variable.
**Reputation**: standard.

### Sanctum

**Bounty range**: medium-high.
**Reputation**: technical team, fair.

### Save (formerly Solend's spinoff)

**Bounty range**: medium.
**Response time**: slow historically.
**Reputation**: post-Solend-incident, more cautious.

### Light Protocol / ZK Compression

**Bounty range**: medium (newer protocol, lower TVL but high tech).
**Response time**: fast for technical findings.
**Triage style**: deeply technical (ZK + compression).
**Reputation**: pays.

### M0 / KAST

**Bounty range**: lower ($50K typical Critical).
**Response time**: variable.
**Triage style**: detail-focused.
**Reputation**: existing programs with rejection history. Velon's prior reports rejected (F1, F2, F5) — known to push back hard on findings without clear funds-at-risk.

---

## Smaller / Newer programs ($10K-$50K Critical)

### Various early-stage protocols

These are scattered. Read the bounty page carefully. Common patterns:
- Lower payouts.
- Faster responses (smaller team, more attention per submission).
- Less mature triage discipline (sometimes overpay, sometimes underpay).
- Higher risk of program changes / cancellation.

### NFT marketplaces (Tensor, Magic Eden, Sharky, Frakt)

**Bounty range**: typically lower (NFT TVL is per-asset, not pooled).
**Response time**: fast for high-impact findings.
**Triage style**: marketplace-specific concerns (royalty enforcement, etc.).
**Reputation**: standard.

---

## Programs with notable triager personalities

(Names elided since triagers rotate.)

Some general patterns:

### Defensive triagers

Will argue every severity claim. Default to downgrading. Require multiple rounds of evidence.

**Approach**: lead with airtight PoC, cite VRC explicitly, reference prior accepted findings of similar class. Don't engage in long debates — make your case crisply, let the call play out.

### Technical triagers

Engage in deep technical discussion. Want to understand the bug fully. Severity often lands close to your claim if technical merit holds up.

**Approach**: provide full technical detail, including alternate paths, related considerations. Treat as collaborator.

### Process-focused triagers

Care about format, completeness, KYC, etc. Severity argued on formal grounds.

**Approach**: meet every formal requirement upfront. Use the report template precisely. Don't deviate.

### Founder triagers

Some smaller programs have founders triaging directly. Often emotional response — high attachment to "their code is good".

**Approach**: be especially diplomatic. Frame as "found this minor issue, here's the fix". Severity often lower than VRC suggests but payout fast.

---

## Payment timeline reality

VRC says X. Programs say Y. Reality is Z.

**Stated timeline**: most programs say 7-30 days for confirmed payout.

**Actual timeline**: often 2-3 months from acceptance to wire.

**Reasons for delay**:
- KYC processing (1-3 weeks).
- Multi-sig payment approval (varies).
- Project's payment cycle (some pay quarterly).
- Crypto vs fiat preference and conversion logistics.

**Mitigation**:
- Submit KYC as soon as possible (don't wait for severity confirmation).
- Use stable wallet for payouts (don't use exchange address that might bounce).
- Politely follow up after stated SLA.

## KYC reality

Most programs require KYC for payouts. Standard providers:
- Synaps
- Persona
- Sumsub

**What's required**:
- Government ID (passport / driver's license).
- Proof of address (utility bill).
- Sometimes selfie + ID match.
- For corporations: incorporation docs.

**Privacy considerations**:
- Solana payments are pseudonymous on-chain but KYC links your identity to the address.
- Some hunters use entities (LLCs, etc.) for separation.
- Some programs allow non-KYC for payouts < $X (typically $5K-$10K).

**Skip-KYC programs**: rare but exist. Check bounty page.

---

## Disclosure norms

After fix:
- Most programs allow public disclosure 30-90 days post-fix.
- Disclosure builds your reputation as a hunter.
- Coordinate with project on disclosure timing and content.

Pre-fix:
- NEVER disclose pre-fix. This violates Immunefi terms.
- Even discussing in private channels (if quotable) can backfire.

---

## How to use this file

When working on a target:
1. Look up the program here for any operational notes.
2. Calibrate response time expectations.
3. Adjust submission style for the triager personality (if known).
4. Plan for KYC + payment timeline.

This is institutional knowledge that's not on the bounty page. Use it.

---

## Updating this file

If you have direct experience with a program:
- Note the response time.
- Note the triager personality.
- Note any unusual rejection reasons.
- Note any payment timeline anomaly.

This file should evolve with experience.
