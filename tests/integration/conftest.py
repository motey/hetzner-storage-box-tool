"""
Integration test suite — requires a live Hetzner Storage Box.

HOW TO ACTIVATE
===============
Set the following environment variables before running pytest.
All tests are automatically skipped when these are absent.

  HSBT_TEST_HOST      Hostname of the storage box
                      Example: u000001.your-storagebox.de

  HSBT_TEST_USER      SSH username (same as the box account name)
                      Example: u000001

  HSBT_TEST_PASSWORD  Account password.
                      Required on first run to deploy the test SSH key.
                      On subsequent runs with a persisted key directory
                      (see HSBT_TEST_KEY_DIR below) it is no longer needed,
                      but safe to leave set.

  HSBT_TEST_SSH_PORT  SSH port (optional, default: 23)

  HSBT_TEST_KEY_DIR   Directory where the test SSH keypair is stored
                      (optional, default: a fresh temp dir each run).
                      Set this to a persistent path, e.g.
                        ~/.config/hsbt/integration-test-keys
                      to avoid redeploying the key on every run.

LOCAL QUICK-START
-----------------
  export HSBT_TEST_HOST=u000001.your-storagebox.de
  export HSBT_TEST_USER=u000001
  export HSBT_TEST_PASSWORD=yourpassword
  ./run_integration_tests.sh

GITHUB ACTIONS SETUP
--------------------
Add these repository secrets (Settings → Secrets and variables → Actions):

  HSBT_TEST_HOST
  HSBT_TEST_USER
  HSBT_TEST_PASSWORD
  HSBT_TEST_SSH_PORT  (optional)

The provided workflow file (.github/workflows/integration.yml) reads them
automatically. GitHub masks secret values in all log output, so the password
will never appear in plain text even if a test fails.

ISOLATION
---------
Each test session creates a unique working directory on the remote box
(_hsbt_integration_test_<8-char-uuid>/) and deletes it on teardown.
The tests never write outside that directory. If a session is interrupted
before teardown you can clean up manually:
  ssh -p 23 <user>@<host> "rm -rf _hsbt_integration_test_*"
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from hsbt.key_manager import KeyManager
from hsbt.storage_box import StorageBox
from hsbt.transport.ssh import SshTransport

# ---------------------------------------------------------------------------
# Read credentials from the environment — never hard-code them here.
# ---------------------------------------------------------------------------

_HOST = os.environ.get("HSBT_TEST_HOST", "")
_USER = os.environ.get("HSBT_TEST_USER", "")
_PASSWORD = os.environ.get("HSBT_TEST_PASSWORD", "")
_PORT = int(os.environ.get("HSBT_TEST_SSH_PORT", "23"))
_KEY_DIR = os.environ.get("HSBT_TEST_KEY_DIR", "")

CREDS_AVAILABLE = bool(_HOST and _USER and _PASSWORD)


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def transport_live(tmp_path_factory):
    """
    Real SshTransport connected to the live storage box.

    Skipped automatically when HSBT_TEST_HOST / _USER / _PASSWORD are not set.
    SSH key deployment is attempted once per session; the password is passed
    via the SSHPASS env variable internally (never echoed to stdout).
    """
    if not CREDS_AVAILABLE:
        pytest.skip(
            "Integration credentials not set. "
            "Set HSBT_TEST_HOST, HSBT_TEST_USER, HSBT_TEST_PASSWORD to enable."
        )

    if _KEY_DIR:
        key_dir = Path(_KEY_DIR).expanduser()
        key_dir.mkdir(parents=True, exist_ok=True)
    else:
        key_dir = tmp_path_factory.mktemp("integration_ssh_keys")

    km = KeyManager(target_dir=key_dir, identifier="integration")
    transport = SshTransport(
        host=_HOST,
        user=_USER,
        key_manager=km,
        port=_PORT,
        remote_dir="/home",
    )
    # Password is stored on the transport object only; it goes to the
    # SSHPASS env variable in run_command() and is never logged.
    transport.password = _PASSWORD or None

    transport.deploy_public_key_if_not_done()
    return transport


@pytest.fixture(scope="session")
def storage_box_live(transport_live):
    """StorageBox facade wrapping the live transport."""
    box = StorageBox.__new__(StorageBox)
    box.ssh = transport_live
    return box


@pytest.fixture(scope="session")
def remote_workdir(transport_live):
    """
    A unique temporary directory on the remote box for this test session.
    Created before any test runs, deleted unconditionally on teardown.
    """
    workdir = f"_hsbt_integration_test_{uuid.uuid4().hex[:8]}"
    transport_live.run_remote_command(f"mkdir -p {workdir}")
    yield workdir
    transport_live.run_remote_command(f"rm -rf {workdir}")
