from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.key_manager import KeyManager
from tests.conftest import make_ok, make_err


class TestKeyPaths:
    def test_default_identifier(self, tmp_path):
        km = KeyManager(target_dir=tmp_path)
        assert km.identifier == "hsbt_key"

    def test_custom_identifier(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        assert km.identifier == "hsbt_mybox"

    def test_private_key_path(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        assert km.private_key_path == tmp_path / "hsbt_mybox"

    def test_public_key_path(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        assert km.public_key_path == tmp_path / "hsbt_mybox.pub"

    def test_known_hosts_path(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        assert km._get_known_host_path() == tmp_path / "known_hosts"

    def test_target_dir_is_created(self, tmp_path):
        new_dir = tmp_path / "deep" / "ssh"
        KeyManager(target_dir=new_dir)
        assert new_dir.is_dir()

    def test_file_as_target_raises(self, tmp_path):
        f = tmp_path / "notadir"
        f.write_text("x")
        with pytest.raises(ValueError):
            KeyManager(target_dir=f)


class TestKnownHostEntry:
    def test_missing_known_hosts_file_returns_false(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="test")
        assert km.known_host_entry_exists("somehost.de") is False

    def test_empty_stdout_means_not_found(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="test")
        (tmp_path / "known_hosts").write_text("")
        with patch("hsbt.key_manager.run_command", return_value=make_ok(stdout="")):
            assert km.known_host_entry_exists("somehost.de") is False

    def test_non_empty_stdout_means_found(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="test")
        (tmp_path / "known_hosts").write_text("somehost.de ssh-ed25519 AAAA...\n")
        with patch("hsbt.key_manager.run_command", return_value=make_ok(stdout="somehost.de ssh-ed25519 AAAA...")):
            assert km.known_host_entry_exists("somehost.de") is True

    def test_port_passed_in_command(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="test")
        (tmp_path / "known_hosts").write_text("[host]:23 ssh-ed25519 AAAA...\n")
        with patch("hsbt.key_manager.run_command", return_value=make_ok(stdout="[host]:23 ssh-ed25519 AAAA...")) as mock_rc:
            km.known_host_entry_exists("host", port="23")
        cmd = mock_rc.call_args[0][0]
        assert "-p 23" in cmd

    def test_command_error_returns_false(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="test")
        (tmp_path / "known_hosts").write_text("x\n")
        with patch("hsbt.key_manager.run_command", side_effect=OSError("boom")):
            assert km.known_host_entry_exists("somehost.de") is False


class TestSshKeygen:
    def test_keygen_calls_run_command(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        with patch("hsbt.key_manager.run_command", return_value=make_ok()) as mock_rc:
            with patch.object(km, "validate_if_keys_exists_and_valid", return_value=False):
                km.ssh_keygen()
        mock_rc.assert_called_once()

    def test_keygen_command_contains_algorithm_and_path(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        with patch("hsbt.key_manager.run_command", return_value=make_ok()) as mock_rc:
            with patch.object(km, "validate_if_keys_exists_and_valid", return_value=False):
                km.ssh_keygen()
        cmd = mock_rc.call_args[0][0]
        assert "ssh-keygen" in cmd
        assert "ed25519" in cmd
        assert str(km.private_key_path) in cmd

    def test_keygen_skipped_when_valid_and_exists_ok(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        with patch("hsbt.key_manager.run_command") as mock_rc:
            with patch.object(km, "validate_if_keys_exists_and_valid", return_value=True):
                km.ssh_keygen(exists_ok=True)
        mock_rc.assert_not_called()

    def test_keygen_raises_when_exists_no_flag(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        with patch.object(km, "validate_if_keys_exists_and_valid", return_value=True):
            with pytest.raises(FileExistsError):
                km.ssh_keygen()

    def test_keygen_overwrites_when_flag_set(self, tmp_path):
        km = KeyManager(target_dir=tmp_path, identifier="mybox")
        with patch("hsbt.key_manager.run_command", return_value=make_ok()) as mock_rc:
            with patch.object(km, "validate_if_keys_exists_and_valid", return_value=True):
                km.ssh_keygen(overwrite_if_exists=True)
        mock_rc.assert_called_once()
