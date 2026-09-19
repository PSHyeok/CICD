from __future__ import annotations

import httpx
from fastapi import HTTPException, Request

from ..github import GitHubApiClient
from ..models import GitHubPushHook, NormalizedEvent
from .base import SourceAdapter, json_body, validate, verify_hmac


class GitHubSourceAdapter(SourceAdapter):
    name = "github"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.api = GitHubApiClient(client)

    async def normalize(self, request: Request) -> NormalizedEvent | None:
        body, payload = await json_body(request)
        verify_hmac(
            body,
            request.headers.get("X-Hub-Signature-256"),
            "GITHUB_WEBHOOK_SECRET",
        )
        event_name = request.headers.get("X-GitHub-Event")
        if event_name != "push":
            return None
        delivery_id = request.headers.get("X-GitHub-Delivery")
        if not delivery_id:
            raise HTTPException(status_code=400, detail="missing X-GitHub-Delivery")
        hook = validate(GitHubPushHook, payload)
        if hook.deleted:
            return None
        return await self.api.normalize(hook, delivery_id)
