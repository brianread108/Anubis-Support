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

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def status_label(status):
    healthy = _get_value(status, "healthy", False)
    error = _get_value(status, "error", None)

    if healthy:
        return "healthy"
    if error:
        return "down"
    return "degraded"


def status_icon(status):
    label = status_label(status)
    if label == "healthy":
        return "🟢"
    if label == "degraded":
        return "🟠"
    return "🔴"


def fmt_value(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return "{:.3f}".format(value)
    return str(value)


def _policy_summary(policy_results):
    counts = {"ALLOW": 0.0, "CHALLENGE": 0.0, "DENY": 0.0}
    for (action, rule), value in policy_results.items():
        if action in counts and isinstance(value, (int, float)):
            counts[action] += value
    return counts


async def poll_instance(instance, timeout):
    try:
        text = await scrape_metrics(instance.url, timeout=timeout)
        samples = parse_prometheus_text(text)
        summary = extract_anubis_summary(samples)
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=True,
            last_seen=datetime.now().astimezone().replace(tzinfo=None),
            error=None,
            raw_samples=samples,
            summary=summary,
        )
    except Exception as exc:
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=False,
            last_seen=None,
            error=str(exc),
            raw_samples=[],
            summary={},
        )


async def refresh_state():
    config = load_config(CONFIG_PATH)
    tasks = [poll_instance(instance, config.timeout) for instance in config.instances]
    results = await asyncio.gather(*tasks) if tasks else []
    STATE.instances = results
    STATE.last_updated = datetime.now().astimezone().replace(tzinfo=None)
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
    app.state.refresh_task = asyncio.create_task(refresh_loop())
    try:
        yield
    finally:
        task = app.state.refresh_task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Anubis Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config(CONFIG_PATH)
    if not STATE.instances and config.instances:
        await refresh_state()

    view_instances = []
    for inst in STATE.instances:
        summary = inst.summary or {}
        policy_results = summary.get("policy_results", {})
        view_instances.append(
            {
                "name": inst.name,
                "url": inst.url,
                "healthy": inst.healthy,
                "last_seen": inst.last_seen,
                "error": inst.error,
                "request_total": summary.get("request_total"),
                "challenge_issued": summary.get("challenge_issued"),
                "policy_counts": _policy_summary(policy_results),
                "policy_rows": [
                    {
                        "action": action,
                        "rule": rule,
                        "value": value,
                    }
                    for (action, rule), value in sorted(policy_results.items())
                ],
            }
        )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "instances": view_instances,
            "refresh": config.refresh,
            "last_updated": STATE.last_updated,
            "config_error": STATE.config_error,
            "status_label": status_label,
            "status_icon": status_icon,
            "fmt_value": fmt_value,
        },
    )