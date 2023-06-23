from typing import List, Any
import os, sys
from pathlib import Path, PurePath
import click

import logging
import yaml
from enum import Enum

if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(
        os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
    )
    MODULE_ROOT_DIR = os.path.join(SCRIPT_DIR, "..")
    print(MODULE_ROOT_DIR)
    sys.path.insert(0, os.path.normpath(MODULE_ROOT_DIR))

from hsbt.connection_manager import ConnectionManager
from hsbt.storage_box_manager import HetznerStorageBox
from hsbt.key_manager import KeyManager
from hsbt.utils import is_root, cast_path


class ENV_VAR_NAMES(str, Enum):
    CONNECTION_CONFIG_FILE = "HSBT_CONNECTIONS_CONFIG_FILE"
    SSH_KEY_DIRECTORY = "HSBT_SSH_KEY_FILE_DIR"
    PASSWORD = "HSBT_PASSWORD"


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
        function = click.option(
            "-c",
            "--config-file-path",
            type=click.STRING,
            required=False,
            help="hsbt saves connection infos into a json file. By default root will store connections into '/etc/hetzner_sb_connections.json' and any other user in '~/.config/hetzner_sb_connections.json'",
            default="/etc/hetzner_sb_connections.json"
            if is_root()
            else "~/.config/hetzner_sb_connections.json",
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
            if with_prompting
            else None,
            help=help,
            default="~/.ssh/",
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


def get_and_validate_storage_box_connection(
    identifier: str = None,
    host: str = None,
    user: str = None,
    ssh_key_dir: str = None,
    password: str = None,
    config_file_path: str = None,
    force_password_use: bool = False,
) -> HetznerStorageBox:
    if config_file_path is None:
        config_file_path = cast_path(
            os.getenv(ENV_VAR_NAMES.CONNECTION_CONFIG_FILE, default=None)
        )
    if ssh_key_dir is None:
        ssh_key_dir = cast_path(
            os.getenv(ENV_VAR_NAMES.SSH_KEY_DIRECTORY, default=None)
        )
    if password is None:
        password = cast_path(os.getenv(ENV_VAR_NAMES.PASSWORD, default=None))
    hsbt: HetznerStorageBox = None
    if identifier not in [None, ""]:
        conman = ConnectionManager(target_config_file=config_file_path)
        con = conman.get_connection(identifier=identifier)
        if con is None:
            raise ValueError(
                f"Could not find connection with identifier '{identifier}'. Use 'hsbt listConnection' to see available connections"
            )
        hsbt = HetznerStorageBox.from_connection(con)
    else:
        hsbt = HetznerStorageBox(
            host=host,
            user=user,
            key_manager=KeyManager(target_dir=ssh_key_dir, identifier=f"{host}"),
        )
    if force_password_use or not hsbt.public_key_is_deployed():
        if password is None:
            password = click.prompt(
                f"Password for Hetzner Storage Box user {user}",
                type=click.STRING,
                hide_input=True,
            )
        hsbt.password = password
        if not force_password_use:
            # first time use of connection. We will create the if necessary and deploy it to the Hetzner storageBox
            hsbt.deploy_public_key_if_not_done()
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
    # prompt="If connection identifiert exists, update/overwrite it?",
    is_flag=True,
    help="If a connection configuration with the same identifier already exists, this command will fail. If you are sure you want to overwrite it pass '-o' to the command to update the existing connection configuration",
    default=False,
)
def set_connection(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir: str | Path,
    overwrite_existing: bool,
    config_file_path: str,
):
    # save connection params as json in /etc/hetzner_connections.json when root or ~/.config/hetzner_connections.json if non root
    # exchange key with hetzner storage box.
    if config_file_path is None:
        config_file_path = cast_path(
            os.getenv(ENV_VAR_NAMES.CONNECTION_CONFIG_FILE, default=None)
        )
    connection_manager = ConnectionManager(target_config_file=config_file_path)
    con = connection_manager.set_connection(
        identifier=identifier,
        user=user,
        host=host,
        key_dir=ssh_key_dir,
        overwrite_existing=overwrite_existing,
        exists_ok=False,
    )
    click.echo(f"Saved connection at '{connection_manager.target_config_file}' as:")
    click.echo(f"\t{con}")

    # ConnectionManager(target_config_file=)


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
    help="Alternative config file instead of '/etc/hetzner_sb_connections.json' and '~/.config/hetzner_sb_connections.json'",
    default=None,
)
def list_connections(format_output, config_file_path):
    if config_file_path is None:
        config_file_path = cast_path(
            os.getenv(ENV_VAR_NAMES.CONNECTION_CONFIG_FILE, default=None),
        )
    connection_manager = ConnectionManager(target_config_file=config_file_path)

    if format_output == "yaml":
        output = yaml.dump(connection_manager.list_connections().dict())
    else:
        output = connection_manager.list_connections().json()
    click.echo(output)


@cli.command(
    name="remoteSSH",
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
    force_password_use: str,
    command: str,
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
    hsbt.run_remote_command(command)


def delete_connection(connection_identifier: str):
    pass


def mount(connection_identifier: str):
    pass


def permament_mount(connection_identifier: str):
    pass


def available_space(connection_identifier: str):
    pass


def download_from_remote(connection_identifier: str):
    pass


def upload_to_remote(connection_identifier: str):
    pass


if __name__ == "__main__":
    cli()
