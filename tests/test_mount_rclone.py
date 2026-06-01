from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.mount.rclone import RcloneMountStrategy
from tests.conftest import make_ok, make_err


@pytest.fixture
def rclone(transport, tmp_path):
    return RcloneMountStrategy(transport, config_file_path=tmp_path / "rclone.conf")


@pytest.fixture
def rclone_no_config(transport):
    return RcloneMountStrategy(transport, config_file_path=None)


class TestConfigHelpers:
    def test_remote_contains_identifier(self, rclone, transport):
        remote = rclone._remote("/home")
        assert transport.key_manager.identifier in remote

    def test_remote_contains_path(self, rclone):
        remote = rclone._remote("/home")
        assert "/home" in remote

    def test_config_param_with_file(self, rclone):
        param = rclone._config_param()
        assert "rclone.conf" in param

    def test_config_param_without_file_is_empty(self, rclone_no_config):
        assert rclone_no_config._config_param() == ""

    def test_fstab_identifier_contains_rclone(self, rclone, tmp_path):
        ident = rclone._fstab_identifier(tmp_path / "mnt", None)
        assert "rclone" in ident

    def test_fstab_identifier_contains_mountpoint(self, rclone, tmp_path):
        mp = tmp_path / "mnt"
        ident = rclone._fstab_identifier(mp, None)
        assert str(mp) in ident


class TestEnsureConfig:
    def test_creates_config_when_missing(self, rclone, transport):
        with patch("hsbt.mount.rclone.run_command") as mock_rc:
            mock_rc.return_value = make_ok(stdout="{}")
            rclone.ensure_config()
        calls = [c[0][0] for c in mock_rc.call_args_list]
        create_calls = [c for c in calls if "config create" in c]
        assert len(create_calls) == 1
        assert transport.host in create_calls[0]
        assert "sftp" in create_calls[0]

    def test_skipped_when_config_matches(self, rclone, transport):
        km = transport.key_manager
        existing = {
            km.identifier: {
                "type": "sftp",
                "host": transport.host,
                "user": transport.user,
                "known_hosts_file": str(km._get_known_host_path()),
                "port": str(transport.port),
                "key_file": str(km.private_key_path),
            }
        }
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok(stdout=json.dumps(existing))) as mock_rc:
            created = rclone.ensure_config()
        assert created is False
        assert mock_rc.call_count == 1

    def test_returns_true_when_created(self, rclone):
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok(stdout="{}")):
            assert rclone.ensure_config() is True


class TestFstabEntry:
    def test_entry_written_with_rclone_type(self, rclone, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                rclone.mount_permanent(mp, fstab_file=fstab)
        assert "rclone" in fstab.read_text()

    def test_entry_contains_netdev(self, rclone, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                rclone.mount_permanent(mp, fstab_file=fstab)
        assert "_netdev" in fstab.read_text()

    def test_entry_is_idempotent(self, rclone, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                rclone.mount_permanent(mp, fstab_file=fstab)
                rclone.mount_permanent(mp, fstab_file=fstab)
        assert fstab.read_text().count(" rclone ") == 1


class TestSync:
    def test_sync_from_remote_calls_rclone_sync(self, rclone, tmp_path):
        local = tmp_path / "sync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()) as mock_rc:
                rclone.sync_from_remote(local)
        cmd = mock_rc.call_args[0][0]
        assert "sync" in cmd
        assert str(local) in cmd

    def test_sync_creates_local_dir(self, rclone, tmp_path):
        local = tmp_path / "new" / "sync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                rclone.sync_from_remote(local)
        assert local.exists()

    def test_bisync_uses_bisync_subcommand(self, rclone, tmp_path):
        local = tmp_path / "bisync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()) as mock_rc:
                rclone.bisync(local)
        assert "bisync" in mock_rc.call_args[0][0]

    def test_bisync_resync_flag(self, rclone, tmp_path):
        local = tmp_path / "bisync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()) as mock_rc:
                rclone.bisync(local, resync=True)
        assert "--resync" in mock_rc.call_args[0][0]

    def test_bisync_no_resync_flag_when_false(self, rclone, tmp_path):
        local = tmp_path / "bisync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()) as mock_rc:
                rclone.bisync(local, resync=False)
        assert "--resync" not in mock_rc.call_args[0][0]

    def test_verbose_flag_passed(self, rclone, tmp_path):
        local = tmp_path / "sync_dir"
        with patch.object(rclone, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()) as mock_rc:
                rclone.sync_from_remote(local, verbose=True)
        assert "--verbose" in mock_rc.call_args[0][0]


class TestIsMounted:
    def test_true_on_success(self, rclone, tmp_path):
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
            assert rclone.is_mounted(tmp_path / "mnt") is True

    def test_false_on_failure(self, rclone, tmp_path):
        with patch("hsbt.mount.rclone.run_command", return_value=make_err(return_code=1)):
            assert rclone.is_mounted(tmp_path / "mnt") is False
