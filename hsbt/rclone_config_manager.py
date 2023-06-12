from pathlib import Path, PurePath
import tempfile
from typing import List, Union
from dataclasses import dataclass
from pydantic import BaseModel

import inspect

from Configs import getConfig
from hsbt.key_manager import KeyManager
from hsbt.storage_box_manager import HetznerStorageBox
from hsbt.utils import ConfigFileEditor


class Rclone:
    class RcloneBinary(BaseModel):
        version: str
        path: Path

    class RcloneRemoteConfig(BaseModel):
        identifier: str
        config_str: str
        config_file_path: Path = None

        def write(self, file_path: Union[Path, str]):
            if isinstance(file_path, str):
                file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wt") as f:
                f.write(self.config_str)
            self.config_file_path = file_path

    def __init__(self, storage_box_manager: HetznerStorageBox):
        self.storage_box_manager = storage_box_manager

    # TODO you are here
    def generate_config_file(self):
        config_str = inspect.cleandoc(
            f"""
                    [{self.key_manager.identifier}]
                    type = sftp
                    host = {self.storage_box_manager.host}
                    user = {self.storage_box_manager.user}
                    known_hosts_file = {self.storage_box_manager.key_manager.known_host_path}
                    port = 23
                    key_file = {self.storage_box_manager.key_manager.private_key_path}
        """
        )
        ConfigFileEditor(target_file=?)
        config_file_path = Path(self.storage_box_manager.identifier)

        self.remote_config = Rclone.RcloneRemoteConfig(
            identifier=identifier,
            config_str=config_str,
        )
        self.remote_config.write(config_file_path)

    def generate_config_file_from_hetzner_storage_box(
        self, storage_box: HetznerStorageBox
    ):
        self.generate_config_file(
            identifier=f"remote-{storage_box.user}",
            host=storage_box.host,
            user=storage_box.user,
            known_host_file=CONFIG.SSH_KNOWN_HOST_FILE,
            private_key_file=storage_box.private_key_file_openssh,
            public_key_file=storage_box.public_key_file,
        )

    def ls_storage_box(self, remote_path="", verbose: bool = False):
        return run_command(
            f"""{self.active_binary_version.path} --config="{self.remote_config.config_file_path.absolute()}" ls {self.remote_config.identifier}:{remote_path} {' --verbose' if verbose else ''}"""
        )

    def bisync_storage_box(
        self,
        local_dir: Union[str, Path],
        remote_path="/",
        resync: bool = False,
        verbose: bool = False,
    ):
        if isinstance(local_dir, str):
            local_dir = Path(local_dir)
        local_dir.mkdir(exist_ok=True, parents=True)
        return run_command(
            f"""{self.active_binary_version.path} --config="{self.remote_config.config_file_path.absolute()}" bisync {self.remote_config.identifier}:{remote_path} {local_dir} {' --resync' if resync else ''}{' --verbose' if verbose else ''}{' --filters-file' + CONFIG.RCLONE_SYNC_FILTER if CONFIG.RCLONE_SYNC_FILTER else ''}"""
        )

    def sync_from_storage_box_to_local(
        self, local_dir: Union[str, Path], remote_path="/", verbose: bool = False
    ):
        return run_command(
            f"""{self.active_binary_version.path} --config="{self.remote_config.config_file_path.absolute()}" sync {self.remote_config.identifier}:{remote_path} {local_dir}{' --verbose' if verbose else ''}{' --filters-file' + CONFIG.RCLONE_SYNC_FILTER if CONFIG.RCLONE_SYNC_FILTER else ''}"""
        )
