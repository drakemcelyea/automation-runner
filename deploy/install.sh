#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

OPEN_FIREWALL=false
CREATE_ADMIN=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --open-firewall) OPEN_FIREWALL=true ;;
        --admin) shift; CREATE_ADMIN="${1:-}" ;;
        -h|--help)
            echo "Usage: sudo ./deploy/install.sh [--open-firewall] [--admin USERNAME]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

require_root
for cmd in podman systemctl loginctl openssl python3; do
    command -v "$cmd" >/dev/null || { echo "Missing required command: $cmd" >&2; exit 1; }
done

if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

# Rootless Podman needs subordinate UID/GID ranges. Allocate one if missing.
allocate_subid() {
    local file="$1" type="$2"
    if grep -q "^${APP_USER}:" "$file" 2>/dev/null; then
        return
    fi
    local start
    start=$(awk -F: '
        BEGIN { max=100000 }
        NF>=3 { e=$2+$3; if(e>max) max=e }
        END {
            block=65536;
            s=int((max+block-1)/block)*block;
            if(s<100000) s=100000;
            print s
        }' "$file" 2>/dev/null || echo 100000)
    if [[ "$type" == uid ]]; then
        usermod --add-subuids "${start}-$((start+65535))" "$APP_USER"
    else
        usermod --add-subgids "${start}-$((start+65535))" "$APP_USER"
    fi
}
allocate_subid /etc/subuid uid
allocate_subid /etc/subgid gid

ensure_user_manager

mkdir -p "$APP_DIR" "$CONFIG_DIR" \
    "$DATA_DIR/projects/demo/project" "$DATA_DIR/runs" "$DATA_DIR/settings" \
    "$DATA_DIR/vault" "$DATA_DIR/config" "$DATA_DIR/home/.ansible/tmp" \
    "$DATA_DIR/.config/containers/systemd" "$DATA_DIR/backups"

touch "$DATA_DIR/inventory.json" "$DATA_DIR/runs.json" "$DATA_DIR/settings.json"

# Preserve an existing source install before replacing it.
if [[ -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" && "$SOURCE_ROOT" != "$APP_DIR" ]]; then
    backup="${APP_DIR}.previous.$(date +%Y%m%d%H%M%S)"
    cp -a "$APP_DIR" "$backup"
    echo "Previous source copied to $backup"
    rm -rf "$APP_DIR"/* "$APP_DIR"/.[!.]* "$APP_DIR"/..?* 2>/dev/null || true
fi

if [[ "$SOURCE_ROOT" != "$APP_DIR" ]]; then
    cp -a "$SOURCE_ROOT"/. "$APP_DIR"/
fi

chown -R root:root "$APP_DIR"
chmod -R a+rX "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$DATA_DIR"

ENV_FILE="$CONFIG_DIR/automation-runner.env"
if [[ ! -f "$ENV_FILE" ]]; then
    cp "$APP_DIR/deploy/automation-runner.env.example" "$ENV_FILE"
    secret=$(openssl rand -hex 32)
    sed -i "s/^SESSION_SECRET=.*/SESSION_SECRET=${secret}/" "$ENV_FILE"
    chmod 0640 "$ENV_FILE"
    chown root:"$APP_USER" "$ENV_FILE"
    echo "Created $ENV_FILE with a generated session secret."
else
    echo "Preserving existing $ENV_FILE"
fi

cp "$APP_DIR/deploy/automation-runner.container" \
   "$DATA_DIR/.config/containers/systemd/automation-runner.container"
chown "$APP_USER":"$APP_USER" \
   "$DATA_DIR/.config/containers/systemd/automation-runner.container"

# Reset Podman user namespace mappings after subid changes, then build.
as_app podman system migrate >/dev/null 2>&1 || true
as_app podman build --no-cache --format docker \
    -t "$IMAGE" \
    -f "$APP_DIR/container/backend/ContainerFile" \
    "$APP_DIR"

user_systemctl daemon-reload
user_systemctl reset-failed "$SERVICE" >/dev/null 2>&1 || true
user_systemctl start "$SERVICE"

if $OPEN_FIREWALL && command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port=8080/tcp
    firewall-cmd --reload
fi

sleep 2
user_systemctl --no-pager --full status "$SERVICE" || true

if [[ -n "$CREATE_ADMIN" ]]; then
    echo
    echo "Creating administrator '$CREATE_ADMIN'..."
    "$APP_DIR/deploy/create-admin.sh" "$CREATE_ADMIN"
fi

echo
echo "Automation Runner installed."
echo "UI: http://<host>:8080/ui"
echo "Status: sudo $APP_DIR/deploy/status.sh"
if [[ -z "$CREATE_ADMIN" ]]; then
    echo "Create the first admin: sudo $APP_DIR/deploy/create-admin.sh <username>"
fi
