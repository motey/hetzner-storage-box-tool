from __future__ import annotations

import logging
import os
from pathlib import Path, PurePath
from typing import Any, List, Union

from hsbt.models import Connection, ConnectionList
from hsbt.utils import is_root, cast_path

__all__ = ["ConnectionManager"]

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, target_config_file: Union[str, Path] = None):
        user_config = Path(PurePath(Path.home(), ".config/hetzner_sbt_connections.json"))
        root_config = Path("/etc/hetzner_sbt_connections.json")
        if target_config_file is None:
            if is_root():
                self.target_config_file: Path = root_config
                self._alt_sources: List[Path] = [user_config]
            else:
                self.target_config_file = user_config
                self._alt_sources = [root_config]
        else:
            self.target_config_file = cast_path(target_config_file)
            self._alt_sources = [root_config, user_config]

    def _sources(self, specific: Union[str, Path, None] = None) -> List[Path]:
        if specific is not None:
            return [cast_path(specific)]
        return [self.target_config_file] + self._alt_sources

    def _load_file(self, path: Path) -> ConnectionList | None:
        if path.is_file() and os.access(path, os.R_OK) and path.stat().st_size > 0:
            return ConnectionList.model_validate_json(path.read_text())
        return None

    def list_connections(
        self,
        from_specific_config_file: Union[str, Path, None] = None,
    ) -> ConnectionList:
        combined = ConnectionList()
        for src in self._sources(from_specific_config_file):
            loaded = self._load_file(src)
            if loaded:
                combined.extend_connections(loaded)
        return combined

    def set_connection(
        self,
        identifier: str,
        user: str,
        host: str,
        key_dir: Union[str, Path] = None,
        overwrite_existing: bool = False,
        exists_ok: bool = True,
    ) -> Connection:
        existing = self.list_connections(self.target_config_file)
        con = Connection(identifier=identifier, host=host, user=user, key_dir=str(key_dir))
        existing.set_connection(con, overwrite_existing=overwrite_existing, exist_ok=exists_ok)
        self.target_config_file.parent.mkdir(parents=True, exist_ok=True)
        self.target_config_file.write_text(existing.model_dump_json())
        return con

    def get_connection(
        self,
        identifier: str,
        default: Any = None,
        from_specific_config_file: Union[str, Path, None] = None,
    ) -> Connection | None:
        for src in self._sources(from_specific_config_file):
            loaded = self._load_file(src)
            if loaded:
                con = loaded.get_connection(identifier)
                if con is not None:
                    return con
        return default

    def delete_connection(
        self,
        identifier: str,
        from_specific_config_file: Union[str, Path, None] = None,
        missing_ok: bool = False,
    ) -> bool:
        for src in self._sources(from_specific_config_file):
            loaded = self._load_file(src)
            if loaded and loaded.get_connection(identifier) is not None:
                if not os.access(src, os.W_OK):
                    raise PermissionError(
                        f"Found '{identifier}' in '{src}' but the file is not writable."
                    )
                loaded.remove_connection(identifier)
                self.target_config_file.write_text(loaded.model_dump_json())
                log.debug(f"Removed connection '{identifier}' from '{src}'")
                return True
        msg = f"Could not find connection '{identifier}'. Sources checked: {self._sources(from_specific_config_file)}"
        if not missing_ok:
            raise ValueError(msg)
        log.debug(msg)
        return False
