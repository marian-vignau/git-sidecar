#!/usr/bin/env python3
"""
GitSidecar - A tool to automatically manage ticket working directories.
Hooks into git checkout to create and link ticket directories.
"""

import argparse
import configparser
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


class RepoIdentifier:
    """Extracts and normalizes repository identifiers from git remotes."""
    
    def __init__(self, git_dir: Optional[Path] = None):
        """
        Initialize with a git directory path.
        If None, will attempt to find repo from current directory.
        """
        self.git_dir = git_dir or self._find_git_repo()
    
    def _find_git_repo(self, start_path: Optional[Path] = None) -> Optional[Path]:
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
    
    def get_remote_url(self, remote_name: str = 'origin') -> Optional[str]:
        """Get URL for a specific remote, or None if not found."""
        if not self.git_dir:
            return None
        
        try:
            result = subprocess.run(
                ['git', '--git-dir', str(self.git_dir), 'remote', 'get-url', remote_name],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def get_all_remotes(self) -> Dict[str, str]:
        """Get all remotes and their URLs."""
        if not self.git_dir:
            return {}
        
        try:
            result = subprocess.run(
                ['git', '--git-dir', str(self.git_dir), 'remote', '-v'],
                capture_output=True,
                text=True,
                check=True
            )
            remotes = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        name = parts[0]
                        url = parts[1].split()[0]  # Remove "(fetch)" or "(push)"
                        if name not in remotes:  # Take first occurrence
                            remotes[name] = url
            return remotes
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize git remote URL to a standard format.
        Examples:
        - https://github.com/owner/repo.git -> github.com/owner/repo
        - git@github.com:owner/repo.git -> github.com/owner/repo
        - https://gitlab.com/user/project.git -> gitlab.com/user/project
        """
        if not url:
            return ""
        
        # Remove .git suffix if present (need to check explicitly, rstrip would remove any of those chars)
        if url.endswith('.git'):
            url = url[:-4]
        
        # Handle SSH format: git@host:owner/repo
        if url.startswith('git@'):
            # Remove 'git@' prefix
            url = url[4:]
            # Replace ':' with '/' after host
            if ':' in url:
                host, path = url.split(':', 1)
                return f"{host}/{path}"
            return url
        
        # Handle HTTPS/HTTP URLs
        if url.startswith(('http://', 'https://')):
            parsed = urlparse(url)
            host = parsed.netloc
            path = parsed.path.strip('/')
            # Remove port if present
            if ':' in host:
                host = host.split(':', 1)[0]
            return f"{host}/{path}" if path else host
        
        # If already in normalized format, return as-is
        return url
    
    def get_repo_identifier(self) -> str:
        """
        Get normalized repository identifier.
        Tries origin remote first, then first available remote, then local identifier.
        Returns format like: 'github.com/owner/repo' or 'local/repo-name-hash123'
        """
        # Try origin first
        origin_url = self.get_remote_url('origin')
        if origin_url:
            normalized = self.normalize_url(origin_url)
            if normalized:
                return normalized
        
        # Try other remotes
        remotes = self.get_all_remotes()
        for remote_name, url in remotes.items():
            if remote_name != 'origin':
                normalized = self.normalize_url(url)
                if normalized:
                    return normalized
        
        # No remotes found - use local identifier
        return self._get_local_identifier()
    
    def _get_local_identifier(self) -> str:
        """
        Generate local identifier for repos without remotes.
        Format: 'local/<dir-name>-<path-hash>'
        """
        if not self.git_dir:
            # Not in a repo at all
            return 'local/unknown'
        
        # Get the repo root directory (parent of .git)
        repo_root = self.git_dir.parent
        
        # Use directory name
        repo_name = repo_root.name
        
        # Create hash of full path for uniqueness
        path_str = str(repo_root.resolve())
        path_hash = hashlib.md5(path_str.encode()).hexdigest()[:8]
        
        return f"local/{repo_name}-{path_hash}"
    
    def get_repo_name_for_path(self) -> str:
        """
        Get sanitized repo name suitable for use in file paths.
        Examples:
        - github.com/owner/repo -> repo (or full path if collision risk)
        - local/repo-name-hash -> repo-name-hash
        """
        identifier = self.get_repo_identifier()
        
        # For local repos, use the full identifier
        if identifier.startswith('local/'):
            return identifier[6:]  # Remove 'local/' prefix
        
        # For remote repos, extract repo name (last component)
        parts = identifier.split('/')
        if len(parts) >= 2:
            return parts[-1]
        
        return identifier


class ConfigManager:
    """Manages configuration file using configparser."""
    
    DEFAULT_CONFIG_DIR = Path.home() / ".sidecar"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.ini"
    
    def __init__(self, config_file: Optional[Path] = None, repo_id: Optional[str] = None):
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self.config = configparser.ConfigParser()
        self._repo_id = repo_id
        self._ensure_config_exists()
        self._load_config()
    
    def get_current_repo_id(self, git_dir: Optional[Path] = None) -> Optional[str]:
        """
        Detect and return the current repository identifier.
        Uses RepoIdentifier to detect from current directory or provided git_dir.
        """
        repo_identifier = RepoIdentifier(git_dir)
        return repo_identifier.get_repo_identifier()
    
    def get_effective_repo_id(self, git_dir: Optional[Path] = None) -> Optional[str]:
        """
        Get the effective repo_id for this config instance.
        Uses instance repo_id if set, otherwise detects from current repo.
        """
        if self._repo_id:
            return self._repo_id
        return self.get_current_repo_id(git_dir)
    
    def _ensure_config_exists(self):
        """Create config directory and default config file if they don't exist."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.config_file.exists():
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration file with hierarchical structure."""
        # Default sections using dot notation for hierarchical structure
        self.config['default.paths'] = {
            'workspace_base': '~/tickets',
            'tools_library_path': '~/tools'
        }
        
        self.config['default.branches'] = {
            'standard_branches': 'main, master, develop, stage, production'
        }
        
        self.config['default.ticket_pattern'] = {
            'prefix_pattern': '[A-Za-z]{1,10}',
            'separator': '[-_]',
            'number_pattern': r'\d+',
            'description_pattern': '.*'
        }
        
        self.config['default.links'] = {
            'current_ticket_link_locations': '~/Downloads',
            'current_ticket_link_filename': 'CurrentTicket',
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
    
    def get(self, section: str, key: str, fallback: Optional[str] = None, repo_id: Optional[str] = None) -> str:
        """
        Get a configuration value with inheritance support.
        
        Args:
            section: Section name (e.g., 'paths', 'ticket_pattern')
            key: Key name within the section
            fallback: Fallback value if not found
            repo_id: Optional repo identifier for repo-specific lookup (uses instance repo_id if not provided)
        
        Returns:
            Configuration value resolved with inheritance: repo → default → fallback
        """
        # Use instance repo_id if not provided
        effective_repo_id = repo_id if repo_id is not None else self._repo_id
        
        # If repo_id available, try repo-specific first
        if effective_repo_id:
            repo_section = f"repo:{effective_repo_id}"
            if self.config.has_section(repo_section):
                # Try dot notation key (e.g., "paths.workspace_base")
                dot_key = f"{section}.{key}"
                if self.config.has_option(repo_section, dot_key):
                    return self.config.get(repo_section, dot_key)
        
        # Try default section
        default_section = f"default.{section}"
        if self.config.has_section(default_section):
            if self.config.has_option(default_section, key):
                return self.config.get(default_section, key)
        
        return fallback or ''
    
    def get_path(self, section: str, key: str, fallback: Optional[str] = None, repo_id: Optional[str] = None) -> Path:
        """Get a path configuration value, expanding ~ and returning Path object."""
        effective_repo_id = repo_id if repo_id is not None else self._repo_id
        value = self.get(section, key, fallback, effective_repo_id)
        if value:
            expanded = os.path.expanduser(value)
            return Path(expanded)
        return Path(fallback) if fallback else Path.home()
    
    def get_list(self, section: str, key: str, fallback: Optional[List[str]] = None, repo_id: Optional[str] = None) -> List[str]:
        """Get a comma-separated list from configuration."""
        effective_repo_id = repo_id if repo_id is not None else self._repo_id
        value = self.get(section, key, repo_id=effective_repo_id)
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return fallback or []
    
    def set(self, section: str, key: str, value: str, repo_id: Optional[str] = None, default: bool = False):
        """
        Set a configuration value.
        
        Args:
            section: Section name (e.g., 'paths', 'ticket_pattern')
            key: Key name within the section
            value: Value to set
            repo_id: If provided, set in repo-specific section using dot notation (e.g., 'paths.workspace_base')
            default: If True, explicitly set in default section (ignores repo_id)
        """
        if default:
            target_section = f"default.{section}"
            target_key = key
        elif repo_id:
            target_section = f"repo:{repo_id}"
            target_key = f"{section}.{key}"
        else:
            # Legacy flat structure - for backward compatibility
            target_section = section
            target_key = key
        
        if not self.config.has_section(target_section):
            self.config.add_section(target_section)
        self.config.set(target_section, target_key, value)
        self._save_config()
        self._load_config()
    
    def get_repo_config(self, repo_id: str) -> Dict[str, str]:
        """Get all configuration for a specific repo."""
        repo_section = f"repo:{repo_id}"
        if self.config.has_section(repo_section):
            return dict(self.config.items(repo_section))
        return {}
    
    def repo_is_configured(self, repo_id: str) -> bool:
        """Check if a repo has a specific configuration section."""
        repo_section = f"repo:{repo_id}"
        return self.config.has_section(repo_section) and len(self.config.items(repo_section)) > 0
    
    def list_configured_repos(self) -> List[str]:
        """List all repo identifiers that have configuration sections."""
        repos = []
        for section in self.config.sections():
            if section.startswith('repo:'):
                repo_id = section[5:]  # Remove 'repo:' prefix
                repos.append(repo_id)
        return repos
    
    def remove_repo_config(self, repo_id: str) -> bool:
        """Remove configuration section for a specific repo."""
        repo_section = f"repo:{repo_id}"
        if self.config.has_section(repo_section):
            self.config.remove_section(repo_section)
            self._save_config()
            self._load_config()
            return True
        return False
    
    def view(self, repo_id: Optional[str] = None, default_only: bool = False, all_repos: bool = False) -> str:
        """
        Return configuration as formatted string.
        
        Args:
            repo_id: Show specific repo config (if provided)
            default_only: Show only default sections
            all_repos: Show all repo configs
        """
        result = []
        
        # Sort sections for consistent output
        sections = sorted(self.config.sections())
        
        if default_only:
            # Show only default sections
            for section in sections:
                if section.startswith('default.'):
                    result.append(f"[{section}]")
                    for key, value in sorted(self.config.items(section)):
                        result.append(f"{key} = {value}")
                    result.append("")
        elif repo_id:
            # Show default + specific repo
            # First show defaults
            for section in sections:
                if section.startswith('default.'):
                    result.append(f"[{section}]")
                    for key, value in sorted(self.config.items(section)):
                        result.append(f"{key} = {value}")
                    result.append("")
            # Then show repo-specific
            repo_section = f"repo:{repo_id}"
            if self.config.has_section(repo_section):
                result.append(f"[{repo_section}]")
                for key, value in sorted(self.config.items(repo_section)):
                    result.append(f"{key} = {value}")
                result.append("")
        elif all_repos:
            # Show everything
            for section in sections:
                result.append(f"[{section}]")
                for key, value in sorted(self.config.items(section)):
                    result.append(f"{key} = {value}")
                result.append("")
        else:
            # Show default + current repo (if in repo)
            current_repo = self.get_current_repo_id()
            # Show defaults
            for section in sections:
                if section.startswith('default.'):
                    result.append(f"[{section}]")
                    for key, value in sorted(self.config.items(section)):
                        result.append(f"{key} = {value}")
                    result.append("")
            # Show current repo if configured
            if current_repo:
                repo_section = f"repo:{current_repo}"
                if self.config.has_section(repo_section):
                    result.append(f"[{repo_section}]")
                    for key, value in sorted(self.config.items(repo_section)):
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
    
    def get_workspace_base(self, repo_id: Optional[str] = None) -> Path:
        """
        Get workspace base directory for repo-scoped workspaces.
        Returns ~/tickets/<repo_name> if repo is configured, or default workspace_base.
        """
        # Get workspace_base from config (repo-specific or default)
        workspace_base = self.config.get_path('paths', 'workspace_base', repo_id=repo_id)
        
        # Check if this is the default workspace_base path (not configured for repo)
        default_workspace_base = self.config.get_path('paths', 'workspace_base', repo_id=None, fallback='~/tickets')
        
        # If repo_id provided and workspace_base matches default (repo not specifically configured),
        # append repo name to make it repo-scoped
        if repo_id and workspace_base == default_workspace_base:
            repo_name = self._sanitize_repo_name(repo_id)
            workspace_base = workspace_base / repo_name
        
        workspace_base.mkdir(parents=True, exist_ok=True)
        return workspace_base
    
    def _sanitize_repo_name(self, repo_id: str) -> str:
        """Sanitize repo identifier for use in directory names."""
        # Remove 'local/' prefix if present
        name = repo_id.replace('local/', '') if repo_id.startswith('local/') else repo_id
        
        # Replace invalid characters with underscores
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Replace slashes with underscores (for host/owner/repo format)
        name = name.replace('/', '_')
        
        # Limit length to 255 characters (safe for most filesystems)
        if len(name) > 255:
            name = name[:255]
        
        return name
    
    def find_existing_ticket_dir(self, prefix: str, number: str, repo_id: Optional[str] = None) -> Optional[Path]:
        """
        Search for existing directory with same prefix and number.
        Returns Path if found, None otherwise.
        """
        workspace_base = self.get_workspace_base(repo_id)
        if not workspace_base.exists():
            return None
        
        # Build pattern to match: prefix-separator-number (with optional separator and more)
        # This matches directories like JIRA-123, JIRA-123-desc, JIRA_123-feature, etc.
        pattern = re.compile(rf"^{re.escape(prefix)}[-_]{re.escape(number)}([-_].*)?$", re.IGNORECASE)
        
        for item in workspace_base.iterdir():
            if item.is_dir():
                dir_name = item.name
                # Check if directory matches prefix-separator-number pattern
                if pattern.match(dir_name):
                    return item
        return None
    
    def create_ticket_directory(self, branch_name: str, ticket_info: Dict[str, str], repo_id: Optional[str] = None) -> Path:
        """
        Create or get ticket directory.
        First searches for existing dir with same prefix+number, otherwise creates new one.
        """
        workspace_base = self.get_workspace_base(repo_id)
        
        # First, try to find existing directory
        existing = self.find_existing_ticket_dir(ticket_info['prefix'], ticket_info['number'], repo_id)
        if existing:
            return existing
        
        # Create new directory with sanitized branch name
        sanitized_name = self.sanitize_directory_name(branch_name)
        ticket_dir = workspace_base / sanitized_name
        
        ticket_dir.mkdir(parents=True, exist_ok=True)
        return ticket_dir
    
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
                # Use a reasonable estimate since we don't have workspace_base here
                workspace_path_len = 100
            except (OSError, RuntimeError):
                workspace_path_len = 100
            
            # Reserve 50 chars for separators, extensions, and safety margin
            max_name_len = max(50, 260 - workspace_path_len - 50)
            
            if len(sanitized) > max_name_len:
                sanitized = sanitized[:max_name_len]
        else:
            # Linux/Mac have longer path limits, but be conservative
            if len(sanitized) > 255:
                sanitized = sanitized[:255]
        
        return sanitized


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
    """Creates configurable symlinks in configured locations."""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def get_link_locations(self, repo_id: Optional[str] = None) -> List[Path]:
        """Get link locations from config with repo context."""
        locations_str = self.config.get('links', 'current_ticket_link_locations', repo_id=repo_id, fallback='')
        return [
            Path(os.path.expanduser(loc.strip()))
            for loc in locations_str.split(',')
            if loc.strip()
        ]
    
    def get_link_filename(self, repo_id: Optional[str] = None) -> str:
        """Get symlink filename from config with repo context."""
        filename = self.config.get('links', 'current_ticket_link_filename', repo_id=repo_id, fallback='CurrentTicket')
        return filename if filename else 'CurrentTicket'
    
    def update_current_ticket_link(self, ticket_dir: Path, repo_id: Optional[str] = None) -> List[str]:
        """
        Create or update symlink in configured locations.
        Returns list of errors (empty if successful).
        """
        errors = []
        link_name = self.get_link_filename(repo_id)
        link_locations = self.get_link_locations(repo_id)
        
        for location in link_locations:
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
                errors.append(f"Failed to create {link_name} link in {location}: {e}")
        
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
    
    def __init__(self, config_file: Optional[Path] = None, repo_id: Optional[str] = None):
        """
        Initialize TicketManager with repo context.
        
        Args:
            config_file: Optional custom config file path
            repo_id: Optional repo identifier (auto-detected if not provided)
        """
        # Detect repo_id if not provided
        if repo_id is None:
            repo_id = ConfigManager(config_file).get_current_repo_id()
        
        self.repo_id = repo_id
        self.config = ConfigManager(config_file, repo_id=repo_id)
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
        
        # Create or get ticket directory (with repo context)
        try:
            ticket_dir = self.dir_manager.create_ticket_directory(branch_name, ticket_info, self.repo_id)
        except Exception as e:
            return False, f"Failed to create ticket directory: {e}"
        
        # Link tools
        tool_errors = self.tools_linker.link_tools(ticket_dir)
        
        # Update CurrentTicket links (with repo context)
        link_errors = self.current_ticket_linker.update_current_ticket_link(ticket_dir, self.repo_id)
        
        all_errors = tool_errors + link_errors
        if all_errors:
            return False, f"Ticket directory created at {ticket_dir}, but errors occurred:\n" + "\n".join(all_errors)
        
        return True, f"Ticket directory set up at {ticket_dir}"
    
    def list_ticket_directories(self, repo_id: Optional[str] = None) -> List[Path]:
        """
        List all ticket directories for a repo.
        
        Args:
            repo_id: Optional repo identifier (uses instance repo_id if not provided)
        """
        effective_repo_id = repo_id if repo_id is not None else self.repo_id
        workspace_base = self.dir_manager.get_workspace_base(effective_repo_id)
        if not workspace_base.exists():
            return []
        
        return [d for d in workspace_base.iterdir() if d.is_dir()]


def _init_repo_config(config: ConfigManager) -> int:
    """
    Interactive repo configuration initialization.
    Prompts user for repo-specific settings.
    """
    # Detect current repo
    repo_identifier = RepoIdentifier()
    repo_id = repo_identifier.get_repo_identifier()
    
    if not repo_id:
        print("Error: Not in a git repository or cannot detect repository.")
        return 1
    
    # Check if already configured
    if config.repo_is_configured(repo_id):
        print(f"Repository '{repo_id}' is already configured.")
        response = input("Reconfigure this repository? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return 0
    
    print(f"\nConfiguring repository: {repo_id}")
    print("You can press Enter to use default values or inherit from defaults.\n")
    
    # Get defaults from config
    default_workspace_base = config.get_path('paths', 'workspace_base', repo_id=None)
    repo_name = repo_identifier.get_repo_name_for_path()
    suggested_workspace_base = default_workspace_base / repo_name
    
    # Prompt for workspace_base
    workspace_input = input(f"Workspace base directory [{suggested_workspace_base}]: ").strip()
    if workspace_input:
        workspace_base = workspace_input
    else:
        workspace_base = str(suggested_workspace_base)
    
    # Save workspace_base
    config.set('paths', 'workspace_base', workspace_base, repo_id=repo_id)
    
    # Ask if user wants to override other settings
    print("\nThe following settings will inherit from defaults:")
    print(f"  - Ticket pattern: {config.get('ticket_pattern', 'prefix_pattern', repo_id=None)}")
    print(f"  - Symlink filename: {config.get('links', 'current_ticket_link_filename', repo_id=None, fallback='CurrentTicket')}")
    print(f"  - Tools library path: {config.get_path('paths', 'tools_library_path', repo_id=None)}")
    
    override = input("\nOverride any of these settings? [y/N]: ").strip().lower()
    if override == 'y':
        # Prompt for ticket pattern override
        prefix_pattern = input(f"Ticket prefix pattern [{config.get('ticket_pattern', 'prefix_pattern', repo_id=None)}]: ").strip()
        if prefix_pattern:
            config.set('ticket_pattern', 'prefix_pattern', prefix_pattern, repo_id=repo_id)
        
        # Prompt for symlink filename
        symlink_filename = input(f"Symlink filename [{config.get('links', 'current_ticket_link_filename', repo_id=None, fallback='CurrentTicket')}]: ").strip()
        if symlink_filename:
            config.set('links', 'current_ticket_link_filename', symlink_filename, repo_id=repo_id)
    
    print(f"\nRepository '{repo_id}' configured successfully!")
    return 0


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
    config_parser.add_argument('--init-repo', action='store_true',
                              help='Initialize configuration for current repository')
    config_parser.add_argument('--list-repos', action='store_true',
                              help='List all configured repositories')
    config_parser.add_argument('--all', action='store_true',
                              help='Show all repo configurations (used with --view)')
    config_parser.add_argument('--default-only', action='store_true',
                              help='Show only default configuration (used with --view)')
    config_parser.add_argument('--repo', metavar='REPO_ID',
                              help='Specify repo identifier (used with --set or --view)')
    config_parser.add_argument('--default', action='store_true',
                              help='Set default configuration (used with --set)')
    
    # Repos command
    repos_parser = subparsers.add_parser('repos', help='Manage repository configurations')
    repos_subparsers = repos_parser.add_subparsers(dest='repos_action', help='Repos action')
    repos_subparsers.add_parser('list', help='List all configured repositories')
    repos_show_parser = repos_subparsers.add_parser('show', help='Show configuration for a repository')
    repos_show_parser.add_argument('repo_id', help='Repository identifier')
    repos_remove_parser = repos_subparsers.add_parser('remove', help='Remove configuration for a repository')
    repos_remove_parser.add_argument('repo_id', help='Repository identifier')
    
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
            # Detect repo and handle setup
            config = ConfigManager()
            repo_identifier = RepoIdentifier(hook_manager.find_git_repo())
            repo_id = repo_identifier.get_repo_identifier()
            
            if not repo_id:
                print("Error: Not in a git repository or cannot detect repository.")
                return 1
            
            # Check if repo is configured
            if not config.repo_is_configured(repo_id):
                # Repo not configured - prompt for setup
                print(f"Repository '{repo_id}' not configured.")
                response = input("Set up repository configuration now? [Y/n]: ").strip().lower()
                if response != 'n':
                    # Interactive setup
                    default_workspace_base = config.get_path('paths', 'workspace_base', repo_id=None)
                    repo_name = repo_identifier.get_repo_name_for_path()
                    suggested_workspace_base = default_workspace_base / repo_name
                    
                    workspace_input = input(f"Workspace base directory [{suggested_workspace_base}]: ").strip()
                    if workspace_input:
                        workspace_base = workspace_input
                    else:
                        workspace_base = str(suggested_workspace_base)
                    
                    # Auto-configure with defaults but with repo-specific workspace_base
                    config.set('paths', 'workspace_base', workspace_base, repo_id=repo_id)
                    print(f"Repository '{repo_id}' configured with defaults.")
                else:
                    # Auto-configure with defaults (non-interactive fallback)
                    default_workspace_base = config.get_path('paths', 'workspace_base', repo_id=None)
                    repo_name = repo_identifier.get_repo_name_for_path()
                    workspace_base = default_workspace_base / repo_name
                    config.set('paths', 'workspace_base', str(workspace_base), repo_id=repo_id)
                    print(f"Repository '{repo_id}' auto-configured with defaults.")
            else:
                # Repo already configured
                print(f"Repository '{repo_id}' already configured.")
                response = input("Reconfigure this repository? [y/N]: ").strip().lower()
                if response == 'y':
                    _init_repo_config(config)
            
            # Proceed with hook installation
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
            repo_id = args.repo if hasattr(args, 'repo') and args.repo else None
            default_only = args.default_only if hasattr(args, 'default_only') else False
            all_repos = args.all if hasattr(args, 'all') else False
            print(config.view(repo_id=repo_id, default_only=default_only, all_repos=all_repos))
            return 0
        elif args.set:
            section, key, value = args.set
            repo_id = args.repo if hasattr(args, 'repo') and args.repo else None
            default = args.default if hasattr(args, 'default') else False
            try:
                config.set(section, key, value, repo_id=repo_id, default=default)
                if default:
                    print(f"Default configuration updated: [{section}] {key} = {value}")
                elif repo_id:
                    print(f"Repository '{repo_id}' configuration updated: [{section}] {key} = {value}")
                else:
                    # Detect current repo context
                    current_repo = config.get_current_repo_id()
                    if current_repo:
                        config.set(section, key, value, repo_id=current_repo)
                        print(f"Repository '{current_repo}' configuration updated: [{section}] {key} = {value}")
                    else:
                        config.set(section, key, value, default=True)
                        print(f"Default configuration updated: [{section}] {key} = {value}")
                return 0
            except Exception as e:
                print(f"Error updating configuration: {e}")
                return 1
        elif args.init_repo:
            # Initialize repo configuration (interactive)
            return _init_repo_config(config)
        elif args.list_repos:
            repos = config.list_configured_repos()
            if not repos:
                print("No repositories configured.")
                return 0
            print("Configured repositories:")
            for repo_id in sorted(repos):
                print(f"  - {repo_id}")
            return 0
        else:
            config_parser.print_help()
            return 1
    elif args.command == 'repos':
        config = ConfigManager()
        if not args.repos_action:
            repos_parser.print_help()
            return 1
        
        if args.repos_action == 'list':
            repos = config.list_configured_repos()
            if not repos:
                print("No repositories configured.")
                return 0
            print("Configured repositories:")
            for repo_id in sorted(repos):
                print(f"  - {repo_id}")
            return 0
        elif args.repos_action == 'show':
            repo_id = args.repo_id
            if not config.repo_is_configured(repo_id):
                print(f"Repository '{repo_id}' is not configured.")
                return 1
            print(f"Configuration for repository '{repo_id}':")
            repo_config = config.get_repo_config(repo_id)
            if repo_config:
                for key, value in sorted(repo_config.items()):
                    print(f"  {key} = {value}")
            else:
                print("  (inheriting from defaults)")
            return 0
        elif args.repos_action == 'remove':
            repo_id = args.repo_id
            if not config.repo_is_configured(repo_id):
                print(f"Repository '{repo_id}' is not configured.")
                return 1
            if config.remove_repo_config(repo_id):
                print(f"Configuration for repository '{repo_id}' removed.")
                return 0
            else:
                print(f"Failed to remove configuration for repository '{repo_id}'.")
                return 1
        else:
            repos_parser.print_help()
            return 1
    
    elif args.command == 'list':
        manager = TicketManager()
        ticket_dirs = manager.list_ticket_directories()
        if not ticket_dirs:
            repo_id = manager.repo_id
            workspace_base = manager.dir_manager.get_workspace_base(repo_id)
            print(f"No ticket directories found in {workspace_base}.")
            return 0
        
        repo_id = manager.repo_id
        workspace_base = manager.dir_manager.get_workspace_base(repo_id)
        print(f"Ticket directories in {workspace_base}:")
        for ticket_dir in sorted(ticket_dirs):
            print(f"  - {ticket_dir.name}")
        return 0
    
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
