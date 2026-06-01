from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hsbt.transport.ssh import SshTransport, DeployKeyPasswordMissingError
from tests.conftest import make_ok, make_err


class TestGetSshOptions:
    def test_key_auth_uses_publickey(self, transport):
        opts = transport._get_ssh_options(pw=None)
        joined = " ".join(k + v for k, v in opts.items())
        assert "publickey" in joined

    def test_key_auth_includes_identity_file(self, transport):
        opts = transport._get_ssh_options(pw=None)
        joined = " ".join(k + v for k, v in opts.items())
        assert "IdentityFile=" in joined

    def test_key_auth_strict_host_checking(self, transport):
        opts = transport._get_ssh_options(pw=None)
        joined = " ".join(k + v for k, v in opts.items())
        assert "StrictHostKeyChecking=yes" in joined

    def test_password_auth_disables_pubkey(self, transport):
        opts = transport._get_ssh_options(pw="secret")
        joined = " ".join(k + v for k, v in opts.items())
        assert "PubkeyAuthentication=no" in joined
        assert "PasswordAuthentication=yes" in joined

    def test_password_auth_no_identity_file(self, transport):
        opts = transport._get_ssh_options(pw="secret")
        joined = " ".join(k + v for k, v in opts.items())
        assert "IdentityFile=" not in joined

    def test_verbose_flag_present(self, transport):
        opts = transport._get_ssh_options(verbose=True)
        assert "-v" in opts

    def test_quiet_no_verbose_flag(self, transport):
        opts = transport._get_ssh_options(verbose=False)
        assert "-v" not in opts

    def test_only_o_options_strips_dash_v(self, transport):
        opts = transport._get_ssh_options(verbose=True, only_ssh_o_options=True)
        for key in opts:
            assert not key.startswith("-v")

    def test_port_included(self, transport):
        opts = transport._get_ssh_options()
        joined = " ".join(k + v for k, v in opts.items())
        assert "Port=23" in joined

    def test_known_hosts_file_included(self, transport):
        opts = transport._get_ssh_options()
        joined = " ".join(k + v for k, v in opts.items())
        assert "known_hosts" in joined

    def test_extra_params_merged(self, transport):
        opts = transport._get_ssh_options(extra_params={"-X": ""})
        assert "-X" in opts


class TestInjectBasePath:
    def test_relative_path_appended(self, transport):
        result = transport._inject_base_path("subdir/file.txt")
        assert str(result) == "/home/subdir/file.txt"

    def test_absolute_path_strips_leading_slash(self, transport):
        result = transport._inject_base_path("/absolute/path")
        assert str(result) == "/home/absolute/path"

    def test_dot_stays_under_base(self, transport):
        result = transport._inject_base_path(".")
        assert "home" in str(result)


class TestRunRemoteCommand:
    def test_success_returns_stdout(self, transport):
        with patch("hsbt.transport.ssh.run_command", return_value=make_ok(stdout="hello")):
            result = transport.run_remote_command("echo hello")
        assert result == "hello"

    def test_failure_raises_by_default(self, transport):
        with patch("hsbt.transport.ssh.run_command", return_value=make_err()):
            with pytest.raises(ChildProcessError):
                transport.run_remote_command("bad cmd")

    def test_failure_no_raise_returns_result(self, transport):
        with patch("hsbt.transport.ssh.run_command", return_value=make_err()):
            result = transport.run_remote_command("bad cmd", raise_error=False, return_stdout_only=False)
        assert result.return_code == 1

    def test_retry_with_password_on_failure(self, transport):
        transport.password = "hunter2"
        with patch("hsbt.transport.ssh.run_command", side_effect=[make_err(return_code=1), make_ok(stdout="ok")]):
            result = transport.run_remote_command("cmd", on_keyauth_fail_retry_with_pw=True)
        assert result == "ok"

    def test_no_retry_when_password_not_set(self, transport):
        transport.password = None
        with patch("hsbt.transport.ssh.run_command", return_value=make_err(return_code=1)):
            with pytest.raises(ChildProcessError):
                transport.run_remote_command("cmd")

    def test_dry_run_returns_command_result(self, transport):
        result = transport.run_remote_command("ls", dry_run=True, return_stdout_only=False)
        assert result.command is not None

    def test_dry_run_command_contains_user_at_host(self, transport):
        result = transport.run_remote_command("whoami", dry_run=True, return_stdout_only=False)
        assert "u000001@u000001.your-storagebox.de" in result.command

    def test_scp_executor_used(self, transport):
        result = transport.run_remote_command(":remote/path /local", executor="scp", dry_run=True, return_stdout_only=False)
        assert "scp" in result.command

    def test_return_full_result_when_requested(self, transport):
        with patch("hsbt.transport.ssh.run_command", return_value=make_ok(stdout="data")):
            result = transport.run_remote_command("ls", return_stdout_only=False)
        assert hasattr(result, "return_code")
        assert result.stdout == "data"


class TestDeployKey:
    def test_deploy_raises_without_password_when_key_not_deployed(self, transport):
        transport.password = None
        with patch.object(transport.key_manager, "validate_if_keys_exists_and_valid", return_value=True):
            with patch.object(transport.key_manager, "create_known_host_entry_if_not_exists"):
                with patch.object(transport, "public_key_is_deployed", return_value=False):
                    with pytest.raises(DeployKeyPasswordMissingError):
                        transport.deploy_public_key_if_not_done()

    def test_deploy_skipped_when_key_already_deployed(self, transport):
        with patch.object(transport.key_manager, "validate_if_keys_exists_and_valid", return_value=True):
            with patch.object(transport.key_manager, "create_known_host_entry_if_not_exists"):
                with patch.object(transport, "public_key_is_deployed", return_value=True):
                    result = transport.deploy_public_key_if_not_done()
        assert result is False

    def test_public_key_is_deployed_true_on_zero_return(self, transport):
        with patch.object(transport, "run_remote_command", return_value=make_ok()):
            assert transport.public_key_is_deployed() is True

    def test_public_key_is_deployed_false_on_255(self, transport):
        with patch.object(transport, "run_remote_command", return_value=make_err(return_code=255)):
            assert transport.public_key_is_deployed() is False
