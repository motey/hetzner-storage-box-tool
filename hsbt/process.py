from __future__ import annotations

import os
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Union

log = logging.getLogger(__name__)


@dataclass
class ProcessOutput:
    command: str
    stdout_lines: List[str] = field(default_factory=list)
    stdout_current: str = ""
    stderr: str = ""
    return_code: int = None
    error_for_raise: ChildProcessError = None


@dataclass
class CommandResult:
    command: str = None
    stdout: str = None
    stderr: str = None
    return_code: int = None
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
        tail_lines = []
        for line in reversed(output.stdout_lines):
            if line.strip():
                tail_lines.insert(0, line)
            if len(tail_lines) == 5:
                break
        tail_str = "\n".join(tail_lines)
        e_msg = (
            f"Command '{output.command}'. ErrorCode: {output.return_code}"
            + (f"\nstderr: {output.stderr}" if output.stderr else "")
            + (f"\ntail stdout:\n{tail_str}" if tail_str else "")
        )
        output.error_for_raise = ChildProcessError(e_msg)
        if raise_error:
            raise output.error_for_raise
    yield output


def run_command(
    command: Union[List[str], str],
    extra_envs: Dict[str, str] = None,
    raise_error: bool = True,
) -> CommandResult:
    process_output = None
    for output in open_process(command=command, extra_envs=extra_envs, raise_error=raise_error):
        process_output = output
    return CommandResult(
        command=process_output.command,
        stdout="\n".join(process_output.stdout_lines),
        stderr=process_output.stderr,
        return_code=process_output.return_code,
        error_for_raise=process_output.error_for_raise,
    )
