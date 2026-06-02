"""
Integration tests for SystemdMountStrategy against a live Hetzner Storage Box.

REQUIREMENTS
============
These tests require TWO conditions — both must be met for the full suite to run:

  1. Storage box credentials (see integration/conftest.py):
       HSBT_TEST_HOST, HSBT_TEST_USER, HSBT_TEST_PASSWORD

  2. Root privileges on the local machine, so that systemd unit files can be
     written to /etc/systemd/system and systemctl can enable/disable them.

Tests are organised into two tiers:

  Tier 1 — no-root tests (use a tmp unit_dir):
    Verify unit file content and names produced from a live transport fixture.
    These run whenever storage box credentials are available.

  Tier 2 — root-required tests:
    Write unit files to /etc/systemd/system, call `systemctl daemon-reload` /
    `enable` / `disable`, and verify the service state via `systemctl is-enabled`.
    These are skipped unless running as root AND storage box creds are available.

IMPORTANT
=========
Tier 2 tests install and immediately remove a transient `.mount` / `.automount`
unit pair.  They never actually mount the storage box — `systemctl enable` only
registers the unit; `start` is never called in these tests.  No filesystem
changes are made beyond writing/removing unit files in /etc/systemd/system.

To run locally:
  sudo -E HSBT_TEST_HOST=... HSBT_TEST_USER=... HSBT_TEST_PASSWORD=... \\
      python -m pytest tests/integration/test_mount_systemd_live.py -v
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from hsbt.mount.systemd import SystemdMountStrategy
from hsbt.process import run_command

# Skip markers
_requires_creds = pytest.mark.skipif(
    not os.environ.get("HSBT_TEST_HOST"),
    reason="HSBT_TEST_HOST not set — skipping systemd integration tests.",
)
_requires_root = pytest.mark.skipif(
    os.geteuid() != 0,
    reason="Root privileges required to write to /etc/systemd/system.",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def strategy(transport_live):
    return SystemdMountStrategy(transport_live)


@pytest.fixture
def unit_dir(tmp_path):
    d = tmp_path / "systemd"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tier 1 — unit file content (no root needed)
# ---------------------------------------------------------------------------

@_requires_creds
class TestUnitFileContent:
    """Verify generated unit file content using a live transport (no root needed)."""

    def test_mount_unit_written_to_tmp_dir(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        from unittest.mock import patch
        with patch("hsbt.mount.systemd.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=unit_dir)
        stem = strategy._unit_stem(mp)
        assert (unit_dir / f"{stem}.mount").exists(), "Expected .mount unit file to be written"

    def test_automount_unit_written_to_tmp_dir(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        from unittest.mock import patch
        with patch("hsbt.mount.systemd.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=unit_dir)
        stem = strategy._unit_stem(mp)
        assert (unit_dir / f"{stem}.automount").exists(), "Expected .automount unit file to be written"

    def test_mount_unit_contains_real_host(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        from unittest.mock import patch
        with patch("hsbt.mount.systemd.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=unit_dir)
        stem = strategy._unit_stem(mp)
        content = (unit_dir / f"{stem}.mount").read_text()
        assert transport_live.host in content

    def test_mount_unit_contains_real_key_path(self, strategy, tmp_path, transport_live):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        from unittest.mock import patch
        with patch("hsbt.mount.systemd.run_command") as mock_rc:
            mock_rc.return_value = type("R", (), {"return_code": 0, "stdout": "", "stderr": ""})()
            strategy.mount_permanent(mp, fstab_file=unit_dir)
        stem = strategy._unit_stem(mp)
        content = (unit_dir / f"{stem}.mount").read_text()
        assert str(transport_live.key_manager.private_key_path) in content

    def test_mount_unit_type_is_fuse_sshfs(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        content = strategy._generate_mount_unit(mp, None, os.getuid(), os.getgid())
        assert "Type=fuse.sshfs" in content

    def test_automount_unit_has_timeout(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        content = strategy._generate_automount_unit(mp)
        assert "TimeoutIdleSec=" in content

    def test_unit_stem_for_mountpoint(self, strategy, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        stem = strategy._unit_stem(mp)
        assert "mybox" in stem
        assert "/" not in stem


# ---------------------------------------------------------------------------
# Tier 2 — real systemd interaction (root required)
# ---------------------------------------------------------------------------

@_requires_creds
@_requires_root
class TestSystemdServiceLifecycle:
    """Write real unit files to /etc/systemd/system and verify via systemctl."""

    UNIT_DIR = Path("/etc/systemd/system")
    MOUNTPOINT = Path("/mnt/_hsbt_integration_test_systemd")

    @pytest.fixture(autouse=True)
    def cleanup(self, strategy):
        """Always clean up unit files after each test, even on failure."""
        yield
        stem = strategy._unit_stem(self.MOUNTPOINT)
        for suffix in (".mount", ".automount"):
            unit = self.UNIT_DIR / f"{stem}{suffix}"
            if unit.exists():
                unit.unlink()
        subprocess.run(["systemctl", "daemon-reload"], check=False)

    def test_unit_files_created_in_system_dir(self, strategy):
        strategy.mount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        stem = strategy._unit_stem(self.MOUNTPOINT)
        assert (self.UNIT_DIR / f"{stem}.mount").exists()
        assert (self.UNIT_DIR / f"{stem}.automount").exists()

    def test_automount_unit_enabled_after_install(self, strategy):
        strategy.mount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        stem = strategy._unit_stem(self.MOUNTPOINT)
        result = subprocess.run(
            ["systemctl", "is-enabled", f"{stem}.automount"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Expected automount unit to be enabled, got: {result.stdout.strip()}"
        )

    def test_unit_files_removed_after_uninstall(self, strategy):
        strategy.mount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        strategy.unmount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        stem = strategy._unit_stem(self.MOUNTPOINT)
        assert not (self.UNIT_DIR / f"{stem}.mount").exists()
        assert not (self.UNIT_DIR / f"{stem}.automount").exists()

    def test_automount_unit_disabled_after_uninstall(self, strategy):
        strategy.mount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        strategy.unmount_permanent(self.MOUNTPOINT, fstab_file=self.UNIT_DIR)
        stem = strategy._unit_stem(self.MOUNTPOINT)
        result = subprocess.run(
            ["systemctl", "is-enabled", f"{stem}.automount"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, "Automount unit should be disabled after uninstall"
