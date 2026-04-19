from dataclasses import dataclass
from decimal import Decimal
from os import getenv


DEFAULT_AAVE_SUBGRAPH_URL = "https://gateway.thegraph.com/api/subgraphs/id/GQFbb95cE6d8mV989mL5figjaGaKCQB3xqYrr1bRyXqF"
DEFAULT_POOL_ADDRESSES_PROVIDER = "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
DEFAULT_PROTOCOL_DATA_PROVIDER = "0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A"
DEFAULT_HANDS_CONTRACT = "0x5573d354c9a991c3d09c34eee775c499e629275e"


@dataclass(frozen=True)
class Settings:
    graph_api_key: str
    rpc_url: str
    private_rpc_url: str
    private_key: str
    wallet_address: str
    hands_contract: str
    subgraph_url: str = DEFAULT_AAVE_SUBGRAPH_URL
    pool_addresses_provider: str = DEFAULT_POOL_ADDRESSES_PROVIDER
    protocol_data_provider: str = DEFAULT_PROTOCOL_DATA_PROVIDER
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
    opportunities_db_path: str = "data/opportunities.db"


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
        subgraph_url=getenv("AAVE_SUBGRAPH_URL", DEFAULT_AAVE_SUBGRAPH_URL),
        pool_addresses_provider=getenv("POOL_ADDRESSES_PROVIDER", DEFAULT_POOL_ADDRESSES_PROVIDER),
        protocol_data_provider=getenv("PROTOCOL_DATA_PROVIDER", DEFAULT_PROTOCOL_DATA_PROVIDER),
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
        opportunities_db_path=getenv("OPPORTUNITIES_DB_PATH", "data/opportunities.db"),
    )
