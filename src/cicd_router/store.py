from __future__ import annotations

import sqlite3
from pathlib import Path


class EventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trigger_claims (
                    source TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_id TEXT,
                    external_url TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source, event_id, policy_id)
                )
                """
            )

    def claim(self, source: str, event_id: str, policy_id: str) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO trigger_claims (source, event_id, policy_id, status)
                    VALUES (?, ?, ?, 'triggering')
                    """,
                    (source, event_id, policy_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def finish(
        self,
        source: str,
        event_id: str,
        policy_id: str,
        status: str,
        external_id: str | None = None,
        external_url: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE trigger_claims
                SET status = ?, external_id = ?, external_url = ?, detail = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE source = ? AND event_id = ? AND policy_id = ?
                """,
                (
                    status,
                    external_id,
                    external_url,
                    detail,
                    source,
                    event_id,
                    policy_id,
                ),
            )

