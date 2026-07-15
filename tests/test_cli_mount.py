from __future__ import annotations

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from hsbt.cli import cli
from hsbt.models import Connection, ConnectionList
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

    def test_default_tool_is_rclone(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, ["mount", *BASE_ARGS, "--mount-point", str(tmp_path / "mnt")])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[0][0] == "rclone"

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

    def test_systemd_automount_style_succeeds(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "systemd-automount",
            ])
        assert result.exit_code == 0, result.output

    def test_systemd_automount_passes_mount_style(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "systemd-automount",
            ])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[1]["mount_style"] == "systemd-automount"

    def test_autofs_style_succeeds(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "autofs",
            ])
        assert result.exit_code == 0, result.output

    def test_autofs_passes_mount_style(self, runner, tmp_path):
        box, strategy = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "mount-perm", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "autofs",
            ])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[1]["mount_style"] == "autofs"

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

    def test_unmount_systemd_style_passes_mount_style(self, runner, tmp_path):
        box, _ = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "unmount", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "systemd-automount",
            ])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[1]["mount_style"] == "systemd-automount"

    def test_unmount_autofs_style_passes_mount_style(self, runner, tmp_path):
        box, _ = _mock_box()
        with patch("hsbt.cli.mount.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "unmount", *BASE_ARGS,
                "--mount-point", str(tmp_path / "mnt"),
                "--mount-style", "autofs",
            ])
        call_kwargs = box.get_mount_strategy.call_args
        assert call_kwargs[1]["mount_style"] == "autofs"


class TestAutoDetectConnection:
    """build_storage_box auto-selects the sole saved connection when --identifier is omitted."""

    def _make_con_list(self, identifiers):
        cl = ConnectionList()
        for ident in identifiers:
            cl.set_connection(Connection(
                identifier=ident,
                host=f"{ident}.your-storagebox.de",
                user=ident,
                key_dir="/tmp",
            ))
        return cl

    def test_auto_selects_single_connection(self, runner, tmp_path):
        """Single saved connection is used without --identifier; message shown."""
        con_list = self._make_con_list(["mybox"])
        # Use a plain MagicMock (no spec) so that box.ssh.password assignment works.
        box = MagicMock()
        box.host = "mybox.your-storagebox.de"
        box.user = "mybox"
        box.get_mount_strategy.return_value = MagicMock()
        with (
            patch("hsbt.cli._common.ConnectionManager") as MockCM,
            patch("hsbt.cli._common.StorageBox") as MockSB,
        ):
            MockCM.return_value.list_connections.return_value = con_list
            MockSB.from_connection.return_value = box
            result = runner.invoke(cli, ["mount", "--mount-point", str(tmp_path / "mnt")])
        assert result.exit_code == 0, result.output
        assert "Using saved connection 'mybox'" in result.output

    def test_multiple_connections_requires_identifier(self):
        """build_storage_box raises UsageError when multiple connections exist and no identifier given."""
        import click
        from hsbt.cli._common import build_storage_box

        con_list = self._make_con_list(["box1", "box2"])
        with patch("hsbt.cli._common.ConnectionManager") as MockCM:
            MockCM.return_value.list_connections.return_value = con_list
            with pytest.raises(click.UsageError, match="box1"):
                build_storage_box(identifier="", host=None, config_file_path="/tmp/fake.json")

    def test_no_connections_no_host_raises(self):
        """build_storage_box raises UsageError when no connections and no host given."""
        import click
        from hsbt.cli._common import build_storage_box

        con_list = self._make_con_list([])
        with patch("hsbt.cli._common.ConnectionManager") as MockCM:
            MockCM.return_value.list_connections.return_value = con_list
            with pytest.raises(click.UsageError, match="set-connection"):
                build_storage_box(identifier="", host=None, config_file_path="/tmp/fake.json")
