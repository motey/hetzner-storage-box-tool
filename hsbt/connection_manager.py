import os
from typing import Union, List, Dict
from pathlib import Path, PurePath
from hsbt.utils import is_root
import json
from pydantic import BaseModel


class ConnectionManager:
    class Connection(BaseModel):
        identifier: str
        host: str
        user: str
        key_dir: Path

    class ConnectionList(BaseModel):
        connections: List["ConnectionManager.Connection"]

        def extend_connections(
            self, other_connection_list: "ConnectionManager.Connection"
        ):
            self.connections.extend(other_connection_list.connections)

    def __init__(self, target_config_file: Union[str, Path] = None):
        user_config_path = Path(
            PurePath(Path.home(), ".config/hetzner_sb_connections.json")
        )
        root_config_path = Path("/etc/hetzner_sb_connections.json")
        if target_config_file is None:
            if is_root():
                target_config_file = root_config_path
                alternative_config_file_sources = [user_config_path]
            else:
                target_config_file = user_config_path
                alternative_config_file_sources = [root_config_path]
        else:
            if not isinstance(target_config_file, Path):
                target_config_file = Path(target_config_file)
            alternative_config_file_sources = [root_config_path, user_config_path]
        self.target_config_file: Path = target_config_file
        self.alternative_config_file_sources = alternative_config_file_sources

    def list_connections(
        self,
        from_specific_config_file: Union[str, Path] = None,
    ) -> ConnectionList:
        if from_specific_config_file is not None:
            sources = from_specific_config_file
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        cons = ConnectionManager.ConnectionList([])
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                cons.extend_connections(
                    ConnectionManager.ConnectionList.parse_file(source_file)
                )
        return cons

    def create_connection(
        self,
        identifier: str,
        user: str,
        host: str,
        key_dir: Union[str, Path] = None,
        overwrite_existing: bool = False,
        exists_ok: bool = True,
    ):
        existing_cons = self.list_connections(self.target_config_file)
        con = ConnectionManager.Connection(
            identifier=identifier, host=host, user=user, key_dir=key_dir
        )
        # todo YOu are here

    def get_connection(
        self,
        identifier: str,
        default: None,
        from_specific_config_file: Union[str, Path] = None,
    ) -> Connection:
        if from_specific_config_file is not None:
            sources = from_specific_config_file
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                for con in ConnectionManager.ConnectionList.parse_file(
                    source_file
                ).connections:
                    if con.identifier == identifier:
                        return con
        return default
