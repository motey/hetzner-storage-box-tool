from __future__ import annotations

import json
import pytest
from pathlib import Path

from hsbt.connection_manager import ConnectionManager


def _mgr(tmp_path: Path) -> ConnectionManager:
    return ConnectionManager(target_config_file=tmp_path / "connections.json")


class TestSetAndGet:
    def test_set_and_get(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        con = mgr.get_connection("box1")
        assert con is not None
        assert con.host == "h.de"
        assert con.user == "u1"

    def test_set_creates_config_file(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        assert mgr.target_config_file.exists()

    def test_config_file_is_valid_json(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        data = json.loads(mgr.target_config_file.read_text())
        assert "connections" in data

    def test_get_missing_returns_none(self, tmp_path):
        assert _mgr(tmp_path).get_connection("missing") is None

    def test_get_missing_returns_custom_default(self, tmp_path):
        assert _mgr(tmp_path).get_connection("missing", default="sentinel") == "sentinel"

    def test_overwrite_existing(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="old.de", key_dir=str(tmp_path))
        mgr.set_connection("box1", user="u2", host="new.de", key_dir=str(tmp_path), overwrite_existing=True)
        assert mgr.get_connection("box1").host == "new.de"

    def test_duplicate_without_overwrite_raises(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        with pytest.raises(ValueError):
            mgr.set_connection("box1", user="u2", host="h2.de", key_dir=str(tmp_path), exists_ok=False)

    def test_exists_ok_is_noop(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        mgr.set_connection("box1", user="u9", host="h9.de", key_dir=str(tmp_path), exists_ok=True)
        assert mgr.get_connection("box1").host == "h.de"


class TestDelete:
    def test_delete_existing(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("box1", user="u1", host="h.de", key_dir=str(tmp_path))
        deleted = mgr.delete_connection("box1")
        assert deleted is True
        assert mgr.get_connection("box1") is None

    def test_delete_missing_raises(self, tmp_path):
        with pytest.raises(ValueError):
            _mgr(tmp_path).delete_connection("nonexistent")

    def test_delete_missing_ok(self, tmp_path):
        result = _mgr(tmp_path).delete_connection("nonexistent", missing_ok=True)
        assert result is False

    def test_delete_one_leaves_others(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("a", user="u1", host="h1.de", key_dir=str(tmp_path))
        mgr.set_connection("b", user="u2", host="h2.de", key_dir=str(tmp_path))
        mgr.delete_connection("a")
        assert mgr.get_connection("a") is None
        assert mgr.get_connection("b") is not None


class TestList:
    def test_list_empty(self, tmp_path):
        assert _mgr(tmp_path).list_connections().connections == {}

    def test_list_multiple(self, tmp_path):
        mgr = _mgr(tmp_path)
        mgr.set_connection("a", user="u1", host="h1.de", key_dir=str(tmp_path))
        mgr.set_connection("b", user="u2", host="h2.de", key_dir=str(tmp_path))
        cl = mgr.list_connections()
        assert "a" in cl.connections
        assert "b" in cl.connections

    def test_list_from_specific_file(self, tmp_path):
        cfg = tmp_path / "custom.json"
        mgr = ConnectionManager(target_config_file=cfg)
        mgr.set_connection("x", user="u1", host="h.de", key_dir=str(tmp_path))
        cl = mgr.list_connections(from_specific_config_file=cfg)
        assert "x" in cl.connections


class TestMultiSourceBehavior:
    def _two_source_mgr(self, tmp_path):
        file1 = tmp_path / "f1.json"
        file2 = tmp_path / "f2.json"
        mgr = ConnectionManager(target_config_file=file1)
        mgr._alt_sources = [file2]
        mgr2 = ConnectionManager(target_config_file=file2)
        return mgr, mgr2, file1, file2

    def test_get_returns_from_primary_when_present_in_both(self, tmp_path):
        mgr, mgr2, _, _ = self._two_source_mgr(tmp_path)
        mgr.set_connection("box", user="u1", host="primary.de", key_dir=str(tmp_path))
        mgr2.set_connection("box", user="u2", host="alt.de", key_dir=str(tmp_path))
        result = mgr.get_connection("box")
        assert result.host == "primary.de"

    def test_get_falls_back_to_alt_source(self, tmp_path):
        mgr, mgr2, _, _ = self._two_source_mgr(tmp_path)
        mgr2.set_connection("box", user="u2", host="alt.de", key_dir=str(tmp_path))
        result = mgr.get_connection("box")
        assert result is not None
        assert result.host == "alt.de"

    def test_list_merges_entries_from_all_sources(self, tmp_path):
        mgr, mgr2, _, _ = self._two_source_mgr(tmp_path)
        mgr.set_connection("a", user="u1", host="h1.de", key_dir=str(tmp_path))
        mgr2.set_connection("b", user="u2", host="h2.de", key_dir=str(tmp_path))
        cl = mgr.list_connections()
        assert "a" in cl.connections
        assert "b" in cl.connections

    def test_delete_succeeds_when_found_in_alt_source(self, tmp_path):
        mgr, mgr2, _, _ = self._two_source_mgr(tmp_path)
        mgr2.set_connection("alt-only", user="u2", host="h2.de", key_dir=str(tmp_path))
        deleted = mgr.delete_connection("alt-only")
        assert deleted is True

    def test_delete_unwritable_file_raises_permission_error(self, tmp_path):
        mgr, _, file1, _ = self._two_source_mgr(tmp_path)
        mgr.set_connection("box", user="u", host="h.de", key_dir=str(tmp_path))
        file1.chmod(0o444)
        try:
            with pytest.raises(PermissionError):
                mgr.delete_connection("box")
        finally:
            file1.chmod(0o644)
