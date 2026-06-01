"""
Integration tests for SshTransport against a live Hetzner Storage Box.

All tests depend on the session-scoped `transport_live` fixture and are
skipped automatically when credentials are not available.
"""

from __future__ import annotations

import pytest

from hsbt.models import FileInfo


class TestConnectivity:
    def test_can_run_command(self, transport_live):
        # Hetzner's restricted shell does not support echo/whoami.
        # df is always available and returns non-empty output.
        result = transport_live.run_remote_command("df")
        assert result.strip() != ""

    def test_multiple_sequential_commands(self, transport_live):
        r1 = transport_live.run_remote_command("df")
        r2 = transport_live.run_remote_command("df -h")
        assert r1.strip() != ""
        assert r2.strip() != ""


class TestListFiles:
    def test_home_listing_returns_entries(self, transport_live):
        fic = transport_live.list_remote_files(".")
        assert len(fic) >= 2  # always has . and ..

    def test_entries_are_file_info_objects(self, transport_live):
        fic = transport_live.list_remote_files(".")
        for entry in fic.values():
            assert isinstance(entry, FileInfo)

    def test_dot_entry_is_directory(self, transport_live):
        fic = transport_live.list_remote_files(".")
        assert "." in fic
        assert fic["."].type_ == "d"

    def test_listing_subdir(self, transport_live, remote_workdir):
        # Create a file so the listing isn't empty
        transport_live.run_remote_command(f"touch {remote_workdir}/listing_probe")
        fic = transport_live.list_remote_files(remote_workdir)
        assert "listing_probe" in fic


class TestDiskSpace:
    def test_raw_returns_filesystem_row(self, transport_live):
        rows = transport_live.get_available_space(human_readable=False)
        assert len(rows) >= 1
        assert "Filesystem" in rows[0]
        assert "Available" in rows[0]

    def test_human_readable_returns_row(self, transport_live):
        rows = transport_live.get_available_space(human_readable=True)
        assert len(rows) >= 1
        assert "Size" in rows[0]

    def test_human_readable_size_has_unit(self, transport_live):
        rows = transport_live.get_available_space(human_readable=True)
        size = rows[0]["Size"]
        assert any(size.endswith(unit) for unit in ("T", "G", "M", "K"))

    def test_use_percent_is_parseable(self, transport_live):
        rows = transport_live.get_available_space(human_readable=False)
        pct = rows[0]["Use%"]
        assert pct.endswith("%")
        assert int(pct.rstrip("%")) <= 100


class TestRemoteDirectory:
    def test_create_remote_directory(self, transport_live, remote_workdir):
        subdir = f"{remote_workdir}/mkdir_test"
        transport_live.create_remote_directory(subdir)
        fic = transport_live.list_remote_files(remote_workdir)
        assert "mkdir_test" in fic
        assert fic["mkdir_test"].type_ == "d"

    def test_create_nested_directory(self, transport_live, remote_workdir):
        nested = f"{remote_workdir}/nested/deep/dir"
        transport_live.create_remote_directory(nested)
        # Just verify it doesn't raise; the parent listing shows 'nested'
        fic = transport_live.list_remote_files(remote_workdir)
        assert "nested" in fic


class TestFileTransfer:
    def test_upload_and_download_roundtrip(self, transport_live, remote_workdir, tmp_path):
        content = "integration test payload\nline two\n"
        local_src = tmp_path / "upload.txt"
        local_dst = tmp_path / "download.txt"
        local_src.write_text(content, encoding="utf-8")

        remote_path = f"{remote_workdir}/roundtrip.txt"
        transport_live.upload_file(local_src, remote_path)
        transport_live.download_file(remote_path, local_dst)

        assert local_dst.read_text(encoding="utf-8") == content

    def test_upload_binary_roundtrip(self, transport_live, remote_workdir, tmp_path):
        data = bytes(range(256))
        local_src = tmp_path / "binary.bin"
        local_dst = tmp_path / "binary_dl.bin"
        local_src.write_bytes(data)

        remote_path = f"{remote_workdir}/binary.bin"
        transport_live.upload_file(local_src, remote_path)
        transport_live.download_file(remote_path, local_dst)

        assert local_dst.read_bytes() == data

    def test_uploaded_file_appears_in_listing(self, transport_live, remote_workdir, tmp_path):
        local = tmp_path / "probe.txt"
        local.write_text("probe", encoding="utf-8")
        transport_live.upload_file(local, f"{remote_workdir}/probe.txt")

        fic = transport_live.list_remote_files(remote_workdir)
        assert "probe.txt" in fic
        assert fic["probe.txt"].type_ == "-"
