from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

__all__ = ["MountStrategy"]


class MountStrategy(ABC):
    """Common interface for all mount strategies (sshfs, cifs, rclone)."""

    @abstractmethod
    def mount(self, local_mountpoint: Path, remote_path: str = None) -> None:
        """Perform a transient (non-persistent) mount."""

    @abstractmethod
    def mount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/fstab"),
        remote_path: str = None,
        uid: int = None,
        gid: int = None,
    ) -> None:
        """Add a persistent fstab entry and mount immediately."""

    @abstractmethod
    def unmount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path = Path("/etc/fstab"),
    ) -> None:
        """Remove the fstab entry and unmount."""

    @abstractmethod
    def is_mounted(self, local_mountpoint: Path) -> bool:
        """Return True if local_mountpoint is currently an active mount."""

    @abstractmethod
    def unmount(self, local_mountpoint: Path) -> None:
        """Unmount without modifying fstab."""
