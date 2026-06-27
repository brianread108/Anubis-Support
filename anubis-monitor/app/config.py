from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class InstanceConfig:
    name: str
    url: str


@dataclass
class AppConfig:
    refresh: int = 10
    instances: list[InstanceConfig] = None

from pathlib import Path
from typing import Union

def load_config(path: Union[str, Path]) -> AppConfig:
    path = Path(path)
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    instances = [
        InstanceConfig(
            name=item["name"],
            url=item["url"],
        )
        for item in raw.get("instances", [])
        if item.get("name") and item.get("url")
    ]

    return AppConfig(
        refresh=int(raw.get("refresh", 10)),
        instances=instances,
    )