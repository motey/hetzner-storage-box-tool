from __future__ import annotations

import pytest

from hsbt.models import Connection, ConnectionList, FileInfo, FileInfoCollection
from hsbt.utils import parse_ls_l_output, convert_df_output_to_dict
from tests.conftest import LS_L_HOME, LS_L_SUBDIR, DF_RAW, DF_H


class TestConnection:
    def test_creation(self):
        con = Connection(identifier="box", host="h.de", user="u1", key_dir="/tmp")
        assert con.identifier == "box"
        assert con.host == "h.de"
        assert con.user == "u1"

    def test_round_trip_json(self):
        con = Connection(identifier="box", host="h.de", user="u1", key_dir="/tmp")
        restored = Connection.model_validate_json(con.model_dump_json())
        assert restored == con


class TestConnectionList:
    def _con(self, id_: str = "box") -> Connection:
        return Connection(identifier=id_, host="h.de", user="u1", key_dir="/tmp")

    def test_set_and_get(self):
        cl = ConnectionList()
        cl.set_connection(self._con())
        assert cl.get_connection("box") is not None

    def test_set_duplicate_raises(self):
        cl = ConnectionList()
        cl.set_connection(self._con())
        with pytest.raises(ValueError):
            cl.set_connection(self._con())

    def test_set_overwrite(self):
        cl = ConnectionList()
        cl.set_connection(self._con())
        updated = Connection(identifier="box", host="new.de", user="u2", key_dir="/tmp")
        cl.set_connection(updated, overwrite_existing=True)
        assert cl.get_connection("box").host == "new.de"

    def test_set_exist_ok_is_noop(self):
        cl = ConnectionList()
        cl.set_connection(self._con())
        cl.set_connection(self._con(), exist_ok=True)
        assert cl.get_connection("box").host == "h.de"

    def test_get_missing_returns_none(self):
        assert ConnectionList().get_connection("missing") is None

    def test_remove(self):
        cl = ConnectionList()
        cl.set_connection(self._con())
        cl.remove_connection("box")
        assert cl.get_connection("box") is None

    def test_remove_nonexistent_is_silent(self):
        ConnectionList().remove_connection("no-such")

    def test_extend(self):
        cl1, cl2 = ConnectionList(), ConnectionList()
        cl1.set_connection(self._con("a"))
        cl2.set_connection(self._con("b"))
        cl1.extend_connections(cl2)
        assert cl1.get_connection("a") is not None
        assert cl1.get_connection("b") is not None

    def test_extend_other_wins_on_conflict(self):
        cl1, cl2 = ConnectionList(), ConnectionList()
        cl1.set_connection(Connection(identifier="x", host="old.de", user="u", key_dir="/tmp"))
        cl2.set_connection(Connection(identifier="x", host="new.de", user="u", key_dir="/tmp"))
        cl1.extend_connections(cl2)
        assert cl1.get_connection("x").host == "new.de"

    def test_json_roundtrip(self):
        cl = ConnectionList()
        cl.set_connection(self._con("a"))
        cl.set_connection(self._con("b"))
        restored = ConnectionList.model_validate_json(cl.model_dump_json())
        assert restored.get_connection("a") is not None
        assert restored.get_connection("b") is not None


class TestFileInfoCollection:
    def test_get_returns_none_for_missing(self):
        fic = FileInfoCollection()
        assert fic.get_file_info("missing") is None

    def test_get_returns_custom_default(self):
        fic = FileInfoCollection()
        assert fic.get_file_info("missing", default="sentinel") == "sentinel"

    def test_set_and_get(self):
        fic = FileInfoCollection()
        fi = FileInfo(
            type_="d", permissions="rwxr-xr-x", hardlink_no="2",
            owner="u1", group="u1", size="4096", date="Jan 1 2024", name="mydir",
        )
        fic["mydir"] = fi
        assert fic.get_file_info("mydir") == fi


class TestParseLsOutput:
    def test_home_dir_entries_present(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert "." in fic
        assert ".." in fic
        assert "backup" in fic

    def test_backup_is_directory(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert fic["backup"].type_ == "d"

    def test_backup_owner(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert fic["backup"].owner == "u000001"

    def test_backup_group(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert fic["backup"].group == "u000001"

    def test_backup_size(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert fic["backup"].size == "4"

    def test_backup_date(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert "Aug" in fic["backup"].date
        assert "2023" in fic["backup"].date

    def test_subdir_hidden_dir_present(self):
        fic = parse_ls_l_output(LS_L_SUBDIR)
        assert ".ssh" in fic
        assert "bareos" in fic

    def test_subdir_ssh_permissions(self):
        fic = parse_ls_l_output(LS_L_SUBDIR)
        assert fic[".ssh"].permissions == "rwx------"

    def test_root_parent_entry(self):
        fic = parse_ls_l_output(LS_L_HOME)
        assert fic[".."].owner == "root"

    def test_parse_error_on_malformed_line(self):
        with pytest.raises(ValueError):
            parse_ls_l_output("drwxr-xr-x incomplete")


class TestConvertDfOutput:
    def test_raw_filesystem_name(self):
        rows = convert_df_output_to_dict(DF_RAW)
        assert rows[0]["Filesystem"] == "u000001"

    def test_raw_use_percent(self):
        rows = convert_df_output_to_dict(DF_RAW)
        assert rows[0]["Use%"] == "1%"

    def test_raw_available(self):
        rows = convert_df_output_to_dict(DF_RAW)
        assert rows[0]["Available"] == "10737413120"

    def test_human_readable_size(self):
        rows = convert_df_output_to_dict(DF_H)
        assert rows[0]["Size"] == "10T"

    def test_human_readable_used(self):
        rows = convert_df_output_to_dict(DF_H)
        assert rows[0]["Used"] == "5.0M"

    def test_single_row_result(self):
        rows = convert_df_output_to_dict(DF_RAW)
        assert len(rows) == 1
