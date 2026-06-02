from __future__ import annotations

import pytest

from hsbt.cli._common import get_config_file_path, get_rclone_config_path, get_ssh_dir


# ---------------------------------------------------------------------------
# get_config_file_path  — caller_value > HSBT_CONNECTIONS_CONFIG_FILE > HSBT_CENTRAL_CONFIG_DIR > None
# ---------------------------------------------------------------------------

class TestGetConfigFilePath:
    def test_caller_value_wins_over_everything(self, tmp_path, monkeypatch):
        caller = tmp_path / "caller.json"
        monkeypatch.setenv("HSBT_CONNECTIONS_CONFIG_FILE", "/env/path.json")
        monkeypatch.setenv("HSBT_CENTRAL_CONFIG_DIR", str(tmp_path / "central"))
        result = get_config_file_path(str(caller))
        assert result == caller

    def test_env_var_used_when_no_caller(self, tmp_path, monkeypatch):
        env_path = tmp_path / "env.json"
        monkeypatch.setenv("HSBT_CONNECTIONS_CONFIG_FILE", str(env_path))
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        result = get_config_file_path(None)
        assert result == env_path

    def test_central_dir_used_when_no_explicit_or_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HSBT_CONNECTIONS_CONFIG_FILE", raising=False)
        monkeypatch.setenv("HSBT_CENTRAL_CONFIG_DIR", str(tmp_path))
        result = get_config_file_path(None)
        assert result == tmp_path / "config" / "hetzner_sbt_connections.json"

    def test_returns_none_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("HSBT_CONNECTIONS_CONFIG_FILE", raising=False)
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        assert get_config_file_path(None) is None


# ---------------------------------------------------------------------------
# get_ssh_dir  — caller_value > HSBT_SSH_KEY_FILE_DIR > HSBT_CENTRAL_CONFIG_DIR/ssh > None
# ---------------------------------------------------------------------------

class TestGetSshDir:
    def test_caller_value_wins(self, tmp_path, monkeypatch):
        caller = tmp_path / "mykeys"
        monkeypatch.setenv("HSBT_SSH_KEY_FILE_DIR", "/env/ssh")
        result = get_ssh_dir(str(caller))
        assert result == caller

    def test_env_var_used_when_no_caller(self, tmp_path, monkeypatch):
        env_dir = tmp_path / "env_ssh"
        monkeypatch.setenv("HSBT_SSH_KEY_FILE_DIR", str(env_dir))
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        result = get_ssh_dir(None)
        assert result == env_dir

    def test_central_dir_used_when_no_explicit_or_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HSBT_SSH_KEY_FILE_DIR", raising=False)
        monkeypatch.setenv("HSBT_CENTRAL_CONFIG_DIR", str(tmp_path))
        result = get_ssh_dir(None)
        assert result == tmp_path / "ssh"

    def test_returns_none_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("HSBT_SSH_KEY_FILE_DIR", raising=False)
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        assert get_ssh_dir(None) is None


# ---------------------------------------------------------------------------
# get_rclone_config_path  — caller_value > HSBT_RCLONE_CONFIG_FILE > HSBT_CENTRAL_CONFIG_DIR/rclone/rclone.conf > None
# ---------------------------------------------------------------------------

class TestGetRcloneConfigPath:
    def test_caller_value_wins(self, tmp_path, monkeypatch):
        caller = tmp_path / "my.conf"
        monkeypatch.setenv("HSBT_RCLONE_CONFIG_FILE", "/env/rclone.conf")
        result = get_rclone_config_path(str(caller))
        assert result == caller

    def test_env_var_used_when_no_caller(self, tmp_path, monkeypatch):
        env_conf = tmp_path / "env_rclone.conf"
        monkeypatch.setenv("HSBT_RCLONE_CONFIG_FILE", str(env_conf))
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        result = get_rclone_config_path(None)
        assert result == env_conf

    def test_central_dir_used_when_no_explicit_or_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HSBT_RCLONE_CONFIG_FILE", raising=False)
        monkeypatch.setenv("HSBT_CENTRAL_CONFIG_DIR", str(tmp_path))
        result = get_rclone_config_path(None)
        assert result == tmp_path / "rclone" / "rclone.conf"

    def test_returns_none_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("HSBT_RCLONE_CONFIG_FILE", raising=False)
        monkeypatch.delenv("HSBT_CENTRAL_CONFIG_DIR", raising=False)
        assert get_rclone_config_path(None) is None
