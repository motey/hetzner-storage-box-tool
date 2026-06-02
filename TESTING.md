# Testing

The test suite is split into two independent layers:

| Layer | Tests | Needs storage box | Needs root | Time |
|---|---|---|---|---|
| **Unit tests** | 425 | No | No | ~0.7 s |
| **Integration tests — Tier 1** | ~50 | Yes | No | ~25 s |
| **Integration tests — Tier 2** | ~10 | Yes | Yes | ~5 s |

Both layers are useful on their own. Running only the unit tests is already a
meaningful quality check — it exercises all command-building logic, file I/O,
fstab/unit-file formatting, config parsing, and CLI option wiring without
requiring any network access or credentials.

---

## Unit tests

### Prerequisites

- Python 3.14+
- [PDM](https://pdm-project.org) (`pip install pdm`)

### Run

```bash
./run_tests.sh
```

The script finds a Python 3.14+ interpreter, creates a PDM virtualenv, installs
test dependencies, and runs pytest. Any extra flags are forwarded to pytest:

```bash
./run_tests.sh -v                        # verbose
./run_tests.sh -k test_config_editor     # run one module
./run_tests.sh --tb=long                 # long tracebacks
```

### What is tested (without a storage box)

| File | Covers |
|---|---|
| `test_models.py` | `Connection`, `ConnectionList` CRUD; `parse_ls_l_output` and `convert_df_output_to_dict` against real Hetzner output captured once from the live box |
| `test_process.py` | `run_command` / `open_process` — success, failure, env injection, streaming |
| `test_config_editor.py` | fstab block insert / update / remove; idempotency; surrounding-content preservation |
| `test_key_manager.py` | Key path generation; `known_host_entry_exists`; `ssh_keygen` argument construction |
| `test_connection_manager.py` | Set / get / delete / list connections across config files |
| `test_ssh_transport.py` | SSH option flags; base-path injection; retry-on-failure; dry-run command building |
| `test_mount_sshfs.py` | fstab entry format; idempotency; `is_mounted()` |
| `test_mount_cifs.py` | Credential file creation; fstab entry; mount command |
| `test_mount_rclone.py` | Config generation; fstab entry; sync / bisync flags |
| `test_mount_systemd.py` | Unit name generation; `.mount` / `.automount` file content; `systemctl` call args; lifecycle |
| `test_mount_autofs.py` | Map entry format; `auto.master` entry; idempotency; lifecycle |
| `test_smb_cifs_secret_manager.py` | Write / read / delete; `0o600` / `0o660` permissions |
| `test_storage_box.py` | `get_mount_strategy()` dispatch for all tools and styles; facade property pass-throughs |
| `test_cli_connection.py` | `set-connection`, `list-connections`, `delete-connection` via Click test runner |
| `test_cli_mount.py` | `mount`, `mount-perm`, `unmount` (all `--mount-style` values) via Click test runner |
| `test_cli_transfer.py` | `remote-cmd`, `available-space`, `upload`, `download` via Click test runner |

All subprocess calls are mocked — no SSH connections are made.

---

## Integration tests

Integration tests connect to a real Hetzner Storage Box. They catch things the
unit tests cannot: protocol quirks, restricted-shell limitations, real `ls`
output format changes, SCP behaviour, and key-deployment edge cases.

### Tiers

Integration tests are split into two tiers by privilege level:

**Tier 1 — no root required**
Runs against the live storage box over SSH. Tests connectivity, file listing,
disk space, directory creation, SCP roundtrip, the StorageBox facade, and
systemd/autofs unit/map file generation into temporary directories.

**Tier 2 — root required**
Writes systemd unit files to `/etc/systemd/system/` and autofs map entries
to `/etc/auto.master`. Verifies that `systemctl enable/disable` and autofs
reload actually apply the configuration. These tests are automatically skipped
unless running as root.

### What is tested

**Tier 1 (storage box + no root):**
- Connectivity — `df` succeeds over the real SSH tunnel
- File listing — `ls -la` output parsed into `FileInfo` objects
- Disk space — `df` / `df -h` output fields and human-readable units
- Remote directory creation — `mkdir -p` including nested paths
- File transfer — text and binary upload + download roundtrip via SCP
- StorageBox facade — list, disk space, `run_remote_command`
- Systemd strategy — unit file content (host, key path, type) written to `tmp_path`
- Autofs strategy — map entry content, `auto.master` entry, idempotency, into `tmp_path`

**Tier 2 (root + storage box):**
- Systemd — unit files written to `/etc/systemd/system/`; `systemctl is-enabled` returns 0 after install; files removed and unit disabled after uninstall
- Autofs — map file and `auto.master` entry written to `/etc`; both cleaned up after uninstall

> **Note on Hetzner's restricted shell:** the SSH login shell on storage boxes
> does not support `echo`, `whoami`, or other general Unix commands. Only a
> limited set is available (`ls`, `df`, `mkdir`, `rm`, `touch`, `mv`, `scp`,
> `rsync`, …). The integration tests only use commands from that supported set.

### Prerequisites

- Python 3.14+ and PDM (same as unit tests)
- `sshpass` installed locally (`apt install sshpass` / `brew install hudochenkov/sshpass/sshpass`)
- A Hetzner Storage Box with **SSH access enabled** (Hetzner Robot → Storage Box → Settings)
- For Tier 2 only: root privileges on the local machine + `sshfs` and/or `autofs` installed

### Credentials

Set these before running, or place them in a `.env` file in the project root
(the script loads it automatically). All tests are **automatically skipped**
when these are absent — no test failures, no errors.

| Variable | Required | Description |
|---|---|---|
| `HSBT_TEST_HOST` | Yes | Storage box hostname, e.g. `u000001.your-storagebox.de` |
| `HSBT_TEST_USER` | Yes | SSH username, e.g. `u000001` |
| `HSBT_TEST_PASSWORD` | Yes* | Account password. Needed to deploy the test SSH key on the first run. See note below. |
| `HSBT_TEST_SSH_PORT` | No | SSH port (default: `23`) |
| `HSBT_TEST_KEY_DIR` | No | Persistent directory for the test SSH keypair. See note below. |

**Password note:** `HSBT_TEST_PASSWORD` is only used to deploy the test SSH
key via `ssh-copy-id`. Once the key is on the box it is not needed again —
unless the key directory changes. If you set `HSBT_TEST_KEY_DIR` to a stable
path the key persists between runs and the password is only used once (ever).

**Key directory note:** by default, the test SSH keypair is generated in a
temporary directory that is discarded after the test session. This means the
key must be redeployed (using the password) on every run. To avoid this, set
`HSBT_TEST_KEY_DIR` to a persistent path:

```bash
export HSBT_TEST_KEY_DIR=~/.config/hsbt/integration-test-keys
```

### .env file

Copy credentials into a `.env` file in the project root and the scripts load
it automatically:

```bash
# .env
HSBT_TEST_HOST=u000001.your-storagebox.de
HSBT_TEST_USER=u000001
HSBT_TEST_PASSWORD=yourpassword
# HSBT_TEST_KEY_DIR=~/.config/hsbt/integration-test-keys
```

`.env` is gitignored — never commit real credentials.

### Run locally (Tier 1, no root)

```bash
./run_integration_tests.sh
```

Or with credentials passed directly:

```bash
export HSBT_TEST_HOST=u000001.your-storagebox.de
export HSBT_TEST_USER=u000001
export HSBT_TEST_PASSWORD=yourpassword
./run_integration_tests.sh
```

Extra pytest flags are forwarded:

```bash
./run_integration_tests.sh -k test_upload      # single test
./run_integration_tests.sh --tb=long           # verbose tracebacks
```

### Run locally (Tier 2, root required)

Tier 2 tests write to `/etc/systemd/system/` and `/etc/`, so they need root.
`sudo` resets `PATH`, which means `pdm` is no longer found. The correct approach
is to build the venv once as your normal user, then run pytest via the venv
directly with `sudo -E` (which preserves your environment variables):

```bash
# Step 1 — build the venv once as your normal user (only needed once)
./run_tests.sh

# Step 2 — run the full integration suite (including Tier 2) as root
sudo -E ./run_integration_tests.sh

# Or target just the systemd/autofs tests:
sudo -E .venv/bin/python -m pytest \
    tests/integration/test_mount_systemd_live.py \
    tests/integration/test_mount_autofs_live.py \
    -v
```

`sudo -E` preserves your exported `HSBT_TEST_*` variables. If you are using a
`.env` file instead of exported variables, load it first:

```bash
set -a && source .env && set +a
sudo -E .venv/bin/python -m pytest tests/integration/ -v
```

The script handles the `pdm`-not-found case automatically: if `pdm` is not on
`PATH` it falls back to `.venv/bin/pytest` directly, so
`sudo -E ./run_integration_tests.sh` works without any manual steps as long as
the venv has been built at least once.

### Isolation and cleanup

Each test session creates a uniquely named working directory on the remote box
(`_hsbt_integration_test_<8-char-id>/`) and removes it at teardown. Tests
never read or write outside that directory.

Tier 2 tests install and immediately remove systemd unit files and autofs map
entries — they never actually trigger an automount.

If a session is interrupted before teardown, clean up manually:

```bash
# Remote workdir
ssh -p 23 u000001@u000001.your-storagebox.de "rm -rf _hsbt_integration_test_*"

# Tier 2 systemd leftovers (if any)
sudo systemctl disable --now mnt-_hsbt_integration_test_systemd.automount 2>/dev/null || true
sudo rm -f /etc/systemd/system/*_hsbt_integration_test*.{mount,automount}
sudo systemctl daemon-reload

# Tier 2 autofs leftovers (if any)
sudo rm -f /etc/auto.hsbt_hsbt_integration
# Remove the /- line from /etc/auto.master manually if needed
```

---

## GitHub Actions CI

The workflow file is at `.github/workflows/integration.yml`.

### Add repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**
and add:

| Secret name | Value |
|---|---|
| `HSBT_TEST_HOST` | e.g. `u000001.your-storagebox.de` |
| `HSBT_TEST_USER` | e.g. `u000001` |
| `HSBT_TEST_PASSWORD` | your account password |
| `HSBT_TEST_SSH_PORT` | `23` (optional, only if non-default) |

### Behaviour

- The workflow runs on every push to `main` that touches `hsbt/` or
  `tests/integration/`, and on manual dispatch.
- When secrets are present all Tier 1 integration tests run against the live box.
- Tier 2 tests (root required) do not run in CI — they are designed for local
  verification only.
- When secrets are absent (e.g. pull requests from forks) all integration
  tests are skipped — the job still passes.
- GitHub automatically redacts any secret value that appears in log output, so
  the password is safe even in verbose pytest output.
- The SSH keypair is cached between runs (per branch) so the password is only
  used when the cache is cold — typically once per branch lifetime.

### Triggering manually

Go to **Actions → Integration Tests → Run workflow** and click
**Run workflow**. This is useful for testing a branch that does not touch the
watched paths.

---

## Project structure

```
tests/
├── conftest.py                   # shared fixtures, real Hetzner ls/df output constants
├── test_*.py                     # 425 unit tests (no network, no root)
└── integration/
    ├── conftest.py               # live transport fixture, remote workdir setup/teardown
    ├── test_transport.py         # SshTransport tests (Tier 1)
    ├── test_storage_box.py       # StorageBox facade tests (Tier 1)
    ├── test_mount_webdav_live.py # WebDAV mount tests (Tier 1)
    ├── test_mount_systemd_live.py# systemd automount tests (Tier 1 + Tier 2)
    └── test_mount_autofs_live.py # autofs mount tests (Tier 1 + Tier 2)

run_tests.sh                      # unit tests — no credentials or root needed
run_integration_tests.sh          # integration tests — credentials required; root optional
.github/workflows/
└── integration.yml               # CI workflow (Tier 1 only)
```
