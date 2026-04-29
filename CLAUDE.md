# Proyecto carteaba — Bug Bounty Agent

## Objetivo
Agente de bug bounty autónomo usando Claude como cerebro principal.
Metodología OWASP completa, reports listos para HackerOne/Bugcrowd.

## Estructura del proyecto
```
carteaba/
├── bug_bounty/
│   ├── agent.py          # Agente principal
│   ├── recon.py          # Reconocimiento automatizado
│   ├── hunt.py           # Hunting de vulnerabilidades
│   ├── validate.py       # Validación de PoCs
│   └── report.py         # Generación de reportes
├── threads_posts.json    # Posts scrapeados de @simplifyinai
├── analysis.md           # Análisis del perfil @simplifyinai
└── CLAUDE.md             # Este archivo
```

## Frameworks instalados / a instalar
- **CAI**: `github.com/aliasrobotics/cai` — base del agente
- **PentestAgent**: `github.com/GH05TCREW/pentestagent` — módulos de pentesting
- **claude-bug-bounty**: `github.com/shuvonsec/claude-bug-bounty` — slash commands

## Variables de entorno necesarias
```bash
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=claude-sonnet-4-6
TARGET=target.com  # dominio del programa de bug bounty
```

## Flujo de trabajo del agente
1. `/recon $TARGET` — Subdominios, puertos, tecnologías
2. `/hunt` — Busca CVEs, OWASP Top 10, lógica de negocio
3. `/autopilot` — Modo autónomo con herramientas Kali
4. `/validate` — Confirma PoC, descarta falsos positivos
5. `/report` — Genera markdown listo para HackerOne/Bugcrowd

## Herramientas de soporte
- **Page-agent.js**: Automatización browser para testing de apps web
- **Agent-Reach**: Acceso web sin API keys para OSINT
- **awesome-free-apis**: APIs gratuitas para enriquecer recon

## Notas de seguridad
- Solo targets con programa de bug bounty activo y autorización explícita
- Guardar scope del programa antes de cada sesión
- No atacar infraestructura fuera del scope definido
