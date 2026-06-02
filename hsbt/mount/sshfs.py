from __future__ import annotations

import logging
import os
from pathlib import Path

from hsbt.config_editor import ConfigFileEditor
from hsbt.mount.base import MountStrategy
from hsbt.process import run_command
from hsbt.transport.ssh import SshTransport
from hsbt.utils import cast_path

__all__ = ["SshfsMountStrategy"]

log = logging.getLogger(__name__)


class SshfsMountStrategy(MountStrategy):
    """Mount via FUSE sshfs."""

    def __init__(self, transport: SshTransport):
        self.transport = transport

    def _ssh_o_options(self) -> dict:
        opts = self.transport._get_ssh_options(pw=None, verbose=False, only_ssh_o_options=True)
        opts.pop("PubkeyAuthentication=", None)
        return opts

    def _fstab_identifier(self, local_mountpoint: Path, remote_path) -> str:
        return f"{self.transport.user}@{self.transport.host}:{remote_path} {local_mountpoint} {self.transport.key_manager.identifier}"

    # ------------------------------------------------------------------
    # MountStrategy interface
    # ------------------------------------------------------------------

    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        rpath = remote_path or self.transport.remote_base_path
        opts = self._ssh_o_options()
        opt_str = ",".join(k + v for k, v in opts.items())
        cmd = (
            f"{self.transport.binaries['sshfs']} "
            f"-o {opt_str},allow_other,default_permissions "
            f"{self.transport.user}@{self.transport.host}:{rpath} {local_mountpoint}"
        )
        local_mountpoint.mkdir(parents=True, exist_ok=True)
        run_command(cmd)

    def mount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/fstab"),
        remote_path: str = None,
        uid: int = None,
        gid: int = None,
    ) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        fstab_file = cast_path(fstab_file)
        if uid is None:
            uid = os.getuid()
        if gid is None:
            gid = os.getgid()
        rpath = remote_path or self.transport.remote_base_path
        opts = self._ssh_o_options()
        opt_str = ",".join(k + v for k, v in opts.items())
        identifier = self._fstab_identifier(local_mountpoint, rpath)
        entry = (
            f"{self.transport.user}@{self.transport.host}:{rpath} {local_mountpoint} fuse.sshfs "
            f"{opt_str},_netdev,delay_connect,users,uid={uid},gid={gid},allow_other,reconnect 0 0"
        )
        fstab = ConfigFileEditor(fstab_file)
        fstab.set_config_entry(entry, identifier=identifier)
        local_mountpoint.mkdir(parents=True, exist_ok=True)
        run_command(f"{self.transport.binaries['mount']} --fstab {fstab_file} -a")
        log.info(f"Mounted '{self.transport.host}' via sshfs at '{local_mountpoint}' (fstab: {fstab_file})")

    def unmount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/fstab"),
    ) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        fstab_file = cast_path(fstab_file)
        rpath = self.transport.remote_base_path
        identifier = self._fstab_identifier(local_mountpoint, rpath)
        run_command(f"{self.transport.binaries['umount']} --fstab {fstab_file} -a")
        ConfigFileEditor(fstab_file).remove_config_entry(identifier)

    def is_mounted(self, local_mountpoint: Path) -> bool:
        result = run_command(
            f"mountpoint -q {cast_path(local_mountpoint)}", raise_error=False
        )
        return result.return_code == 0

    def unmount(self, local_mountpoint: Path) -> None:
        run_command(f"{self.transport.binaries['umount']} {cast_path(local_mountpoint)}")
