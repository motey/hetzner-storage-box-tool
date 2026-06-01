from __future__ import annotations

import grp
import logging
import os
import pwd
from pathlib import Path, PurePath

from hsbt.config_editor import ConfigFileEditor
from hsbt.mount.base import MountStrategy
from hsbt.process import run_command
from hsbt.transport.ssh import SshTransport
from hsbt.utils import cast_path, slugify_string

log = logging.getLogger(__name__)


class SmbCifsSecretManager:
    """Manages a CIFS credentials file (username=, password=, optional domain=)."""

    def __init__(self, target_file: Path | str | None = None, identifier: str = None):
        if identifier is None:
            identifier = "default"
        if target_file is None:
            target_file = Path(
                PurePath(Path.home(), ".cifs", f"hsbt_{slugify_string(identifier)}.secret.cifs")
            )
        target_file = Path(target_file) if not isinstance(target_file, Path) else target_file
        if target_file.exists() and target_file.is_dir():
            raise ValueError(f"Path must be a file, got a directory: '{target_file}'")
        self.target_file = target_file
        self.identifier = identifier

    def create_secret_file(
        self,
        username: str,
        password: str,
        domain: str = None,
        exist_ok: bool = True,
        owner: str = None,
        group: str = None,
        group_writable: bool = False,
    ) -> None:
        creds = {"username": username, "password": password}
        if domain:
            creds["domain"] = domain
        if self.exists():
            if not exist_ok:
                raise FileExistsError(f"Secret file already exists: {self.target_file}")
            try:
                if self.read_secret_file() == creds:
                    return
            except Exception:
                pass
            current = self.target_file.stat().st_mode
            if not (current & 0o200):
                self.target_file.chmod(current | 0o200)
        self.target_file.parent.mkdir(parents=True, exist_ok=True)
        self.target_file.write_text("\n".join(f"{k}={v}" for k, v in creds.items()) + "\n")
        mode = 0o600
        if group_writable:
            mode |= 0o060
        self.target_file.chmod(mode)
        if owner or group:
            uid = pwd.getpwnam(owner).pw_uid if owner else -1
            gid = grp.getgrnam(group).gr_gid if group else -1
            os.chown(self.target_file, uid, gid)

    def read_secret_file(self) -> dict:
        if not self.exists():
            raise FileNotFoundError(f"Secret file not found: {self.target_file}")
        return {
            k.strip(): v.strip()
            for line in self.target_file.read_text().strip().split("\n")
            if line.strip() and "=" in line
            for k, v in [line.split("=", 1)]
        }

    def delete_secret_file(self) -> None:
        if self.exists():
            self.target_file.unlink()

    def exists(self) -> bool:
        return self.target_file.exists()

    def validate_credentials(self) -> bool:
        try:
            creds = self.read_secret_file()
            return all(creds.get(f) for f in ["username", "password"])
        except Exception:
            return False

    def get_mount_credentials_string(self) -> str:
        return f"credentials={self.target_file}"

    def __repr__(self) -> str:
        return f"SmbCifsSecretManager({self.identifier!r}, {self.target_file})"


class CifsMountStrategy(MountStrategy):
    """Mount via CIFS/SMB (Hetzner Storage Box Samba interface)."""

    def __init__(
        self,
        transport: SshTransport,
        smb_username: str = None,
        smb_password: str = None,
        smb_domain: str = None,
    ):
        self.transport = transport
        self.smb_username = smb_username or transport.user
        self.smb_password = smb_password
        self.smb_domain = smb_domain
        self._secrets_manager: SmbCifsSecretManager | None = None

    def _get_secrets_manager(self) -> SmbCifsSecretManager:
        if self._secrets_manager is None:
            self._secrets_manager = SmbCifsSecretManager(
                identifier=self.transport.key_manager.identifier
            )
        return self._secrets_manager

    def _ensure_credentials(self) -> SmbCifsSecretManager:
        sm = self._get_secrets_manager()
        if not sm.validate_credentials():
            if not self.smb_username or not self.smb_password:
                raise ValueError(
                    "SMB credentials are required for CIFS mount. "
                    "Provide smb_username and smb_password."
                )
            sm.create_secret_file(
                username=self.smb_username,
                password=self.smb_password,
                domain=self.smb_domain,
            )
        return sm

    def _smb_share_path(self, remote_path: str | None) -> str:
        rpath = remote_path or ""
        return f"//{self.transport.user}.{self.transport.host}/{rpath}"

    def _fstab_identifier(self, local_mountpoint: Path, remote_path: str | None) -> str:
        return f"{self._smb_share_path(remote_path)} {local_mountpoint}"

    # ------------------------------------------------------------------
    # MountStrategy interface
    # ------------------------------------------------------------------

    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        local_mountpoint = cast_path(local_mountpoint)
        sm = self._ensure_credentials()
        uid, gid = os.getuid(), os.getgid()
        local_mountpoint.mkdir(parents=True, exist_ok=True)
        cmd = (
            f"{self.transport.binaries['mount']} -t cifs "
            f"{self._smb_share_path(remote_path)} {local_mountpoint} "
            f"-o iocharset=utf8,rw,seal,{sm.get_mount_credentials_string()},"
            f"uid={uid},gid={gid},file_mode=0660,dir_mode=0770"
        )
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
        sm = self._ensure_credentials()
        identifier = self._fstab_identifier(local_mountpoint, remote_path)
        entry = (
            f"{self._smb_share_path(remote_path)} {local_mountpoint} cifs "
            f"iocharset=utf8,rw,seal,{sm.get_mount_credentials_string()},"
            f"uid={uid},gid={gid},file_mode=0660,dir_mode=0770 0 0"
        )
        fstab = ConfigFileEditor(fstab_file)
        fstab.set_config_entry(entry, identifier=identifier)
        local_mountpoint.mkdir(parents=True, exist_ok=True)
        run_command(f"{self.transport.binaries['mount']} --fstab {fstab_file} -a")
        log.info(f"Mounted '{self.transport.host}' via CIFS at '{local_mountpoint}' (fstab: {fstab_file})")

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
