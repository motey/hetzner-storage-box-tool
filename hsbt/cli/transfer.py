from __future__ import annotations

import click

from hsbt.cli._common import (
    build_storage_box,
    connection_options,
    get_config_file_path,
    get_ssh_dir,
    _conditional_prompts,
)
from hsbt.process import CommandResult


@click.command(
    name="remote-cmd",
    help="Run a command on the storage box. See https://docs.hetzner.com/robot/storage-box/access/access-ssh-rsync-borg#available-commands",
)
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    help="Saved connection name. Alternatively pass --host and --user directly.",
    callback=_conditional_prompts,
)
@connection_options(with_prompting=True, optional=True)
@click.option(
    "-n", "--no-exec",
    is_flag=True, default=False,
    help="Print the SSH command without running it.",
)
@click.argument("command", type=click.STRING)
def remote_cmd(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    command: str,
    no_exec: bool,
):
    box = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    result: CommandResult = box.run_remote_command(command, dry_run=no_exec, return_stdout_only=False)
    click.echo(result.command if no_exec else result.stdout)


@click.command(name="available-space", help="Show available disk space on the storage box.")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.option(
    "--human-readable", "-H",
    is_flag=True, default=False,
    help="Show sizes in human-readable format (KB, MB, GB).",
)
def available_space(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    human_readable: bool,
):
    box = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    rows = box.get_available_space(human_readable=human_readable)
    for row in rows:
        click.echo("  ".join(f"{k}: {v}" for k, v in row.items()))


@click.command(name="upload", help="Upload a local file to the storage box.")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path", type=click.STRING)
def upload(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    local_path: str,
    remote_path: str,
):
    box = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    box.upload_file(local_path, remote_path)
    click.echo(f"Uploaded '{local_path}' → '{remote_path}' on {box.host}")


@click.command(name="download", help="Download a file from the storage box.")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.argument("remote_path", type=click.STRING)
@click.argument("local_path", type=click.Path())
def download(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    remote_path: str,
    local_path: str,
):
    box = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    box.download_file(remote_path, local_path)
    click.echo(f"Downloaded '{remote_path}' from {box.host} → '{local_path}'")
