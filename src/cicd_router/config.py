from __future__ import annotations

from pathlib import Path

import yaml

from .models import RouterConfig


def load_config(path: str | Path) -> RouterConfig:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return RouterConfig.model_validate(data)

