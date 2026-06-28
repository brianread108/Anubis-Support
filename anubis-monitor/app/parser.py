from typing import Dict, Optional


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def parse_prometheus_text(text: str) -> Dict[str, float]:
    metrics = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        name = parts[0]
        value = _safe_float(parts[1])
        if value is None:
            continue

        metrics[name] = value

    return metrics


def _find_metric(metrics: Dict[str, float], names) -> Optional[float]:
    for name in names:
        if name in metrics:
            return metrics[name]
    return None


def extract_anubis_summary(metrics: Dict[str, float]) -> Dict[str, Optional[float]]:
    request_rate = _find_metric(
        metrics,
        [
            "anubis_requests_total",
            "anubis_request_total",
            "anubis_requests_per_second",
            "anubis_request_rate",
        ],
    )
    challenge_rate = _find_metric(
        metrics,
        [
            "anubis_challenges_total",
            "anubis_challenge_total",
            "anubis_challenges_per_second",
            "anubis_challenge_rate",
        ],
    )
    success_rate = _find_metric(
        metrics,
        [
            "anubis_success_total",
            "anubis_success_rate",
        ],
    )
    failure_rate = _find_metric(
        metrics,
        [
            "anubis_failure_total",
            "anubis_failure_rate",
        ],
    )
    backend_latency = _find_metric(
        metrics,
        [
            "anubis_backend_latency_seconds",
            "anubis_backend_latency",
            "anubis_request_duration_seconds",
        ],
    )

    return {
        "request_rate": request_rate,
        "challenge_rate": challenge_rate,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "backend_latency": backend_latency,
    }