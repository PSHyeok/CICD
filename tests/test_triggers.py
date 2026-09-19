import httpx

from cicd_router.models import JenkinsTrigger, NormalizedEvent, Source
from cicd_router.triggers import HttpTriggerClient


def event() -> NormalizedEvent:
    return NormalizedEvent(
        source=Source.GITHUB,
        event_id="evt-9",
        event_name="push",
        repositories=["apps/web"],
        branch="main",
        revision="abc123",
        changed_files=["src/index.ts"],
        repository_files={"apps/web": ["src/index.ts"]},
    )


async def test_jenkins_nested_job_url(monkeypatch) -> None:
    monkeypatch.setenv("JENKINS_TEST_USER", "router")
    monkeypatch.setenv("JENKINS_TEST_TOKEN", "secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/job/team/job/web/buildWithParameters"
        assert request.url.params["HOOK_REVISION"] == "abc123"
        assert request.url.params["ROUTING_MANIFEST_VERSION"] == "manifest-v1"
        return httpx.Response(201, headers={"Location": "https://jenkins/queue/7"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await HttpTriggerClient(http).trigger(
            "web-jenkins",
            JenkinsTrigger(
                base_url="https://jenkins",
                job="team/web",
                username_env="JENKINS_TEST_USER",
                token_env="JENKINS_TEST_TOKEN",
            ),
            event().model_copy(update={"metadata": {"manifest_version": "manifest-v1"}}),
        )
    assert result.external_url == "https://jenkins/queue/7"
