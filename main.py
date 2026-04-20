from web3.types import RPCEndpoint
from hexbytes import HexBytes

import asyncio
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from os import getenv
from typing import Any

import aiohttp
from dotenv import load_dotenv
from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

DEFAULT_AAVE_SUBGRAPH_DEPLOYMENT_ID = "GQFbb95cE6d8mV989mL5figjaGaKCQB3xqYrr1bRyXqF"
DEFAULT_POOL_ADDRESSES_PROVIDER = "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
DEFAULT_HANDS_CONTRACT = "0x5573d354c9a991c3d09c34eee775c499e629275e"
WAD = Decimal("1000000000000000000")
BPS = Decimal("10000")
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

POOL_ADDRESSES_PROVIDER_ABI = [
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

POOL_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"internalType": "uint256", "name": "totalCollateralBase", "type": "uint256"},
            {"internalType": "uint256", "name": "totalDebtBase", "type": "uint256"},
            {"internalType": "uint256", "name": "availableBorrowsBase", "type": "uint256"},
            {"internalType": "uint256", "name": "currentLiquidationThreshold", "type": "uint256"},
            {"internalType": "uint256", "name": "ltv", "type": "uint256"},
            {"internalType": "uint256", "name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

BASE_AAVE_HANDS_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "userAddress", "type": "address"},
            {"internalType": "address", "name": "debtAsset", "type": "address"},
            {"internalType": "address", "name": "collateralAsset", "type": "address"},
        ],
        "name": "executeLiquidation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "proxy", "type": "address"},
            {"internalType": "address", "name": "service", "type": "address"},
            {"internalType": "address", "name": "debtAsset", "type": "address"},
            {"internalType": "address", "name": "rewardAsset", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "bytes", "name": "serviceCallData", "type": "bytes"},
        ],
        "name": "executeRebalance",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

MULTICALL3_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bool", "name": "allowFailure", "type": "bool"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Call3[]",
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate3",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "success", "type": "bool"},
                    {"internalType": "bytes", "name": "returnData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Result[]",
                "name": "returnData",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "payable",
        "type": "function",
    }
]


@dataclass(frozen=True)
class Settings:
    graph_api_key: str
    rpc_url: str
    private_rpc_url: str
    private_key: str
    wallet_address: str
    hands_contract: str
    subgraph_url: str
    pool_addresses_provider: str = DEFAULT_POOL_ADDRESSES_PROVIDER
    chain_id: int = 8453
    execution_enabled: bool = True
    heartbeat_seconds: int = 10
    borrower_limit: int = 100
    subgraph_page_size: int = 1000
    max_candidates_per_tick: int = 3
    min_profit_usd: Decimal = Decimal("1")
    liquidation_bonus_bps: Decimal = Decimal("500")
    flashloan_fee_bps: Decimal = Decimal("9")
    max_priority_fee_cap_gwei: Decimal = Decimal("2")
    base_currency_decimals: int = 8
    require_gas_estimate: bool = True
    use_private_transaction_method: bool = False


@dataclass(frozen=True)
class BorrowerPosition:
    user: str
    debt_asset: str
    collateral_asset: str
    debt_base_usd: Decimal
    collateral_base_usd: Decimal
    health_factor: Decimal


@dataclass(frozen=True)
class Candidate:
    position: BorrowerPosition
    estimated_profit_usd: Decimal


def env_bool(name: str, default: str = "false") -> bool:
    return getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = getenv(name)
    return default if raw is None or raw.strip() == "" else int(raw)


def env_decimal(name: str, default: str) -> Decimal:
    raw = getenv(name)
    return Decimal(default if raw is None or raw.strip() == "" else raw)


def load_settings() -> Settings:
    required = {
        "GRAPH_API_KEY": getenv("GRAPH_API_KEY", ""),
        "BASE_RPC_URL": getenv("BASE_RPC_URL", ""),
        "PRIVATE_RPC_URL": getenv("PRIVATE_RPC_URL", ""),
        "PRIVATE_KEY": getenv("PRIVATE_KEY", ""),
        "WALLET_ADDRESS": getenv("WALLET_ADDRESS", ""),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    return Settings(
        graph_api_key=required["GRAPH_API_KEY"],
        rpc_url=required["BASE_RPC_URL"],
        private_rpc_url=required["PRIVATE_RPC_URL"],
        private_key=required["PRIVATE_KEY"],
        wallet_address=required["WALLET_ADDRESS"],
        hands_contract=getenv("HANDS_CONTRACT", DEFAULT_HANDS_CONTRACT),
        subgraph_url=getenv(
            "AAVE_SUBGRAPH_URL",
            f"https://gateway.thegraph.com/api/{required['GRAPH_API_KEY']}/subgraphs/id/{DEFAULT_AAVE_SUBGRAPH_DEPLOYMENT_ID}",
        ),
        pool_addresses_provider=getenv("POOL_ADDRESSES_PROVIDER", DEFAULT_POOL_ADDRESSES_PROVIDER),
        chain_id=env_int("CHAIN_ID", 8453),
        execution_enabled=env_bool("EXECUTION_ENABLED", "true"),
        heartbeat_seconds=env_int("HEARTBEAT_SECONDS", 10),
        borrower_limit=env_int("BORROWER_LIMIT", 100),
        subgraph_page_size=env_int("SUBGRAPH_PAGE_SIZE", 1000),
        max_candidates_per_tick=env_int("MAX_CANDIDATES_PER_TICK", 3),
        min_profit_usd=env_decimal("MIN_PROFIT_USD", "1"),
        liquidation_bonus_bps=env_decimal("LIQUIDATION_BONUS_BPS", "500"),
        flashloan_fee_bps=env_decimal("FLASHLOAN_FEE_BPS", "9"),
        max_priority_fee_cap_gwei=env_decimal("MAX_PRIORITY_FEE_CAP_GWEI", "2"),
        base_currency_decimals=env_int("BASE_CURRENCY_DECIMALS", 8),
        require_gas_estimate=env_bool("REQUIRE_GAS_ESTIMATE", "true"),
        use_private_transaction_method=env_bool("USE_PRIVATE_TRANSACTION_METHOD", "false"),
    )


class BaseSearcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.public_w3 = AsyncWeb3(AsyncHTTPProvider(settings.rpc_url))
        self.private_w3 = AsyncWeb3(AsyncHTTPProvider(settings.private_rpc_url))
        self.account = Account.from_key(settings.private_key)
        self.pool = None
        self.provider = self.public_w3.eth.contract(
            address=self.public_w3.to_checksum_address(settings.pool_addresses_provider),
            abi=POOL_ADDRESSES_PROVIDER_ABI,
        )
        self.hands = self.private_w3.eth.contract(
            address=self.private_w3.to_checksum_address(settings.hands_contract),
            abi=BASE_AAVE_HANDS_ABI,
        )
        self.multicall = self.public_w3.eth.contract(
            address=self.public_w3.to_checksum_address(MULTICALL3),
            abi=MULTICALL3_ABI,
        )
        self.blocked_assets = self._address_set(getenv("BLOCKED_ASSETS", ""))
        self.opportunities: dict[str, list[dict[str, Any]]] = {
            "liquidation": [],
            "rebalance_watchlist": [],
        }

    def _address_set(self, csv_value: str) -> set[str]:
        return {
            self.public_w3.to_checksum_address(item.strip())
            for item in csv_value.split(",")
            if item.strip()
        }

    def log(self, level: str, **payload: Any) -> None:
        print(json.dumps({"level": level, **payload}, default=str), flush=True)

    def record_opportunity(self, kind: str, position: BorrowerPosition, estimated_profit_usd: Decimal, status: str, tx_hash: str | None = None) -> None:
        bucket = self.opportunities.setdefault(kind, [])
        bucket.append(
            {
                "observedAt": time.time(),
                "user": position.user,
                "debtAsset": position.debt_asset,
                "collateralAsset": position.collateral_asset,
                "healthFactor": str(position.health_factor),
                "debtBaseUsd": str(position.debt_base_usd),
                "collateralBaseUsd": str(position.collateral_base_usd),
                "estimatedProfitUsd": str(estimated_profit_usd),
                "status": status,
                "txHash": tx_hash,
            }
        )
        if len(bucket) > 10000:
            del bucket[: len(bucket) - 10000]

    def opportunity_summary(self) -> dict[str, Any]:
        cutoff = time.time() - 86400
        summary = []
        for kind, rows in self.opportunities.items():
            recent = [row for row in rows if row["observedAt"] >= cutoff]
            statuses = sorted({row["status"] for row in recent})
            for status in statuses:
                matching = [row for row in recent if row["status"] == status]
                estimated_profit = sum(Decimal(row["estimatedProfitUsd"]) for row in matching)
                summary.append(
                    {
                        "kind": kind,
                        "status": status,
                        "count": len(matching),
                        "estimatedProfitUsd": estimated_profit,
                    }
                )
        return {"last24h": summary}

    async def start(self) -> None:
        await self.validate_runtime()
        pool_address = await self.provider.functions.getPool().call()
        self.pool = self.public_w3.eth.contract(
            address=self.public_w3.to_checksum_address(pool_address),
            abi=POOL_ABI,
        )
        self.log(
            "info",
            message="bot_started",
            wallet=self.account.address,
            pool=self.pool.address,
            executionEnabled=self.settings.execution_enabled,
        )
        while True:
            try:
                await self.tick()
            except Exception as exc:
                self.log("error", message=str(exc))
                await asyncio.sleep(self.settings.heartbeat_seconds)

    async def validate_runtime(self) -> None:
        if not await self.public_w3.is_connected():
            raise RuntimeError("BASE_RPC_URL connection failed")
        if not await self.private_w3.is_connected():
            raise RuntimeError("PRIVATE_RPC_URL connection failed")
        chain_id = await self.public_w3.eth.chain_id
        private_chain_id = await self.private_w3.eth.chain_id
        if chain_id != self.settings.chain_id or private_chain_id != self.settings.chain_id:
            raise RuntimeError(
                f"Expected Base chain id {self.settings.chain_id}; got public={chain_id}, private={private_chain_id}"
            )
        configured_wallet = self.public_w3.to_checksum_address(self.settings.wallet_address)
        if configured_wallet != self.account.address:
            raise RuntimeError("WALLET_ADDRESS does not match PRIVATE_KEY")

    async def tick(self) -> None:
        positions = await self.fetch_top_borrowers()
        candidates = self.pick_candidates(positions)
        rebalance_watchlist = self.pick_rebalance_watchlist(positions)
        for candidate in candidates:
            self.record_opportunity("liquidation", candidate.position, candidate.estimated_profit_usd, "candidate")
        for position in rebalance_watchlist:
            self.record_opportunity("rebalance_watchlist", position, Decimal("0"), "watching")

        executed = 0
        if candidates and self.settings.execution_enabled:
            for candidate in candidates[: self.settings.max_candidates_per_tick]:
                tx_hash = await self.execute_candidate(candidate)
                self.record_opportunity("liquidation", candidate.position, candidate.estimated_profit_usd, "sent", tx_hash)
                executed += 1
                self.log(
                    "info",
                    message="liquidation_sent",
                    tx=tx_hash,
                    user=candidate.position.user,
                    debtAsset=candidate.position.debt_asset,
                    collateralAsset=candidate.position.collateral_asset,
                    estimatedProfitUsd=candidate.estimated_profit_usd,
                )
        elif candidates:
            self.log("info", message="candidates_found_execution_disabled", candidates=len(candidates))

        if rebalance_watchlist:
            self.log(
                "info",
                message="rebalance_watchlist",
                users=[
                    {
                        "user": position.user,
                        "healthFactor": position.health_factor,
                        "debtBaseUsd": position.debt_base_usd,
                        "collateralBaseUsd": position.collateral_base_usd,
                    }
                    for position in rebalance_watchlist[:10]
                ],
            )

        self.log(
            "info",
            message="heartbeat",
            positions=len(positions),
            candidates=len(candidates),
            rebalanceWatchlist=len(rebalance_watchlist),
            executed=executed,
            executionEnabled=self.settings.execution_enabled,
            opportunitySummary=self.opportunity_summary(),
        )
        await asyncio.sleep(self.settings.heartbeat_seconds)

    async def fetch_top_borrowers(self) -> list[BorrowerPosition]:
        if self.pool is None:
            raise RuntimeError("Pool is not initialized")

        query = """
        query TopBorrowers($first: Int!) {
          userReserves(
            first: $first
            orderBy: currentTotalDebt
            orderDirection: desc
            where: { currentTotalDebt_gt: "0" }
          ) {
            user { id }
            reserve { underlyingAsset symbol }
            currentTotalDebt
            currentATokenBalance
            usageAsCollateralEnabledOnUser
          }
        }
        """
        headers = {"Authorization": f"Bearer {self.settings.graph_api_key}"}
        variables = {"first": min(self.settings.subgraph_page_size, self.settings.borrower_limit * 10)}
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.settings.subgraph_url,
                json={"query": query, "variables": variables},
                headers=headers,
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"Subgraph HTTP {response.status}: {payload}")

        if payload.get("errors"):
            raise RuntimeError(f"Subgraph errors: {payload['errors']}")

        grouped = self._group_user_reserves(payload.get("data", {}).get("userReserves", []))
        positions = await self._hydrate_positions(grouped)
        return positions[: self.settings.borrower_limit]

    def _group_user_reserves(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            user = self.public_w3.to_checksum_address(row["user"]["id"])
            asset = self.public_w3.to_checksum_address(row["reserve"]["underlyingAsset"])
            if asset in self.blocked_assets:
                continue

            debt = Decimal(str(row.get("currentTotalDebt") or "0"))
            collateral = Decimal(str(row.get("currentATokenBalance") or "0"))
            entry = grouped.setdefault(
                user,
                {
                    "debt_asset": asset,
                    "collateral_asset": asset,
                    "max_debt": Decimal("0"),
                    "max_collateral": Decimal("0"),
                },
            )
            if debt > entry["max_debt"]:
                entry["max_debt"] = debt
                entry["debt_asset"] = asset
            if row.get("usageAsCollateralEnabledOnUser", True) and collateral > entry["max_collateral"]:
                entry["max_collateral"] = collateral
                entry["collateral_asset"] = asset
        return grouped

    async def _hydrate_positions(self, grouped: dict[str, dict[str, Any]]) -> list[BorrowerPosition]:
        account_data = await self.fetch_account_data(list(grouped.keys()))
        base_unit = Decimal(10) ** self.settings.base_currency_decimals
        positions: list[BorrowerPosition] = []
        for user, entry in grouped.items():
            data = account_data.get(user)
            if not data:
                continue
            total_collateral_base, total_debt_base, health_factor = data
            if total_debt_base <= 0 or total_collateral_base <= 0:
                continue
            if entry["debt_asset"] == entry["collateral_asset"]:
                continue
            positions.append(
                BorrowerPosition(
                    user=user,
                    debt_asset=entry["debt_asset"],
                    collateral_asset=entry["collateral_asset"],
                    debt_base_usd=Decimal(total_debt_base) / base_unit,
                    collateral_base_usd=Decimal(total_collateral_base) / base_unit,
                    health_factor=Decimal(health_factor) / WAD,
                )
            )
        positions.sort(key=lambda item: item.debt_base_usd, reverse=True)
        return positions

    async def fetch_account_data(self, users: list[str]) -> dict[str, tuple[int, int, int]]:
        if not users or self.pool is None:
            return {}
        calls = []
        for user in users:
            fn = self.pool.functions.getUserAccountData(user)
            call_data = fn._encode_transaction_data()
            calls.append((self.pool.address, True, bytes.fromhex(call_data[2:])))
        results = await self.multicall.functions.aggregate3(calls).call()
        data: dict[str, tuple[int, int, int]] = {}
        for user, result in zip(users, results):
            success, raw = result
            if not success or not raw:
                continue
            decoded = self.public_w3.codec.decode(
                ["uint256", "uint256", "uint256", "uint256", "uint256", "uint256"],
                raw,
            )
            data[user] = (int(decoded[0]), int(decoded[1]), int(decoded[5]))
        return data

    def pick_candidates(self, positions: list[BorrowerPosition]) -> list[Candidate]:
        picked = []
        for position in positions:
            if position.health_factor >= Decimal("1"):
                continue
            profit = self.estimate_liquidation_profit(position)
            if profit >= self.settings.min_profit_usd:
                picked.append(Candidate(position=position, estimated_profit_usd=profit))
        picked.sort(key=lambda item: item.estimated_profit_usd, reverse=True)
        return picked

    def pick_rebalance_watchlist(self, positions: list[BorrowerPosition]) -> list[BorrowerPosition]:
        watchlist = [
            position
            for position in positions
            if Decimal("1") <= position.health_factor < Decimal(getenv("REBALANCE_HEALTH_FACTOR_CEILING", "1.05"))
        ]
        watchlist.sort(key=lambda item: item.health_factor)
        return watchlist

    def estimate_liquidation_profit(self, position: BorrowerPosition) -> Decimal:
        close_factor_debt = position.debt_base_usd / Decimal("2")
        bonus = close_factor_debt * self.settings.liquidation_bonus_bps / BPS
        flash_fee = close_factor_debt * self.settings.flashloan_fee_bps / BPS
        gas_fee = self.estimate_gas_fee_usd(650000)
        return bonus - flash_fee - gas_fee

    def estimate_gas_fee_usd(self, gas_units: int) -> Decimal:
        base_fee_gwei = Decimal(getenv("ASSUMED_BASE_FEE_GWEI", "0.02"))
        eth_price = Decimal(getenv("ETH_PRICE_USD", "3000"))
        priority_gwei = min(self.settings.max_priority_fee_cap_gwei, Decimal(getenv("ASSUMED_PRIORITY_FEE_GWEI", "0.04")))
        return (base_fee_gwei + priority_gwei) * Decimal(gas_units) * eth_price / Decimal("1000000000")

    async def execute_candidate(self, candidate: Candidate) -> str:
        tx = await self.build_liquidation_tx(candidate)
        signed = self.account.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        return await self.send_private_transaction(HexBytes(raw))

    async def build_liquidation_tx(self, candidate: Candidate) -> dict[str, Any]:
        position = candidate.position
        function = self.hands.functions.executeLiquidation(
            position.user,
            position.debt_asset,
            position.collateral_asset,
        )
        nonce = await self.private_w3.eth.get_transaction_count(self.account.address, "pending")
        fees = await self.dynamic_fees(candidate.estimated_profit_usd)
        tx_base = {
            "from": self.account.address,
            "chainId": self.settings.chain_id,
            "nonce": nonce,
            "type": 2,
            **fees,
        }
        gas = await self.estimate_execution_gas(function, tx_base)
        return await function.build_transaction({**tx_base, "gas": gas})

    async def estimate_execution_gas(self, function: Any, tx_base: dict[str, Any]) -> int:
        try:
            estimated = await function.estimate_gas({"from": tx_base["from"]})
            return int(Decimal(estimated) * Decimal("1.25"))
        except Exception as exc:
            if self.settings.require_gas_estimate:
                raise RuntimeError(f"Gas estimate failed; refusing to send likely reverting tx: {exc}") from exc
            return 650000

    async def dynamic_fees(self, profit_usd: Decimal) -> dict[str, int]:
        block = await self.private_w3.eth.get_block("latest")
        base_fee = int(block.get("baseFeePerGas", self.private_w3.to_wei(Decimal("0.02"), "gwei")))
        eth_price = Decimal(getenv("ETH_PRICE_USD", "3000"))
        max_tip_usd = min(Decimal("2"), profit_usd * Decimal("0.04"))
        priority_wei = int(max_tip_usd / eth_price * Decimal("1000000000000000000") / Decimal("650000"))
        priority_wei = max(priority_wei, int(self.private_w3.to_wei(Decimal("0.001"), "gwei")))
        priority_wei = min(priority_wei, int(self.private_w3.to_wei(self.settings.max_priority_fee_cap_gwei, "gwei")))
        return {
            "maxFeePerGas": base_fee * 2 + priority_wei,
            "maxPriorityFeePerGas": priority_wei,
        }

    async def rpc_request(self, method: str, params: list[Any]) -> Any:
        response = await self.private_w3.provider.make_request(RPCEndpoint(method), params)
        if response.get("error"):
            raise RuntimeError(response["error"])
        return response.get("result")

    async def send_private_transaction(self, raw_tx: HexBytes) -> str:
        raw_hex = raw_tx.hex()
        if self.settings.use_private_transaction_method:
            try:
                result = await self.rpc_request("eth_sendPrivateTransaction", [{"tx": raw_hex}])
                if result:
                    return str(result)
            except Exception as exc:
                self.log("warning", message="private_transaction_method_failed_falling_back", error=str(exc))
        tx_hash = await self.private_w3.eth.send_raw_transaction(HexBytes(raw_tx))
        return tx_hash.hex()


async def main() -> None:
    load_dotenv(override=True)
    settings = load_settings()
    searcher = BaseSearcher(settings)
    await searcher.start()


if __name__ == "__main__":
    asyncio.run(main())
