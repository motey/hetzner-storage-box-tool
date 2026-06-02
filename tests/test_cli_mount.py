from __future__ import annotations

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from hsbt.cli import cli
from hsbt.storage_box import StorageBox


@pytest.fixture
def runner():
    return CliRunner()


def _mock_box(host="u000001.your-storagebox.de", user="u000001"):
    box = MagicMock(spec=StorageBox)
    box.host = host
    box.user = user
    strategy = MagicMock()
    box.get_mount_strategy.return_value = strategy
    return box, strategy


BASE_ARGS = ["--host", "u000001.your-storagebox.de", "--user", "u000001", "--ssh-key-dir", "/tmp"]


class TestMountCommand:
    def test_exits_ok(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["mount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt")])
        assert result.exit_code == 0, result.output

    def test_strategy_mount_called(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, ["mount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt")])
        strategy.mount.assert_called_once()

    def test_default_tool_is_sshfs(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, ["mount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt")])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[0][0] == "sshfs"

    def test_cifs_tool_selected(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-tool", "cifs",
                "--smb-username", "smb_u",
                "--smb-password", "smb_p",
            ])
        box.get_mount_strategy.assert_called_once_with(
            "cifs",
            rclone_config_path=None,
            smb_username="smb_u",
            smb_password="smb_p",
            smb_domain=None,
            webdav_password=None,
        )

    def test_rclone_tool_selected(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-tool", "rclone",
            ])
        tool = box.get_mount_strategy.call_args[0][0]
        assert tool == "rclone"

    def test_output_mentions_host(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["mount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt")])
        assert "u000001.your-storagebox.de" in result.output


class TestMountPermCommand:
    def test_exits_ok(self, runner, tmp_path):
        box, strategy = _mock_box()
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--fstab-file", str(fstab),
            ])
        assert result.exit_code == 0, result.output

    def test_mount_permanent_called(self, runner, tmp_path):
        box, strategy = _mock_box()
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--fstab-file", str(fstab),
            ])
        strategy.mount_permanent.assert_called_once()

    def test_systemd_automount_style_raises(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "systemd-automount",
            ])
        assert result.exit_code != 0

    def test_custom_uid_gid_passed(self, runner, tmp_path):
        box, strategy = _mock_box()
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--fstab-file", str(fstab),
                "--uid", "1234", "--gid", "5678",
            ])
        call_kwargs = strategy.mount_permanent.call_args[1]
        assert call_kwargs["uid"] == 1234
        assert call_kwargs["gid"] == 5678


class TestUnmountCommand:
    def test_exits_ok(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "unmount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt"),
            ])
        assert result.exit_code == 0, result.output

    def test_unmount_permanent_called_by_default(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "unmount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt"),
            ])
        strategy.unmount_permanent.assert_called_once()
        strategy.unmount.assert_not_called()

    def test_keep_fstab_calls_unmount_only(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "unmount", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--keep-fstab",
            ])
        strategy.unmount.assert_called_once()
        strategy.unmount_permanent.assert_not_called()
