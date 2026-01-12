# GitSidecar

<p align="center">
  <img alt="GitSidecar logo" src="LogoC.png" width="180" />
</p>


**Automatically manage working directories for your git ticket branches**

Sidecar is a command-line tool that automatically creates and manages dedicated working directories whenever you checkout a ticket branch in git. It eliminates the hassle of manually organizing files, documentation, notebooks, and scripts for each ticket you work on.

## 🎯 Target Users

This tool is perfect for:

- **Software Developers** working with issue tracking systems (JIRA, GitHub Issues, Linear, etc.)
- **DevOps Engineers** managing multiple tickets and their associated resources
- **Technical Writers** organizing documentation per feature/ticket
- **QA Engineers** maintaining test files and results for different tickets
- **Anyone** who works with git branches following a ticket naming convention (e.g., `JIRA-123`, `TICKET-456-feature-name`)

## 💡 Use Cases

### Use Case 1: Organized Ticket Workflow
**Problem**: You're working on ticket `JIRA-789` and need to:
- Store temporary & working files
- Keep test notebooks
- Save debugging logs
- Reference previous similar tickets

**Solution**: Sidecar automatically creates `~/tickets/JIRA-789-feature-name/` when you checkout the branch, giving you a dedicated space for everything related to this ticket.

### Use Case 2: Quick Access from Anywhere
**Problem**: You want quick access to your current ticket's directory from your Downloads folder or desktop.

**Solution**: Sidecar creates a `CurrentTicket` symlink in configured locations (e.g., `~/Downloads/CurrentTicket`), so you can always quickly navigate to your active ticket directory.

### Use Case 3: Shared Tools Library
**Problem**: You have utility scripts, notebooks, and helper tools you use across all tickets, but copying them manually is tedious.

**Solution**: Sidecar automatically symlinks your tools library (e.g., `notebooks/`, `scripts/`, `utils/`) into every ticket directory, so they're always available without duplication.

### Use Case 4: Consistent Ticket Organization
**Problem**: When switching between multiple tickets, you forget where you saved files or lose track of ticket-specific resources.

**Solution**: Sidecar ensures every ticket branch gets its own directory automatically, maintaining consistent organization across your entire workflow.

### Use Case 5: Multiple Projects, Different Workflows
**Problem**: You work on multiple projects with different ticket systems, naming conventions, or workspace requirements. You need different configurations for each project.

**Solution**: Sidecar supports multi-repository configuration with per-repo settings that inherit from defaults. Each repository can have its own ticket patterns, workspace location, and symlink names while sharing common defaults.

## ✨ Key Features

### 🚀 Automatic Directory Creation
- **Hooks into git checkout**: Automatically triggers when you checkout a branch
- **Smart branch detection**: Recognizes ticket branches based on configurable patterns (e.g., `JIRA-123`, `TICKET-456-feature`)
- **Reuses existing directories**: If you've worked on a ticket before, it finds and reuses the existing directory
- **Cross-platform support**: Works on Linux, macOS, and Windows

### 📁 Intelligent Directory Management
- **Sanitized directory names**: Creates OS-safe directory names from branch names
- **Prefix matching**: Finds existing directories even if the description changed (e.g., `JIRA-123-old-desc` → `JIRA-123-new-desc`)
- **Standard branch handling**: Ignores standard branches like `main`, `master`, `develop`

### 🔗 Automatic Tool Linking
- **Symlink tools library**: Automatically links your common tools (notebooks, scripts, utilities) into each ticket directory
- **No duplication**: Uses symlinks, so tools stay in one place but are accessible everywhere
- **Configurable**: Specify which tools to link in your configuration

### 📍 Current Ticket Tracking
- **Multiple symlink locations**: Creates symlinks in multiple configured locations (e.g., `~/Downloads`, `~/Desktop`)
- **Configurable symlink names**: Customize the symlink filename per repository (default: "CurrentTicket")
- **Always up-to-date**: Automatically updates when you checkout a different ticket branch
- **Quick access**: Navigate to your active ticket from anywhere

### ⚙️ Highly Configurable
- **Customizable patterns**: Configure ticket branch naming patterns to match your team's conventions
- **Flexible paths**: Set your workspace base directory and tools library location
- **Standard branches**: Define which branches to ignore (main, master, etc.)
- **Multi-repository support**: Configure different settings per repository with hierarchical inheritance
- **Per-repo workspace isolation**: Each repository gets its own workspace directory (`~/tickets/<repo>/<ticket>`)
- **Configurable symlink names**: Customize the symlink filename per repository (default: "CurrentTicket")

## 📋 Prerequisites

- Python 3.8 or higher
- Git installed and configured
- A git repository (for using the hook functionality)
- `pipx` or `uv` (with `uv tool install`) for installation (recommended)

## 🚀 Installation

### Recommended: Install via pipx or uv tool

Install from GitHub repository:

**Using pipx:**
```bash
pipx install git+https://github.com/marian-vignau/git-sidecar.git
```

**Using uv tool (from uv - for permanent installation):**
```bash
uv tool install git+https://github.com/marian-vignau/git-sidecar.git
```

After installation, the `sidecar` command will be available globally.

**Note:** `uvx sidecar@git+...` runs the command once in an ephemeral environment but does not permanently install it. Use `uv tool install` for permanent installation (equivalent to `pipx install`).

### Alternative: Manual Installation

1. **Clone or download this repository**:
   ```bash
   git clone <repository-url>
   cd GitSidecar
   ```

2. **Install locally** (optional, for development):
   ```bash
   pip install -e .
   ```

3. **Or run directly** (without installation):
   ```bash
   python3 main.py hook install
   ```

## 📖 Usage

### Basic Workflow

1. **Configure Sidecar defaults** (optional - uses sensible defaults):
   ```bash
   # View current configuration
   sidecar config --view

   # Set default workspace base directory
   sidecar config --set paths workspace_base ~/tickets --default

   # Set default tools library path
   sidecar config --set paths tools_library_path ~/tools --default

   # Configure default link locations (comma-separated)
   sidecar config --set links current_ticket_link_locations ~/Downloads,~/Desktop --default

   # Set default symlink filename (optional)
   sidecar config --set links current_ticket_link_filename CurrentTicket --default
   ```

2. **Set up repository configuration** (automatic during hook install):
   ```bash
   # Install git hook - this will prompt to configure the repository
   sidecar hook install
   # Or manually initialize repo configuration:
   sidecar config --init-repo
   ```

3. **Work with your tickets normally**:
   ```bash
   git checkout JIRA-123-implement-feature
   # Sidecar automatically:
   # - Creates ~/tickets/<repo-name>/JIRA-123-implement-feature/
   # - Links your tools library into it
   # - Creates symlinks with configured filename in configured locations
   ```

4. **List all ticket directories**:
   ```bash
   sidecar list
   ```

### Commands

All commands use the `sidecar` command (or `python3 main.py` if running directly).

#### Install Git Hook
```bash
sidecar hook install
```
Installs a post-checkout hook that automatically processes branches when you checkout.

When installing a hook in a repository for the first time, Sidecar will:
- Detect the repository identifier (from git remote or directory)
- Prompt to configure repository-specific settings (optional)
- Auto-configure with defaults if you skip the prompt
- Set up repository-specific workspace directory

The hook installation is interactive, so repository configuration happens during setup, not during checkout operations.

#### Uninstall Git Hook
```bash
sidecar hook uninstall
```
Removes the Sidecar post-checkout hook.

#### Process Current Checkout (Manual)
```bash
sidecar process
```
Manually process the current git branch (useful for testing or if you prefer not to use hooks).

#### View Configuration
```bash
sidecar config --view                    # Show default + current repo config
sidecar config --view --default-only     # Show only default configuration
sidecar config --view --all              # Show all repository configurations
sidecar config --view --repo <repo-id>   # Show default + specific repo config
```
Display current configuration settings with repository context awareness.

#### Set Configuration
```bash
sidecar config --set <section> <key> <value>              # Set for current repo (or default if not in repo)
sidecar config --set <section> <key> <value> --default    # Explicitly set default configuration
sidecar config --set <section> <key> <value> --repo <id>  # Set for specific repository
```
Update a configuration value. Examples:
```bash
# Set default workspace base (affects all repos unless overridden)
sidecar config --set paths workspace_base ~/tickets --default

# Set workspace base for current repository
sidecar config --set paths workspace_base ~/tickets/project-a

# Set workspace base for specific repository
sidecar config --set paths workspace_base ~/tickets/project-b --repo github.com/owner/project-b
```

#### Initialize Repository Configuration
```bash
sidecar config --init-repo
```
Interactively set up configuration for the current repository without installing a hook. Useful for configuring repositories before installing hooks or updating existing configurations.

#### List Configured Repositories
```bash
sidecar config --list-repos
```
List all repositories that have specific configuration sections.

#### Manage Repository Configurations
```bash
sidecar repos list                    # List all configured repositories
sidecar repos show <repo-id>          # Show configuration for a specific repository
sidecar repos remove <repo-id>        # Remove configuration for a repository
```
Manage repository-specific configurations.

#### List Ticket Directories
```bash
sidecar list
```
List all existing ticket directories in your workspace for the current repository.

## 🔀 Multi-Repository Management

Sidecar supports managing multiple repositories, each with its own configuration that inherits from defaults.

### Getting Started with Multiple Repositories

1. **Set up default configuration** (optional):
   ```bash
   sidecar config --set paths workspace_base ~/tickets --default
   sidecar config --set links current_ticket_link_filename CurrentTicket --default
   ```

2. **Configure each repository** (automatic during hook install):
   ```bash
   cd ~/projects/project-a
   sidecar hook install  # Prompts for repository-specific settings
   
   cd ~/projects/project-b
   sidecar hook install  # Configures this repository separately
   ```

3. **Work normally** - Sidecar automatically uses the correct configuration for each repository.

### Repository Configuration Examples

**Example 1: Different ticket patterns per project**
```bash
# Project A uses JIRA tickets (default)
sidecar hook install  # Uses default pattern

# Project B uses custom ticket format
cd ~/projects/project-b
sidecar hook install
# When prompted, override ticket pattern:
sidecar config --set ticket_pattern prefix_pattern [A-Z]{2,5} --repo github.com/owner/project-b
```

**Example 2: Different workspace locations**
```bash
# Project A goes to ~/tickets/project-a (auto-configured)
sidecar hook install

# Project B goes to custom location
cd ~/projects/project-b
sidecar config --set paths workspace_base ~/work/project-b-tickets --repo github.com/owner/project-b
```

**Example 3: Different symlink names**
```bash
# Project A uses default "CurrentTicket"
sidecar hook install

# Project B uses "ActiveWork"
cd ~/projects/project-b
sidecar config --set links current_ticket_link_filename ActiveWork --repo github.com/owner/project-b
```

### Managing Repository Configurations

**View all configured repositories:**
```bash
sidecar repos list
```

**View specific repository configuration:**
```bash
sidecar repos show github.com/owner/project-a
```

**Remove repository configuration (falls back to defaults):**
```bash
sidecar repos remove github.com/owner/project-a
```

**Update repository configuration:**
```bash
# Reconfigure interactively
sidecar config --init-repo

# Or set specific values
sidecar config --set paths workspace_base ~/new-location --repo github.com/owner/project-a
```

### Repository Identification

Sidecar automatically identifies repositories using:
- **Git remote URL**: For repositories with remotes (e.g., `github.com/owner/repo`)
- **Directory name + hash**: For local repositories without remotes (e.g., `local/project-name-abc123`)

Repository identifiers are normalized consistently:
- `https://github.com/owner/repo.git` → `github.com/owner/repo`
- `git@github.com:owner/repo.git` → `github.com/owner/repo`
- Local repo without remote → `local/<directory>-<hash>`

## ⚙️ Configuration

Configuration is stored in `~/.sidecar/config.ini` using a hierarchical structure that supports multi-repository settings with inheritance.

### Configuration Structure

The configuration uses hierarchical sections:
- **`[default.*]`**: Default configuration used by all repositories unless overridden
- **`[repo:<repo-id>]`**: Repository-specific overrides using dot notation for logical grouping

### Default Configuration

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
```

### Repository-Specific Configuration

```ini
[repo:github.com/owner/project-a]
paths.workspace_base = ~/tickets/project-a
ticket_pattern.prefix_pattern = [A-Z]{2,5}

[repo:github.com/owner/project-b]
paths.workspace_base = ~/tickets/project-b
links.current_ticket_link_filename = CurrentProjectBTicket
```

Repository sections inherit all settings from `[default.*]` sections. Only override values that differ from defaults.

### Configuration Resolution

Configuration values are resolved in this order:
1. **Repository-specific** (`[repo:<id>]` section with dot notation keys like `paths.workspace_base`)
2. **Default** (`[default.<section>]` sections)
3. **Hardcoded fallback** (if neither exists)

### Configuration Sections

- **`[default.paths]`** / **`paths.*` in repo sections**: Base directories for workspaces and tools
- **`[default.branches]`** / **`branches.*` in repo sections**: Standard branches to ignore (comma-separated)
- **`[default.ticket_pattern]`** / **`ticket_pattern.*` in repo sections**: Regex patterns for matching ticket branches
- **`[default.links]`** / **`links.*` in repo sections**: Symlink locations, symlink filename, and tools to link

### Repository Identification

Sidecar identifies repositories using:
- **Git remote URL**: Normalized format like `github.com/owner/repo` (from `origin` remote, or first available remote)
- **Local repositories**: Format `local/<directory-name>-<hash>` for repos without remotes

Repository identifiers are automatically detected from git remotes and normalized consistently across different URL formats (HTTPS, SSH, etc.).

### Customizing Ticket Patterns

The default pattern matches branches like:
- `JIRA-123-description`
- `TICKET_456_feature_name`
- `ABC-789`

To customize defaults (affects all repos):
```bash
# Example: Match only uppercase prefixes with 2-5 chars
sidecar config --set ticket_pattern prefix_pattern [A-Z]{2,5} --default

# Example: Only allow hyphens as separators
sidecar config --set ticket_pattern separator - --default
```

To customize for a specific repository:
```bash
# Set pattern for current repository
sidecar config --set ticket_pattern prefix_pattern [A-Z]{2,5}

# Set pattern for specific repository
sidecar config --set ticket_pattern prefix_pattern [A-Z]{2,5} --repo github.com/owner/project-a
```

### Customizing Symlink Filename

By default, Sidecar creates symlinks named "CurrentTicket". You can customize this per repository:

```bash
# Set default symlink filename
sidecar config --set links current_ticket_link_filename CurrentTicket --default

# Set custom symlink filename for a repository
sidecar config --set links current_ticket_link_filename ActiveWork --repo github.com/owner/project-a
```

## 📁 Directory Structure Example

### Single Repository (Legacy Structure)
After checking out `JIRA-789-implement-authentication` in a repository without repo-specific configuration:

```
~/tickets/
└── JIRA-789-implement-authentication/
    ├── notebooks/          # Symlinked from tools library
    ├── scripts/            # Symlinked from tools library
    └── utils/              # Symlinked from tools library

~/Downloads/
└── CurrentTicket -> ~/tickets/JIRA-789-implement-authentication
```

### Multi-Repository Structure (Recommended)
After checking out `JIRA-789-implement-authentication` in a configured repository:

```
~/tickets/
├── project-a/                          # Repository-specific workspace
│   └── JIRA-789-implement-authentication/
│       ├── notebooks/                  # Symlinked from tools library
│       ├── scripts/                    # Symlinked from tools library
│       └── utils/                      # Symlinked from tools library
└── project-b/                          # Another repository's workspace
    └── TICKET-456-feature-name/
        ├── notebooks/
        ├── scripts/
        └── utils/

~/Downloads/
└── CurrentTicket -> ~/tickets/project-a/JIRA-789-implement-authentication
```

Each repository gets its own workspace subdirectory, keeping tickets organized by project.

## 🔍 How It Works

1. **Repository Detection**: Sidecar detects the current repository identifier from git remotes or directory path
2. **Configuration Resolution**: Resolves configuration using repository-specific settings (if configured) or defaults
3. **Branch Detection**: Analyzes the branch name when you checkout
4. **Pattern Matching**: Checks if the branch matches your configured ticket pattern (repo-specific or default)
5. **Directory Creation**: Creates (or finds existing) ticket directory in the repository-specific workspace (`~/tickets/<repo>/<ticket>`)
6. **Tool Linking**: Symlinks configured tools from your tools library
7. **Current Ticket Links**: Updates symlinks with configured filename in all configured locations

### Multi-Repository Workflow

When working with multiple repositories:

1. **First-time setup**: Run `sidecar hook install` in each repository. Sidecar will prompt to configure repository-specific settings.
2. **Configuration inheritance**: Each repository inherits from default settings, only requiring overrides for differences.
3. **Automatic workspace isolation**: Each repository's tickets are stored in `~/tickets/<repo-name>/`, preventing conflicts.
4. **Checkout processing**: When checking out a branch, Sidecar uses the repository's configuration automatically (no prompts, safe for non-interactive environments).

### Hook Installation Process

During `sidecar hook install`:
- Repository identifier is detected automatically
- If repository is not configured, interactive setup is offered
- Repository-specific workspace is configured (e.g., `~/tickets/<repo-name>`)
- Configuration is saved before hook installation proceeds
- Subsequent checkouts use saved configuration (no prompts)

This ensures checkout operations never require user interaction, making it safe for scripts and CI environments.

## 🛠️ Troubleshooting

### Hook Not Running
- Verify the hook is installed: Check `.git/hooks/post-checkout` exists
- Ensure the hook is executable: `chmod +x .git/hooks/post-checkout`
- Check hook content contains `sidecar`

### Directory Not Created
- Verify you're in a git repository: `git rev-parse --git-dir`
- Check branch name matches your ticket pattern: `sidecar config --view`
- Verify repository is configured: `sidecar repos show <repo-id>` or `sidecar config --view`
- Check repository workspace directory exists and is writable
- Try manual processing: `sidecar process`

### Repository Not Detected
- Verify git remote is configured: `git remote -v`
- Check repository identifier: Sidecar uses normalized remote URLs or local directory names
- For local repositories without remotes, Sidecar uses `local/<directory-name>-<hash>` format

### Configuration Issues
- View current repository configuration: `sidecar config --view`
- List all configured repositories: `sidecar repos list`
- Check if repository is using defaults or has specific config: `sidecar repos show <repo-id>`
- Reconfigure repository: `sidecar config --init-repo` or reinstall hook with `--reconfigure`

### Wrong Workspace Directory
- Check repository-specific workspace: Look in `~/tickets/<repo-name>/` for ticket directories
- Verify repository configuration: `sidecar config --view --repo <repo-id>`
- Default workspace structure changed to `~/tickets/<repo-name>/<ticket>` for repository isolation

### Symlink Errors (Windows)
- Ensure you have administrator privileges or Developer Mode enabled
- Check that your filesystem supports symlinks (NTFS supports them)

### Tools Not Linking
- Verify tools library path exists: Check `tools_library_path` in config (default or repo-specific)
- Ensure tool items exist: Check that `notebooks/`, `scripts/`, etc. exist in your tools library
- Check tool names match: Tool names in `tools_to_link` must match directory names
- Verify repository-specific configuration if tools library path differs per repo

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone <your-fork-url>
   cd GitSidecar
   ```

2. **Run tests locally before submitting**:
   ```bash
   python3 -m unittest test_sidecar.py -v
   ```
   All tests must pass before submitting a Pull Request.

### Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and ensure tests pass locally

3. **Submit a Pull Request** targeting the `main` branch

4. **CI Requirements**: 
   - All automated tests must pass (runs on Python 3.8-3.12)
   - Code quality checks must pass
   - PR must be approved before merging

### Branch Protection

The `main` branch is protected. Direct commits to `main` are not allowed. All changes must go through Pull Requests that:
- Pass all CI tests
- Receive required approvals
- Have no merge conflicts

**Note**: Repository administrators should configure branch protection rules in GitHub Settings → Branches → Add rule for `main` branch:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging (check `test`)
- ✅ Require branches to be up to date before merging
- ✅ Include administrators

## 📝 License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

Built for developers who value organized, automated workflows and hate manual directory management.
