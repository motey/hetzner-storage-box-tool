from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import click

from hsbt.cli._common import (
    build_storage_box,
    connection_options,
    get_rclone_config_path,
    _conditional_prompts,
)
from hsbt.env_var_names import EnvVarNames
from hsbt.storage_box import StorageBox

log = logging.getLogger(__name__)

_MOUNT_TOOL_CHOICES = click.Choice(["sshfs", "rclone", "cifs", "webdav"], case_sensitive=False)


def _resolve_webdav_password(cli_value: str | None) -> str | None:
    if cli_value:
        return cli_value
    return os.getenv(EnvVarNames.WEBDAV_PASSWORD, None) or None


@click.command(name="mount", help="Temporarily mount a storage box (not persistent across reboots).")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.option("-mp", "--mount-point", required=True, type=click.STRING, help="Local path to mount to.")
@click.option(
    "-mt", "--mount-tool",
    type=_MOUNT_TOOL_CHOICES,
    default="sshfs",
    help="Mount backend to use.",
)
@click.option("-r", "--remote-path", type=click.STRING, default=None, help="Remote path to mount (default: home dir).")
@click.option("-rc", "--rclone-config-file", type=click.STRING, default=None, help="Custom rclone config file path.")
@click.option("--smb-username", type=click.STRING, default=None, help="SMB/CIFS username (CIFS only).")
@click.option("--smb-password", type=click.STRING, default=None, hide_input=True, help="SMB/CIFS password (CIFS only).")
@click.option("--smb-domain", type=click.STRING, default=None, help="SMB/CIFS domain (CIFS only, optional).")
@click.option("--webdav-password", type=click.STRING, default=None, hide_input=True, help="WebDAV password (WebDAV only). Falls back to HSBT_WEBDAV_PASSWORD env var.")
def mount(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    mount_point: str,
    mount_tool: str,
    remote_path: str,
    rclone_config_file: str,
    smb_username: str,
    smb_password: str,
    smb_domain: str,
    webdav_password: str,
):
    box: StorageBox = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    strategy = box.get_mount_strategy(
        mount_tool,
        rclone_config_path=get_rclone_config_path(rclone_config_file),
        smb_username=smb_username,
        smb_password=smb_password,
        smb_domain=smb_domain,
        webdav_password=_resolve_webdav_password(webdav_password),
    )
    strategy.mount(Path(mount_point), remote_path=remote_path)
    click.echo(f"Mounted '{box.host}' at '{mount_point}' via {mount_tool}.")


@click.command(
    name="mount-perm",
    help="Add a persistent mount entry to /etc/fstab and mount immediately.",
)
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.option("-m", "--mount-point", required=True, type=click.STRING, help="Local path to mount to.")
@click.option("-r", "--remote-path", type=click.STRING, default=None, help="Remote path (default: home dir).")
@click.option(
    "-mt", "--mount-tool",
    type=_MOUNT_TOOL_CHOICES,
    default="sshfs",
    help="Mount backend to use.",
)
@click.option(
    "-ms", "--mount-style",
    type=click.Choice(["fstab", "systemd-automount", "autofs"], case_sensitive=False),
    default="fstab",
    help="How to make the mount persistent. Currently only 'fstab' is implemented.",
)
@click.option("-ff", "--fstab-file", type=click.STRING, default="/etc/fstab", help="fstab file to write to.")
@click.option("-ui", "--uid", type=click.STRING, default=None, help="UID for the mount. Defaults to current user.")
@click.option("-gi", "--gid", type=click.STRING, default=None, help="GID for the mount. Defaults to current group.")
@click.option("-rc", "--rclone-config-file", type=click.STRING, default=None, help="Custom rclone config file.")
@click.option("--smb-username", type=click.STRING, default=None, help="SMB/CIFS username (CIFS only).")
@click.option("--smb-password", type=click.STRING, default=None, hide_input=True, help="SMB/CIFS password (CIFS only).")
@click.option("--smb-domain", type=click.STRING, default=None, help="SMB/CIFS domain (CIFS only, optional).")
@click.option("--webdav-password", type=click.STRING, default=None, hide_input=True, help="WebDAV password (WebDAV only). Falls back to HSBT_WEBDAV_PASSWORD env var.")
def mount_perm(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    mount_point: str,
    remote_path: str,
    mount_tool: str,
    mount_style: str,
    fstab_file: str,
    uid: str,
    gid: str,
    rclone_config_file: str,
    smb_username: str,
    smb_password: str,
    smb_domain: str,
    webdav_password: str,
):
    _style_defaults = {
        "fstab": "/etc/fstab",
        "systemd-automount": "/etc/systemd/system",
        "autofs": "/etc",
    }
    effective_fstab = fstab_file if fstab_file != "/etc/fstab" else _style_defaults[mount_style]
    box: StorageBox = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    strategy = box.get_mount_strategy(
        mount_tool,  # type: ignore[arg-type]
        mount_style=mount_style,  # type: ignore[arg-type]
        rclone_config_path=get_rclone_config_path(rclone_config_file),
        smb_username=smb_username,
        smb_password=smb_password,
        smb_domain=smb_domain,
        webdav_password=_resolve_webdav_password(webdav_password),
    )
    strategy.mount_permanent(
        local_mountpoint=Path(mount_point),
        fstab_file=Path(effective_fstab),
        remote_path=remote_path,
        uid=int(uid) if uid else None,
        gid=int(gid) if gid else None,
    )
    if mount_style == "systemd-automount":
        click.echo(
            f"Installed systemd automount for '{box.host}' at '{mount_point}'. "
            f"Units written to '{effective_fstab}'."
        )
    elif mount_style == "autofs":
        click.echo(
            f"Installed autofs mount for '{box.host}' at '{mount_point}'. "
            f"Map written to '{effective_fstab}'."
        )
    else:
        click.echo(
            f"Mounted '{box.host}' at '{mount_point}' via {mount_tool}. "
            f"Entry written to '{effective_fstab}'."
        )


@click.command(name="unmount", help="Unmount and remove the fstab entry for a storage box mount.")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.option("-m", "--mount-point", required=True, type=click.STRING, help="Mount point to unmount.")
@click.option(
    "-mt", "--mount-tool",
    type=_MOUNT_TOOL_CHOICES,
    default="sshfs",
)
@click.option(
    "-ms", "--mount-style",
    type=click.Choice(["fstab", "systemd-automount", "autofs"], case_sensitive=False),
    default="fstab",
    help="Persistence style used when the mount was installed.",
)
@click.option("-ff", "--fstab-file", type=click.STRING, default=None,
              help="Config dir override. Defaults to /etc/fstab, /etc/systemd/system, or /etc based on --mount-style.")
@click.option(
    "--keep-fstab", is_flag=True, default=False,
    help="Only unmount without removing the persistent config entry.",
)
def unmount(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    mount_point: str,
    mount_tool: str,
    mount_style: str,
    fstab_file: str,
    keep_fstab: bool,
):
    _style_defaults = {
        "fstab": "/etc/fstab",
        "systemd-automount": "/etc/systemd/system",
        "autofs": "/etc",
    }
    effective_fstab = fstab_file or _style_defaults[mount_style]
    box: StorageBox = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    strategy = box.get_mount_strategy(mount_tool, mount_style=mount_style)  # type: ignore[arg-type]
    mp = Path(mount_point)
    if keep_fstab:
        strategy.unmount(mp)
    else:
        strategy.unmount_permanent(mp, fstab_file=Path(effective_fstab))
    click.echo(f"Unmounted '{mount_point}'.")


@click.command(name="sync", help="Sync storage box contents to a local directory using rclone.")
@click.option(
    "-i", "--identifier",
    type=click.STRING, default="",
    callback=_conditional_prompts,
    help="Saved connection name.",
)
@connection_options(with_prompting=True, optional=True)
@click.option("-l", "--local-dir", required=True, type=click.Path(), help="Local directory to sync into.")
@click.option("-r", "--remote-path", type=click.STRING, default="", help="Remote path to sync from.")
@click.option(
    "--mode",
    type=click.Choice(["sync", "bisync"], case_sensitive=False),
    default="sync",
    help="'sync' copies remote→local. 'bisync' keeps both sides in sync.",
)
@click.option("--resync", is_flag=True, default=False, help="Force full resync (bisync only).")
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("-rc", "--rclone-config-file", type=click.STRING, default=None)
def sync(
    identifier: str,
    host: str,
    user: str,
    ssh_key_dir,
    password: str,
    config_file_path: str,
    force_password_use: bool,
    local_dir: str,
    remote_path: str,
    mode: str,
    resync: bool,
    verbose: bool,
    rclone_config_file: str,
):
    box: StorageBox = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    rclone = box.get_mount_strategy(
        "rclone",
        rclone_config_path=get_rclone_config_path(rclone_config_file),
    )
    from hsbt.mount.rclone import RcloneMountStrategy
    assert isinstance(rclone, RcloneMountStrategy)
    if mode == "bisync":
        rclone.bisync(Path(local_dir), remote_path=remote_path, resync=resync, verbose=verbose)
    else:
        rclone.sync_from_remote(Path(local_dir), remote_path=remote_path, verbose=verbose)
    click.echo(f"Sync complete: '{box.host}:{remote_path}' ↔ '{local_dir}'")
