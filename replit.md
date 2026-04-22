# Aave Liquidation Bot (Base Network)

## Overview
A Python-based liquidation bot ("searcher") for the Aave v3 protocol on the Base (L2) blockchain. It monitors borrower positions, identifies those with a health factor below 1.0, and executes liquidations to earn a profit.

## Tech Stack
- **Language**: Python 3.12
- **Async**: asyncio + aiohttp
- **Blockchain**: web3.py (v6+)
- **Environment**: python-dotenv

## Project Structure
- `main.py` — Core bot logic (BaseSearcher class, ABI definitions, main loop)
- `requirements.txt` — Python dependencies
- `procfile` — Process definition (worker: python main.py)

## How It Works
1. Queries the Aave subgraph (The Graph) for borrower positions
2. Hydrates positions via Multicall3 on-chain calls
3. Monitors a watchlist of positions nearing liquidation
4. Calculates profitability (accounting for gas + flash loan costs)
5. Executes liquidations if `EXECUTION_ENABLED=true`

## Required Environment Variables
Set these in Replit Secrets before running:

| Variable | Description |
|---|---|
| `GRAPH_API_KEY` | The Graph API key for querying the Aave subgraph |
| `BASE_RPC_URL` | Public Base RPC URL for reading chain data |
| `PRIVATE_RPC_URL` | Private RPC URL for submitting transactions (e.g., Flashbots) |
| `PRIVATE_KEY` | Wallet private key for signing transactions |
| `WALLET_ADDRESS` | Searcher wallet address |

## Optional Environment Variables
| Variable | Default | Description |
|---|---|---|
| `EXECUTION_ENABLED` | false | Set to `true` to enable live liquidation execution |
| `HANDS_CONTRACT` | 0x5573d... | Custom liquidation contract address |
| `POOL_ADDRESSES_PROVIDER` | 0xe20f... | Aave Pool Addresses Provider |
| `AAVE_SUBGRAPH_URL` | (default) | Custom subgraph URL |

## Workflow
- **Start application** — `python main.py` (console output, background worker)
- The bot will fail to start without the required environment variables configured.

## Network
- Chain: Base (Chain ID: 8453)
- Protocol: Aave v3
