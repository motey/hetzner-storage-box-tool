from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.mount.rclone import RcloneMountStrategy
from tests.conftest import make_ok, make_err


@pytest.fixture
def webdav(transport, tmp_path):
    return RcloneMountStrategy(
        transport,
        config_file_path=tmp_path / "rclone.conf",
        backend="webdav",
        webdav_password="s3cr3t",
    )


@pytest.fixture
def webdav_no_config(transport):
    return RcloneMountStrategy(
        transport,
        config_file_path=None,
        backend="webdav",
        webdav_password="s3cr3t",
    )


class TestBuildWebdavConfig:
    def test_type_is_webdav(self, webdav, transport):
        cfg = webdav._build_webdav_config()
        assert cfg["type"] == "webdav"

    def test_url_uses_https_and_host(self, webdav, transport):
        cfg = webdav._build_webdav_config()
        assert cfg["url"] == f"https://{transport.host}"

    def test_user_matches_transport(self, webdav, transport):
        cfg = webdav._build_webdav_config()
        assert cfg["user"] == transport.user

    def test_vendor_is_other(self, webdav):
        cfg = webdav._build_webdav_config()
        assert cfg["vendor"] == "other"

    def test_no_key_file_or_port(self, webdav):
        cfg = webdav._build_webdav_config()
        assert "key_file" not in cfg
        assert "port" not in cfg


class TestEnsureWebdavConfig:
    def test_creates_config_when_missing(self, webdav, transport):
        with patch("hsbt.mount.rclone.run_command") as mock_rc:
            mock_rc.return_value = make_ok(stdout="{}")
            webdav.ensure_config()
        calls = [c[0][0] for c in mock_rc.call_args_list]
        create_calls = [c for c in calls if "config create" in c]
        assert len(create_calls) == 1
        assert "webdav" in create_calls[0]
        assert transport.host in create_calls[0]

    def test_create_command_includes_pass(self, webdav):
        with patch("hsbt.mount.rclone.run_command") as mock_rc:
            mock_rc.return_value = make_ok(stdout="{}")
            webdav.ensure_config()
        create_call = next(c[0][0] for c in mock_rc.call_args_list if "config create" in c[0][0])
        assert "pass" in create_call
        assert "s3cr3t" in create_call

    def test_skipped_when_config_matches(self, webdav, transport):
        existing = {
            transport.key_manager.identifier: {
                "type": "webdav",
                "url": f"https://{transport.host}",
                "user": transport.user,
                "vendor": "other",
                "pass": "OBSCURED_VALUE",
            }
        }
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok(stdout=json.dumps(existing))) as mock_rc:
            created = webdav.ensure_config()
        assert created is False
        assert mock_rc.call_count == 1  # only the config dump call

    def test_recreates_when_url_differs(self, webdav, transport):
        existing = {
            transport.key_manager.identifier: {
                "type": "webdav",
                "url": "https://old-host.example.com",
                "user": transport.user,
                "vendor": "other",
                "pass": "OBSCURED_VALUE",
            }
        }
        with patch("hsbt.mount.rclone.run_command") as mock_rc:
            mock_rc.return_value = make_ok(stdout=json.dumps(existing))
            created = webdav.ensure_config()
        assert created is True
        calls = [c[0][0] for c in mock_rc.call_args_list]
        assert any("config create" in c for c in calls)

    def test_recreates_when_pass_missing(self, webdav, transport):
        existing = {
            transport.key_manager.identifier: {
                "type": "webdav",
                "url": f"https://{transport.host}",
                "user": transport.user,
                "vendor": "other",
                # no 'pass' key
            }
        }
        with patch("hsbt.mount.rclone.run_command") as mock_rc:
            mock_rc.return_value = make_ok(stdout=json.dumps(existing))
            created = webdav.ensure_config()
        assert created is True

    def test_raises_without_password(self, transport, tmp_path):
        strategy = RcloneMountStrategy(
            transport,
            config_file_path=tmp_path / "rclone.conf",
            backend="webdav",
            webdav_password=None,
        )
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok(stdout="{}")):
            with pytest.raises(ValueError, match="webdav_password is required"):
                strategy.ensure_config()

    def test_returns_true_when_created(self, webdav):
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok(stdout="{}")):
            assert webdav.ensure_config() is True


class TestWebdavFstabEntry:
    def test_entry_written_with_rclone_type(self, webdav, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(webdav, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                webdav.mount_permanent(mp, fstab_file=fstab)
        assert "rclone" in fstab.read_text()

    def test_entry_contains_netdev(self, webdav, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(webdav, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                webdav.mount_permanent(mp, fstab_file=fstab)
        assert "_netdev" in fstab.read_text()

    def test_entry_is_idempotent(self, webdav, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch.object(webdav, "ensure_config"):
            with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
                webdav.mount_permanent(mp, fstab_file=fstab)
                webdav.mount_permanent(mp, fstab_file=fstab)
        assert fstab.read_text().count(" rclone ") == 1


class TestWebdavRemoteHelpers:
    def test_remote_contains_identifier(self, webdav, transport):
        remote = webdav._remote("/home")
        assert transport.key_manager.identifier in remote

    def test_remote_contains_path(self, webdav):
        remote = webdav._remote("/home")
        assert "/home" in remote

    def test_config_param_with_file(self, webdav):
        param = webdav._config_param()
        assert "rclone.conf" in param

    def test_config_param_without_file_is_empty(self, webdav_no_config):
        assert webdav_no_config._config_param() == ""


class TestWebdavIsMounted:
    def test_true_on_success(self, webdav, tmp_path):
        with patch("hsbt.mount.rclone.run_command", return_value=make_ok()):
            assert webdav.is_mounted(tmp_path / "mnt") is True

    def test_false_on_failure(self, webdav, tmp_path):
        with patch("hsbt.mount.rclone.run_command", return_value=make_err(return_code=1)):
            assert webdav.is_mounted(tmp_path / "mnt") is False
