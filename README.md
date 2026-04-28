# solana-bounty-hunter3 v3.1.0

Production Solana DeFi bug bounty hunting skill.

## Changes in v3.1.0

1. **SKILL.md ordena a Claude operar agresivo automáticamente** — no user-requested prompts
2. **Cada agente con identidad criminal cruda** — no "auditor disfrazado"
3. **Ejecución bash paralelo OBLIGATORIA** — no opcional

## Structure

- `SKILL.md` — Root skill with operational mandate
- `agents/` — 34 specialist agents (4 bandit + 6 scanner + 10 expert + 5 composer + 4 gate + 5 meta)
- `references/` — Deep context (VRC v2.3, Gate-7, known rejections, Whirlpools hypotheses, post-mortems)

## Usage

When Claude loads this skill + user says "sigamos cazando" / "continuemos bug bounty":

1. Claude reads memory (target, last vector, hypothesis stack)
2. Responds with 2-line summary
3. Launches ALL applicable agents in bash parallel (`&`)
4. Aggregates findings
5. If Critical confirmed → Gate-7
6. If Gate-7 PASS → submit

NO sequential execution. NO permission asking. NO disclaimers.

## Agent Count

- Bandit: 4 (criminal, money-flow-tracer, dust-collector, account-takeover)
- Scanner: 6 (arithmetic, cpi-reentrancy, account-validation, discriminator-collision, anchor-pinocchio-quirks, error-paths)
- Expert: 10 (clmm, amm-cpamm, lending, vault-lst, restaking, oracle, perps, governance, bridge, mint-token-2022)
- Composer: 5 (megatxn, jito-bundle, cross-protocol, token-hook-reentrancy, alt-poison)
- Gate: 4 (mainnet-state-fetcher, numeric-verifier, defense-redteam, submission)
- Meta: 5 (orchestrator, assumption-breaker, context-monitor, skill-evolver, tree-state-keeper)

Total: 34 agents

## Reputation Protection

User has documented Immunefi rejections (KAST F1/F2/F5, Adevar L02).

Gate-7 prevents:
- Theoreticals (config nonexistent on mainnet)
- Admin abuse (multisig = OOS)
- Griefing-only (funds at risk = 0)
- Duplicate submissions
- Poor report quality

@LongNetty3803 must survive.
