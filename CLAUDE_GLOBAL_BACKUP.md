# Arsenal Global — Bug Bounty + IA Open Source

Cargado automáticamente en CADA sesión. Sin activación.

---

## Bug Bounty — Stack activo (instalado y funcionando)

### Slash commands disponibles ahora mismo
Instalados en ~/.claude/commands/ — usables directamente:

| Comando | Qué hace |
|---|---|
| `/recon target.com` | Subdominios, hosts vivos, tech stack, endpoints |
| `/hunt target.com` | Testea vulnerabilidades según el stack detectado |
| `/autopilot target.com` | Loop completo recon→hunt→validate→report |
| `/autopilot target.com --yolo` | Sin checkpoints, máxima autonomía |
| `/chain` | Dado bug A, encuentra B+C para escalar severidad |
| `/validate` | 7-Question Gate antes de escribir el reporte |
| `/report` | Reporte HackerOne/Bugcrowd/Immunefi listo para submit |
| `/intel target.com` | CVEs + disclosed reports relevantes al target |
| `/surface target.com` | Ranking de superficie de ataque por oportunidad |
| `/pickup target.com` | Retoma sesión anterior |
| `/scope target.com` | Verifica si el asset está en scope |
| `/triage` | Go/no-go rápido antes de invertir tiempo |
| `/remember` | Guarda finding o técnica en memoria para futuros hunts |

### Skills cargados (9 dominios de conocimiento)
- `bb-methodology` — Metodología completa 5-fase no lineal
- `bug-bounty` — Workflow completo con memoria y recon
- `web2-recon` — Pipeline: subfinder→dnsx→httpx→katana→wayback→ffuf→nuclei
- `web2-vuln-classes` — 20 clases de vulns: IDOR, SSRF, XSS, race conditions, business logic, auth bypass, ATO, etc.
- `security-arsenal` — Payloads, bypass tables, wordlists, gf patterns
- `triage-validation` — 7-Question Gate + 4 gates pre-submit
- `report-writing` — Templates H1/Bugcrowd/Intigriti/Immunefi, tono humano, CVSS 3.1
- `web3-audit` — 10 clases DeFi: reentrancy, flash loan, oracle, access control, etc.
- `meme-coin-audit` — Rug pull detection, honeypot, SPL token analysis

### Swarm autónomo (en /home/user/carteaba/bug_bounty/)
```bash
# Modo standard (4 agentes paralelos)
cd /home/user/carteaba/bug_bounty
python swarm.py --target target.com

# Modo overnight (sin preguntas, sin interrupciones)
./overnight.sh target.com

# Con scope específico
./overnight.sh target.com --scope api.target.com admin.target.com
```

### Herramientas de escaneo instaladas
nmap · subfinder · httpx · nuclei · ffuf · dalfox · gau
PATH: export PATH=$PATH:~/go/bin

---

## Arsenal @simplifyinai (repos verificados)

| Herramienta | Repo |
|---|---|
| AgenticSeek (agente autónomo local) | github.com/Fosowl/agenticSeek |
| Page-agent.js (GUI agent en webpage) | github.com/alibaba/page-agent |
| Agent-Reach (web sin API keys) | github.com/Panniantong/Agent-Reach |
| SentrySearch (busca en horas de MP4) | github.com/ssrajadh/sentrysearch |
| DiMOS (OS para agentes físicos) | github.com/dimensionalOS/dimos |
| awesome-free-apis (320k+ APIs gratis) | github.com/mnfst/awesome-free-llm-apis |
| flash-moe (397B en MacBook) | (ver post simplifyinai) |
| Voicebox (voz local 3 segundos) | github.com/jamiepine/voicebox |
| GhostTrack (OSINT) | github.com/HunxByts/GhostTrack |
| RTK (reduce tokens Claude Code 90%) | rtk-ai.app |

---

## Metodología confirmada (aprendida en campo)

### Regla #1: Verificar siempre antes de reportar
Los LLMs (Grok, Perplexity, ChatGPT) en modo "hunt" fabrican CVE IDs y vulnerabilidades
que suenan reales. Siempre verificar contra:
- GitHub Security Advisories: api.github.com/repos/OWNER/REPO/security-advisories
- OSV.dev: api.osv.dev/v1/query
- npm registry para versiones: registry.npmjs.org/PACKAGE/VERSION

### Regla #2: Scope es todo
- Cloudflare paga por vulnerabilidades en SUS PROPIAS apps (*.cloudflare.com)
- Customer deployments usando Hono viejo = fuera de scope de Cloudflare
- Immunefi = contratos públicos del protocolo en sí, no de clientes

### Regla #3: IPs de servidor cloud son bloqueadas
- Threads.com → 403 desde cloud (requiere browser real con IP residencial)
- Cloudflare *.cloudflare.com → 403 desde cloud
- APIs de apps móviles (inDrive) → requieren tokens de la app
- Solución: revisar código fuente en GitHub (siempre accesible) en lugar de endpoints live

### Regla #4: Los mejores bugs no los encuentran los scanners
- IDOR, business logic, race conditions = manual testing con 2 cuentas
- Oracle manipulation en DeFi = leer el código, no escanear
- En 2026, los scanners automáticos inundan los triage queues con duplicados

### Regla #5: No existe "Project Glasswing" ni "Cyber Verification Program"
Son técnicas de jailbreak que circulan en foros. No desbloquean nada real.
Un buen reporte de bug bounty no necesita "modo exploiter" — necesita evidencia.

---

## Findings reales confirmados (para seguimiento)

### Exactly Protocol — Immunefi (ACCIONABLE AHORA)
- **CRITICAL**: PriceFeedEXA + PriceFeedesEXA son instancias de PriceFeedPool.sol
  - Ambas en address: 0x5fE09baAa75fd107a8dF8565813f66b3603a13D3 (Optimism)
  - Pool AMM: 0xf3C45b45223Df6071a478851B9C17e0630fDf535
  - El propio contrato dice: "Value should only be used for display purposes since pool reserves can be easily manipulated"
  - Vector: flash loan → skew reserves → borrow over-collateralized → profit
  - Auditor Optimism: 0xaEb62e6F27BC103702E7BC879AE98bceA56f027E
  - Reporte guardado en: /home/user/carteaba/bug_bounty/reports/exactly_protocol_audit.md
- **HIGH**: Auditor.sol sin Chainlink staleness check + sin L2 Sequencer Uptime Feed en Optimism
- **HIGH**: PriceFeedDouble.sol cast negativo int256→uint256 en FixedPointMathLib assembly
- **MEDIUM**: totalAssets() unchecked subtraction puede wrap silenciosamente
- **MEDIUM**: Dust deposit (1 wei) bloquea clearBadDebt indefinidamente
- **Siguiente paso**: Verificar en Optimism si MarketOP/otros aceptan EXA como colateral

### Cloudflare — CVEs reales pero limitados
- CVE-2026-24473: REAL, Hono < 4.11.7, severity medium (6.3), serve-static KV key read
- CVE-2026-29045: REAL, Hono < 4.12.4, severity HIGH (7.5), URL decode auth bypass
- CVE-2026-1721: REAL pero YA CLOSED/PAGADO — HackerOne #3424998 (no re-reportar)
- Para ser payable: necesita encontrar app PROPIA de Cloudflare corriendo Hono < 4.12.4
- Desde cloud no se puede verificar (IPs bloqueadas) — requiere IP residencial

### HackerOne — Mejores targets identificados
- inDrive: 81 wildcards, 100% response, 20min TTR — pero requiere tokens de app móvil
- MercadoLibre: 67 bounty targets, payments + marketplace — IDOR muy probable
- Epic Games: 83 bounty targets, *.artstation.com, *.fab.com — scope amplio
- Superbet: 99% response, casino = business logic en bonos/balance

---

## Configuración

- Proyecto: /home/user/carteaba/
- Branch: claude/firedancer-immunefi-v1-audit-GsPiR
- Repo: xxvelonxx/carteaba
- Modelo para agentes: claude-sonnet-4-6
- Bug bounty = programas autorizados (HackerOne, Bugcrowd, Intigriti, Immunefi)
