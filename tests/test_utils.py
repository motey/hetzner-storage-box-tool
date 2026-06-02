from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hsbt.utils import (
    RequirementMissing,
    cast_path,
    convert_df_output_to_dict,
    download_file,
    get_external_executable_path,
    is_root,
    parse_ls_l_output,
    slugify_string,
    unzip_file,
)
from tests.conftest import LS_L_HOME, LS_L_SUBDIR, DF_RAW


# ---------------------------------------------------------------------------
# cast_path
# ---------------------------------------------------------------------------

class TestCastPath:
    def test_none_returns_none(self):
        assert cast_path(None) is None

    def test_str_returns_path(self, tmp_path):
        result = cast_path(str(tmp_path))
        assert isinstance(result, Path)
        assert result == tmp_path

    def test_path_returns_path(self, tmp_path):
        assert cast_path(tmp_path) == tmp_path

    def test_list_joins_parts(self, tmp_path):
        result = cast_path([str(tmp_path), "sub", "file.txt"])
        assert result == tmp_path / "sub" / "file.txt"

    def test_tilde_is_expanded(self):
        result = cast_path("~/something")
        assert "~" not in str(result)

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError):
            cast_path(42)


# ---------------------------------------------------------------------------
# slugify_string
# ---------------------------------------------------------------------------

class TestSlugifyString:
    def test_spaces_become_spacer(self):
        assert slugify_string("hello world") == "hello-world"

    def test_custom_spacer(self):
        assert slugify_string("hello world", spacer_char="_") == "hello_world"

    def test_uppercase_lowercased(self):
        assert slugify_string("HELLO") == "hello"

    def test_alphanumeric_preserved(self):
        assert slugify_string("abc123") == "abc123"

    def test_special_chars_dropped(self):
        # Non-alnum, non-space chars are filtered out entirely
        assert slugify_string("hello!world") == "helloworld"

    def test_empty_string(self):
        assert slugify_string("") == ""

    def test_mixed(self):
        # '#' is not alnum and not a space, so it is dropped entirely
        result = slugify_string("My Box #1")
        assert result == "my-box-1"


# ---------------------------------------------------------------------------
# is_root
# ---------------------------------------------------------------------------

class TestIsRoot:
    def test_true_when_uid_is_zero(self):
        with patch("hsbt.utils.os.geteuid", return_value=0):
            assert is_root() is True

    def test_false_when_uid_is_nonzero(self):
        with patch("hsbt.utils.os.geteuid", return_value=1000):
            assert is_root() is False


# ---------------------------------------------------------------------------
# get_external_executable_path
# ---------------------------------------------------------------------------

class TestGetExternalExecutablePath:
    def test_env_var_override_for_known_binary(self, monkeypatch):
        monkeypatch.setenv("HSBT_BIN_PATH_RCLONE", "/custom/rclone")
        result = get_external_executable_path("rclone", raise_error=False)
        assert str(result) == "/custom/rclone"

    def test_shutil_which_used_for_unknown_binary(self):
        with patch("hsbt.utils.shutil.which", return_value="/usr/bin/git") as mock_which:
            result = get_external_executable_path("git", raise_error=False)
        mock_which.assert_called_once_with("git")
        assert str(result) == "/usr/bin/git"

    def test_raises_requirement_missing_when_not_found(self):
        with patch("hsbt.utils.shutil.which", return_value=None):
            with pytest.raises(RequirementMissing):
                get_external_executable_path("nonexistent_binary_xyz_abc")

    def test_returns_none_when_not_found_and_no_raise(self):
        with patch("hsbt.utils.shutil.which", return_value=None):
            result = get_external_executable_path("nonexistent_xyz", raise_error=False)
        assert result is None

    def test_returns_path_when_found(self):
        with patch("hsbt.utils.shutil.which", return_value="/usr/bin/ls"):
            result = get_external_executable_path("ls", raise_error=False)
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# download_file
# ---------------------------------------------------------------------------

def _mock_response(chunks: list[bytes]):
    resp = MagicMock()
    resp.iter_content.return_value = chunks
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestDownloadFile:
    def test_download_to_file_path(self, tmp_path):
        dest = tmp_path / "output.bin"
        with patch("hsbt.utils.requests.get", return_value=_mock_response([b"hello", b" world"])):
            result = download_file("http://example.com/file.bin", dest)
        assert result == dest
        assert dest.read_bytes() == b"hello world"

    def test_download_to_directory_uses_url_filename(self, tmp_path):
        with patch("hsbt.utils.requests.get", return_value=_mock_response([b"data"])):
            result = download_file("http://example.com/archive.zip", tmp_path)
        assert result == tmp_path / "archive.zip"
        assert (tmp_path / "archive.zip").read_bytes() == b"data"

    def test_download_to_string_path(self, tmp_path):
        dest = str(tmp_path / "out.bin")
        with patch("hsbt.utils.requests.get", return_value=_mock_response([b"x"])):
            result = download_file("http://example.com/x", dest)
        assert result == Path(dest)

    def test_download_to_binary_io_returns_fileobj(self, tmp_path):
        buf = BytesIO()
        with patch("hsbt.utils.requests.get", return_value=_mock_response([b"bytes"])):
            result = download_file("http://example.com/x", buf)
        assert result is buf
        buf.seek(0)
        assert buf.read() == b"bytes"

    def test_http_error_propagates(self, tmp_path):
        import requests as req_lib
        resp = MagicMock()
        resp.raise_for_status.side_effect = req_lib.exceptions.HTTPError("404")
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        dest = tmp_path / "out.bin"
        with patch("hsbt.utils.requests.get", return_value=resp):
            with pytest.raises(req_lib.exceptions.HTTPError):
                download_file("http://example.com/missing", dest)


# ---------------------------------------------------------------------------
# unzip_file
# ---------------------------------------------------------------------------

class TestUnzipFile:
    def test_extracts_from_zip_path(self, tmp_path):
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("hello.txt", "world")
        target = tmp_path / "extracted"
        unzip_file(zip_path, target)
        assert (target / "hello.txt").read_text() == "world"

    def test_extracts_multiple_files(self, tmp_path):
        zip_path = tmp_path / "multi.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "aaa")
            zf.writestr("b.txt", "bbb")
        target = tmp_path / "out"
        unzip_file(zip_path, target)
        assert (target / "a.txt").read_text() == "aaa"
        assert (target / "b.txt").read_text() == "bbb"

    def test_extracts_from_bytesio(self, tmp_path):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("file.txt", "content")
        buf.seek(0)
        target = tmp_path / "out"
        unzip_file(buf, target)
        assert (target / "file.txt").read_text() == "content"


# ---------------------------------------------------------------------------
# parse_ls_l_output
# ---------------------------------------------------------------------------

class TestParseLsLOutput:
    def test_parses_home_output(self):
        result = parse_ls_l_output(LS_L_HOME)
        assert "backup" in result

    def test_parses_subdir_output(self):
        result = parse_ls_l_output(LS_L_SUBDIR)
        assert ".ssh" in result
        assert "bareos" in result

    def test_file_info_fields_populated(self):
        result = parse_ls_l_output(LS_L_HOME)
        entry = result["backup"]
        assert entry.owner == "u000001"
        assert entry.name == "backup"

    def test_skips_total_line(self):
        result = parse_ls_l_output(LS_L_HOME)
        assert "total" not in result

    def test_malformed_line_raises(self):
        with pytest.raises(ValueError, match="Expected 9 columns"):
            parse_ls_l_output("not a valid ls output line at all no good")


# ---------------------------------------------------------------------------
# convert_df_output_to_dict
# ---------------------------------------------------------------------------

class TestConvertDfOutputToDict:
    def test_returns_list_of_dicts(self):
        result = convert_df_output_to_dict(DF_RAW)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_headers_become_keys(self):
        result = convert_df_output_to_dict(DF_RAW)
        row = result[0]
        assert "Filesystem" in row
        assert "Use%" in row

    def test_values_parsed_correctly(self):
        result = convert_df_output_to_dict(DF_RAW)
        assert result[0]["Filesystem"] == "u000001"
