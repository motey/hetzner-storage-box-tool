from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path, PurePath
from typing import Dict, Literal, Union

from hsbt.key_manager import KeyManager
from hsbt.models import Connection, FileInfoCollection
from hsbt.process import CommandResult, run_command
from hsbt.utils import cast_path, parse_ls_l_output, convert_df_output_to_dict

__all__ = [
    "DeployKeyPasswordMissingError",
    "SshTransport",
]

log = logging.getLogger(__name__)

_DEFAULT_BINARIES: Dict[str, str] = {
    "ssh": "ssh",
    "ssh-copy-id": "ssh-copy-id",
    "scp": "scp",
    "sshfs": "sshfs",
    "sshpass": "sshpass",
    "rclone": "rclone",
    "mount": "mount",
    "umount": "umount",
}


class DeployKeyPasswordMissingError(Exception):
    pass


class SshTransport:
    """Handles all SSH/SCP communication with a Hetzner Storage Box."""

    def __init__(
        self,
        host: str,
        user: str,
        key_manager: KeyManager,
        password: str = None,
        port: int = 23,
        remote_dir: str | Path = "/home",
        binaries: Dict[str, str] = None,
    ):
        if remote_dir is None:
            remote_dir = "/home"
        if str(remote_dir) == "/":
            log.warning(
                "Root dir '/' set as remote entry point. "
                "Hetzner storage boxes don't expose '/'; use relative paths instead."
            )
        self.host = host
        self.user = user
        self.port = port
        self.password: str = password
        self.key_manager = key_manager
        self.remote_base_path: Path = cast_path(remote_dir)
        self.binaries: Dict[str, str] = {**_DEFAULT_BINARIES, **(binaries or {})}

    @classmethod
    def from_connection(cls, con: Connection, binaries: Dict[str, str] = None) -> SshTransport:
        return cls(
            host=con.host,
            user=con.user,
            key_manager=KeyManager(target_dir=con.key_dir, identifier=con.identifier),
            binaries=binaries,
        )

    # ------------------------------------------------------------------
    # SSH option building
    # ------------------------------------------------------------------

    def _get_ssh_options(
        self,
        pw: str = None,
        verbose: bool = True,
        extra_params: Dict[str, str] = None,
        only_ssh_o_options: bool = False,
    ) -> Dict[str, str]:
        opts: Dict[str, str] = {}
        if verbose:
            opts["-v"] = ""
        opts["-o UserKnownHostsFile="] = str(self.key_manager._get_known_host_path())
        opts["-o Port="] = str(self.port)
        if pw:
            opts["-o PreferredAuthentications="] = "password"
            opts["-o PasswordAuthentication="] = "yes"
            opts["-o PubkeyAuthentication="] = "no"
        else:
            opts["-o StrictHostKeyChecking="] = "yes"
            opts["-o PreferredAuthentications="] = "publickey"
            opts["-o PasswordAuthentication="] = "no"
            opts["-o IdentityFile="] = str(self.key_manager.private_key_path)
            opts["-o IdentitiesOnly="] = "yes"
            opts["-o PubkeyAuthentication="] = "yes"
        if extra_params:
            opts = opts | extra_params
        if only_ssh_o_options:
            return {k.lstrip("-o "): v for k, v in opts.items() if k.startswith("-o ")}
        return opts

    # ------------------------------------------------------------------
    # Remote command execution
    # ------------------------------------------------------------------

    def run_remote_command(
        self,
        command: str,
        pw: str = None,
        executor: Literal["ssh", "scp", "ssh-copy-id"] = "ssh",
        on_keyauth_fail_retry_with_pw: bool = True,
        extra_params: Dict[str, str] = None,
        verbose: bool = False,
        return_stdout_only: bool = True,
        raise_error: bool = True,
        dry_run: bool = False,
    ) -> str | CommandResult:
        opts = self._get_ssh_options(pw=pw, verbose=verbose, extra_params=extra_params)
        if executor == "ssh":
            command = f" {command}"
        sshpass_bin = self.binaries["sshpass"]
        executor_bin = self.binaries[executor]
        sshpass_prefix = f"{sshpass_bin} -e " if pw else ""
        if dry_run and pw:
            sshpass_prefix = f"{sshpass_bin} -p {pw} "
        full_cmd = (
            f"{sshpass_prefix}{executor_bin} "
            f"{' '.join(k + v for k, v in opts.items())} "
            f"{self.user}@{self.host}{command}"
        )
        if dry_run:
            return CommandResult(command=full_cmd)
        result = run_command(full_cmd, extra_envs={"SSHPASS": pw} if pw else {}, raise_error=False)
        if (
            result.return_code != 0
            and on_keyauth_fail_retry_with_pw
            and self.password is not None
        ):
            log.debug(f"Retrying '{command}' with password auth")
            return self.run_remote_command(
                command=command,
                pw=self.password,
                executor=executor,
                on_keyauth_fail_retry_with_pw=False,
                extra_params=extra_params,
                verbose=verbose,
                return_stdout_only=return_stdout_only,
                raise_error=raise_error,
            )
        if result.return_code != 0 and raise_error:
            raise result.error_for_raise
        return result.stdout if return_stdout_only else result

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def public_key_is_deployed(self) -> bool:
        self._ensure_key_manager()
        result: CommandResult = self.run_remote_command(
            "exit",
            on_keyauth_fail_retry_with_pw=False,
            verbose=True,
            return_stdout_only=False,
            raise_error=False,
        )
        if result.return_code == 255:
            log.debug(
                f"Public key '{self.key_manager.public_key_path}' not yet deployed at '{self.host}'. "
                f"Command: `{result.command}`, stderr: `{result.stderr}`"
            )
            return False
        if result.return_code == 0:
            return True
        log.error("Could not determine if key is deployed")
        return False

    def deploy_public_key_if_not_done(self, sftp_mode: bool = False) -> bool:
        """Deploy public key to storage box if not already present.

        Returns True if the key was freshly deployed, False if already present.
        """
        self._ensure_key_manager()
        if not self.key_manager.validate_if_keys_exists_and_valid(raise_if_not_valid=False):
            self.key_manager.ssh_keygen(overwrite_if_exists=True)
        self.key_manager.create_known_host_entry_if_not_exists(self.host, ports=self.port)
        if self.key_manager.private_key_path is None:
            self.key_manager.ssh_keygen(exists_ok=True)
        if self.public_key_is_deployed():
            return False
        if not self.password:
            raise DeployKeyPasswordMissingError(
                f"To deploy '{self.key_manager.public_key_path}' to '{self.host}' for the first time "
                "a password is required. Provide it once; subsequent connections use the key."
            )
        extra = {"-s": ""} if sftp_mode else {}
        result: CommandResult = self.run_remote_command(
            "",
            executor="ssh-copy-id",
            extra_params={"-i ": str(self.key_manager.public_key_path)} | extra,
            verbose=False,
            return_stdout_only=False,
            raise_error=False,
        )
        if 'ssh-copy-id is only supported with the "-s" argument.' in (result.stdout or "") + (result.stderr or ""):
            return self.deploy_public_key_if_not_done(sftp_mode=True)
        if result.error_for_raise:
            raise result.error_for_raise
        return True

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def upload_file(self, local_path: str | Path, remote_path: str | Path) -> None:
        remote = self._inject_base_path(remote_path)
        self._scp_upload(cast_path(local_path), remote)

    def download_file(self, remote_path: str | Path, local_path: str | Path) -> None:
        remote = self._inject_base_path(remote_path)
        self._scp_download(remote, cast_path(local_path))

    def _scp_upload(self, local_path: Path, remote_path: Path) -> None:
        self.run_remote_command(
            f":{remote_path}", extra_params={str(local_path): ""}, executor="scp"
        )

    def _scp_download(self, remote_path: Path, local_path: Path) -> None:
        self.run_remote_command(
            f":{remote_path} {local_path}", executor="scp"
        )

    def list_remote_files(self, remote_path: str | Path = ".") -> FileInfoCollection:
        remote = self._inject_base_path(remote_path)
        return parse_ls_l_output(self.run_remote_command(f"ls -la {remote}"))

    def get_available_space(self, human_readable: bool = False) -> list:
        return convert_df_output_to_dict(
            self.run_remote_command(f"df{' -h' if human_readable else ''}")
        )

    def create_remote_directory(self, path: str | Path) -> None:
        self.run_remote_command(f"mkdir -p {cast_path(path)}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_key_manager(self) -> None:
        if self.key_manager is None:
            self.key_manager = KeyManager(identifier=self.host)

    def _get_remote_authorized_keys(self) -> Path:
        tmp = Path(f"/tmp/{uuid.uuid4().hex}")
        files = self._list_files_raw(".")
        if ".ssh" not in files or "authorized_keys" not in self._list_files_raw(".ssh"):
            self.run_remote_command("mkdir -p .ssh")
            self.run_remote_command("touch .ssh/authorized_keys")
        self._scp_download(Path(".ssh/authorized_keys"), tmp)
        return tmp

    def _list_files_raw(self, remote_path: str) -> FileInfoCollection:
        return parse_ls_l_output(self.run_remote_command(f"ls -la {remote_path}"))

    def _inject_base_path(self, path: str | Path) -> Path:
        p = cast_path(path)
        if p and p.parts and p.parts[0] == "/":
            p = Path(PurePath(*p.parts[1:]))
        return Path(PurePath(self.remote_base_path, p))
