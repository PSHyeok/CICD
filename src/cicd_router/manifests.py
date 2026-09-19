from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from .models import (
    FileManifestSource,
    HttpManifestSource,
    ManifestSourceConfig,
    PipelinePolicy,
    RoutingManifest,
    RouterConfig,
    SqliteManifestSource,
)


@dataclass(frozen=True)
class ManifestSnapshot:
    version: str
    routes: list[PipelinePolicy]


class ManifestProvider(ABC):
    @abstractmethod
    async def load(self) -> ManifestSnapshot: ...


class StaticManifestProvider(ManifestProvider):
    def __init__(self, routes: list[PipelinePolicy]) -> None:
        self.routes = routes

    async def load(self) -> ManifestSnapshot:
        return ManifestSnapshot(version="static", routes=self.routes)


class FileManifestProvider(ManifestProvider):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def load(self) -> ManifestSnapshot:
        with self.path.open(encoding="utf-8") as handle:
            manifest = RoutingManifest.model_validate(yaml.safe_load(handle))
        return ManifestSnapshot(manifest.manifest_version, manifest.routes)


class SqliteManifestProvider(ManifestProvider):
    """Store versioned manifest documents behind a replaceable DB boundary."""

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
                CREATE TABLE IF NOT EXISTS routing_manifests (
                    manifest_version TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_routing_manifest
                ON routing_manifests(active) WHERE active = 1
                """
            )

    def replace(self, manifest: RoutingManifest) -> None:
        document = manifest.model_dump_json()
        with self._connect() as connection:
            connection.execute("UPDATE routing_manifests SET active = 0 WHERE active = 1")
            connection.execute(
                """
                INSERT INTO routing_manifests (manifest_version, document, active)
                VALUES (?, ?, 1)
                ON CONFLICT(manifest_version) DO UPDATE SET
                    document = excluded.document,
                    active = 1
                """,
                (manifest.manifest_version, document),
            )

    async def load(self) -> ManifestSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT document FROM routing_manifests
                WHERE active = 1 ORDER BY created_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("no active routing manifest exists in the database")
        manifest = RoutingManifest.model_validate_json(row["document"])
        return ManifestSnapshot(manifest.manifest_version, manifest.routes)


class HttpManifestProvider(ManifestProvider):
    def __init__(self, config: HttpManifestSource, client: httpx.AsyncClient) -> None:
        self.config = config
        self.client = client
        self._etag: str | None = None
        self._cached: ManifestSnapshot | None = None

    async def load(self) -> ManifestSnapshot:
        headers = {
            "Accept": "application/vnd.github.raw+json, application/yaml, application/json"
        }
        if self._etag:
            headers["If-None-Match"] = self._etag
        if self.config.token_env:
            token = os.getenv(self.config.token_env)
            if not token:
                raise RuntimeError(
                    f"required environment variable is not set: {self.config.token_env}"
                )
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = await self.client.get(self.config.url, headers=headers)
            if response.status_code == 304 and self._cached:
                return self._cached
            response.raise_for_status()
            manifest = RoutingManifest.model_validate(yaml.safe_load(response.text))
            snapshot = ManifestSnapshot(manifest.manifest_version, manifest.routes)
            self._etag = response.headers.get("ETag")
            self._cached = snapshot
            return snapshot
        except Exception:
            if self.config.use_cached_on_error and self._cached:
                return self._cached
            raise


def build_manifest_provider(
    config: RouterConfig, client: httpx.AsyncClient
) -> ManifestProvider:
    source: ManifestSourceConfig | None = config.manifest_source
    if source is None:
        return StaticManifestProvider(config.pipelines)
    if isinstance(source, FileManifestSource):
        return FileManifestProvider(source.path)
    if isinstance(source, SqliteManifestSource):
        return SqliteManifestProvider(source.path)
    if isinstance(source, HttpManifestSource):
        return HttpManifestProvider(source, client)
    raise TypeError(f"unsupported manifest source: {type(source).__name__}")
