#!/usr/bin/env bash
#
# install.sh -- dependency-checking installer for the Image Storage Demo.
#
# Designed for Ubuntu Server 24.04 LTS. For each required dependency it
# checks whether it is already present and only installs what's missing,
# so the script is safe to re-run. Must be run with sudo/root for the
# system package steps; the Python virtualenv steps run as the invoking
# user.
#
# Usage:
#   chmod +x install.sh
#   sudo ./install.sh
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10
VENV_DIR="${PROJECT_DIR}/venv"

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[install][warn]\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31m[install][error]\033[0m %s\n' "$1" >&2; }

require_root_for_apt() {
  if [[ "${EUID}" -ne 0 ]]; then
    err "This step needs root to install system packages. Re-run with: sudo ./install.sh"
    exit 1
  fi
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

apt_install_if_missing() {
  # apt_install_if_missing <check-command> <apt-package> [<apt-package> ...]
  local check_cmd="$1"; shift
  local packages=("$@")
  if command_exists "${check_cmd}"; then
    log "'${check_cmd}' already present, skipping (${packages[*]})."
    return 0
  fi
  require_root_for_apt
  log "Installing missing dependency: ${packages[*]}"
  apt-get install -y "${packages[@]}"
}

dpkg_package_installed() {
  dpkg -s "$1" >/dev/null 2>&1
}

main() {
  log "Detecting OS..."
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log "Detected: ${PRETTY_NAME:-unknown}"
    if [[ "${ID:-}" != "ubuntu" ]]; then
      warn "This script targets Ubuntu Server 24.04 LTS; detected ID='${ID:-unknown}'. Continuing anyway."
    fi
  else
    warn "/etc/os-release not found; cannot confirm this is Ubuntu. Continuing anyway."
  fi

  log "Checking core build/runtime dependencies..."
  local need_apt_update=0
  for check in python3 python3-venv python3-pip mysql apache2ctl git; do
    if ! command_exists "${check}" && ! dpkg_package_installed "${check}"; then
      need_apt_update=1
      break
    fi
  done
  if [[ "${need_apt_update}" -eq 1 ]]; then
    require_root_for_apt
    log "Refreshing apt package index..."
    apt-get update -y
  fi

  # --- Python 3 + venv + pip ------------------------------------------
  apt_install_if_missing python3 python3
  apt_install_if_missing pip3 python3-pip
  if ! python3 -c "import venv" >/dev/null 2>&1; then
    require_root_for_apt
    log "Installing python3-venv..."
    apt-get install -y python3-venv
  else
    log "'python3 -m venv' already available, skipping."
  fi

  local py_major py_minor
  py_major="$(python3 -c 'import sys; print(sys.version_info[0])')"
  py_minor="$(python3 -c 'import sys; print(sys.version_info[1])')"
  if (( py_major < PYTHON_MIN_MAJOR || (py_major == PYTHON_MIN_MAJOR && py_minor < PYTHON_MIN_MINOR) )); then
    warn "Detected Python ${py_major}.${py_minor}; 3.12+ is recommended for production. Continuing."
  else
    log "Python ${py_major}.${py_minor} OK."
  fi

  # --- Pillow build dependencies ---------------------------------------
  log "Ensuring image library headers for Pillow (libjpeg, zlib, libwebp)..."
  local pillow_deps=(libjpeg-dev zlib1g-dev libwebp-dev)
  local missing_pillow_deps=()
  for pkg in "${pillow_deps[@]}"; do
    dpkg_package_installed "${pkg}" || missing_pillow_deps+=("${pkg}")
  done
  if [[ "${#missing_pillow_deps[@]}" -gt 0 ]]; then
    require_root_for_apt
    apt-get install -y "${missing_pillow_deps[@]}"
  else
    log "Pillow build dependencies already present, skipping."
  fi

  # --- MySQL Server 8 ----------------------------------------------------
  if command_exists mysql; then
    log "MySQL client already present, skipping mysql-server install."
  else
    require_root_for_apt
    log "Installing mysql-server..."
    apt-get install -y mysql-server
    systemctl enable --now mysql
  fi

  # --- Apache2 + mod_wsgi -----------------------------------------------
  apt_install_if_missing apache2ctl apache2
  if dpkg_package_installed libapache2-mod-wsgi-py3; then
    log "libapache2-mod-wsgi-py3 already present, skipping."
  else
    require_root_for_apt
    log "Installing libapache2-mod-wsgi-py3..."
    apt-get install -y libapache2-mod-wsgi-py3
  fi

  # --- Git -----------------------------------------------------------
  apt_install_if_missing git git

  # --- Python virtual environment + requirements ------------------------
  if [[ -d "${VENV_DIR}" ]]; then
    log "Virtual environment already exists at ${VENV_DIR}, reusing it."
  else
    log "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
  fi

  log "Installing/upgrading Python dependencies from requirements.txt..."
  "${VENV_DIR}/bin/pip" install --upgrade pip
  "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"

  # --- .env scaffold -----------------------------------------------------
  if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    log "Creating .env from .env.example (edit it before running in production!)..."
    cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
  else
    log ".env already exists, leaving it untouched."
  fi

  mkdir -p "${PROJECT_DIR}/uploads" "${PROJECT_DIR}/instance"

  log "Dependency check/install complete."
  cat <<EOF

Next steps:
  1. Edit ${PROJECT_DIR}/.env with your real SECRET_KEY and DATABASE_URL.
  2. Create the MySQL database and user (see docs/INSTALLATION.md), or:
       sudo mysql < database/schema.sql
  3. Run database migrations:
       source ${VENV_DIR}/bin/activate
       flask db upgrade
  4. Start the dev server to verify it works:
       source ${VENV_DIR}/bin/activate
       flask run
  5. For production, configure Apache + mod_wsgi:
       see docs/INSTALLATION.md and deployment/apache/image-storage-demo.conf

EOF
}

main "$@"
