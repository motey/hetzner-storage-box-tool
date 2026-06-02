from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from hsbt.mount.autofs import AutofsMountStrategy
from tests.conftest import make_ok, make_err


@pytest.fixture
def autofs(transport):
    return AutofsMountStrategy(transport)


@pytest.fixture
def autofs_cifs(transport):
    return AutofsMountStrategy(
        transport, mount_tool="cifs", smb_username="u", smb_password="p"
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestPathHelpers:
    def test_map_file_contains_identifier(self, autofs, transport, tmp_path):
        path = autofs._map_file_path(tmp_path)
        assert transport.key_manager.identifier in path.name

    def test_map_file_in_autofs_dir(self, autofs, tmp_path):
        path = autofs._map_file_path(tmp_path)
        assert path.parent == tmp_path

    def test_master_file_is_auto_master(self, autofs, tmp_path):
        assert autofs._master_file_path(tmp_path).name == "auto.master"


# ---------------------------------------------------------------------------
# Map entry content — sshfs
# ---------------------------------------------------------------------------

class TestMapEntrySshfs:
    @pytest.fixture
    def entry(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        return autofs._map_entry(mp, None, 1000, 1000)

    def test_starts_with_mountpoint(self, entry, tmp_path):
        assert entry.startswith(str(tmp_path / "mnt" / "mybox"))

    def test_contains_host(self, entry, transport):
        assert transport.host in entry

    def test_contains_user(self, entry, transport):
        assert transport.user in entry

    def test_contains_fstype_sshfs(self, entry):
        assert "fstype=fuse.sshfs" in entry

    def test_contains_identity_file(self, entry, transport):
        assert "IdentityFile=" in entry
        assert str(transport.key_manager.private_key_path) in entry

    def test_contains_uid_gid(self, entry):
        assert "uid=1000" in entry
        assert "gid=1000" in entry

    def test_custom_remote_path(self, autofs, tmp_path):
        mp = tmp_path / "mnt"
        entry = autofs._map_entry(mp, "/backups", 0, 0)
        assert ":/backups" in entry


# ---------------------------------------------------------------------------
# Map entry content — cifs
# ---------------------------------------------------------------------------

class TestMapEntryCifs:
    @pytest.fixture
    def entry(self, autofs_cifs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        with patch("hsbt.mount.autofs.SmbCifsSecretManager") as MockSM:
            instance = MockSM.return_value
            instance.validate_credentials.return_value = True
            instance.target_file = Path("/home/.cifs/creds")
            return autofs_cifs._map_entry(mp, None, 1000, 1000)

    def test_contains_fstype_cifs(self, entry):
        assert "fstype=cifs" in entry

    def test_contains_credentials(self, entry):
        assert "credentials=" in entry

    def test_smb_share_format(self, entry, transport):
        assert f"//{transport.user}.{transport.host}" in entry


# ---------------------------------------------------------------------------
# Master entry
# ---------------------------------------------------------------------------

class TestMasterEntry:
    def test_starts_with_direct_map_indicator(self, autofs, tmp_path):
        map_file = autofs._map_file_path(tmp_path)
        entry = autofs._master_entry(map_file)
        assert entry.startswith("/-")

    def test_contains_map_file_path(self, autofs, tmp_path):
        map_file = autofs._map_file_path(tmp_path)
        entry = autofs._master_entry(map_file)
        assert str(map_file) in entry

    def test_contains_timeout(self, autofs, tmp_path):
        map_file = autofs._map_file_path(tmp_path)
        entry = autofs._master_entry(map_file)
        assert "--timeout=" in entry


# ---------------------------------------------------------------------------
# mount_permanent
# ---------------------------------------------------------------------------

class TestMountPermanent:
    def test_writes_map_file(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        assert map_file.exists()
        assert str(mp) in map_file.read_text()

    def test_writes_auto_master_entry(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        master = autofs._master_file_path(autofs_dir)
        assert master.exists()
        assert "/-" in master.read_text()

    def test_calls_autofs_reload(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()) as mock_rc:
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("autofs" in c for c in calls)

    def test_creates_mountpoint_dir(self, autofs, tmp_path):
        mp = tmp_path / "deep" / "new" / "mnt"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        assert mp.exists()

    def test_idempotent_map_entry(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        # ConfigFileEditor wraps entries in comment markers, so count actual
        # map lines (start with the mountpoint, no '#')
        lines = [l for l in map_file.read_text().splitlines() if l.startswith(str(mp))]
        assert len(lines) == 1

    def test_idempotent_master_entry(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
            autofs.mount_permanent(mp, fstab_file=autofs_dir)
        master = autofs._master_file_path(autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        # Count actual /- lines (not comment markers) pointing to our map file
        lines = [l for l in master.read_text().splitlines()
                 if l.startswith("/-") and str(map_file) in l]
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# unmount_permanent
# ---------------------------------------------------------------------------

class TestUnmountPermanent:
    def _install(self, autofs, mp, autofs_dir):
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp, fstab_file=autofs_dir)

    def test_removes_map_entry(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        self._install(autofs, mp, autofs_dir)
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.unmount_permanent(mp, fstab_file=autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        assert not map_file.exists()

    def test_removes_master_entry_when_map_empty(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        self._install(autofs, mp, autofs_dir)
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.unmount_permanent(mp, fstab_file=autofs_dir)
        master = autofs._master_file_path(autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        assert not map_file.exists()
        assert str(map_file) not in master.read_text()

    def test_keeps_master_entry_when_map_still_has_entries(self, autofs, tmp_path):
        mp1 = tmp_path / "mnt" / "box1"
        mp2 = tmp_path / "mnt" / "box2"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.mount_permanent(mp1, fstab_file=autofs_dir)
            autofs.mount_permanent(mp2, fstab_file=autofs_dir)
            autofs.unmount_permanent(mp1, fstab_file=autofs_dir)
        map_file = autofs._map_file_path(autofs_dir)
        assert map_file.exists()
        assert str(mp2) in map_file.read_text()

    def test_calls_autofs_reload(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        self._install(autofs, mp, autofs_dir)
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()) as mock_rc:
            autofs.unmount_permanent(mp, fstab_file=autofs_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("autofs" in c for c in calls)

    def test_tolerates_missing_map_file(self, autofs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        autofs_dir = tmp_path / "etc"
        autofs_dir.mkdir()
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            autofs.unmount_permanent(mp, fstab_file=autofs_dir)


# ---------------------------------------------------------------------------
# mount() raises, unmount() and is_mounted()
# ---------------------------------------------------------------------------

class TestMountRaisesNotImplemented:
    def test_mount_raises(self, autofs, tmp_path):
        with pytest.raises(NotImplementedError):
            autofs.mount(tmp_path / "mnt")


class TestIsMounted:
    def test_true_when_mountpoint_succeeds(self, autofs, tmp_path):
        with patch("hsbt.mount.autofs.run_command", return_value=make_ok()):
            assert autofs.is_mounted(tmp_path / "mnt") is True

    def test_false_when_mountpoint_fails(self, autofs, tmp_path):
        with patch("hsbt.mount.autofs.run_command", return_value=make_err(return_code=1)):
            assert autofs.is_mounted(tmp_path / "mnt") is False
