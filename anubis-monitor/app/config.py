from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

import yaml


@dataclass
class InstanceConfig:
    name: str
    url: str


@dataclass
class AppConfig:
    refresh: int = 30
    timeout: float = 5.0
    history_db: str = "data/anubis-monitor.sqlite3"
    history_days: int = 30
    chart_hours: int = 24
    instances: List[InstanceConfig] = field(default_factory=list)


def load_config(path: Union[str, Path]) -> AppConfig:
    path = Path(path)
    raw = {}

    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

    instances = []
    for item in raw.get("instances", []):
        name = item.get("name")
        url = item.get("url")
        if name and url:
            instances.append(InstanceConfig(name=name, url=url))

    return AppConfig(
        refresh=max(5, int(raw.get("refresh", 30))),
        timeout=float(raw.get("timeout", 5.0)),
        history_db=str(raw.get("history_db", "data/anubis-monitor.sqlite3")),
        history_days=max(1, int(raw.get("history_days", 30))),
        chart_hours=max(1, int(raw.get("chart_hours", 24))),
        instances=instances,
    )