from pathlib import Path, PurePath
import logging
from typing import List, Union, Dict
from dataclasses import dataclass
from pydantic import BaseModel

import json

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
        self.binaries: Dict[str, str] = {"rclone": "rclone"}

    def _get_config_file_param(self) -> str:
        return (
            f'--config="{str(self.config_file_path)}"' if self.config_file_path else ""
        )

    def get_existing_config(self, name: str, missing_ok: bool = False) -> Dict | None:
        command = f"""{self.binaries['rclone']} -q {self._get_config_file_param()} config dump"""
        result = run_command(command)
        configs = json.loads(result.stdout)
        if name in configs:
            return configs[name]
        if missing_ok:
            return None
        raise ValueError(f"Can not find a rclone config by the name '{name}'")

    def generate_config_file_if_not_exists(self) -> bool:
        config = dict(
            type="sftp",
            host=self.storage_box_manager.host,
            user=self.storage_box_manager.user,
            known_hosts_file=str(
                self.storage_box_manager.key_manager._get_known_host_path()
            ),
            port="23",
            key_file=str(self.storage_box_manager.key_manager.private_key_path),
        )
        existing_config = self.get_existing_config(
            name=self.storage_box_manager.key_manager.identifier, missing_ok=True
        )
        if existing_config == config:
            # all cool. nothing to do
            return False
        # https://rclone.org/commands/rclone_config_create/
        command = f"""{self.binaries['rclone']} {self._get_config_file_param()} config create {self.storage_box_manager.key_manager.identifier} sftp {' '.join(k+' "'+v+'"' for k,v in config.items())}"""
        log.debug(f"Create rclone config")
        run_command(command)
        return True

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
        command = f"{self.binaries['rclone']} {self._get_config_file_param()} mount {self.storage_box_manager.key_manager.identifier}:{self.storage_box_manager.remote_base_path} {local_dir}"
        print(command)
        cast_path(local_dir).mkdir(exist_ok=True, parents=True)
        run_command(command)
