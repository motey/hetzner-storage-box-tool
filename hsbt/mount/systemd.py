from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from hsbt.mount.base import MountStrategy
from hsbt.mount.cifs import SmbCifsSecretManager
from hsbt.process import run_command
from hsbt.transport.ssh import SshTransport
from hsbt.utils import cast_path

log = logging.getLogger(__name__)


def _systemd_escape_path(mountpoint: Path) -> str:
    """Convert a mount path to a systemd unit name stem.

    Approximates `systemd-escape -p`: strip leading '/', replace '/' with '-'.
    Handles only alphanumeric paths and common separators — sufficient for
    typical storage-box mountpoints.
    """
    return str(mountpoint).lstrip("/").replace("/", "-")


class SystemdMountStrategy(MountStrategy):
    """Persistent mount via systemd .mount + .automount unit files.

    Writes two unit files to *unit_dir* (default /etc/systemd/system):
      - ``{name}.mount``      — defines the actual mount
      - ``{name}.automount``  — triggers the mount on first access

    The ``fstab_file`` parameter inherited from :class:`MountStrategy` is
    reinterpreted here as *unit_dir* so the base-class interface stays intact.
    The CLI passes the value of ``--fstab-file`` which defaults to
    ``/etc/systemd/system`` when ``--mount-style=systemd-automount``.
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
    # Unit name helpers
    # ------------------------------------------------------------------

    def _unit_stem(self, mountpoint: Path) -> str:
        return _systemd_escape_path(cast_path(mountpoint))

    def _mount_unit_path(self, unit_dir: Path, mountpoint: Path) -> Path:
        return unit_dir / f"{self._unit_stem(mountpoint)}.mount"

    def _automount_unit_path(self, unit_dir: Path, mountpoint: Path) -> Path:
        return unit_dir / f"{self._unit_stem(mountpoint)}.automount"

    # ------------------------------------------------------------------
    # Options builders
    # ------------------------------------------------------------------

    def _sshfs_options(self, uid: int, gid: int) -> str:
        km = self.transport.key_manager
        parts = [
            f"IdentityFile={km.private_key_path}",
            f"Port={self.transport.port}",
            "StrictHostKeyChecking=yes",
            f"UserKnownHostsFile={km._get_known_host_path()}",
            "_netdev",
            "delay_connect",
            "allow_other",
            "reconnect",
            f"uid={uid}",
            f"gid={gid}",
        ]
        return ",".join(parts)

    def _cifs_options(self, uid: int, gid: int, creds_file: Path) -> str:
        parts = [
            f"credentials={creds_file}",
            "iocharset=utf8",
            "rw",
            "seal",
            "_netdev",
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
                    "SMB credentials are required for CIFS systemd mount. "
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
    # Unit file content generators
    # ------------------------------------------------------------------

    def _generate_mount_unit(
        self,
        mountpoint: Path,
        remote_path: str,
        uid: int,
        gid: int,
    ) -> str:
        km = self.transport.key_manager
        identifier = km.identifier

        if self.mount_tool == "cifs":
            sm = self._ensure_cifs_credentials()
            what = f"//{self.transport.user}.{self.transport.host}/"
            if remote_path and remote_path.strip("/"):
                what = f"//{self.transport.user}.{self.transport.host}/{remote_path.strip('/')}"
            mount_type = "cifs"
            options = self._cifs_options(uid, gid, sm.target_file)
        else:
            rpath = remote_path or str(self.transport.remote_base_path)
            what = f"{self.transport.user}@{self.transport.host}:{rpath}"
            mount_type = "fuse.sshfs"
            options = self._sshfs_options(uid, gid)

        return (
            f"[Unit]\n"
            f"Description=Hetzner Storage Box - {identifier} at {mountpoint}\n"
            f"After=network-online.target\n"
            f"Wants=network-online.target\n"
            f"\n"
            f"[Mount]\n"
            f"What={what}\n"
            f"Where={mountpoint}\n"
            f"Type={mount_type}\n"
            f"Options={options}\n"
            f"\n"
            f"[Install]\n"
            f"WantedBy=multi-user.target\n"
        )

    def _generate_automount_unit(self, mountpoint: Path) -> str:
        identifier = self.transport.key_manager.identifier
        return (
            f"[Unit]\n"
            f"Description=Automount Hetzner Storage Box - {identifier} at {mountpoint}\n"
            f"After=network-online.target\n"
            f"Wants=network-online.target\n"
            f"\n"
            f"[Automount]\n"
            f"Where={mountpoint}\n"
            f"TimeoutIdleSec=600\n"
            f"\n"
            f"[Install]\n"
            f"WantedBy=multi-user.target\n"
        )

    # ------------------------------------------------------------------
    # MountStrategy interface
    # ------------------------------------------------------------------

    def mount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/systemd/system"),
        remote_path: str = None,
        uid: int = None,
        gid: int = None,
    ) -> None:
        unit_dir = cast_path(fstab_file)
        local_mountpoint = cast_path(local_mountpoint)
        if uid is None:
            uid = os.getuid()
        if gid is None:
            gid = os.getgid()

        unit_dir.mkdir(parents=True, exist_ok=True)
        local_mountpoint.mkdir(parents=True, exist_ok=True)

        mount_unit = self._mount_unit_path(unit_dir, local_mountpoint)
        automount_unit = self._automount_unit_path(unit_dir, local_mountpoint)

        mount_unit.write_text(
            self._generate_mount_unit(local_mountpoint, remote_path, uid, gid)
        )
        automount_unit.write_text(self._generate_automount_unit(local_mountpoint))

        stem = self._unit_stem(local_mountpoint)
        run_command("systemctl daemon-reload")
        run_command(f"systemctl enable --now {stem}.automount")
        log.info(
            f"Installed systemd automount for '{self.transport.host}' at "
            f"'{local_mountpoint}' (units: {unit_dir})"
        )

    def unmount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/systemd/system"),
    ) -> None:
        unit_dir = cast_path(fstab_file)
        local_mountpoint = cast_path(local_mountpoint)
        stem = self._unit_stem(local_mountpoint)

        run_command(
            f"systemctl disable --now {stem}.automount {stem}.mount",
            raise_error=False,
        )

        for unit_file in (
            self._mount_unit_path(unit_dir, local_mountpoint),
            self._automount_unit_path(unit_dir, local_mountpoint),
        ):
            if unit_file.exists():
                unit_file.unlink()

        run_command("systemctl daemon-reload")
        log.info(f"Removed systemd automount for '{local_mountpoint}'")

    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        stem = self._unit_stem(cast_path(local_mountpoint))
        run_command(f"systemctl start {stem}.mount")

    def unmount(self, local_mountpoint: Path) -> None:
        stem = self._unit_stem(cast_path(local_mountpoint))
        run_command(
            f"systemctl stop {stem}.automount {stem}.mount", raise_error=False
        )

    def is_mounted(self, local_mountpoint: Path) -> bool:
        result = run_command(
            f"mountpoint -q {cast_path(local_mountpoint)}", raise_error=False
        )
        return result.return_code == 0
