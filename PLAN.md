# HSBT — Development Plan

Status key: ✅ Done · 🔄 Partial · ⬜ Todo · 🔁 Deferred

---

## Phase 1 — Critical Bug Fixes

All blocking bugs fixed as part of the refactor. Two additional bugs were found
and fixed during the Phase 8 test run against the live storage box.

| # | Item | Status |
|---|------|--------|
| 1.1 | `env_var_names.py` — `BIN_PATH_SSH` copied `RCLONE` env var name | ✅ |
| 1.2 | `utils.py` — `download_file()` called `Path(str)` (type object) instead of `Path(target)` | ✅ |
| 1.3 | `utils.py` — `download_file()` called `.close()` on a boolean flag instead of the file handle | ✅ |
| 1.4 | `rclone_manager.py` — `mount_fstab()` referenced undefined variable `command` | ✅ |
| 1.5 | `storage_box_manager.py` — Several mount methods missing `self`; `|` dict merge syntax error | ✅ |
| 1.6 | `config_editor.py` — `_File.is_last()` used physical line index instead of cursor position, causing `IndexError` on any second call to `set_config_entry()` (every fstab update after the first would crash) | ✅ |
| 1.7 | `transport/ssh.py` — `deploy_public_key_if_not_done()` checked `result.stdout` for the Hetzner SFTP-mode message but the message arrives on `result.stderr`; SFTP retry never fired | ✅ |

---

## Phase 2 — Code Quality & Structural Cleanup

Addressed entirely by the refactor in Phase 7.

| # | Item | Status |
|---|------|--------|
| 2.1 | Remove `print()` debug statements; use `logging` consistently | ✅ |
| 2.2 | Fix `ovewrite_existing` typo → `overwrite_existing` throughout | ✅ |
| 2.3 | Replace bare `except:` in `key_manager.py` with specific exception types | ✅ |
| 2.4 | Flatten the `connection_options` decorator (was triple-nested ternary logic) | ✅ |
| 2.5 | Deduplicate `get_config_file_path` / `get_ssh_dir` / `get_rclone_config_file_path` helpers | ✅ |
| 2.6 | Rename CLI commands from camelCase to kebab-case (`setConnection` → `set-connection`, etc.) | ✅ |
| 2.7 | Add `__all__` exports to public module surfaces | ⬜ |

---

## Phase 3 — Complete Existing Partial Features

All wired up.

| # | Item | Status |
|---|------|--------|
| 3.1 | `rclone mount_fstab()` — was broken (undefined `command`); now `RcloneMountStrategy.mount_permanent()` | ✅ |
| 3.2 | `storage_box_is_mounted()` — was `raise NotImplementedError`; now `is_mounted()` on each strategy via `mountpoint -q` | ✅ |
| 3.3 | `get_mount_commands_for_sshfs()` — partially done; replaced by `SshfsMountStrategy.mount()` | ✅ |
| 3.4 | `mount_storage_box_via_sshfs()` (direct/temp mount) — was stub; now `SshfsMountStrategy.mount()` | ✅ |
| 3.5 | `available_space` CLI command — was stub function; now wired as `hsbt available-space` | ✅ |
| 3.6 | `upload_to_remote` / `download_from_remote` CLI stubs — now `hsbt upload` / `hsbt download` | ✅ |

---

## Phase 4 — SMB/CIFS Mount Support

| # | Item | Status |
|---|------|--------|
| 4.1 | `SmbCifsSecretManager` — was untracked file; now integrated into `hsbt/mount/cifs.py` | ✅ |
| 4.2 | `mount_storage_box_via_cifs()` — was stub; now `CifsMountStrategy.mount()` | ✅ |
| 4.3 | `mount_storage_box_via_fstab_via_cifs()` — was skeleton; now `CifsMountStrategy.mount_permanent()` | ✅ |
| 4.4 | SMB credentials (username/password/domain) plumbed through CLI options | ✅ |
| 4.5 | `--mount-tool=cifs` on both `mount` and `mount-perm` commands | ✅ |
| 4.6 | `hsbt unmount` command — was missing; now implemented | ✅ |

---

## Phase 5 — Rclone Sync & Bisync

| # | Item | Status |
|---|------|--------|
| 5.1 | `RcloneMountStrategy.bisync()` — was stub; now implemented | ✅ |
| 5.2 | `RcloneMountStrategy.sync_from_remote()` — was stub; now implemented | ✅ |
| 5.3 | `hsbt sync` command with `--mode=sync` / `--mode=bisync` and `--resync` flag | ✅ |

---

## Phase 6 — Rclone Fstab / Permanent Mount

| # | Item | Status |
|---|------|--------|
| 6.1 | `RcloneMountStrategy.mount_permanent()` — was broken; now implemented with correct fstab entry format | ✅ |
| 6.2 | `--mount-tool=rclone` on `mount-perm` command | ✅ |

---

## Phase 7 — Architecture Refactor

The full structural overhaul completed in this session.

| # | Item | Status |
|---|------|--------|
| 7.1 | Extract `models.py` — `Connection`, `ConnectionList`, `FileInfo`, `FileInfoCollection` | ✅ |
| 7.2 | Extract `process.py` — `ProcessOutput`, `CommandResult`, `open_process()`, `run_command()` | ✅ |
| 7.3 | Extract `config_editor.py` — `ConfigFileEditor` | ✅ |
| 7.4 | Trim `utils.py` to pure utilities; fix all bugs | ✅ |
| 7.5 | Update `connection_manager.py` — use `models.py`, Pydantic v2 API | ✅ |
| 7.6 | Create `transport/ssh.py` — `SshTransport` extracted from `HetznerStorageBox` | ✅ |
| 7.7 | Create `mount/base.py` — abstract `MountStrategy` | ✅ |
| 7.8 | Create `mount/sshfs.py` — `SshfsMountStrategy` | ✅ |
| 7.9 | Create `mount/cifs.py` — `CifsMountStrategy` + `SmbCifsSecretManager` | ✅ |
| 7.10 | Create `mount/rclone.py` — `RcloneMountStrategy` | ✅ |
| 7.11 | Create `storage_box.py` — `StorageBox` facade | ✅ |
| 7.12 | Replace monolithic `cli.py` with `cli/` package (`_common`, `connection`, `mount`, `transfer`) | ✅ |
| 7.13 | Replace `setup.py` with `pyproject.toml` (PDM backend); register all subpackages | ✅ |
| 7.14 | Delete superseded files (`storage_box_manager.py`, `rclone_manager.py`, `smb_cifs_secrets_manager.py`) | ✅ |

---

## Phase 8 — PyTest Setup & CI

> Goal: establish a test suite that covers the logic that can be tested without a live storage box,
> plus an opt-in integration layer that runs against a real box.

| # | Item | Status |
|---|------|--------|
| 8.1 | Add `pytest` and `pytest-mock` to `[project.optional-dependencies]` in `pyproject.toml` | ✅ |
| 8.2 | Create `tests/` directory with `conftest.py` (shared fixtures, real Hetzner `ls`/`df` output constants) | ✅ |
| 8.3 | `tests/test_models.py` — `Connection`, `ConnectionList` CRUD, `FileInfo` parsing | ✅ |
| 8.4 | `tests/test_process.py` — `run_command()` success/failure paths using real shell (no mock needed) | ✅ |
| 8.5 | `tests/test_config_editor.py` — insert/update/remove fstab blocks; idempotency | ✅ |
| 8.6 | `tests/test_key_manager.py` — key path generation; `known_host_entry_exists` (mock `run_command`) | ✅ |
| 8.7 | `tests/test_connection_manager.py` — set/get/delete across config files (`tmp_path`) | ✅ |
| 8.8 | `tests/test_ssh_transport.py` — `_get_ssh_options()`, `run_remote_command()` retry logic (mock) | ✅ |
| 8.9 | `tests/test_mount_sshfs.py` — fstab entry format, idempotent write, `is_mounted()` | ✅ |
| 8.10 | `tests/test_mount_cifs.py` — credential file creation/update, fstab entry format | ✅ |
| 8.11 | `tests/test_mount_rclone.py` — config generation, fstab entry format, sync/bisync flags | ✅ |
| 8.12 | `tests/test_smb_cifs_secret_manager.py` — file write/read/delete, permission bits | ✅ |
| 8.13 | `tests/test_storage_box.py` — `get_mount_strategy()` returns correct type; facade pass-throughs | ✅ |
| 8.14 | `tests/test_cli_connection.py` — Click test runner for `set-connection`, `list-connections`, `delete-connection` | ✅ |
| 8.15 | `tests/test_cli_mount.py` — Click test runner for `mount`, `mount-perm`, `unmount` (mock strategy) | ✅ |
| 8.16 | `tests/test_cli_transfer.py` — Click test runner for `remote-cmd`, `upload`, `download`, `available-space` | ✅ |
| 8.17 | `[tool.pytest.ini_options]` in `pyproject.toml` | ✅ |
| 8.18 | GitHub Actions workflow for **unit tests** on every push/PR (no credentials needed) | ⬜ |
| 8.19 | GitHub Actions workflow for **integration tests** — triggers on push to `main`, reads storage box credentials from repository secrets | ✅ |
| 8.20 | Upgrade to Python 3.14; switch from `setup.py` to PDM (`pyproject.toml`) | ✅ |
| 8.21 | `run_tests.sh` — one-shot script: finds Python 3.14+, sets up PDM venv, runs unit tests | ✅ |
| 8.22 | Integration test suite `tests/integration/` — 24 tests covering real SSH connectivity, file listing, disk space, directory creation, SCP roundtrip, StorageBox facade; skipped automatically without credentials | ✅ |
| 8.23 | `run_integration_tests.sh` — validates credentials, runs integration suite with `--tb=short` to avoid credential leakage in tracebacks | ✅ |
| 8.24 | `TESTING.md` — documents unit and integration test setup, all env vars, GitHub Actions secrets, key-caching behaviour | ✅ |

---

## Phase 9 — Documentation

| # | Item | Status |
|---|------|--------|
| 9.1 | Rewrite `README.md` — installation, quick-start, all current command names with examples | ✅ |
| 9.2 | Migration guide section — map old camelCase commands to new kebab-case equivalents | ⬜ |
| 9.3 | Document all CLI options per command (can use `hsbt <cmd> --help` output as source) | ✅ |
| 9.4 | Document CIFS/SMB setup — what Hetzner settings to enable, what credentials to use | ⬜ |
| 9.5 | Document rclone setup — when to use rclone vs sshfs vs cifs | ⬜ |
| 9.6 | Add docstrings to public classes: `StorageBox`, `SshTransport`, `MountStrategy` subclasses, `ConnectionManager` | ⬜ |
| 9.7 | Add `CHANGELOG.md` — document breaking changes from the refactor | ⬜ |
| 9.8 | Replace `setup.py` with `pyproject.toml` (modern packaging, PDM backend, Python 3.14) | ✅ |

---

## Phase 10 — Systemd Automount / Autofs (Deferred)

Low priority. Only worth doing after Phases 8–9 are complete.

| # | Item | Status |
|---|------|--------|
| 10.1 | `SystemdMountStrategy` — generate `.mount` + `.automount` unit files, `systemctl enable/start` | ✅ |
| 10.2 | `AutofsMountStrategy` — write `/etc/auto.master` entry and map file | ✅ |
| 10.3 | Wire `--mount-style=systemd-automount` and `--mount-style=autofs` into `mount-perm` | ✅ |

---

## Phase 11 — New Features / Ideas

| # | Item | Status |
|---|------|--------|
| 11.1 | Default connection identifier for single-box setups — skip `--identifier` when only one connection is saved | ✅ |
| 11.2 | Evaluate WebDAV support — does it fit alongside SSH/CIFS as a third transport? | ✅ |

---

## Current File Structure

```
hsbt/
├── models.py             # Connection, ConnectionList, FileInfo, FileInfoCollection
├── process.py            # ProcessOutput, CommandResult, open_process, run_command
├── config_editor.py      # ConfigFileEditor
├── env_var_names.py      # Env var constants (all fixed)
├── utils.py              # is_root, cast_path, parse_ls_l_output, download_file, ...
├── key_manager.py        # SSH key generation and known_hosts management
├── connection_manager.py # Load/save named connections from JSON
├── storage_box.py        # StorageBox facade
├── transport/
│   └── ssh.py            # SshTransport — SSH/SCP execution, key deploy, file ops
├── mount/
│   ├── base.py           # Abstract MountStrategy
│   ├── sshfs.py          # SshfsMountStrategy
│   ├── cifs.py           # CifsMountStrategy + SmbCifsSecretManager
│   ├── rclone.py         # RcloneMountStrategy (+ sync/bisync)
│   ├── systemd.py        # SystemdMountStrategy (.mount + .automount units)
│   └── autofs.py         # AutofsMountStrategy (direct map + auto.master)
└── cli/
    ├── _common.py        # Shared helpers, build_storage_box factory
    ├── connection.py     # set-connection, list-connections, repair-connection, delete-connection
    ├── mount.py          # mount, mount-perm, unmount, sync
    └── transfer.py       # remote-cmd, available-space, upload, download

tests/
├── conftest.py           # shared fixtures, real Hetzner ls/df output constants
├── test_*.py             # 247 unit tests (no network, ~0.5 s)
└── integration/
    ├── conftest.py       # live transport fixture, remote workdir setup/teardown
    ├── test_transport.py # 15 real SshTransport tests
    └── test_storage_box.py # 9 real StorageBox tests

run_tests.sh              # unit test runner (sets up PDM + Python 3.14)
run_integration_tests.sh  # integration test runner (requires live box credentials)
TESTING.md                # full test setup documentation
.github/workflows/
└── integration.yml       # CI for integration tests (reads repository secrets)
```

## CLI Command Reference (current)

| Command | Description |
|---------|-------------|
| `hsbt set-connection` | Create or update a named connection |
| `hsbt list-connections` | List all saved connections |
| `hsbt repair-connection` | Re-deploy SSH key if broken |
| `hsbt delete-connection` | Remove a connection (optionally its SSH keys) |
| `hsbt mount` | Transient mount (sshfs / cifs / rclone) |
| `hsbt mount-perm` | Persistent fstab mount (sshfs / cifs / rclone) |
| `hsbt unmount` | Unmount and optionally remove fstab entry |
| `hsbt sync` | Sync via rclone (one-way or bisync) |
| `hsbt remote-cmd` | Run a command on the storage box |
| `hsbt available-space` | Show disk usage |
| `hsbt upload` | Upload a local file via SCP |
| `hsbt download` | Download a file via SCP |
