# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run unit tests
```bash
python3 -m unittest tests/test_sidecar.py -v
```

### Run a single test class or method
```bash
python3 -m unittest tests/test_sidecar.py::TestConfigManager -v
python3 -m unittest tests/test_sidecar.py::TestConfigManager::test_default_config_creation -v
```

### Syntax / import check (mirrors CI lint job)
```bash
python3 -m py_compile main.py tests/test_sidecar.py
python3 -c "import main"
```

### Build package
```bash
python3 -m pip install build
python3 -m build
```

### Run E2E tests (Docker)
```bash
# From tests/ directory (docker-compose.yml lives there)
cd tests && docker-compose up --build
```

### Run directly without installation
```bash
python3 main.py --help
python3 main.py config --view
```

## Architecture

The entire tool lives in a single module: `main.py`. There are no sub-packages. The test file is `tests/test_sidecar.py` and imports `main` directly.

### Class responsibilities in `main.py`

| Class | Responsibility |
|---|---|
| `RepoIdentifier` | Finds `.git` directory, reads remotes via `git` subprocess, normalises remote URLs to `host/owner/repo` form (handles HTTPS and SSH). Falls back to `local/<dir>-<hash>` for repos without remotes. |
| `ConfigManager` | Reads/writes `~/.sidecar/config.ini`. Hierarchical structure: `[default.<section>]` holds global defaults; `[repo:<repo-id>]` holds per-repo overrides stored as dotted keys (`paths.workspace_base`). Resolution order: repo-specific → default → hardcoded fallback. |
| `BranchAnalyzer` | Uses regex from config to decide whether a branch name is a ticket branch or a standard branch (main, master, etc.). |
| `DirectoryManager` | Creates ticket directories under `<workspace_base>/<ticket-name>/`. Reuses existing directories by prefix-matching on ticket number. Sanitises branch names to OS-safe directory names. |
| `ToolsLinker` | Symlinks named subdirectories from `tools_library_path` into each ticket directory. |
| `CurrentTicketLinker` | Creates/updates a named symlink (default: `CurrentTicket`) in each configured location pointing to the active ticket directory. |
| `GitHookManager` | Installs/uninstalls the `post-checkout` hook in `.git/hooks/`. The hook calls `sidecar process`. |
| `TicketManager` | Orchestrates the full checkout flow: detect repo, resolve config, analyse branch, create directory, link tools, update symlinks. |

### Configuration file format (`~/.sidecar/config.ini`)

```ini
[default.paths]
workspace_base = ~/tickets
tools_library_path = ~/tools

[default.branches]
standard_branches = main, master, develop, stage, production

[default.ticket_pattern]
prefix_pattern = [A-Za-z]{1,10}
separator = [-_]
number_pattern = \d+
description_pattern = .*

[default.links]
current_ticket_link_locations = ~/Downloads
current_ticket_link_filename = CurrentTicket
tools_to_link = notebooks, scripts, utils

[repo:github.com/owner/project]
paths.workspace_base = ~/tickets/project
links.current_ticket_link_filename = ActiveWork
```

### Entry point

`pyproject.toml` maps the `sidecar` CLI command to `main:main`. The `main()` function builds an `argparse` parser with subcommands: `hook`, `process`, `config`, `repos`, `list`.

### Testing approach

Unit tests use `tempfile.mkdtemp()` for isolated config directories and `unittest.mock.patch` to mock filesystem and subprocess calls. No third-party test dependencies — only the standard library. E2E tests are shell scripts run inside Docker (`tests/test-e2e.sh`, `tests/entrypoint.sh`).

### CI

Three jobs run on Python 3.8–3.12 (matrix): `test` (unittest), `lint` (py_compile + import check), `package` (build wheel + verify `sidecar` entry point).
