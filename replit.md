# Aave Liquidation Bot (Base Network)

## Overview
A Python-based liquidation bot ("searcher") for the Aave v3 protocol on the Base (L2) blockchain. It monitors borrower positions, identifies those with a health factor below 1.0, and executes liquidations to earn a profit using flash loans and direct EOA gas payment.

## Tech Stack
- **Language**: Python 3.12
- **Async**: asyncio + aiohttp (persistent session with DNS cache)
- **Blockchain**: web3.py (v7+), EIP-1559 type-2 transactions
- **ETH Price**: Live CoinGecko feed (60 s cache, env fallback)
- **Environment**: python-dotenv

## Project Structure
- `main.py` — Core bot logic: BaseSearcher class, slippage guard, dynamic fees, main loop
- `requirements.txt` — Python dependencies
- `procfile` — Process definition (`worker: python main.py`)
- `README_FIXED.md` — Full optimization & change log

## How It Works
1. Queries the Aave V3 Base subgraph (The Graph) for top borrowers by debt
2. Hydrates all positions via Multicall3 (on-chain batch RPC) to get live health factors
3. Filters positions with health factor < 1.0 and estimated profit ≥ MIN_PROFIT_USD
4. Runs slippage guard: collateral seized must exceed (debt + flash fee + gas) × 1.01
5. Executes liquidations via HANDS contract using EOA direct gas payment (no paymaster)
6. Watches near-liquidation positions (HF 1.00–1.05) on the rebalance watchlist

## Required Environment Variables (Secrets)
| Variable | Description |
|---|---|
| `GRAPH_API_KEY` | The Graph API key for the Aave V3 Base subgraph |
| `BASE_RPC_URL` | HTTPS RPC URL for Base mainnet (public reads) |
| `PRIVATE_RPC_URL` | HTTPS RPC URL for private tx submission |
| `PRIVATE_KEY` | EOA wallet private key (signs liquidation transactions) |
| `WALLET_ADDRESS` | Must match the address derived from PRIVATE_KEY |

## Optional Environment Variables
| Variable | Default | Description |
|---|---|---|
| `EXECUTION_ENABLED` | `true` | `false` = dry-run (scan only, no tx) |
| `BASE_WSS_URL` | _(none)_ | WSS provider for public RPC (lower latency) |
| `PRIVATE_WSS_URL` | _(none)_ | WSS provider for private RPC |
| `AAVE_SUBGRAPH_URL` | The Graph Aave V3 Base | Override subgraph endpoint |
| `HANDS_CONTRACT` | `0x5573d...` | Liquidation contract address |
| `MIN_PROFIT_USD` | `1` | Minimum estimated profit to attempt liquidation |
| `MIN_COLLATERAL_COVERAGE` | `1.01` | Collateral must exceed costs by this factor (1 % guard) |
| `FLASHLOAN_FEE_BPS` | `9` | Aave V3 flash loan fee (9 bps = 0.09%) |
| `LIQUIDATION_BONUS_BPS` | `500` | Aave liquidation bonus (5%) |
| `MAX_PRIORITY_FEE_CAP_GWEI` | `2` | EIP-1559 priority tip cap |
| `ASSUMED_BASE_FEE_GWEI` | `0.02` | Pre-screening gas base fee assumption |
| `ASSUMED_PRIORITY_FEE_GWEI` | `0.04` | Pre-screening priority fee assumption |
| `ETH_PRICE_USD` | `3000` | Fallback ETH price if CoinGecko unreachable |
| `HEARTBEAT_SECONDS` | `10` | Polling interval |
| `BORROWER_LIMIT` | `100` | Max borrowers hydrated per tick |
| `MAX_CANDIDATES_PER_TICK` | `3` | Max liquidations per tick |
| `BLOCKED_ASSETS` | _(none)_ | Comma-separated asset addresses to skip |

## Workflow
- **Start application** — `python main.py` (console output, background worker)
- Bot will fail to start until required secrets are configured.
- When running, logs show `"status": "hunting_on_mainnet"` or `"dry_run"`.

## Optimizations Applied
- Persistent aiohttp session with TCP/DNS caching
- Live ETH price fetch (CoinGecko) for accurate gas USD estimates
- Dynamic EIP-1559 fees using live block baseFeePerGas
- Explicit slippage/collateral coverage guard before every execution
- Named Aave V3 flash loan fee constant (9 bps) matching executeOperation premium
- WSS provider option (BASE_WSS_URL / PRIVATE_WSS_URL)
- Enhanced startup logging with contract, chain, and mode info

## Network
- Chain: Base Mainnet (Chain ID: 8453)
- Protocol: Aave V3
- Gas: EOA direct (EIP-1559), no paymaster
