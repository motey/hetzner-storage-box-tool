"""
Live WebDAV integration tests — requires rclone and a real Hetzner Storage Box.

Additional env var (on top of the standard HSBT_TEST_* set):

  HSBT_TEST_WEBDAV_PASSWORD   Storage box password for HTTP Basic auth.
                               Falls back to HSBT_TEST_PASSWORD when not set,
                               since Hetzner uses the same password for both.

All tests in this file are skipped when neither HSBT_TEST_WEBDAV_PASSWORD nor
HSBT_TEST_PASSWORD is set, or when the standard HSBT_TEST_* credentials are absent.

These tests call real rclone against the live box over HTTPS (port 443).
rclone must be installed and reachable as 'rclone' on PATH (or override with
HSBT_BIN_PATH_RCLONE).
"""

from __future__ import annotations

import os
import shutil
import pytest

from hsbt.mount.rclone import RcloneMountStrategy
from tests.integration.conftest import CREDS_AVAILABLE

_WEBDAV_PASSWORD = os.environ.get("HSBT_TEST_WEBDAV_PASSWORD", "") or os.environ.get("HSBT_TEST_PASSWORD", "")
WEBDAV_CREDS_AVAILABLE = CREDS_AVAILABLE and bool(_WEBDAV_PASSWORD)
RCLONE_AVAILABLE = shutil.which("rclone") is not None


@pytest.fixture(scope="module")
def webdav_strategy(transport_live, tmp_path_factory):
    """RcloneMountStrategy with WebDAV backend, backed by a temp rclone config."""
    if not WEBDAV_CREDS_AVAILABLE:
        pytest.skip(
            "WebDAV credentials not set. "
            "Set HSBT_TEST_WEBDAV_PASSWORD (and the standard HSBT_TEST_* vars) to enable."
        )
    if not RCLONE_AVAILABLE:
        pytest.skip("rclone not found on PATH.")
    config_path = tmp_path_factory.mktemp("rclone_webdav") / "rclone.conf"
    return RcloneMountStrategy(
        transport_live,
        config_file_path=config_path,
        backend="webdav",
        webdav_password=_WEBDAV_PASSWORD,
    )


class TestWebdavEnsureConfig:
    def test_ensure_config_creates_entry(self, webdav_strategy, transport_live):
        created = webdav_strategy.ensure_config()
        assert created is True

    def test_ensure_config_is_idempotent(self, webdav_strategy):
        # Second call: all non-secret fields match and 'pass' exists → skip.
        created = webdav_strategy.ensure_config()
        assert created is False

    def test_config_dump_contains_webdav_type(self, webdav_strategy, transport_live):
        webdav_strategy.ensure_config()
        existing = webdav_strategy.get_existing_config(
            transport_live.key_manager.identifier, missing_ok=True
        )
        assert existing is not None
        assert existing.get("type") == "webdav"

    def test_config_dump_contains_correct_url(self, webdav_strategy, transport_live):
        webdav_strategy.ensure_config()
        existing = webdav_strategy.get_existing_config(
            transport_live.key_manager.identifier
        )
        assert transport_live.host in existing["url"]
        assert existing["url"].startswith("https://")

    def test_config_dump_has_obscured_pass(self, webdav_strategy, transport_live):
        webdav_strategy.ensure_config()
        existing = webdav_strategy.get_existing_config(
            transport_live.key_manager.identifier
        )
        assert "pass" in existing
        # rclone stores an obscured (non-cleartext) value
        assert existing["pass"] != _WEBDAV_PASSWORD


class TestWebdavLiveConnectivity:
    """Exercises an actual rclone lsd call against the WebDAV remote.

    This goes over the network to port 443, so it validates both the config
    format and that Hetzner accepts the credentials.
    """

    def test_lsd_lists_remote_root(self, webdav_strategy, transport_live):
        from hsbt.process import run_command
        webdav_strategy.ensure_config()
        # WebDAV root on Hetzner is '/', not '/home' like SFTP — pass explicit root path.
        remote = webdav_strategy._remote("/")
        config_param = webdav_strategy._config_param()
        cmd = f"rclone {config_param} lsd {remote}"
        result = run_command(cmd)
        assert result.return_code == 0
