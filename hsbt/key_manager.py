import os
from typing import Union
from pathlib import Path, PurePath
from hsbt.utils import run_command
import logging


log = logging.getLogger(__name__)


class KeyManager:
    def __init__(self, target_dir: Union[Path, str] = None, identifier: str = None):
        if target_dir is None:
            target_dir = Path(PurePath(Path.home(), ".ssh"))
        if not isinstance(target_dir, Path):
            target_dir: Path = Path(target_dir)
        if target_dir.is_file():
            raise ValueError(
                f"Path to key target must be a dir. got a file: '{target_dir}'"
            )
        target_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir = target_dir
        self.identifier = identifier if identifier else "hsbt_key"
        self.private_key_path: Path = None
        self.public_key_path: Path = None
        self.public_key_rfc_path: Path = None
        self.known_host_path: Path = None

    def ssh_keygen(
        self, overwrite_if_exists: bool = False, exists_ok=False, key_length: int = 2048
    ):
        private_key_file = "{}".format(self.identifier)
        public_key_file = "{}.pub".format(self.identifier)
        self.private_key_path = Path(PurePath(self.target_dir, private_key_file))
        self.public_key_path = Path(PurePath(self.target_dir, public_key_file))
        if (
            self.validate_if_keys_exists_and_valid()
            and not overwrite_if_exists
            and not exists_ok
        ):
            raise FileExistsError(
                f"Can not generate key at {self.private_key_path}, because file allready exists. Use the `overwrite_if_exist` param if you want to overwrite it. Or use the `exists_ok` param if the existing file is ok"
            )
        elif (
            self.validate_if_keys_exists_and_valid()
            and not overwrite_if_exists
            and exists_ok
        ):
            return
        run_command(
            f'ssh-keygen -b {key_length} -t rsa -f {self.private_key_path} -q -N ""'
        )

    def gen_rfc4716_format_copy(
        self,
        target_path: Union[Path, str] = None,
        overwrite_if_exist: bool = False,
        exists_ok=False,
    ) -> Path:
        if isinstance(target_path, str):
            target_path: Path = Path(target_path)
        elif target_path is None:
            target_path = Path(
                PurePath(
                    self.public_key_path.parent, self.public_key_path.stem + ".rfc.pub"
                )
            )
        if target_path.is_file() and not overwrite_if_exist and not exists_ok:
            raise FileExistsError(
                f"Can not convert {self.public_key_file} into RFC 4716 format, because file at target path `{target_path}` allready exists. Use the `overwrite_if_exist` param if you want to overwrite it. Or use the `exists_ok` param if the existing file is ok"
            )
        elif target_path.is_file() and not overwrite_if_exist and exists_ok:
            self.public_key_rfc_path = target_path
            return target_path
        run_command(
            f"ssh-keygen -e -f {self.public_key_path} -m RFC4716 > {target_path}"
        )
        self.public_key_rfc_path = target_path
        return target_path

    def get_private_key(self) -> bytes:
        with open(self.private_key_path, "rb") as f:
            return f.read()

    def get_public_key(self, in_rfc4716_format: bool = False) -> bytes:
        key_file_path = (
            self.public_key_rfc_path if in_rfc4716_format else self.public_key_path
        )
        with open(key_file_path, "rb") as f:
            return f.read()

    def _get_known_host_path(self):
        if self.known_host_path is None:
            self.known_host_path: Path = Path(PurePath(self.target_dir, "known_hosts"))
        return self.known_host_path

    def create_know_host_entry_if_not_exists(self, host: str):
        know_host_file: Path = self._get_known_host_path()
        if not self.known_host_entry_exists(host):
            run_command(
                f"ssh-keyscan -t dsa,rsa,ecdsa,ed25519 {host} >> {know_host_file}"
            )

    def known_host_entry_exists(self, host: str) -> bool:
        # https://unix.stackexchange.com/a/31556
        # todo: this function may be a little bit shaky. improve.
        know_host_file: Path = self._get_known_host_path()
        if not self.known_host_path.exists():
            return False
        try:
            result = run_command(f"ssh-keygen -F {host} -f {know_host_file}")
        except:
            return False
        if result.stdout:
            return True
        return False

    def validate_if_keys_exists_and_valid(
        self, raise_if_not_valid: bool = True
    ) -> bool:
        if not self.private_key_path.is_file():
            return False
        if not self.public_key_path.is_file():
            return False
        try:
            run_command(f"ssh-keygen -l -f {self.private_key_path}")
            log.debug(f"{self.private_key_path} is valid")
            run_command(f"ssh-keygen -l -f {self.public_key_path}")
            log.debug(f"{self.public_key_path} is valid")
        except Exception as r:
            if raise_if_not_valid:
                raise r
            return False

        return True
