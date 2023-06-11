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
        connections: Dict[str, "ConnectionManager.Connection"]

        def extend_connections(
            self, other_connection_list: "ConnectionManager.ConnectionList"
        ):
            self.connections = self.connections | other_connection_list.connections

        def set_connection(
            self,
            other_connection: "ConnectionManager.Connection",
            ovewrite_existing: bool = False,
            exist_ok: bool = False,
        ):
            if (
                other_connection.identifier in self.connections
                and not ovewrite_existing
            ):
                raise ValueError(
                    f"Connection '{other_connection.identifier}' already exist."
                )
            elif other_connection.identifier in self.connections and exist_ok:
                return
            self.connections[other_connection.identifier] = other_connection

        def get_connection(self, identifier: str) -> "ConnectionManager.Connection":
            return self.connections.get(identifier, None)

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
        cons = ConnectionManager.ConnectionList({})
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                cons.extend_connections(
                    ConnectionManager.ConnectionList.parse_file(source_file)
                )
        return cons

    def set_connection(
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
        existing_cons.set_connection(
            con, ovewrite_existing=overwrite_existing, exist_ok=exists_ok
        )
        with open(self.target_config_file, "w") as file:
            file.write(existing_cons.json())

    def get_connection(
        self,
        identifier: str,
        default: None,
        from_specific_config_file: Union[str, Path] = None,
    ) -> Connection:
        if from_specific_config_file is not None:
            sources = [from_specific_config_file]
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                con = ConnectionManager.ConnectionList.parse_file(
                    source_file
                ).get_connection(identifier=identifier)
                if con is not None:
                    return con
        return default
