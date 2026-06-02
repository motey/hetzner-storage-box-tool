# Mount Backends

hsbt supports four mount backends. This guide explains when to use each one and how to set
up the prerequisites on both your local machine and the Hetzner side.

## Choosing a backend

The default backend is **rclone** (used when `--mount-tool` is not specified).

| Backend | Protocol | Port | Requires on Hetzner | Local dependency | Good for |
|---|---|---|---|---|---|
| `rclone` | SFTP over SSH | 23 | SSH access | `rclone` | `Default` Recommended general use, sync/bisync |
| `sshfs` | SFTP over SSH | 23 | SSH access | `sshfs` | Simple mounts, lighweight |
| `cifs` | SMB/CIFS | 445 | Samba/CIFS access | `cifs-utils` | Windows/NAS compatibility, NFS-style sharing |
| `webdav` | WebDAV over HTTPS | 443 | WebDAV/HTTPS access | `rclone` | Restricted networks, proxy/firewall traversal |

**Short recommendation:**

- Use `rclone` for most cases. It is actively developed, supports sync/bisync, and performs
  better under heavy I/O due to its VFS caching layer.
- Use `sshfs` if you want a lighter option for simple temporary mounts and do not need sync.
  The project is in maintenance mode (bug fixes, regular releases, no new features) — it is
  stable and widely packaged.
- Use `cifs` if you need native SMB semantics or are sharing the mount with Windows clients.
- Use `webdav` when ports 23 and 445 are blocked (common in corporate networks).

---

## sshfs

**Protocol:** SFTP over SSH, port 23

**Local dependency:**

```bash
apt install sshfs
```

**Hetzner setup:** Enable SSH access in Hetzner Robot under Storage Box > Settings > SSH.
No additional steps needed.

**Usage:**

```bash
# Temporary
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool sshfs

# Persistent (fstab)
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool sshfs
```

**Notes:**

- sshfs is in maintenance mode: the project receives regular bug-fix releases and is shipped
  by all major Linux distributions, but there is no active feature development. See the
  [upstream repository](https://github.com/libfuse/sshfs) for current status.
- Performance under heavy or random I/O is lower than rclone (no caching layer).
- Does not support sync or bisync.

---

## rclone

**Protocol:** SFTP over SSH, port 23

**Local dependency:**

```bash
apt install rclone
```

**Hetzner setup:** Same as sshfs — SSH access must be enabled in Hetzner Robot.
No extra steps needed.

**Usage:**

```bash
# Temporary mount
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool rclone

# Persistent (fstab)
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool rclone --uid 1000 --gid 1000

# One-way sync (remote to local)
hsbt sync -i mybox --local-dir ~/backup/mybox

# Bidirectional sync
hsbt sync -i mybox --local-dir ~/mybox-mirror --mode bisync --resync
```

**Notes:**

- `--uid` and `--gid` on `mount-perm` set the owner of the fstab-mounted filesystem.
  Use your own UID/GID so that normal users can write to the mount without root.
- rclone writes its own config section per connection. hsbt manages this automatically.
  The config is stored at `~/.config/rclone/rclone.conf` by default, or at the path set
  via `HSBT_RCLONE_CONFIG_FILE` / `--rclone-config-file`.
- For `--mode bisync`, run with `--resync` on the very first call to establish a baseline.
  After that, use it without `--resync` for normal operation.

---

## CIFS / SMB

**Protocol:** SMB over TCP, port 445

**Local dependency:**

```bash
apt install cifs-utils
```

**Hetzner setup:**

1. Log in to [Hetzner Robot](https://robot.hetzner.com).
2. Go to **Storage Box** and select your box.
3. Under **Settings**, enable **Samba/CIFS** access.
4. Note your username (same as SSH, e.g. `u000001`) and the box password.

The SMB share path is `//u000001.your-storagebox.de/backup` where the share name
is always `backup`.

**Credentials file:** hsbt creates a credentials file at `~/.config/hsbt/<identifier>.cifs`
with permissions `0600`. The file contains the username and password in the format expected
by `mount.cifs`. It is managed automatically and you do not need to create it manually.

**Usage:**

```bash
# Temporary mount
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool cifs \
    --smb-username u000001 --smb-password secret

# Persistent (fstab)
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool cifs \
    --smb-username u000001 --smb-password secret

# systemd automount with CIFS
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox \
    --mount-style systemd-automount --mount-tool cifs \
    --smb-username u000001 --smb-password secret
```

**`--smb-domain`** is optional. Most Hetzner setups do not require it.

**Notes:**

- CIFS mounts require root (`sudo`) even for temporary mounts.
- The `--smb-password` flag accepts the value on the command line. For scripts, prefer
  passing it via a credentials file or environment variable to avoid the password appearing
  in the process list.
- Persistent CIFS mounts write the credentials file path into `/etc/fstab`. The credentials
  file itself must remain at the same path for the mount to work after a reboot.

---

## WebDAV

**Protocol:** WebDAV over HTTPS, port 443

**Local dependency:**

```bash
apt install rclone
```

WebDAV uses rclone internally. No additional tools are needed.

**Hetzner setup:**

1. Log in to [Hetzner Robot](https://robot.hetzner.com).
2. Go to **Storage Box** and select your box.
3. Under **Settings**, enable **WebDAV/HTTPS** access.
4. Your WebDAV endpoint is `https://u000001.your-storagebox.de`.
5. The username is the same as SSH. The password is your box password or a sub-account password.

**Usage:**

```bash
# Temporary mount
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav \
    --webdav-password secret

# Persistent (fstab)
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-tool webdav \
    --webdav-password secret

# Using an environment variable instead of the flag
export HSBT_WEBDAV_PASSWORD=secret
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav
```

`HSBT_WEBDAV_PASSWORD` is checked first; if not set, `HSBT_PASSWORD` is used as a fallback.

**When to use WebDAV:**

- Port 23 (SSH/SFTP) and port 445 (SMB) are blocked by a corporate firewall or proxy.
- You need HTTPS-only access (e.g. security policy).
- You are behind a proxy that intercepts HTTPS but not SSH.

**Limitations:**

- WebDAV performance is lower than SFTP-based backends under high-throughput workloads.
- Sync (`hsbt sync`) is not supported with the WebDAV backend.
- `--mount-style systemd-automount` and `--mount-style autofs` are not supported with WebDAV.

---

## Persistence styles

All backends (where supported) can be made persistent in three ways:

### fstab

Writes a standard entry to `/etc/fstab`. The filesystem is mounted at boot.

- Supports: sshfs, rclone, cifs, webdav
- Requires root to write to `/etc/fstab`

### systemd-automount

Writes two systemd unit files. The filesystem is mounted on first access and automatically
unmounted after 10 minutes of inactivity.

- Supports: sshfs, cifs
- Requires root and systemd
- Useful for laptops and desktops that should not hold a persistent SSH connection

### autofs

Writes an autofs direct map entry. The filesystem is mounted on demand by the `automountd`
daemon and released after a configurable timeout.

- Supports: sshfs, cifs
- Requires root and the `autofs` package
- Useful for servers with many storage boxes: only active paths incur a connection
