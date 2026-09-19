import hashlib
import hmac

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from cicd_router.sources import GitHubSourceAdapter, SourceAdapterRegistry


def request(body: bytes, headers: dict[str, str]) -> Request:
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/hooks/github",
            "headers": [
                (name.lower().encode(), value.encode())
                for name, value in headers.items()
            ],
        },
        receive,
    )


async def test_github_ping_validates_signature_and_is_ignored(monkeypatch) -> None:
    secret = "webhook-secret"
    body = b'{"zen":"Keep it logically awesome."}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)

    async with httpx.AsyncClient() as client:
        adapter = GitHubSourceAdapter(client)
        result = await adapter.normalize(
            request(
                body,
                {
                    "X-GitHub-Event": "ping",
                    "X-Hub-Signature-256": f"sha256={signature}",
                },
            )
        )
    assert result is None


async def test_github_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    async with httpx.AsyncClient() as client:
        adapter = GitHubSourceAdapter(client)
        with pytest.raises(HTTPException) as error:
            await adapter.normalize(
                request(
                    b"{}",
                    {
                        "X-GitHub-Event": "ping",
                        "X-Hub-Signature-256": "sha256=wrong",
                    },
                )
            )
    assert error.value.status_code == 401


def test_registry_lists_sources_and_rejects_unknown() -> None:
    registry = SourceAdapterRegistry([])
    assert registry.names == []
    with pytest.raises(HTTPException) as error:
        registry.get("bitbucket")
    assert error.value.status_code == 404
