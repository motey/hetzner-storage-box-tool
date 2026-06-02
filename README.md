# hsbt - Hetzner Storage Box Tool

A command-line tool for working with [Hetzner Storage Boxes](https://www.hetzner.com/storage/storage-box).
It handles SSH key deployment, mounting (temporary and persistent), file transfers, and remote commands
from a single, scriptable interface.

## How it works

hsbt stores named connections in a JSON config file (default: `~/.config/hetzner_sbt_connections.json`).
Each connection holds the hostname, username, and path to an SSH keypair. On first use hsbt deploys your
public key to the storage box via password auth so that all subsequent operations are key-only.

The mount commands support four backends:

| Backend | Protocol | Port | Notes |
|---------|----------|------|-------|
| `sshfs` | SFTP over SSH | 23 | Simple, no extra config. Officially unmaintained upstream. |
| `rclone` | SFTP over SSH | 23 | Recommended. Also supports sync and bisync. |
| `cifs` | SMB | 445 | Useful when you need native Windows/NAS compatibility. |
| `webdav` | WebDAV over HTTPS | 443 | Best firewall/proxy traversal. Uses rclone internally; no extra dependency. |

Connections can be used one-off (pass `--host` and `--user` directly) or by name (pass `--identifier`
after running `set-connection` once).


## Installation

**System dependencies** (Debian/Ubuntu):

```bash
apt install openssh-client sshfs sshpass rclone cifs-utils
```

**Python package** (requires Python 3.14+):

```bash
pip install git+https://github.com/motey/hetzner-storage-box-tool.git
```

Or with [PDM](https://pdm-project.org):

```bash
pdm add git+https://github.com/motey/hetzner-storage-box-tool.git
```

After installation the `hsbt` command is available on your PATH.

```
hsbt --help
```


## Configuration

### Environment variables

All settings can be configured through environment variables. CLI flags always take precedence.

| Variable | Description |
|----------|-------------|
| `HSBT_CENTRAL_CONFIG_DIR` | One-stop directory. hsbt will look for `<dir>/config/hetzner_sbt_connections.json`, `<dir>/ssh/`, and `<dir>/rclone/rclone.conf` automatically. |
| `HSBT_CONNECTIONS_CONFIG_FILE` | Explicit path to the connections JSON file. |
| `HSBT_SSH_KEY_FILE_DIR` | Directory to store SSH keypairs. Defaults to `~/.ssh/`. |
| `HSBT_RCLONE_CONFIG_FILE` | Path to the rclone config file. |
| `HSBT_PASSWORD` | Storage box password. Used for initial key deployment and `--force-password-use`. |
| `HSBT_WEBDAV_PASSWORD` | Password for the WebDAV backend (`--mount-tool webdav`). Falls back to `HSBT_PASSWORD` when not set. |

### Binary paths

If system tools are not on your PATH you can point hsbt at them directly:

| Variable | Tool |
|----------|------|
| `HSBT_BIN_PATH_SSH` | `ssh` |
| `HSBT_BIN_PATH_SCP` | `scp` |
| `HSBT_BIN_PATH_SSHFS` | `sshfs` |
| `HSBT_BIN_PATH_SSHPASS` | `sshpass` |
| `HSBT_BIN_PATH_SSH_COPY_ID` | `ssh-copy-id` |
| `HSBT_BIN_PATH_RCLONE` | `rclone` |
| `HSBT_BIN_PATH_MOUNT` | `mount` |
| `HSBT_BIN_PATH_UMOUNT` | `umount` |


## Usage

### Connection management

Save a connection (prompts for host, user, and SSH key directory if not given as flags):

```bash
hsbt set-connection -i mybox -h u000001.your-storagebox.de -u u000001
```

On first run hsbt will prompt for your storage box password to deploy the SSH public key.
After that, the password is no longer needed.

```
Password for storage box user 'u000001': ...
Deployed public key '/home/tim/.ssh/hsbt_mybox.pub' to 'u000001.your-storagebox.de'.
Saved connection to '/home/tim/.config/hetzner_sbt_connections.json':
  identifier='mybox' host='u000001.your-storagebox.de' user='u000001' key_dir='~/.ssh/'
```

List saved connections:

```bash
hsbt list-connections
hsbt list-connections --format-output yaml
```

Repair a broken connection (re-deploys SSH key, updates known_hosts):

```bash
hsbt repair-connection -i mybox
```

Delete a connection:

```bash
hsbt delete-connection -i mybox
hsbt delete-connection -i mybox --delete-keys    # also removes SSH keypair from disk
```

### Mounting

**Temporary mount** (gone after reboot):

```bash
hsbt mount -i mybox --mount-point /mnt/mybox
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool rclone
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool cifs --smb-username u000001 --smb-password secret
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav --webdav-password secret
```

The WebDAV backend connects over HTTPS (port 443) — useful when ports 23 or 445 are blocked by a
firewall or proxy. It uses rclone internally, so no additional system package is required. The password
can also be supplied via the `HSBT_WEBDAV_PASSWORD` environment variable (falls back to `HSBT_PASSWORD`).

Without a saved connection, pass host and user directly:

```bash
hsbt mount -h u000001.your-storagebox.de -u u000001 --mount-point /mnt/mybox
```

**Persistent mount** (writes an entry to `/etc/fstab` and mounts immediately):

```bash
hsbt mount-perm -i mybox --mount-point /mnt/mybox
hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool rclone --uid 1000 --gid 1000
hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool webdav --webdav-password secret
```

**Unmount** (also removes the fstab entry by default):

```bash
hsbt unmount -i mybox --mount-point /mnt/mybox
hsbt unmount -i mybox --mount-point /mnt/mybox --keep-fstab   # only unmount, leave fstab intact
```

**Sync** remote to local using rclone:

```bash
hsbt sync -i mybox --local-dir /backup/mybox
hsbt sync -i mybox --local-dir /backup/mybox --mode bisync     # bidirectional
hsbt sync -i mybox --local-dir /backup/mybox --mode bisync --resync  # force full resync
```

### File transfer and remote commands

Upload a file:

```bash
hsbt upload -i mybox ./local_file.tar.gz /backup/file.tar.gz
```

Download a file:

```bash
hsbt download -i mybox /backup/file.tar.gz ./local_file.tar.gz
```

Check available disk space:

```bash
hsbt available-space -i mybox
hsbt available-space -i mybox --human-readable
```

Run a remote command (Hetzner's restricted shell supports `ls`, `df`, `mkdir`, `rm`, `touch`, `mv`,
`scp`, `rsync`, and a few others):

```bash
hsbt remote-cmd -i mybox "ls -la"
hsbt remote-cmd -i mybox --no-exec "df -h"    # print the SSH command without running it
```

### Global flags

All commands accept `--debug` to enable verbose logging:

```bash
hsbt --debug mount -i mybox --mount-point /mnt/mybox
```


## Development

### Setup

```bash
git clone https://github.com/motey/hetzner-storage-box-tool.git
cd hetzner-storage-box-tool
pip install pdm
pdm install -G test
```

The package entry point is [hsbt/cli/__init__.py](hsbt/cli/__init__.py). Commands are organized in three
modules under [hsbt/cli/](hsbt/cli/): `connection.py`, `mount.py`, and `transfer.py`. The shared Click
options and the `StorageBox` factory live in [hsbt/cli/_common.py](hsbt/cli/_common.py).

The core logic lives in [hsbt/storage_box.py](hsbt/storage_box.py) which composes an `SshTransport`
([hsbt/transport/ssh.py](hsbt/transport/ssh.py)) with pluggable mount strategies in
[hsbt/mount/](hsbt/mount/).

### Adding a command

1. Write the Click command in the appropriate `hsbt/cli/*.py` module (or create a new one).
2. Register it in [hsbt/cli/__init__.py](hsbt/cli/__init__.py) with `cli.add_command(...)`.
3. Use the `@connection_options(...)` decorator from `_common.py` and `build_storage_box(...)` to get a
   `StorageBox` instance — this keeps connection handling consistent across all commands.

### Adding a mount backend

1. Create a new strategy class in [hsbt/mount/](hsbt/mount/) that extends `MountStrategy`
   ([hsbt/mount/base.py](hsbt/mount/base.py)).
2. Implement `mount()`, `unmount()`, `mount_permanent()`, and `unmount_permanent()`.
3. Register it in `StorageBox.get_mount_strategy()` in [hsbt/storage_box.py](hsbt/storage_box.py).
4. Expose it as a choice on the `--mount-tool` option in [hsbt/cli/mount.py](hsbt/cli/mount.py).

### Testing

See [TESTING.md](TESTING.md) for the full guide. The short version:

```bash
./run_tests.sh                # 339 unit tests, no credentials needed
./run_integration_tests.sh    # integration tests, needs a real storage box
```
