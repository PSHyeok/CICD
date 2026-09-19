from cicd_router.models import (
    JenkinsTrigger,
    MatchConfig,
    NormalizedEvent,
    PipelinePolicy,
    Source,
)
import pytest

from cicd_router.policy import PathsUnavailableError, matches


def policy(repository: str, include: str = "*") -> PipelinePolicy:
    return PipelinePolicy(
        id="test",
        match=MatchConfig(
            sources=[Source.GITHUB],
            repositories=[repository],
            branches=["main"],
            include_paths=[include],
        ),
        trigger=JenkinsTrigger(
            base_url="https://jenkins", job="build", token_env="TEST_TOKEN"
        ),
    )


def github_event() -> NormalizedEvent:
    return NormalizedEvent(
        source=Source.GITHUB,
        event_id="evt-1",
        event_name="pull_request",
        repositories=["services/api", "docs/site"],
        branch="main",
        revision="commit-sha",
        changed_files=["src/app.py", "guide.md"],
        repository_files={
            "services/api": ["src/app.py"],
            "docs/site": ["guide.md"],
        },
    )


def test_paths_are_scoped_to_matching_repository() -> None:
    event = github_event()
    assert matches(policy("services/api", "src/*"), event)
    assert not matches(policy("docs/site", "src/*"), event)


def test_excluded_path_does_not_trigger() -> None:
    item = policy("services/api", "src/*")
    item.match.exclude_paths = ["src/*"]
    assert not matches(item, github_event())


def test_incomplete_github_paths_fail_open() -> None:
    event = github_event().model_copy(
        update={
            "source": Source.GITHUB,
            "event_name": "push",
            "paths_complete": False,
        }
    )
    item = policy("services/api", "a-path-that-was-not-returned/*")
    item.match.sources = [Source.GITHUB]
    assert matches(item, event)


def test_omitted_include_paths_matches_without_changed_files() -> None:
    item = policy("services/api")
    item.match.include_paths = None
    event = github_event().model_copy(
        update={
            "changed_files": [],
            "repository_files": {"services/api": [], "docs/site": []},
        }
    )
    assert matches(item, event)


def test_pr_source_and_target_branches_are_distinct() -> None:
    item = policy("services/api", "src/*")
    item.match.sources = [Source.GITHUB]
    item.match.events = ["pull_request"]
    item.match.source_branches = ["feature/*"]
    item.match.target_branches = ["main"]
    event = github_event().model_copy(
        update={
            "source": Source.GITHUB,
            "event_name": "pull_request",
            "branch": "main",
            "source_branch": "feature/login",
            "target_branch": "main",
        }
    )
    assert matches(item, event)


def test_paths_unavailable_can_skip_or_error() -> None:
    event = github_event().model_copy(update={"paths_complete": False})
    item = policy("services/api", "src/*")
    item.match.on_paths_unavailable = "skip"
    assert not matches(item, event)

    item.match.on_paths_unavailable = "error"
    with pytest.raises(PathsUnavailableError):
        matches(item, event)
