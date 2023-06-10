from typing import Union, Dict, List, Literal
import logging
from pathlib import Path
import os
from hsbt.utils import (
    run_command,
    convert_df_output_to_dict,
    ConfigFileEditor,
    CommandResult,
)
from hsbt.key_manager import KeyManager

log = logging.getLogger(__name__)


class DeployKeyPasswordMissingError(Exception):
    pass


class HetznerStorageBox:
    def __init__(
        self,
        local_mount_point: Union[str, Path],
        host: str,
        user: str,
        password: str = None,
        key_manager: KeyManager = None,
        remote_dir: Union[str, Path] = "/",
    ):
        if not isinstance(local_mount_point, Path):
            local_mount_point: Path = Path(local_mount_point)
        if not isinstance(remote_dir, Path):
            remote_dir: Path = Path(remote_dir)
        self.local_mount_point = local_mount_point
        self.remote_path = remote_dir
        self.host = host
        self.user = user

        self.password = password
        if self.password is None:
            os.getenv("HSBT_PASSWORD", None)
        self.key_manager: KeyManager = key_manager

    def add_key_manager(self, key_manager: KeyManager = None):
        if key_manager is None:
            key_manager = KeyManager(identifier=f"hsbt_{self.user}")
        self.key_manager = key_manager

    def get_key_manager(self) -> KeyManager:
        if self.key_manager is None:
            self.add_key_manager()

    def upload_file(self, local_path: Union[str, Path], remote_path: Union[str, Path]):
        if not isinstance(local_path, Path):
            local_path: Path = Path(local_path)
        if remote_path and not isinstance(local_path, Path):
            remote_path: Path = Path(remote_path)
        self.run_remote_command(
            f":{str(remote_path)}", extra_params={str(local_path): ""}, executor="scp"
        )

    def download_file(
        self, remote_path: Union[str, Path], local_path: Union[str, Path]
    ):
        if not isinstance(local_path, Path):
            local_path: Path = Path(local_path)
        if remote_path and not isinstance(local_path, Path):
            remote_path: Path = Path(remote_path)
        self.run_remote_command(
            f":{str(remote_path)} {str(local_path)}", executor="scp"
        )

    def _get_remote_authorized_keys(self):
        run_command(
            "sshpass -e sftp -oStrictHostKeyChecking=no -oPort=22 ${STORAGE_BOX_USER}@${STORAGE_BOX} <<<'mkdir /.ssh'"
        )

    def deploy_public_key_if_not_done(
        self, openssh_format: bool = True, rfc_format: bool = True
    ):
        self.get_key_manager()
        self.key_manager.create_know_host_entry_if_not_exists(self.host)
        if self.key_manager.private_key_path is None:
            self.key_manager.ssh_keygen(exists_ok=True)

        if self.check_if_public_key_is_deployed():
            return
        if not self.password:
            raise DeployKeyPasswordMissingError(
                f"To deploy your public SSH Key (`{self.key_manager.public_key_path}`) at `{self.host}` the first time, storage box password must be provided. After that future connections will be authorized by the deployed key and no password is required anymore."
            )
        run_command(
            f"cat {self.key_manager.public_key_path} | sshpass -e ssh -p23 {self.user}@{self.host} install-ssh-key",
            extra_envs={"SSHPASS": self.password},
        )
        self.check_if_public_key_is_deployed(self.key_manager.private_key_path)

        return

    def check_if_public_key_is_deployed(self) -> bool:
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
            log.error("Could determine ")

    def _get_ssh_options(
        self, pw: str = None, verbose: bool = True, extra_params: Dict = None
    ) -> Dict:
        options: Dict = {}
        if verbose:
            options = options | {
                "-v": "",
            }
        options = options | {
            "-o StrictHostKeyChecking=": "yes",
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
                "-o PreferredAuthentications=": "publickey",
                "-o PasswordAuthentication=": "no",
                "-o IdentityFile=": str(self.key_manager.private_key_path),
                "-o IdentitiesOnly=": "yes",
                "-o PubkeyAuthentication=": "yes",
            }
        # it is important to keep adding extra params at the end. this enables the caller to add string just before {self.user}@{self.host} so we can create scp commands as well
        if extra_params:
            options = options | extra_params

        return options

    def run_remote_command(
        self,
        command: str,
        pw: str = None,
        executor: Literal["ssh", "scp"] = "ssh",
        on_keyauth_fail_retry_with_pw_auth: bool = True,
        extra_params: Dict = None,
        verbose: bool = True,
        return_stdout_only: bool = True,
        raise_error: bool = True,
    ) -> str | CommandResult:
        options = self._get_ssh_options(
            pw=pw, verbose=verbose, extra_params=extra_params
        )
        if executor == "ssh":
            # ssh commands are added after the base command. scp params are added directly to the remote {self.user}@{self.host} part.
            # therefore we need to add a space to ssh commands
            command = f" {command}"

        remote_command = f"{'sshpass -e' if pw else ''} {executor} {' '.join([k+v for k,v in options.items()])} {self.user}@{self.host}{command}"

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

    def create_remote_directory(self, path: Union[str, Path]):
        if not isinstance(path, Path):
            path: Path = Path(path)
        self.run_remote_command(f"mkdir -p {path}")

    def storage_box_is_mounted(self):
        # wip
        pass

    def _mount_via_fstab(
        self,
        identifier: str,
        fstab_entry: str,
        fstab_file: Union[str, Path] = "/etc/fstab",
        remove: bool = True,
    ):
        fstab = ConfigFileEditor(fstab_file)
        if remove:
            run_command(f"umount --fstab {fstab.target_file} -a")
            fstab.remove_config_entry(identifier)

        else:
            fstab.set_config_entry(
                fstab_entry,
                identifier=identifier,
            )
            self.local_mount_point.mkdir(parents=True, exist_ok=True)
            run_command(f"mount --fstab {fstab.target_file} -a")

    def mount_storage_box_via_fstab_via_sshfs(
        self, fstab_file: Union[str, Path] = "/etc/fstab", remove: bool = False
    ):
        identifier = (
            f"{self.user}@{self.host}:{self.remote_path} {self.local_mount_point}"
        )
        fstab_entry = f"{self.user}@{self.host}:{self.remote_path} {self.local_mount_point} fuse.sshfs IdentityFile={self.key_manager.private_key_path},_netdev,nofail,delay_connect,_netdev,user,idmap=user,reconnect 0 0"
        self._mount_via_fstab(
            identifier=identifier,
            fstab_entry=fstab_entry,
            fstab_file=fstab_file,
            remove=remove,
        )

    def mount_storage_box_via_fstab_with_rclone(
        self, fstab_file: Union[str, Path] = "/etc/fstab", remove: bool = False
    ):
        # https://rclone.org/commands/rclone_mount/
        # sftp1:subdir /mnt/data rclone rw,noauto,nofail,_netdev,x-systemd.automount,args2env,vfs_cache_mode=writes,config=/etc/rclone.conf,cache_dir=/var/cache/rclone 0 0
        raise NotImplementedError()
        identifier = (
            f"{self.user}@{self.host}:{self.remote_path} {self.local_mount_point}"
        )
        fstab_entry = f"{self.user}@{self.host}:{self.remote_path} {self.local_mount_point} rclone IdentityFile={self.key_manager.private_key_path},_netdev,nofail,delay_connect,_netdev,user,idmap=user,reconnect 0 0"
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

    def get_available_space(self, human_readable: bool = False) -> Dict:
        # https://docs.hetzner.com/robot/storage-box/available-disk-space
        # wip
        raise NotImplementedError()
        convert_df_output_to_dict()
