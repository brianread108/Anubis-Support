#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <name> <port> [--target <url>] [--difficulty <1-10>]"
  exit 1
}

NAME="${1:-}"
PORT="${2:-}"

[[ -z "${NAME}" || -z "${PORT}" ]] && usage

shift 2

TARGET="https://mail.bjsystems.co.uk:443"
DIFFICULTY="3"

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
  level: DEBUG
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

chown anubis:anubis "$ENV_FILE" "$POLICY_FILE"
chmod 0640 "$ENV_FILE" "$POLICY_FILE"
chmod 0644 "$UNIT_FILE"

systemctl daemon-reload
systemctl enable --now "${NAME}-anubis.service"

echo "Created and started ${NAME}-anubis.service"