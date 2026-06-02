"""
Integration tests for AutofsMountStrategy against a live Hetzner Storage Box.

REQUIREMENTS
============
These tests require TWO conditions — both must be met for the full suite to run:

  1. Storage box credentials (see integration/conftest.py):
       HSBT_TEST_HOST, HSBT_TEST_USER, HSBT_TEST_PASSWORD

  2. Root privileges on the local machine, so that autofs map files can be
     written to /etc and /etc/auto.master can be updated.

Tests are organised into two tiers:

  Tier 1 — no-root tests (use tmp directories for the autofs config):
    Verify map entry and auto.master entry content produced from a live
    transport fixture.  These run whenever storage box credentials are
    available.

  Tier 2 — root-required tests:
    Write map file and auto.master entry to /etc, reload autofs, and verify
    the configuration has been applied.  These are skipped unless running as
    root AND storage box creds are available.

IMPORTANT
=========
Tier 2 tests install and immediately remove the autofs configuration.
They never actually trigger an automount — only the config file changes are
verified.  No filesystem mounts are performed.

To run locally:
  sudo -E HSBT_TEST_HOST=... HSBT_TEST_USER=... HSBT_TEST_PASSWORD=... \\
      python -m pytest tests/integration/test_mount_autofs_live.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from hsbt.mount.autofs import AutofsMountStrategy

# Skip markers
_requires_creds = pytest.mark.skipif(
    not os.environ.get("HSBT_TEST_HOST"),
    reason="HSBT_TEST_HOST not set — skipping autofs integration tests.",
)
_requires_root = pytest.mark.skipif(
    os.geteuid() != 0,
    reason="Root privileges required to write to /etc and /etc/auto.master.",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def strategy(transport_live):
    return AutofsMountStrategy(transport_live)


# ---------------------------------------------------------------------------
# Tier 1 — map entry content (no root needed)
# ---------------------------------------------------------------------------

@_requires_creds
class TestMapEntryContent:
    """Verify generated map entry content using a live transport (no root needed)."""

    def test_map_entry_contains_real_host(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        entry = strategy._map_entry(mp, None, os.getuid(), os.getgid())
        assert transport_live.host in entry

    def test_map_entry_contains_real_user(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        entry = strategy._map_entry(mp, None, os.getuid(), os.getgid())
        assert transport_live.user in entry

    def test_map_entry_contains_real_key_path(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        entry = strategy._map_entry(mp, None, os.getuid(), os.getgid())
        assert str(transport_live.key_manager.private_key_path) in entry

    def test_map_entry_starts_with_mountpoint(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        entry = strategy._map_entry(mp, None, os.getuid(), os.getgid())
        assert entry.startswith(str(mp))

    def test_map_entry_contains_fstype_sshfs(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        entry = strategy._map_entry(mp, None, os.getuid(), os.getgid())
        assert "fstype=fuse.sshfs" in entry

    def test_master_entry_references_map_file(self, strategy, tmp_path):
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        map_file = strategy._map_file_path(autofs_dir)
        entry = strategy._master_entry(map_file)
        assert str(map_file) in entry
        assert entry.startswith("/-")

    def test_mount_permanent_writes_map_file_to_tmp(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=autofs_dir)
        map_file = strategy._map_file_path(autofs_dir)
        assert map_file.exists()
        assert transport_live.host in map_file.read_text()

    def test_mount_permanent_writes_master_entry_to_tmp(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=autofs_dir)
        master = strategy._master_file_path(autofs_dir)
        assert master.exists()
        assert "/-" in master.read_text()

    def test_idempotent_install(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=autofs_dir)
            strategy.mount_permanent(mp, fstab_file=autofs_dir)
        map_file = strategy._map_file_path(autofs_dir)
        # ConfigFileEditor wraps entries in comment markers containing the path,
        # so count only actual map lines (start with mountpoint, not '#')
        lines = [l for l in map_file.read_text().splitlines() if l.startswith(str(mp))]
        assert len(lines) == 1

    def test_mount_raises_not_implemented(self, strategy, tmp_path):
        with pytest.raises(NotImplementedError):
            strategy.mount(tmp_path / "mnt")


# ---------------------------------------------------------------------------
# Tier 2 — real /etc changes (root required)
# ---------------------------------------------------------------------------

@_requires_creds
@_requires_root
class TestAutofsMasterFileLifecycle:
    """Write real autofs config to /etc and verify it is cleaned up correctly."""

    AUTOFS_DIR = Path("/etc")

    @pytest.fixture(autouse=True)
    def cleanup(self, strategy, tmp_path):
        """Remove the map file and any master entry written by the test."""
        yield
        mp = tmp_path / "mnt" / "_hsbt_integration_test_autofs"
        map_file = strategy._map_file_path(self.AUTOFS_DIR)
        master = strategy._master_file_path(self.AUTOFS_DIR)
        if map_file.exists():
            map_file.unlink()
        if master.exists():
            # Remove the test entry from auto.master without deleting the file
            from hsbt.config_editor import ConfigFileEditor
            ConfigFileEditor(master).remove_config_entry(
                strategy._master_identifier(map_file)
            )
        # Best-effort autofs reload — autofs may not be running in CI
        import subprocess
        subprocess.run(["systemctl", "reload", "autofs"], check=False, capture_output=True)

    def test_map_file_written_to_etc(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "_hsbt_integration_test_autofs"
        strategy.mount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        map_file = strategy._map_file_path(self.AUTOFS_DIR)
        assert map_file.exists(), f"Expected map file at {map_file}"

    def test_master_entry_written_to_etc(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "_hsbt_integration_test_autofs"
        strategy.mount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        master = strategy._master_file_path(self.AUTOFS_DIR)
        map_file = strategy._map_file_path(self.AUTOFS_DIR)
        assert master.exists()
        assert str(map_file) in master.read_text()

    def test_map_file_removed_after_uninstall(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "_hsbt_integration_test_autofs"
        strategy.mount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        strategy.unmount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        map_file = strategy._map_file_path(self.AUTOFS_DIR)
        assert not map_file.exists()

    def test_master_entry_removed_after_uninstall(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "_hsbt_integration_test_autofs"
        map_file = strategy._map_file_path(self.AUTOFS_DIR)
        strategy.mount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        strategy.unmount_permanent(mp, fstab_file=self.AUTOFS_DIR)
        master = strategy._master_file_path(self.AUTOFS_DIR)
        if master.exists():
            assert str(map_file) not in master.read_text()
