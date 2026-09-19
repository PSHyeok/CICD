from fastapi import HTTPException

from .base import SourceAdapter


class SourceAdapterRegistry:
    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def get(self, name: str) -> SourceAdapter:
        adapter = self._adapters.get(name)
        if adapter is None:
            raise HTTPException(
                status_code=404, detail=f"unsupported hook source: {name}"
            )
        return adapter

    @property
    def names(self) -> list[str]:
        return sorted(self._adapters)

