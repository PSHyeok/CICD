from __future__ import annotations

from fnmatch import fnmatchcase

from .models import NormalizedEvent, PipelinePolicy


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

    # GitHub Compare returns at most 300 files. When the set is incomplete,
    # triggering an extra build is safer than silently skipping a required one.
    if not event.paths_complete:
        return True

    relevant_files = [
        path
        for repository in matched_repositories
        for path in event.repository_files.get(repository, [])
    ]
    if not relevant_files:
        return rule.include_paths == ["*"] and not rule.exclude_paths

    included = [
        path for path in relevant_files if _any_match([path], rule.include_paths)
    ]
    return any(
        not _any_match([path], rule.exclude_paths) for path in included
    )


def matching_policies(
    policies: list[PipelinePolicy], event: NormalizedEvent
) -> list[PipelinePolicy]:
    return [policy for policy in policies if matches(policy, event)]
