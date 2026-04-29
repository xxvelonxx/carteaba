# Exactly Protocol — Security Audit
**Plataforma**: Immunefi
**Fecha**: 2026-04-29
**Contratos**: Market.sol, Auditor.sol, InterestRateModel.sol, PriceFeedPool.sol, PriceFeedDouble.sol, PriceFeedWrapper.sol, MarketBase.sol, FixedLib.sol
**Red**: Optimism (L2)

---

## FINDING 1 — CRITICAL: PriceFeedPool.sol — Flash Loan Oracle Manipulation

**El contrato ADMITE el problema en su propio código:**
```solidity
/// @dev Value should only be used for display purposes since pool reserves can be easily manipulated.
```

**Vector de ataque:**
1. Flash loan de gran cantidad
2. Swap masivo para manipular `reserve0/reserve1`
3. Llamar función del protocolo que use este price feed (borrow, liquidation check)
4. Robar colateral o pedir prestado más de lo que el colateral vale
5. Repagar flash loan en la misma tx

**Cadena:**
`Auditor.accountLiquidity()` → `assetPrice(m.priceFeed)` → `PriceFeedPool.latestAnswer()` → reservas manipuladas → `sumCollateral` inflado

**PoC (pseudocódigo):**
```
1. flashloan(WETH, 1000 ETH)
2. pool.swap(1000 ETH → tokenX)  // skews reserves
3. market.borrow(maxAmount)       // uses inflated collateral price
4. pool.swap(tokenX → WETH)      // restore reserves
5. repay flashloan
```

**ACCIÓN REQUERIDA**: Verificar en Optimism si algún Market tiene PriceFeedPool como oracle principal.
Contrato Auditor en Optimism: necesita confirmación de dirección deployada.

---

## FINDING 2 — HIGH: Auditor.sol — Sin staleness check en Chainlink + sin sequencer check en Optimism

**Código vulnerable:**
```solidity
function assetPrice(IPriceFeed priceFeed) public view returns (uint256) {
    if (address(priceFeed) == BASE_FEED) return basePrice;
    int256 price = priceFeed.latestAnswer();  // deprecated, no timestamp
    if (price <= 0) revert InvalidPrice();
    return uint256(price) * baseFactor;
}
```

**Problemas:**
1. Usa `latestAnswer()` (deprecated por Chainlink) — no verifica timestamp
2. No tiene Chainlink L2 Sequencer Uptime Feed para Optimism
3. Durante downtime del sequencer, precios stale se usan para borrow/liquidation

**Impacto en Optimism**: Cuando el sequencer cae y vuelve, precios pueden estar horas desactualizados.
Permite over-borrowing (precio colateral inflado) o bloqueo de liquidaciones necesarias.

**Fix estándar:**
```solidity
(, int256 price, , uint256 updatedAt, ) = priceFeed.latestRoundData();
require(block.timestamp - updatedAt <= HEARTBEAT, "StalePrice");
// + sequencer uptime feed check
```

---

## FINDING 3 — HIGH: PriceFeedDouble.sol — Cast negativo int256 → uint256

**Código:**
```solidity
function latestAnswer() external view returns (int256) {
    return int256(uint256(priceFeedOne.latestAnswer()).mulDivDown(
        uint256(priceFeedTwo.latestAnswer()), baseUnit
    ));
}
```

**Si `priceFeedTwo` devuelve negativo**: `uint256(-1) = 2^256 - 1` → precio astronomicamente inflado.
`FixedPointMathLib.mulDivDown` usa assembly interno (unchecked) → no hay overflow protection de Solidity 0.8.

---

## FINDING 4 — HIGH: Market.sol — Cross-purpose allowance (deposit shares usadas para autorizar borrows)

La misma variable `allowance[account][msg.sender]` (diseñada para ERC4626 withdrawal shares) se usa para autorizar borrows de terceros.

Usuario que aprobó a un tercero para retirar shares implícitamente le dio permiso para pedir prestado en su nombre.

---

## FINDING 5 — MEDIUM: MarketBase.totalAssets() — unchecked wrapping subtracción

```solidity
function totalAssets() public view override returns (uint256) {
    unchecked {
        // ...
        return ... + (totalFloatingBorrowAssets() - floatingDebt).mulWadDown(...);
        //           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        //           Esta resta está en bloque unchecked — si underflows, wraps a uint256 max
    }
}
```

Share price inflado artificialmente → redimir más del valor real depositado.

---

## FINDING 6 — MEDIUM: Auditor.sol — Dust deposit griefing bloquea clearBadDebt

```solidity
if (assets.mulDivDown(assetPrice(m.priceFeed), 10**m.decimals).mulWadDown(m.adjustFactor) > 0) return;
```

Con solo **1 wei** en cualquier market con precio no-cero, un atacante puede prevenir que su deuda mala sea eliminada indefinidamente. Costo del ataque: mínimo.

---

## PRÓXIMOS PASOS CONCRETOS

### Paso 1: Verificar configuración deployada
```bash
# Encontrar address del Auditor en Optimism
# Leer qué price feed está registrado para cada market
# Si algún market usa PriceFeedPool → Finding 1 es CRITICAL y explotable
```

### Paso 2: Verificar sequencer check
```bash
# Verificar que Auditor no tiene Chainlink L2 Sequencer Feed
# Explorar https://optimistic.etherscan.io/address/[AUDITOR_ADDRESS]
```

### Paso 3: Escribir reportes para Immunefi
Orden de prioridad: Finding 1 > Finding 2 > Finding 5 > Finding 6

