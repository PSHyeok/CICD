from __future__ import annotations

from .manifests import ManifestProvider, StaticManifestProvider
from .models import HookResponse, NormalizedEvent, RouterConfig, TriggerResult
from .policy import matching_policies
from .store import EventStore
from .triggers import TriggerClient


class RouterService:
    def __init__(
        self,
        config: RouterConfig,
        store: EventStore,
        trigger_client: TriggerClient,
        manifest_provider: ManifestProvider | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.trigger_client = trigger_client
        self.manifest_provider = manifest_provider or StaticManifestProvider(
            config.pipelines
        )

    async def route(self, event: NormalizedEvent) -> HookResponse:
        manifest = await self.manifest_provider.load()
        policies = matching_policies(manifest.routes, event)
        results: list[TriggerResult] = []
        trigger_event = event.model_copy(
            update={
                "metadata": {
                    **event.metadata,
                    "manifest_version": manifest.version,
                }
            }
        )

        for policy in policies:
            claimed = self.store.claim(event.source.value, event.event_id, policy.id)
            if not claimed:
                results.append(
                    TriggerResult(
                        policy_id=policy.id,
                        provider=policy.trigger.provider,
                        status="duplicate",
                        detail="this event and policy were already claimed",
                    )
                )
                continue

            try:
                result = await self.trigger_client.trigger(
                    policy.id, policy.trigger, trigger_event
                )
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                self.store.finish(
                    event.source.value,
                    event.event_id,
                    policy.id,
                    "failed",
                    detail=detail,
                )
                results.append(
                    TriggerResult(
                        policy_id=policy.id,
                        provider=policy.trigger.provider,
                        status="failed",
                        detail=detail,
                    )
                )
                continue

            self.store.finish(
                event.source.value,
                event.event_id,
                policy.id,
                "triggered",
                external_id=result.external_id,
                external_url=result.external_url,
            )
            results.append(result)

        return HookResponse(
            event_id=event.event_id,
            manifest_version=manifest.version,
            matched_policies=[policy.id for policy in policies],
            results=results,
        )
