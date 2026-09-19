from cicd_router.models import (
    JenkinsTrigger,
    MatchConfig,
    NormalizedEvent,
    PipelinePolicy,
    Source,
)
from cicd_router.policy import matches


def policy(repository: str, include: str = "*") -> PipelinePolicy:
    return PipelinePolicy(
        id="test",
        match=MatchConfig(
            sources=[Source.REPO_MANIFEST],
            repositories=[repository],
            branches=["main"],
            include_paths=[include],
        ),
        trigger=JenkinsTrigger(
            base_url="https://jenkins", job="build", token_env="TEST_TOKEN"
        ),
    )


def manifest_event() -> NormalizedEvent:
    return NormalizedEvent(
        source=Source.REPO_MANIFEST,
        event_id="evt-1",
        event_name="sync",
        repositories=["services/api", "docs/site"],
        branch="main",
        revision="manifest-sha",
        changed_files=["src/app.py", "guide.md"],
        repository_files={
            "services/api": ["src/app.py"],
            "docs/site": ["guide.md"],
        },
    )


def test_manifest_paths_are_scoped_to_matching_repository() -> None:
    event = manifest_event()
    assert matches(policy("services/api", "src/*"), event)
    assert not matches(policy("docs/site", "src/*"), event)


def test_excluded_path_does_not_trigger() -> None:
    item = policy("services/api", "src/*")
    item.match.exclude_paths = ["src/*"]
    assert not matches(item, manifest_event())


def test_incomplete_github_paths_fail_open() -> None:
    event = manifest_event().model_copy(
        update={
            "source": Source.GITHUB,
            "event_name": "push",
            "paths_complete": False,
        }
    )
    item = policy("services/api", "a-path-that-was-not-returned/*")
    item.match.sources = [Source.GITHUB]
    assert matches(item, event)
