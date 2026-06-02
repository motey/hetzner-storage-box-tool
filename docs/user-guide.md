# User Guide

This guide covers every `hsbt` command with all available options and flags.
For choosing a mount backend, see [Mount Backends](backends.md).
For environment variable reference, see the [Configuration](#configuration) section at the bottom.

## Contents

- [Connection management](#connection-management)
- [Mounting](#mounting)
- [Unmounting](#unmounting)
- [Sync](#sync)
- [File transfer](#file-transfer)
- [Remote commands](#remote-commands)
- [Global flags](#global-flags)
- [Configuration](#configuration)

---

## Connection management

### set-connection

Save a named connection. On first use hsbt deploys your public SSH key to the storage box so that
all subsequent operations are key-only.

```
hsbt set-connection [OPTIONS]

  -i, --identifier TEXT       Name for this connection  [required]
  -h, --host TEXT             Hetzner hostname, e.g. u000001.your-storagebox.de
  -u, --user TEXT             Hetzner username, e.g. u000001
  -s, --ssh-key-dir TEXT      Directory for SSH keypairs (default: ~/.ssh/)
  -c, --config-file-path TEXT Path to the connections JSON file
  -o, --overwrite-existing    Replace an existing connection with the same name
  -e, --exists-ok             Exit silently if the connection already exists
  -k, --skip-key-deployment   Save the connection but do not deploy the SSH key yet
```

**Example:**

```bash
hsbt set-connection -i mybox -h u000001.your-storagebox.de -u u000001
```

If `--host` and `--user` are omitted, hsbt prompts for them interactively.
The password is also prompted on first run in order to deploy the SSH key.

**Skip key deployment** is useful in scripts that provision connections in advance without needing
network access at that moment. The key is deployed automatically on the first command that connects:

```bash
hsbt set-connection -i mybox -h u000001.your-storagebox.de -u u000001 --skip-key-deployment
```

### list-connections

```
hsbt list-connections [OPTIONS]

  -f, --format-output [json|yaml]   Output format (default: json)
  -c, --config-file-path TEXT       Path to the connections JSON file
```

```bash
hsbt list-connections
hsbt list-connections --format-output yaml
```

### repair-connection

Re-deploy the SSH key and update `known_hosts` for an existing connection. Use this when the
connection is broken after a storage box password change or key rotation.

```
hsbt repair-connection [OPTIONS]

  -i, --identifier TEXT       Name of the connection to repair  [required]
  -c, --config-file-path TEXT Path to the connections JSON file
```

```bash
hsbt repair-connection -i mybox
```

### delete-connection

```
hsbt delete-connection [OPTIONS]

  -i, --identifier TEXT       Name of the connection to delete  [required]
  -k, --delete-keys           Also remove the SSH keypair files from disk
  -m, --missing-ok            Exit silently if the connection does not exist
  -c, --config-file-path TEXT Path to the connections JSON file
```

```bash
hsbt delete-connection -i mybox
hsbt delete-connection -i mybox --delete-keys
```

---

## Mounting

### mount

Temporarily mount a storage box. The mount is not persistent and will not survive a reboot.

```
hsbt mount [OPTIONS]

  -i, --identifier TEXT         Saved connection name
  -h, --host TEXT               Hostname (alternative to --identifier)
  -u, --user TEXT               Username (alternative to --identifier)
  -s, --ssh-key-dir TEXT        SSH key directory
  -mp, --mount-point TEXT       Local path to mount to  [required]
  -mt, --mount-tool [sshfs|rclone|cifs|webdav]
                                Mount backend (default: rclone)
  -r, --remote-path TEXT        Remote path to mount (default: home directory)
  -rc, --rclone-config-file TEXT  Custom rclone config file path
  --smb-username TEXT           SMB username (CIFS only)
  --smb-password TEXT           SMB password (CIFS only)
  --smb-domain TEXT             SMB domain (CIFS only, optional)
  --webdav-password TEXT        WebDAV password (WebDAV only)
  -p, --password TEXT           Storage box password (for key deployment or --force-password-use)
  -f, --force-password-use      Use password auth instead of SSH key
  -c, --config-file-path TEXT   Path to the connections JSON file
```

**Examples:**

```bash
# Default backend (rclone)
hsbt mount -i mybox --mount-point /mnt/mybox

# CIFS/SMB
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool cifs \
    --smb-username u000001 --smb-password secret

# WebDAV over HTTPS (useful when ports 23 and 445 are blocked)
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav \
    --webdav-password secret

# Without a saved connection
hsbt mount -h u000001.your-storagebox.de -u u000001 --mount-point /mnt/mybox
```

The WebDAV password can also be supplied via the `HSBT_WEBDAV_PASSWORD` environment variable
(falls back to `HSBT_PASSWORD` when `HSBT_WEBDAV_PASSWORD` is not set).

### mount-perm

Add a persistent mount entry and mount immediately. Requires root for most persistence styles.

```
hsbt mount-perm [OPTIONS]

  -i, --identifier TEXT         Saved connection name
  -h, --host TEXT               Hostname (alternative to --identifier)
  -u, --user TEXT               Username (alternative to --identifier)
  -s, --ssh-key-dir TEXT        SSH key directory
  -m, --mount-point TEXT        Local path to mount to  [required]
  -mt, --mount-tool [sshfs|rclone|cifs|webdav]
                                Mount backend (default: rclone)
  -ms, --mount-style [fstab|systemd-automount|autofs]
                                Persistence style (default: fstab)
  -r, --remote-path TEXT        Remote path to mount (default: home directory)
  -ff, --fstab-file TEXT        Override the config file path written to
  -ui, --uid TEXT               UID for the mount (default: current user)
  -gi, --gid TEXT               GID for the mount (default: current group)
  -rc, --rclone-config-file TEXT  Custom rclone config file path
  --smb-username TEXT           SMB username (CIFS only)
  --smb-password TEXT           SMB password (CIFS only)
  --smb-domain TEXT             SMB domain (CIFS only, optional)
  --webdav-password TEXT        WebDAV password (WebDAV only)
  -p, --password TEXT           Storage box password
  -f, --force-password-use      Use password auth instead of SSH key
  -c, --config-file-path TEXT   Path to the connections JSON file
```

**Default config file paths by persistence style:**

| Style | Default config path |
|---|---|
| `fstab` | `/etc/fstab` |
| `systemd-automount` | `/etc/systemd/system/` |
| `autofs` | `/etc/` |

Use `--fstab-file` to override any of these.

**Examples:**

```bash
# fstab entry (survives reboots)
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool rclone --uid 1000 --gid 1000

# systemd automount: on-demand, auto-disconnects after 10 minutes of inactivity
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style systemd-automount

# autofs: on-demand via automountd daemon
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style autofs

# CIFS with systemd automount
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox \
    --mount-style systemd-automount --mount-tool cifs \
    --smb-username u000001 --smb-password secret
```

> `systemd-automount` and `autofs` support `--mount-tool sshfs` and `--mount-tool cifs` only.

#### systemd automount in detail

`--mount-style systemd-automount` writes two unit files to `/etc/systemd/system/`:

- `<name>.mount` — defines the actual mount (type, source, options)
- `<name>.automount` — triggers the mount on first filesystem access and unmounts after
  10 minutes of inactivity (`TimeoutIdleSec=600`)

The unit name is derived from the mount path: `/mnt/mybox` becomes `mnt-mybox`.
The automount unit is enabled and started immediately after installation.

```bash
# Install
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style systemd-automount

# Trigger: just access the directory, the mount happens automatically
ls /mnt/mybox

# Remove
sudo hsbt unmount -i mybox --mount-point /mnt/mybox --mount-style systemd-automount
```

#### autofs in detail

`--mount-style autofs` writes two files:

- `/etc/auto.hsbt_<identifier>` — the autofs direct map, one entry per mountpoint
- `/etc/auto.master` — a direct-map line pointing to the map file above

The `automountd` daemon triggers the mount when the path is accessed and releases it after
`--timeout` seconds (default: 60).

If you run `mount-perm --mount-style autofs` for multiple boxes, each gets its own map file
but only one entry is added to `auto.master` per connection, keeping the file clean.

```bash
sudo apt install autofs
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style autofs

# Access triggers the mount
ls /mnt/mybox

# Remove
sudo hsbt unmount -i mybox --mount-point /mnt/mybox --mount-style autofs
```

---

## Unmounting

### unmount

Unmount and remove the persistent config entry. Pass `--keep-fstab` to only unmount without
touching the config.

```
hsbt unmount [OPTIONS]

  -i, --identifier TEXT         Saved connection name
  -h, --host TEXT               Hostname (alternative to --identifier)
  -u, --user TEXT               Username
  -m, --mount-point TEXT        Mount point to unmount  [required]
  -mt, --mount-tool [sshfs|rclone|cifs|webdav]
                                Backend that was used to mount (default: sshfs)
  -ms, --mount-style [fstab|systemd-automount|autofs]
                                Persistence style that was used (default: fstab)
  -ff, --fstab-file TEXT        Override the config directory path
  --keep-fstab                  Only unmount, leave the config entry in place
  -c, --config-file-path TEXT   Path to the connections JSON file
```

**Examples:**

```bash
# fstab mount
hsbt unmount -i mybox --mount-point /mnt/mybox
hsbt unmount -i mybox --mount-point /mnt/mybox --keep-fstab

# systemd automount
sudo hsbt unmount -i mybox --mount-point /mnt/mybox --mount-style systemd-automount

# autofs
sudo hsbt unmount -i mybox --mount-point /mnt/mybox --mount-style autofs
```

---

## Sync

### sync

Sync storage box contents to a local directory using rclone.

```
hsbt sync [OPTIONS]

  -i, --identifier TEXT         Saved connection name
  -h, --host TEXT               Hostname (alternative to --identifier)
  -u, --user TEXT               Username
  -l, --local-dir PATH          Local directory to sync into  [required]
  -r, --remote-path TEXT        Remote path to sync from (default: home directory)
  --mode [sync|bisync]          sync = remote to local only; bisync = bidirectional (default: sync)
  --resync                      Force a full resync (bisync only, use after first setup)
  -v, --verbose                 Verbose rclone output
  -rc, --rclone-config-file TEXT  Custom rclone config file path
  -c, --config-file-path TEXT   Path to the connections JSON file
```

**Examples:**

```bash
# One-way sync (remote to local)
hsbt sync -i mybox --local-dir ~/backup/mybox

# Bidirectional sync
hsbt sync -i mybox --local-dir ~/mybox-mirror --mode bisync

# First-time bisync: force full resync to establish a baseline
hsbt sync -i mybox --local-dir ~/mybox-mirror --mode bisync --resync

# Sync a specific remote subdirectory
hsbt sync -i mybox --local-dir ~/backup/docs --remote-path /home/docs
```

> Use `--resync` on the first `bisync` run or after a reset. Without it, bisync compares
> against the last-known state, which does not exist yet on the first run.

---

## File transfer

### upload

Upload a local file to the storage box via SCP.

```
hsbt upload [OPTIONS] LOCAL_PATH REMOTE_PATH

  -i, --identifier TEXT   Saved connection name
  LOCAL_PATH              Path to the local file (must exist)
  REMOTE_PATH             Destination path on the storage box
```

```bash
hsbt upload -i mybox ./backup.tar.gz /backups/backup.tar.gz
```

### download

Download a file from the storage box via SCP.

```
hsbt download [OPTIONS] REMOTE_PATH LOCAL_PATH

  -i, --identifier TEXT   Saved connection name
  REMOTE_PATH             Path on the storage box
  LOCAL_PATH              Local destination path
```

```bash
hsbt download -i mybox /backups/backup.tar.gz ./backup.tar.gz
```

### available-space

Show disk usage for the storage box.

```
hsbt available-space [OPTIONS]

  -i, --identifier TEXT    Saved connection name
  -H, --human-readable     Show sizes in human-readable units (KB, MB, GB)
```

```bash
hsbt available-space -i mybox
hsbt available-space -i mybox --human-readable
```

---

## Remote commands

### remote-cmd

Run a command on the storage box over SSH. Hetzner's restricted shell supports a limited set
of commands: `ls`, `df`, `mkdir`, `rm`, `touch`, `mv`, `scp`, `rsync`, and a few others.

Full list: https://docs.hetzner.com/robot/storage-box/access/access-ssh-rsync-borg#available-commands

```
hsbt remote-cmd [OPTIONS] COMMAND

  -i, --identifier TEXT   Saved connection name
  -n, --no-exec           Print the SSH command without running it
  COMMAND                 Command string to execute on the remote shell
```

```bash
hsbt remote-cmd -i mybox "ls -la"
hsbt remote-cmd -i mybox "mkdir -p /home/backups/2026"
hsbt remote-cmd -i mybox --no-exec "df -h"   # prints the SSH command, does not run it
```

---

## Global flags

All commands accept `--debug` before the subcommand name to enable verbose logging:

```bash
hsbt --debug mount -i mybox --mount-point /mnt/mybox
hsbt --debug set-connection -i mybox -h u000001.your-storagebox.de -u u000001
```

---

## Configuration

### Environment variables

CLI flags always take precedence over environment variables.

**Paths and credentials:**

| Variable | Description |
|---|---|
| `HSBT_CENTRAL_CONFIG_DIR` | One-stop directory. hsbt looks for `<dir>/config/hetzner_sbt_connections.json`, `<dir>/ssh/`, and `<dir>/rclone/rclone.conf` automatically. Useful for containers. |
| `HSBT_CONNECTIONS_CONFIG_FILE` | Explicit path to the connections JSON file. |
| `HSBT_SSH_KEY_FILE_DIR` | Directory for SSH keypairs. Defaults to `~/.ssh/`. |
| `HSBT_RCLONE_CONFIG_FILE` | Path to the rclone config file. |
| `HSBT_PASSWORD` | Storage box password. Used for initial key deployment and `--force-password-use`. Never stored. |
| `HSBT_WEBDAV_PASSWORD` | Password for the WebDAV backend. Falls back to `HSBT_PASSWORD` when not set. |

**Example: container / CI setup using `HSBT_CENTRAL_CONFIG_DIR`:**

```bash
export HSBT_CENTRAL_CONFIG_DIR=/run/secrets/hsbt
# hsbt will find:
#   /run/secrets/hsbt/config/hetzner_sbt_connections.json
#   /run/secrets/hsbt/ssh/<keypair files>
#   /run/secrets/hsbt/rclone/rclone.conf
```

### Binary path overrides

If system tools are not on your `PATH`, point hsbt at them directly:

| Variable | Tool |
|---|---|
| `HSBT_BIN_PATH_SSH` | `ssh` |
| `HSBT_BIN_PATH_SCP` | `scp` |
| `HSBT_BIN_PATH_SSHFS` | `sshfs` |
| `HSBT_BIN_PATH_SSHPASS` | `sshpass` |
| `HSBT_BIN_PATH_SSH_COPY_ID` | `ssh-copy-id` |
| `HSBT_BIN_PATH_RCLONE` | `rclone` |
| `HSBT_BIN_PATH_MOUNT` | `mount` |
| `HSBT_BIN_PATH_UMOUNT` | `umount` |

### Config file defaults

| Context | Default path |
|---|---|
| Normal user | `~/.config/hetzner_sbt_connections.json` |
| Root | `/etc/hetzner_sbt_connections.json` |
| `HSBT_CENTRAL_CONFIG_DIR` set | `<dir>/config/hetzner_sbt_connections.json` |
| `HSBT_CONNECTIONS_CONFIG_FILE` set | the value of that variable |
