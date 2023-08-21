from typing import List, Any, Literal, Dict
import os, sys
from pathlib import Path, PurePath
import click

import logging
import yaml
from enum import Enum


log = logging.getLogger(__name__)

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")
    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))

from hsbt.connection_manager import ConnectionManager
from hsbt.storage_box_manager import HetznerStorageBox, CommandResult
from hsbt.key_manager import KeyManager
from hsbt.utils import is_root, cast_path
from hsbt.env_var_names import EnvVarNames, EXECUTABLE_PATH_ENV_VAR_MAPPING
from hsbt.rclone_manager import Rclone


def get_config_file_path(caller_param_config_file_path: None | str | Path) -> Path:
    config_file_path: Path = cast_path(caller_param_config_file_path)
    if caller_param_config_file_path is None:
        config_file_path = cast_path(
            os.getenv(EnvVarNames.CONNECTION_CONFIG_FILE, default=None)
        )
    central_dir = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, default=None)
    if config_file_path is None and central_dir:
        return cast_path([central_dir, "config", "hetzner_sbt_connections.json"])
    return config_file_path


def get_ssh_dir(caller_param_config_file_path: None | str | Path) -> Path:
    config_file_path: Path = cast_path(caller_param_config_file_path)
    if caller_param_config_file_path is None:
        config_file_path = cast_path(
            os.getenv(EnvVarNames.SSH_KEY_DIRECTORY, default=None)
        )
    central_dir = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, default=None)
    if config_file_path is None and central_dir:
        return cast_path([central_dir, "ssh"])
    return config_file_path


def get_rclone_config_file_path(
    caller_param_config_file_path: None | str | Path,
) -> Path:
    config_file_path: Path = cast_path(caller_param_config_file_path)
    print("caller_param_config_file_path", caller_param_config_file_path)
    if caller_param_config_file_path is None:
        config_file_path = cast_path(
            os.getenv(EnvVarNames.RCLONE_CONFIG_FILE, default=None)
        )
    central_dir = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, default=None)
    if config_file_path is None and central_dir:
        return cast_path([central_dir, "rclone", "rclone.conf"])
    return config_file_path


def ssh_dir_callback(
    ctx: click.Context, param: click.Option, connection_identifier: Any
):
    return get_ssh_dir(connection_identifier)


def conditonal_connection_prompts(
    ctx: click.Context, param: click.Option, connection_identifier: Any
):
    if not connection_identifier in ["", None]:
        for other_param in ctx.command.params:
            if other_param.name in ["host", "user", "ssh_key_dir"]:
                other_param.prompt = None
                other_param.required = False
                other_param.default = None

    else:
        click.echo(
            "No connection identifier ('-i'/'--identifier') provided. Will prompt for connection details."
        )
    return connection_identifier


def connection_options(
    with_prompting: bool = False,
    optional: bool = False,
    exlude_params: List[str] = None,
):
    if exlude_params is None:
        exlude_params = []

    def connection_options_generator(function):
        default_param = dict()
        if optional:
            default_param["default"] = None
        else:
            default_param["required"] = True
        help_optional_postfix = ". Only required if ('-i'/'--identifier') is empty."
        ###
        ### force-password-use
        ###
        if "force-password-use" not in exlude_params:
            function = click.option(
                "-f",
                "--force-password-use",
                type=click.BOOL,
                is_flag=True,
                required=False,
                help="To skip ssh key generation and deployment use the flag '-f'. A password must be provided",
                default=False,
            )(function)
        ###
        ### password
        ###
        if "password" not in exlude_params:
            function = click.option(
                "-p",
                "--password",
                type=click.STRING,
                hide_input=True,
                required=False,
                help="Password for the Hetzner Storage Box user. Only needed for first time setup or '--force-password-use'",
                default=False,
            )(function)
        ###
        ### config-file-path
        ###

        default = (
            "/etc/hetzner_sbt_connections.json"
            if is_root()
            else "~/.config/hetzner_sbt_connections.json"
        )
        default_from_env = get_config_file_path(None)
        if default_from_env:
            default = default_from_env
        function = click.option(
            "-c",
            "--config-file-path",
            type=click.STRING,
            required=False,
            help="hsbt saves connection infos into a json file. By default root will store connections into '/etc/hetzner_sbt_connections.json' and any other user in '~/.config/hetzner_sbt_connections.json'",
            default=default,
        )(function)
        ###
        ### ssh-key-dir
        ###
        help = "Directory to store the public-, private-key and known_hosts files."
        if optional:
            help += help_optional_postfix
        function = click.option(
            "-s",
            "--ssh-key-dir",
            type=click.STRING,
            prompt="Directory to store ssh private and public key"
            if with_prompting and get_ssh_dir(None) is None
            else None,
            help=help,
            default="~/.ssh/" if get_ssh_dir(None) is None else get_ssh_dir(None),
            callback=ssh_dir_callback,
        )(function)
        ###
        ### user
        ###
        help = "The username to connect to the Hetzner storage box. e.g. 'u0000001' or 'u00000001-sub1'"
        if optional:
            help += help_optional_postfix
        function = click.option(
            "-u",
            "--user",
            type=click.STRING,
            prompt="Username of the Hetzner storage Box" if with_prompting else None,
            help=help,
            **default_param,
        )(function)
        ###
        ### host
        ###
        help = "The hostname to reach the reach the Hetzner storage box e.g. 'u000001.your-storagebox.de'"
        if optional:
            help += help_optional_postfix
        function = click.option(
            "-h",
            "--host",
            type=click.STRING,
            prompt="Host name of the Hetzner storage box" if with_prompting else None,
            help=help,
            **default_param,
        )(function)

        return function

    return connection_options_generator


def get_executable_binary_path_map() -> Dict[str, str]:
    map = {}
    for name, envvar in EXECUTABLE_PATH_ENV_VAR_MAPPING.items():
        map[name] = os.getenv(envvar.value, name)
    return map


def get_and_validate_storage_box_connection(
    identifier: str = None,
    host: str = None,
    user: str = None,
    ssh_key_dir: str = None,
    password: str = None,
    config_file_path: str = None,
    force_password_use: bool = False,
    validate_connection: bool = False,
) -> HetznerStorageBox:
    config_file_path: Path = get_config_file_path(config_file_path)
    ssh_key_dir: Path = get_ssh_dir(ssh_key_dir)
    con = None
    if password is None:
        password = cast_path(os.getenv(EnvVarNames.PASSWORD, default=None))
    hsbt: HetznerStorageBox = None
    if identifier not in [None, ""]:
        conman = ConnectionManager(target_config_file=config_file_path)
        con = conman.get_connection(identifier=identifier)
        if con is None:
            raise click.UsageError(
                f"Could not find a connection with the identifier '{identifier}'. Use 'hsbt listConnection' to see available connections and/or create a new connection with 'hsbt setConnection'"
            )
        hsbt = HetznerStorageBox.from_connection(con)

        hsbt.binaries = get_executable_binary_path_map()
    else:
        hsbt = HetznerStorageBox(
            host=host,
            user=user,
            key_manager=KeyManager(
                target_dir=ssh_key_dir, identifier=identifier if identifier else host
            ),
        )
        hsbt.binaries = get_executable_binary_path_map()
    if force_password_use or (
        validate_connection and not hsbt.public_key_is_deployed()
    ):
        if password is None:
            password = click.prompt(
                f"Password for Hetzner Storage Box user {user if con is None else con.user}",
                type=click.STRING,
                hide_input=True,
            )
        hsbt.password = password
        if not force_password_use:
            # first time use of connection. We will create the if necessary and deploy it to the Hetzner storageBox
            key_just_deployd: bool = hsbt.deploy_public_key_if_not_done()
            if key_just_deployd:
                click.echo(
                    f"Deployd public key '{hsbt.key_manager.public_key_path}' at '{hsbt.host}'."
                )
    return hsbt


@click.group()
@click.option("--debug/--no-debug", default=False)
def cli(debug):
    if debug:
        click.echo(f"Debug mode is on")
        logging.basicConfig(level="DEBUG")


@cli.command(
    name="setConnection",
    help="Define a new named connection to reference in all other commands",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    prompt="Identifying name for the connection",
    help="An identifier to point to the connection in all other commands.",
)
@connection_options(
    with_prompting=True,
    optional=False,
    exlude_params=["force-password-use", "password"],
)
@click.option(
    "-o",
    "--overwrite-existing",
    type=click.BOOL,
    is_flag=True,
    help="If a connection configuration with the same identifier already exists, this command will fail. If you are sure you want to overwrite it pass '-o' to the command to update the existing connection configuration",
    default=False,
)
@click.option(
    "-k",
    "--skip-key-deployment",
    type=click.BOOL,
    is_flag=True,
    help="If set will not do any external communication. This can be helpful for pre-creating the connection config file. If the key is not deployed, hsbt will ask for the password on first use of the connection to exchange the key then.",
    default=False,
)
def set_connection(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir: str | Path,
    overwrite_existing: bool,
    config_file_path: str,
    skip_key_deployment: bool,
):
    config_file_path: Path = get_config_file_path(config_file_path)
    ssh_key_dir: Path = get_ssh_dir(ssh_key_dir)
    connection_manager = ConnectionManager(target_config_file=config_file_path)
    con = connection_manager.set_connection(
        identifier=identifier,
        user=user,
        host=host,
        key_dir=ssh_key_dir,
        overwrite_existing=overwrite_existing,
        exists_ok=False,
    )
    if not skip_key_deployment:
        get_and_validate_storage_box_connection(
            con.identifier, validate_connection=True, config_file_path=config_file_path
        )
    click.echo(f"Saved connection at '{connection_manager.target_config_file}' as:")
    click.echo(f"\t{con}")

    # ConnectionManager(target_config_file=)


@cli.command(
    name="repairConnection",
    help="Check if keys and known_hosts_file are existing valid, and deployd. If not try to fix it.",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    prompt="Identifying name for the connection",
    help="An identifier to point to the connection in all other commands.",
)
@click.option(
    "-c",
    "--config-file-path",
    type=click.STRING,
    required=False,
    help="hsbt saves connection infos into a json file. By default root will store connections into '/etc/hetzner_sbt_connections.json' and any other user in '~/.config/hetzner_sbt_connections.json'",
    default="/etc/hetzner_sbt_connections.json"
    if is_root()
    else "~/.config/hetzner_sbt_connections.json",
)
def repair_connection(identifier: str, config_file_path: str):
    config_file_path: Path = get_config_file_path(config_file_path)

    connection_manager = ConnectionManager(target_config_file=config_file_path)
    con = connection_manager.get_connection(identifier=identifier)
    if con is None:
        raise click.UsageError(
            f"Could not find a connection with the identifier '{identifier}' to be repaired. Use 'hsbt listConnection' to see available connections and/or create a new connection with 'hsbt setConnection'"
        )
    hsbt = get_and_validate_storage_box_connection(
        identifier=identifier, validate_connection=True
    )
    if hsbt.public_key_is_deployed():
        click.echo("Connection seems to work (again).")
    else:
        # todo: provide some more data for debugging
        raise ConnectionError("Can not repair connection.")


@cli.command(
    name="deleteConnection",
    help="Define a new named connection to reference in all other commands",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    prompt="Identifying name for the connection",
    help="An identifier to point to the connection in all other commands.",
)
@click.option(
    "-m",
    "--missing-ok",
    type=click.BOOL,
    is_flag=True,
    help="If a connection configuration with the same identifier already exists, this command will fail. If you are sure you want to overwrite it pass '-o' to the command to update the existing connection configuration",
    default=False,
)
@click.option(
    "-c",
    "--config-file-path",
    type=click.STRING,
    required=False,
    help="hsbt saves connection infos into a json file. By default root will store connections into '/etc/hetzner_sbt_connections.json' and any other user in '~/.config/hetzner_sbt_connections.json'",
    default="/etc/hetzner_sbt_connections.json"
    if is_root()
    else "~/.config/hetzner_sbt_connections.json",
)
@click.option(
    "-k",
    "--delete-keys",
    type=click.BOOL,
    is_flag=True,
    help="Delete ssh keys that are mapped to this connection as well.",
    default=False,
)
def delete_connection(
    identifier: str,
    config_file_path: str | Path,
    delete_keys: bool,
    missing_ok: bool,
):
    config_file_path: Path = get_config_file_path(config_file_path)

    connection_manager = ConnectionManager(target_config_file=config_file_path)
    con = connection_manager.get_connection(identifier=identifier)
    if con is not None and delete_keys:
        hsbt = HetznerStorageBox.from_connection(con)
        hsbt.key_manager.private_key_path.unlink(missing_ok=True)
        hsbt.key_manager.public_key_path.unlink(missing_ok=True)
    connection_manager.delete_connection(identifier=identifier, missing_ok=missing_ok)


@cli.command(name="listConnection")
@click.option(
    "-f",
    "--format-output",
    type=click.Choice(["json", "yaml"], case_sensitive=False),
    multiple=False,
    default=None,
)
@click.option(
    "-c",
    "--config-file-path",
    type=click.STRING,
    help="Alternative config file instead of '/etc/hetzner_sbt_connections.json' and '~/.config/hetzner_sbt_connections.json'",
    default=None,
)
def list_connections(format_output, config_file_path):
    config_file_path: Path = get_config_file_path(config_file_path)

    connection_manager = ConnectionManager(target_config_file=config_file_path)

    if format_output == "yaml":
        output = yaml.dump(connection_manager.list_connections().dict())
    else:
        output = connection_manager.list_connections().json()
    click.echo(output)


@cli.command(
    name="remoteCmd",
    help="Run a command at the Hetzner storage box. See https://docs.hetzner.com/robot/storage-box/access/access-sshsync-borg#available-commands for available commands",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    help="An identifier of an existing connection defined with 'hsbt setConnection'. Alternatively set '--user' and '--host' to define a connection on the fly (which will not be saved).",
    default="",
    callback=conditonal_connection_prompts,
)
@connection_options(with_prompting=False, optional=True)
@click.option(
    "-n",
    "--no-exec",
    type=click.BOOL,
    is_flag=True,
    default=False,
    help="Only return the local ssh command with all parameters to run the remote command",
)
@click.argument(
    "command",
    type=click.STRING,
)
def run_remote_command(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir: str | Path,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    command: str,
    no_exec: bool,
) -> str:
    config_file_path: Path = get_config_file_path(config_file_path)
    ssh_key_dir: Path = get_ssh_dir(ssh_key_dir)
    hsbt: HetznerStorageBox = get_and_validate_storage_box_connection(
        identifier=identifier,
        host=host,
        user=user,
        ssh_key_dir=ssh_key_dir,
        password=password,
        config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    result: CommandResult = hsbt.run_remote_command(
        command, dry_run=no_exec, return_stdout_only=False
    )
    click.echo(result.command if no_exec else result.stdout)


@cli.command(
    name="mount",
    help="Run a command at the Hetzner storage box. See https://docs.hetzner.com/robot/storage-box/access/access-ssh-rsync-borg#available-commands for available commands",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    help="An identifier of an existing connection defined with 'hsbt setConnection'. Alternatively set '--user' and '--host' to define a connection on the fly (which will not be saved).",
    default="",
    callback=conditonal_connection_prompts,
)
@connection_options(with_prompting=True, optional=True)
@click.option(
    "-r",
    "--rclone-config-file",
    type=click.STRING,
    default=None,
)
@click.option(
    "-m",
    "--mount-point",
    type=click.STRING,
)
@click.option(
    "-t",
    "--mount-tool",
    type=click.Choice(["sshfs", "rclone"], case_sensitive=False),
    multiple=False,
    default="rclone",
)
def mount(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir: str | Path,
    password: str,
    config_file_path: str,
    force_password_use: str,
    rclone_config_file: str,
    mount_point: str,
    mount_tool: Literal["sshfs", "rclone"],
):
    hsbt: HetznerStorageBox = get_and_validate_storage_box_connection(
        identifier=identifier,
        host=host,
        user=user,
        ssh_key_dir=ssh_key_dir,
        password=password,
        config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    if mount_tool == "sshfs":
        log.warning(
            "sshfs is unmaintained at the moment. see https://github.com/libfuse/sshfs for more details. \
            It is recommended to use rclone (https://rclone.org/commands/rclone_mount/) as mounting tool. \
            Just use the '-t rclone' / '--mount-tool=rclone' parameter."
        )
        hsbt.mount_storage_box_via_sshfs(local_mountpoint=mount_point)
    elif mount_tool == "rclone":
        rclone = Rclone(
            storage_box_manager=hsbt,
            config_file_path=get_rclone_config_file_path(rclone_config_file),
        )
        rclone.binaries = get_executable_binary_path_map()
        rclone.generate_config_file_if_not_exists()
        rclone.mount(mount_point)


@cli.command(
    name="mountPerm",
    help="Run a command at the Hetzner storage box. See https://docs.hetzner.com/robot/storage-box/access/access-sshsync-borg#available-commands for available commands",
)
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    help="An identifier of an existing connection defined with 'hsbt setConnection'. Alternatively set '--user' and '--host' to define a connection on the fly (which will not be saved).",
    default="",
    callback=conditonal_connection_prompts,
)
@connection_options(with_prompting=True, optional=True)
@click.option(
    "-m",
    "--mount-point",
    type=click.STRING,
)
def mount_permanent(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir: str | Path,
    password: str,
    config_file_path: str,
    force_password_use: str,
    mount_point: str,
    mount_tool: Literal["sshfs", "rclone"],
    mount_style: Literal["fstab", "systemd-automount", "autofs"],
):
    if mount_style in ["systemd-automount", "autofs"]:
        raise NotImplementedError(
            'mount-style "systemd-automount" and "autofs" is not implemented yet.'
        )
    hsbt: HetznerStorageBox = get_and_validate_storage_box_connection(
        identifier=identifier,
        host=host,
        user=user,
        ssh_key_dir=ssh_key_dir,
        password=password,
        config_file_path=config_file_path,
        force_password_use=force_password_use,
    )


def available_space(connection_identifier: str):
    pass


def download_from_remote(connection_identifier: str):
    pass


def upload_to_remote(connection_identifier: str):
    pass


if __name__ == "__main__":
    cli()
