from typing import Dict
from enum import Enum


class EnvVarNames(str, Enum):
    CENTRAL_CONFIG_DIR = "HSBT_CENTRAL_CONFIG_DIR"
    CONNECTION_CONFIG_FILE = "HSBT_CONNECTIONS_CONFIG_FILE"
    SSH_KEY_DIRECTORY = "HSBT_SSH_KEY_FILE_DIR"
    RCLONE_CONFIG_FILE = "HSBT_RCLONE_CONFIG_FILE"
    PASSWORD = "HSBT_PASSWORD"
    BIN_PATH_RCLONE = "HSBT_BIN_PATH_RCLONE"
    BIN_PATH_SSH = "HSBT_BIN_PATH_RCLONE"
    BIN_PATH_SSHFS = "HSBT_BIN_PATH_SSHFS"
    BIN_PATH_SCP = "HSBT_BIN_PATH_SCP"
    BIN_PATH_SSH_COPY_ID = "HSBT_BIN_PATH_SSH_COPY_ID"
    BIN_PATH_SSHPASS = "HSBT_BIN_PATH_SSHPASS"
    BIN_PATH_MOUNT = "HSBT_BIN_PATH_MOUNT"
    BIN_PATH_UMOUNT = "HSBT_BIN_PATH_UMOUNT"


EXECUTABLE_PATH_ENV_VAR_MAPPING: Dict[str, EnvVarNames] = {
    "rclone": EnvVarNames.BIN_PATH_RCLONE,
    "ssh": EnvVarNames.BIN_PATH_SSH,
    "sshfs": EnvVarNames.BIN_PATH_SSHFS,
    "scp": EnvVarNames.BIN_PATH_SCP,
    "ssh-copy-id": EnvVarNames.BIN_PATH_SSH_COPY_ID,
    "sshpass": EnvVarNames.BIN_PATH_SSHPASS,
    "umount": EnvVarNames.BIN_PATH_UMOUNT,
    "mount": EnvVarNames.BIN_PATH_MOUNT,
}
