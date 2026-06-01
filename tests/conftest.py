from __future__ import annotations

import pytest
from pathlib import Path

from hsbt.key_manager import KeyManager
from hsbt.models import Connection
from hsbt.process import CommandResult
from hsbt.transport.ssh import SshTransport

# ---------------------------------------------------------------------------
# Raw outputs captured from u000001.your-storagebox.de (SSH port 23)
# Used to drive parse_ls_l_output / convert_df_output_to_dict tests.
# ---------------------------------------------------------------------------

LS_L_HOME = (
    "total 23\n"
    "drwxr-xr-x 3 u000001 u000001  3 Aug 21  2023 .\n"
    "dr-x--x--x 7 root    root    11 Feb 25 08:37 ..\n"
    "drwxrwsr-x 4 u000001 u000001  4 Aug 25  2023 backup"
)

LS_L_SUBDIR = (
    "total 2\n"
    "drwxrwsr-x 4 u000001 u000001 4 Aug 25  2023 .\n"
    "drwxr-xr-x 3 u000001 u000001 3 Aug 21  2023 ..\n"
    "drwx------ 2 u000001 u000001 3 Aug 21  2023 .ssh\n"
    "drwxr-sr-x 2 u000001 u000001 5 Aug 26  2023 bareos"
)

DF_RAW = (
    "Filesystem       1K-blocks  Used   Available Use% Mounted on\n"
    "u000001        10737418240  5120 10737413120   1% /home"
)

DF_H = (
    "Filesystem      Size  Used Avail Use% Mounted on\n"
    "u000001          10T  5.0M   10T   1% /home"
)


# ---------------------------------------------------------------------------
# Fixtures exposing the raw strings
# ---------------------------------------------------------------------------

@pytest.fixture
def ls_home():
    return LS_L_HOME


@pytest.fixture
def ls_subdir():
    return LS_L_SUBDIR


@pytest.fixture
def df_raw():
    return DF_RAW


@pytest.fixture
def df_h():
    return DF_H


# ---------------------------------------------------------------------------
# Core object fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def connection(tmp_path):
    return Connection(
        identifier="testbox",
        host="u000001.your-storagebox.de",
        user="u000001",
        key_dir=str(tmp_path / "ssh"),
    )


@pytest.fixture
def key_manager(tmp_path):
    return KeyManager(target_dir=tmp_path / "ssh", identifier="testbox")


@pytest.fixture
def transport(key_manager):
    return SshTransport(
        host="u000001.your-storagebox.de",
        user="u000001",
        key_manager=key_manager,
        port=23,
        remote_dir="/home",
    )


# ---------------------------------------------------------------------------
# CommandResult factory helpers (plain functions, importable from this module)
# ---------------------------------------------------------------------------

def make_ok(stdout: str = "", command: str = "cmd") -> CommandResult:
    return CommandResult(command=command, stdout=stdout, stderr="", return_code=0)


def make_err(return_code: int = 1, stderr: str = "error", command: str = "cmd") -> CommandResult:
    err = ChildProcessError(f"Command '{command}'. ErrorCode: {return_code}\nstderr: {stderr}")
    return CommandResult(
        command=command,
        stdout="",
        stderr=stderr,
        return_code=return_code,
        error_for_raise=err,
    )
