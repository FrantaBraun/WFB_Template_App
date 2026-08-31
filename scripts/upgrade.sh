#!/bin/bash
# upgrade.sh — in-place upgrade of the auth service with automatic rollback
# Run as root. Configuration is read from $(dirname "$0")/deploy.config.sh.
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
die()  { echo -e "${RED}ERROR: $*${NC}" >&2; exit 1; }
info() { echo -e "${GREEN}[upgrade]${NC} $*"; }
step() { echo -e "\n${BOLD}── $* ──${NC}"; }
warn() { echo -e "${YELLOW}WARN: $*${NC}"; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root (sudo $0)"
command -v curl     &>/dev/null || die "curl is required"
command -v python3  &>/dev/null || die "python3 is required"
command -v pg_dump  &>/dev/null || die "pg_dump is required"
command -v psql     &>/dev/null || die "psql is required"

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/deploy.config.sh"
[[ -f "$CONFIG_FILE" ]] || die "Config not found: $CONFIG_FILE"
# shellcheck source=deploy.config.sh.example
source "$CONFIG_FILE"

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${INSTALL_DIR}/backup"
BACKEND_BAK="${BACKUP_DIR}/backend-${DATE}.tar.gz"
FRONTEND_BAK="${BACKUP_DIR}/frontend-${DATE}.tar.gz"
DB_BAK="${BACKUP_DIR}/db-${DATE}.sql.gz"

# ── Helpers ───────────────────────────────────────────────────────────────────

ftp_latest_file() {
    local remote_path="$1" prefix="$2"
    curl -sf --ftp-pasv -u "${FTP_USER}:${FTP_PASS}" \
        "ftp://${FTP_HOST}:${FTP_PORT}${remote_path}/" \
        --list-only \
        | grep "^${prefix}" | sort | tail -1
}

ftp_download() {
    local remote_path="$1" local_file="$2"
    info "  Downloading ftp://${FTP_HOST}${remote_path} …"
    curl -sf --ftp-pasv -u "${FTP_USER}:${FTP_PASS}" \
        "ftp://${FTP_HOST}:${FTP_PORT}${remote_path}" \
        -o "$local_file" || die "FTP download failed: $remote_path"
}

parse_db_url() {
    local env_file="${INSTALL_DIR}/backend/.env"
    [[ -f "$env_file" ]] || die "backend/.env not found."
    local url
    url=$(grep "^DATABASE_URL=" "$env_file" | cut -d= -f2-)
    eval "$(python3 - <<PYEOF
import urllib.parse
url = """$url""".replace("postgresql+asyncpg://", "postgresql://")
p = urllib.parse.urlparse(url)
print(f"DB_USER={p.username}")
print(f"DB_PASS={urllib.parse.unquote(p.password or '')}")
print(f"DB_HOST={p.hostname or 'localhost'}")
print(f"DB_PORT={p.port or 5432}")
print(f"DB_NAME={p.path.lstrip('/')}")
PYEOF
)"
}

# Resolve UPLOADS_DIR out of a preserved .env into an absolute path, the same
# way the running app resolves a relative value: against backend/, which is
# its systemd WorkingDirectory. Fails (prints nothing) if the setting isn't
# present in that .env at all — apps that don't define it are a no-op.
resolve_uploads_dir() {
    local env_file="$1"
    local raw
    raw=$(grep "^UPLOADS_DIR=" "$env_file" | tail -1 | cut -d= -f2-) || true
    [[ -n "$raw" ]] || return 1
    if [[ "$raw" = /* ]]; then
        printf '%s\n' "$raw"
    else
        printf '%s\n' "${INSTALL_DIR}/backend/${raw#./}"
    fi
}

# Copy the resolved uploads dir (if it currently exists) to $1, so it
# survives the backend/ wipe-and-recreate the same way .env does. A no-op
# when UPLOADS_DIR isn't configured or the directory doesn't exist yet.
backup_uploads_dir() {
    [[ -n "${UPLOADS_DIR_RESOLVED:-}" && -d "$UPLOADS_DIR_RESOLVED" ]] || return 0
    cp -a "$UPLOADS_DIR_RESOLVED" "$1"
}

# Restore a directory previously saved by backup_uploads_dir back to its
# resolved location. A no-op when there was nothing to restore.
restore_uploads_dir() {
    [[ -n "${UPLOADS_DIR_RESOLVED:-}" && -d "$1" ]] || return 0
    mkdir -p "$(dirname "$UPLOADS_DIR_RESOLVED")"
    rm -rf "$UPLOADS_DIR_RESOLVED"
    cp -a "$1" "$UPLOADS_DIR_RESOLVED"
}

install_python_deps() {
    local venv="${INSTALL_DIR}/backend/.venv"
    if command -v uv &>/dev/null; then
        uv venv "$venv" --python python3
        if [[ -f "${INSTALL_DIR}/backend/requirements.txt" ]]; then
            uv pip install --python "${venv}/bin/python" -r "${INSTALL_DIR}/backend/requirements.txt"
        else
            uv pip install --python "${venv}/bin/python" "${INSTALL_DIR}/backend/"
        fi
    else
        python3 -m venv "$venv"
        "${venv}/bin/pip" install --upgrade pip -q
        if [[ -f "${INSTALL_DIR}/backend/requirements.txt" ]]; then
            "${venv}/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt" -q
        else
            "${venv}/bin/pip" install "${INSTALL_DIR}/backend/" -q
        fi
    fi
}

rollback() {
    warn "Rolling back …"
    systemctl stop ${APP_SERVICE_NAME} 2>/dev/null || true

    if [[ -f "$BACKEND_BAK" ]]; then
        rm -rf "${INSTALL_DIR}/backend"
        mkdir -p "${INSTALL_DIR}/backend"
        tar -xzf "$BACKEND_BAK" -C "${INSTALL_DIR}"
        info "  backend/ restored from backup."
    fi

    if [[ -f "$FRONTEND_BAK" ]]; then
        rm -rf "${INSTALL_DIR}/frontend"
        mkdir -p "${INSTALL_DIR}/frontend"
        tar -xzf "$FRONTEND_BAK" -C "${INSTALL_DIR}"
        info "  frontend/ restored from backup."
    fi

    if [[ -f "$DB_BAK" ]]; then
        parse_db_url
        info "  Restoring database ${DB_NAME} …"
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${DB_NAME};"
        sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
        PGPASSWORD="$DB_PASS" gunzip -c "$DB_BAK" \
            | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
        info "  Database restored."
    fi

    chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
    cp "${TMP_DIR}/.env.bak" "${INSTALL_DIR}/backend/.env"
    restore_uploads_dir "${TMP_DIR}/uploads.bak"

    systemctl start ${APP_SERVICE_NAME}
    echo -e "${RED}${BOLD}Rollback complete. Service restarted from backup.${NC}"
    exit 1
}

# ── Steps ─────────────────────────────────────────────────────────────────────
CURRENT_DIR="$(pwd)"

step "1/8  Stop service"
systemctl stop ${APP_SERVICE_NAME}
info "${APP_SERVICE_NAME} stopped."

step "2/8  Backup database"
mkdir -p "$BACKUP_DIR"
parse_db_url
info "  pg_dump ${DB_NAME} → ${DB_BAK}"
PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" \
    | gzip > "$DB_BAK"

step "3/8  Backup application files"
info "  backend/ → ${BACKEND_BAK}"
tar -czf "$BACKEND_BAK"  -C "$INSTALL_DIR" backend
info "  frontend/ → ${FRONTEND_BAK}"
tar -czf "$FRONTEND_BAK" -C "$INSTALL_DIR" frontend

step "4/8  Download new archives from FTP"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

BACKEND_FILE=$(ftp_latest_file "$FTP_BACKEND_PATH" "backend-") \
    || die "No backend archive found on FTP."
FRONTEND_FILE=$(ftp_latest_file "$FTP_FRONTEND_PATH" "frontend-") \
    || die "No frontend archive found on FTP."

ftp_download "${FTP_BACKEND_PATH}/${BACKEND_FILE}"   "${TMP_DIR}/backend.zip"
ftp_download "${FTP_FRONTEND_PATH}/${FRONTEND_FILE}" "${TMP_DIR}/frontend.zip"

step "5/8  Extract archives"
# Preserve .env and the uploads dir it points at – neither is shipped in the
# archive, so without this both would be silently wiped on every deploy.
cp "${INSTALL_DIR}/backend/.env" "${TMP_DIR}/.env.bak"
UPLOADS_DIR_RESOLVED="$(resolve_uploads_dir "${INSTALL_DIR}/backend/.env")" || UPLOADS_DIR_RESOLVED=""
backup_uploads_dir "${TMP_DIR}/uploads.bak"

rm -rf "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
mkdir -p "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
unzip -q "${TMP_DIR}/backend.zip"  -d "${INSTALL_DIR}/backend"
unzip -q "${TMP_DIR}/frontend.zip" -d "${INSTALL_DIR}/frontend"

cp "${TMP_DIR}/.env.bak" "${INSTALL_DIR}/backend/.env"
restore_uploads_dir "${TMP_DIR}/uploads.bak"
if [[ -n "$UPLOADS_DIR_RESOLVED" ]]; then
    info "  Uploads dir preserved: ${UPLOADS_DIR_RESOLVED}"
fi

info "Backend:  ${BACKEND_FILE}"
info "Frontend: ${FRONTEND_FILE}"

step "6/8  Update Python dependencies"
install_python_deps

step "7/8  File permissions"
chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
chmod -R o-rwx "${INSTALL_DIR}/backend"

step "8/8  Database migrations + health check"
cd "${INSTALL_DIR}/backend"
.venv/bin/alembic upgrade heads
cd "$INSTALL_DIR"

systemctl start ${APP_SERVICE_NAME}
info "${APP_SERVICE_NAME} started – waiting 8 s …"
sleep 8

if curl -sf "http://127.0.0.1:${BACKEND_PORT}/api/public/version" > /dev/null; then
    info "Health check passed."
    rm -f "$DB_BAK" "$BACKEND_BAK" "$FRONTEND_BAK"
    info "Backups removed."
    echo -e "\n${GREEN}${BOLD}Upgrade complete!${NC}"
    echo -e "  Service:  systemctl status ${APP_SERVICE_NAME}"
    echo -e "  Logs:     journalctl -u ${APP_SERVICE_NAME} -f"
else
    warn "Health check failed at http://127.0.0.1:${BACKEND_PORT}/api/public/version"
    rollback
fi
