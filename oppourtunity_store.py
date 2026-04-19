import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


class OpportunityStore:
    def __init__(self, database_path: str):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    user TEXT NOT NULL,
                    debt_asset TEXT NOT NULL,
                    collateral_asset TEXT NOT NULL,
                    health_factor TEXT NOT NULL,
                    debt_base_usd TEXT NOT NULL,
                    collateral_base_usd TEXT NOT NULL,
                    estimated_profit_usd TEXT NOT NULL,
                    execution_enabled INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    tx_hash TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_user_kind_observed
                ON opportunities(user, kind, observed_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_status_observed
                ON opportunities(status, observed_at)
                """
            )

    def record(self, kind: str, position: Any, estimated_profit_usd: Decimal, execution_enabled: bool, status: str, tx_hash: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO opportunities (
                    observed_at,
                    kind,
                    user,
                    debt_asset,
                    collateral_asset,
                    health_factor,
                    debt_base_usd,
                    collateral_base_usd,
                    estimated_profit_usd,
                    execution_enabled,
                    status,
                    tx_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    kind,
                    position.user,
                    position.debt_asset,
                    position.collateral_asset,
                    str(position.health_factor),
                    str(position.debt_base_usd),
                    str(position.collateral_base_usd),
                    str(estimated_profit_usd),
                    1 if execution_enabled else 0,
                    status,
                    tx_hash,
                ),
            )

    def recent_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT kind, status, COUNT(*), COALESCE(SUM(CAST(estimated_profit_usd AS REAL)), 0)
                FROM opportunities
                WHERE observed_at >= datetime('now', '-24 hours')
                GROUP BY kind, status
                ORDER BY kind, status
                """
            ).fetchall()
        return {
            "last24h": [
                {
                    "kind": kind,
                    "status": status,
                    "count": count,
                    "estimatedProfitUsd": estimated_profit,
                }
                for kind, status, count, estimated_profit in rows
            ]
        }
