from __future__ import annotations

import stat
import pytest
from pathlib import Path

from hsbt.mount.cifs import SmbCifsSecretManager


@pytest.fixture
def sm(tmp_path):
    return SmbCifsSecretManager(
        target_file=tmp_path / "cifs" / "test.secret.cifs",
        identifier="testbox",
    )


class TestCreateAndRead:
    def test_create_and_read_basic(self, sm):
        sm.create_secret_file("user1", "pass1")
        creds = sm.read_secret_file()
        assert creds["username"] == "user1"
        assert creds["password"] == "pass1"

    def test_create_with_domain(self, sm):
        sm.create_secret_file("user1", "pass1", domain="WORKGROUP")
        creds = sm.read_secret_file()
        assert creds["domain"] == "WORKGROUP"

    def test_create_without_domain_has_no_domain_key(self, sm):
        sm.create_secret_file("u", "p")
        assert "domain" not in sm.read_secret_file()

    def test_creates_parent_directory(self, sm):
        sm.create_secret_file("u", "p")
        assert sm.target_file.parent.is_dir()


class TestPermissions:
    def test_default_mode_is_600(self, sm):
        sm.create_secret_file("u", "p")
        assert stat.S_IMODE(sm.target_file.stat().st_mode) == 0o600

    def test_group_writable_mode_is_660(self, sm):
        sm.create_secret_file("u", "p", group_writable=True)
        assert stat.S_IMODE(sm.target_file.stat().st_mode) == 0o660


class TestIdempotency:
    def test_same_credentials_no_rewrite(self, sm):
        sm.create_secret_file("u", "p")
        mtime1 = sm.target_file.stat().st_mtime_ns
        sm.create_secret_file("u", "p")
        mtime2 = sm.target_file.stat().st_mtime_ns
        assert mtime1 == mtime2

    def test_changed_credentials_rewrite(self, sm):
        sm.create_secret_file("u", "old")
        sm.create_secret_file("u", "new")
        assert sm.read_secret_file()["password"] == "new"

    def test_exist_ok_false_raises_when_exists(self, sm):
        sm.create_secret_file("u", "p")
        with pytest.raises(FileExistsError):
            sm.create_secret_file("u", "p2", exist_ok=False)


class TestDelete:
    def test_delete_removes_file(self, sm):
        sm.create_secret_file("u", "p")
        sm.delete_secret_file()
        assert not sm.exists()

    def test_delete_nonexistent_is_silent(self, sm):
        sm.delete_secret_file()

    def test_exists_false_before_create(self, sm):
        assert sm.exists() is False

    def test_exists_true_after_create(self, sm):
        sm.create_secret_file("u", "p")
        assert sm.exists() is True

    def test_read_nonexistent_raises(self, sm):
        with pytest.raises(FileNotFoundError):
            sm.read_secret_file()


class TestValidate:
    def test_validate_true_with_both_fields(self, sm):
        sm.create_secret_file("u", "p")
        assert sm.validate_credentials() is True

    def test_validate_false_when_missing(self, sm):
        assert sm.validate_credentials() is False


class TestCredentialsString:
    def test_starts_with_credentials_equals(self, sm):
        assert sm.get_mount_credentials_string().startswith("credentials=")

    def test_contains_file_path(self, sm):
        assert str(sm.target_file) in sm.get_mount_credentials_string()


class TestConstructor:
    def test_default_path_includes_identifier(self):
        sm = SmbCifsSecretManager(identifier="my-box")
        assert "hsbt_my" in str(sm.target_file)

    def test_directory_as_target_raises(self, tmp_path):
        with pytest.raises(ValueError):
            SmbCifsSecretManager(target_file=tmp_path)


class TestChown:
    def test_chown_called_with_correct_uid_when_owner_set(self, sm):
        from unittest.mock import MagicMock, patch
        with patch("hsbt.mount.cifs.pwd.getpwnam") as mock_getpwnam:
            with patch("hsbt.mount.cifs.os.chown") as mock_chown:
                mock_getpwnam.return_value = MagicMock(pw_uid=1234)
                sm.create_secret_file("u", "p", owner="someuser")
        mock_chown.assert_called_once()
        _, uid, _ = mock_chown.call_args[0]
        assert uid == 1234

    def test_chown_called_with_correct_gid_when_group_set(self, sm):
        from unittest.mock import MagicMock, patch
        with patch("hsbt.mount.cifs.grp.getgrnam") as mock_getgrnam:
            with patch("hsbt.mount.cifs.os.chown") as mock_chown:
                mock_getgrnam.return_value = MagicMock(gr_gid=5678)
                sm.create_secret_file("u", "p", group="somegroup")
        mock_chown.assert_called_once()
        _, _, gid = mock_chown.call_args[0]
        assert gid == 5678

    def test_chown_not_called_without_owner_or_group(self, sm):
        from unittest.mock import patch
        with patch("hsbt.mount.cifs.os.chown") as mock_chown:
            sm.create_secret_file("u", "p")
        mock_chown.assert_not_called()


class TestMalformedFile:
    def test_lines_without_equals_are_skipped(self, sm):
        sm.target_file.parent.mkdir(parents=True, exist_ok=True)
        sm.target_file.write_text("username=user1\nno_equals_here\npassword=pass1\n")
        creds = sm.read_secret_file()
        assert creds == {"username": "user1", "password": "pass1"}

    def test_value_containing_equals_is_preserved(self, sm):
        sm.target_file.parent.mkdir(parents=True, exist_ok=True)
        sm.target_file.write_text("username=user1\npassword=p=ss=word\n")
        creds = sm.read_secret_file()
        assert creds["password"] == "p=ss=word"
