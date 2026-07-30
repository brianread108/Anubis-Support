import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import load_config
from app.parser import extract_anubis_summary, parse_prometheus_text
from app.scraper import scrape_metrics
from app.state import InstanceStatus, STATE

from app.history import history_rows, initialise, period_delta, prune_history, save_sample

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def fmt_value(value):
    if value is None:
        return "-"

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"

    return str(value)


def fmt_bytes(value):
    if value is None:
        return "-"

    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(value)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024

    return "-"


def fmt_duration(seconds):
    if seconds is None or seconds < 0:
        return "-"

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"


def status_label(status):
    if status.healthy:
        return "healthy"
    if status.error:
        return "down"
    return "degraded"


def status_icon(status):
    return {
        "healthy": "🟢",
        "degraded": "🟠",
        "down": "🔴",
    }[status_label(status)]


def counter_delta(current, previous):
    if current is None or previous is None:
        return 0.0

    delta = current - previous

    # A Prometheus counter normally falls only after a process restart.
    return current if delta < 0 else delta


def policy_totals(policy_results):
    totals = {"ALLOW": 0.0, "CHALLENGE": 0.0, "DENY": 0.0}

    for (action, _rule), value in policy_results.items():
        if action in totals:
            totals[action] += value

    return totals


def derive_summary(summary, previous_summary, elapsed_seconds):
    current_policy = summary.get("policy_results", {})
    previous_policy = previous_summary.get("policy_results", {}) if previous_summary else {}

    policy_delta = {
        key: counter_delta(value, previous_policy.get(key))
        for key, value in current_policy.items()
    }

    current_totals = policy_totals(current_policy)
    delta_totals = policy_totals(policy_delta)
    total_decisions = sum(current_totals.values())
    delta_decisions = sum(delta_totals.values())

    previous_proxied = previous_summary.get("proxied_total") if previous_summary else None
    previous_challenges = previous_summary.get("challenge_issued") if previous_summary else None

    proxied_delta = counter_delta(summary.get("proxied_total"), previous_proxied)
    challenges_delta = counter_delta(summary.get("challenge_issued"), previous_challenges)

    runtime = summary.get("runtime", {})
    previous_runtime = previous_summary.get("runtime", {}) if previous_summary else {}

    received_delta = counter_delta(
        runtime.get("process_network_receive_bytes_total"),
        previous_runtime.get("process_network_receive_bytes_total"),
    )
    transmitted_delta = counter_delta(
        runtime.get("process_network_transmit_bytes_total"),
        previous_runtime.get("process_network_transmit_bytes_total"),
    )

    rate_multiplier = 60 / elapsed_seconds if elapsed_seconds > 0 else 0

    rule_rows = []
    for (action, rule), total in sorted(current_policy.items()):
        delta = policy_delta.get((action, rule), 0.0)
        rule_rows.append({
            "action": action,
            "rule": rule or "-",
            "total": total,
            "delta": delta,
            "per_minute": delta * rate_multiplier,
        })

    rule_rows.sort(key=lambda row: row["delta"], reverse=True)

    start_time = runtime.get("process_start_time_seconds")
    uptime = datetime.now().timestamp() - start_time if start_time else None

    return {
        "totals": current_totals,
        "deltas": delta_totals,
        "total_decisions": total_decisions,
        "delta_decisions": delta_decisions,
        "proxied_delta": proxied_delta,
        "challenges_delta": challenges_delta,
        "per_minute": {
            "decisions": delta_decisions * rate_multiplier,
            "proxied": proxied_delta * rate_multiplier,
            "challenges": challenges_delta * rate_multiplier,
            "deny": delta_totals["DENY"] * rate_multiplier,
            "received_bytes": received_delta * rate_multiplier,
            "transmitted_bytes": transmitted_delta * rate_multiplier,
        },
        "percentages": {
            action: (100 * value / total_decisions if total_decisions else 0)
            for action, value in current_totals.items()
        },
        "rules": rule_rows,
        "runtime": runtime,
        "uptime": uptime,
    }


async def poll_instance(instance, timeout, previous_status=None):
    try:
        text = await scrape_metrics(instance.url, timeout=timeout)
        samples = parse_prometheus_text(text)
        summary = extract_anubis_summary(samples)

        now = datetime.now().astimezone()
        previous_summary = previous_status.summary if previous_status and previous_status.healthy else {}
        previous_time = previous_status.last_seen if previous_status else None

        elapsed = 0
        if previous_time:
            elapsed = (now - previous_time).total_seconds()

        derived = derive_summary(summary, previous_summary, elapsed)

        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=True,
            last_seen=now,
            error=None,
            raw_samples=samples,
            summary=summary,
            derived=derived,
        )

    except Exception as exc:
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=False,
            last_seen=None,
            error=str(exc),
        )


async def refresh_state():
    config = load_config(CONFIG_PATH)
    previous = {instance.name: instance for instance in STATE.instances}

    tasks = [
        poll_instance(instance, config.timeout, previous.get(instance.name))
        for instance in config.instances
    ]

    STATE.instances = await asyncio.gather(*tasks) if tasks else []
    for instance in STATE.instances:
        save_sample(config.history_db, instance)
    prune_history(config.history_db, config.history_days)
    STATE.last_updated = datetime.now().astimezone()
    STATE.config_error = None


async def refresh_loop():
    while True:
        try:
            await refresh_state()
        except Exception as exc:
            STATE.config_error = str(exc)

        config = load_config(CONFIG_PATH)
        await asyncio.sleep(max(1, int(config.refresh)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config(CONFIG_PATH)
    initialise(config.history_db)

    app.state.refresh_task = asyncio.create_task(refresh_loop())
    try:
        yield
    finally:
        app.state.refresh_task.cancel()
        try:
            await app.state.refresh_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Anubis Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config(CONFIG_PATH)

    if not STATE.instances and config.instances:
        await refresh_state()

    history = {}

    for instance in STATE.instances:
        rows = history_rows(
            config.history_db,
            instance.name,
            config.chart_hours,
        )

        history[instance.name] = {
            "rows": rows,
            "decisions": period_delta(rows, "decisions"),
            "allow": period_delta(rows, "allow"),
            "challenge": period_delta(rows, "challenge"),
            "deny": period_delta(rows, "deny"),
            "issued": period_delta(rows, "challenges_issued"),
            "proxied": period_delta(rows, "proxied"),
        }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "instances": STATE.instances,
            "history": history,
            "refresh": config.refresh,
            "chart_hours": config.chart_hours,
            "last_updated": STATE.last_updated,
            "config_error": STATE.config_error,
            "status_label": status_label,
            "status_icon": status_icon,
            "fmt_value": fmt_value,
            "fmt_bytes": fmt_bytes,
            "fmt_duration": fmt_duration,
        },
    )