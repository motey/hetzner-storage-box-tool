from __future__ import annotations

import json
import pytest
from click.testing import CliRunner

from hsbt.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cfg(tmp_path):
    return str(tmp_path / "connections.json")


class TestSetConnection:
    def _invoke_set(self, runner, tmp_path, cfg, identifier="testbox", extra_args=None):
        args = [
            "set-connection",
            "--identifier", identifier,
            "--host", "u000001.your-storagebox.de",
            "--user", "u000001",
            "--ssh-key-dir", str(tmp_path / "ssh"),
            "--config-file-path", cfg,
            "--skip-key-deployment",
        ]
        if extra_args:
            args += extra_args
        return runner.invoke(cli, args)

    def test_success_exit_code(self, runner, tmp_path, cfg):
        result = self._invoke_set(runner, tmp_path, cfg)
        assert result.exit_code == 0, result.output

    def test_output_contains_identifier(self, runner, tmp_path, cfg):
        result = self._invoke_set(runner, tmp_path, cfg)
        assert "testbox" in result.output

    def test_config_file_created(self, runner, tmp_path, cfg):
        self._invoke_set(runner, tmp_path, cfg)
        import os
        assert os.path.exists(cfg)

    def test_connection_persisted(self, runner, tmp_path, cfg):
        self._invoke_set(runner, tmp_path, cfg)
        data = json.loads(open(cfg).read())
        assert "testbox" in data["connections"]

    def test_duplicate_without_flag_fails(self, runner, tmp_path, cfg):
        self._invoke_set(runner, tmp_path, cfg)
        result = self._invoke_set(runner, tmp_path, cfg)
        assert result.exit_code != 0

    def test_overwrite_flag_allows_duplicate(self, runner, tmp_path, cfg):
        self._invoke_set(runner, tmp_path, cfg)
        result = self._invoke_set(runner, tmp_path, cfg, extra_args=["--overwrite-existing"])
        assert result.exit_code == 0, result.output

    def test_exists_ok_flag_is_silent_on_duplicate(self, runner, tmp_path, cfg):
        self._invoke_set(runner, tmp_path, cfg)
        result = self._invoke_set(runner, tmp_path, cfg, extra_args=["--exists-ok"])
        assert result.exit_code == 0, result.output


class TestListConnections:
    def test_empty_list_exits_ok(self, runner, cfg):
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg])
        assert result.exit_code == 0

    def test_empty_list_contains_connections_key(self, runner, cfg):
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg])
        assert "connections" in result.output

    def test_shows_added_connection(self, runner, tmp_path, cfg):
        runner.invoke(cli, [
            "set-connection", "-i", "box1", "-h", "h.de", "-u", "u1",
            "-s", str(tmp_path / "ssh"), "-c", cfg, "--skip-key-deployment",
        ])
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg])
        assert "box1" in result.output

    def test_yaml_format_exits_ok(self, runner, cfg):
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg, "--format-output", "yaml"])
        assert result.exit_code == 0

    def test_yaml_format_contains_connections(self, runner, cfg):
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg, "--format-output", "yaml"])
        assert "connections" in result.output


class TestDeleteConnection:
    def test_delete_existing(self, runner, tmp_path, cfg):
        runner.invoke(cli, [
            "set-connection", "-i", "box1", "-h", "h.de", "-u", "u1",
            "-s", str(tmp_path / "ssh"), "-c", cfg, "--skip-key-deployment",
        ])
        result = runner.invoke(cli, ["delete-connection", "-i", "box1", "-c", cfg])
        assert result.exit_code == 0, result.output

    def test_delete_removes_from_list(self, runner, tmp_path, cfg):
        runner.invoke(cli, [
            "set-connection", "-i", "box1", "-h", "h.de", "-u", "u1",
            "-s", str(tmp_path / "ssh"), "-c", cfg, "--skip-key-deployment",
        ])
        runner.invoke(cli, ["delete-connection", "-i", "box1", "-c", cfg])
        result = runner.invoke(cli, ["list-connections", "--config-file-path", cfg])
        assert "box1" not in result.output

    def test_delete_missing_with_missing_ok(self, runner, cfg):
        result = runner.invoke(cli, ["delete-connection", "-i", "ghost", "--missing-ok", "-c", cfg])
        assert result.exit_code == 0

    def test_delete_missing_without_flag_exits_nonzero(self, runner, cfg):
        result = runner.invoke(cli, ["delete-connection", "-i", "ghost", "-c", cfg])
        assert result.exit_code != 0
