#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <name> <port> [--target <url>] [--difficulty <1-10>] [--monitor-url <url>] [--monitor-refresh <seconds>]"
  exit 1
}

NAME="${1:-}"
PORT="${2:-}"

[[ -z "${NAME}" || -z "${PORT}" ]] && usage

shift 2

TARGET="https://mail.bjsystems.co.uk:443"
DIFFICULTY="3"
MONITOR_URL="http://127.0.0.1:8000"
MONITOR_REFRESH="10"
MONITOR_USER="root" #"anubis-monitor"
MONITOR_GROUP="root" #"anubis-monitor"
MONITOR_DIR="/root/Anubis-Support/anubis-monitor"
MONITOR_VENV="${MONITOR_DIR}/.venv"
MONITOR_SERVICE="/etc/systemd/system/anubis-monitor.service"
MONITOR_CONFIG="${MONITOR_DIR}/config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -lt 2 ]] && usage
      TARGET="$2"
      shift 2
      ;;
    --difficulty)
      [[ $# -lt 2 ]] && usage
      DIFFICULTY="$2"
      shift 2
      ;;
    --monitor-url)
      [[ $# -lt 2 ]] && usage
      MONITOR_URL="$2"
      shift 2
      ;;
    --monitor-refresh)
      [[ $# -lt 2 ]] && usage
      MONITOR_REFRESH="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Error: port must be 1-65535"
  exit 1
fi

if ! [[ "$DIFFICULTY" =~ ^[0-9]+$ ]] || (( DIFFICULTY < 1 || DIFFICULTY > 10 )); then
  echo "Error: difficulty must be 1-10"
  exit 1
fi

if ! [[ "$MONITOR_REFRESH" =~ ^[0-9]+$ ]] || (( MONITOR_REFRESH < 1 )); then
  echo "Error: monitor refresh must be >= 1"
  exit 1
fi

BIN="/usr/sbin/anubis"
CONF_DIR="/etc/anubis"
ENV_FILE="${CONF_DIR}/${NAME}.env"
POLICY_FILE="${CONF_DIR}/${NAME}.botPolicies.yaml"
UNIT_FILE="/etc/systemd/system/${NAME}-anubis.service"
BIND_ADDR="0.0.0.0:${PORT}"
METRICS_PORT=$((PORT + 10000))

if (( METRICS_PORT > 65535 )); then
  echo "Error: metrics port would exceed 65535"
  exit 1
fi

if [[ ! -x "$BIN" ]]; then
  echo "Error: $BIN not found or not executable"
  exit 1
fi

if ! id anubis >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -d /nonexistent anubis
fi

if ! id "${MONITOR_USER}" >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -d "${MONITOR_DIR}" "${MONITOR_USER}"
fi

mkdir -p "$CONF_DIR"
chmod 0750 "$CONF_DIR"
chown anubis:anubis "$CONF_DIR"

cat > "$POLICY_FILE" <<'EOF'
bots:
  # Block obviously malicious traffic
  - import: (data)/bots/_deny-pathological.yaml

  # Block aggressive AI crawlers
  - import: (data)/meta/ai-block-aggressive.yaml

  # Allow well-behaved search engines
  - import: (data)/crawlers/_allow-good.yaml

  # Explicitly allow normal browsers
  - name: browser
    user_agent_regex: "(?i)(Mozilla|Chrome|Chromium|Firefox|Safari|Edg)"
    action: ALLOW

  # Everything else must solve the JavaScript challenge
  - name: unknown-clients
    user_agent_regex: ".*"
    action: CHALLENGE

store:
  backend: bbolt
  parameters:
    path: /var/lib/anubis/anubis.bdb

status_codes:
  CHALLENGE: 200
  DENY: 403

logging:
  sink: stdio
  level: INFO
EOF

cat > "$ENV_FILE" <<EOF
BIND=$BIND_ADDR
BIND_NETWORK=tcp
DIFFICULTY=$DIFFICULTY
METRICS_BIND=127.0.0.1:$METRICS_PORT
METRICS_BIND_NETWORK=tcp
POLICY_FNAME=$POLICY_FILE
TARGET=$TARGET
BASE_PREFIX=/${NAME}
SERVE_ROBOTS_TXT=0
EOF

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Anubis for ${NAME}
After=network.target

[Service]
Type=simple
User=anubis
Group=anubis
WorkingDirectory=/etc/anubis
EnvironmentFile=$ENV_FILE
ExecStart=$BIN
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

mkdir -p "$MONITOR_DIR"
if [[ ! -f "${MONITOR_CONFIG}" ]]; then
  cat > "$MONITOR_CONFIG" <<EOF
refresh: ${MONITOR_REFRESH}

instances:
  - name: ${NAME}
    url: http://127.0.0.1:${METRICS_PORT}/metrics
EOF
elif grep -qE "^[[:space:]]*name:[[:space:]]*${NAME}[[:space:]]*$" "$MONITOR_CONFIG"; then
  python3 - "$MONITOR_CONFIG" "$NAME" "$METRICS_PORT" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
name = sys.argv[2]
port = sys.argv[3]
lines = path.read_text().splitlines()
out = []
i = 0
replaced = False
while i < len(lines):
    line = lines[i]
    if line.strip() == f"- name: {name}":
        out.append(line)
        i += 1
        while i < len(lines) and lines[i].startswith("    "):
            i += 1
        out.append(f"    url: http://127.0.0.1:{port}/metrics")
        replaced = True
        continue
    out.append(line)
    i += 1
if not replaced:
    out = lines
path.write_text("\n".join(out) + "\n")
PY
else
  cat >> "$MONITOR_CONFIG" <<EOF

  - name: ${NAME}
    url: http://127.0.0.1:${METRICS_PORT}/metrics
EOF
fi

chown anubis:anubis "$ENV_FILE" "$POLICY_FILE"
chmod 0640 "$ENV_FILE" "$POLICY_FILE"
chmod 0644 "$UNIT_FILE"

cat > "$MONITOR_SERVICE" <<EOF
[Unit]
Description=Anubis Monitor
After=network.target

[Service]
Type=simple
User=${MONITOR_USER}
Group=${MONITOR_GROUP}
WorkingDirectory=${MONITOR_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/uvicorn --app-dir ${MONITOR_DIR} app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chown "${MONITOR_USER}:${MONITOR_USER}" "$MONITOR_SERVICE" 2>/dev/null || true
chmod 0644 "$MONITOR_SERVICE"

systemctl daemon-reload
systemctl enable --now "${NAME}-anubis.service"
systemctl restart "${NAME}-anubis.service"

systemctl enable --now anubis-monitor.service
systemctl restart anubis-monitor.service

if systemctl is-active --quiet "${NAME}-anubis.service"; then
  echo "Started/restarted ${NAME}-anubis.service"
else
  echo "Error: ${NAME}-anubis.service failed to start"
  systemctl --no-pager -l status "${NAME}-anubis.service" || true
  exit 1
fi

if systemctl is-active --quiet anubis-monitor.service; then
  echo "Started/restarted anubis-monitor.service"
else
  echo "Error: anubis-monitor.service failed to start"
  systemctl --no-pager -l status anubis-monitor.service || true
  exit 1
fi

echo "Monitor config updated at ${MONITOR_CONFIG}"