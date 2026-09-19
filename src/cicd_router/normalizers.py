from __future__ import annotations

from .models import NormalizedEvent, PerforceHook, RepoManifestHook, Source


def normalize_perforce(hook: PerforceHook) -> NormalizedEvent:
    return NormalizedEvent(
        source=Source.PERFORCE,
        event_id=hook.event_id or f"p4-{hook.changelist}",
        event_name=hook.event_name,
        repositories=[hook.depot],
        branch=hook.branch,
        revision=str(hook.changelist),
        changed_files=hook.changed_files,
        repository_files={hook.depot: hook.changed_files},
        actor=hook.actor,
        metadata={"changelist": hook.changelist},
    )


def normalize_repo_manifest(hook: RepoManifestHook) -> NormalizedEvent:
    changed_files = [path for project in hook.projects for path in project.changed_files]
    return NormalizedEvent(
        source=Source.REPO_MANIFEST,
        event_id=hook.event_id,
        event_name=hook.event_name,
        repositories=[project.name for project in hook.projects],
        branch=hook.branch,
        revision=hook.revision,
        changed_files=changed_files,
        repository_files={
            project.name: project.changed_files for project in hook.projects
        },
        actor=hook.actor,
        metadata={
            "manifest": hook.manifest,
            "project_revisions": {
                project.name: project.revision for project in hook.projects
            },
        },
    )
