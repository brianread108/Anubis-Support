Here is a clean **project specification document** for the Anubis Monitor. I’ve written it as something you could drop straight into a Git repository as `SPEC.md` and review before any implementation.

---

# Anubis Monitor — Project Specification

## 1. Overview

The **Anubis Monitor** is a lightweight observability dashboard for multiple instances of the Anubis reverse proxy.

It is designed to:

* Monitor multiple Anubis instances protecting different services
* Provide a single, human-readable status dashboard
* Track live metrics from Prometheus endpoints exposed by each instance
* Offer basic historical visibility (Phase 2+)
* Remain simple to deploy on a single server alongside Anubis

It is explicitly **not** intended to replace Prometheus or Grafana, but to provide a focused operational view for small-to-medium self-hosted environments.

---

## 2. Goals

### Primary goals

* Display health and status of multiple Anubis instances
* Show key real-time metrics per instance:

  * request rate
  * challenge rate
  * success/failure rate
  * backend latency (if available)
* Provide a single dashboard view of all protected services
* Detect and highlight instance downtime or scrape failures

### Secondary goals (later phases)

* Store historical metrics (SQLite)
* Provide graphs (request/challenge trends)
* Alerting on anomalies (spikes, downtime)
* API endpoint for external integration

---

## 3. Non-goals

* Full Prometheus replacement
* Distributed monitoring system
* Multi-user authentication system (initially)
* Complex role-based access control
* High-scale telemetry ingestion (this is for small infra)

---

## 4. Assumptions

* Each Anubis instance exposes a Prometheus metrics endpoint (typically `/metrics`)
* Instances are reachable from the monitor host over HTTP(S)
* Metrics format follows standard Prometheus text exposition format
* Instances are relatively low count (1–50 targets typical use)

---

## 5. System Architecture

### Phase 1 (MVP architecture)

```text
           +----------------------+
           |  Anubis Instance A   | ---- /metrics
           +----------------------+
           +----------------------+
           |  Anubis Instance B   | ---- /metrics
           +----------------------+

                      ↓ polling (HTTP)

           +----------------------+
           |  Anubis Monitor      |
           |  (FastAPI app)       |
           |                      |
           |  - scraper           |
           |  - parser            |
           |  - in-memory state   |
           +----------------------+

                      ↓

           Web Dashboard (HTML)
```

No database in Phase 1.

---

## 6. Configuration

Configuration is defined in a YAML file.

### Example

```yaml
refresh: 10

instances:
  - name: Wiki
    url: http://127.0.0.1:9090/metrics

  - name: Forum
    url: http://127.0.0.1:9091/metrics

  - name: Gitea
    url: http://127.0.0.1:9092/metrics
```

### Fields

* `refresh`: polling interval in seconds
* `instances[]`:

  * `name`: display name
  * `url`: Prometheus metrics endpoint

---

## 7. Functional Requirements

### 7.1 Scraping

* System must poll each instance at a fixed interval
* Requests must be concurrent (non-blocking I/O preferred)
* Timeout per request (default 3–5 seconds)
* Failed requests must mark instance as unhealthy

---

### 7.2 Metrics Parsing

* Must parse Prometheus text format
* Extract only relevant metrics initially:

  * request counters
  * challenge counters
  * success/failure counters
  * latency metrics (if present)
* Preserve raw metrics optionally for debugging (Phase 2+)

---

### 7.3 State Management

* Maintain in-memory state:

  * last successful scrape timestamp
  * health status
  * latest metric snapshot per instance
  * last error (if any)

---

### 7.4 Dashboard

Single web page (initially):

* List of all instances
* Status indicator:

  * 🟢 Healthy
  * 🟠 Degraded (partial failure / stale metrics)
  * 🔴 Down (scrape failure)
* Key metrics per instance:

  * requests/sec
  * challenges/sec
  * success rate
* Last updated timestamp

Auto-refresh via meta refresh or lightweight JS polling.

---

## 8. Data Model

### InstanceConfig

* name: string
* url: string

### InstanceStatus

* name
* url
* healthy: bool
* last_seen: datetime
* error: string
* metrics: dict[str, float]

---

## 9. API / UI (Phase 1)

### Web routes

* `/` → dashboard page

Optional future:

* `/api/status` → JSON summary
* `/instance/{name}` → detailed view
* `/metrics/raw/{name}` → raw scraped metrics

---

## 10. Technology Choices

* Python 3.12+
* FastAPI (web framework)
* httpx (async HTTP client)
* Jinja2 (templates)
* PyYAML (configuration parsing)

No JavaScript framework.

No frontend build step.

---

## 11. Performance Expectations

* Designed for low-to-moderate scale:

  * 1–50 instances
  * polling every 5–30 seconds
* Lightweight CPU usage
* Minimal memory footprint (<100MB typical)

---

## 12. Reliability Requirements

* Individual instance failure must not affect system stability
* Timeouts must be enforced on all HTTP requests
* Partial data must still render dashboard
* System must degrade gracefully

---

## 13. Security Considerations

* No authentication in Phase 1 (assumes trusted network)
* Should be deployed behind:

  * reverse proxy (e.g. nginx, Caddy)
  * or internal-only network interface
* No sensitive data stored by default

Future:

* Basic auth or token-based access
* IP allowlisting

---

## 14. Deployment Model

Single-host deployment:

* Runs as systemd service or Docker container
* Co-located with Anubis proxy server
* Exposed on internal port (e.g. 8000)

---

## 15. Phased Roadmap

### Phase 1 — MVP (current scope)

* config loader
* metrics scraper
* Prometheus parser
* in-memory state
* dashboard page

---

### Phase 2 — Persistence

* SQLite storage
* historical sampling (1m intervals)
* basic graphs

---

### Phase 3 — UI enhancement

* Bootstrap UI
* instance detail pages
* filtering and search
* HTMX live updates

---

### Phase 4 — Alerting

* threshold-based alerts
* webhook integrations
* optional email/Matrix/Discord notifications

---

### Phase 5 — Advanced features

* anomaly detection (basic heuristics)
* per-client breakdown (if exposed by Anubis)
* multi-monitor federation (optional)

---

## 16. Key Design Principle

The system prioritises:

> **clarity over completeness**

It is intentionally opinionated: it shows what an operator needs to know in seconds, not everything that *could* be known.

---

If you want, next step I can turn this into:

* a repo scaffold (all files created)
* or Phase 1 implementation starting from `main.py` + scraper first

Just say which direction you prefer.

