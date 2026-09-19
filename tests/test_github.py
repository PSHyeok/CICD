import httpx

from cicd_router.github import GitHubApiClient, ZERO_SHA
from cicd_router.models import GitHubPullRequestHook, GitHubPushHook


def push_hook(**overrides) -> GitHubPushHook:
    payload = {
        "ref": "refs/heads/main",
        "before": "a" * 40,
        "after": "b" * 40,
        "repository": {"full_name": "acme/api"},
        "sender": {"login": "alice"},
        "commits": [],
        "size": 1,
    }
    payload.update(overrides)
    return GitHubPushHook.model_validate(payload)


async def test_compare_api_normalizes_native_github_push(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/acme/api/compare/{'a' * 40}...{'b' * 40}"
        assert request.headers["Authorization"] == "Bearer github-secret"
        assert request.headers["X-GitHub-Api-Version"] == "2026-03-10"
        return httpx.Response(
            200,
            json={
                "files": [
                    {"filename": "src/new.py", "previous_filename": "src/old.py"}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        event = await GitHubApiClient(http).normalize(push_hook(), "delivery-1")

    assert event.event_id == "delivery-1"
    assert event.repositories == ["acme/api"]
    assert event.changed_files == ["src/new.py", "src/old.py"]
    assert event.paths_complete is True


async def test_new_branch_uses_webhook_commits_without_compare_api() -> None:
    async def unexpected(_: httpx.Request) -> httpx.Response:
        raise AssertionError("compare API must not be called for an all-zero base")

    hook = push_hook(
        before=ZERO_SHA,
        created=True,
        commits=[{"added": ["src/new.py"], "removed": [], "modified": []}],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
        event = await GitHubApiClient(http).normalize(hook, "delivery-2")

    assert event.changed_files == ["src/new.py"]
    assert event.paths_complete is True


async def test_300_compare_files_are_marked_incomplete() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"files": [{"filename": f"generated/{i}"} for i in range(300)]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        event = await GitHubApiClient(http).normalize(push_hook(), "delivery-3")

    assert event.paths_complete is False


async def test_pull_request_uses_files_api_and_branch_roles() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/acme/api/pulls/17/files"
        assert request.url.params["per_page"] == "100"
        return httpx.Response(
            200,
            json=[{"filename": "backend/api.py"}, {"filename": "docs/readme.md"}],
        )

    hook = GitHubPullRequestHook.model_validate(
        {
            "action": "opened",
            "number": 17,
            "repository": {"full_name": "acme/api"},
            "sender": {"login": "alice"},
            "pull_request": {
                "head": {"ref": "feature/login", "sha": "head-sha"},
                "base": {"ref": "main", "sha": "base-sha"},
            },
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        event = await GitHubApiClient(http).normalize_pull_request(hook, "delivery-pr")

    assert event.event_name == "pull_request"
    assert event.source_branch == "feature/login"
    assert event.target_branch == "main"
    assert event.branch == "main"
    assert event.pull_request_number == 17
    assert event.changed_files == ["backend/api.py", "docs/readme.md"]
