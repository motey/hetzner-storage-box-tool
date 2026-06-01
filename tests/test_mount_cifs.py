from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.mount.cifs import CifsMountStrategy, SmbCifsSecretManager
from tests.conftest import make_ok, make_err


@pytest.fixture
def cifs(transport, tmp_path):
    strategy = CifsMountStrategy(
        transport,
        smb_username="u000001",
        smb_password="hunter2",
    )
    # Pre-wire a tmp_path-scoped secret file so tests don't write to ~/.cifs
    strategy._secrets_manager = SmbCifsSecretManager(
        target_file=tmp_path / "cifs.secret",
        identifier=transport.key_manager.identifier,
    )
    return strategy


class TestSmbSharePath:
    def test_starts_with_double_slash(self, cifs):
        assert cifs._smb_share_path(None).startswith("//")

    def test_contains_user(self, cifs, transport):
        assert transport.user in cifs._smb_share_path(None)

    def test_contains_host(self, cifs, transport):
        assert transport.host in cifs._smb_share_path(None)

    def test_subpath_appended(self, cifs):
        assert "backup" in cifs._smb_share_path("backup")


class TestFstabEntry:
    def test_identifier_contains_share_and_mountpoint(self, cifs, tmp_path):
        mp = tmp_path / "mnt"
        ident = cifs._fstab_identifier(mp, None)
        assert "//" in ident
        assert str(mp) in ident

    def test_entry_contains_cifs_type(self, cifs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount_permanent(mp, fstab_file=fstab)
        assert " cifs " in fstab.read_text()

    def test_entry_contains_credentials(self, cifs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount_permanent(mp, fstab_file=fstab)
        assert "credentials=" in fstab.read_text()

    def test_entry_contains_iocharset(self, cifs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount_permanent(mp, fstab_file=fstab)
        assert "iocharset=utf8" in fstab.read_text()

    def test_entry_is_idempotent(self, cifs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount_permanent(mp, fstab_file=fstab)
            cifs.mount_permanent(mp, fstab_file=fstab)
        assert fstab.read_text().count(" cifs ") == 1

    def test_custom_uid_gid_in_entry(self, cifs, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("")
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount_permanent(mp, fstab_file=fstab, uid=1234, gid=5678)
        content = fstab.read_text()
        assert "uid=1234" in content
        assert "gid=5678" in content


class TestMount:
    def test_mount_command_specifies_cifs_type(self, cifs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()) as mock_rc:
            cifs.mount(mp)
        assert "-t cifs" in mock_rc.call_args[0][0]

    def test_mount_command_contains_share_path(self, cifs, transport, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()) as mock_rc:
            cifs.mount(mp)
        assert "//" in mock_rc.call_args[0][0]

    def test_mount_command_contains_mountpoint(self, cifs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()) as mock_rc:
            cifs.mount(mp)
        assert str(mp) in mock_rc.call_args[0][0]

    def test_mount_creates_mountpoint_directory(self, cifs, tmp_path):
        mp = tmp_path / "new" / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            cifs.mount(mp)
        assert mp.exists()

    def test_mount_without_credentials_raises(self, transport, tmp_path):
        no_creds = CifsMountStrategy(transport)
        # Isolate to tmp_path so test is independent of any ~/.cifs residue
        no_creds._secrets_manager = SmbCifsSecretManager(
            target_file=tmp_path / "no_creds.secret",
            identifier=transport.key_manager.identifier,
        )
        with pytest.raises(ValueError, match="SMB credentials"):
            no_creds.mount(tmp_path / "mnt")

    def test_mount_command_contains_credentials_path(self, cifs, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()) as mock_rc:
            cifs.mount(mp)
        assert "credentials=" in mock_rc.call_args[0][0]


class TestIsMounted:
    def test_true_on_success(self, cifs, tmp_path):
        with patch("hsbt.mount.cifs.run_command", return_value=make_ok()):
            assert cifs.is_mounted(tmp_path / "mnt") is True

    def test_false_on_failure(self, cifs, tmp_path):
        with patch("hsbt.mount.cifs.run_command", return_value=make_err(return_code=1)):
            assert cifs.is_mounted(tmp_path / "mnt") is False
