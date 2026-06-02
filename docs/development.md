# Development Guide

This guide covers the project architecture, how to set up a development environment,
and how to extend hsbt with new commands or mount backends.

For the test suite, see [TESTING.md](../TESTING.md).

## Contents

- [Setup](#setup)
- [Project structure](#project-structure)
- [Architecture](#architecture)
- [Adding a CLI command](#adding-a-cli-command)
- [Adding a mount backend](#adding-a-mount-backend)
- [Code conventions](#code-conventions)

---

## Setup

```bash
git clone https://github.com/motey/hetzner-storage-box-tool.git
cd hetzner-storage-box-tool

pip install pdm
pdm install -G test
```

This creates a `.venv` virtualenv and installs all runtime and test dependencies.
The `hsbt` command is available inside the venv at `.venv/bin/hsbt`.

To run the tool during development without activating the venv:

```bash
.venv/bin/hsbt --help
```

---

## Project structure

```
hsbt/
  __init__.py           re-exports the public API (StorageBox, Connection, ConnectionManager, ...)
  models.py             Connection, ConnectionList, FileInfo, FileInfoCollection (Pydantic models)
  process.py            ProcessOutput, CommandResult, run_command(), open_process()
  config_editor.py      ConfigFileEditor: idempotent block insert/update/remove in text config files
  env_var_names.py      EnvVarNames enum and EXECUTABLE_PATH_ENV_VAR_MAPPING dict
  utils.py              is_root(), cast_path(), parse_ls_l_output(), convert_df_output_to_dict()
  key_manager.py        SSH key generation, known_hosts management
  connection_manager.py Load/save named connections to/from JSON
  storage_box.py        StorageBox facade + MountTool/MountStyle type aliases
  transport/
    ssh.py              SshTransport: SSH/SCP execution, key deployment, file ops
  mount/
    base.py             Abstract MountStrategy base class
    sshfs.py            SshfsMountStrategy
    cifs.py             CifsMountStrategy + SmbCifsSecretManager
    rclone.py           RcloneMountStrategy (SFTP + WebDAV, sync/bisync)
    systemd.py          SystemdMountStrategy (.mount + .automount unit files)
    autofs.py           AutofsMountStrategy (direct map + auto.master)
  cli/
    __init__.py         Click group + add_command() registrations
    _common.py          Shared helpers: connection_options decorator, build_storage_box factory
    connection.py       set-connection, list-connections, repair-connection, delete-connection
    mount.py            mount, mount-perm, unmount, sync
    transfer.py         remote-cmd, available-space, upload, download

tests/
  conftest.py           Shared fixtures, real Hetzner ls/df output constants
  test_*.py             425 unit tests (no network, no root)
  integration/
    conftest.py         Live transport fixture, remote workdir setup/teardown
    test_transport.py   SshTransport Tier-1 tests
    test_storage_box.py StorageBox facade Tier-1 tests
    test_mount_*.py     Per-backend live tests (Tier 1 + Tier 2)
```

---

## Architecture

### Layers

```
CLI (hsbt/cli/)
    |
    v
StorageBox facade (hsbt/storage_box.py)
    |
    +-- SshTransport (hsbt/transport/ssh.py)   -- all SSH/SCP I/O
    |
    +-- MountStrategy (hsbt/mount/*.py)        -- per-backend mount logic
         SshfsMountStrategy
         CifsMountStrategy
         RcloneMountStrategy
         SystemdMountStrategy
         AutofsMountStrategy
```

**`SshTransport`** handles all network operations: running remote commands, uploading and
downloading files via SCP, deploying SSH keys, and maintaining `known_hosts`. It is the only
module that calls `ssh`, `scp`, `sshpass`, and `ssh-copy-id`.

**`MountStrategy`** subclasses handle mount-specific logic: building mount commands, writing
fstab/unit-file entries, and unmounting. They receive an `SshTransport` instance so they can
read connection details (host, user, key paths) without making any SSH calls themselves.

**`StorageBox`** is the public facade. It composes a single `SshTransport` with any number of
mount strategies via `get_mount_strategy()`. Callers import `StorageBox` and do not need to
know about `SshTransport` directly.

**`ConfigFileEditor`** handles idempotent block insert/update/remove in line-based config files
(fstab, rclone.conf). It is used by multiple mount strategies and is tested independently.

### Connection flow

1. `ConnectionManager` loads a `Connection` (hostname, username, key directory) from JSON.
2. `StorageBox.from_connection(con)` builds a `KeyManager` and an `SshTransport`.
3. On first use, `SshTransport.deploy_public_key_if_not_done()` uses `sshpass` + `ssh-copy-id`
   to push the public key, then switches to key-only auth permanently.
4. All subsequent `SshTransport` calls use the keypair directly via `-i <private_key>`.

### CLI wiring

Every CLI command follows the same pattern:

1. Accept either `--identifier` (named connection) or `--host` + `--user` (ad-hoc).
2. Call `build_storage_box(...)` from `hsbt/cli/_common.py` to get a `StorageBox`.
3. Call the appropriate method on the `StorageBox`.

`build_storage_box` also handles auto-selection when exactly one connection is saved,
and prompts for a password if key deployment has not happened yet.

---

## Adding a CLI command

1. Write the Click command function in the appropriate module under `hsbt/cli/` or create
   a new module if the command does not fit an existing grouping.

2. Use the `@connection_options(...)` decorator from `_common.py` to attach the standard
   `--identifier`, `--host`, `--user`, `--ssh-key-dir`, `--password`, and related flags.

3. Call `build_storage_box(...)` at the start of the function body to get a `StorageBox`
   from whatever connection the user specified.

4. Register the command in `hsbt/cli/__init__.py`:

```python
from hsbt.cli.mymodule import my_command
cli.add_command(my_command)
```

**Minimal example:**

```python
# hsbt/cli/mymodule.py
import click
from hsbt.cli._common import build_storage_box, connection_options, _conditional_prompts

@click.command(name="my-command", help="Does something useful.")
@click.option("-i", "--identifier", type=click.STRING, default="", callback=_conditional_prompts)
@connection_options(with_prompting=True, optional=True)
@click.option("--my-flag", is_flag=True, default=False)
def my_command(identifier, host, user, ssh_key_dir, password, config_file_path,
               force_password_use, my_flag):
    box = build_storage_box(
        identifier=identifier, host=host, user=user, ssh_key_dir=ssh_key_dir,
        password=password, config_file_path=config_file_path,
        force_password_use=force_password_use,
    )
    # use box here
    click.echo(f"Connected to {box.host}")
```

---

## Adding a mount backend

1. Create a new file in `hsbt/mount/`, e.g. `hsbt/mount/mybackend.py`.

2. Subclass `MountStrategy` from `hsbt/mount/base.py` and implement all abstract methods:

```python
from pathlib import Path
from hsbt.mount.base import MountStrategy
from hsbt.transport.ssh import SshTransport

class MyBackendMountStrategy(MountStrategy):
    def __init__(self, transport: SshTransport, **kwargs):
        self.transport = transport

    def mount(self, local_mountpoint: Path, remote_path: str | None = None) -> None:
        ...

    def unmount(self, local_mountpoint: Path) -> None:
        ...

    def mount_permanent(self, local_mountpoint: Path, fstab_file: Path,
                        remote_path: str | None = None,
                        uid: int | None = None, gid: int | None = None) -> None:
        ...

    def unmount_permanent(self, local_mountpoint: Path, fstab_file: Path) -> None:
        ...
```

3. Register it in `StorageBox.get_mount_strategy()` in `hsbt/storage_box.py`:

```python
if tool == "mybackend":
    return MyBackendMountStrategy(self.ssh, **relevant_kwargs)
```

4. Add `"mybackend"` to the `_MOUNT_TOOL_CHOICES` in `hsbt/cli/mount.py`:

```python
_MOUNT_TOOL_CHOICES = click.Choice(["sshfs", "rclone", "cifs", "webdav", "mybackend"], ...)
```

5. Update the `MountTool` type alias in `hsbt/storage_box.py`:

```python
MountTool = Literal["sshfs", "cifs", "rclone", "webdav", "mybackend"]
```

6. Add a test file `tests/test_mount_mybackend.py` covering at minimum:
   - the fstab/unit-file format
   - idempotency of `mount_permanent` (calling it twice should not duplicate the entry)
   - `is_mounted()` behaviour

---

## Code conventions

- **No comments** unless the why is non-obvious. Well-named identifiers do the explaining.
- **No bare `except`**: catch specific exception types.
- All subprocess calls go through `run_command()` or `open_process()` from `hsbt/process.py`.
  Never call `subprocess` directly in strategy or transport code.
- All path handling uses `pathlib.Path`. Use `cast_path()` from `hsbt/utils.py` to normalize
  strings, lists, and `None` to `Path | None`.
- Keep the `hsbt/__init__.py` re-exports in sync when adding public classes.
