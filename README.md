# DirTickets

**Automatically manage working directories for your git ticket branches**

DirTickets is a command-line tool that automatically creates and manages dedicated working directories whenever you checkout a ticket branch in git. It eliminates the hassle of manually organizing files, documentation, notebooks, and scripts for each ticket you work on.

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

**Solution**: DirTickets automatically creates `~/tickets/JIRA-789-feature-name/` when you checkout the branch, giving you a dedicated space for everything related to this ticket.

### Use Case 2: Quick Access from Anywhere
**Problem**: You want quick access to your current ticket's directory from your Downloads folder or desktop.

**Solution**: DirTickets creates a `CurrentTicket` symlink in configured locations (e.g., `~/Downloads/CurrentTicket`), so you can always quickly navigate to your active ticket directory.

### Use Case 3: Shared Tools Library
**Problem**: You have utility scripts, notebooks, and helper tools you use across all tickets, but copying them manually is tedious.

**Solution**: DirTickets automatically symlinks your tools library (e.g., `notebooks/`, `scripts/`, `utils/`) into every ticket directory, so they're always available without duplication.

### Use Case 4: Consistent Ticket Organization
**Problem**: When switching between multiple tickets, you forget where you saved files or lose track of ticket-specific resources.

**Solution**: DirTickets ensures every ticket branch gets its own directory automatically, maintaining consistent organization across your entire workflow.

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
- **Multiple symlink locations**: Creates `CurrentTicket` symlinks in multiple configured locations (e.g., `~/Downloads`, `~/Desktop`)
- **Always up-to-date**: Automatically updates when you checkout a different ticket branch
- **Quick access**: Navigate to your active ticket from anywhere

### ⚙️ Highly Configurable
- **Customizable patterns**: Configure ticket branch naming patterns to match your team's conventions
- **Flexible paths**: Set your workspace base directory and tools library location
- **Standard branches**: Define which branches to ignore (main, master, etc.)

## 📋 Prerequisites

- Python 3.7 or higher
- Git installed and configured
- A git repository (for using the hook functionality)

## 🚀 Installation

1. **Clone or download this repository**:
   ```bash
   git clone <repository-url>
   cd DirTickets
   ```

2. **Make the script executable** (if needed):
   ```bash
   chmod +x main.py
   ```

3. **Install the git hook** in your repository:
   ```bash
   python3 main.py hook install
   ```

   Or install it from any git repository:
   ```bash
   cd /path/to/your/git/repo
   python3 /path/to/DirTickets/main.py hook install
   ```

## 📖 Usage

### Basic Workflow

1. **Configure DirTickets** (optional - uses sensible defaults):
   ```bash
   # View current configuration
   python3 main.py config --view

   # Set workspace base directory
   python3 main.py config --set paths workspace_base ~/tickets

   # Set tools library path
   python3 main.py config --set paths tools_library_path ~/tools

   # Configure link locations (comma-separated)
   python3 main.py config --set links current_ticket_link_locations ~/Downloads,~/Desktop

   # Install git hook 
   python3 main.py hook install
   ```

2. **Work with your tickets normally**:
   ```bash
   git checkout JIRA-123-implement-feature
   # DirTickets automatically:
   # - Creates ~/tickets/JIRA-123-implement-feature/
   # - Links your tools library into it
   # - Creates CurrentTicket symlinks in configured locations
   ```

3. **List all ticket directories**:
   ```bash
   python3 main.py list
   ```

### Commands

#### Install Git Hook
```bash
python3 main.py hook install
```
Installs a post-checkout hook that automatically processes branches when you checkout.

#### Uninstall Git Hook
```bash
python3 main.py hook uninstall
```
Removes the DirTickets post-checkout hook.

#### Process Current Checkout (Manual)
```bash
python3 main.py process
```
Manually process the current git branch (useful for testing or if you prefer not to use hooks).

#### View Configuration
```bash
python3 main.py config --view
```
Display current configuration settings.

#### Set Configuration
```bash
python3 main.py config --set <section> <key> <value>
```
Update a configuration value. Example:
```bash
python3 main.py config --set paths workspace_base ~/my-tickets
```

#### List Ticket Directories
```bash
python3 main.py list
```
List all existing ticket directories in your workspace.

## ⚙️ Configuration

Configuration is stored in `~/.dirtickets/config.ini`. The default configuration includes:

```ini
[paths]
workspace_base = ~/tickets
tools_library_path = ~/tools

[branches]
standard_branches = main, master, develop, stage, production

[ticket_pattern]
prefix_pattern = [A-Za-z]{1,10}
separator = [-_]
number_pattern = \d+
description_pattern = .*

[links]
current_ticket_link_locations = ~/Downloads
tools_to_link = notebooks, scripts, utils
```

### Configuration Sections

- **`[paths]`**: Base directories for workspaces and tools
- **`[branches]`**: Standard branches to ignore (comma-separated)
- **`[ticket_pattern]`**: Regex patterns for matching ticket branches
- **`[links]`**: Symlink locations and tools to link

### Customizing Ticket Patterns

The default pattern matches branches like:
- `JIRA-123-description`
- `TICKET_456_feature_name`
- `ABC-789`

To customize, adjust the pattern components:
```bash
# Example: Match only uppercase prefixes with 2-5 chars
python3 main.py config --set ticket_pattern prefix_pattern [A-Z]{2,5}

# Example: Only allow hyphens as separators
python3 main.py config --set ticket_pattern separator -
```

## 📁 Directory Structure Example

After checking out `JIRA-789-implement-authentication`:

```
~/tickets/
└── JIRA-789-implement-authentication/
    ├── notebooks/          # Symlinked from tools library
    ├── scripts/            # Symlinked from tools library
    └── utils/              # Symlinked from tools library

~/Downloads/
└── CurrentTicket -> ~/tickets/JIRA-789-implement-authentication
```

## 🔍 How It Works

1. **Branch Detection**: When you checkout a branch, DirTickets analyzes the branch name
2. **Pattern Matching**: Checks if the branch matches your configured ticket pattern
3. **Directory Creation**: Creates (or finds existing) ticket directory with sanitized name
4. **Tool Linking**: Symlinks configured tools from your tools library
5. **Current Ticket Links**: Updates `CurrentTicket` symlinks in all configured locations

## 🛠️ Troubleshooting

### Hook Not Running
- Verify the hook is installed: Check `.git/hooks/post-checkout` exists
- Ensure the hook is executable: `chmod +x .git/hooks/post-checkout`
- Check hook content contains `DirTickets`

### Directory Not Created
- Verify you're in a git repository: `git rev-parse --git-dir`
- Check branch name matches your ticket pattern: `python3 main.py config --view`
- Try manual processing: `python3 main.py process`

### Symlink Errors (Windows)
- Ensure you have administrator privileges or Developer Mode enabled
- Check that your filesystem supports symlinks (NTFS supports them)

### Tools Not Linking
- Verify tools library path exists: Check `tools_library_path` in config
- Ensure tool items exist: Check that `notebooks/`, `scripts/`, etc. exist in your tools library
- Check tool names match: Tool names in `tools_to_link` must match directory names

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

[Add your license here]

## 🙏 Acknowledgments

Built for developers who value organized, automated workflows and hate manual directory management.
