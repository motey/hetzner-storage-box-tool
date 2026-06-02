from __future__ import annotations

import os
import shutil
import zipfile
import requests
import logging
from pathlib import Path, PurePath
from typing import BinaryIO, List, Union

from hsbt.env_var_names import EXECUTABLE_PATH_ENV_VAR_MAPPING
from hsbt.models import FileInfo, FileInfoCollection

__all__ = [
    "RequirementMissing",
    "is_root",
    "cast_path",
    "download_file",
    "unzip_file",
    "parse_ls_l_output",
    "convert_df_output_to_dict",
    "get_external_executable_path",
    "slugify_string",
]

log = logging.getLogger(__name__)


def is_root() -> bool:
    return os.geteuid() == 0


def cast_path(path: str | Path | List[str] | None) -> Path | None:
    if path is None:
        return None
    elif isinstance(path, Path):
        return path.expanduser()
    elif isinstance(path, str):
        return Path(path).expanduser()
    elif isinstance(path, list):
        return Path(PurePath(*path)).expanduser()
    raise ValueError(
        f"Expected Path, str, List[str] or None — got {type(path)}"
    )


def download_file(url: str, target: Union[str, Path, BinaryIO]) -> Union[Path, BinaryIO]:
    close_after = True
    final_path = None
    if isinstance(target, str):
        target = Path(target)
    if isinstance(target, Path):
        if target.is_dir():
            target = target / url.split("/")[-1]
        final_path = target
        target = open(target, "wb")
    else:
        close_after = False
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=8192):
            target.write(chunk)
    if close_after:
        target.close()
        return final_path
    return target


def unzip_file(zip_file: Union[str, Path, BinaryIO], target_dir: Path) -> None:
    with zipfile.ZipFile(zip_file, "r") as zf:
        zf.extractall(target_dir)


def parse_ls_l_output(ls_output: str) -> FileInfoCollection:
    def extract_name(line: str) -> str:
        return line.split("'")[1] if "'" in line else line.split(" ")[-1]

    files = FileInfoCollection()
    for line in ls_output.split("\n"):
        if not line.startswith("total ") and len(line) > 10:
            name = extract_name(line)
            while "  " in line:
                line = line.replace("  ", " ")
            parts = [p for p in line.split(" ", 9) if p != ""]
            if len(parts) == 9:
                parts = [parts[0][0], parts[0][1:]] + parts[1:]
                parts = parts[:6] + [" ".join(parts[6:9])] + [parts[-1]]
                files[name] = FileInfo(
                    type_=parts[0],
                    permissions=parts[1],
                    hardlink_no=parts[2],
                    owner=parts[3],
                    group=parts[4],
                    size=parts[5],
                    date=parts[6],
                    name=name,
                )
            else:
                raise ValueError(
                    f"Could not parse ls -l output. Expected 9 columns, got {len(parts)}."
                )
    return files


def convert_df_output_to_dict(df_output: str) -> List[dict]:
    lines = df_output.strip().split("\n")
    headers = lines[0].split()
    return [dict(zip(headers, line.split())) for line in lines[1:]]


class RequirementMissing(Exception):
    pass


def get_external_executable_path(executable: str, raise_error: bool = True) -> Path | None:
    env_var = EXECUTABLE_PATH_ENV_VAR_MAPPING.get(executable)
    if env_var:
        path = os.getenv(env_var.value, None)
    else:
        path = shutil.which(executable)
    if path is None:
        if raise_error:
            raise RequirementMissing(f"'{executable}' is not installed or not in PATH.")
        return None
    log.debug(f"Found '{executable}' at '{path}'")
    return cast_path(path)


def slugify_string(s: str, spacer_char: str = "-") -> str:
    return "".join(
        c.lower() if c.isalnum() else spacer_char
        for c in s
        if c.isalnum() or c == " "
    )
