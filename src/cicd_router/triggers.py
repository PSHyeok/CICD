from __future__ import annotations

import os
from abc import ABC, abstractmethod
from urllib.parse import quote

import httpx

from .models import (
    JenkinsTrigger,
    NormalizedEvent,
    TriggerConfig,
    TriggerResult,
)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable is not set: {name}")
    return value


class TriggerClient(ABC):
    @abstractmethod
    async def trigger(
        self, policy_id: str, config: TriggerConfig, event: NormalizedEvent
    ) -> TriggerResult: ...


class HttpTriggerClient(TriggerClient):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def trigger(
        self, policy_id: str, config: TriggerConfig, event: NormalizedEvent
    ) -> TriggerResult:
        return await self._jenkins(policy_id, config, event)

    async def _jenkins(
        self, policy_id: str, config: JenkinsTrigger, event: NormalizedEvent
    ) -> TriggerResult:
        job_path = "/job/".join(quote(part, safe="") for part in config.job.split("/"))
        url = f"{config.base_url.rstrip('/')}/job/{job_path}/buildWithParameters"
        parameters = {
            **config.parameters,
            "HOOK_EVENT_ID": event.event_id,
            "HOOK_SOURCE": event.source.value,
            "HOOK_BRANCH": event.branch,
            "HOOK_SOURCE_BRANCH": event.source_branch or "",
            "HOOK_TARGET_BRANCH": event.target_branch or "",
            "HOOK_REVISION": event.revision,
            "HOOK_REPOSITORIES": ",".join(event.repositories),
            "HOOK_PULL_REQUEST": str(event.pull_request_number or ""),
            "ROUTING_MANIFEST_VERSION": str(
                event.metadata.get("manifest_version", "")
            ),
        }
        response = await self.client.post(
            url,
            params=parameters,
            auth=(
                _required_env(config.username_env),
                _required_env(config.token_env),
            ),
        )
        response.raise_for_status()
        queue_url = response.headers.get("Location")
        return TriggerResult(
            policy_id=policy_id,
            provider="jenkins",
            status="triggered",
            external_url=queue_url,
        )
