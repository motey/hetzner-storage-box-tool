from __future__ import annotations

import logging
from pathlib import Path, PurePath
from typing import List, Literal, Union

from hsbt.process import run_command
from hsbt.utils import cast_path

__all__ = ["KeyManager"]

log = logging.getLogger(__name__)


class KeyManager:
    def __init__(self, target_dir: Union[Path, str] = None, identifier: str = None):
        if target_dir is None:
            target_dir = Path(PurePath(Path.home(), ".ssh"))
        target_dir = Path(target_dir) if not isinstance(target_dir, Path) else target_dir
        if target_dir.is_file():
            raise ValueError(f"Key target must be a directory, got a file: '{target_dir}'")
        target_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir = target_dir
        self.identifier = f"hsbt_{identifier or 'key'}"
        self.private_key_path: Path = None
        self.public_key_path: Path = None
        self.public_key_rfc_path: Path = None
        self.known_host_path: Path = None
        self.key_alg: Literal["ed25519", "rsa"] = "ed25519"
        self.rsa_key_length_bits: int = 4096
        self._generate_key_paths()

    def _generate_key_paths(self) -> None:
        self.private_key_path = Path(PurePath(self.target_dir, self.identifier))
        self.public_key_path = Path(PurePath(self.target_dir, f"{self.identifier}.pub"))

    def ssh_keygen(self, overwrite_if_exists: bool = False, exists_ok: bool = False) -> None:
        valid = self.validate_if_keys_exists_and_valid(raise_if_not_valid=False)
        if valid and not overwrite_if_exists and not exists_ok:
            raise FileExistsError(
                f"Key already exists at {self.private_key_path}. "
                "Pass overwrite_if_exists=True to regenerate or exists_ok=True to skip."
            )
        if valid and exists_ok and not overwrite_if_exists:
            return
        run_command(
            f'ssh-keygen -b {self.rsa_key_length_bits} -t {self.key_alg} -f {self.private_key_path} -q -N ""'
        )

    def gen_rfc4716_format_copy(
        self,
        target_path: Union[Path, str] = None,
        overwrite_if_exist: bool = False,
        exists_ok: bool = False,
    ) -> Path:
        if isinstance(target_path, str):
            target_path = Path(target_path)
        elif target_path is None:
            target_path = Path(PurePath(
                self.public_key_path.parent,
                self.public_key_path.stem + ".rfc.pub",
            ))
        if target_path.is_file() and not overwrite_if_exist and not exists_ok:
            raise FileExistsError(
                f"RFC4716 target already exists at '{target_path}'. "
                "Pass overwrite_if_exist=True or exists_ok=True."
            )
        if target_path.is_file() and exists_ok and not overwrite_if_exist:
            self.public_key_rfc_path = target_path
            return target_path
        run_command(f"ssh-keygen -e -f {self.public_key_path} -m RFC4716 > {target_path}")
        self.public_key_rfc_path = target_path
        return target_path

    def get_private_key(self) -> bytes:
        with open(self.private_key_path, "rb") as f:
            return f.read()

    def get_public_key(self, in_rfc4716_format: bool = False) -> bytes:
        path = self.public_key_rfc_path if in_rfc4716_format else self.public_key_path
        with open(path, "rb") as f:
            return f.read()

    def _get_known_host_path(self) -> Path:
        if self.known_host_path is None:
            self.known_host_path = Path(PurePath(self.target_dir, "known_hosts"))
        return self.known_host_path

    def create_known_host_entry_if_not_exists(
        self,
        host: str,
        ports: int | str | List[int | str] = None,
    ) -> None:
        if ports:
            ports = [str(ports)] if isinstance(ports, (int, str)) else [str(p) for p in ports]
        else:
            ports = [None]
        known_hosts = self._get_known_host_path()
        for port in ports:
            if not self.known_host_entry_exists(host, port=port):
                run_command(
                    f"ssh-keyscan -t {self.key_alg} {'-p ' + port if port else ''} {host} >> {known_hosts}"
                )

    def known_host_entry_exists(self, host: str, port: str = None) -> bool:
        known_hosts = self._get_known_host_path()
        if not known_hosts.exists():
            return False
        try:
            result = run_command(
                f"ssh-keygen -F {host} {'-p ' + port if port else ''} -f {known_hosts}",
                raise_error=False,
            )
            return bool(result.stdout)
        except (OSError, ChildProcessError):
            return False

    def validate_if_keys_exists_and_valid(self, raise_if_not_valid: bool = True) -> bool:
        if not self.private_key_path.is_file() or not self.public_key_path.is_file():
            return False
        try:
            run_command(f"ssh-keygen -l -f {self.private_key_path}")
            run_command(f"ssh-keygen -l -f {self.public_key_path}")
        except Exception as exc:
            if raise_if_not_valid:
                raise exc
            return False
        return True
