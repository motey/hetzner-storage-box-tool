from typing import Union, Dict, List, Literal
import logging
from pathlib import Path, PurePath
import os
from hsbt.utils import (
    run_command,
    cast_path,
    convert_df_output_to_dict,
    ConfigFileEditor,
    CommandResult,
    FileInfoCollection,
    FileInfo,
    parse_ls_l_output,
)
from hsbt.key_manager import KeyManager
from hsbt.connection_manager import ConnectionManager

import uuid

log = logging.getLogger(__name__)


class DeployKeyPasswordMissingError(Exception):
    pass


class HetznerStorageBox:
    def __init__(
        self,
        host: str,
        user: str,
        password: str = None,
        key_manager: KeyManager = None,
        remote_dir: str | Path = "/home",
    ):
        if remote_dir is None:
            remote_dir = "/home"
        if remote_dir == "/":
            log.warning(
                "Hint: The root directory ('/') is defined as entry point on the remote storage (param: `remote_dir` for `hsbt.HetznerStorageBox`). \
                On Hetzner storageboxes there is no access to the root dir."
            )
        self.remote_base_path: Path = cast_path(remote_dir)
        self.host: str = host
        self.user: str = user

        self.password: str = password
        self.key_manager: KeyManager = key_manager

    @classmethod
    def from_connection(cls, con: ConnectionManager.Connection):
        return HetznerStorageBox(
            host=con.host,
            user=con.user,
            password=None,
            key_manager=KeyManager(target_dir=con.key_dir, identifier=con.identifier),
        )

    def _create_remote_directory(self, path: str | Path):
        path = cast_path(path)
        if not isinstance(path, Path):
            path: Path = Path(path)
        self.run_remote_command(f"mkdir -p {path}")

    def create_remote_directory(self, path: str | Path):
        path = cast_path([path])
        self.run_remote_command(f"mkdir -p {path}")

    def _upload_file(self, local_path: str | Path, remote_path: str | Path):
        remote_path: Path = cast_path(remote_path)
        local_path: Path = cast_path(local_path)
        self.run_remote_command(
            f":{str(remote_path)}", extra_params={str(local_path): ""}, executor="scp"
        )

    def upload_file(self, local_path: str | Path, remote_path: str | Path):
        remote_path: Path = self._inject_base_path_to_abs_path(remote_path)
        local_path: Path = cast_path(local_path)
        self._upload_file(local_path=local_path, remote_path=remote_path)

    def download_file(self, remote_path: str | Path, local_path: str | Path):
        remote_path: Path = self._inject_base_path_to_abs_path(remote_path)
        local_path: Path = cast_path(local_path)
        self._download_file(remote_path=remote_path, local_path=local_path)

    def _download_file(self, remote_path: str | Path, local_path: str | Path):
        remote_path: Path = cast_path(remote_path)
        local_path: Path = cast_path(local_path)
        self.run_remote_command(
            f":{str(remote_path)} {str(local_path)}", executor="scp"
        )

    def _list_remote_files(self, remote_path: str | Path) -> FileInfoCollection:
        remote_path = cast_path(remote_path)
        return parse_ls_l_output(self.run_remote_command(f"ls -la {remote_path}"))

    def list_remote_files(self, remote_path: str | Path = ".") -> FileInfoCollection:
        remote_path: Path = self._inject_base_path_to_abs_path(remote_path)
        return self._list_remote_files(remote_path)

    def get_available_space(self, human_readable_file_sizes: bool = False) -> Dict:
        # https://docs.hetzner.com/robot/storage-box/available-disk-space
        return convert_df_output_to_dict(
            self.run_remote_command(f"df{' -h' if human_readable_file_sizes else ''}")
        )

    def add_key_manager(self, key_manager: KeyManager = None):
        if key_manager is None:
            key_manager = KeyManager(identifier=self.host)
        self.key_manager = key_manager

    def get_key_manager(self) -> KeyManager:
        if self.key_manager is None:
            self.add_key_manager()
        return self.key_manager

    def _get_remote_authorized_keys(
        self, generate_empty_file_if_not_exist: bool = True
    ) -> Path:
        target_local_path: Path = Path(f"/tmp/{uuid.uuid4().hex}")
        if (
            self._list_remote_files(".").get_file_info(".ssh") is None
            or self._list_remote_files(".ssh").get_file_info("authorized_keys") is None
        ) and generate_empty_file_if_not_exist:
            self.run_remote_command("mkdir -p .ssh")
            self.run_remote_command("touch .ssh/authorized_keys")
        self._download_file(
            remote_path=".ssh/authorized_keys", local_path=target_local_path
        )
        return target_local_path

    def deploy_public_key_if_not_done(self, sftp_mode: bool = False):
        self.get_key_manager()
        self.key_manager.create_known_host_entry_if_not_exists(
            self.host, ports=[22, 23]
        )
        if self.key_manager.private_key_path is None:
            self.key_manager.ssh_keygen(exists_ok=True)
        if self.public_key_is_deployed():
            return
        if not self.password:
            raise DeployKeyPasswordMissingError(
                f"To deploy your public SSH Key (`{self.key_manager.public_key_path}`) at `{self.host}` the first time, storage box password must be provided. After that future connections will be authorized by the deployed key and no password is required anymore."
            )
        options = {"-s": ""} if sftp_mode else {}
        result: CommandResult = self.run_remote_command(
            "",
            executor="ssh-copy-id",
            extra_params={"-i ": str(self.key_manager.public_key_path)} | options,
            verbose=False,
            return_stdout_only=False,
            raise_error=False,
        )
        if 'ssh-copy-id is only supported with the "-s" argument.' in result.stdout:
            self.deploy_public_key_if_not_done(sftp_mode=True)
        elif result.error_for_raise:
            raise result.error_for_raise

        return

    def public_key_is_deployed(self) -> bool:
        # https://docs.hetzner.com/de/robot/storage-box/backup-space-ssh-keys
        self.get_key_manager()
        command_result: CommandResult = self.run_remote_command(
            "exit",
            on_keyauth_fail_retry_with_pw_auth=False,
            verbose=True,
            return_stdout_only=False,
            raise_error=False,
        )
        if command_result.return_code == 255:
            log.debug(
                f"Your local public key ('{self.key_manager.public_key_path}') is probably not deployed at your Hetzner Storage Box ('{self.host}'). Check debug output for more details if needed. Executed command: `{command_result.command}`, Result error code: `{command_result.return_code}`, debug output: `{command_result.stderr}`"
            )
            return False
        elif command_result.return_code == 0:
            return True
        else:
            log.error("Could determine if key is deployd")

    def _get_ssh_options(
        self,
        pw: str = None,
        verbose: bool = True,
        extra_params: Dict = None,
        only_ssh_o_options: bool = False,
    ) -> Dict:
        options: Dict = {}
        if verbose:
            options = options | {
                "-v": "",
            }
        options = options | {
            "-o UserKnownHostsFile=": str(self.key_manager._get_known_host_path()),
            "-o Port=": "23",
        }

        if pw:
            options = options | {
                "-o PreferredAuthentications=": "password",
                "-o PasswordAuthentication=": "yes",
                "-o PubkeyAuthentication=": "no",
            }
        else:
            options = options | {
                "-o StrictHostKeyChecking=": "yes",
                "-o PreferredAuthentications=": "publickey",
                "-o PasswordAuthentication=": "no",
                "-o IdentityFile=": str(self.key_manager.private_key_path),
                "-o IdentitiesOnly=": "yes",
                "-o PubkeyAuthentication=": "yes",
            }
        # it is important to keep adding extra params at the end. this enables the caller to add string just before {self.user}@{self.host} so we can create scp commands as well
        if extra_params:
            options = options | extra_params
        if only_ssh_o_options:
            filtered_options: Dict = {}
            for key, val in options.items():
                if key.startswith("-o "):
                    filtered_options[key.lstrip("-o ")] = val
            return filtered_options

        return options

    def run_remote_command(
        self,
        command: str,
        pw: str = None,
        executor: Literal["ssh", "scp", "ssh-copy-id"] = "ssh",
        on_keyauth_fail_retry_with_pw_auth: bool = True,
        extra_params: Dict = None,
        verbose: bool = False,
        return_stdout_only: bool = True,
        raise_error: bool = True,
        dry_run: bool = False,
    ) -> str | CommandResult:
        """_summary_

        Args:
            command (str): _description_
            pw (str, optional): _description_. Defaults to None.
            executor (Literal[&quot;ssh&quot;, &quot;scp&quot;, &quot;ssh, optional): _description_. Defaults to "ssh".
            on_keyauth_fail_retry_with_pw_auth (bool, optional): _description_. Defaults to True.
            extra_params (Dict, optional): _description_. Defaults to None.
            verbose (bool, optional): _description_. Defaults to False.
            return_stdout_only (bool, optional): _description_. Defaults to True.
            raise_error (bool, optional): _description_. Defaults to True.
            dry_run (bool, optional): Only generate and return the command. Do not execute it. Defaults to False.

        Raises:
            command_result.error_for_raise: _description_

        Returns:
            str | CommandResult: _description_
        """
        options = self._get_ssh_options(
            pw=pw, verbose=verbose, extra_params=extra_params
        )
        if executor == "ssh":
            # ssh commands are added after the base command. scp param/path is added directly to the remote {self.user}@{self.host} part.
            # therefore we need to add a space to ssh commands
            command = f" {command}"
        sshpass = f"{'sshpass -e ' if pw else ''}"
        if dry_run and pw:
            # dry run can be used to generate command. We contain the password to make the command to be able to be executed as it is
            sshpass = f" sshpass -p {pw} "
        remote_command = f"{sshpass}{executor} {' '.join([k+v for k,v in options.items()])} {self.user}@{self.host}{command}"
        if dry_run:
            return CommandResult(command=remote_command)
        command_result = run_command(
            remote_command, extra_envs={"SSHPASS": pw} if pw else {}, raise_error=False
        )
        if (
            command_result.return_code != 0
            and on_keyauth_fail_retry_with_pw_auth
            and self.password is not None
        ):
            # return code 255 means a ssh error. No connection could be established
            # propably there is an problem with the ssh key or its just not deployed yet.
            # if the password provided by the caller in this 'HetznerStorageBox'-instance we can retry it with a password provided connection

            log.debug(
                f"Retry ssh remote command '{command}' with password authentication"
            )
            return self.run_remote_command(
                command=command,
                pw=self.password,
                executor=executor,
                on_keyauth_fail_retry_with_pw_auth=False,
                extra_params=extra_params,
                verbose=verbose,
                return_stdout_only=return_stdout_only,
                raise_error=raise_error,
            )
        elif command_result.return_code != 0 and raise_error:
            raise command_result.error_for_raise
        return command_result.stdout if return_stdout_only else command_result

    def storage_box_is_mounted(self):
        # wip
        raise NotImplementedError()

    def get_mount_commands_for_sshfs(
        self,
        local_mountpoint: str | Path = None,
    ) -> str:
        if local_mountpoint is None:
            local_mountpoint = Path(f"/mnt/{self.key_manager.identifier}")
        else:
            local_mountpoint = cast_path(local_mountpoint)
        options = self._get_ssh_options(pw=None, verbose=False, only_ssh_o_options=True)
        # hackfix - PubkeyAuthentication is not compatible iwth fuse.sshfs
        options.pop("PubkeyAuthentication=")
        return f"""sudo sshfs -o {",".join(k + v for k, v in options.items())},allow_other,default_permissions {self.user}@{self.host}:{self.remote_base_path} {local_mountpoint}"""

    def _mount_via_fstab(
        self,
        identifier: str,
        fstab_entry: str,
        local_mountpoint: str | Path = None,
        fstab_file: Union[str, Path] = "/etc/fstab",
        remove: bool = True,
    ):
        # https://manpages.debian.org/testing/fuse/mount.fuse.8.en.html
        if local_mountpoint is None:
            local_mountpoint = Path(f"/mnt/{self.key_manager.identifier}")
        else:
            local_mountpoint = cast_path(local_mountpoint)
        fstab = ConfigFileEditor(fstab_file)
        if remove:
            run_command(f"umount --fstab {fstab.target_file} -a")
            fstab.remove_config_entry(identifier)
        else:
            fstab.set_config_entry(
                fstab_entry,
                identifier=identifier,
            )
            local_mountpoint.mkdir(parents=True, exist_ok=True)
            run_command(f"mount --fstab {fstab.target_file} -a")

    def mount_storage_box_via_fstab_via_sshfs(
        self,
        local_mountpoint: str | Path = None,
        fstab_file: Union[str, Path] = "/etc/fstab",
        remove: bool = False,
        user_id: str | int = None,
        group_id: str | int = None,
    ):
        if user_id is None:
            user_id = os.getuid()
        if group_id is None:
            group_id = os.getgid()
        user_id = str(user_id)
        group_id = str(group_id)
        identifier = f"{self.user}@{self.host}:{self.remote_base_path} {local_mountpoint} {self.key_manager.identifier}"
        options = self._get_ssh_options(pw=None, verbose=False, only_ssh_o_options=True)
        # hackfix - PubkeyAuthentication is not compatible iwth fuse.sshfs
        options.pop("PubkeyAuthentication=")
        # /hackfix
        fstab_entry = f"{self.user}@{self.host}:{self.remote_base_path} {local_mountpoint} fuse.sshfs {','.join(k+v for k,v in  options.items())},_netdev,delay_connect,users,uid={user_id},gid={group_id},reconnect 0 0"
        self._mount_via_fstab(
            local_mountpoint=local_mountpoint,
            identifier=identifier,
            fstab_entry=fstab_entry,
            fstab_file=fstab_file,
            remove=remove,
        )

    def mount_storage_box_via_fstab_with_rclone(
        self,
        local_mountpoint: str | Path = None,
        fstab_file: Union[str, Path] = "/etc/fstab",
        remove: bool = False,
    ):
        # https://rclone.org/commands/rclone_mount/
        # sftp1:subdir /mnt/data rclone rw,noauto,nofail,_netdev,x-systemd.automount,args2env,vfs_cache_mode=writes,config=/etc/rclone.conf,cache_dir=/var/cache/rclone 0 0
        raise NotImplementedError()
        identifier = (
            f"{self.user}@{self.host}:{self.remote_base_path} {self.local_mount_point}"
        )
        fstab_entry = f"{self.user}@{self.host}:{self.remote_base_path} {self.local_mount_point} rclone IdentityFile={self.key_manager.private_key_path},_netdev,nofail,delay_connect,_netdev,user,idmap=user,reconnect 0 0"
        self._mount_via_fstab(
            identifier=identifier,
            fstab_entry=fstab_entry,
            fstab_file=fstab_file,
            remove=remove,
        )

    def mount_storage_box_via_autofs_with_sshfs(self):
        # wip: work on this example. its just mockup code
        # https://community.hetzner.com/tutorials/setup-autofs-mount-storagebox
        raise NotImplementedError()
        sshfs_cmd = f"sshfs -o password_stdin {self.storage_box_username}@{self.storage_box_hostname}:/ {self.local_mount_point}"
        sshfs_proc = subprocess.Popen(sshfs_cmd, stdin=subprocess.PIPE, shell=True)
        sshfs_proc.communicate(input=self.storage_box_password.encode())

    def mount_storage_box_via_autofs_with_rclone(self):
        # https://rclone.org/commands/rclone_mount/
        raise NotImplementedError()
        pass

    def mount_storage_box_via_automount_with_sshfs(self):
        # wip: work on this example. its just mockup code
        # https://community.hetzner.com/tutorials/setup-autofs-mount-storagebox
        raise NotImplementedError()
        sshfs_cmd = f"sshfs -o password_stdin {self.storage_box_username}@{self.storage_box_hostname}:/ {self.local_mount_point}"
        sshfs_proc = subprocess.Popen(sshfs_cmd, stdin=subprocess.PIPE, shell=True)
        sshfs_proc.communicate(input=self.storage_box_password.encode())

    def mount_storage_box_via_automount_with_rclone(self):
        # https://rclone.org/commands/rclone_mount/
        raise NotImplementedError()

    def temp_mount_storage_box_via_sshfs():
        raise NotImplementedError()

    def temp_mount_storage_box_via_rclone():
        raise NotImplementedError()

    def _inject_base_path_to_abs_path(self, path: str | Path):
        path: Path = cast_path(path)
        if path and len(path.parts) != 0 and path.parts[0] == "/":
            # remove trailing slash to convert path into a "relative" path
            path = Path(PurePath(*path.parts[1:]))
        return Path(PurePath(self.remote_base_path, path))
