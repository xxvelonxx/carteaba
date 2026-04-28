# VRC v2.3 Severity Classification (Immunefi)

CRITICAL:
- Direct theft of user funds
- Direct theft of protocol funds
- Permanent freezing of funds

HIGH:
- Theft requiring conditions (flash loan, oracle manipulation, etc.)
- Permanent freezing requiring conditions
- Protocol insolvency

MEDIUM:
- Griefing (no profit to attacker, DoS, etc.)
- Temporary freezing

LOW:
- Contract fails to deliver promised returns (yield farming, staking)

INFORMATIONAL:
- Theoretical bugs with no funds at risk today

KEY RULES:
- Admin/multisig abuse → OOS or Low (not Critical)
- Feasibility limits downgrade severity
- PoC required (no PoC = auto-reject)
