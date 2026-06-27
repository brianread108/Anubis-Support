#!/usr/bin/env python3
"""
Anubis End-to-End Test Suite v2

Improvements:
- Body-based assertions (contains / not-contains)
- Larger response capture (4096 bytes)
- Better distinction between origin vs challenge pages
- Server header capture
- More robust probe test
- Improved PASS/FAIL diagnostics
"""

import csv
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import http.client
import html

# ============================================================
# Config
# ============================================================

OUT_CSV = "anubis_test_results.csv"

TIMEOUT = 10
RETRIES = 2
BODY_PREVIEW_LIMIT = 4096

ANUBIS_HOST = "192.168.2.165"
ANUBIS_PORT = 3002

PUBLIC_BASE_URL = "https://mail.bjsystems.co.uk"

# ============================================================
# Test definitions
# ============================================================

TESTS = [
    {
        "name": "anubis_probe",
        "url": f"http://{ANUBIS_HOST}:{ANUBIS_PORT}/",
        "headers": {
            "Host": "mail.bjsystems.co.uk",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
        },
        "expect_status": [200, 500],
    },
    {
        "name": "public_homepage",
        "url": f"{PUBLIC_BASE_URL}/",
        "headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "expect_status": [200],
        "reject_body_contains": [
            "not a bot"
        ],
    },
    {
        "name": "allow_browser",
        "url": f"{PUBLIC_BASE_URL}/mesdb/",
        "headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "expect_status": [200],
        "reject_body_contains": [
            "not a bot"
        ],
    },
    {
        "name": "challenge_ai",
        "url": f"{PUBLIC_BASE_URL}/mesdb/",
        "headers": {
            "User-Agent": "GPTBot/1.0"
        },
        "expect_status": [200, 403],
		"expect_body_contains" : [
			"Access Denied",
			"anubis",
		]
    },
    {
        "name": "challenge_scraper",
        "url": f"{PUBLIC_BASE_URL}/mesdb/",
        "headers": {
            "User-Agent": "SomeBadScraper/0.1"
        },
        "expect_status": [200, 403],
		"expect_body_contains" : [
			"not a bot",
			"anubis",
		]
    },
    {
        "name": "bad_path",
        "url": f"{PUBLIC_BASE_URL}/definitely-does-not-exist/",
        "headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "expect_status": [404],
    },
]

# ============================================================
# Utilities
# ============================================================

def ts():
    return datetime.now(timezone.utc).isoformat()


def create_conn(parsed):
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=TIMEOUT,
            context=ssl.create_default_context(),
        )
    return http.client.HTTPConnection(
        parsed.hostname,
        parsed.port or 80,
        timeout=TIMEOUT,
    )


def make_request(url, headers):
    parsed = urlparse(url)
    start = time.monotonic()

    try:
        conn = create_conn(parsed)

        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()

        elapsed = round((time.monotonic() - start) * 1000)

        headers_out = {k.lower(): v for k, v in resp.getheaders()}

        return {
            "status": resp.status,
            "reason": resp.reason,
            "headers": headers_out,
            "body": body[:BODY_PREVIEW_LIMIT].decode(errors="replace"),
            "len": len(body),
            "ms": elapsed,
            "error": None,
        }

    except Exception as e:
        return {
            "status": None,
            "reason": "",
            "headers": {},
            "body": "",
            "len": 0,
            "ms": None,
            "error": str(e),
        }


def evaluate(test, result):
    if result["status"] is None:
        return False, "request_failed"

    if result["status"] not in test.get("expect_status", []):
        return False, "status_mismatch"

    body = html.unescape(result["body"])

    for s in test.get("expect_body_contains", []):
        if s not in body:
            return False, f"missing_expected_body:{s}"

    for s in test.get("reject_body_contains", []):
        if s in body:
            return False, f"unexpected_body:{s}"

    return True, "ok"

def run_test(test, ts_run):
    result = make_request(test["url"], test.get("headers", {}))

    passed, reason = evaluate(test, result)

    h = result["headers"]

    return {
        "time": ts_run,
        "test": test["name"],
        "url": test["url"],
        "status": result["status"],
        "ms": result["ms"],
        "len": result["len"],
        "server": h.get("server", ""),
        "anubis_action": h.get("x-anubis-action", ""),
        "anubis_rule": h.get("x-anubis-rule", ""),
        "anubis_status": h.get("x-anubis-status", ""),
        "passed": passed,
        "reason": reason,
        "error": result["error"],
        "body": result["body"],
    }


def write(rows):
    fields = [
        "time","test","url","status","ms","len","server",
        "anubis_action","anubis_rule","anubis_status",
        "passed","reason","error","body"
    ]

    new = not Path(OUT_CSV).exists()

    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    t = ts()
    print("Starting:", t)

    rows = []

    for test in TESTS:
        r = run_test(test, t)
        rows.append(r)

        status = r["status"] if r["status"] is not None else "ERR"
        mark = "PASS" if r["passed"] else "FAIL"

        print(f"[{mark}] {r['test']} status={status} ms={r['ms']} reason={r['reason']}")

        if not r["passed"] and r["body"]:
            print("  Body:", r["body"][:99999999])

        time.sleep(0.2)

    write(rows)

    passed = sum(1 for r in rows if r["passed"])

    print(f"\nSummary: {passed}/{len(rows)} passed")
    print("CSV:", OUT_CSV)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
