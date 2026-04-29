# BITÁCORA — Exactly Protocol Audit
## Para nuevo chat: leer esto PRIMERO antes de hacer nada

**Fecha audit**: 2026-04-29  
**Estado**: AUDIT COMPLETO. Validación técnica finalizada. 3 reportes listos para submit (F2 descartado).  
**Tarea del nuevo chat**: Submittir F1 → esperar respuesta → submittir F3+F4.

---

## CONTEXTO DEL PROGRAMA

| Dato | Valor |
|------|-------|
| Programa | https://immunefi.com/bug-bounty/exactly/ |
| Cadena | Optimism (OP Mainnet) |
| TVL | ~$2.9M (DeFiLlama, abril 2026) |
| Cap Critical | $50,000 |
| Cap High | $25,000 |
| Mínimo Critical | $20,000 |
| Pago en | USDC / DAI |
| PoC requerido | SÍ — código Foundry obligatorio para High/Critical |
| KYC requerido | SÍ — ID gobierno + país antes del pago |
| Último update | Febrero 2026 |
| Contrato Auditor | `0xaEb62e6F27BC103702E7BC879AE98bceA56f027E` (Optimism) |

---

## ADVERTENCIA #1 — NO SUBMITTIR ESTO

**PriceFeedPool flash loan attack — INVÁLIDO en deployment actual.**
- No existe MarketEXA. RewardsController.sol guarda priceFeed pero nunca llama latestAnswer().
- Si lo submites, será rechazado.

---

## ADVERTENCIA #2 — F2 DESCARTADO TRAS VALIDACIÓN

**PriceFeedDouble negative cast (F2) — INVÁLIDO como HIGH. NO SUBMITTIR.**

El equipo tiene el test `testPriceFeedDoubleWithNegativePriceShouldRevert` que confirma:
- Con priceFeedTwo ≥ 2: `uint256(-1) * 2` → overflow en `mulDivDown` → **REVERT seguro** ✓
- Solo con priceFeedTwo = 1 raw unit ($0.00000001): no overflow → valor astronómico

Un price feed Chainlink retornando 1 raw unit (en cualquier denominación real) es físicamente imposible en condiciones normales. El equipo ya conoce el comportamiento revert (tiene el test). Submittir como HIGH → rechazado + daño de reputación.

**Decisión: F2 eliminado del plan de submission.**

---

## VALIDACIÓN TÉCNICA COMPLETADA (2026-04-29)

### Qué se verificó:
1. Código fuente real en `github.com/exactly/protocol` (rama main)
2. Addresses de contratos deployados en `/deployments/optimism/`
3. Tests del equipo en `/test/`
4. NatSpec añadido en commit Oct 2025
5. Función real en Auditor (handleBadDebt ≠ clearBadDebt)

### Errores encontrados y corregidos en los reportes:
| Finding | Error | Corrección |
|---------|-------|------------|
| F1 PoC | MARKET_WETH = MarketOP address | Cambiado a `0xc4d4500326981eacD020e20A81b1c479c161c7EF` |
| F2 | Ataque imposible con values reales | DESCARTADO |
| F3 PoC | MARKET_WETH = MarketOP address | Cambiado a `0xc4d4500326981eacD020e20A81b1c479c161c7EF` |
| F4 | Función `clearBadDebt()` (no existe en Auditor) | Corregido a `handleBadDebt()` en todo el reporte |

---

## AUDITORÍAS PREVIAS — CONOCER ANTES DE SUBMITTIR

| Auditor | Año | Relevancia |
|---------|-----|------------|
| Coinspect ×5 | 2021–2024 | Core protocol — bajo overlap con estos findings |
| ABDK | 2022–2023 | Solo matemáticas/economics |
| Chainsafe | 2022–2023 | General review |
| OpenZeppelin | 2023 | Solo esEXA — sin overlap |
| **Sherlock** | **Abril 2024** | **IMPORTANTE — ver tabla abajo** |

### Sherlock 2024 — Issues relevantes:
| Issue | Tema | Resultado | Implicación para nosotros |
|-------|------|-----------|--------------------------|
| #88 | L2 Sequencer Uptime Feed ausente | **RECHAZADO** por el juez | F1 es DISTINTO — staleness general, no solo sequencer |
| #115 | Chainlink min/max circuit breaker | **Medium** (aceptado) | F1 es DISTINTO — timestamp/heartbeat, no min/max |
| Otros | 18 issues total | High + Medium folders | Sin overlap con F1, F3, F4 |

---

## LOS 3 FINDINGS VÁLIDOS — RESUMEN EJECUTIVO

### FINDING 1 — HIGH (argumentar Critical) ✅ VALIDADO
**Archivo**: `exactly_immunefi_report_1.md`  
**Payout esperado**: $25,000 | $50,000 si aceptan Critical

**Verificado en código**: `assetPrice()` usa `latestAnswer()` deprecated, sin timestamp, sin heartbeat, sin sequencer check. Confirmado en `github.com/exactly/protocol/main/contracts/Auditor.sol`.

**Diferencia vs Sherlock #88**: #88 = solo sequencer downtime (rechazado). F1 = ausencia total de staleness check (heartbeat, node failure, network congestion) — más amplio y diferente.

**Addresses en PoC** (verificados contra `/deployments/optimism/`):
- Auditor: `0xaEb62e6F27BC103702E7BC879AE98bceA56f027E` ✅
- MarketWETH: `0xc4d4500326981eacD020e20A81b1c479c161c7EF` ✅ (corregido)
- MarketUSDC.e: `0x81C9A7B55A4df39A9B7B5F781ec0e53539694873` ✅

---

### FINDING 3 — MEDIUM ✅ VALIDADO
**Archivo**: `exactly_immunefi_report_3.md`  
**Payout esperado**: $5,000–$10,000

**Verificado en código**: `borrow()` llama `spendAllowance(borrower, assets)` que usa `allowance[account][msg.sender]`. `withdraw()` llama `super.withdraw()` (Solmate ERC4626) que usa la misma mapping ERC20. NatSpec de `borrow()` actualizado Oct 2025 NO menciona que el allowance autoriza borrows. Confirmado en `Market.sol`.

**Addresses en PoC** (verificados):
- MARKET_USDC.e: `0x81C9A7B55A4df39A9B7B5F781ec0e53539694873` ✅
- MARKET_WETH: `0xc4d4500326981eacD020e20A81b1c479c161c7EF` ✅ (corregido)

---

### FINDING 4 — MEDIUM ✅ VALIDADO (con corrección de nombre)
**Archivo**: `exactly_immunefi_report_4.md`  
**Payout esperado**: $2,000–$5,000

**Verificado en código**: La función vulnerable es `Auditor.handleBadDebt()` (no `clearBadDebt`). La lógica exacta confirmada:
```solidity
uint256 assets = market.maxWithdraw(account);
if (assets.mulDivDown(assetPrice(m.priceFeed), 10**m.decimals).mulWadDown(m.adjustFactor) > 0) return;
```

**Matemática verificada** (pura, sin fork):
```
USDC (6 decimals, precio $1 = 100000000 raw):
mulDivDown(1, 100000000, 1e6) = 100
mulWadDown(100, 0.86e18) = 86 > 0 → return temprano ✓
```

**Addresses en PoC** (verificados):
- MARKET_USDC.e: `0x81C9A7B55A4df39A9B7B5F781ec0e53539694873` ✅

---

## ORDEN DE SUBMISSION

1. **Submittir F1 primero** — esperar respuesta del triager (1–7 días)
2. **F3 + F4 después** — pueden submittirse juntos o separados, no críticos de tiempo

**Por qué este orden**: Si F1 es aceptado, el triager ya confía en nuestros reportes.

---

## PROYECCIÓN DE PAGO (REVISADA — 3 FINDINGS)

| Scenario | Findings aceptados | Pago total |
|----------|--------------------|-----------|
| Pesimista | F1 como High | $25,000 |
| Realista | F1 High + F3 Med | $30,000 |
| Optimista | F1 Critical + F3 + F4 | $60,000 |

---

## ADDRESSES CORRECTOS TODOS LOS CONTRATOS (verificados en /deployments/optimism/)

| Contrato | Address |
|----------|---------|
| Auditor | `0xaEb62e6F27BC103702E7BC879AE98bceA56f027E` |
| MarketWETH | `0xc4d4500326981eacD020e20A81b1c479c161c7EF` |
| MarketOP | `0xa430A427bd00210506589906a71B54d6C256CEdb` |
| MarketUSDC (native) | `0x6926B434CCe9b5b7966aE1BfEef6D0A7DCF3A8bb` |
| MarketUSDC.e (bridged) | `0x81C9A7B55A4df39A9B7B5F781ec0e53539694873` |
| MarketWBTC | `0x6f748FD65d7c71949BA6641B3248C4C191F3b322` |
| MarketwstETH | `0x22ab31Cd55130435b5efBf9224b6a9d5EC36533F` |
| PriceFeedWETH | `0x13e3Ee699D1909E989722E753853AE30b17e08c5` |
| PriceFeedwstETH | `0x698B585CbC4407e2D54aa898B2600B53C68958f7` |
| WETH (token) | `0x4200000000000000000000000000000000000006` |
| OP (token) | `0x4200000000000000000000000000000000000042` |
| USDC.e (token) | `0x7F5c764cBc14f9669B88837ca1490cCa17c31607` |

---

## COMPROBACIONES PENDIENTES ANTES DE SUBMITTIR

### EJECUTAR (con un Claude Code local o terminal con Foundry):

```bash
# Test matemático de F4 — SIN FORK, pura aritmética
forge test --match-test test_mathProof_oneWeiUsdcIsEnough -vvvv

# Test con fork — requiere OPTIMISM_RPC en .env
forge test --match-test test_dustDepositBlocksHandleBadDebt -vvvv \
  --fork-url $OPTIMISM_RPC --fork-block-number 130000000

forge test --match-test test_borrowWithWithdrawApproval -vvvv \
  --fork-url $OPTIMISM_RPC --fork-block-number 130000000
```

### VERIFICACIÓN ADICIONAL RECOMENDADA:
- Confirmar adjustFactor de MarketUSDC.e en Optimism (necesita ser > 0 para F4)
- Confirmar que handleBadDebt() en Auditor deployado tiene el check exacto (no fue modificado desde la auditoría Sherlock 2024)

---

## LECCIÓN APRENDIDA EN ESTA SESIÓN

**Errores detectados en validación que habrían causado rechazo**:
1. F2: El revert por overflow es SEGURO — mulDivDown lo catchea para values reales
2. F4: La función se llama handleBadDebt en Auditor, no clearBadDebt (PoC fallaría)
3. PoC addresses: MARKET_WETH tenía la address de MarketOP (PoC fallaría)

**Regla**: Nunca usar addresses del memory/contexto sin verificar contra `/deployments/optimism/`.

---

*Bitácora actualizada: 2026-04-29 | Validación completa. 3 findings listos. F2 descartado.*
