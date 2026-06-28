from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

import yaml


@dataclass
class InstanceConfig:
    name: str
    url: str


@dataclass
class AppConfig:
    refresh: int = 10
    instances: List[InstanceConfig] = field(default_factory=list)


def load_config(path: Union[str, Path]) -> AppConfig:
    path = Path(path)
    raw = {}

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    instances = []
    for item in raw.get("instances", []):
        name = item.get("name")
        url = item.get("url")
        if name and url:
            instances.append(InstanceConfig(name=name, url=url))

    return AppConfig(
        refresh=int(raw.get("refresh", 10)),
        instances=instances,
    )