from __future__ import annotations

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from hsbt.cli import cli
from hsbt.process import CommandResult
from hsbt.storage_box import StorageBox


@pytest.fixture
def runner():
    return CliRunner()


def _mock_box(host="u000001.your-storagebox.de", user="u000001"):
    box = MagicMock(spec=StorageBox)
    box.host = host
    box.user = user
    return box


BASE_ARGS = ["--host", "u000001.your-storagebox.de", "--user", "u000001", "--ssh-key-dir", "/tmp"]


class TestRemoteCmd:
    def test_no_exec_prints_command_string(self, runner):
        box = _mock_box()
        box.run_remote_command.return_value = CommandResult(
            command="ssh ... ls", stdout="", stderr="", return_code=None,
        )
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["remote-cmd", *BASE_ARGS, "--no-exec", "ls"])
        assert result.exit_code == 0
        box.run_remote_command.assert_called_once_with("ls", dry_run=True, return_stdout_only=False)

    def test_exec_prints_stdout(self, runner):
        box = _mock_box()
        box.run_remote_command.return_value = CommandResult(
            command="ssh ...", stdout="file1\nfile2", stderr="", return_code=0,
        )
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["remote-cmd", *BASE_ARGS, "ls"])
        assert "file1" in result.output

    def test_exec_mode_passes_dry_run_false(self, runner):
        box = _mock_box()
        box.run_remote_command.return_value = CommandResult(
            command="ssh ...", stdout="ok", stderr="", return_code=0,
        )
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            runner.invoke(cli, ["remote-cmd", *BASE_ARGS, "df"])
        box.run_remote_command.assert_called_once_with("df", dry_run=False, return_stdout_only=False)


class TestAvailableSpace:
    def test_exits_ok(self, runner):
        box = _mock_box()
        box.get_available_space.return_value = []
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["available-space", *BASE_ARGS])
        assert result.exit_code == 0

    def test_output_contains_disk_info(self, runner):
        box = _mock_box()
        box.get_available_space.return_value = [
            {"Filesystem": "u000001", "Size": "10T", "Used": "5.0M", "Avail": "10T", "Use%": "1%"}
        ]
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["available-space", *BASE_ARGS])
        assert "10T" in result.output

    def test_human_readable_flag_forwarded(self, runner):
        box = _mock_box()
        box.get_available_space.return_value = []
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            runner.invoke(cli, ["available-space", *BASE_ARGS, "--human-readable"])
        box.get_available_space.assert_called_once_with(human_readable=True)

    def test_no_human_readable_flag(self, runner):
        box = _mock_box()
        box.get_available_space.return_value = []
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            runner.invoke(cli, ["available-space", *BASE_ARGS])
        box.get_available_space.assert_called_once_with(human_readable=False)


class TestUpload:
    def test_exits_ok(self, runner, tmp_path):
        box = _mock_box()
        local = tmp_path / "file.txt"
        local.write_text("content")
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["upload", *BASE_ARGS, str(local), "/remote/file.txt"])
        assert result.exit_code == 0, result.output

    def test_upload_file_called_with_paths(self, runner, tmp_path):
        box = _mock_box()
        local = tmp_path / "file.txt"
        local.write_text("content")
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            runner.invoke(cli, ["upload", *BASE_ARGS, str(local), "/remote/file.txt"])
        box.upload_file.assert_called_once_with(str(local), "/remote/file.txt")

    def test_output_mentions_host(self, runner, tmp_path):
        box = _mock_box()
        local = tmp_path / "file.txt"
        local.write_text("content")
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["upload", *BASE_ARGS, str(local), "/remote/file.txt"])
        assert "u000001.your-storagebox.de" in result.output

    def test_missing_local_file_fails(self, runner, tmp_path):
        box = _mock_box()
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, ["upload", *BASE_ARGS, str(tmp_path / "missing.txt"), "/remote/file.txt"])
        assert result.exit_code != 0


class TestDownload:
    def test_exits_ok(self, runner, tmp_path):
        box = _mock_box()
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "download", *BASE_ARGS,
                "/remote/file.txt", str(tmp_path / "local.txt"),
            ])
        assert result.exit_code == 0, result.output

    def test_download_file_called_with_paths(self, runner, tmp_path):
        box = _mock_box()
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            runner.invoke(cli, [
                "download", *BASE_ARGS,
                "/remote/file.txt", str(tmp_path / "local.txt"),
            ])
        box.download_file.assert_called_once_with("/remote/file.txt", str(tmp_path / "local.txt"))

    def test_output_mentions_host(self, runner, tmp_path):
        box = _mock_box()
        with patch("hsbt.cli.transfer.build_storage_box", return_value=box):
            result = runner.invoke(cli, [
                "download", *BASE_ARGS,
                "/remote/file.txt", str(tmp_path / "local.txt"),
            ])
        assert "u000001.your-storagebox.de" in result.output
