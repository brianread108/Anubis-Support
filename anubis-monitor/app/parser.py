from typing import Dict, List, Optional, Tuple


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def _split_sample(sample_name: str) -> Tuple[str, Dict[str, str]]:
    if "{" not in sample_name:
        return sample_name, {}

    name, rest = sample_name.split("{", 1)
    labels_text = rest.rsplit("}", 1)[0]
    labels = {}

    if labels_text.strip():
        parts = []
        current = []
        in_quotes = False
        escape = False

        for ch in labels_text:
            if escape:
                current.append(ch)
                escape = False
                continue
            if ch == "\\":
                current.append(ch)
                escape = True
                continue
            if ch == '"':
                in_quotes = not in_quotes
                current.append(ch)
                continue
            if ch == "," and not in_quotes:
                parts.append("".join(current).strip())
                current = []
                continue
            current.append(ch)

        if current:
            parts.append("".join(current).strip())

        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"')
            value = value.replace('\\"', '"').replace("\\\\", "\\")
            labels[key] = value

    return name, labels


def parse_prometheus_text(text: str) -> List[Dict[str, object]]:
    samples = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        name, labels = _split_sample(parts[0])
        value = _safe_float(parts[1])

        if value is not None:
            samples.append({
                "name": name,
                "labels": labels,
                "value": value,
            })

    return samples


def extract_anubis_summary(samples: List[Dict[str, object]]) -> Dict[str, object]:
    summary = {
        "proxied_total": 0.0,
        "proxied_by_host": {},
        "challenge_issued": 0.0,
        "challenges_by_method": {},
        "policy_results": {},
        "runtime": {},
    }

    runtime_metrics = {
        "process_start_time_seconds",
        "process_cpu_seconds_total",
        "process_resident_memory_bytes",
        "process_open_fds",
        "process_max_fds",
        "process_network_receive_bytes_total",
        "process_network_transmit_bytes_total",
        "go_goroutines",
        "go_threads",
    }

    for sample in samples:
        name = sample.get("name")
        labels = sample.get("labels", {})
        value = sample.get("value")

        if not isinstance(value, (int, float)):
            continue

        if name == "anubis_proxied_requests_total":
            host = labels.get("host", "unknown")
            summary["proxied_by_host"][host] = value
            summary["proxied_total"] += value

        elif name == "anubis_challenges_issued":
            method = labels.get("method", "unknown")
            summary["challenges_by_method"][method] = value
            summary["challenge_issued"] += value

        elif name == "anubis_policy_results":
            action = labels.get("action", "UNKNOWN")
            rule = labels.get("rule", "")
            summary["policy_results"][(action, rule)] = value

        elif name in runtime_metrics:
            summary["runtime"][name] = value

    return summary
