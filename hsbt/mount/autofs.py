from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from hsbt.config_editor import ConfigFileEditor
from hsbt.mount.base import MountStrategy
from hsbt.mount.cifs import SmbCifsSecretManager
from hsbt.process import run_command
from hsbt.transport.ssh import SshTransport
from hsbt.utils import cast_path

__all__ = ["AutofsMountStrategy"]

log = logging.getLogger(__name__)

_AUTOFS_TIMEOUT = 60
_AUTOFS_OPTS = f"--timeout={_AUTOFS_TIMEOUT} --ghost"


class AutofsMountStrategy(MountStrategy):
    """Persistent on-demand mount via autofs.

    Writes a direct-map autofs map file (``/etc/auto.hsbt_{identifier}``) and
    registers it in ``/etc/auto.master`` using a ``/-`` direct-map entry.

    The ``fstab_file`` parameter inherited from :class:`MountStrategy` is
    reinterpreted here as *autofs_dir* (default ``/etc``) so the base-class
    interface stays intact.  The CLI passes the value of ``--fstab-file``
    which defaults to ``/etc`` when ``--mount-style=autofs``.

    Calling :meth:`mount` raises :exc:`NotImplementedError` because autofs
    mounts automatically when the mountpoint is first accessed — there is no
    separate "transient mount" step.
    """

    def __init__(
        self,
        transport: SshTransport,
        mount_tool: Literal["sshfs", "cifs"] = "sshfs",
        smb_username: str | None = None,
        smb_password: str | None = None,
        smb_domain: str | None = None,
    ):
        self.transport = transport
        self.mount_tool = mount_tool
        self.smb_username = smb_username or transport.user
        self.smb_password = smb_password
        self.smb_domain = smb_domain

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _map_file_path(self, autofs_dir: Path) -> Path:
        identifier = self.transport.key_manager.identifier
        return autofs_dir / f"auto.hsbt_{identifier}"

    def _master_file_path(self, autofs_dir: Path) -> Path:
        return autofs_dir / "auto.master"

    # ------------------------------------------------------------------
    # Options builders
    # ------------------------------------------------------------------

    def _sshfs_options(self, uid: int, gid: int) -> str:
        km = self.transport.key_manager
        parts = [
            "fstype=fuse.sshfs",
            f"IdentityFile={km.private_key_path}",
            f"Port={self.transport.port}",
            "StrictHostKeyChecking=yes",
            f"UserKnownHostsFile={km._get_known_host_path()}",
            "allow_other",
            f"uid={uid}",
            f"gid={gid}",
        ]
        return ",".join(parts)

    def _cifs_options(self, uid: int, gid: int, creds_file: Path) -> str:
        parts = [
            "fstype=cifs",
            f"credentials={creds_file}",
            "iocharset=utf8",
            "rw",
            "seal",
            f"uid={uid}",
            f"gid={gid}",
            "file_mode=0660",
            "dir_mode=0770",
        ]
        return ",".join(parts)

    def _ensure_cifs_credentials(self) -> SmbCifsSecretManager:
        sm = SmbCifsSecretManager(identifier=self.transport.key_manager.identifier)
        if not sm.validate_credentials():
            if not self.smb_password:
                raise ValueError(
                    "SMB credentials are required for CIFS autofs mount. "
                    "Provide smb_username and smb_password."
                )
            if self.smb_domain:
                sm.create_secret_file(
                    username=self.smb_username or self.transport.user,
                    password=self.smb_password,
                    domain=self.smb_domain,
                )
            else:
                sm.create_secret_file(
                    username=self.smb_username or self.transport.user,
                    password=self.smb_password,
                )
        return sm

    # ------------------------------------------------------------------
    # Entry content builders
    # ------------------------------------------------------------------

    def _map_entry(
        self,
        mountpoint: Path,
        remote_path: str,
        uid: int,
        gid: int,
    ) -> str:
        """Return the line to write into the autofs direct map file."""
        if self.mount_tool == "cifs":
            sm = self._ensure_cifs_credentials()
            options = self._cifs_options(uid, gid, sm.target_file)
            remote = f"//{self.transport.user}.{self.transport.host}/"
            if remote_path and remote_path.strip("/"):
                remote = f"//{self.transport.user}.{self.transport.host}/{remote_path.strip('/')}"
        else:
            options = self._sshfs_options(uid, gid)
            rpath = remote_path or str(self.transport.remote_base_path)
            remote = f"{self.transport.user}@{self.transport.host}:{rpath}"

        return f"{mountpoint} -{options}  {remote}"

    def _map_identifier(self, mountpoint: Path) -> str:
        """Unique string used by ConfigFileEditor to find/replace this entry."""
        return str(mountpoint)

    def _master_entry(self, map_file: Path) -> str:
        return f"/- {map_file} {_AUTOFS_OPTS}"

    def _master_identifier(self, map_file: Path) -> str:
        return f"/- {map_file}"

    # ------------------------------------------------------------------
    # autofs service reload
    # ------------------------------------------------------------------

    def _reload_autofs(self) -> None:
        result = run_command("systemctl reload autofs", raise_error=False)
        if result.return_code != 0:
            run_command("service autofs restart", raise_error=False)

    # ------------------------------------------------------------------
    # MountStrategy interface
    # ------------------------------------------------------------------

    def mount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc"),
        remote_path: str = None,
        uid: int = None,
        gid: int = None,
    ) -> None:
        autofs_dir = cast_path(fstab_file)
        local_mountpoint = cast_path(local_mountpoint)
        if uid is None:
            uid = os.getuid()
        if gid is None:
            gid = os.getgid()

        map_file = self._map_file_path(autofs_dir)
        master_file = self._master_file_path(autofs_dir)

        # Ensure map file exists before editing
        if not map_file.exists():
            map_file.touch()

        entry = self._map_entry(local_mountpoint, remote_path, uid, gid)
        ConfigFileEditor(map_file).set_config_entry(
            entry, identifier=self._map_identifier(local_mountpoint)
        )

        # Ensure auto.master exists before editing
        if not master_file.exists():
            master_file.touch()

        master_entry = self._master_entry(map_file)
        ConfigFileEditor(master_file).set_config_entry(
            master_entry, identifier=self._master_identifier(map_file)
        )

        local_mountpoint.mkdir(parents=True, exist_ok=True)
        self._reload_autofs()
        log.info(
            f"Installed autofs mount for '{self.transport.host}' at "
            f"'{local_mountpoint}' (map: {map_file})"
        )

    def unmount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc"),
    ) -> None:
        autofs_dir = cast_path(fstab_file)
        local_mountpoint = cast_path(local_mountpoint)

        map_file = self._map_file_path(autofs_dir)
        master_file = self._master_file_path(autofs_dir)

        if map_file.exists():
            ConfigFileEditor(map_file).remove_config_entry(
                self._map_identifier(local_mountpoint)
            )
            remaining = map_file.read_text().strip()
            if not remaining:
                map_file.unlink()
                if master_file.exists():
                    ConfigFileEditor(master_file).remove_config_entry(
                        self._master_identifier(map_file)
                    )

        self._reload_autofs()
        log.info(f"Removed autofs mount for '{local_mountpoint}'")

    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        raise NotImplementedError(
            "Autofs mounts automatically on first access. "
            "Use 'mount_permanent' to install the autofs configuration, "
            "then simply access the mountpoint."
        )

    def unmount(self, local_mountpoint: Path) -> None:
        run_command(
            f"{self.transport.binaries['umount']} {cast_path(local_mountpoint)}",
            raise_error=False,
        )

    def is_mounted(self, local_mountpoint: Path) -> bool:
        result = run_command(
            f"mountpoint -q {cast_path(local_mountpoint)}", raise_error=False
        )
        return result.return_code == 0
