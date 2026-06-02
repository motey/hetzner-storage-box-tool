"""
Integration tests for the StorageBox facade against a live Hetzner Storage Box.
"""

from __future__ import annotations

from hsbt.mount.cifs import CifsMountStrategy
from hsbt.mount.rclone import RcloneMountStrategy
from hsbt.mount.sshfs import SshfsMountStrategy


class TestStorageBoxFacade:
    def test_host_and_user_match_env(self, storage_box_live):
        from tests.integration.conftest import _HOST, _USER
        assert storage_box_live.host == _HOST
        assert storage_box_live.user == _USER

    def test_list_remote_files(self, storage_box_live):
        fic = storage_box_live.list_remote_files()
        assert len(fic) >= 2

    def test_get_available_space(self, storage_box_live):
        rows = storage_box_live.get_available_space()
        assert len(rows) >= 1

    def test_get_available_space_human_readable(self, storage_box_live):
        rows = storage_box_live.get_available_space(human_readable=True)
        assert "Size" in rows[0]

    def test_run_remote_command(self, storage_box_live):
        # Hetzner's restricted shell supports df but not echo/whoami.
        result = storage_box_live.run_remote_command("df")
        assert "Filesystem" in result


class TestMountStrategyDispatch:
    """Verifies strategy objects are constructed correctly — no actual mounting."""

    def test_sshfs_strategy_type(self, storage_box_live):
        assert isinstance(storage_box_live.get_mount_strategy("sshfs"), SshfsMountStrategy)

    def test_cifs_strategy_type(self, storage_box_live):
        s = storage_box_live.get_mount_strategy(
            "cifs", smb_username="u", smb_password="p"
        )
        assert isinstance(s, CifsMountStrategy)

    def test_rclone_strategy_type(self, storage_box_live):
        assert isinstance(storage_box_live.get_mount_strategy("rclone"), RcloneMountStrategy)

    def test_sshfs_strategy_has_correct_host(self, storage_box_live):
        s = storage_box_live.get_mount_strategy("sshfs")
        assert s.transport.host == storage_box_live.host

    def test_webdav_strategy_type(self, storage_box_live):
        s = storage_box_live.get_mount_strategy("webdav", webdav_password="p")
        assert isinstance(s, RcloneMountStrategy)

    def test_webdav_strategy_backend(self, storage_box_live):
        s = storage_box_live.get_mount_strategy("webdav", webdav_password="p")
        assert s.backend == "webdav"

    def test_webdav_strategy_has_correct_url(self, storage_box_live):
        s = storage_box_live.get_mount_strategy("webdav", webdav_password="p")
        cfg = s._build_webdav_config()
        assert storage_box_live.host in cfg["url"]
        assert cfg["url"].startswith("https://")
