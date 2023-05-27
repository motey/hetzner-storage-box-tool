import os
import zipfile
import requests
from pathlib import Path, PurePath
from typing import Union, List, BinaryIO, Dict
import subprocess
import logging

log = logging.getLogger(__name__)


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


def unzip_file(zip_file: Union[str, Path, BinaryIO], target_dir: Path):
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(target_dir)


def run_command(
    command: Union[List, str],
    extra_envs: Dict[str, str] = None,
):
    if extra_envs is None:
        extra_envs = {}
    if isinstance(command, str):
        command = [command]
    command = ["/bin/bash", "-c"] + command

    # print("comamnd:", type(command), command)
    # print("RUN#:", " ".join(command))
    current_env: Dict[str, str] = os.environ.copy()
    log.debug(f"RUN COMMAND: {' '.join(command)}")
    proc = subprocess.run(
        command, capture_output=True, text=True, env=current_env | extra_envs
    )
    if proc.stderr:
        e_msg = (
            f"Command '{command}'. ErrorCode: {proc.returncode} Error:\n{proc.stderr}"
        )
        # log.error(e_msg)
        raise ChildProcessError(
            e_msg,
            proc.returncode,
        )
    log.debug(f"COMMAND RESULT: {proc.stdout}")
    return proc.stdout


