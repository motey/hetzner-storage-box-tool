from typing import List
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
from hsbt.utils import is_root, cast_path


class ENV_VAR_NAMES(str, Enum):
    CONNECTION_CONFIG_FILE = "HSBT_CONNECTIONS_CONFIG_FILE"


def connection_options(with_prompting: bool = False, optional: bool = False):
    def connection_options_generator(function):
        default_param = dict()
        if optional:
            default_param["default"] = None
        else:
            default_param["required"] = True

        function = click.option(
            "-h",
            "--host",
            type=click.STRING,
            prompt="Host name of the Hetzner storage box" if with_prompting else None,
            help="The hostname to reach the reach the Hetzner storage box e.g. 'u000001.your-storagebox.de'",
            **default_param,
        )(function)
        function = click.option(
            "-u",
            "--user",
            type=click.STRING,
            prompt="Username of the Hetzner storage Box" if with_prompting else None,
            help="The username to connect to the Hetzner storage box. e.g. 'u0000001' or 'u00000001-sub1'",
            **default_param,
        )(function)
        function = click.option(
            "-s",
            "--ssh-key-dir",
            type=click.STRING,
            prompt="Directory to store ssh private and public key"
            if with_prompting
            else None,
            help="The username to connect to the Hetzner storage box. e.g. 'u0000001' or 'u00000001-sub1'",
            default="~/.ssh/",
        )(function)

        return function

    return connection_options_generator


@click.group()
@click.option("--debug/--no-debug", default=False)
def cli(debug):
    if debug:
        click.echo(f"Debug mode is on")
        logging.basicConfig(level="DEBUG")


@cli.command(name="setConnection")
@click.option(
    "-i",
    "--identifier",
    type=click.STRING,
    prompt="Identifying name for the connection",
    help="An identifier to point to the connection in all other commands.",
)
@connection_options(with_prompting=True, optional=False)
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
):
    # save connection params as json in /etc/hetzner_connections.json when root or ~/.config/hetzner_connections.json if non root
    # exchange key with hetzner storage box.

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
def list_connections(format_output):
    config_file_path = cast_path(
        os.getenv(ENV_VAR_NAMES.CONNECTION_CONFIG_FILE, default="yaml")
    )
    connection_manager = ConnectionManager(target_config_file=config_file_path)

    if format_output == "yaml":
        output = yaml.dump(connection_manager.list_connections().dict())
    else:
        output = connection_manager.list_connections().json()
    click.echo(output)


def run_remote_command(connection_identifier: str):
    # allowd commands https://docs.hetzner.com/de/robot/storage-box/access/access-ssh-rsync-borg#verfugbare-befehle
    # if identifier is passed check for matching connection params in /etc/hetzner_connections.json or ~/.config/hetzner_connections.json
    # othwerwise params must be passed as function params
    pass


def mount(connection_identifier: str):
    pass


def available_space(connection_identifier: str):
    pass


def download_from_remote(connection_identifier: str):
    pass


def upload_to_remote(connection_identifier: str):
    pass


if __name__ == "__main__":
    cli()
