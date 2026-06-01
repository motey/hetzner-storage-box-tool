from __future__ import annotations

import logging

import click

from hsbt.cli.connection import (
    set_connection,
    list_connections,
    repair_connection,
    delete_connection,
)
from hsbt.cli.mount import mount, mount_perm, unmount, sync
from hsbt.cli.transfer import remote_cmd, available_space, upload, download


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug logging.")
def cli(debug: bool):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        click.echo("Debug mode on")


cli.add_command(set_connection)
cli.add_command(list_connections)
cli.add_command(repair_connection)
cli.add_command(delete_connection)
cli.add_command(mount)
cli.add_command(mount_perm)
cli.add_command(unmount)
cli.add_command(sync)
cli.add_command(remote_cmd)
cli.add_command(available_space)
cli.add_command(upload)
cli.add_command(download)
