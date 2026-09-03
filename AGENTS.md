# AGENTS.md

## Overview

This repository contains tools for managing and monitoring Anubis bot-protection setups on Koozali infrastructure. It includes scripts for setting up Anubis services and testing their behavior, as well as a standalone web dashboard for observing multiple Anubis instances.

## Key Commands

- `sudo ./make-anubis-2.sh <name> <port>`: Set up an Anubis service with specified name and port.
- `python3 anubis_test_v2.py`: Run end-to-end tests against deployed setup.
- `cd anubis-monitor && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`: Run the Anubis Monitor dashboard.

## Structure

- `make-anubis-2.sh`: Sets up Anubis service configuration and systemd unit.
- `anubis_test_v2.py`: Tests deployed setup with HTTP requests and generates CSV reports.
- `anubis-monitor/`: Standalone web dashboard for monitoring Anubis instances:
  - `app/main.py`: FastAPI application serving the dashboard.
  - `app/config.py`: Configuration loading logic.
  - `app/history.py`: SQLite-based history tracking.
  - `app/parser.py`: Prometheus text parsing logic.
  - `app/state.py`: Application state management.

## Notes

- The Anubis binary must be installed at `/usr/sbin/anubis`.
- Anubis Monitor runs on port 8000 by default.
- Configuration for Anubis Monitor is in `anubis-monitor/config.yaml`.
- Test script writes results to `anubis_test_results.csv`.