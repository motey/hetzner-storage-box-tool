from __future__ import annotations

from pathlib import Path
from typing import Dict, Literal

from hsbt.key_manager import KeyManager
from hsbt.models import Connection, FileInfoCollection
from hsbt.mount.autofs import AutofsMountStrategy
from hsbt.mount.base import MountStrategy
from hsbt.mount.cifs import CifsMountStrategy
from hsbt.mount.rclone import RcloneMountStrategy
from hsbt.mount.sshfs import SshfsMountStrategy
from hsbt.mount.systemd import SystemdMountStrategy
from hsbt.process import CommandResult
from hsbt.transport.ssh import SshTransport

MountTool = Literal["sshfs", "cifs", "rclone", "webdav"]
MountStyle = Literal["fstab", "systemd-automount", "autofs"]


class StorageBox:
    """High-level entry point for interacting with a Hetzner Storage Box.

    Composes an SshTransport for connectivity with pluggable MountStrategy
    objects for the three supported mount methods (sshfs, cifs, rclone).

    Usage::

        box = StorageBox.from_connection(con, binaries=resolve_binaries())
        box.ssh.deploy_public_key_if_not_done()
        box.get_mount_strategy("sshfs").mount_permanent("/mnt/mybox")
    """

    def __init__(
        self,
        host: str,
        user: str,
        key_manager: KeyManager,
        password: str = None,
        remote_dir: str | Path = "/home",
        binaries: Dict[str, str] = None,
    ):
        self.ssh = SshTransport(
            host=host,
            user=user,
            key_manager=key_manager,
            password=password,
            remote_dir=remote_dir,
            binaries=binaries,
        )

    @classmethod
    def from_connection(cls, con: Connection, binaries: Dict[str, str] = None) -> StorageBox:
        return cls(
            host=con.host,
            user=con.user,
            key_manager=KeyManager(target_dir=con.key_dir, identifier=con.identifier),
            binaries=binaries,
        )

    # ------------------------------------------------------------------
    # Mount strategy factory
    # ------------------------------------------------------------------

    def get_mount_strategy(
        self,
        tool: MountTool,
        mount_style: MountStyle = "fstab",
        rclone_config_path: Path | None = None,
        smb_username: str | None = None,
        smb_password: str | None = None,
        smb_domain: str | None = None,
        webdav_password: str | None = None,
    ) -> MountStrategy:
        if mount_style in ("systemd-automount", "autofs"):
            if tool not in ("sshfs", "cifs"):
                raise ValueError(
                    f"mount_style='{mount_style}' only supports tool='sshfs' or tool='cifs', "
                    f"got '{tool}'."
                )
            _tool = tool  # type: ignore[assignment]  # narrowed above
            if mount_style == "systemd-automount":
                return SystemdMountStrategy(
                    self.ssh,
                    mount_tool=_tool,
                    smb_username=smb_username,
                    smb_password=smb_password,
                    smb_domain=smb_domain,
                )
            return AutofsMountStrategy(
                self.ssh,
                mount_tool=_tool,
                smb_username=smb_username,
                smb_password=smb_password,
                smb_domain=smb_domain,
            )
        if tool == "sshfs":
            return SshfsMountStrategy(self.ssh)
        if tool == "cifs":
            return CifsMountStrategy(
                self.ssh,
                smb_username=smb_username,
                smb_password=smb_password,
                smb_domain=smb_domain,
            )
        if tool == "rclone":
            return RcloneMountStrategy(self.ssh, config_file_path=rclone_config_path)
        if tool == "webdav":
            return RcloneMountStrategy(
                self.ssh,
                config_file_path=rclone_config_path,
                backend="webdav",
                webdav_password=webdav_password,
            )
        raise ValueError(f"Unknown mount tool '{tool}'. Choose: sshfs, cifs, rclone, webdav")

    # ------------------------------------------------------------------
    # Convenience pass-throughs so callers don't import SshTransport
    # ------------------------------------------------------------------

    @property
    def host(self) -> str:
        return self.ssh.host

    @property
    def user(self) -> str:
        return self.ssh.user

    @property
    def key_manager(self) -> KeyManager:
        return self.ssh.key_manager

    def run_remote_command(self, command: str, **kwargs) -> str | CommandResult:
        return self.ssh.run_remote_command(command, **kwargs)

    def upload_file(self, local_path: str | Path, remote_path: str | Path) -> None:
        self.ssh.upload_file(local_path, remote_path)

    def download_file(self, remote_path: str | Path, local_path: str | Path) -> None:
        self.ssh.download_file(remote_path, local_path)

    def list_remote_files(self, remote_path: str | Path = ".") -> FileInfoCollection:
        return self.ssh.list_remote_files(remote_path)

    def get_available_space(self, human_readable: bool = False) -> list:
        return self.ssh.get_available_space(human_readable)

    def public_key_is_deployed(self) -> bool:
        return self.ssh.public_key_is_deployed()

    def deploy_public_key_if_not_done(self) -> bool:
        return self.ssh.deploy_public_key_if_not_done()
