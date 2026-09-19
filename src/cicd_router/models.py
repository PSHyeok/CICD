from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class Source(str, Enum):
    GITHUB = "github"
    PERFORCE = "perforce"


class GitHubRepository(BaseModel):
    full_name: str = Field(pattern=r"^[^/]+/[^/]+$")


class GitHubSender(BaseModel):
    login: str


class GitHubCommit(BaseModel):
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)


class GitHubPushHook(BaseModel):
    ref: str
    before: str
    after: str
    created: bool = False
    deleted: bool = False
    size: int = 0
    repository: GitHubRepository
    sender: GitHubSender
    commits: list[GitHubCommit] = Field(default_factory=list)


class GitHubBranchReference(BaseModel):
    ref: str
    sha: str


class GitHubPullRequest(BaseModel):
    head: GitHubBranchReference
    base: GitHubBranchReference


class GitHubPullRequestHook(BaseModel):
    action: str
    number: int
    repository: GitHubRepository
    sender: GitHubSender
    pull_request: GitHubPullRequest


class PerforceHook(BaseModel):
    changelist: int
    depot: str
    branch: str = "main"
    changed_files: list[str] = Field(default_factory=list)
    event_id: str | None = None
    event_name: str = "submit"
    actor: str | None = None


class NormalizedEvent(BaseModel):
    source: Source
    event_id: str
    event_name: str
    repositories: list[str]
    branch: str
    revision: str
    changed_files: list[str]
    repository_files: dict[str, list[str]]
    paths_complete: bool = True
    source_branch: str | None = None
    target_branch: str | None = None
    pull_request_number: int | None = None
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MatchConfig(BaseModel):
    sources: list[Source]
    events: list[str] = Field(default_factory=lambda: ["*"])
    repositories: list[str] = Field(default_factory=lambda: ["*"])
    branches: list[str] = Field(default_factory=lambda: ["*"])
    source_branches: list[str] | None = None
    target_branches: list[str] | None = None
    include_paths: list[str] | None = None
    exclude_paths: list[str] = Field(default_factory=list)
    on_paths_unavailable: Literal["trigger", "skip", "error"] = "trigger"


class JenkinsTrigger(BaseModel):
    provider: Literal["jenkins"] = "jenkins"
    base_url: str
    job: str
    username_env: str = "JENKINS_USERNAME"
    token_env: str = "JENKINS_TOKEN"
    parameters: dict[str, str] = Field(default_factory=dict)


TriggerConfig = JenkinsTrigger


class PipelinePolicy(BaseModel):
    id: str
    enabled: bool = True
    match: MatchConfig
    trigger: TriggerConfig


class FileManifestSource(BaseModel):
    provider: Literal["file"] = "file"
    path: str


class SqliteManifestSource(BaseModel):
    provider: Literal["sqlite"] = "sqlite"
    path: str


class HttpManifestSource(BaseModel):
    provider: Literal["http"] = "http"
    url: str
    token_env: str | None = None
    use_cached_on_error: bool = True


ManifestSourceConfig = Annotated[
    FileManifestSource | SqliteManifestSource | HttpManifestSource,
    Field(discriminator="provider"),
]


class RouterConfig(BaseModel):
    version: Literal[1]
    pipelines: list[PipelinePolicy] = Field(default_factory=list)
    manifest_source: ManifestSourceConfig | None = None


class RoutingManifest(BaseModel):
    version: Literal[1]
    manifest_version: str
    routes: list[PipelinePolicy]


class TriggerResult(BaseModel):
    policy_id: str
    provider: str
    status: Literal["triggered", "duplicate", "failed"]
    external_id: str | None = None
    external_url: str | None = None
    detail: str | None = None


class HookResponse(BaseModel):
    event_id: str
    manifest_version: str | None = None
    matched_policies: list[str]
    results: list[TriggerResult]


class IgnoredHookResponse(BaseModel):
    status: Literal["ignored"] = "ignored"
