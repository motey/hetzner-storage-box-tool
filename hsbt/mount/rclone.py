from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from hsbt.config_editor import ConfigFileEditor
from hsbt.mount.base import MountStrategy
from hsbt.process import run_command
from hsbt.transport.ssh import SshTransport
from hsbt.utils import cast_path

log = logging.getLogger(__name__)

_DEFAULT_FSTAB_ARGS = (
    "rw,noauto,nofail,_netdev,x-systemd.automount,args2env,"
    "vfs_cache_mode=writes,cache_dir=/var/cache/rclone"
)


class RcloneMountStrategy(MountStrategy):
    """Mount via rclone (SFTP backend)."""

    def __init__(self, transport: SshTransport, config_file_path: Path | str | None = None):
        self.transport = transport
        self.config_file_path: Path | None = cast_path(config_file_path)

    # ------------------------------------------------------------------
    # rclone config helpers
    # ------------------------------------------------------------------

    def _config_param(self, prefix: str = "--") -> str:
        return f'{prefix}config="{self.config_file_path}"' if self.config_file_path else ""

    def get_existing_config(self, name: str, missing_ok: bool = False) -> dict | None:
        cmd = f"{self.transport.binaries['rclone']} -q {self._config_param()} config dump"
        result = run_command(cmd)
        configs = json.loads(result.stdout) if result.stdout.strip() else {}
        if name in configs:
            return configs[name]
        if missing_ok:
            return None
        raise ValueError(f"No rclone config named '{name}'")

    def ensure_config(self) -> bool:
        """Create rclone sftp config for this connection if it doesn't match. Returns True if created/updated."""
        km = self.transport.key_manager
        expected = dict(
            type="sftp",
            host=self.transport.host,
            user=self.transport.user,
            known_hosts_file=str(km._get_known_host_path()),
            port=str(self.transport.port),
            key_file=str(km.private_key_path),
        )
        existing = self.get_existing_config(km.identifier, missing_ok=True)
        if existing == expected:
            return False
        params = " ".join(f'{k} "{v}"' for k, v in expected.items())
        cmd = f"{self.transport.binaries['rclone']} {self._config_param()} config create {km.identifier} sftp {params}"
        run_command(cmd)
        log.debug(f"Created/updated rclone config '{km.identifier}'")
        return True

    def _remote(self, remote_path: str | Path | None = None) -> str:
        rpath = remote_path or self.transport.remote_base_path
        return f"{self.transport.key_manager.identifier}:{rpath}"

    def _fstab_identifier(self, local_mountpoint: Path, remote_path) -> str:
        return f"{self._remote(remote_path)} {local_mountpoint} rclone"

    # ------------------------------------------------------------------
    # MountStrategy interface
    # ------------------------------------------------------------------

    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        self.ensure_config()
        cmd = (
            f"{self.transport.binaries['rclone']} {self._config_param()} "
            f"mount {self._remote(remote_path)} {local_mountpoint}"
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
        fstab_args: str = _DEFAULT_FSTAB_ARGS,
    ) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        fstab_file = cast_path(fstab_file)
        self.ensure_config()
        config_arg = self._config_param(prefix="")
        all_args = f"{fstab_args},{config_arg}" if config_arg else fstab_args
        identifier = self._fstab_identifier(local_mountpoint, remote_path)
        entry = f"{self._remote(remote_path)} {local_mountpoint} rclone {all_args} 0 0"
        fstab = ConfigFileEditor(fstab_file)
        fstab.set_config_entry(entry, identifier=identifier)
        local_mountpoint.mkdir(parents=True, exist_ok=True)
        run_command(f"{self.transport.binaries['mount']} --fstab {fstab_file} -a")
        log.info(f"Mounted '{self.transport.host}' via rclone at '{local_mountpoint}' (fstab: {fstab_file})")

    def unmount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/fstab"),
    ) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        fstab_file = cast_path(fstab_file)
        identifier = self._fstab_identifier(local_mountpoint, None)
        run_command(f"{self.transport.binaries['umount']} --fstab {fstab_file} -a")
        ConfigFileEditor(fstab_file).remove_config_entry(identifier)

    def is_mounted(self, local_mountpoint: Path) -> bool:
        result = run_command(
            f"mountpoint -q {cast_path(local_mountpoint)}", raise_error=False
        )
        return result.return_code == 0

    def unmount(self, local_mountpoint: Path) -> None:
        run_command(f"{self.transport.binaries['umount']} {cast_path(local_mountpoint)}")

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def sync_from_remote(
        self,
        local_dir: Path,
        remote_path: str = "",
        verbose: bool = False,
    ) -> None:
        local_dir = cast_path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_config()
        cmd = (
            f"{self.transport.binaries['rclone']} {self._config_param()} "
            f"sync {self._remote(remote_path)} {local_dir}"
            + (" --verbose" if verbose else "")
        )
        run_command(cmd)

    def bisync(
        self,
        local_dir: Path,
        remote_path: str = "/",
        resync: bool = False,
        verbose: bool = False,
    ) -> None:
        local_dir = cast_path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_config()
        cmd = (
            f"{self.transport.binaries['rclone']} {self._config_param()} "
            f"bisync {self._remote(remote_path)} {local_dir}"
            + (" --resync" if resync else "")
            + (" --verbose" if verbose else "")
        )
        run_command(cmd)
