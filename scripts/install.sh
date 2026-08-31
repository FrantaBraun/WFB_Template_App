#!/bin/bash
# install.sh — first-time installation of the auth service
# Run as root from any directory. Configuration is read from
# $(dirname "$0")/deploy.config.sh (copy from deploy.config.sh.example).
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
die()  { echo -e "${RED}ERROR: $*${NC}" >&2; exit 1; }
info() { echo -e "${GREEN}[install]${NC} $*"; }
step() { echo -e "\n${BOLD}── $* ──${NC}"; }
warn() { echo -e "${YELLOW}WARN: $*${NC}"; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root (sudo $0)"
command -v curl     &>/dev/null || die "curl is required"
command -v python3  &>/dev/null || die "python3 is required"
command -v psql     &>/dev/null || die "psql is required"
command -v nginx    &>/dev/null || die "nginx is required"
command -v systemctl &>/dev/null || die "systemd is required"

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/deploy.config.sh"
[[ -f "$CONFIG_FILE" ]] || die "Config not found: $CONFIG_FILE\nCopy deploy.config.sh.example and fill in your values."
# shellcheck source=deploy.config.sh.example
source "$CONFIG_FILE"

# ── Helpers ───────────────────────────────────────────────────────────────────

# Returns the name of the latest file on FTP matching a prefix (sorted lexicographically).
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

# Parse DATABASE_URL from backend/.env into DB_USER DB_PASS DB_HOST DB_PORT DB_NAME.
parse_db_url() {
    local env_file="${INSTALL_DIR}/backend/.env"
    [[ -f "$env_file" ]] || die "backend/.env not found – place it in ${INSTALL_DIR}/backend/ before running this step."
    local url
    url=$(grep "^DATABASE_URL=" "$env_file" | cut -d= -f2-)
    eval "$(python3 - <<PYEOF
import urllib.parse, sys
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

install_python_deps() {
    local venv="${INSTALL_DIR}/backend/.venv"
    if command -v uv &>/dev/null; then
        info "  Using uv …"
        uv venv "$venv" --python python3
        if [[ -f "${INSTALL_DIR}/backend/requirements.txt" ]]; then
            uv pip install --python "${venv}/bin/python" -r "${INSTALL_DIR}/backend/requirements.txt"
        else
            uv pip install --python "${venv}/bin/python" "${INSTALL_DIR}/backend/"
        fi
    else
        info "  Using pip …"
        python3 -m venv "$venv"
        "${venv}/bin/pip" install --upgrade pip -q
        if [[ -f "${INSTALL_DIR}/backend/requirements.txt" ]]; then
            "${venv}/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt" -q
        else
            "${venv}/bin/pip" install "${INSTALL_DIR}/backend/" -q
        fi
    fi
}

# ── Steps ─────────────────────────────────────────────────────────────────────

CURRENT_DIR="$(pwd)"

step "1/10  System user"
if ! getent group "$APP_GROUP" &>/dev/null; then
    groupadd --system "$APP_GROUP"
    info "Group $APP_GROUP created."
fi
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false --gid "$APP_GROUP" "$APP_USER"
    info "User $APP_USER created."
else
    warn "User $APP_USER already exists – skipping."
fi

step "2/10  Download archives from FTP"
mkdir -p "$INSTALL_DIR"

cd "$INSTALL_DIR"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

BACKEND_FILE=$(ftp_latest_file "$FTP_BACKEND_PATH" "backend-") \
    || die "No backend archive found on FTP under ${FTP_BACKEND_PATH}"
FRONTEND_FILE=$(ftp_latest_file "$FTP_FRONTEND_PATH" "frontend-") \
    || die "No frontend archive found on FTP under ${FTP_FRONTEND_PATH}"

ftp_download "${FTP_BACKEND_PATH}/${BACKEND_FILE}"  "${TMP_DIR}/backend.zip"
ftp_download "${FTP_FRONTEND_PATH}/${FRONTEND_FILE}" "${TMP_DIR}/frontend.zip"

step "3/10  Extract archives"
# No uploads dir to preserve on a first install (nothing has been uploaded
# yet); an app that defines UPLOADS_DIR creates it itself on first boot.
# upgrade.sh is what carries an existing uploads dir across later deploys.
rm -rf "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
mkdir -p "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
unzip -q "${TMP_DIR}/backend.zip"  -d "${INSTALL_DIR}/backend"
unzip -q "${TMP_DIR}/frontend.zip" -d "${INSTALL_DIR}/frontend"
info "Backend:  ${BACKEND_FILE}"
info "Frontend: ${FRONTEND_FILE}"

cp "${CURRENT_DIR}/.env" "${INSTALL_DIR}/backend/.env" \
    || die "Copy .env to ${INSTALL_DIR}/backend/.env before running install."

# Disable CORS in production (frontend and backend are served from the same domain)
sed -i -e 's/CORS_ENABLED\=true/CORS_ENABLED=false/g' "${CURRENT_DIR}/.env"
sed -i -e 's/GOOGLE_REDIRECT_URI\=http:\/\/localhost:8000\/auth\/google\/callback/GOOGLE_REDIRECT_URI\=https:\/\/auth.withfbraun.com\/auth\/google\/callback/g' "${CURRENT_DIR}/.env"
sed -i -e 's/APP_BASE_URL\=http:\/\/localhost:8000/APP_BASE_URL\=https:\/\/auth.withfbraun.com/g' "${CURRENT_DIR}/.env"
sed -i -e 's/FRONTEND_URL\=http:\/\/localhost:5174/FRONTEND_URL\=https:\/\/auth.withfbraun.com/g' "${CURRENT_DIR}/.env"

step "4/10  PostgreSQL database"
[[ -f "${INSTALL_DIR}/backend/.env" ]] \
    || die "Place backend/.env in ${INSTALL_DIR}/backend/ before running install."
parse_db_url
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}';
        RAISE NOTICE 'Role ${DB_USER} created.';
    ELSE
        RAISE NOTICE 'Role ${DB_USER} already exists.';
    END IF;
END
\$\$;
SELECT 'CREATE DATABASE' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = '${DB_NAME}'
)\gexec
SQL
# The SELECT … \gexec trick creates the DB only if it doesn't exist.
# Grant is idempotent.
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
info "Database: ${DB_NAME}, owner: ${DB_USER}"

step "5/10  Python virtualenv + dependencies"
install_python_deps

step "6/10  Database migrations"
cd "${INSTALL_DIR}/backend"
.venv/bin/alembic upgrade heads
cd "$INSTALL_DIR"

step "7/10  File permissions"
chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend"
chmod -R o-rwx "${INSTALL_DIR}/backend"     # no world access on backend
info "Permissions set for ${APP_USER}:${APP_GROUP}"

step "8/10  systemd service"
cat > /etc/systemd/system/${APP_SERVICE_NAME} <<SERVICE
[Unit]
Description=${APP_SERVICE_DESC}
After=network.target postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}/backend
ExecStart=${INSTALL_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable ${APP_SERVICE_NAME}
info "${APP_SERVICE_NAME} installed and enabled."

step "9/10  nginx – HTTP-only config (pre-certificate)"
NGINX_CONF="${NGINX_SITES_CONF}/${DOMAIN}.conf"
# Write HTTP-only config first so nginx starts cleanly and certbot can complete
# the HTTP-01 ACME challenge. The SSL server block is added after the cert exists.
cat > "$NGINX_CONF" <<NGINX
# ${DOMAIN} – generated by install.sh (HTTP-only, pre-certificate)
server {
    listen      80;
    listen      [::]:80;
    server_name ${DOMAIN};

    # ACME challenge for certbot
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect everything else to HTTPS once cert is in place
    location / {
        return 301 https://\$host\$request_uri;
    }
}
NGINX

nginx -t || die "nginx config test failed."
nginx -s reload 2>/dev/null || nginx
info "nginx running with HTTP-only config."

step "10/10  TLS certificate + full nginx config + start"
# Register domain for certbot
grep -qxF "$DOMAIN" "$CERTBOT_DOMAINS_FILE" 2>/dev/null \
    || echo "$DOMAIN" >> "$CERTBOT_DOMAINS_FILE"
info "Domain added to $CERTBOT_DOMAINS_FILE"

if [[ -x "$CERTBOT_REFRESH_SCRIPT" ]]; then
    info "Running $CERTBOT_REFRESH_SCRIPT …"
    "$CERTBOT_REFRESH_SCRIPT"
else
    warn "Certbot script not found or not executable: $CERTBOT_REFRESH_SCRIPT"
    warn "Generate certificate manually (e.g. certbot certonly --standalone -d ${DOMAIN}),"
    warn "then re-run this script or write the SSL nginx config manually."
    exit 0
fi

# Certificate exists — write the full HTTPS config
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
[[ -f "${CERT_DIR}/fullchain.pem" ]] || die "Certificate not found in ${CERT_DIR} after certbot run."

cat > "$NGINX_CONF" <<NGINX
# ${DOMAIN} – generated by install.sh
server {
    listen      80;
    listen      [::]:80;
    server_name ${DOMAIN};
    return      301 https://\$host\$request_uri;
}

server {
    listen      443 ssl http2;
    listen      [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Access-Control-Allow-Origin "*" always;

    # Backend – API and OAuth routes
    location ~ ^/(api|auth|health)(/|\$) {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    # Frontend SPA
    location / {
        root      ${INSTALL_DIR}/frontend;
        index     index.html;
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX

nginx -t || die "nginx SSL config test failed."
nginx -s reload
info "nginx running with full HTTPS config."

systemctl start ${APP_SERVICE_NAME}

echo -e "\n${GREEN}${BOLD}Installation complete!${NC}"
echo -e "  Service:  systemctl status ${APP_SERVICE_NAME}"
echo -e "  Logs:     journalctl -u ${APP_SERVICE_NAME} -f"
echo -e "  URL:      https://${DOMAIN}"
