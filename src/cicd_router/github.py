from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from .models import GitHubPullRequestHook, GitHubPushHook, NormalizedEvent, Source

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

    async def normalize_pull_request(
        self, hook: GitHubPullRequestHook, delivery_id: str
    ) -> NormalizedEvent:
        files, paths_complete = await self._pull_request_files(
            hook.repository.full_name, hook.number
        )
        repository = hook.repository.full_name
        return NormalizedEvent(
            source=Source.GITHUB,
            event_id=delivery_id,
            event_name="pull_request",
            repositories=[repository],
            # Legacy branch policies apply to the PR target branch.
            branch=hook.pull_request.base.ref,
            revision=hook.pull_request.head.sha,
            changed_files=files,
            repository_files={repository: files},
            paths_complete=paths_complete,
            source_branch=hook.pull_request.head.ref,
            target_branch=hook.pull_request.base.ref,
            pull_request_number=hook.number,
            actor=hook.sender.login,
            metadata={"action": hook.action},
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": os.getenv(
                "GITHUB_API_VERSION", "2026-03-10"
            ),
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _pull_request_files(
        self, full_name: str, pull_number: int
    ) -> tuple[list[str], bool]:
        owner, repository = full_name.split("/", 1)
        api_url = os.getenv("GITHUB_API_URL", "https://api.github.com")
        url = (
            f"{api_url.rstrip('/')}/repos/{quote(owner, safe='')}/"
            f"{quote(repository, safe='')}/pulls/{pull_number}/files"
        )
        files: set[str] = set()
        try:
            for page in range(1, 31):
                response = await self.client.get(
                    url,
                    headers=self._headers(),
                    params={"per_page": 100, "page": page},
                )
                response.raise_for_status()
                items = response.json()
                files.update(
                    name
                    for item in items
                    for name in (item.get("filename"), item.get("previous_filename"))
                    if name
                )
                if len(items) < 100:
                    return sorted(files), True
            return sorted(files), False
        except httpx.HTTPError:
            # Path availability is a routing policy decision. Preserve the event
            # so each route can choose trigger, skip, or error.
            return [], False

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
        response = await self.client.get(url, headers=self._headers())
        response.raise_for_status()
        changed = response.json().get("files", [])
        files = {
            name
            for item in changed
            for name in (item.get("filename"), item.get("previous_filename"))
            if name
        }
        return sorted(files), len(changed) < 300
