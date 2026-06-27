#!/usr/bin/env python3
import sys
from pathlib import Path

TEMPLATE_SPEC = """# Anubis Monitor — Project Specification

(Place your full SPEC.md here or replace this file after scaffold creation.)
"""

def create_scaffold(base='anubis-monitor'):
    basep = Path(base)
    structure = [
        'README.md',
        'SPEC.md',
        '.gitignore',
        'pyproject.toml',
        'requirements.txt',
        'app/__init__.py',
        'app/main.py',
        'app/config.py',
        'app/scraper.py',
        'app/parser.py',
        'app/state.py',
        'app/templates/index.html',
        'app/static/.gitkeep',
        'tests/test_scraper.py',
        'scripts/run.sh',
        'deploy/Dockerfile',
        'deploy/docker-compose.yml'
    ]

    basep.mkdir(parents=True, exist_ok=True)

    for p in structure:
        fp = basep / Path(p)
        fp.parent.mkdir(parents=True, exist_ok=True)
        if not fp.exists():
            # create sensible placeholder content for common file types
            if fp.suffix == '.py':
                content = '# ' + p + '\\n'
                if p.endswith('__init__.py'):
                    content += '__all__ = []\\n'
                elif p.endswith('main.py'):
                    content += (
                        'from fastapi import FastAPI\\n'
                        'from starlette.responses import HTMLResponse\\n\\n'
                        'app = FastAPI()\\n\\n'
                        "@app.get('/', response_class=HTMLResponse)\\n"
                        'async def index():\\n'
                        "    return '<h1>Anubis Monitor</h1>'\\n"
                    )
                elif p.endswith('scraper.py'):
                    content += (
                        'import asyncio\\n'
                        'import httpx\\n\\n'
                        'async def scrape(url, timeout=5):\\n'
                        '    async with httpx.AsyncClient(timeout=timeout) as client:\\n'
                        '        resp = await client.get(url)\\n'
                        '        resp.raise_for_status()\\n'
                        '        return resp.text\\n'
                    )
                elif p.endswith('parser.py'):
                    content += (
                        'def parse_prometheus_text(text):\\n'
                        '    # minimal parser stub: returns dict of metric->value\\n'
                        "    metrics = {}\\n"
                        '    for line in text.splitlines():\\n'
                        "        if line.startswith('#') or not line.strip():\\n"
                        '            continue\\n'
                        '        parts = line.split()\\n'
                        '        if len(parts) >= 2:\\n'
                        '            metrics[parts[0]] = float(parts[1])\\n'
                        '    return metrics\\n'
                    )
                elif p.endswith('state.py'):
                    content += (
                        'from dataclasses import dataclass, field\\n'
                        'from datetime import datetime\\n\\n'
                        '@dataclass\\n'
                        'class InstanceStatus:\\n'
                        '    name: str\\n'
                        '    url: str\\n'
                        '    healthy: bool = False\\n'
                        '    last_seen: datetime | None = None\\n'
                        '    error: str | None = None\\n'
                        '    metrics: dict = field(default_factory=dict)\\n'
                    )
                else:
                    content += '\\n'
            elif fp.suffix in ('.md', '.txt'):
                content = '# ' + p + '\\n'
                if p == 'SPEC.md':
                    content = TEMPLATE_SPEC
            elif fp.name == '.gitignore':
                content = '__pycache__/\\n.env\\n.venv/\\n*.pyc\\n'
            elif fp.suffix in ('.yml', '.yaml'):
                content = '# placeholder\\n'
            elif fp.suffix == '.sh':
                content = '#!/usr/bin/env bash\\n# run script placeholder\\n'
            else:
                content = ''
            fp.write_text(content)
            # make scripts executable
            if fp.suffix == '.sh':
                fp.chmod(0o755)

    print(f'Scaffold created at: {basep.resolve()}')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'anubis-monitor'
    create_scaffold(target)
