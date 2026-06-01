from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.mount.sshfs import SshfsMountStrategy
from tests.conftest import make_ok, make_err


@pytest.fixture
def sshfs(transport):
    return SshfsMountStrategy(transport)


class TestFstabEntry:
    def test_identifier_contains_user_host_mountpoint(self, sshfs, transport):
        mp = Path("/mnt/mybox")
        ident = sshfs._fstab_identifier(mp, "/home")
        assert transport.user in ident
        assert transport.host in ident
        assert "/mnt/mybox" in ident
        assert "/home" in ident

    def test_fstab_entry_written_with_fuse_sshfs(self, sshfs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab)
        assert "fuse.sshfs" in fstab.read_text()

    def test_fstab_entry_contains_host(self, sshfs, transport, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab)
        assert transport.host in fstab.read_text()

    def test_fstab_entry_contains_netdev(self, sshfs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab)
        assert "_netdev" in fstab.read_text()

    def test_fstab_entry_contains_allow_other(self, sshfs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab)
        assert "allow_other" in fstab.read_text()

    def test_fstab_entry_is_idempotent(self, sshfs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab)
            sshfs.mount_permanent(mp, fstab_file=fstab)
        assert fstab.read_text().count("fuse.sshfs") == 1

    def test_custom_uid_gid_in_entry(self, sshfs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount_permanent(mp, fstab_file=fstab, uid=1234, gid=5678)
        content = fstab.read_text()
        assert "uid=1234" in content
        assert "gid=5678" in content


class TestMount:
    def test_mount_command_contains_sshfs(self, sshfs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()) as mock_rc:
            sshfs.mount(mp)
        assert "sshfs" in mock_rc.call_args[0][0]

    def test_mount_command_contains_user_at_host(self, sshfs, transport, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()) as mock_rc:
            sshfs.mount(mp)
        assert f"{transport.user}@{transport.host}" in mock_rc.call_args[0][0]

    def test_mount_command_contains_mountpoint(self, sshfs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()) as mock_rc:
            sshfs.mount(mp)
        assert str(mp) in mock_rc.call_args[0][0]

    def test_mount_creates_mountpoint_directory(self, sshfs, tmp_path):
        mp = tmp_path / "new" / "deep" / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            sshfs.mount(mp)
        assert mp.exists()

    def test_mount_command_includes_allow_other(self, sshfs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()) as mock_rc:
            sshfs.mount(mp)
        assert "allow_other" in mock_rc.call_args[0][0]


class TestIsMounted:
    def test_true_when_mountpoint_command_succeeds(self, sshfs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_ok()):
            assert sshfs.is_mounted(mp) is True

    def test_false_when_mountpoint_command_fails(self, sshfs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.sshfs.run_command", return_value=make_err(return_code=1)):
            assert sshfs.is_mounted(mp) is False
