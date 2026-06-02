#!/usr/bin/env bash
# Run the integration test suite against a live Hetzner Storage Box.
#
# Required environment variables (set before calling this script,
# or place them in a .env file — see sample.env):
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
# .env file support:
#   Copy sample.env to .env, fill in your credentials, and this script loads
#   it automatically. Or pass a custom path with --env-file:
#     ./run_integration_tests.sh --env-file /path/to/my.env
#   Variables already set in the environment take precedence over the .env file.
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

# ---------------------------------------------------------------------------
# Parse --env-file option; collect remaining args to forward to pytest
# ---------------------------------------------------------------------------
ENV_FILE=""
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --env-file=*)
            ENV_FILE="${1#*=}"
            shift
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# Auto-detect .env in the project root when no explicit file is given
if [[ -z "$ENV_FILE" && -f "$SCRIPT_DIR/.env" ]]; then
    ENV_FILE="$SCRIPT_DIR/.env"
fi

# Load the .env file, letting already-exported variables take precedence
if [[ -n "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "Error: env file not found: $ENV_FILE"
        exit 1
    fi
    echo "==> Loading credentials from $ENV_FILE"
    # Export every assignment from the file; skip comment/blank lines
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Strip leading whitespace and skip comments / blank lines
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        # Strip optional "export " prefix
        line="${line#export }"
        # Only set if not already in the environment
        var="${line%%=*}"
        if [[ -n "$var" && -z "${!var:-}" ]]; then
            export "$line"
        fi
    done < "$ENV_FILE"
fi

# ---------------------------------------------------------------------------
# Validate required variables
# ---------------------------------------------------------------------------
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
    echo "Set them in the environment, or copy sample.env to .env and fill in your credentials."
    exit 1
fi

echo "==> Target: ${HSBT_TEST_USER}@${HSBT_TEST_HOST} (port ${HSBT_TEST_SSH_PORT:-23})"

echo "==> Installing dependencies..."
pdm install -G test -q

echo "==> Running integration tests..."
# --tb=short: keeps tracebacks compact and avoids printing local variable
# values, which reduces the risk of leaking credentials in terminal output.
pdm run pytest tests/integration/ -v --tb=short "${PYTEST_ARGS[@]:+${PYTEST_ARGS[@]}}"
