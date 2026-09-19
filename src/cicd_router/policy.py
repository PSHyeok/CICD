from __future__ import annotations

from fnmatch import fnmatchcase

from .models import NormalizedEvent, PipelinePolicy


class PathsUnavailableError(RuntimeError):
    pass


def _any_match(values: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for value in values for pattern in patterns)


def matches(policy: PipelinePolicy, event: NormalizedEvent) -> bool:
    rule = policy.match
    if not policy.enabled or event.source not in rule.sources:
        return False
    if not _any_match([event.event_name], rule.events):
        return False
    matched_repositories = [
        repository
        for repository in event.repositories
        if _any_match([repository], rule.repositories)
    ]
    if not matched_repositories:
        return False
    if not _any_match([event.branch], rule.branches):
        return False
    if rule.source_branches is not None:
        if event.source_branch is None or not _any_match(
            [event.source_branch], rule.source_branches
        ):
            return False
    if rule.target_branches is not None:
        if event.target_branch is None or not _any_match(
            [event.target_branch], rule.target_branches
        ):
            return False

    if not event.paths_complete:
        if rule.on_paths_unavailable == "trigger":
            return True
        if rule.on_paths_unavailable == "skip":
            return False
        raise PathsUnavailableError(
            f"changed paths are unavailable for policy: {policy.id}"
        )

    relevant_files = [
        path
        for repository in matched_repositories
        for path in event.repository_files.get(repository, [])
    ]
    if not relevant_files:
        # Omitting include_paths means repository/branch matching alone is
        # sufficient. An explicit path list requires at least one changed file.
        return rule.include_paths is None

    include_paths = rule.include_paths or ["*"]
    included = [
        path for path in relevant_files if _any_match([path], include_paths)
    ]
    return any(
        not _any_match([path], rule.exclude_paths) for path in included
    )


def matching_policies(
    policies: list[PipelinePolicy], event: NormalizedEvent
) -> list[PipelinePolicy]:
    return [policy for policy in policies if matches(policy, event)]
