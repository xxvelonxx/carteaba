# Mythos: Two Architectures, One Principle

## The Parallel

Both systems are built on the same core insight: **depth through iteration beats breadth through scale**.

| Dimension | OpenMythos (kyegomez) | Bandit/Mythos (our hunt framework) |
|-----------|----------------------|-------------------------------------|
| Reference | https://github.com/kyegomez/OpenMythos | This repo — `hunt-state/tree.json` |
| Domain | Language model architecture | Bug bounty agent methodology |
| "Loop" unit | Latent-space recurrent block (one CoT step in continuous space) | Agent wave (one swarm attack cycle) |
| Loop depth | Configurable T iterations per forward pass | N waves, each spawning parallel sub-agents |
| Weight/agent sharing | Shared weights across recurrent block iterations | Shared knowledge base (tree.json) across waves |
| Input injection | `h_{t+1} = A·h_t + B·e + Transformer(h_t, e)` — signal re-injected every step | Prior wave findings injected into each new wave prompt |
| Halting | Adaptive Computation Time (ACT) per input complexity | Kill switch: finding exhausted → hunt terminates |
| Efficiency | Parameter count constant; depth scales via iterations | Agent count constant; coverage scales via waves |
| Output | Implicit chain-of-thought in latent space | Explicit findings written to tree.json |

---

## OpenMythos Architecture (RDT)

Three-stage computation:

```
Input → [Prelude: N std transformer blocks]
      → [Recurrent Block: T iterations of shared weights]
           h_{t+1} = A·h_t + B·e + Transformer(h_t, e)
           spectral_radius(A) < 1  (stability guarantee)
      → [Coda: N std transformer blocks]
      → Output
```

Key properties:
- Each loop iteration ≈ one step of chain-of-thought in continuous latent space
- GQA or MLA attention (Flash Attention 2 support)
- Sparse MoE FFN: ~5% expert activation per token
- Scales from 1B → 1T parameters via dimension/expert/iteration configs
- Training: PyTorch DDP, FineWeb-Edu, 30B tokens, bfloat16

---

## Our Mythos Architecture (Agent Swarm)

Multi-wave attack loop:

```
Target → [Wave 1: 4-8 parallel recon agents]
       → [Synthesis: tree.json updated with LIVE/DEAD/ESCALATE]
       → [Wave 2: 4-8 parallel attack agents on LIVE leads]
       → [Gate-7: pre-Immunefi 7-check filter]
       → Kill or Submit
```

Key properties:
- Each wave = one "depth level" of investigation
- Bandit mentality: bottom-up from money (TVL × max_bounty first)
- Agents share state via tree.json (equivalent to hidden state `h_t`)
- Gate-7 is the ACT halting condition (stops when no exploitable path remains)
- All 6 waves completed on Orca Whirlpools: 25 agents, 0 Critical/High, 1 Medium

---

## What OpenMythos Gets Right (for us)

1. **Implicit depth**: OpenMythos computes reasoning without externalizing CoT tokens. Our hunt implicitly reasons across waves without re-explaining findings — each wave receives prior state and goes deeper. We should lean harder into this: agents shouldn't re-read dead leads.

2. **Stability constraint** (`ρ(A) < 1`): In model terms, this prevents hidden state explosion. In hunt terms: each wave should **contract** the search space, not expand it. If wave N produces more open questions than wave N-1, the hunt is diverging (bad).

3. **Loop index embedding**: OpenMythos uses a RoPE-like mechanism so each iteration can play a distinct role despite shared weights. We do this organically: Wave 1 = recon, Wave 2 = deep attack, Wave 3 = kill confirmation, etc. Each wave has an assigned role, not just "look for bugs."

4. **ACT halting**: The model stops looping when it's confident. Our Gate-7 filter plays this role — once 7 checks fail, the lead is dead and we don't recurse.

5. **MoE sparse activation**: ~5% of experts fire per token. Our agent swarm does the same — we don't assign every agent to every lead. Specialized agents (fee growth expert, tick array expert) fire only when relevant.

---

## What We Have That OpenMythos Lacks

1. **External tool use**: Agents read source files, grep, run code. RDT is fully latent.
2. **Explicit kill/escalate decisions**: We write structured findings to a shared ledger (tree.json). RDT just updates `h_t`.
3. **Adversarial framing**: Bandit mentality — we model the attacker, not the output. RDT is generation-focused.
4. **Gate-7 quality filter**: Pre-submission check calibrated to Immunefi VRC v2.3. No analogue in RDT.

---

## Synthesis: Improving Our Hunt Loop

Borrowing from OpenMythos RDT design:

| OpenMythos concept | Hunt improvement |
|-------------------|------------------|
| Spectral stability (ρ < 1) | Each wave must close more leads than it opens. Track: `leads_killed / leads_opened` ratio per wave. If < 1, force kill pass before opening new angles. |
| Input injection every step | Begin every wave prompt with the full tree.json MEDIUM/LIVE section, not just a summary. Prevents agent "drift" from ground truth. |
| Loop index role | Assign explicit roles by wave index: W1=surface recon, W2=deep attack, W3=numeric PoC, W4=kill confirmation. Don't mix roles in one wave. |
| ACT halting | Hard rule: if 3 consecutive waves produce zero LIVE findings, hunt terminates. Don't loop forever. |
| MoE expert specialization | Pre-tag each lead with required expertise (fee_math, tick_array, pinocchio, token_2022) and route only to matching specialized agents. |
