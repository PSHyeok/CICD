from pathlib import Path

from cicd_router.models import (
    JenkinsTrigger,
    MatchConfig,
    NormalizedEvent,
    PipelinePolicy,
    RouterConfig,
    Source,
    TriggerConfig,
    TriggerResult,
)
from cicd_router.service import RouterService
from cicd_router.store import EventStore
from cicd_router.triggers import TriggerClient


class FakeTriggerClient(TriggerClient):
    def __init__(self) -> None:
        self.calls = 0

    async def trigger(
        self, policy_id: str, config: TriggerConfig, event: NormalizedEvent
    ) -> TriggerResult:
        self.calls += 1
        return TriggerResult(
            policy_id=policy_id,
            provider=config.provider,
            status="triggered",
            external_id="build-1",
        )


class FirstFailureTriggerClient(FakeTriggerClient):
    async def trigger(
        self, policy_id: str, config: TriggerConfig, event: NormalizedEvent
    ) -> TriggerResult:
        self.calls += 1
        if policy_id == "api-build":
            raise RuntimeError("provider unavailable")
        return TriggerResult(
            policy_id=policy_id,
            provider=config.provider,
            status="triggered",
            external_id="build-2",
        )


def make_service(database: Path, client: TriggerClient) -> RouterService:
    config = RouterConfig(
        version=1,
        pipelines=[
            PipelinePolicy(
                id="api-build",
                match=MatchConfig(
                    sources=[Source.GITHUB], repositories=["services/api"]
                ),
                trigger=JenkinsTrigger(
                    base_url="https://jenkins", job="api", token_env="TEST_TOKEN"
                ),
            )
        ],
    )
    return RouterService(config, EventStore(database), client)


def git_event() -> NormalizedEvent:
    return NormalizedEvent(
        source=Source.GITHUB,
        event_id="delivery-123",
        event_name="push",
        repositories=["services/api"],
        branch="main",
        revision="deadbeef",
        changed_files=["src/api.py"],
        repository_files={"services/api": ["src/api.py"]},
    )


async def test_route_claims_event_once(tmp_path: Path) -> None:
    client = FakeTriggerClient()
    service = make_service(tmp_path / "events.db", client)

    first = await service.route(git_event())
    second = await service.route(git_event())

    assert first.results[0].status == "triggered"
    assert second.results[0].status == "duplicate"
    assert client.calls == 1


async def test_one_provider_failure_does_not_stop_later_policy(tmp_path: Path) -> None:
    client = FirstFailureTriggerClient()
    service = make_service(tmp_path / "events.db", client)
    service.config.pipelines.append(
        PipelinePolicy(
            id="api-deploy",
            match=MatchConfig(
                sources=[Source.GITHUB], repositories=["services/api"]
            ),
            trigger=JenkinsTrigger(
                base_url="https://jenkins", job="deploy", token_env="TEST_TOKEN"
            ),
        )
    )

    response = await service.route(git_event())

    assert [result.status for result in response.results] == ["failed", "triggered"]
    assert client.calls == 2
