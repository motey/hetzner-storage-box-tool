#!/usr/bin/env bash
# Run the integration test suite against a live Hetzner Storage Box.
#
# Required environment variables (set before calling this script):
#
#   HSBT_TEST_HOST      Hostname  e.g. u000001.your-storagebox.de
#   HSBT_TEST_USER      Username  e.g. u000001
#   HSBT_TEST_PASSWORD  Account password (needed for first-time key deployment)
#
# Optional:
#   HSBT_TEST_SSH_PORT  SSH port (default: 23)
#   HSBT_TEST_KEY_DIR   Persistent directory for the test SSH keypair.
#                       Defaults to a fresh temp dir (key redeployed every run).
#                       Set to a stable path to skip redeployment on repeat runs:
#                         export HSBT_TEST_KEY_DIR=~/.config/hsbt/integration-keys
#
# Example:
#   export HSBT_TEST_HOST=u000001.your-storagebox.de
#   export HSBT_TEST_USER=u000001
#   export HSBT_TEST_PASSWORD=yourpassword
#   ./run_integration_tests.sh
#
# Extra pytest flags are forwarded:
#   ./run_integration_tests.sh -v -k test_upload
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Validate required variables
missing=()
[[ -z "${HSBT_TEST_HOST:-}" ]]     && missing+=("HSBT_TEST_HOST")
[[ -z "${HSBT_TEST_USER:-}" ]]     && missing+=("HSBT_TEST_USER")
[[ -z "${HSBT_TEST_PASSWORD:-}" ]] && missing+=("HSBT_TEST_PASSWORD")

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Error: missing required environment variables:"
    for v in "${missing[@]}"; do
        echo "  $v"
    done
    echo ""
    echo "See the top of tests/integration/conftest.py for setup instructions."
    exit 1
fi

echo "==> Target: ${HSBT_TEST_USER}@${HSBT_TEST_HOST} (port ${HSBT_TEST_SSH_PORT:-23})"

echo "==> Installing dependencies..."
pdm install -G test -q

echo "==> Running integration tests..."
# --tb=short: keeps tracebacks compact and avoids printing local variable
# values, which reduces the risk of leaking credentials in terminal output.
pdm run pytest tests/integration/ -v --tb=short "$@"
