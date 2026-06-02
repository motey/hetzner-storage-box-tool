from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import click

from hsbt.connection_manager import ConnectionManager
from hsbt.env_var_names import EnvVarNames, EXECUTABLE_PATH_ENV_VAR_MAPPING
from hsbt.key_manager import KeyManager
from hsbt.storage_box import StorageBox
from hsbt.transport.ssh import DeployKeyPasswordMissingError
from hsbt.utils import is_root, cast_path

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Path resolution helpers
# ------------------------------------------------------------------

def get_config_file_path(caller_value=None) -> Path | None:
    if caller_value is not None:
        return cast_path(caller_value)
    env_val = os.getenv(EnvVarNames.CONNECTION_CONFIG_FILE, None)
    if env_val:
        return cast_path(env_val)
    central = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, None)
    if central:
        return cast_path([central, "config", "hetzner_sbt_connections.json"])
    return None


def get_ssh_dir(caller_value=None) -> Path | None:
    if caller_value is not None:
        return cast_path(caller_value)
    env_val = os.getenv(EnvVarNames.SSH_KEY_DIRECTORY, None)
    if env_val:
        return cast_path(env_val)
    central = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, None)
    if central:
        return cast_path([central, "ssh"])
    return None


def get_rclone_config_path(caller_value=None) -> Path | None:
    if caller_value is not None:
        return cast_path(caller_value)
    env_val = os.getenv(EnvVarNames.RCLONE_CONFIG_FILE, None)
    if env_val:
        return cast_path(env_val)
    central = os.getenv(EnvVarNames.CENTRAL_CONFIG_DIR, None)
    if central:
        return cast_path([central, "rclone", "rclone.conf"])
    return None


def _default_config_file() -> str:
    from_env = get_config_file_path(None)
    if from_env:
        return str(from_env)
    return "/etc/hetzner_sbt_connections.json" if is_root() else "~/.config/hetzner_sbt_connections.json"


def _default_ssh_dir() -> str:
    from_env = get_ssh_dir(None)
    if from_env:
        return str(from_env)
    return "~/.ssh/"


def resolve_binaries() -> Dict[str, str]:
    defaults = {
        "ssh": "ssh",
        "ssh-copy-id": "ssh-copy-id",
        "scp": "scp",
        "sshfs": "sshfs",
        "sshpass": "sshpass",
        "rclone": "rclone",
        "mount": "mount",
        "umount": "umount",
    }
    for name, envvar in EXECUTABLE_PATH_ENV_VAR_MAPPING.items():
        val = os.getenv(envvar.value, None)
        if val:
            defaults[name] = val
    return defaults


# ------------------------------------------------------------------
# Click callbacks
# ------------------------------------------------------------------

def _ssh_dir_callback(ctx: click.Context, param: click.Option, value: Any) -> Any:
    return get_ssh_dir(value)


def _conditional_prompts(ctx: click.Context, param: click.Option, value: Any) -> Any:
    """Suppress host/user/ssh-key-dir prompts when --identifier is given or when exactly one connection is saved."""
    suppress = value not in ["", None]
    if not suppress:
        try:
            suppress = len(ConnectionManager().list_connections().connections) == 1
        except Exception:
            pass
    if suppress:
        for p in ctx.command.params:
            if p.name in ["host", "user", "ssh_key_dir"]:
                p.prompt = None
                p.required = False
                p.default = None
    return value


# ------------------------------------------------------------------
# Shared decorator
# ------------------------------------------------------------------

def connection_options(
    with_prompting: bool = False,
    optional: bool = False,
    exclude_params: List[str] = None,
):
    """Decorator that attaches standard connection options to a Click command."""
    if exclude_params is None:
        exclude_params = []

    def decorator(fn):
        default_param = {"default": None} if optional else {"required": True}
        opt_hint = " Only required when '--identifier' is not set." if optional else ""

        if "force-password-use" not in exclude_params:
            fn = click.option(
                "-f", "--force-password-use",
                is_flag=True, default=False, required=False,
                help="Skip SSH key setup and use password auth instead.",
            )(fn)

        if "password" not in exclude_params:
            fn = click.option(
                "-p", "--password",
                type=click.STRING, hide_input=True, required=False, default=False,
                help="Storage box password. Needed for first-time key deployment or --force-password-use.",
            )(fn)

        fn = click.option(
            "-c", "--config-file-path",
            type=click.STRING, required=False,
            default=_default_config_file(),
            help="Path to the hsbt connections JSON file.",
        )(fn)

        fn = click.option(
            "-s", "--ssh-key-dir",
            type=click.STRING,
            prompt="Directory for SSH keys" if with_prompting and get_ssh_dir(None) is None else None,
            help=f"Directory to store SSH key files.{opt_hint}",
            default=_default_ssh_dir(),
            callback=_ssh_dir_callback,
        )(fn)

        fn = click.option(
            "-u", "--user",
            type=click.STRING,
            prompt="Storage box username" if with_prompting else None,
            help=f"Hetzner Storage Box username (e.g. u0000001).{opt_hint}",
            **default_param,
        )(fn)

        fn = click.option(
            "-h", "--host",
            type=click.STRING,
            prompt="Storage box hostname" if with_prompting else None,
            help=f"Hetzner Storage Box hostname (e.g. u000001.your-storagebox.de).{opt_hint}",
            **default_param,
        )(fn)

        return fn
    return decorator


# ------------------------------------------------------------------
# StorageBox factory used by all commands
# ------------------------------------------------------------------

def build_storage_box(
    identifier: str = None,
    host: str = None,
    user: str = None,
    ssh_key_dir: Path = None,
    password: str = None,
    config_file_path=None,
    force_password_use: bool = False,
    validate_connection: bool = False,
) -> StorageBox:
    cfg = get_config_file_path(config_file_path)
    ssh_dir = get_ssh_dir(ssh_key_dir)
    binaries = resolve_binaries()

    if not password:
        password = os.getenv(EnvVarNames.PASSWORD, None) or None

    if identifier not in [None, ""]:
        con_mgr = ConnectionManager(target_config_file=cfg)
        con = con_mgr.get_connection(identifier=identifier)
        if con is None:
            raise click.UsageError(
                f"No connection '{identifier}'. "
                "Run 'hsbt list-connections' to see saved connections, "
                "or 'hsbt set-connection' to create one."
            )
        box = StorageBox.from_connection(con, binaries=binaries)
    elif not host:
        con_mgr = ConnectionManager(target_config_file=cfg)
        all_cons = list(con_mgr.list_connections().connections.values())
        if len(all_cons) == 1:
            con = all_cons[0]
            click.echo(f"Using saved connection '{con.identifier}'.")
            box = StorageBox.from_connection(con, binaries=binaries)
        elif len(all_cons) > 1:
            names = ", ".join(c.identifier for c in all_cons)
            raise click.UsageError(
                f"Multiple connections saved ({names}). "
                "Use --identifier (-i) to select one."
            )
        else:
            raise click.UsageError(
                "No connection specified and no saved connections found. "
                "Run 'hsbt set-connection' to create one, "
                "or pass --host and --user directly."
            )
    else:
        box = StorageBox(
            host=host,
            user=user,
            key_manager=KeyManager(target_dir=ssh_dir, identifier=identifier or host),
            binaries=binaries,
        )

    box.ssh.password = password

    needs_password = force_password_use or (
        validate_connection and not box.public_key_is_deployed()
    )
    if needs_password:
        if not password:
            password = click.prompt(
                f"Password for storage box user '{box.user}'",
                type=click.STRING,
                hide_input=True,
            )
        box.ssh.password = password
        if not force_password_use:
            deployed = box.deploy_public_key_if_not_done()
            if deployed:
                click.echo(
                    f"Deployed public key '{box.key_manager.public_key_path}' to '{box.host}'."
                )

    return box
