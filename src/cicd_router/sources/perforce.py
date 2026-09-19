from fastapi import Request

from ..models import NormalizedEvent, PerforceHook
from ..normalizers import normalize_perforce
from .base import SourceAdapter, json_body, validate, verify_hmac


class PerforceSourceAdapter(SourceAdapter):
    name = "perforce"

    async def normalize(self, request: Request) -> NormalizedEvent:
        body, payload = await json_body(request)
        verify_hmac(body, request.headers.get("X-Hook-Signature"), "HOOK_SECRET")
        hook = validate(PerforceHook, payload)
        return normalize_perforce(hook)
