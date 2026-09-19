from __future__ import annotations

import hashlib
import hmac
import json
import os
from abc import ABC, abstractmethod
from typing import TypeVar

from fastapi import HTTPException, Request
from pydantic import BaseModel, ValidationError

from ..models import NormalizedEvent

ModelT = TypeVar("ModelT", bound=BaseModel)


def verify_hmac(body: bytes, supplied: str | None, secret_env: str) -> None:
    secret = os.getenv(secret_env)
    if not secret:
        return
    if not supplied:
        raise HTTPException(status_code=401, detail="missing hook signature")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    actual = supplied.removeprefix("sha256=")
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=401, detail="invalid hook signature")


async def json_body(request: Request) -> tuple[bytes, object]:
    body = await request.body()
    try:
        return body, json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc


def validate(model: type[ModelT], payload: object) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


class SourceAdapter(ABC):
    """Translate one repository system's native webhook into NormalizedEvent."""

    name: str

    @abstractmethod
    async def normalize(self, request: Request) -> NormalizedEvent | None: ...
