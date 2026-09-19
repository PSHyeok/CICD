from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(str, Enum):
    GITHUB = "github"
    PERFORCE = "perforce"
    REPO_MANIFEST = "repo_manifest"


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


class PerforceHook(BaseModel):
    changelist: int
    depot: str
    branch: str = "main"
    changed_files: list[str] = Field(default_factory=list)
    event_id: str | None = None
    event_name: str = "submit"
    actor: str | None = None


class ManifestProjectChange(BaseModel):
    name: str
    revision: str
    changed_files: list[str] = Field(default_factory=list)


class RepoManifestHook(BaseModel):
    event_id: str
    manifest: str
    branch: str
    revision: str
    projects: list[ManifestProjectChange]
    event_name: str = "sync"
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
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MatchConfig(BaseModel):
    sources: list[Source]
    events: list[str] = Field(default_factory=lambda: ["*"])
    repositories: list[str] = Field(default_factory=lambda: ["*"])
    branches: list[str] = Field(default_factory=lambda: ["*"])
    include_paths: list[str] = Field(default_factory=lambda: ["*"])
    exclude_paths: list[str] = Field(default_factory=list)


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


class RouterConfig(BaseModel):
    version: Literal[1]
    pipelines: list[PipelinePolicy]


class TriggerResult(BaseModel):
    policy_id: str
    provider: str
    status: Literal["triggered", "duplicate", "failed"]
    external_id: str | None = None
    external_url: str | None = None
    detail: str | None = None


class HookResponse(BaseModel):
    event_id: str
    matched_policies: list[str]
    results: list[TriggerResult]


class IgnoredHookResponse(BaseModel):
    status: Literal["ignored"] = "ignored"
