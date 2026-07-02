#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"

load_shell_path() {
  for profile in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc"; do
    if [ -f "$profile" ]; then
      # shellcheck disable=SC1090
      source "$profile"
    fi
  done
}

echo "==> Deploying aiassist in ${APP_DIR}"

if [ ! -f ".env" ]; then
  echo "ERROR: .env not found on server."
  echo "Create ${APP_DIR}/.env with production values before deploying."
  exit 1
fi

if [ -f "requirements.txt" ]; then
  if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating virtual environment"
    "$PYTHON" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  echo "==> Installing Python dependencies"
  python -m pip install --upgrade pip
  grep -v '^pywin32' requirements.txt | python -m pip install -r /dev/stdin
fi

if [ -f "package.json" ]; then
  echo "==> Installing Node dependencies"
  if [ -f "package-lock.json" ]; then
    npm ci
  else
    npm install
  fi
fi

if [ "${SKIP_SERVICE_RESTART:-false}" = "true" ]; then
  echo "==> Skipping PM2 restart (SKIP_SERVICE_RESTART=true)"
  echo "==> Deploy complete"
  exit 0
fi

load_shell_path

if ! command -v pm2 >/dev/null 2>&1; then
  echo "ERROR: pm2 not found in PATH for user $(whoami)."
  echo "Install PM2 or ensure it is available in the deploy user's shell profile."
  exit 1
fi

echo "==> Restarting all PM2 services"
if pm2 restart all --update-env; then
  pm2 save
  echo "==> PM2 services restarted"
else
  if [ -f "ecosystem.config.cjs" ]; then
    echo "==> No running PM2 apps found, starting from ecosystem.config.cjs"
    pm2 startOrReload ecosystem.config.cjs --update-env
    pm2 save
    echo "==> PM2 services started"
  else
    echo "ERROR: No PM2 apps running and no ecosystem.config.cjs found."
    exit 1
  fi
fi

echo "==> Deploy complete"
