from __future__ import annotations

import pytest
from pathlib import Path

from hsbt.config_editor import ConfigFileEditor


def _ed(path: Path, base_id: str = "hsbt") -> ConfigFileEditor:
    return ConfigFileEditor(path, base_identifier=base_id)


class TestSetAndGet:
    def test_write_to_nonexistent_file_creates_it(self, tmp_path):
        f = tmp_path / "fstab"
        _ed(f).set_config_entry("myentry", identifier="mymount")
        assert f.exists()

    def test_written_content_is_readable(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("my fstab line", identifier="box1")
        assert ed.get_config_entry("box1") == ["my fstab line"]

    def test_delimiters_present_in_file(self, tmp_path):
        f = tmp_path / "fstab"
        _ed(f).set_config_entry("entry", identifier="box1")
        content = f.read_text()
        assert "<" in content and ">" in content

    def test_update_replaces_old_content(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("old line", identifier="box1")
        ed.set_config_entry("new line", identifier="box1")
        assert ed.get_config_entry("box1") == ["new line"]
        assert "old line" not in f.read_text()

    def test_update_is_idempotent(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("entry", identifier="box1")
        ed.set_config_entry("entry", identifier="box1")
        assert f.read_text().count("entry") == 1

    def test_multiline_entry(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry(["line one", "line two"], identifier="multi")
        assert ed.get_config_entry("multi") == ["line one", "line two"]

    def test_get_missing_entry_returns_empty(self, tmp_path):
        f = tmp_path / "fstab"
        assert _ed(f).get_config_entry("nonexistent") == []

    def test_get_missing_file_returns_empty(self, tmp_path):
        f = tmp_path / "nonexistent_fstab"
        assert _ed(f).get_config_entry("box1") == []


class TestMultipleEntries:
    def test_independent_entries_coexist(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("entry-a", identifier="a")
        ed.set_config_entry("entry-b", identifier="b")
        assert ed.get_config_entry("a") == ["entry-a"]
        assert ed.get_config_entry("b") == ["entry-b"]

    def test_update_one_leaves_other_intact(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("entry-a", identifier="a")
        ed.set_config_entry("entry-b", identifier="b")
        ed.set_config_entry("entry-a-new", identifier="a")
        assert ed.get_config_entry("a") == ["entry-a-new"]
        assert ed.get_config_entry("b") == ["entry-b"]


class TestRemove:
    def test_remove_clears_entry(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("to remove", identifier="box1")
        ed.remove_config_entry("box1")
        assert ed.get_config_entry("box1") == []
        assert "to remove" not in f.read_text()

    def test_remove_leaves_other_entries(self, tmp_path):
        f = tmp_path / "fstab"
        ed = _ed(f)
        ed.set_config_entry("keep this", identifier="keep")
        ed.set_config_entry("remove this", identifier="remove")
        ed.remove_config_entry("remove")
        assert ed.get_config_entry("keep") == ["keep this"]

    def test_remove_nonexistent_is_silent(self, tmp_path):
        f = tmp_path / "fstab"
        f.write_text("")
        _ed(f).remove_config_entry("ghost")


class TestSurroundingContent:
    def test_preserves_pre_existing_lines(self, tmp_path):
        f = tmp_path / "fstab"
        f.write_text("# existing fstab content\n/dev/sda1 / ext4 defaults 0 1\n")
        ed = _ed(f)
        ed.set_config_entry("new entry", identifier="box1")
        content = f.read_text()
        assert "# existing fstab content" in content
        assert "/dev/sda1" in content
        assert "new entry" in content

    def test_pre_existing_lines_survive_update(self, tmp_path):
        f = tmp_path / "fstab"
        f.write_text("/dev/sda1 / ext4 defaults 0 1\n")
        ed = _ed(f)
        ed.set_config_entry("v1", identifier="box1")
        ed.set_config_entry("v2", identifier="box1")
        assert "/dev/sda1" in f.read_text()
        assert "v2" in f.read_text()


class TestErrors:
    def test_target_is_dir_raises(self, tmp_path):
        with pytest.raises(ValueError):
            _ed(tmp_path).set_config_entry("x", identifier="box1")

    def test_not_writable_raises(self, tmp_path):
        f = tmp_path / "fstab"
        f.write_text("x\n")
        f.chmod(0o444)
        try:
            with pytest.raises(PermissionError):
                _ed(f).set_config_entry("y", identifier="box1")
        finally:
            f.chmod(0o644)
