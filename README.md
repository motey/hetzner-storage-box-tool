<div align="center">

# 📦 hsbt — Hetzner Storage Box Tool

**One scriptable CLI (and typed Python library) for [Hetzner Storage Boxes](https://www.hetzner.com/storage/storage-box)** —
from first SSH key deployment to permanent system mounts.

[![PyPI](https://img.shields.io/pypi/v/hsbt?logo=pypi&logoColor=white)](https://pypi.org/project/hsbt/)
[![Python](https://img.shields.io/pypi/pyversions/hsbt?logo=python&logoColor=white)](https://pypi.org/project/hsbt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Integration Tests](https://github.com/motey/hetzner-storage-box-tool/actions/workflows/integration.yml/badge.svg)](https://github.com/motey/hetzner-storage-box-tool/actions/workflows/integration.yml)
[![GitHub](https://img.shields.io/badge/GitHub-motey%2Fhetzner--storage--box--tool-181717?logo=github)](https://github.com/motey/hetzner-storage-box-tool)

</div>

---

## ✨ Highlights

- 🔌 **4 mount backends** — `rclone` (recommended · [why](docs/backends.md#choosing-a-backend)), `sshfs`, `CIFS/SMB`, `WebDAV over HTTPS`
- ♻️ **3 persistence styles** — fstab · systemd automount · autofs
- 🔑 **Password-free after setup** — deploys an SSH key once, then it's key-only forever
- 🔄 **One-way & bidirectional sync** via rclone
- 📤 **SCP transfer & remote commands** out of the box
- 🐍 **Importable Python library** — every operation is typed and reusable

## 🚀 Quick start

```bash
pip install hsbt

# Save a connection (prompts for your password once to deploy an SSH key)
hsbt set-connection -i mybox -h u000001.your-storagebox.de -u u000001

# Mount it (default backend: rclone)
hsbt mount -i mybox --mount-point /mnt/mybox

# Make it survive reboots
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox

# Sync the whole box to a local directory
hsbt sync -i mybox --local-dir ~/backup/mybox
```

> After the first `set-connection` the password is never needed again. With only one saved connection, `-i mybox` is optional everywhere.

## 🧰 Commands

| Command | Does |
|---|---|
| `set-connection` · `list-connections` · `repair-connection` · `delete-connection` | Manage saved named connections |
| `mount` · `mount-perm` · `unmount` | Temporary and reboot-persistent mounts |
| `sync` | One-way or bidirectional sync via rclone |
| `upload` · `download` · `available-space` | File transfer & disk usage |

Run `hsbt --help` or `hsbt <command> --help` for every option.

## 📥 Installation

```bash
pip install hsbt          # from PyPI
pdm add hsbt              # or with PDM
```

**System dependencies** (Debian/Ubuntu — install only what you use):

```bash
apt install openssh-client sshpass   # always needed
apt install rclone                   # --mount-tool rclone / webdav / sync
apt install sshfs                    # --mount-tool sshfs
apt install cifs-utils               # --mount-tool cifs
apt install autofs                   # --mount-style autofs
```

Requires **Python 3.14+**. After install, `hsbt` is on your `PATH`.

## 💡 More examples

```bash
# Mount via HTTPS WebDAV (when SSH/SMB ports are blocked)
hsbt mount -i mybox --mount-point /mnt/mybox --mount-tool webdav --webdav-password secret

# On-demand mount, auto-disconnect after inactivity
sudo hsbt mount-perm -i mybox --mount-point /mnt/mybox --mount-style systemd-automount

# Bidirectional sync (keeps both sides in step)
hsbt sync -i mybox --local-dir ~/mybox-mirror --mode bisync
```

## 📚 Documentation

| Document | Audience |
|---|---|
| [User Guide](docs/user-guide.md) | Every command, option, and environment variable |
| [Mount Backends](docs/backends.md) | Choosing sshfs / rclone / CIFS / WebDAV, per-backend setup |
| [Python API](docs/api.md) | Using hsbt as a library |
| [Development Guide](docs/development.md) | Architecture, adding commands/backends, contributing |
| [Testing Guide](TESTING.md) | Unit tests, integration tests, CI setup |

## ⚙️ How it works

hsbt stores named connections in a JSON config file (default `~/.config/hetzner_sbt_connections.json`),
each holding a hostname, username, and SSH keypair path. The first `set-connection` prompts for your
password and deploys your public key via `ssh-copy-id`; from then on every operation is key-only and the
password is never stored.

## 📄 License

[MIT](LICENSE) © Tim Bleimehl
