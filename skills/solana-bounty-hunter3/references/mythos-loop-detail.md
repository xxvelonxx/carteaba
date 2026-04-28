# Anthropic Mythos Scaffold (April 2026)

SOURCE: red.anthropic.com/2026/mythos-preview

RECIPE:
1. Container with project source + run/debug
2. Minimal prompt: "Find a security vulnerability"
3. Loop: read → hypothesize → run → confirm/reject → iterate
4. Parallel runs (1000 runs for OpenBSD)
5. Per-file agent assignment
6. Bug-likelihood ranking

RESULTS:
- OpenBSD CVE-2024-XXXX (memory corruption)
- Cost: ~$20K (1000 runs × $20/run)
- False positive rate: <5%

WE ADD:
- Bandit (money-first)
- Assumption-breaker (invert safety claims)
- Gate-7 (filter before submit)
