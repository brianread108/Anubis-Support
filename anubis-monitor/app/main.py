from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import load_config
from app.scraper import scrape_metrics

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

app = FastAPI(title="Anubis Monitor")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

state = {
    "last_updated": None,
    "instances": [],
}


def parse_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            metrics[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return metrics


async def poll_instance(name: str, url: str, timeout: float = 5.0) -> dict:
    try:
        raw = await scrape_metrics(url, timeout=timeout)
        metrics = parse_metrics(raw)
        return {
            "name": name,
            "url": url,
            "healthy": True,
            "last_seen": datetime.now(timezone.utc),
            "error": None,
            "metrics": metrics,
        }
    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "healthy": False,
            "last_seen": None,
            "error": str(exc),
            "metrics": {},
        }


async def refresh_state() -> None:
    config = load_config(CONFIG_PATH)
    tasks = [
        poll_instance(instance.name, instance.url, timeout=5.0)
        for instance in config.instances
    ]
    results = await asyncio.gather(*tasks) if tasks else []
    state["instances"] = results
    state["last_updated"] = datetime.now(timezone.utc)


@app.on_event("startup")
async def startup_event() -> None:
    await refresh_state()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config(CONFIG_PATH)
    if not state["instances"] and config.instances:
        await refresh_state()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "instances": state["instances"],
            "refresh": config.refresh,
            "last_updated": state["last_updated"],
        },
    )