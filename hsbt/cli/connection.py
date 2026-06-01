from __future__ import annotations

import click
import yaml

from hsbt.cli._common import (
    build_storage_box,
    connection_options,
    get_config_file_path,
    get_ssh_dir,
    _default_config_file,
)
from hsbt.connection_manager import ConnectionManager
from hsbt.storage_box import StorageBox


@click.command(name="set-connection", help="Define a named connection for use in all other commands.")
@click.option("-i", "--identifier", prompt="Connection name", help="Unique name for this connection.")
@connection_options(with_prompting=True, optional=False, exclude_params=["force-password-use", "password"])
@click.option(
    "-o", "--overwrite-existing",
    is_flag=True, default=False,
    help="Replace an existing connection with the same name.",
)
@click.option(
    "-e", "--exists-ok",
    is_flag=True, default=False,
    help="Exit silently if the connection already exists.",
)
@click.option(
    "-k", "--skip-key-deployment",
    is_flag=True, default=False,
    help="Save the connection without deploying an SSH key yet. The key will be deployed on first use.",
)
def set_connection(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    overwrite_existing: bool,
    exists_ok: bool,
    config_file_path: str,
    skip_key_deployment: bool,
):
    cfg = get_config_file_path(config_file_path)
    ssh_dir = get_ssh_dir(ssh_key_dir)
    con_mgr = ConnectionManager(target_config_file=cfg)
    con = con_mgr.set_connection(
        identifier=identifier,
        user=user,
        host=host,
        key_dir=ssh_dir,
        overwrite_existing=overwrite_existing,
        exists_ok=exists_ok,
    )
    if not skip_key_deployment:
        build_storage_box(con.identifier, validate_connection=True, config_file_path=cfg)
    click.echo(f"Saved connection to '{con_mgr.target_config_file}':")
    click.echo(f"  {con}")


@click.command(name="list-connections", help="List all saved connections.")
@click.option(
    "-f", "--format-output",
    type=click.Choice(["json", "yaml"], case_sensitive=False),
    default=None,
)
@click.option("-c", "--config-file-path", type=click.STRING, default=None,
              help="Override default config file path.")
def list_connections(format_output, config_file_path):
    cfg = get_config_file_path(config_file_path)
    con_mgr = ConnectionManager(target_config_file=cfg)
    connections = con_mgr.list_connections()
    if format_output == "yaml":
        click.echo(yaml.dump(connections.model_dump()))
    else:
        click.echo(connections.model_dump_json(indent=2))


@click.command(name="repair-connection", help="Verify and repair SSH keys and known_hosts for a connection.")
@click.option("-i", "--identifier", prompt="Connection name", help="Name of the connection to repair.")
@click.option(
    "-c", "--config-file-path",
    type=click.STRING, required=False,
    default=_default_config_file(),
    help="Path to the hsbt connections JSON file.",
)
def repair_connection(identifier: str, config_file_path: str):
    cfg = get_config_file_path(config_file_path)
    con_mgr = ConnectionManager(target_config_file=cfg)
    if con_mgr.get_connection(identifier=identifier) is None:
        raise click.UsageError(
            f"No connection '{identifier}'. Run 'hsbt list-connections' to see available connections."
        )
    box = build_storage_box(identifier=identifier, validate_connection=True, config_file_path=cfg)
    if box.public_key_is_deployed():
        click.echo("Connection is working.")
    else:
        raise ConnectionError("Could not repair connection.")


@click.command(name="delete-connection", help="Remove a saved connection.")
@click.option("-i", "--identifier", prompt="Connection name", help="Name of the connection to delete.")
@click.option(
    "-m", "--missing-ok",
    is_flag=True, default=False,
    help="Exit silently if the connection does not exist.",
)
@click.option(
    "-c", "--config-file-path",
    type=click.STRING, required=False,
    default=_default_config_file(),
)
@click.option(
    "-k", "--delete-keys",
    is_flag=True, default=False,
    help="Also delete the SSH keys associated with this connection.",
)
def delete_connection(identifier: str, config_file_path: str, delete_keys: bool, missing_ok: bool):
    cfg = get_config_file_path(config_file_path)
    con_mgr = ConnectionManager(target_config_file=cfg)
    con = con_mgr.get_connection(identifier=identifier)
    if con is not None and delete_keys:
        box = StorageBox.from_connection(con)
        box.key_manager.private_key_path.unlink(missing_ok=True)
        box.key_manager.public_key_path.unlink(missing_ok=True)
        click.echo(f"Deleted SSH keys for '{identifier}'.")
    con_mgr.delete_connection(identifier=identifier, missing_ok=missing_ok)
    click.echo(f"Deleted connection '{identifier}'.")
