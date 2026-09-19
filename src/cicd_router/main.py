from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request

from .config import load_config
from .models import HookResponse, IgnoredHookResponse
from .service import RouterService
from .sources import (
    GitHubSourceAdapter,
    PerforceSourceAdapter,
    RepoManifestSourceAdapter,
    SourceAdapterRegistry,
)
from .store import EventStore
from .triggers import HttpTriggerClient


def _build_runtime() -> tuple[RouterService, SourceAdapterRegistry, httpx.AsyncClient]:
    config_path = os.getenv("CICD_ROUTER_CONFIG", "config/policies.yaml")
    database_path = os.getenv("CICD_ROUTER_DB", "cicd-router.db")
    client = httpx.AsyncClient(timeout=20)
    service = RouterService(
        config=load_config(config_path),
        store=EventStore(database_path),
        trigger_client=HttpTriggerClient(client),
    )
    adapters = SourceAdapterRegistry(
        [
            GitHubSourceAdapter(client),
            PerforceSourceAdapter(),
            RepoManifestSourceAdapter(),
        ]
    )
    return service, adapters, client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    service, adapters, client = _build_runtime()
    app.state.router_service = service
    app.state.source_adapters = adapters
    yield
    await client.aclose()


app = FastAPI(title="CI/CD Hook Router", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str | list[str]]:
    return {
        "status": "ok",
        "sources": request.app.state.source_adapters.names,
    }


@app.post("/v1/hooks/{source}", response_model=HookResponse | IgnoredHookResponse)
async def receive_hook(
    source: str, request: Request
) -> HookResponse | IgnoredHookResponse:
    adapters: SourceAdapterRegistry = request.app.state.source_adapters
    service: RouterService = request.app.state.router_service
    event = await adapters.get(source).normalize(request)
    if event is None:
        return IgnoredHookResponse()
    return await service.route(event)
