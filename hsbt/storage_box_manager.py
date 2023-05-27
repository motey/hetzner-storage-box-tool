
from typing import Union

from pathlib import Path

from hsbt.utils import run_command
from hsbt.key_manager import KeyManager



class DeployKeyPasswordMissingError(Exception):
    pass

class HetznerStorageBox:
    def __init__(self, host: str, user: str, password: str=None, local_mount_point key_manager:KeyManager=None):
        self.host = host
        self.user = user
        self.password = password
        self.key_manager:KeyManager = key_manager

    def add_key_manager(self, key_manager:KeyManager=None):
        if key_manager is None:
            key_manager = KeyManager(identifier=f"hsbt_{self.user}")
        self.key_manager = key_manager

    def get_key_manager(self) -> KeyManager:
        if self.key_manager is None:
            self.add_key_manager()

    def deploy_public_key_if_not_done(self):
        self.get_key_manager()
        self.key_manager.create_know_host_entry_if_not_exists(self.host)
        if self.key_manager.private_key_path is None:
            self.key_manager.ssh_keygen(exists_ok=True)
        
        if self.check_if_public_key_is_deployed(self.key_manager.private_key_path):
            return
        if not self.password:
            raise DeployKeyPasswordMissingError(
                f"To deploy the SSH Key at {self.host} the first time, storage box password must be provided. After that future connections will be authorized by the deployd key and no password is needed anymore."
            )
        run_command(
            f"cat {self.key_manager.public_key_path} | sshpass -e ssh -p23 {self.user}@{self.host} install-ssh-key",
            extra_envs={"SSHPASS": self.password},
        )
        self.check_if_public_key_is_deployed(self.key_manager.private_key_path)
        
        return

    def check_if_public_key_is_deployed(self):
        self.get_key_manager()
        result = run_command(
            f"""ssh -v -t -i {self.key_manager.private_key_path} -o PasswordAuthentication=no \
                -o PreferredAuthentications=publickey -o StrictHostKeyChecking=no \
                -o UserKnownHostsFile={self.key_manager.known_host_path} {self.user}@{self.host} exit 2>&1 | grep 'Authentication succeeded'"""
        )

    def _run_remote_ssh_command(self,command:str):
        remote_command = f"ssh -p23 -i {self.key_manager.private_key_path} \
            -o PreferredAuthentications=publickey \
            -o UserKnownHostsFile={self.key_manager.known_host_path} \
            {self.user}@{self.host} \
            {command}"
        run_command(remote_command)

    def create_remote_directory(self, path:Union[str,Path]):
        if not isinstance(path, Path):
            path: Path = Path(path)
        self._run_remote_ssh_command(f"mkdir -p {path}")

    def storage_box_is_mounted(self):
        pass

    def mount_storage_box_via_fstab():
        # work on this example. its just mockup code
        fstab_entry = f"{self.storage_box_username}@{self.storage_box_hostname}:/ {self.local_mount_point} fuse.sshfs IdentityFile={self.keyfile_path},delay_connect,_netdev,user,idmap=user 0 0"
        with open("/etc/fstab", "a") as f:
            f.write(fstab_entry)

    def mount_storage_box_via_autofs():
        # work on this example. its just mockup code
        sshfs_cmd = f"sshfs -o password_stdin {self.storage_box_username}@{self.storage_box_hostname}:/ {self.local_mount_point}"
        sshfs_proc = subprocess.Popen(sshfs_cmd, stdin=subprocess.PIPE, shell=True)
        sshfs_proc.communicate(input=self.storage_box_password.encode())
