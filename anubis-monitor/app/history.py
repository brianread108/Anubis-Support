import sqlite3
import time
from datetime import datetime
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    timestamp INTEGER NOT NULL,
    instance TEXT NOT NULL,

    decisions REAL NOT NULL,
    allow_count REAL NOT NULL,
    challenge_count REAL NOT NULL,
    deny_count REAL NOT NULL,

    challenges_issued REAL NOT NULL,
    proxied_total REAL NOT NULL,

    resident_memory_bytes REAL,
    goroutines REAL,
    open_fds REAL,

    PRIMARY KEY (timestamp, instance)
);

CREATE INDEX IF NOT EXISTS samples_instance_timestamp
ON samples (instance, timestamp);
"""


def _connection(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def initialise(db_path):
    with _connection(db_path) as connection:
        connection.executescript(SCHEMA)


def save_sample(db_path, instance):
    if not instance.healthy:
        return

    summary = instance.summary or {}
    derived = instance.derived or {}
    totals = derived.get("totals", {})
    runtime = derived.get("runtime", {})

    timestamp = int(time.time())

    with _connection(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO samples (
                timestamp, instance,
                decisions, allow_count, challenge_count, deny_count,
                challenges_issued, proxied_total,
                resident_memory_bytes, goroutines, open_fds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                instance.name,
                derived.get("total_decisions", 0),
                totals.get("ALLOW", 0),
                totals.get("CHALLENGE", 0),
                totals.get("DENY", 0),
                summary.get("challenge_issued", 0),
                summary.get("proxied_total", 0),
                runtime.get("process_resident_memory_bytes"),
                runtime.get("go_goroutines"),
                runtime.get("process_open_fds"),
            ),
        )


def prune_history(db_path, days):
    cutoff = int(time.time()) - (days * 86400)

    with _connection(db_path) as connection:
        connection.execute(
            "DELETE FROM samples WHERE timestamp < ?",
            (cutoff,),
        )


def history_rows(db_path, instance_name, hours, bucket_seconds):
    cutoff = int(time.time()) - (hours * 3600)

    with _connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT s.*
            FROM samples AS s
            JOIN (
                SELECT
                    instance,
                    (timestamp / ?) * ? AS bucket,
                    MAX(timestamp) AS latest_timestamp
                FROM samples
                WHERE instance = ? AND timestamp >= ?
                GROUP BY instance, bucket
            ) AS buckets
              ON s.instance = buckets.instance
             AND s.timestamp = buckets.latest_timestamp
            WHERE s.instance = ?
            ORDER BY s.timestamp
            """,
            (
                bucket_seconds,
                bucket_seconds,
                instance_name,
                cutoff,
                instance_name,
            ),
        ).fetchall()

    output = []

    for row in rows:
        local_time = datetime.fromtimestamp(row["timestamp"]).astimezone()

        output.append({
            "time": local_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "timestamp": row["timestamp"],
            "decisions": row["decisions"],
            "allow": row["allow_count"],
            "challenge": row["challenge_count"],
            "deny": row["deny_count"],
            "challenges_issued": row["challenges_issued"],
            "proxied": row["proxied_total"],
            "memory": row["resident_memory_bytes"],
            "goroutines": row["goroutines"],
            "open_fds": row["open_fds"],
        })

    return output

def period_delta(rows, field):
    """Sum the true increase in a cumulative counter across the window.

    Prometheus counters reset to zero whenever the scraped Anubis process
    restarts. A naive ``last - first`` comparison across the whole window
    silently discards everything accumulated before a mid-window restart
    (it looks like the totals "disappeared"). Instead we walk consecutive
    samples and sum each incremental step, treating any decrease as a
    counter reset: the post-reset sample's own value is the amount
    accumulated since the restart, so it is added in full rather than
    subtracted from the previous (pre-restart) value.
    """
    if len(rows) < 2:
        return 0

    total = 0.0
    previous = rows[0].get(field) or 0

    for row in rows[1:]:
        current = row.get(field) or 0
        delta = current - previous

        # A drop means the counter was reset by an Anubis restart between
        # these two samples; `current` is everything accrued since then.
        total += current if delta < 0 else delta
        previous = current

    return total
