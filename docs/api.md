# Python API

hsbt is usable as a Python library. All public classes and types are re-exported from the
top-level `hsbt` package, so you only need a single import statement in most cases.

## Installation

```bash
pip install git+https://github.com/motey/hetzner-storage-box-tool.git
```

## Public API surface

| Import path | Exported names |
|---|---|
| `hsbt` | `StorageBox`, `MountTool`, `MountStyle`, `Connection`, `ConnectionList`, `FileInfo`, `FileInfoCollection`, `ConnectionManager` |
| `hsbt.mount` | `MountStrategy`, `SshfsMountStrategy`, `CifsMountStrategy`, `SmbCifsSecretManager`, `RcloneMountStrategy`, `SystemdMountStrategy`, `AutofsMountStrategy` |
| `hsbt.transport` | `SshTransport`, `DeployKeyPasswordMissingError` |

---

## Common patterns

### Load a saved connection and connect

```python
from hsbt import StorageBox, ConnectionManager

mgr = ConnectionManager()
con = mgr.get_connection("mybox")

box = StorageBox.from_connection(con)
```

`ConnectionManager()` uses the default config file path (`~/.config/hetzner_sbt_connections.json`)
unless `HSBT_CONNECTIONS_CONFIG_FILE` or `HSBT_CENTRAL_CONFIG_DIR` is set. Pass
`target_config_file` to specify a path explicitly:

```python
from pathlib import Path
mgr = ConnectionManager(target_config_file=Path("/etc/myapp/hsbt.json"))
```

### Deploy the SSH key (first run)

```python
# deploys the key using the stored password; no-op if already deployed
deployed = box.deploy_public_key_if_not_done()
```

If the key has not been deployed yet and no password is set on the transport, this raises
`DeployKeyPasswordMissingError`. Set the password before calling:

```python
from hsbt.transport import DeployKeyPasswordMissingError

box.ssh.password = "yourpassword"
box.deploy_public_key_if_not_done()
```

### File operations

```python
# List files in a remote directory
files = box.list_remote_files("/home")
for f in files:
    print(f.name, f.size, f.modified)

# Upload
box.upload_file("/local/archive.tar.gz", "/home/backups/archive.tar.gz")

# Download
box.download_file("/home/backups/archive.tar.gz", "/tmp/archive.tar.gz")
```

`list_remote_files` returns a `FileInfoCollection`. Iterating it yields `FileInfo` objects
with `.name`, `.size`, `.permissions`, `.modified`, `.owner`, and `.group` attributes.

### Disk space

```python
rows = box.get_available_space()              # raw numbers
rows = box.get_available_space(human_readable=True)  # KB/MB/GB strings

for row in rows:
    print(row)   # dict with keys like "Filesystem", "1K-blocks", "Used", "Available"
```

### Run a remote command

```python
result = box.run_remote_command("ls -la /home")
print(result.stdout)

# dry run: returns the SSH command string without executing
result = box.run_remote_command("df -h", dry_run=True, return_stdout_only=False)
print(result.command)
```

`return_stdout_only=True` (default) returns the stdout string directly.
`return_stdout_only=False` returns a `CommandResult` with `.stdout`, `.stderr`, `.returncode`,
and `.command`.

---

## Mounting

### Temporary mount

```python
from pathlib import Path
from hsbt import StorageBox, ConnectionManager

mgr = ConnectionManager()
box = StorageBox.from_connection(mgr.get_connection("mybox"))

strategy = box.get_mount_strategy("rclone")
strategy.mount(Path("/mnt/mybox"))
```

### Permanent mount (fstab)

```python
strategy = box.get_mount_strategy("rclone")
strategy.mount_permanent(
    local_mountpoint=Path("/mnt/mybox"),
    fstab_file=Path("/etc/fstab"),
    uid=1000,
    gid=1000,
)
```

### Unmount

```python
strategy.unmount(Path("/mnt/mybox"))                                 # just unmount
strategy.unmount_permanent(Path("/mnt/mybox"), fstab_file=Path("/etc/fstab"))  # unmount + remove fstab entry
```

### CIFS mount

```python
strategy = box.get_mount_strategy(
    "cifs",
    smb_username="u000001",
    smb_password="secret",
)
strategy.mount(Path("/mnt/mybox"))
```

### WebDAV mount

```python
strategy = box.get_mount_strategy(
    "webdav",
    webdav_password="secret",
)
strategy.mount(Path("/mnt/mybox"))
```

### systemd automount

```python
from pathlib import Path

strategy = box.get_mount_strategy("sshfs", mount_style="systemd-automount")
strategy.mount_permanent(
    local_mountpoint=Path("/mnt/mybox"),
    fstab_file=Path("/etc/systemd/system"),
)
```

### autofs

```python
strategy = box.get_mount_strategy("sshfs", mount_style="autofs")
strategy.mount_permanent(
    local_mountpoint=Path("/mnt/mybox"),
    fstab_file=Path("/etc"),
)
```

---

## Sync (rclone only)

```python
from pathlib import Path
from hsbt.mount.rclone import RcloneMountStrategy

strategy = box.get_mount_strategy("rclone")
assert isinstance(strategy, RcloneMountStrategy)

# One-way sync: remote to local
strategy.sync_from_remote(Path("/backup/mybox"))

# Bidirectional sync
strategy.bisync(Path("/backup/mybox"), resync=True)   # first run
strategy.bisync(Path("/backup/mybox"))                 # subsequent runs
```

---

## Creating a connection programmatically

```python
from hsbt import ConnectionManager

mgr = ConnectionManager()
con = mgr.set_connection(
    identifier="mybox",
    host="u000001.your-storagebox.de",
    user="u000001",
    key_dir="~/.ssh/",
    overwrite_existing=False,
    exists_ok=False,
)
```

The `Connection` object returned by `set_connection` (and `get_connection`) is a Pydantic model
with `.identifier`, `.host`, `.user`, and `.key_dir` fields.

---

## Building StorageBox without a saved connection

```python
from hsbt import StorageBox
from hsbt.key_manager import KeyManager

box = StorageBox(
    host="u000001.your-storagebox.de",
    user="u000001",
    key_manager=KeyManager(target_dir="~/.ssh/", identifier="mybox"),
    password="yourpassword",   # only needed for key deployment
)
box.deploy_public_key_if_not_done()
```

---

## Type reference

### `MountTool`

```python
MountTool = Literal["sshfs", "cifs", "rclone", "webdav"]
```

### `MountStyle`

```python
MountStyle = Literal["fstab", "systemd-automount", "autofs"]
```

### `StorageBox.get_mount_strategy`

```python
def get_mount_strategy(
    self,
    tool: MountTool,
    mount_style: MountStyle = "fstab",
    rclone_config_path: Path | None = None,
    smb_username: str | None = None,
    smb_password: str | None = None,
    smb_domain: str | None = None,
    webdav_password: str | None = None,
) -> MountStrategy: ...
```

`mount_style` is only meaningful when `tool` is `"sshfs"` or `"cifs"`. Passing
`mount_style="systemd-automount"` or `mount_style="autofs"` with `tool="rclone"` or
`tool="webdav"` raises `ValueError`.

### `MountStrategy` (abstract base)

All strategy classes implement this interface:

```python
class MountStrategy:
    def mount(self, local_mountpoint: Path, remote_path: str | None = None) -> None: ...
    def unmount(self, local_mountpoint: Path) -> None: ...
    def mount_permanent(
        self,
        local_mountpoint: Path,
        fstab_file: Path,
        remote_path: str | None = None,
        uid: int | None = None,
        gid: int | None = None,
    ) -> None: ...
    def unmount_permanent(self, local_mountpoint: Path, fstab_file: Path) -> None: ...
    def is_mounted(self, local_mountpoint: Path) -> bool: ...
```
