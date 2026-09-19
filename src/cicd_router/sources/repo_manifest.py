from fastapi import Request

from ..models import NormalizedEvent, RepoManifestHook
from ..normalizers import normalize_repo_manifest
from .base import SourceAdapter, json_body, validate, verify_hmac


class RepoManifestSourceAdapter(SourceAdapter):
    name = "repo-manifest"

    async def normalize(self, request: Request) -> NormalizedEvent:
        body, payload = await json_body(request)
        verify_hmac(body, request.headers.get("X-Hook-Signature"), "HOOK_SECRET")
        hook = validate(RepoManifestHook, payload)
        return normalize_repo_manifest(hook)
