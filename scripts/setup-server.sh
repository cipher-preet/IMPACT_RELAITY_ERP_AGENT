#!/usr/bin/env bash
set -euo pipefail

# One-time server bootstrap for PM2-based deployment.
#
# Usage:
#   bash scripts/setup-server.sh /home/ubuntu-dark-shadow/Desktop/SERVER_ADVANCE_SHARED/IMPACT/aiassist

DEPLOY_PATH="${1:-/home/ubuntu-dark-shadow/Desktop/SERVER_ADVANCE_SHARED/IMPACT/aiassist}"

echo "==> Creating deploy directory: ${DEPLOY_PATH}"
mkdir -p "${DEPLOY_PATH}"

if [ ! -f "${DEPLOY_PATH}/.env" ]; then
  echo "==> Create ${DEPLOY_PATH}/.env with production secrets before first deploy."
fi

if ! command -v pm2 >/dev/null 2>&1; then
  echo "==> PM2 not found. Install with: npm install -g pm2"
  exit 1
fi

echo "==> Server setup complete"
echo "Next steps:"
echo "  1. Ensure SSH password login works for the deploy user"
echo "  2. Create ${DEPLOY_PATH}/.env"
echo "  3. After first code sync, start services once:"
echo "       cd ${DEPLOY_PATH} && bash scripts/deploy.sh"
echo "  4. Optional: pm2 startup && pm2 save"
