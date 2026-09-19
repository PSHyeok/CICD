from pathlib import Path

import httpx

from cicd_router.manifests import (
    FileManifestProvider,
    HttpManifestProvider,
    SqliteManifestProvider,
)
from cicd_router.manifest_admin import import_manifest
from cicd_router.models import HttpManifestSource, RoutingManifest


def manifest_document(version: str = "v1") -> dict:
    return {
        "version": 1,
        "manifest_version": version,
        "routes": [
            {
                "id": "backend-pr",
                "match": {
                    "sources": ["github"],
                    "events": ["pull_request"],
                    "repositories": ["acme/platform"],
                    "target_branches": ["main"],
                },
                "trigger": {
                    "provider": "jenkins",
                    "base_url": "https://jenkins",
                    "job": "backend/pr",
                },
            }
        ],
    }


async def test_file_manifest_provider_loads_example() -> None:
    root = Path(__file__).parents[1]
    snapshot = await FileManifestProvider(
        root / "config" / "routing-manifest.example.yaml"
    ).load()
    assert snapshot.version == "2026-09-19.1"
    assert len(snapshot.routes) == 4


async def test_sqlite_manifest_provider_replaces_active_version(tmp_path: Path) -> None:
    provider = SqliteManifestProvider(tmp_path / "manifest.db")
    provider.replace(RoutingManifest.model_validate(manifest_document("v1")))
    provider.replace(RoutingManifest.model_validate(manifest_document("v2")))

    snapshot = await provider.load()
    assert snapshot.version == "v2"


async def test_import_manifest_activates_yaml_in_sqlite(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "routes.db"
    version = import_manifest(
        database, root / "config" / "routing-manifest.example.yaml"
    )

    snapshot = await SqliteManifestProvider(database).load()
    assert version == "2026-09-19.1"
    assert snapshot.version == version
    assert snapshot.routes[0].id == "platform-backend-pr"


async def test_http_manifest_provider_uses_etag_cache() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=manifest_document(), headers={"ETag": "v1"})
        assert request.headers["If-None-Match"] == "v1"
        return httpx.Response(304)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = HttpManifestProvider(
            HttpManifestSource(url="https://manifest.example/routes.yaml"), client
        )
        first = await provider.load()
        second = await provider.load()

    assert first == second
    assert calls == 2
