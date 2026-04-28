# Triager Negotiation — How to Handle Pushback

After submission, you'll get one of:
1. **Acknowledged + accepted at your severity** (rare, 5-15% of submissions)
2. **Acknowledged + downgraded** (common, 40-60%)
3. **Rejected as OOS / duplicate / known issue** (20-30%)
4. **No response within SLA** (10-20%)
5. **Asked for clarification / additional PoC** (15%)

This file is the playbook for each response.

## Response 1 — Accepted at your severity

Don't celebrate yet. Verify:
- Severity confirmed in writing.
- Payout amount stated explicitly.
- Payment timeline stated (some programs delay by 30-90 days).
- Any conditions (e.g., KYC, fix verification).

Reply with thanks + KYC info + wallet for payment + any follow-up findings.

## Response 2 — Downgraded

Most common. The argument has just begun.

### Step 1 — Read the downgrade reason carefully

Common reasons:
- "Requires victim cooperation"
- "External preconditions"
- "Already known issue"
- "Theoretical / not exploitable"
- "Severity scaled to TVL"
- "Rounding / dust amounts"
- "Self-griefing"
- "Out-of-scope"

### Step 2 — Determine if reason is legitimate

For each reason, evaluate honestly:

#### "Requires victim cooperation"

**Legitimate** if attack truly requires victim to do something unusual (sign a malicious tx, approve a weird permission).

**Not legitimate** if "cooperation" = victim using protocol normally (depositing, swapping, opening positions).

**Argument back**: "Victim's action is normal protocol use, not cooperation. Specifically: any user who deposits via the standard `deposit` instruction is exposed. This is not opt-in to attack; it's standard usage."

#### "External preconditions"

**Legitimate** if attack requires admin to configure something specific OR an external oracle to behave in a way that's manipulated outside the program.

**Not legitimate** if precondition is normal market behavior or attacker-controllable.

**Argument back**: "The precondition X is reproducible by the attacker without admin or governance involvement. Specifically: [explain how attacker triggers X]. PoC includes the trigger as part of the attack flow."

#### "Already known issue"

**Legitimate** if you find the issue in the project's audit reports, security advisories, or GitHub issues.

**Not legitimate** if the cited "known issue" is a different bug, or if it's not actually documented anywhere public.

**Argument back**: "Could you cite the specific reference? I've reviewed [X audit] and [Y advisory] and don't find this. The closest match is [Z], which differs in: [specific differences]." Force them to point to actual documentation.

#### "Theoretical / not exploitable"

**Legitimate** if your PoC has hidden conditions or doesn't actually run.

**Not legitimate** if your PoC runs and shows extraction.

**Argument back**: "PoC executes successfully and extracts [$X]. Logs attached: [stdout]. Attack flow runs in [N] tx with [Y] CU. Please specify what makes this 'theoretical' — every state change is triggered by a real instruction."

#### "Severity scaled to TVL"

**Legitimate** if TVL is genuinely small.

**Not legitimate** if TVL referenced is a wrong subset.

**Argument back**: "TVL at risk is $X based on [DeFiLlama / on-chain query]. The exposed pool/vault has TVL of $Y. Please confirm which TVL number is being used for severity calculation."

#### "Rounding / dust"

**Legitimate** if the exploit extracts dust amounts that aren't economically meaningful.

**Not legitimate** if the exploit can be repeated to drain.

**Argument back**: "Exploit can be repeated [N] times per slot, extracting [$X] per cycle. Aggregate per hour: [$Y]. Aggregate per day: [$Z]. PoC includes the multiplier loop."

#### "Self-griefing"

**Legitimate** if the only person who can be hurt is the attacker themselves.

**Not legitimate** if attacker can hurt OTHER users (or the protocol) through the bug.

**Argument back**: "Bug affects [other users / protocol vault / etc.], not the attacker themselves. PoC shows victim user [Y] losing [$X]; attacker is the beneficiary. This is theft, not self-grief."

#### "Out-of-scope"

**Legitimate** if the affected program/contract is in the OOS list on the bounty page.

**Not legitimate** if the program is in scope but the triager cites a different OOS rule.

**Argument back**: "Bounty page lists [program ID] as in-scope (link). The bug is in this program. Could you specify which OOS rule you're applying?"

### Step 3 — Compose the response

Structure:
1. Acknowledge their concern.
2. State your disagreement specifically.
3. Provide new evidence (if available) or reference existing PoC.
4. Map to VRC explicitly.
5. Ask for specific reasoning if you don't get it.

Tone: professional, factual, not defensive. You're a peer collaborator, not a customer complaining.

Example response:

```
Thanks for the review. I want to push back on the downgrade to Medium.

The downgrade reason cited is "requires victim cooperation". The PoC shows the
attack triggers when any user calls the `deposit` function with standard
parameters. This is not cooperation — `deposit` is the canonical way users
interact with the vault.

Mapping to VRC v2.3:
- Direct theft of user funds at-rest: confirmed in PoC stdout (line 47-52)
- No admin precondition: PoC has no admin or governance instructions
- No external infra dependency: PoC runs in litesvm without external state

I believe this maps to Critical per "Direct theft of user funds at rest"
(Smart Contract / Critical).

Could you clarify which specific element of the attack you're considering as
"cooperation"? I want to make sure my PoC isn't missing something.
```

### Step 4 — Be willing to accept the downgrade

If after your argument the triager holds firm with reasoning, accept. Don't grind. Triagers have memory across submissions — credibility is your asset.

## Response 3 — Rejected (OOS / duplicate / known issue)

### If "OOS"

Re-read the scope page. If you're confident the bug is in scope, push back ONCE with specifics. If they hold, accept and move on.

### If "duplicate"

Ask for the reference. If it's a real duplicate, accept and move on (or argue you submitted first if timing matters).

If the cited "duplicate" is a different bug, push back: "The duplicate cited (X) is about [different issue]. My finding is about [my issue]. Could you confirm these are the same?"

### If "known issue"

Same approach. Force them to cite the public reference.

## Response 4 — No response within SLA

Most programs have stated SLA (typically 7-14 days for initial response, longer for resolution). After SLA expires:

1. Send a polite follow-up: "Following up on submission [#X] from [date]. Per the bounty page, initial response is within [N] days. I haven't received a response yet — could you confirm receipt?"
2. If no response after another 7 days, escalate to Immunefi support.

Do NOT publicly disclose. The bug is still in your private channel; disclosure violates Immunefi terms and kills your reputation.

## Response 5 — Asked for clarification

Common requests:
- "Provide a clearer PoC."
- "Walk through step by step."
- "Test on mainnet fork."
- "Try with parameter X."

Respond promptly. Triagers reward responsiveness. If you provide what they ask within 24h, severity tends to land closer to your claim.

## Tone calibration

The right tone is:
- **Direct**: "this is wrong because X" not "I'm not sure but maybe..."
- **Specific**: cite line numbers, VRC rows, on-chain data
- **Professional**: no anger, no whining, no veiled threats
- **Confident**: you've done the work, you know the bug

Avoid:
- Defensive language ("I think this might be...")
- Padding ("Just wanted to follow up if possible thank you so much")
- Aggressive language ("You're wrong about this")
- Disclosure threats ("If this isn't fixed I'll have to...")

## Defending the report

When pushback comes, your evidence is:

1. **The PoC stdout**. Actual numbers, actual logs.
2. **VRC v2.3 mapping**. Cite exact section.
3. **The protocol's docs / audit history**. Cite specific public source.
4. **On-chain evidence**. If exploit hits mainnet (unlikely, but possible after fix), tx signatures.

If you don't have one of these, you may not have a strong case.

## Response thread management

- Keep all communication in the Immunefi report thread, not external (Discord, email).
- Number your responses if multiple back-and-forth.
- Save copies of every message (Immunefi reports can be edited).
- If discussion gets long, summarize: "TL;DR: severity is X because Y; remaining open question is Z."

## When to escalate to Immunefi support

Escalate if:
- Triager is non-responsive past SLA + 7 days.
- Triager makes claims that contradict the public bounty page.
- Triager appears to have a conflict of interest with the project.
- Severity dispute hits an impasse and you have strong evidence.

Don't escalate if:
- You disagree with a reasonable triager call.
- You're frustrated by slow response (be patient first).
- You feel the program "should pay more" without specific argument.

## Long game

Your Immunefi reputation is built across submissions. Each one:
- Builds rapport with the triager team.
- Adds credibility for your claims on future submissions.
- Adds context the team has about your work quality.

Hunters with track records get faster acknowledgments and more benefit-of-doubt. Hunters with reputation for inflating severity or low-quality submissions get harder triage.

Play the long game. Submit clean. Negotiate hard but fair. Move on when you've made your case.
