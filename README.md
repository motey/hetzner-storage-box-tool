# hsbt - Hetzner Storage Box Tool

A command-line tool and Python library for [Hetzner Storage Boxes](https://www.hetzner.com/storage/storage-box).
It handles everything from first-time SSH key deployment through permanent system mounts, with a single
scriptable interface that works well in automation, containers, and CI pipelines.

**Key features:**

- Four mount backends: **sshfs**, **rclone** (recommended), **CIFS/SMB**, and **WebDAV over HTTPS**
- Three persistence styles for permanent mounts: **fstab**, **systemd automount**, and **autofs**
- Saved named connections: set up once, reuse everywhere
- One-way and bidirectional **sync** via rclone
- **SCP file transfer** and **remote command** execution
- Usable as a **Python library**: all logic is importable and typed

## Quick start

```bash
# 1. Install
pip install git+https://github.com/motey/hetzner-storage-box-tool.git

# 2. Save a connection (prompts for your password once to deploy an SSH key)
hsbt set-connection -i mybox -h u000001.your-storagebox.de -u u000001

# 3. Mount it
hsbt mount -i mybox --mount-point /mnt/mybox

# 4. Make it survive reboots
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox

# 5. Sync the whole box to a local directory
hsbt sync -i mybox --local-dir ~/backup/mybox
```

After step 2 the password is never needed again. All subsequent operations use the deployed SSH key.
If you only have one saved connection, you can omit `-i mybox` everywhere.

## More examples

```bash
# Upload a backup
hsbt upload -i mybox ./archive.tar.gz /backups/archive.tar.gz

# Check how much space is left
hsbt available-space -i mybox --human-readable

# Mount via HTTPS WebDAV (useful when SSH/SMB ports are blocked)
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav --webdav-password secret

# On-demand mount with auto-disconnect after 10 min of inactivity
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style systemd-automount

# Bidirectional sync (keeps both sides in step)
hsbt sync -i mybox --local-dir ~/mybox-mirror --mode bisync
```

## Installation

**System dependencies** (Debian/Ubuntu, install only what you need):

```bash
apt install openssh-client sshpass   # always needed
apt install sshfs                    # for --mount-tool sshfs
apt install rclone                   # for --mount-tool rclone / webdav / sync
apt install cifs-utils               # for --mount-tool cifs
apt install autofs                   # for --mount-style autofs
```

**Python package** (requires Python 3.14+):

```bash
pip install git+https://github.com/motey/hetzner-storage-box-tool.git
```

Or with [PDM](https://pdm-project.org):

```bash
pdm add git+https://github.com/motey/hetzner-storage-box-tool.git
```

After installation `hsbt` is available on your PATH. Run `hsbt --help` to confirm.

## How it works

hsbt stores named connections in a JSON config file (default: `~/.config/hetzner_sbt_connections.json`).
Each connection holds the hostname, username, and a path to an SSH keypair.

On the first `set-connection` call hsbt prompts for your password and deploys your public key to the
storage box via `ssh-copy-id`. After that all operations are key-only and the password is never stored.

When exactly **one** connection is saved, passing `-i <name>` is optional: hsbt selects it automatically.
With multiple connections `-i <name>` is always required.

## Documentation

| Document | Audience |
|---|---|
| [User Guide](docs/user-guide.md) | Every command, every option, all environment variables |
| [Mount Backends](docs/backends.md) | Choosing between sshfs / rclone / CIFS / WebDAV, setup per backend |
| [Python API](docs/api.md) | Using hsbt as a library in Python code |
| [Development Guide](docs/development.md) | Architecture, adding commands/backends, contributing |
| [Testing Guide](TESTING.md) | Unit tests, integration tests, CI setup |

## License

MIT
