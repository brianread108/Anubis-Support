from datetime import datetime
from pathlib import Path
from typing import List

import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import AppConfig, InstanceConfig, load_config
from app.parser import parse_prometheus_text
from app.scraper import scrape_metrics
from app.state import InstanceStatus, STATE

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(title="Anubis Monitor")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def status_label(status: InstanceStatus) -> str:
    if status.healthy:
        return "healthy"
    if status.error:
        return "down"
    return "degraded"


async def poll_instance(instance: InstanceConfig) -> InstanceStatus:
    try:
        text = await scrape_metrics(instance.url, timeout=5.0)
        metrics = parse_prometheus_text(text)
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=True,
            last_seen=datetime.utcnow(),
            error=None,
            metrics=metrics,
        )
    except Exception as exc:
        return InstanceStatus(
            name=instance.name,
            url=instance.url,
            healthy=False,
            last_seen=None,
            error=str(exc),
            metrics={},
        )


async def refresh_state() -> None:
    config = load_config(CONFIG_PATH)
    tasks = [poll_instance(instance) for instance in config.instances]
    results = await asyncio.gather(*tasks) if tasks else []
    STATE.instances = results
    STATE.last_updated = datetime.utcnow()


@app.on_event("startup")
async def startup_event() -> None:
    await refresh_state()


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
            "status_label": status_label,
        },
    )