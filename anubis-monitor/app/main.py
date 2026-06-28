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


def status_label(status):
    if status.healthy:
        return "healthy"
    if status.error:
        return "down"
    return "degraded"


async def poll_instance(instance, timeout):
    try:
        text = await scrape_metrics(instance.url, timeout=timeout)
        metrics = parse_prometheus_text(text)
        summary = extract_anubis_summary(metrics)
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=True,
            last_seen=datetime.utcnow(),
            error=None,
            metrics=metrics,
            summary=summary,
        )
    except Exception as exc:
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=False,
            last_seen=None,
            error=str(exc),
            metrics={},
            summary={},
        )


async def refresh_state():
    config = load_config(CONFIG_PATH)
    tasks = [poll_instance(instance, config.timeout) for instance in config.instances]
    results = await asyncio.gather(*tasks) if tasks else []
    STATE.instances = results
    STATE.last_updated = datetime.utcnow()
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

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "instances": STATE.instances,
            "refresh": config.refresh,
            "last_updated": STATE.last_updated,
            "config_error": STATE.config_error,
            "status_label": status_label,
        },
    )