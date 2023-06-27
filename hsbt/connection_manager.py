import os, sys
from typing import Union, List, Dict, Any
from pathlib import Path, PurePath
from hsbt.utils import is_root, cast_path
import json
from pydantic import BaseModel, Field

import logging

log = logging.getLogger(__name__)


class ConnectionManager:
    class Connection(BaseModel):
        identifier: str
        host: str
        user: str
        key_dir: str

    class ConnectionList(BaseModel):
        connections: Dict[str, "ConnectionManager.Connection"] = Field(
            default_factory=dict
        )

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

        def remove_connection(
            self, connection: Union[str, "ConnectionManager.Connection"]
        ) -> "ConnectionManager.Connection":
            conid = None
            if isinstance(connection, ConnectionManager.Connection):
                conid = connection.identifier

            elif isinstance(connection, str):
                conid = connection
            self.connections = {
                key: con for key, con in self.connections.items() if key != conid
            }

    def __init__(self, target_config_file: Union[str, Path] = None):
        user_config_path = Path(
            PurePath(Path.home(), ".config/hetzner_sbt_connections.json")
        )
        root_config_path = Path("/etc/hetzner_sbt_connections.json")
        if target_config_file is None:
            if is_root():
                target_config_file = root_config_path
                alternative_config_file_sources = [user_config_path]
            else:
                target_config_file = user_config_path
                alternative_config_file_sources = [root_config_path]
        else:
            target_config_file = cast_path(target_config_file)
            alternative_config_file_sources = [root_config_path, user_config_path]
        self.target_config_file: Path = target_config_file
        self.alternative_config_file_sources = alternative_config_file_sources

    def list_connections(
        self,
        from_specific_config_file: Union[str, Path] = None,
    ) -> ConnectionList:
        if from_specific_config_file is not None:
            sources = [from_specific_config_file]
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        cons = ConnectionManager.ConnectionList()
        for source_file in sources:
            if (
                source_file.is_file()
                and os.access(source_file, os.R_OK)
                and os.stat(source_file).st_size != 0
            ):
                ConnectionManager.ConnectionList.update_forward_refs()
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
    ) -> Connection:
        existing_cons = self.list_connections(self.target_config_file)
        con = ConnectionManager.Connection(
            identifier=identifier, host=host, user=user, key_dir=str(key_dir)
        )
        existing_cons.set_connection(
            con, ovewrite_existing=overwrite_existing, exist_ok=exists_ok
        )
        self.target_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.target_config_file, "w") as file:
            file.write(existing_cons.json())
        return con

    def get_connection(
        self,
        identifier: str,
        default: Any = None,
        from_specific_config_file: Union[str, Path] = None,
    ) -> Connection:
        if from_specific_config_file is not None:
            sources = [from_specific_config_file]
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                ConnectionManager.ConnectionList.update_forward_refs()
                con = ConnectionManager.ConnectionList.parse_file(
                    source_file
                ).get_connection(identifier=identifier)
                if con is not None:
                    return con
        return default

    def delete_connection(
        self,
        identifier: str,
        from_specific_config_file: Union[str, Path] = None,
        missing_ok: bool = False,
    ) -> Connection:
        if from_specific_config_file is not None:
            sources = [from_specific_config_file]
        else:
            sources = [self.target_config_file] + self.alternative_config_file_sources
        for source_file in sources:
            if source_file.is_file() and os.access(source_file, os.R_OK):
                conlist = ConnectionManager.ConnectionList.parse_file(source_file)
                if conlist.get_connection(identifier=identifier) is not None:
                    if not os.access(source_file, os.W_OK):
                        raise PermissionError(
                            f"Found connection '{identifier}' in '{source_file}'. But file is not writable. Please try again with correct/sudo permissions."
                        )
                    conlist.remove_connection(identifier)
                    with open(self.target_config_file, "w") as file:
                        file.write(conlist.json())
                    log.debug(
                        f"Removed connection with identifier '{identifier}' from file '{source_file}'"
                    )
                    return True
        not_found_message = f"Could not find connection with identifier '{identifier}'. Config files checked: {sources}"
        if not missing_ok:
            raise ValueError(not_found_message)
        else:
            log.debug(not_found_message)
            return False
