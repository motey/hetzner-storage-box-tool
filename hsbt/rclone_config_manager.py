from pathlib import Path, PurePath
import logging
from typing import List, Union
from dataclasses import dataclass
from pydantic import BaseModel

import inspect

from Configs import getConfig
from hsbt.key_manager import KeyManager
from hsbt.storage_box_manager import HetznerStorageBox
from hsbt.utils import ConfigFileEditor
from hsbt.utils import cast_path, run_command

log = logging.getLogger(__name__)


class Rclone:
    def __init__(
        self,
        storage_box_manager: HetznerStorageBox,
        config_file_path: str | Path = None,
    ):
        self.storage_box_manager = storage_box_manager
        self.config_file_path: Path = cast_path(config_file_path)

    def generate_config_file(self):
        options = dict(
            type="sftp",
            host=self.storage_box_manager.host,
            user=self.storage_box_manager.user,
            known_hosts_file=self.storage_box_manager.key_manager.known_host_path,
            port="23",
            key_file=self.storage_box_manager.key_manager.private_key_path,
        )
        # https://rclone.org/commands/rclone_config_create/
        command = f"""rclone {'--config="' + str(self.config_file_path) + '"' if self.config_file_path else ''} config create {self.storage_box_manager.key_manager.identifier} sftp {' '.join(k+' "'+str(v)+'"' for k,v in options.items())}"""
        log.debug("Create rclone config")
        run_command(command)
        return command

    def bisync_storage_box(
        self,
        local_dir: Union[str, Path],
        remote_path="/",
        resync: bool = False,
        verbose: bool = False,
    ):
        raise NotImplementedError()
        if isinstance(local_dir, str):
            local_dir = Path(local_dir)
        local_dir.mkdir(exist_ok=True, parents=True)
        return run_command(
            f"""{self.active_binary_version.path} --config="{self.remote_config.config_file_path.absolute()}" bisync {self.remote_config.identifier}:{remote_path} {local_dir} {' --resync' if resync else ''}{' --verbose' if verbose else ''}{' --filters-file' + CONFIG.RCLONE_SYNC_FILTER if CONFIG.RCLONE_SYNC_FILTER else ''}"""
        )

    def sync_from_storage_box_to_local(
        self, local_dir: Union[str, Path], remote_path="/", verbose: bool = False
    ):
        raise NotImplementedError()
        return run_command(
            f"""{self.active_binary_version.path} --config="{self.remote_config.config_file_path.absolute()}" sync {self.remote_config.identifier}:{remote_path} {local_dir}{' --verbose' if verbose else ''}{' --filters-file' + CONFIG.RCLONE_SYNC_FILTER if CONFIG.RCLONE_SYNC_FILTER else ''}"""
        )

    def mount(self, local_dir: str):
        raise NotImplementedError()
