from __future__ import annotations

from typing import Dict
from pathlib import Path
from pydantic import BaseModel, Field

__all__ = [
    "Connection",
    "ConnectionList",
    "FileInfo",
    "FileInfoCollection",
]


class Connection(BaseModel):
    identifier: str
    host: str
    user: str
    key_dir: str


class ConnectionList(BaseModel):
    connections: Dict[str, Connection] = Field(default_factory=dict)

    def extend_connections(self, other: ConnectionList) -> None:
        self.connections = self.connections | other.connections

    def set_connection(
        self,
        connection: Connection,
        overwrite_existing: bool = False,
        exist_ok: bool = False,
    ) -> None:
        exists = connection.identifier in self.connections
        if exists and not overwrite_existing and not exist_ok:
            raise ValueError(f"Connection '{connection.identifier}' already exists.")
        if exists and exist_ok and not overwrite_existing:
            return
        self.connections[connection.identifier] = connection

    def get_connection(self, identifier: str) -> Connection | None:
        return self.connections.get(identifier, None)

    def remove_connection(self, identifier: str) -> None:
        self.connections = {k: v for k, v in self.connections.items() if k != identifier}


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
    def get_file_info(self, name: str, default=None) -> FileInfo | None:
        return self.get(name, default)
