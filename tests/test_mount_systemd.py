from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import call, patch

from hsbt.mount.systemd import SystemdMountStrategy, _systemd_escape_path
from tests.conftest import make_ok, make_err


@pytest.fixture
def systemd(transport):
    return SystemdMountStrategy(transport)


@pytest.fixture
def systemd_cifs(transport):
    return SystemdMountStrategy(
        transport, mount_tool="cifs", smb_username="u", smb_password="p"
    )


# ---------------------------------------------------------------------------
# Unit name helpers
# ---------------------------------------------------------------------------

class TestSystemdEscapePath:
    def test_simple_mountpoint(self):
        assert _systemd_escape_path(Path("/mnt/mybox")) == "mnt-mybox"

    def test_nested_mountpoint(self):
        assert _systemd_escape_path(Path("/mnt/data/mybox")) == "mnt-data-mybox"

    def test_root_stripped(self):
        assert not _systemd_escape_path(Path("/mnt/box")).startswith("/")


class TestUnitStem:
    def test_stem_matches_escape(self, systemd):
        mp = Path("/mnt/mybox")
        assert systemd._unit_stem(mp) == "mnt-mybox"

    def test_mount_unit_path(self, systemd, tmp_path):
        mp = Path("/mnt/mybox")
        assert systemd._mount_unit_path(tmp_path, mp) == tmp_path / "mnt-mybox.mount"

    def test_automount_unit_path(self, systemd, tmp_path):
        mp = Path("/mnt/mybox")
        assert systemd._automount_unit_path(tmp_path, mp) == tmp_path / "mnt-mybox.automount"


# ---------------------------------------------------------------------------
# .mount unit content — sshfs
# ---------------------------------------------------------------------------

class TestMountUnitContentSshfs:
    @pytest.fixture
    def content(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        return systemd._generate_mount_unit(mp, None, 1000, 1000)

    def test_contains_fuse_sshfs_type(self, content):
        assert "Type=fuse.sshfs" in content

    def test_contains_host_in_what(self, content, transport):
        assert transport.host in content

    def test_contains_user_in_what(self, content, transport):
        assert transport.user in content

    def test_what_field_format(self, content, transport):
        assert f"What={transport.user}@{transport.host}" in content

    def test_where_contains_mountpoint(self, content, tmp_path):
        assert str(tmp_path / "mnt" / "mybox") in content

    def test_contains_netdev(self, content):
        assert "_netdev" in content

    def test_contains_identity_file(self, content, transport):
        assert "IdentityFile=" in content
        assert str(transport.key_manager.private_key_path) in content

    def test_contains_port(self, content, transport):
        assert f"Port={transport.port}" in content

    def test_contains_uid_gid(self, content):
        assert "uid=1000" in content
        assert "gid=1000" in content

    def test_contains_network_online_after(self, content):
        assert "After=network-online.target" in content

    def test_contains_install_section(self, content):
        assert "[Install]" in content
        assert "WantedBy=multi-user.target" in content

    def test_custom_remote_path(self, systemd, tmp_path):
        mp = tmp_path / "mnt"
        content = systemd._generate_mount_unit(mp, "/backups", 0, 0)
        assert ":/backups" in content


# ---------------------------------------------------------------------------
# .mount unit content — cifs
# ---------------------------------------------------------------------------

class TestMountUnitContentCifs:
    @pytest.fixture
    def content(self, systemd_cifs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        with patch("hsbt.mount.systemd.SmbCifsSecretManager") as MockSM:
            instance = MockSM.return_value
            instance.validate_credentials.return_value = True
            instance.target_file = Path("/home/user/.cifs/hsbt_testbox.secret.cifs")
            return systemd_cifs._generate_mount_unit(mp, None, 1000, 1000)

    def test_contains_cifs_type(self, content):
        assert "Type=cifs" in content

    def test_what_uses_smb_share_format(self, content, transport):
        assert f"//{transport.user}.{transport.host}" in content

    def test_contains_credentials_option(self, content):
        assert "credentials=" in content


# ---------------------------------------------------------------------------
# .automount unit content
# ---------------------------------------------------------------------------

class TestAutomountUnitContent:
    @pytest.fixture
    def content(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        return systemd._generate_automount_unit(mp)

    def test_contains_automount_section(self, content):
        assert "[Automount]" in content

    def test_where_contains_mountpoint(self, content, tmp_path):
        assert str(tmp_path / "mnt" / "mybox") in content

    def test_contains_timeout(self, content):
        assert "TimeoutIdleSec=600" in content

    def test_contains_network_online_after(self, content):
        assert "After=network-online.target" in content

    def test_contains_install_section(self, content):
        assert "[Install]" in content


# ---------------------------------------------------------------------------
# mount_permanent
# ---------------------------------------------------------------------------

class TestMountPermanent:
    def test_writes_mount_unit_file(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        stem = systemd._unit_stem(mp)
        assert (unit_dir / f"{stem}.mount").exists()

    def test_writes_automount_unit_file(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        stem = systemd._unit_stem(mp)
        assert (unit_dir / f"{stem}.automount").exists()

    def test_mount_unit_content_has_type(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        stem = systemd._unit_stem(mp)
        content = (unit_dir / f"{stem}.mount").read_text()
        assert "Type=fuse.sshfs" in content

    def test_calls_daemon_reload(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("daemon-reload" in c for c in calls)

    def test_calls_systemctl_enable(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("enable" in c and "automount" in c for c in calls)

    def test_creates_mountpoint_dir(self, systemd, tmp_path):
        mp = tmp_path / "deep" / "new" / "mnt"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.mount_permanent(mp, fstab_file=unit_dir)
        assert mp.exists()

    def test_cifs_mount_unit_has_cifs_type(self, systemd_cifs, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()), \
             patch("hsbt.mount.systemd.SmbCifsSecretManager") as MockSM:
            instance = MockSM.return_value
            instance.validate_credentials.return_value = True
            instance.target_file = Path("/home/.cifs/creds")
            systemd_cifs.mount_permanent(mp, fstab_file=unit_dir)
        stem = systemd_cifs._unit_stem(mp)
        content = (unit_dir / f"{stem}.mount").read_text()
        assert "Type=cifs" in content


# ---------------------------------------------------------------------------
# unmount_permanent
# ---------------------------------------------------------------------------

class TestUnmountPermanent:
    def _install(self, systemd, mp, unit_dir):
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.mount_permanent(mp, fstab_file=unit_dir)

    def test_removes_mount_unit(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        self._install(systemd, mp, unit_dir)
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.unmount_permanent(mp, fstab_file=unit_dir)
        assert not (unit_dir / "mnt-mybox.mount").exists()

    def test_removes_automount_unit(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        self._install(systemd, mp, unit_dir)
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.unmount_permanent(mp, fstab_file=unit_dir)
        assert not (unit_dir / "mnt-mybox.automount").exists()

    def test_calls_systemctl_disable(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        self._install(systemd, mp, unit_dir)
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.unmount_permanent(mp, fstab_file=unit_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("disable" in c for c in calls)

    def test_calls_daemon_reload_on_removal(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        self._install(systemd, mp, unit_dir)
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.unmount_permanent(mp, fstab_file=unit_dir)
        calls = [str(c) for c in mock_rc.call_args_list]
        assert any("daemon-reload" in c for c in calls)

    def test_tolerates_missing_unit_files(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        unit_dir = tmp_path / "systemd"
        unit_dir.mkdir(parents=True)
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            systemd.unmount_permanent(mp, fstab_file=unit_dir)  # no files to remove


# ---------------------------------------------------------------------------
# mount / unmount / is_mounted
# ---------------------------------------------------------------------------

class TestMount:
    def test_mount_calls_systemctl_start(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.mount(mp)
        assert "start" in mock_rc.call_args[0][0]
        assert "mnt-mybox.mount" in mock_rc.call_args[0][0]

    def test_unmount_calls_systemctl_stop(self, systemd, tmp_path):
        mp = tmp_path / "mnt" / "mybox"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()) as mock_rc:
            systemd.unmount(mp)
        assert "stop" in mock_rc.call_args[0][0]


class TestIsMounted:
    def test_true_when_mountpoint_succeeds(self, systemd, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.systemd.run_command", return_value=make_ok()):
            assert systemd.is_mounted(mp) is True

    def test_false_when_mountpoint_fails(self, systemd, tmp_path):
        mp = tmp_path / "mnt"
        with patch("hsbt.mount.systemd.run_command", return_value=make_err(return_code=1)):
            assert systemd.is_mounted(mp) is False
