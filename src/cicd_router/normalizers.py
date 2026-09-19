from __future__ import annotations

from .models import NormalizedEvent, PerforceHook, Source


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
