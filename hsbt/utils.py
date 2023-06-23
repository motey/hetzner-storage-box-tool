import os
import zipfile
import requests
from pathlib import Path, PurePath
from typing import Union, List, BinaryIO, Dict, Generator
import subprocess
import logging
from dataclasses import dataclass, field
from pydantic import BaseModel
import datetime

log = logging.getLogger(__name__)


def is_root():
    return os.geteuid() == 0


def download_file(
    url: str, target: Union[str, Path, BinaryIO]
) -> Union[Path, BinaryIO]:
    close_file_obj = True
    final_target_path = None
    if isinstance(target, str):
        target = Path(str)
    if isinstance(target, Path):
        if target.is_dir():
            local_filename = url.split("/")[-1]
            target = Path(PurePath(target, local_filename))
        final_target_path = target
        target = open(target, "wb")
    else:
        close_file_obj = False

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=8192):
            target.write(chunk)
    if close_file_obj:
        close_file_obj.close()
        return final_target_path
    return target


class FileInfo(BaseModel):
    type_: str
    permissions: str
    hardlink_no: str
    owner: str
    group: str
    size: str
    date: str
    name: str


class FileInfoCollection(dict[str, FileInfo]):
    def get_file_info(self, name: str, default=None) -> FileInfo:
        return self.get(name, default)


def cast_path(path: str | Path | List[str]) -> Path:
    if path is None:
        return None
    elif isinstance(path, Path):
        return path.expanduser()
    elif isinstance(path, str):
        return Path(path).expanduser()
    elif isinstance(path, list):
        return Path(PurePath(*path)).expanduser()
    else:
        raise ValueError(
            f"Expected `pathlib.Path`, `str`, `List[str | pathlib.Path]` or `None` got {type(path)}"
        )


def parse_ls_l_output(ls_output: str) -> FileInfoCollection:
    def extract_file_name(ls_line: str) -> str:
        if "'" in ls_line:
            return ls_line.split("'")[1]
        else:
            return ls_line.split(" ")[-1]

    """expecting `ls -l` from hetzner storage box format"""
    data = []
    files = FileInfoCollection()
    lines = ls_output.split("\n")
    for line in lines:
        if not line.startswith("total ") and len(line) > 10:
            file_name = extract_file_name(line)
            while "  " in line:
                line = line.replace("  ", " ")
            data: List[str] = line.split(" ", 9)
            # remove empty values (happens when ls creates indentations)
            data = [i for i in data if i != ""]
            if len(data) == 9:
                # seperate persmmision from file type
                data = [data[0][0], data[0][1:]] + data[1:]
                # pull date string
                data = data[:6] + [" ".join(data[6:9])] + [data[-1]]
                file = FileInfo(
                    type_=data[0],
                    permissions=data[1],
                    hardlink_no=data[2],
                    owner=data[3],
                    group=data[4],
                    size=data[5],
                    date=data[6],
                    name=file_name,
                )
                files[file.name] = file
            else:
                raise ValueError(
                    f"Could not parse `ls -l` output. Expected 9 columns per line got {len(data)}. input data: \n {lines}"
                )
    return files


def convert_df_output_to_dict(df_output):
    lines = df_output.strip().split("\n")
    headers = lines[0].split()
    devices = []

    for line in lines[1:]:
        values = line.split()
        device = dict(zip(headers, values))
        devices.append(device)
    return devices


def unzip_file(zip_file: Union[str, Path, BinaryIO], target_dir: Path):
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(target_dir)


import sys


@dataclass
class ProcessOutput:
    command: str
    stdout_lines: List[str] = field(default_factory=list)
    stdout_current: str = ""
    stderr: List[str] = field(default_factory=list)
    return_code: str = None
    error_for_raise: ChildProcessError = None


def open_process(
    command: Union[List[str], str],
    extra_envs: Dict[str, str] = None,
    raise_error: bool = True,
) -> Generator[ProcessOutput, None, None]:
    env = os.environ.copy()
    if extra_envs:
        env = env | extra_envs

    if isinstance(command, str):
        command = [command]
    output = ProcessOutput(command=" ".join(command))

    process = subprocess.Popen(
        args=command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        env=env,
    )
    while True:
        if output.stdout_current:
            output.stdout_lines.append(output.stdout_current)
            output.stdout_current = None
        process.poll()
        if process.returncode is not None:
            break

        output.stdout_current = process.stdout.readline().decode().strip()
        if output.stdout_current:
            yield output
    output.stderr = process.stderr.read().decode().strip()
    process.wait()
    output.return_code = process.returncode
    if output.return_code != 0:
        e_msg = f"""Command '{output.command}'. ErrorCode: {output.return_code} {'stderr:' + os.linesep + output.stderr if  output.stderr else ''} {os.linesep + 'stdout laste line:' + os.linesep + output.stdout_current if output.stdout_current else ''}"""
        output.error_for_raise = ChildProcessError(e_msg)
        if raise_error:
            raise output.error_for_raise
    yield output


@dataclass
class CommandResult:
    command: str = None
    stdout: str = None
    stderr: str = None
    return_code: str = None
    error_for_raise: ChildProcessError = None


def run_command(
    command: Union[List[str], str],
    extra_envs: Dict[str, str] = None,
    raise_error: bool = True,
) -> CommandResult:
    process_output = None
    for output in open_process(
        command=command, extra_envs=extra_envs, raise_error=raise_error
    ):
        process_output = output
    return CommandResult(
        command=process_output.command,
        stdout="\n".join(process_output.stdout_lines),
        stderr=process_output.stderr,
        return_code=output.return_code,
        error_for_raise=output.error_for_raise,
    )

    env = os.environ.copy()
    if extra_envs:
        env = env | extra_envs
    if isinstance(command, str):
        command = [command]
    prefixed_command = ["/bin/bash", "-c"] + command

    log.debug(f"RUN COMMAND: {' '.join(prefixed_command)}")
    proc = subprocess.run(prefixed_command, capture_output=True, text=True, env=env)
    log.debug(f"COMMAND stdout: `{proc.stdout}`")
    log.debug(f"COMMAND stderr: `{proc.stderr}`")
    log.debug(f"COMMAND return code: `{proc.returncode}`")
    result = CommandResult(" ".join(command), proc.stdout, proc.stderr, proc.returncode)
    if result.return_code != 0:
        e_msg = f"""Command '{" ".join(command)}'. ErrorCode: {proc.returncode} {'stderr:' + os.linesep + proc.stderr if proc.stderr else ''} {os.linesep + 'stdout:' + os.linesep + proc.stdout if proc.stdout else ''}"""
        result.error_for_raise = ChildProcessError(
            e_msg,
            proc.returncode,
        )
        if raise_error:
            raise result.error_for_raise
    return result


class ConfigEntryExistsError(Exception):
    pass


class ConfigFileEditor:
    """Helper function to edit line based config files e.g. /etc/fstab
    Can insert/update/remove lines. Added lines will be enclosed by command in a certain format.
    This enables ConfigFileEditor to later re-identify lines.
    """

    def __init__(
        self,
        target_file: Union[str, Path],
        base_identifier: str = "",
        line_comment_line_delimiter: str = "#",
        source_hint: str = "CONFIG LINES GENERATED BY HSBT SCRIPT",
        create_file_if_not_exists: bool = True,
        create_mode: int = 0o660,
    ):
        if isinstance(target_file, str):
            target_file = Path(target_file)
        self.target_file = target_file
        self.line_comment_line_delimiter = line_comment_line_delimiter
        self.base_identifier = base_identifier
        self.source_hint = source_hint
        self.create_file_if_not_exists = create_file_if_not_exists
        self.create_mode = create_mode

    class ConfigFile:
        class Line:
            def __init__(
                self, content: str, file: "ConfigFileEditor.ConfigFile" = None
            ):
                self.content = content
                self.file = file
                self.removed = False

            def remove(self):
                self.removed = True

            def is_(self, val: str):
                return self.content == val

            @property
            def number(self):
                return self.file.lines.index(self)

            def insert_after(
                self,
                lines: Union[
                    str,
                    "ConfigFileEditor.ConfigFile.Line",
                    List[Union[str, "ConfigFileEditor.ConfigFile.Line"]],
                ],
            ):
                if not isinstance(lines, list):
                    lines = [lines]
                self.file.insert_lines(lines, self.number)

            def is_last(self):
                return self.number + 1 == len(self.file.lines)

        def __init__(self, path: Path):
            self.path = path
            self.lines: List[ConfigFileEditor.ConfigFile.Line] = []
            self.cursor: int = None
            self.current_line = None
            self.record: bool = True

        def read(self):
            with open(self.path, "r") as file:
                for line in file.readlines():
                    self.lines.append(
                        ConfigFileEditor.ConfigFile.Line(line.strip("\n"), self)
                    )
            self.cursor = 0

        def next_line(self) -> Line:
            if not self.record and self.current_line:
                self.current_line.remove()
            self.current_line = self.lines[self.cursor]
            self.cursor += 1
            return self.current_line

        def insert_line(self, line: Union[str, Line], index: int):
            if isinstance(line, str):
                line = ConfigFileEditor.ConfigFile.Line(line, self)
            elif not isinstance(line, ConfigFileEditor.ConfigFile.Line):
                raise ValueError(
                    f"Expected 'ConfigFileEditor.ConfigFile.Line' or string type. Got {type(line)}, {line}"
                )
            self.lines.insert(index, line)
            self.cursor += 1

        def insert_lines(self, lines: List[Union[str, Line]], index: int):
            for no, line in enumerate(lines):
                self.insert_line(line, index + no)

        def attach_lines(self, lines: List[Union[str, Line]]):
            for line in lines:
                self.insert_line(line, len(self.lines))

        def is_empty(self):
            return len(self.lines) == 0

        def save(self):
            with open(self.path, "w") as file:
                file.writelines(
                    line.content + "\n" for line in self.lines if not line.removed
                )

    def _validate_and_prepare_target(self, supress_creating: bool = False):
        if self.target_file.is_dir():
            raise ValueError(
                f"Target file {self.target_file} is directory. Expected a file."
            )
        elif self.target_file.is_file():
            if not os.access(self.target_file, os.W_OK):
                raise ValueError(f"Target file {self.target_file} is not writable.")
        elif not self.target_file.exists() and (
            self.create_file_if_not_exists and not supress_creating
        ):
            self.target_file.parent.mkdir(exist_ok=True, parents=True, mode=551)
            self.target_file.touch(mode=self.create_mode)
        elif not self.target_file.exists() and not self.create_file_if_not_exists:
            raise ValueError(f"Target file {self.target_file} does not exist.")

    def get_config_entry(self, identifier) -> List[str]:
        start_delimiter: str = self._get_start_delimiter(identifier=identifier)
        end_delimiter: str = self._get_end_delimiter(identifier=identifier)
        if not self.target_file.exists():
            return []
        file = ConfigFileEditor.ConfigFile(path=self.target_file)
        file.read()
        if file.is_empty():
            return []
        result = []
        cursor_in_entry: bool = False
        while True:
            line = file.next_line()
            if line.is_(end_delimiter):
                cursor_in_entry = False
            if cursor_in_entry:
                result.append(line.content)
            if line.is_(start_delimiter):
                cursor_in_entry = True
            if line.is_last():
                break
        return result

    def set_config_entry(
        self,
        content: Union[str, List[str]],
        identifier: str,
    ):
        self._validate_and_prepare_target(supress_creating=not bool(content))
        if content and not isinstance(content, list):
            content = [content]
        start_delimiter: str = self._get_start_delimiter(identifier=identifier)
        end_delimiter: str = self._get_end_delimiter(identifier=identifier)

        file = ConfigFileEditor.ConfigFile(path=self.target_file)
        file.read()
        content_inserted: bool = False
        if not file.is_empty():
            while True:
                line = file.next_line()
                if line.is_(start_delimiter):
                    line.remove()
                    file.record = False
                if line.is_(end_delimiter):
                    line.remove()
                    file.record = True
                    if content:
                        line.insert_after([start_delimiter] + content + [end_delimiter])
                    content_inserted = True
                if line.is_last():
                    break
        if not content_inserted and content:
            file.attach_lines([start_delimiter] + content + [end_delimiter])
        file.save()
        return

    def remove_config_entry(self, identifier: str):
        self.set_config_entry(content=None, identifier=identifier)

    def _get_start_delimiter(self, identifier: str):
        return f"{self.line_comment_line_delimiter} <{self.source_hint} '{self.base_identifier}/{identifier}'>"

    def _get_end_delimiter(self, identifier: str):
        return f"{self.line_comment_line_delimiter} </{self.source_hint} '{self.base_identifier}/{identifier}'>"
