from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class InstanceStatus:
    name: str
    url: str
    healthy: bool = False
    last_seen: Optional[datetime] = None
    error: Optional[str] = None
    raw_samples: List[Dict[str, object]] = field(default_factory=list)
    summary: Dict[str, object] = field(default_factory=dict)


@dataclass
class MonitorState:
    last_updated: Optional[datetime] = None
    instances: List[InstanceStatus] = field(default_factory=list)
    config_error: Optional[str] = None


STATE = MonitorState()