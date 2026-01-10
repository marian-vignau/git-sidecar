#!/usr/bin/env python3
"""
GitSidecar - A tool to automatically manage ticket working directories.
Hooks into git checkout to create and link ticket directories.
"""

import argparse
import configparser
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ConfigManager:
    """Manages configuration file using configparser."""
    
    DEFAULT_CONFIG_DIR = Path.home() / ".sidecar"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.ini"
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()
    
    def _ensure_config_exists(self):
        """Create config directory and default config file if they don't exist."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.config_file.exists():
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration file."""
        self.config['paths'] = {
            'workspace_base': '~/tickets',
            'tools_library_path': '~/tools'
        }
        
        self.config['branches'] = {
            'standard_branches': 'main, master, develop, stage, production'
        }
        
        self.config['ticket_pattern'] = {
            'prefix_pattern': '[A-Za-z]{1,10}',
            'separator': '[-_]',
            'number_pattern': r'\d+',
            'description_pattern': '.*'
        }
        
        self.config['links'] = {
            'current_ticket_link_locations': '~/Downloads',
            'tools_to_link': 'notebooks, scripts, utils'
        }
        
        self._save_config()
    
    def _load_config(self):
        """Load configuration from file."""
        self.config.read(self.config_file)
    
    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section: str, key: str, fallback: Optional[str] = None) -> str:
        """Get a configuration value."""
        return self.config.get(section, key, fallback=fallback)
    
    def get_path(self, section: str, key: str, fallback: Optional[str] = None) -> Path:
        """Get a path configuration value, expanding ~ and returning Path object."""
        value = self.get(section, key, fallback)
        if value:
            expanded = os.path.expanduser(value)
            return Path(expanded)
        return Path(fallback) if fallback else Path.home()
    
    def get_list(self, section: str, key: str, fallback: Optional[List[str]] = None) -> List[str]:
        """Get a comma-separated list from configuration."""
        value = self.get(section, key)
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return fallback or []
    
    def set(self, section: str, key: str, value: str):
        """Set a configuration value."""
        if section not in self.config:
            self.config.add_section(section)
        self.config.set(section, key, value)
        self._save_config()
        self._load_config()
    
    def view(self) -> str:
        """Return configuration as formatted string."""
        result = []
        for section in self.config.sections():
            result.append(f"[{section}]")
            for key, value in self.config.items(section):
                result.append(f"{key} = {value}")
            result.append("")
        return "\n".join(result)


class BranchAnalyzer:
    """Analyzes git branch names to extract ticket information."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.standard_branches = config.get_list('branches', 'standard_branches')
        
        # Build regex pattern from config
        prefix_pattern = config.get('ticket_pattern', 'prefix_pattern')
        separator = config.get('ticket_pattern', 'separator')
        number_pattern = config.get('ticket_pattern', 'number_pattern')
        description_pattern = config.get('ticket_pattern', 'description_pattern')
        
        # Escape separator for regex (except for character class)
        if separator.startswith('[') and separator.endswith(']'):
            sep_pattern = separator
        else:
            sep_pattern = re.escape(separator)
        
        self.pattern = re.compile(
            rf"^({prefix_pattern})({sep_pattern})({number_pattern})({sep_pattern})({description_pattern})$"
        )
    
    def is_standard_branch(self, branch_name: str) -> bool:
        """Check if branch is a standard branch (main, master, etc.)."""
        return branch_name in self.standard_branches
    
    def extract_ticket_info(self, branch_name: str) -> Optional[Dict[str, str]]:
        """
        Extract ticket information from branch name.
        Returns dict with 'prefix', 'number', 'description' or None if not a ticket.
        """
        match = self.pattern.match(branch_name)
        if match:
            return {
                'prefix': match.group(1),
                'number': match.group(3),
                'description': match.group(5),
                'full': branch_name
            }
        return None
    
    def get_current_branch(self) -> Optional[str]:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None


class DirectoryManager:
    """Manages ticket directory creation and searching."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.workspace_base = config.get_path('paths', 'workspace_base')
        self.workspace_base.mkdir(parents=True, exist_ok=True)
    
    def sanitize_directory_name(self, name: str) -> str:
        """
        Create OS-safe directory name from branch name.
        Replaces invalid characters with underscores.
        Checks OS and adjusts length limits accordingly.
        """
        # Invalid characters for Windows/Linux: < > : " / \ | ? *
        invalid_chars = r'<>:"/\|?*'
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Remove leading/trailing dots and spaces (Windows issue)
        sanitized = sanitized.strip('. ')
        
        # Handle Windows reserved names
        reserved = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
        if sanitized.upper() in reserved:
            sanitized = f"_{sanitized}"
        
        # Check OS and adjust path length limits
        is_windows = platform.system() == 'Windows'
        
        if is_windows:
            # Windows has a 260 character path limit (MAX_PATH)
            # Calculate full path length: workspace_base + sanitized + separators
            # Reserve extra space for potential separators and extension
            try:
                workspace_path_len = len(str(self.workspace_base.resolve()))
            except (OSError, RuntimeError):
                # If we can't resolve, use a conservative estimate
                workspace_path_len = 100
            
            # Reserve 50 chars for separators, extensions, and safety margin
            # max() ensures we always have at least 50 characters for the name
            max_name_len = max(50, 260 - workspace_path_len - 50)
            
            if len(sanitized) > max_name_len:
                sanitized = sanitized[:max_name_len]
        else:
            # Linux/Mac have longer path limits, but be conservative
            # Typical limit is 255 for a single filename, but full paths can be much longer
            # We'll use 255 as a conservative limit for the directory name itself
            if len(sanitized) > 255:
                sanitized = sanitized[:255]
        
        return sanitized
    
    def find_existing_ticket_dir(self, prefix: str, number: str) -> Optional[Path]:
        """
        Search for existing directory with same prefix and number.
        Returns Path if found, None otherwise.
        """
        if not self.workspace_base.exists():
            return None
        
        # Build pattern to match: prefix-separator-number (with optional separator and more)
        # This matches directories like JIRA-123, JIRA-123-desc, JIRA_123-feature, etc.
        pattern = re.compile(rf"^{re.escape(prefix)}[-_]{re.escape(number)}([-_].*)?$", re.IGNORECASE)
        
        for item in self.workspace_base.iterdir():
            if item.is_dir():
                dir_name = item.name
                # Check if directory matches prefix-separator-number pattern
                if pattern.match(dir_name):
                    return item
        return None
    
    def create_ticket_directory(self, branch_name: str, ticket_info: Dict[str, str]) -> Path:
        """
        Create or get ticket directory.
        First searches for existing dir with same prefix+number, otherwise creates new one.
        """
        # First, try to find existing directory
        existing = self.find_existing_ticket_dir(ticket_info['prefix'], ticket_info['number'])
        if existing:
            return existing
        
        # Create new directory with sanitized branch name
        sanitized_name = self.sanitize_directory_name(branch_name)
        ticket_dir = self.workspace_base / sanitized_name
        
        ticket_dir.mkdir(parents=True, exist_ok=True)
        return ticket_dir


class ToolsLinker:
    """Links tools library items into ticket directories."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.tools_library_path = config.get_path('paths', 'tools_library_path')
        self.tools_to_link = config.get_list('links', 'tools_to_link')
    
    def link_tools(self, ticket_dir: Path) -> List[str]:
        """
        Link tools library items into ticket directory.
        Returns list of errors (empty if successful).
        """
        errors = []
        
        if not self.tools_library_path.exists():
            errors.append(f"Tools library path does not exist: {self.tools_library_path}")
            return errors
        
        for tool_name in self.tools_to_link:
            source = self.tools_library_path / tool_name
            target = ticket_dir / tool_name
            
            if not source.exists():
                errors.append(f"Tool item not found: {source}")
                continue
            
            try:
                # Remove existing symlink or file if exists
                if target.exists() or target.is_symlink():
                    if target.is_symlink():
                        target.unlink()
                    elif target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                
                # Create symlink
                target.symlink_to(source, target_is_directory=source.is_dir())
            except OSError as e:
                errors.append(f"Failed to link {tool_name}: {e}")
        
        return errors


class CurrentTicketLinker:
    """Creates 'CurrentTicket' symlinks in configured locations."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        # Handle comma-separated locations
        locations_str = config.get('links', 'current_ticket_link_locations', '')
        self.link_locations = [
            Path(os.path.expanduser(loc.strip()))
            for loc in locations_str.split(',')
            if loc.strip()
        ]
    
    def update_current_ticket_link(self, ticket_dir: Path) -> List[str]:
        """
        Create or update 'CurrentTicket' symlink in configured locations.
        Returns list of errors (empty if successful).
        """
        errors = []
        link_name = "CurrentTicket"
        
        for location in self.link_locations:
            # location is the directory where we want to create the symlink
            if not location.exists():
                # Try to create the directory if it doesn't exist
                try:
                    location.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"Directory does not exist and cannot be created: {location} ({e})")
                    continue
            
            if not location.is_dir():
                errors.append(f"Location is not a directory: {location}")
                continue
            
            target = location / link_name
            
            try:
                # Remove existing symlink or file/dir if exists
                if target.exists() or target.is_symlink():
                    if target.is_symlink():
                        target.unlink()
                    elif target.is_dir():
                        # On Windows, might need to remove directory first
                        try:
                            target.rmdir()
                        except OSError:
                            shutil.rmtree(target)
                    else:
                        target.unlink()
                
                # Create symlink
                target.symlink_to(ticket_dir, target_is_directory=True)
            except OSError as e:
                errors.append(f"Failed to create CurrentTicket link in {location}: {e}")
        
        return errors


class GitHookManager:
    """Manages git post-checkout hook installation."""
    
    def __init__(self, script_path: Optional[Path] = None):
        self.script_path = script_path
        self.use_command = self._check_command_available()
    
    def _check_command_available(self) -> bool:
        """Check if 'sidecar' command is available in PATH."""
        return shutil.which('sidecar') is not None
    
    def find_git_repo(self, start_path: Path = None) -> Optional[Path]:
        """Find .git directory starting from start_path or current directory."""
        if start_path is None:
            start_path = Path.cwd()
        
        current = Path(start_path).resolve()
        
        while current != current.parent:
            git_dir = current / '.git'
            if git_dir.exists():
                return git_dir
            current = current.parent
        
        return None
    
    def install_hook(self) -> Tuple[bool, str]:
        """Install post-checkout hook."""
        git_dir = self.find_git_repo()
        if not git_dir:
            return False, "Not in a git repository"
        
        hooks_dir = git_dir / 'hooks'
        hooks_dir.mkdir(exist_ok=True)
        
        hook_file = hooks_dir / 'post-checkout'
        
        # Determine how to call sidecar: use command if available, else use script path
        if self.use_command:
            # Installed as package - use 'sidecar' command directly
            hook_content = """#!/bin/sh
# sidecar post-checkout hook
sidecar process
"""
        elif self.script_path:
            # Direct execution - use Python with script path
            python_exec = sys.executable
            script_path_str = str(self.script_path.resolve())
            # Escape quotes for shell script
            script_path_escaped = script_path_str.replace('"', '\\"')
            hook_content = f"""#!/bin/sh
# sidecar post-checkout hook
"{python_exec}" "{script_path_escaped}" process
"""
        else:
            return False, "Cannot determine how to run sidecar. Please install via pipx/uvx or provide script path."
        
        try:
            with open(hook_file, 'w') as f:
                f.write(hook_content)
            
            # Make executable
            os.chmod(hook_file, 0o755)
            return True, f"Hook installed at {hook_file}"
        except Exception as e:
            return False, f"Failed to install hook: {e}"
    
    def uninstall_hook(self) -> Tuple[bool, str]:
        """Remove post-checkout hook."""
        git_dir = self.find_git_repo()
        if not git_dir:
            return False, "Not in a git repository"
        
        hook_file = git_dir / 'hooks' / 'post-checkout'
        
        if not hook_file.exists():
            return False, "Hook not installed"
        
        # Check if it's our hook (contains sidecar)
        try:
            with open(hook_file, 'r') as f:
                content = f.read()
                if 'sidecar' not in content:
                    return False, "Hook exists but is not a sidecar hook"
        except Exception:
            return False, "Cannot read hook file"
        
        try:
            hook_file.unlink()
            return True, "Hook uninstalled"
        except Exception as e:
            return False, f"Failed to uninstall hook: {e}"


class TicketManager:
    """Main manager that orchestrates ticket directory creation and linking."""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config = ConfigManager(config_file)
        self.branch_analyzer = BranchAnalyzer(self.config)
        self.dir_manager = DirectoryManager(self.config)
        self.tools_linker = ToolsLinker(self.config)
        self.current_ticket_linker = CurrentTicketLinker(self.config)
    
    def process_checkout(self) -> Tuple[bool, str]:
        """
        Process current git checkout.
        Returns (success, message).
        """
        branch_name = self.branch_analyzer.get_current_branch()
        if not branch_name:
            return False, "Not in a git repository or cannot get current branch"
        
        # Check if standard branch
        if self.branch_analyzer.is_standard_branch(branch_name):
            return True, f"Standard branch '{branch_name}' - no action taken"
        
        # Extract ticket info
        ticket_info = self.branch_analyzer.extract_ticket_info(branch_name)
        if not ticket_info:
            return True, f"Branch '{branch_name}' does not match ticket pattern - no action taken"
        
        # Create or get ticket directory
        try:
            ticket_dir = self.dir_manager.create_ticket_directory(branch_name, ticket_info)
        except Exception as e:
            return False, f"Failed to create ticket directory: {e}"
        
        # Link tools
        tool_errors = self.tools_linker.link_tools(ticket_dir)
        
        # Update CurrentTicket links
        link_errors = self.current_ticket_linker.update_current_ticket_link(ticket_dir)
        
        all_errors = tool_errors + link_errors
        if all_errors:
            return False, f"Ticket directory created at {ticket_dir}, but errors occurred:\n" + "\n".join(all_errors)
        
        return True, f"Ticket directory set up at {ticket_dir}"
    
    def list_ticket_directories(self) -> List[Path]:
        """List all ticket directories."""
        workspace_base = self.config.get_path('paths', 'workspace_base')
        if not workspace_base.exists():
            return []
        
        return [d for d in workspace_base.iterdir() if d.is_dir()]


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='GitSidecar - Manage ticket working directories automatically'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Hook install command
    hook_install_parser = subparsers.add_parser('hook', help='Manage git hooks')
    hook_subparsers = hook_install_parser.add_subparsers(dest='hook_action', help='Hook action')
    hook_subparsers.add_parser('install', help='Install post-checkout hook')
    hook_subparsers.add_parser('uninstall', help='Uninstall post-checkout hook')
    
    # Process command (called by hook)
    subparsers.add_parser('process', help='Process current checkout (called by hook)')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='View or edit configuration')
    config_parser.add_argument('--view', action='store_true', help='View current configuration')
    config_parser.add_argument('--set', nargs=3, metavar=('SECTION', 'KEY', 'VALUE'),
                              help='Set a configuration value')
    
    # List command
    subparsers.add_parser('list', help='List existing ticket directories')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Determine script path - only needed if not installed as package
    # GitHookManager will auto-detect if 'sidecar' command is available
    script_path = None if shutil.which('sidecar') else Path(__file__).resolve()
    
    if args.command == 'hook':
        if not args.hook_action:
            hook_install_parser.print_help()
            return 1
        
        hook_manager = GitHookManager(script_path)
        if args.hook_action == 'install':
            success, message = hook_manager.install_hook()
            print(message)
            return 0 if success else 1
        elif args.hook_action == 'uninstall':
            success, message = hook_manager.uninstall_hook()
            print(message)
            return 0 if success else 1
        else:
            hook_install_parser.print_help()
            return 1
    
    elif args.command == 'process':
        manager = TicketManager()
        success, message = manager.process_checkout()
        print(message)
        return 0 if success else 1
    
    elif args.command == 'config':
        config = ConfigManager()
        if args.view:
            print(config.view())
            return 0
        elif args.set:
            section, key, value = args.set
            try:
                config.set(section, key, value)
                print(f"Configuration updated: [{section}] {key} = {value}")
                return 0
            except Exception as e:
                print(f"Error updating configuration: {e}")
                return 1
        else:
            config_parser.print_help()
            return 1
    
    elif args.command == 'list':
        manager = TicketManager()
        ticket_dirs = manager.list_ticket_directories()
        if not ticket_dirs:
            print("No ticket directories found.")
            return 0
        
        workspace_base = manager.config.get_path('paths', 'workspace_base')
        print(f"Ticket directories in {workspace_base}:")
        for ticket_dir in sorted(ticket_dirs):
            print(f"  - {ticket_dir.name}")
        return 0
    
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
