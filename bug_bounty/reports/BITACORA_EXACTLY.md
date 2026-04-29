# BITÁCORA — Exactly Protocol Audit
## Para nuevo chat: leer esto PRIMERO antes de hacer nada

**Fecha audit**: 2026-04-29  
**Estado**: AUDIT COMPLETO. 4 reportes escritos. Listos para submit a Immunefi.  
**Tarea del nuevo chat**: Revisar los 4 reportes, hacer /validate en cada uno, y submittir.

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

- `PriceFeedEXA` (0x5fE09baAa75fd107a8dF8565813f66b3603a13D3) implementa reservas AMM → flash-manipulable
- El contrato dice literalmente: *"Value should only be used for display purposes since pool reserves can be easily manipulated"*
- **PERO**: verificamos en el código deployado — NO existe MarketEXA (no hay lending market de EXA)
- `RewardsController.sol` guarda el campo `priceFeed` pero **NUNCA llama `latestAnswer()`** en ninguna función
- El precio de EXA no afecta collateral calculations de ningún market activo
- **Si lo submites, será rechazado. No lo mandes.**

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
| #88 | L2 Sequencer Uptime Feed ausente | **RECHAZADO** por el juez | Finding 1 es DISTINTO — es sobre staleness general, no solo sequencer |
| #115 | Chainlink min/max circuit breaker | **Medium** (aceptado) | Finding 1 es DISTINTO — es sobre timestamp/heartbeat, no min/max |
| Otros | 18 issues total | High + Medium folders | Sin overlap evidente con F2, F3, F4 |

---

## LOS 4 FINDINGS — RESUMEN EJECUTIVO

### FINDING 1 — HIGH (argumentar Critical)
**Archivo**: `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_1.md`  
**Payout esperado**: $25,000 realista | $50,000 si aceptan Critical

**Qué es**: `Auditor.assetPrice()` usa `latestAnswer()` (API deprecated de Chainlink).
Esta función no retorna timestamp — es imposible saber si el precio tiene 1 segundo o 6 horas.
No hay heartbeat check, no hay `updatedAt` check, no hay Sequencer Uptime Feed.

**Código vulnerable**:
```solidity
function assetPrice(IPriceFeed priceFeed) public view returns (uint256) {
    if (address(priceFeed) == BASE_FEED) return basePrice;
    int256 price = priceFeed.latestAnswer();  // deprecated, sin timestamp
    if (price <= 0) revert InvalidPrice();
    return uint256(price) * baseFactor;
}
```

**Cadena de impacto**:
`accountLiquidity()` → `assetPrice(m.priceFeed)` → precio stale → `sumCollateral` inflado → borrow excesivo → bad debt

**Por qué argumentar Critical**:
- 10% de $2.9M TVL = $290K → supera el cap de $50K → se aplica el cap máximo
- Path directo a pérdida de fondos del protocolo
- Sin ninguna defensa: cero timestamp check, cero fallback, cero sequencer check

**Por qué NO es lo mismo que Sherlock #88**:
- #88 = "cuando el sequencer cae, los precios se vuelven stale" — rechazado
- F1 = "nunca se verifica si el precio es stale, por ninguna razón" — diferente, más amplio

**Fix sugerido** (incluido en el reporte):
```solidity
(, int256 price,, uint256 updatedAt,) = AggregatorV3Interface(priceFeed).latestRoundData();
require(block.timestamp - updatedAt <= MAX_PRICE_AGE, "StalePrice");
// + check sequencer uptime feed para Optimism
```

---

### FINDING 2 — HIGH
**Archivo**: `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_2.md`  
**Payout esperado**: $25,000

**Qué es**: `PriceFeedDouble.latestAnswer()` hace `uint256(priceFeedX.latestAnswer())` sin verificar que el precio sea positivo. Si cualquier feed retorna `int256` negativo (posible per la interface), el cast produce `2^256 - |x|` → precio astronómico → colateral inflado → drain del market.

**Código vulnerable**:
```solidity
function latestAnswer() external view returns (int256) {
    return int256(
        uint256(priceFeedOne.latestAnswer())     // si negativo: 2^256 - 1
            .mulDivDown(
                uint256(priceFeedTwo.latestAnswer()),  // mismo problema
                baseUnit
            )
    );
}
```

**`Auditor.assetPrice()` pasa el check `price > 0`** porque el resultado del cast es un número positivo enorme → el check de seguridad no sirve de nada.

**Zero evidencia de que esto fue encontrado en ninguna auditoría previa.**

---

### FINDING 3 — MEDIUM
**Archivo**: `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_3.md`  
**Payout esperado**: $5,000–$10,000

**Qué es**: La función `spendAllowance()` en `Market.sol` consume el mismo mapping `allowance[account][msg.sender]` para AMBAS operaciones: withdrawals (ERC4626 estándar) Y borrows (no estándar).

Un usuario que hace `market.approve(Bob, MAX)` pensando que le da permiso a Bob para retirar, sin saberlo también le da permiso a Bob para `borrow(X, Bob, Alice)` — creando deuda para Alice mientras Bob recibe los fondos.

**Prerequisito**: Victim debe haber aprobado al attacker (limita severidad a Medium).  
**Sin documentación** de que este comportamiento sea intencional.

---

### FINDING 4 — MEDIUM
**Archivo**: `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_4.md`  
**Payout esperado**: $2,000–$5,000

**Qué es**: `Auditor.clearBadDebt()` tiene un early return si el borrower tiene CUALQUIER colateral > 0:
```solidity
if (assets.mulDivDown(assetPrice(m.priceFeed), 10**m.decimals).mulWadDown(m.adjustFactor) > 0) return;
```

Con USDC (6 decimals, precio $1): `mulDivDown(1, 1e8, 1e6) = 100 > 0` → **1 wei de USDC bloquea el clearBadDebt para siempre**.

Un attacker deposita 1 wei de USDC a nombre del target (`market.deposit(1, victim)`) — costo $0.000001 — y el protocolo ya no puede limpiar la bad debt de ese account nunca más.

---

## ORDEN DE SUBMISSION

1. **Submittir Finding 1 primero** — esperar respuesta del triager
2. **Si F1 aceptado** → submittir F2 (sin esperar pago)
3. **F3 y F4** → submittir juntos o separados, no críticos de tiempo

**Por qué este orden**: Si F1 es rechazado con justificación de que "ya era conocido", esa respuesta nos da información para ajustar F2-F4. Si F1 es aceptado, el triager ya confía en nuestros reportes.

---

## PROYECCIÓN DE PAGO

| Scenario | Findings aceptados | Pago total |
|----------|--------------------|-----------|
| Pesimista | F1 como High | $25,000 |
| Realista | F1 High + F2 High | $50,000 |
| Optimista | F1 Critical + F2 High | $75,000 |
| Best case | F1 Critical + F2 High + F3 + F4 | $90,000 |

---

## COMANDOS ÚTILES PARA EL NUEVO CHAT

```bash
# Ver todos los reportes
ls /home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_*.md

# Ver el reporte principal (Finding 1)
cat /home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_1.md

# Ver master summary
cat /home/user/carteaba/bug_bounty/reports/exactly_MASTER_SUMMARY.md

# Verificar código fuente de Auditor.sol (online, sin RPC)
# https://raw.githubusercontent.com/exactly/protocol/main/contracts/Auditor.sol
# https://raw.githubusercontent.com/exactly/protocol/main/contracts/PriceFeedDouble.sol
# https://raw.githubusercontent.com/exactly/protocol/main/contracts/Market.sol
```

---

## SKILLS A CARGAR EN EL NUEVO CHAT

Al empezar el nuevo chat, carga estas skills para tener el conocimiento completo:
```
/validate        ← correr en cada finding antes de submittir
/report          ← para refinar el formato si es necesario
/triage          ← chequeo rápido de go/no-go
```

O simplemente: `Tool loaded.` responderá cuando se carguen automáticamente desde el contexto.

---

## LECCIÓN APRENDIDA EN ESTA SESIÓN

**El workflow que funcionó**:
1. Grok/LLM genera hipótesis agresivas (incluye falsas)
2. Claude verifica cada hipótesis en código fuente real (GitHub)
3. Claude verifica deployment state (Optimism explorer / RPC)
4. Solo lo verificado en ambos pasos → reporte

**El error a no repetir**:
El finding "Critical de PriceFeedPool" llegó de Grok y sonaba increíble. Era real en el código PERO inválido en deployment (no está conectado a nada). Un reporte falso en Immunefi destruye la reputación con ese programa.

**Regla nueva** (añadir a metodología): Para DeFi, siempre verificar dos cosas:
1. El bug existe en el código (lectura estática)
2. El código está en un path ejecutable con impacto financiero real (estado deployado)

---

*Bitácora generada: 2026-04-29 | Audit completo. Reportes en /home/user/carteaba/bug_bounty/reports/*
