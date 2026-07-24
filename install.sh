#!/usr/bin/env bash
#
# install.sh -- all-in-one installer for the Image Storage Demo.
#
# Designed for Ubuntu Server 24.04 LTS. For each dependency it checks
# whether it's already present before installing it, so it's safe to
# re-run after a partial failure. Beyond system packages, it also:
#   - provisions the MySQL database + application user
#   - writes a working .env (generating SECRET_KEY / DB password as needed)
#   - runs Flask-Migrate against the real database
#   - runs an end-to-end smoke test (upload, retrieve, validate) against a
#     disposable throwaway database that is dropped afterward, so the real
#     database/uploads/ folder are never touched by test data
#
# Every step is reported in green (pass) or red (fail); a summary prints
# at the end and the script exits non-zero if anything failed.
#
# Usage:
#   chmod +x install.sh
#   sudo ./install.sh [--skip-smoke-test] [--skip-db]
#
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
DB_NAME="image_storage_demo"
DB_USER="image_demo_user"
DB_PASSWORD=""
SKIP_SMOKE_TEST=0
SKIP_DB=0

for arg in "$@"; do
  case "${arg}" in
    --skip-smoke-test) SKIP_SMOKE_TEST=1 ;;
    --skip-db) SKIP_DB=1 ;;
    -h|--help)
      echo "Usage: sudo ./install.sh [--skip-smoke-test] [--skip-db]"
      exit 0
      ;;
    *)
      echo "Unknown option: ${arg}" >&2
      exit 1
      ;;
  esac
done

# --- Colors -------------------------------------------------------------
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  RED="$(tput setaf 1)"; GREEN="$(tput setaf 2)"; YELLOW="$(tput setaf 3)"
  BLUE="$(tput setaf 4)"; BOLD="$(tput bold)"; RESET="$(tput sgr0)"
else
  RED=""; GREEN=""; YELLOW=""; BLUE=""; BOLD=""; RESET=""
fi

log()  { printf '%s[install]%s %s\n' "${BLUE}" "${RESET}" "$1"; }
warn() { printf '%s[install][warn]%s %s\n' "${YELLOW}" "${RESET}" "$1"; }
err()  { printf '%s[install][error]%s %s\n' "${RED}" "${RESET}" "$1" >&2; }

STEPS_PASSED=()
STEPS_FAILED=()

# run_step <description> <function> [args...]
# Prints a colored PASS/FAIL line and records it for the final summary.
# Does NOT stop the script -- callers decide whether a failure is fatal.
run_step() {
  local description="$1"; shift
  printf '%s→%s %s...\n' "${BLUE}" "${RESET}" "${description}"
  if "$@"; then
    printf '%s✔ PASS%s  %s\n\n' "${GREEN}" "${RESET}" "${description}"
    STEPS_PASSED+=("${description}")
    return 0
  else
    printf '%s✘ FAIL%s  %s\n\n' "${RED}" "${RESET}" "${description}"
    STEPS_FAILED+=("${description}")
    return 1
  fi
}

# abort <message> -- for failures where continuing is pointless.
abort() {
  err "$1"
  print_summary
  exit 1
}

print_summary() {
  echo "${BOLD}==================== Installation Summary ====================${RESET}"
  for s in "${STEPS_PASSED[@]:-}"; do
    [[ -n "${s}" ]] && printf '  %s✔%s %s\n' "${GREEN}" "${RESET}" "${s}"
  done
  for s in "${STEPS_FAILED[@]:-}"; do
    [[ -n "${s}" ]] && printf '  %s✘%s %s\n' "${RED}" "${RESET}" "${s}"
  done
  echo "${BOLD}================================================================${RESET}"
  if [[ "${#STEPS_FAILED[@]}" -gt 0 ]]; then
    err "Installation completed with ${#STEPS_FAILED[@]} failed step(s). See the output above for details."
  else
    printf '%s%sAll steps passed.%s The application is installed, migrated, and verified working.\n' "${GREEN}" "${BOLD}" "${RESET}"
  fi
}

command_exists() { command -v "$1" >/dev/null 2>&1; }
dpkg_package_installed() { dpkg -s "$1" >/dev/null 2>&1; }

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    err "This script needs root for system package/database steps. Re-run with: sudo ./install.sh"
    exit 1
  fi
}

# Waits for the apt/dpkg lock to free up instead of failing immediately --
# unattended-upgrades commonly holds it for a few minutes after boot.
wait_for_apt_lock() {
  local waited=0 timeout=300 announced=0
  while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
     || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    if [[ "${waited}" -ge "${timeout}" ]]; then
      err "Timed out after ${timeout}s waiting for the apt/dpkg lock (likely held by unattended-upgrades)."
      return 1
    fi
    if [[ "${announced}" -eq 0 ]]; then
      warn "apt/dpkg lock is held by another process (likely unattended-upgrades) -- waiting for it to finish..."
      announced=1
    fi
    sleep 5
    waited=$((waited + 5))
  done
  return 0
}

APT_UPDATED=0
apt_update_once() {
  [[ "${APT_UPDATED}" -eq 1 ]] && return 0
  wait_for_apt_lock || return 1
  log "Refreshing apt package index..."
  apt-get update -y || return 1
  APT_UPDATED=1
}

apt_install_if_missing() {
  # apt_install_if_missing <check-command-or-''> <apt-package> [<apt-package> ...]
  local check_cmd="$1"; shift
  local packages=("$@")
  if [[ -n "${check_cmd}" ]] && command_exists "${check_cmd}"; then
    log "'${check_cmd}' already present, skipping (${packages[*]})."
    return 0
  fi
  local missing=()
  for pkg in "${packages[@]}"; do
    dpkg_package_installed "${pkg}" || missing+=("${pkg}")
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    log "${packages[*]} already present, skipping."
    return 0
  fi
  apt_update_once || return 1
  wait_for_apt_lock || return 1
  log "Installing: ${missing[*]}"
  apt-get install -y "${missing[@]}"
}

# ------------------------------------------------------------------------
# Step implementations
# ------------------------------------------------------------------------

step_detect_os() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log "Detected: ${PRETTY_NAME:-unknown}"
    if [[ "${ID:-}" != "ubuntu" ]]; then
      warn "This script targets Ubuntu Server 24.04 LTS; detected ID='${ID:-unknown}'. Continuing anyway."
    fi
  else
    warn "/etc/os-release not found; cannot confirm this is Ubuntu. Continuing anyway."
  fi
  return 0
}

# A prior interrupted apt/dpkg operation (common on freshly-provisioned
# VM images) leaves dpkg in a state where every subsequent apt-get call
# fails with "dpkg was interrupted, you must manually run 'dpkg
# --configure -a'". Both commands below are safe no-ops when nothing is
# actually broken, so it's cheap to always run them as a preflight repair.
step_repair_dpkg() {
  wait_for_apt_lock || return 1
  dpkg --configure -a || return 1
  apt-get install -f -y || return 1
  return 0
}

step_python() {
  apt_install_if_missing python3 python3 || return 1
  apt_install_if_missing "" python3-pip python3-pip || return 1

  local py_major py_minor
  py_major="$(python3 -c 'import sys; print(sys.version_info[0])')"
  py_minor="$(python3 -c 'import sys; print(sys.version_info[1])')"

  # `import venv` succeeds even when the version-specific venv package
  # (which provides ensurepip support) is missing -- `python3 -m venv`
  # then fails at creation time with a much less obvious error. Always
  # ensure both the generic and exact-version packages are present.
  apt_update_once || return 1
  wait_for_apt_lock || return 1
  log "Ensuring venv support (python3-venv, python3.${py_minor}-venv)..."
  apt-get install -y python3-venv "python3.${py_minor}-venv" || return 1

  # Verify venv actually works end-to-end, not just that the module
  # imports, by creating and discarding a throwaway environment.
  local probe_dir
  probe_dir="$(mktemp -d)"
  if ! python3 -m venv "${probe_dir}/venv" >/dev/null 2>&1; then
    err "'python3 -m venv' still fails after installing python3.${py_minor}-venv."
    rm -rf "${probe_dir}"
    return 1
  fi
  rm -rf "${probe_dir}"

  if (( py_major < 3 || (py_major == 3 && py_minor < 10) )); then
    warn "Detected Python ${py_major}.${py_minor}; 3.12+ is recommended for production. Continuing."
  else
    log "Python ${py_major}.${py_minor} OK."
  fi
  return 0
}

step_pillow_deps() {
  local pkgs=(libjpeg-dev zlib1g-dev libwebp-dev)
  local missing=()
  for pkg in "${pkgs[@]}"; do
    dpkg_package_installed "${pkg}" || missing+=("${pkg}")
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    log "Pillow build dependencies already present, skipping."
    return 0
  fi
  apt_update_once || return 1
  wait_for_apt_lock || return 1
  apt-get install -y "${missing[@]}"
}

step_mysql() {
  if command_exists mysql; then
    log "MySQL client already present, skipping mysql-server install."
    return 0
  fi
  apt_update_once || return 1
  wait_for_apt_lock || return 1
  apt-get install -y mysql-server || return 1
  systemctl enable --now mysql
}

step_apache() {
  apt_install_if_missing apache2ctl apache2 || return 1
  if dpkg_package_installed libapache2-mod-wsgi-py3; then
    log "libapache2-mod-wsgi-py3 already present, skipping."
    return 0
  fi
  apt_update_once || return 1
  wait_for_apt_lock || return 1
  apt-get install -y libapache2-mod-wsgi-py3
}

step_git() {
  apt_install_if_missing git git
}

step_venv() {
  if [[ -d "${VENV_DIR}" ]]; then
    log "Virtual environment already exists at ${VENV_DIR}, reusing it."
  else
    log "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}" || return 1
  fi
  log "Installing/upgrading Python dependencies from requirements.txt..."
  "${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null || return 1
  "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"
}

# Extracts the password out of an existing mysql+pymysql:// DATABASE_URL.
_extract_password_from_url() {
  echo "$1" | sed -E 's#^[a-z+]+://[^:]+:([^@]+)@.*#\1#'
}

step_provision_mysql() {
  if ! command_exists mysql; then
    err "mysql client not found; cannot provision the database."
    return 1
  fi

  local existing_url=""
  if [[ -f "${PROJECT_DIR}/.env" ]] && grep -q '^DATABASE_URL=' "${PROJECT_DIR}/.env"; then
    existing_url="$(grep '^DATABASE_URL=' "${PROJECT_DIR}/.env" | head -1 | cut -d= -f2-)"
  fi

  if [[ -n "${existing_url}" && "${existing_url}" != *CHANGE_ME* && "${existing_url}" == mysql* ]]; then
    log "Reusing database credentials already configured in .env."
    DB_PASSWORD="$(_extract_password_from_url "${existing_url}")"
  else
    DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  fi

  if [[ -z "${DB_PASSWORD}" ]]; then
    err "Could not determine a database password."
    return 1
  fi

  sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
}

step_write_env() {
  if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
  fi

  if ! grep -q '^SECRET_KEY=' "${PROJECT_DIR}/.env" \
     || grep -q 'change-me-to-a-long-random-value' "${PROJECT_DIR}/.env"; then
    local secret_key
    secret_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    sed -i "s#^SECRET_KEY=.*#SECRET_KEY=${secret_key}#" "${PROJECT_DIR}/.env"
  fi

  # .env.example ships with illustrative /var/www/image-storage-demo
  # paths, but the project can be cloned anywhere -- always point these
  # at wherever this script actually is, so a mismatched path never
  # crashes the app trying to open a log file that doesn't exist.
  if grep -q '^UPLOAD_FOLDER=' "${PROJECT_DIR}/.env"; then
    sed -i "s#^UPLOAD_FOLDER=.*#UPLOAD_FOLDER=${PROJECT_DIR}/uploads#" "${PROJECT_DIR}/.env"
  else
    echo "UPLOAD_FOLDER=${PROJECT_DIR}/uploads" >> "${PROJECT_DIR}/.env"
  fi
  if grep -q '^LOG_FILE=' "${PROJECT_DIR}/.env"; then
    sed -i "s#^LOG_FILE=.*#LOG_FILE=${PROJECT_DIR}/instance/app.log#" "${PROJECT_DIR}/.env"
  else
    echo "LOG_FILE=${PROJECT_DIR}/instance/app.log" >> "${PROJECT_DIR}/.env"
  fi

  if [[ "${SKIP_DB}" -eq 0 ]]; then
    local db_url="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@localhost:3306/${DB_NAME}"
    if grep -q '^DATABASE_URL=' "${PROJECT_DIR}/.env"; then
      sed -i "s#^DATABASE_URL=.*#DATABASE_URL=${db_url}#" "${PROJECT_DIR}/.env"
    else
      echo "DATABASE_URL=${db_url}" >> "${PROJECT_DIR}/.env"
    fi
  fi

  mkdir -p "${PROJECT_DIR}/uploads" "${PROJECT_DIR}/instance"
  return 0
}

step_migrate_real_db() {
  export FLASK_APP=run.py
  export DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@localhost:3306/${DB_NAME}"
  if [[ ! -d "${PROJECT_DIR}/migrations" ]]; then
    "${VENV_DIR}/bin/flask" db init || return 1
    "${VENV_DIR}/bin/flask" db migrate -m "Initial schema" || return 1
  fi
  "${VENV_DIR}/bin/flask" db upgrade
}

cleanup_smoke_test() {
  local smoke_db="$1" smoke_dir="$2"
  sudo mysql -e "DROP DATABASE IF EXISTS ${smoke_db};" >/dev/null 2>&1 || true
  rm -rf "${smoke_dir}"
}

step_smoke_test() {
  local smoke_db="${DB_NAME}_smoketest"
  local smoke_upload_dir
  smoke_upload_dir="$(mktemp -d)"

  log "Provisioning disposable database '${smoke_db}' for the smoke test (dropped afterward)..."
  if ! sudo mysql -e "DROP DATABASE IF EXISTS ${smoke_db}; CREATE DATABASE ${smoke_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON ${smoke_db}.* TO '${DB_USER}'@'localhost'; FLUSH PRIVILEGES;"; then
    err "Could not create the throwaway smoke-test database."
    cleanup_smoke_test "${smoke_db}" "${smoke_upload_dir}"
    return 1
  fi

  export FLASK_APP=run.py
  export DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@localhost:3306/${smoke_db}"
  export UPLOAD_FOLDER="${smoke_upload_dir}"
  export SECRET_KEY="${SECRET_KEY:-smoke-test-only-key}"
  export SMOKE_TEST_ENV=development

  local rc=0
  if ! "${VENV_DIR}/bin/flask" db upgrade; then
    err "Migration against the smoke-test database failed."
    rc=1
  else
    "${VENV_DIR}/bin/python" "${PROJECT_DIR}/scripts/smoke_test.py"
    rc=$?
  fi

  unset DATABASE_URL UPLOAD_FOLDER SMOKE_TEST_ENV
  cleanup_smoke_test "${smoke_db}" "${smoke_upload_dir}"
  return "${rc}"
}

# The whole script runs under sudo, so everything it creates (venv/,
# uploads/, .env) would otherwise end up owned by root -- breaking
# `flask run` for the normal user immediately after install.
step_fix_ownership() {
  local target_user="${SUDO_USER:-}"
  if [[ -z "${target_user}" || "${target_user}" == "root" ]]; then
    log "No non-root invoking user detected (SUDO_USER unset) -- skipping ownership fix."
    return 0
  fi
  local target_group
  target_group="$(id -gn "${target_user}" 2>/dev/null || echo "${target_user}")"
  chown -R "${target_user}:${target_group}" "${PROJECT_DIR}"
}

# ------------------------------------------------------------------------
main() {
  require_root

  run_step "Detect operating system" step_detect_os
  run_step "Repair any interrupted dpkg/apt state" step_repair_dpkg
  run_step "Install Python 3 / pip / venv" step_python || abort "Cannot continue without Python."
  run_step "Install Pillow's native image libraries" step_pillow_deps
  if [[ "${SKIP_DB}" -eq 0 ]]; then
    run_step "Install MySQL server" step_mysql || abort "Cannot continue without MySQL (use --skip-db to manage it yourself)."
  fi
  run_step "Install Apache2 + mod_wsgi" step_apache
  run_step "Install Git" step_git
  run_step "Create virtual environment and install requirements" step_venv \
    || abort "Cannot continue without the Python virtual environment."

  if [[ "${SKIP_DB}" -eq 0 ]]; then
    run_step "Provision MySQL database and application user" step_provision_mysql \
      || abort "Cannot continue without a working database connection."
    run_step "Write .env (SECRET_KEY, DATABASE_URL)" step_write_env
    run_step "Run database migrations against ${DB_NAME}" step_migrate_real_db \
      || abort "Migrations failed against the real database -- fix and re-run before deploying."

    if [[ "${SKIP_SMOKE_TEST}" -eq 0 ]]; then
      run_step "Run end-to-end smoke test (isolated throwaway database)" step_smoke_test
    else
      log "Skipping smoke test (--skip-smoke-test)."
    fi
  else
    run_step "Write .env (SECRET_KEY only, --skip-db set)" step_write_env
    warn "Skipped MySQL provisioning and migrations (--skip-db). Set DATABASE_URL in .env yourself, then run: flask db upgrade"
  fi

  run_step "Restore file ownership to the invoking user" step_fix_ownership

  print_summary

  cat <<EOF

Next steps:
  1. Review ${PROJECT_DIR}/.env (SECRET_KEY and DATABASE_URL were generated for you).
  2. Start the dev server to try it manually:
       source ${VENV_DIR}/bin/activate
       flask run
  3. For production, configure Apache + mod_wsgi:
       see docs/INSTALLATION.md and deployment/apache/image-storage-demo.conf

EOF

  [[ "${#STEPS_FAILED[@]}" -gt 0 ]] && exit 1
  exit 0
}

main "$@"
