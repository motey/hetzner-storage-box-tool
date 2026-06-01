# Testing

The test suite is split into two independent layers:

| Layer | Tests | Needs storage box | Time |
|---|---|---|---|
| **Unit tests** | 247 | No | ~0.5 s |
| **Integration tests** | 24 | Yes | ~25 s |

Both layers are useful on their own. Running only the unit tests is already a
meaningful quality check — it exercises all command-building logic, file I/O,
fstab formatting, config parsing, and CLI option wiring without requiring any
network access or credentials.

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
| `test_smb_cifs_secret_manager.py` | Write / read / delete; `0o600` / `0o660` permissions |
| `test_storage_box.py` | `get_mount_strategy()` dispatch; facade property pass-throughs |
| `test_cli_connection.py` | `set-connection`, `list-connections`, `delete-connection` via Click test runner |
| `test_cli_mount.py` | `mount`, `mount-perm`, `unmount` via Click test runner |
| `test_cli_transfer.py` | `remote-cmd`, `available-space`, `upload`, `download` via Click test runner |

All subprocess calls are mocked — no SSH connections are made.

---

## Integration tests

Integration tests connect to a real Hetzner Storage Box. They catch things the
unit tests cannot: protocol quirks, restricted-shell limitations, real `ls`
output format changes, SCP behaviour, and key-deployment edge cases.

### What is tested

- **Connectivity** — `df` succeeds over the real SSH tunnel
- **File listing** — `ls -la` output parsed into `FileInfo` objects
- **Disk space** — `df` / `df -h` output fields and human-readable units
- **Remote directory creation** — `mkdir -p` including nested paths
- **File transfer** — text and binary upload + download roundtrip via SCP
- **StorageBox facade** — list, disk space, and `run_remote_command` through the high-level API
- **Mount strategy dispatch** — correct strategy type returned for each tool (no actual mounting)

> **Note on Hetzner's restricted shell:** the SSH login shell on storage boxes
> does not support `echo`, `whoami`, or other general Unix commands. Only a
> limited set is available (`ls`, `df`, `mkdir`, `rm`, `touch`, `mv`, `scp`,
> `rsync`, …). The integration tests only use commands from that supported set.

### Prerequisites

- Python 3.14+ and PDM (same as unit tests)
- `sshpass` installed locally (`apt install sshpass` / `brew install hudochenkov/sshpass/sshpass`)
- A Hetzner Storage Box with **SSH access enabled** (Hetzner Robot → Storage Box → Settings)

### Environment variables

Set these before running. All tests are **automatically skipped** when they
are absent — no test failures, no errors.

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

The directory is created automatically if it does not exist. After the first
run the key is already on the box and subsequent runs do not need the password
(though leaving it set is harmless).

### Run locally

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

### Isolation and cleanup

Each test session creates a uniquely named working directory on the remote box
(`_hsbt_integration_test_<8-char-id>/`) and removes it at teardown. Tests
never read or write outside that directory.

If a session is interrupted before teardown, clean up manually:

```bash
ssh -p 23 u000001@u000001.your-storagebox.de "rm -rf _hsbt_integration_test_*"
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
- When secrets are present all 24 integration tests run against the live box.
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
├── conftest.py            # shared fixtures, real Hetzner ls/df output constants
├── test_*.py              # 247 unit tests (no network)
└── integration/
    ├── conftest.py        # live transport fixture, remote workdir setup/teardown
    ├── test_transport.py  # 15 real SshTransport tests
    └── test_storage_box.py # 9 real StorageBox tests

run_tests.sh               # unit tests — no credentials needed
run_integration_tests.sh   # integration tests — credentials required
.github/workflows/
└── integration.yml        # CI workflow for integration tests
```
