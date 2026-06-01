#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Find a Python 3.14+ interpreter
PYTHON_BIN=""
for candidate in python3.14 python3 python; do
    if command -v "$candidate" &>/dev/null && \
       "$candidate" -c "import sys; exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "Error: Python 3.14+ not found. Please install it and make sure it is on PATH."
    exit 1
fi

echo "==> Using $($PYTHON_BIN --version)"

echo "==> Configuring PDM to use Python 3.14..."
pdm use "$PYTHON_BIN" -f -q

echo "==> Installing dependencies..."
pdm install -G test -q

echo "==> Running unit tests..."
# Integration tests live in tests/integration/ and require a live storage box.
# Run them separately with ./run_integration_tests.sh
pdm run pytest tests/ --ignore=tests/integration/ "$@"
