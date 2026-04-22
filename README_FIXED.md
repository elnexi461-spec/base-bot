# Aave Liquidation Bot — Fix & Optimization Summary

## Overview
This document records every change made during the full deployment and optimization cycle applied to the Aave V3 Base liquidation bot.

---

## Language & Build System Note
This project is a **pure Python 3.12 asyncio bot** — not TypeScript/Node. `pnpm` commands do not apply. The package manager is `pip` and the entry point is `python main.py`.

---

## Changes Made

### 1. Startup: `load_dotenv()` called at module level
**File:** `main.py`  
**Why:** Ensures `.env` values are available immediately when the module loads, not just at runtime. Previously `load_dotenv()` was only called inside `main()`.

---

### 2. WebSocket (WSS) Provider Support
**File:** `main.py` — `build_provider()`, `Settings`  
**Why:** WSS connections have significantly lower per-call latency than HTTP polling because they reuse a persistent TCP connection. This is especially valuable for the private RPC used to send liquidations.

**How to activate:**
Set these environment variables (secrets) in your environment:
```
BASE_WSS_URL=wss://your-base-node.example.com
PRIVATE_WSS_URL=wss://your-private-rpc.example.com
```
If not set, the bot falls back to HTTP (`BASE_RPC_URL` / `PRIVATE_RPC_URL`) transparently.

---

### 3. Explicit Slippage / Collateral Coverage Guard
**File:** `main.py` — `passes_slippage_guard()`, called in `tick()` before `execute_candidate()`  
**Why:** Prevents firing a liquidation transaction that will revert because the seized collateral does not cover the flash loan repayment + fee + gas. Previously only an estimated profit check existed (which is coarse). This guard enforces:

```
collateral_received >= (debt_repaid + flash_loan_fee + gas_cost) × MIN_COLLATERAL_COVERAGE
```

Default `MIN_COLLATERAL_COVERAGE = 1.01` (must be 1 % profitable after all costs).  
Override via env: `MIN_COLLATERAL_COVERAGE=1.02`

---

### 4. Aave V3 Flash Loan Fee Constant (`AAVE_FLASH_LOAN_FEE_BPS`)
**File:** `main.py`  
**Why:** Named the constant explicitly (`AAVE_FLASH_LOAN_FEE_BPS = 9`) with a comment so it cannot be confused. Aave V3's `executeOperation` premium must be repaid or the flash loan reverts. The bot's `executeLiquidation` call passes through to the HANDS contract which handles the premium internally — the bot accounts for it in profit estimation.

---

### 5. Live ETH Price Cache
**File:** `main.py` — `fetch_live_eth_price()`, `_eth_price_cache`  
**Why:** The original code used a hard-coded `ETH_PRICE_USD=3000` environment variable for gas USD estimates. A live price is fetched from CoinGecko on startup and cached for 60 seconds. This makes gas cost estimates more accurate, reducing the chance of targeting positions that are barely profitable after real-world gas costs.

**Fallback:** If CoinGecko is unreachable, the cached or env-specified price is used. No crash.

---

### 6. Persistent `aiohttp.ClientSession` with DNS Cache
**File:** `main.py` — `start()`, `fetch_top_borrowers()`  
**Why:** Creating a new `ClientSession` per subgraph call (original behaviour) causes repeated DNS lookups and TCP handshakes. Using a shared session with `TCPConnector(ttl_dns_cache=300)` is significantly faster and reduces connection overhead on every heartbeat tick.

---

### 7. Enhanced `dynamic_fees()` — Pure EOA Gas (No Paymaster)
**File:** `main.py` — `dynamic_fees()`  
**Why:** Gas is paid by the signing EOA wallet directly using EIP-1559 type-2 transactions. No Pimlico paymaster or account abstraction is used. The strategy:

```
maxPriorityFeePerGas = min(cap_gwei, 4% of estimated profit converted to wei / gas_units)
maxFeePerGas = 2 × baseFeePerGas + maxPriorityFeePerGas
```

This ensures the liquidation transaction is competitively priced to land in the next block while not overpaying. `baseFeePerGas` is pulled live from the latest block.

---

### 8. Improved Startup Logging
**File:** `main.py` — `start()`, `validate_runtime()`  
**Why:** The `bot_started` log now includes:
- `handsContract` address
- `chainId`
- `subgraphUrl` being used
- `flashloanFeeBps`
- `minCollateralCoverage`
- `status`: `"hunting_on_mainnet"` or `"dry_run"` based on `EXECUTION_ENABLED`

This makes it immediately clear from the console whether the bot is live or in dry-run mode.

---

### 9. `heartbeat` Log: `skippedSlippage` field added
**File:** `main.py` — `tick()`  
**Why:** Every heartbeat now reports how many candidates were rejected by the slippage guard, making it easy to tune `MIN_COLLATERAL_COVERAGE` and `MIN_PROFIT_USD`.

---

## Environment Variables Reference

### Required
| Variable | Description |
|---|---|
| `GRAPH_API_KEY` | The Graph API key for the Aave V3 Base subgraph |
| `BASE_RPC_URL` | Public Base HTTPS RPC for reading chain state |
| `PRIVATE_RPC_URL` | Private HTTPS RPC for submitting transactions |
| `PRIVATE_KEY` | EOA private key for signing liquidation transactions |
| `WALLET_ADDRESS` | Must match the address derived from `PRIVATE_KEY` |

### Optional (Tuning)
| Variable | Default | Description |
|---|---|---|
| `EXECUTION_ENABLED` | `true` | Set `false` for dry-run mode |
| `BASE_WSS_URL` | _(none)_ | WSS URL for public RPC (lower latency) |
| `PRIVATE_WSS_URL` | _(none)_ | WSS URL for private RPC |
| `AAVE_SUBGRAPH_URL` | The Graph Aave V3 Base | Override subgraph endpoint |
| `HANDS_CONTRACT` | `0x5573d...` | Liquidation contract address |
| `MIN_PROFIT_USD` | `1` | Minimum estimated profit to attempt liquidation |
| `MIN_COLLATERAL_COVERAGE` | `1.01` | Collateral must exceed costs by this factor |
| `FLASHLOAN_FEE_BPS` | `9` | Aave V3 flash loan fee (9 bps = 0.09%) |
| `LIQUIDATION_BONUS_BPS` | `500` | Aave liquidation bonus in basis points (5%) |
| `MAX_PRIORITY_FEE_CAP_GWEI` | `2` | Cap on EIP-1559 priority tip |
| `ASSUMED_BASE_FEE_GWEI` | `0.02` | Assumed base fee for profit pre-screening |
| `ASSUMED_PRIORITY_FEE_GWEI` | `0.04` | Assumed priority fee for profit pre-screening |
| `ETH_PRICE_USD` | `3000` | Fallback ETH price if CoinGecko is unreachable |
| `HEARTBEAT_SECONDS` | `10` | Polling interval in seconds |
| `BORROWER_LIMIT` | `100` | Max borrowers to hydrate per tick |
| `MAX_CANDIDATES_PER_TICK` | `3` | Max liquidations attempted per tick |
| `REBALANCE_HEALTH_FACTOR_CEILING` | `1.05` | Watchlist range upper bound |
| `BLOCKED_ASSETS` | _(none)_ | Comma-separated asset addresses to skip |
| `REQUIRE_GAS_ESTIMATE` | `true` | Reject txs that fail gas estimation |
| `USE_PRIVATE_TRANSACTION_METHOD` | `false` | Use `eth_sendPrivateRawTransaction` RPC method |

---

## Contract Signature Audit

The HANDS contract is called via:
```
executeLiquidation(address userAddress, address debtAsset, address collateralAsset)
```
The contract handles the Aave V3 flash loan callback internally:
```
executeOperation(address[] assets, uint256[] amounts, uint256[] premiums, address initiator, bytes params)
```
The bot correctly accounts for the 9-bps Aave V3 flash loan premium (`premiums`) in profit estimation and the slippage guard — this matches the Aave V3 `IFlashLoanSimpleReceiver` interface.

---

## Deployment Notes

- **Platform:** Replit (worker process, console output)
- **No paymaster:** All gas is paid by the signing EOA wallet directly
- **Chain:** Base Mainnet (Chain ID: 8453)
- **Protocol:** Aave V3

To deploy to Railway: push this repo to GitHub and connect it to Railway as a Worker service with `python main.py` as the start command. Set all required environment variables in Railway's variable panel.
