from __future__ import annotations

import pytest

from hsbt.storage_box import StorageBox
from hsbt.mount.autofs import AutofsMountStrategy
from hsbt.mount.cifs import CifsMountStrategy
from hsbt.mount.rclone import RcloneMountStrategy
from hsbt.mount.sshfs import SshfsMountStrategy
from hsbt.mount.systemd import SystemdMountStrategy


@pytest.fixture
def box(connection):
    return StorageBox.from_connection(connection)


class TestFromConnection:
    def test_host_matches(self, box, connection):
        assert box.host == connection.host

    def test_user_matches(self, box, connection):
        assert box.user == connection.user

    def test_key_manager_identifier_matches(self, box, connection):
        assert connection.identifier in box.key_manager.identifier


class TestGetMountStrategy:
    def test_sshfs_returns_correct_type(self, box):
        assert isinstance(box.get_mount_strategy("sshfs"), SshfsMountStrategy)

    def test_cifs_returns_correct_type(self, box):
        s = box.get_mount_strategy("cifs", smb_username="u", smb_password="p")
        assert isinstance(s, CifsMountStrategy)

    def test_rclone_returns_correct_type(self, box):
        assert isinstance(box.get_mount_strategy("rclone"), RcloneMountStrategy)

    def test_unknown_tool_raises(self, box):
        with pytest.raises(ValueError, match="Unknown mount tool"):
            box.get_mount_strategy("nfs")

    def test_systemd_automount_returns_systemd_strategy(self, box):
        s = box.get_mount_strategy("sshfs", mount_style="systemd-automount")
        assert isinstance(s, SystemdMountStrategy)

    def test_systemd_automount_cifs_returns_systemd_strategy(self, box):
        s = box.get_mount_strategy("cifs", mount_style="systemd-automount", smb_username="u", smb_password="p")
        assert isinstance(s, SystemdMountStrategy)
        assert s.mount_tool == "cifs"

    def test_systemd_automount_rejects_rclone(self, box):
        with pytest.raises(ValueError, match="mount_style="):
            box.get_mount_strategy("rclone", mount_style="systemd-automount")

    def test_autofs_returns_autofs_strategy(self, box):
        s = box.get_mount_strategy("sshfs", mount_style="autofs")
        assert isinstance(s, AutofsMountStrategy)

    def test_autofs_cifs_returns_autofs_strategy(self, box):
        s = box.get_mount_strategy("cifs", mount_style="autofs", smb_username="u", smb_password="p")
        assert isinstance(s, AutofsMountStrategy)
        assert s.mount_tool == "cifs"

    def test_autofs_rejects_rclone(self, box):
        with pytest.raises(ValueError, match="mount_style="):
            box.get_mount_strategy("rclone", mount_style="autofs")

    def test_cifs_passes_smb_credentials(self, box):
        s = box.get_mount_strategy("cifs", smb_username="smb_u", smb_password="smb_p", smb_domain="DOM")
        assert isinstance(s, CifsMountStrategy)
        assert s.smb_username == "smb_u"
        assert s.smb_password == "smb_p"
        assert s.smb_domain == "DOM"

    def test_rclone_passes_config_path(self, box, tmp_path):
        cfg = tmp_path / "rclone.conf"
        s = box.get_mount_strategy("rclone", rclone_config_path=cfg)
        assert isinstance(s, RcloneMountStrategy)
        assert s.config_file_path == cfg

    def test_webdav_returns_rclone_strategy(self, box):
        s = box.get_mount_strategy("webdav", webdav_password="p")
        assert isinstance(s, RcloneMountStrategy)

    def test_webdav_backend_attribute_is_webdav(self, box):
        s = box.get_mount_strategy("webdav", webdav_password="p")
        assert s.backend == "webdav"

    def test_webdav_passes_password(self, box):
        s = box.get_mount_strategy("webdav", webdav_password="mypassword")
        assert s.webdav_password == "mypassword"

    def test_webdav_passes_rclone_config_path(self, box, tmp_path):
        cfg = tmp_path / "rclone.conf"
        s = box.get_mount_strategy("webdav", webdav_password="p", rclone_config_path=cfg)
        assert s.config_file_path == cfg


class TestFromConnection:
    def test_key_manager_identifier_derived_from_connection(self, connection):
        box = StorageBox.from_connection(connection)
        assert connection.identifier in box.key_manager.identifier

    def test_key_manager_uses_key_dir_from_connection(self, connection):
        box = StorageBox.from_connection(connection)
        assert connection.key_dir in str(box.key_manager.private_key_path)


class TestPassThroughs:
    def test_host_property(self, box, transport):
        box.ssh = transport
        assert box.host == transport.host

    def test_user_property(self, box, transport):
        box.ssh = transport
        assert box.user == transport.user
