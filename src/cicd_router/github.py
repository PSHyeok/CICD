from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from .models import GitHubPushHook, NormalizedEvent, Source

ZERO_SHA = "0" * 40


def _branch(ref: str) -> str:
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def _payload_files(hook: GitHubPushHook) -> list[str]:
    return sorted(
        {
            path
            for commit in hook.commits
            for path in (commit.added + commit.removed + commit.modified)
        }
    )


class GitHubApiClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def normalize(
        self, hook: GitHubPushHook, delivery_id: str
    ) -> NormalizedEvent:
        files, paths_complete = await self._changed_files(hook)
        repository = hook.repository.full_name
        return NormalizedEvent(
            source=Source.GITHUB,
            event_id=delivery_id,
            event_name="push",
            repositories=[repository],
            branch=_branch(hook.ref),
            revision=hook.after,
            changed_files=files,
            repository_files={repository: files},
            paths_complete=paths_complete,
            actor=hook.sender.login,
            metadata={"before": hook.before, "created": hook.created},
        )

    async def _changed_files(self, hook: GitHubPushHook) -> tuple[list[str], bool]:
        # A newly created ref has an all-zero base SHA, which cannot be sent to
        # the compare endpoint. GitHub includes up to 2,048 commits in payload.
        if hook.created or hook.before == ZERO_SHA:
            complete = hook.size <= len(hook.commits) and len(hook.commits) < 2048
            return _payload_files(hook), complete

        owner, repository = hook.repository.full_name.split("/", 1)
        api_url = os.getenv("GITHUB_API_URL", "https://api.github.com")
        basehead = quote(f"{hook.before}...{hook.after}", safe=".")
        url = (
            f"{api_url.rstrip('/')}/repos/{quote(owner, safe='')}/"
            f"{quote(repository, safe='')}/compare/{basehead}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": os.getenv(
                "GITHUB_API_VERSION", "2026-03-10"
            ),
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        changed = response.json().get("files", [])
        files = {
            name
            for item in changed
            for name in (item.get("filename"), item.get("previous_filename"))
            if name
        }
        return sorted(files), len(changed) < 300
