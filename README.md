# Anubis-Support

Tools for Anubis support on Koozali infrastructure.

# Anubis Setup and Test Scripts

This repository contains two companion scripts for deploying and validating an Anubis bot-protection setup. The shell script creates the service configuration, and the Python script runs end-to-end checks against the public site and the local Anubis instance [file:1][file:2].

## What’s included

- `make-anubis-2.sh` sets up an Anubis service, writes policy and environment files, and creates a systemd unit for the instance [file:1].
- `anubis_test_v2.py` exercises the deployed setup with HTTP requests, checks expected status codes and body content, and writes results to CSV [file:2].
- `anubis-monitor/` is a standalone web dashboard for keeping an eye on one or more running Anubis instances at a glance — see [Anubis Monitor](#anubis-monitor) below.

## Requirements

- Linux system with `bash`, `systemd`, and standard core utilities [file:1].
- An installed Anubis binary at `/usr/sbin/anubis` [file:1].
- Python 3 for the test runner [file:2].
- Network access to the target service and the public URL being tested [file:2].

## Script overview

### `make-anubis-2.sh`

The setup script expects a service name and a port, then validates the inputs before generating configuration files under `/etc/anubis` and a systemd service under `/etc/systemd/system` [file:1]. It also creates an `anubis` system user if needed, assigns permissions, and defines a policy that allows normal browsers while challenging unknown clients [file:1]. The script also calculates a metrics port by adding `10000` to the service port and fails safely if that would exceed the valid port range [file:1].

### `anubis_test_v2.py`

The test script targets both the local Anubis listener and the public site, using a set of named test cases with headers, expected statuses, and body assertions [file:2]. It captures response status, selected headers, timing, and a body preview, then writes all results into `anubis_test_results.csv` [file:2]. The tests include browser allowance, bot challenge behavior, a probe request, and a negative path check [file:2].

## Usage

### 1. Create the Anubis service

Run the setup script with a service name and port, then optionally override the target and difficulty settings [file:1].

```bash
sudo ./make-anubis-2.sh <name> <port> [--target <url>] [--difficulty <1-10>]  (I think it is 1-5 actually)
```

Example:

```bash
sudo ./make-anubis-2.sh mail 3002 --target https://mail.bjsystems.co.uk:443 --difficulty 3
```

### 2. Run the test suite

After deployment, run the Python test script to validate behavior and generate a CSV report [file:2].

```bash
python3 anubis_test_v2.py
```

## Output

The test runner appends rows to `anubis_test_results.csv`, including timestamp, test name, URL, status, latency, response length, headers, pass/fail state, failure reason, and a response body preview [file:2].

## Notes

- The setup script is opinionated and writes fixed paths and defaults, so review the generated policy before using it in production [file:1].
- The test script is intended for repeated verification and may append to an existing CSV file rather than overwriting it [file:2].
- Some configuration values, such as hostnames, ports, and the public base URL, are hard-coded in the test script and may need editing for a different environment [file:2].

# Anubis Monitor

`anubis-monitor/` is a lightweight observability dashboard for one or more Anubis reverse-proxy instances. It polls each instance's Prometheus `/metrics` endpoint, tracks health and policy-decision counters, and renders a single self-refreshing web page summarising the fleet — without needing a full Prometheus/Grafana stack.

Full design notes live in [`anubis-monitor/SPEC.md`](anubis-monitor/SPEC.md).

## What it does

- Polls every configured Anubis instance on a fixed interval and marks it healthy, degraded, or down.
- Parses each instance's Prometheus text output and extracts Anubis-specific counters: policy decisions (`ALLOW` / `CHALLENGE` / `DENY`), challenges issued, and requests proxied upstream.
- Keeps a rolling history in a local SQLite database so it can show traffic trends over a configurable window, not just the current snapshot.
- Surfaces service-health details per instance: uptime, resident memory, open file descriptors, and network throughput.
- Degrades gracefully — a single unreachable instance doesn't affect the rest of the dashboard.

## The website / dashboard

Anubis Monitor is a small [FastAPI](https://fastapi.tiangolo.com/) application (`anubis-monitor/app/main.py`) that serves one auto-refreshing dashboard page at `/`, plus a `/static` mount for its assets (favicon and a bundled copy of Chart.js). By convention on this project's infrastructure it runs on **port 8000** (see the note in `bugs.koozali.org.params`), typically co-located on the same host as the Anubis instances it watches.

![Example graph](example%20graph.png)

For each configured instance, the dashboard shows:

- A status header with a colour-coded indicator (🟢 healthy / 🟠 degraded / 🔴 down) and the last successful scrape time.
- Current counters and rates: total policy decisions, challenges issued, requests proxied upstream, requests denied, and the allow/challenge share as a percentage.
- A rolling-window summary (default last 24 hours) of the same counters.
- A traffic-trend bar chart (challenges, denials, and proxied requests per time bucket) rendered client-side with Chart.js from the stored history.
- Expandable detail panels for the per-rule policy breakdown, proxied-upstream targets by host, and low-level service health (uptime, memory, threads, file descriptors, network in/out).

The page itself has no JavaScript framework or build step — it's server-rendered HTML (Jinja2 templates) with one small inline script to draw the charts, so it's easy to deploy alongside Anubis with no extra tooling.

## Configuration

Anubis Monitor is configured entirely through `anubis-monitor/config.yaml`:

```yaml
refresh: 300              # polling interval in seconds
timeout: 5                # per-request scrape timeout in seconds
history_db: data/anubis-monitor.sqlite3
history_days: 30          # how long history is retained
chart_hours: 24           # window shown in the traffic chart
chart_bucket_seconds: 300 # chart bucket size

instances:
  - name: bugs
    url: http://127.0.0.1:19001/metrics
  - name: forums
    url: http://127.0.0.1:19002/metrics
  - name: wiki
    url: http://127.0.0.1:19003/metrics
  - name: gitea
    url: http://127.0.0.1:19004/metrics
```

Each entry under `instances` is a display name plus the Prometheus metrics URL exposed by that Anubis instance.

## Notes

- Built with Python 3.12+, FastAPI, httpx, Jinja2, and PyYAML; no authentication is implemented in this phase, so it should be run on a trusted/internal network or behind a reverse proxy.
- The `deploy/` folder contains placeholders for a Dockerfile and `docker-compose.yml` for containerised deployment — these are scaffolding for a future phase and are not yet filled in.
