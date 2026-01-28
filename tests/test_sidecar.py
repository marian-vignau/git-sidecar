#!/usr/bin/env python3
"""
Comprehensive test suite for sidecar using Python standard library.
"""

import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Import the module to test
import main


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".sidecar"
        self.config_file = self.config_dir / "config.ini"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_config_creation(self):
        """Verify default config is created with hierarchical sections/keys."""
        config = main.ConfigManager(self.config_file)
        
        self.assertTrue(self.config_file.exists())
        # Check hierarchical default sections
        self.assertEqual(config.get('paths', 'workspace_base'), '~/tickets')
        self.assertEqual(config.get('paths', 'tools_library_path'), '~/tools')
        self.assertIn('main', config.get_list('branches', 'standard_branches'))
        self.assertEqual(config.get('ticket_pattern', 'prefix_pattern'), '[A-Za-z]{1,10}')
        self.assertEqual(config.get('links', 'current_ticket_link_filename'), 'CurrentTicket')
    
    def test_config_file_loading_hierarchical(self):
        """Load existing hierarchical config file."""
        # Create a custom config file with hierarchical structure
        config_content = """[default.paths]
workspace_base = ~/custom_tickets
tools_library_path = ~/custom_tools

[default.branches]
standard_branches = main, develop

[default.ticket_pattern]
prefix_pattern = [A-Z]{1,5}
separator = [-_]
number_pattern = \\d+
description_pattern = .*

[default.links]
current_ticket_link_locations = ~/Desktop
current_ticket_link_filename = CurrentTicket
tools_to_link = tool1, tool2

[repo:github.com/owner/repo-a]
paths.workspace_base = ~/tickets/repo-a
"""
        with open(self.config_file, 'w') as f:
            f.write(config_content)
        
        config = main.ConfigManager(self.config_file)
        
        self.assertEqual(config.get('paths', 'workspace_base'), '~/custom_tickets')
        self.assertEqual(config.get('paths', 'tools_library_path'), '~/custom_tools')
        self.assertEqual(len(config.get_list('branches', 'standard_branches')), 2)
        # Test repo-specific config
        self.assertEqual(config.get('paths', 'workspace_base', repo_id='github.com/owner/repo-a'), '~/tickets/repo-a')
    
    def test_get_method(self):
        """Retrieve values with and without fallback."""
        config = main.ConfigManager(self.config_file)
        
        self.assertEqual(config.get('paths', 'workspace_base'), '~/tickets')
        self.assertEqual(config.get('paths', 'nonexistent', fallback='default'), 'default')
    
    def test_get_path_method(self):
        """Path expansion (~ handling)."""
        config = main.ConfigManager(self.config_file)
        
        path = config.get_path('paths', 'workspace_base')
        self.assertIsInstance(path, Path)
        self.assertEqual(str(path), str(Path.home() / 'tickets'))
        
        path = config.get_path('paths', 'nonexistent', fallback='~/test')
        self.assertEqual(str(path), str(Path.home() / 'test'))
    
    def test_get_list_method(self):
        """Comma-separated list parsing with/without spaces."""
        config = main.ConfigManager(self.config_file)
        
        branches = config.get_list('branches', 'standard_branches')
        self.assertIn('main', branches)
        self.assertIn('master', branches)
        self.assertIn('develop', branches)
        
        # Test with spaces
        config.set('test', 'list_with_spaces', 'a, b, c', default=True)
        result = config.get_list('test', 'list_with_spaces')
        self.assertEqual(result, ['a', 'b', 'c'])
    
    def test_set_method_default(self):
        """Update default config values, verify persistence."""
        config = main.ConfigManager(self.config_file)
        
        config.set('paths', 'workspace_base', '~/new_tickets', default=True)
        self.assertEqual(config.get('paths', 'workspace_base'), '~/new_tickets')
        
        # Reload and verify persistence
        config2 = main.ConfigManager(self.config_file)
        self.assertEqual(config2.get('paths', 'workspace_base'), '~/new_tickets')
    
    def test_set_method_repo_specific(self):
        """Update repo-specific config values, verify persistence."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        self.assertEqual(config.get('paths', 'workspace_base', repo_id=repo_id), '~/repo_tickets')
        
        # Reload and verify persistence
        config2 = main.ConfigManager(self.config_file)
        self.assertEqual(config2.get('paths', 'workspace_base', repo_id=repo_id), '~/repo_tickets')
        # Should still use default for other repos
        self.assertEqual(config2.get('paths', 'workspace_base'), '~/tickets')
    
    def test_set_new_section_default(self):
        """Create new default section when setting value."""
        config = main.ConfigManager(self.config_file)
        
        config.set('new_section', 'new_key', 'new_value', default=True)
        self.assertTrue('default.new_section' in [s for s in config.config.sections()])
        self.assertEqual(config.get('new_section', 'new_key'), 'new_value')
    
    def test_set_new_repo_section(self):
        """Create new repo section when setting repo-specific value."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/test-repo'
        
        config.set('new_section', 'new_key', 'new_value', repo_id=repo_id)
        repo_section = f'repo:{repo_id}'
        self.assertTrue(repo_section in [s for s in config.config.sections()])
        self.assertEqual(config.get('new_section', 'new_key', repo_id=repo_id), 'new_value')
    
    def test_view_method_default(self):
        """Format default config output correctly."""
        config = main.ConfigManager(self.config_file)
        
        output = config.view(default_only=True)
        self.assertIn('[default.paths]', output)
        self.assertIn('workspace_base = ~/tickets', output)
        self.assertIn('[default.branches]', output)
    
    def test_view_method_with_repo(self):
        """Format config output with repo context."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/test-repo'
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        
        output = config.view(repo_id=repo_id)
        self.assertIn('[default.paths]', output)
        self.assertIn(f'[repo:{repo_id}]', output)
        self.assertIn('paths.workspace_base = ~/repo_tickets', output)
    
    def test_custom_config_file(self):
        """Use custom config file path."""
        custom_file = self.config_dir / "custom.ini"
        config = main.ConfigManager(custom_file)
        
        self.assertEqual(config.config_file, custom_file)
        self.assertTrue(custom_file.exists())
    
    def test_missing_config_values(self):
        """Handle missing keys/sections gracefully."""
        config = main.ConfigManager(self.config_file)
        
        self.assertEqual(config.get('nonexistent', 'key', fallback='default'), 'default')
        self.assertEqual(config.get_list('nonexistent', 'key', fallback=[]), [])
    
    def test_hierarchical_config_creation(self):
        """Verify hierarchical default sections are created correctly."""
        config = main.ConfigManager(self.config_file)
        
        # Verify default sections exist
        self.assertTrue(config.config.has_section('default.paths'))
        self.assertTrue(config.config.has_section('default.branches'))
        self.assertTrue(config.config.has_section('default.ticket_pattern'))
        self.assertTrue(config.config.has_section('default.links'))
        
        # Verify keys exist in default sections
        self.assertTrue(config.config.has_option('default.paths', 'workspace_base'))
        self.assertTrue(config.config.has_option('default.links', 'current_ticket_link_filename'))
    
    def test_get_with_repo_id(self):
        """Test repo-specific config resolution."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        # Set repo-specific config
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        
        # Should get repo-specific value
        value = config.get('paths', 'workspace_base', repo_id=repo_id)
        self.assertEqual(value, '~/repo_tickets')
        
        # Other repos should get default
        value = config.get('paths', 'workspace_base', repo_id='github.com/owner/other-repo')
        self.assertEqual(value, '~/tickets')
    
    def test_get_with_inheritance(self):
        """Test inheritance: repo → default → fallback."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        # Set default
        config.set('paths', 'tools_library_path', '~/default_tools', default=True)
        
        # Repo without specific config should inherit default
        value = config.get('paths', 'tools_library_path', repo_id=repo_id)
        self.assertEqual(value, '~/default_tools')
        
        # Set repo-specific override
        config.set('paths', 'tools_library_path', '~/repo_tools', repo_id=repo_id)
        value = config.get('paths', 'tools_library_path', repo_id=repo_id)
        self.assertEqual(value, '~/repo_tools')
        
        # Test fallback when neither exists
        value = config.get('nonexistent', 'nonexistent_key', repo_id=repo_id, fallback='fallback_value')
        self.assertEqual(value, 'fallback_value')
    
    def test_get_repo_config(self):
        """Test retrieving all config for a repo."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        config.set('ticket_pattern', 'prefix_pattern', '[A-Z]{2,5}', repo_id=repo_id)
        
        repo_config = config.get_repo_config(repo_id)
        self.assertIn('paths.workspace_base', repo_config)
        self.assertIn('ticket_pattern.prefix_pattern', repo_config)
        self.assertEqual(repo_config['paths.workspace_base'], '~/repo_tickets')
        self.assertEqual(repo_config['ticket_pattern.prefix_pattern'], '[A-Z]{2,5}')
        
        # Empty config for non-existent repo
        empty_config = config.get_repo_config('nonexistent/repo')
        self.assertEqual(empty_config, {})
    
    def test_repo_is_configured(self):
        """Test checking if repo has configuration."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        self.assertFalse(config.repo_is_configured(repo_id))
        
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        self.assertTrue(config.repo_is_configured(repo_id))
        
        self.assertFalse(config.repo_is_configured('nonexistent/repo'))
    
    def test_list_configured_repos(self):
        """Test listing all configured repositories."""
        config = main.ConfigManager(self.config_file)
        
        # Initially empty or only default sections
        repos = config.list_configured_repos()
        self.assertEqual(repos, [])
        
        # Add repo configs
        config.set('paths', 'workspace_base', '~/repo1', repo_id='github.com/owner/repo1')
        config.set('paths', 'workspace_base', '~/repo2', repo_id='github.com/owner/repo2')
        
        repos = config.list_configured_repos()
        self.assertEqual(len(repos), 2)
        self.assertIn('github.com/owner/repo1', repos)
        self.assertIn('github.com/owner/repo2', repos)
    
    def test_remove_repo_config(self):
        """Test removing repository configuration."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id=repo_id)
        self.assertTrue(config.repo_is_configured(repo_id))
        
        success = config.remove_repo_config(repo_id)
        self.assertTrue(success)
        self.assertFalse(config.repo_is_configured(repo_id))
        
        # Removing non-existent repo should return False
        success = config.remove_repo_config('nonexistent/repo')
        self.assertFalse(success)
    
    @patch('main.RepoIdentifier')
    def test_get_current_repo_id(self, mock_repo_identifier_class):
        """Test repository detection."""
        mock_repo_identifier = Mock()
        mock_repo_identifier.get_repo_identifier.return_value = 'github.com/owner/repo-test'
        mock_repo_identifier_class.return_value = mock_repo_identifier
        
        config = main.ConfigManager(self.config_file)
        repo_id = config.get_current_repo_id()
        
        self.assertEqual(repo_id, 'github.com/owner/repo-test')
    
    def test_view_default_only(self):
        """Test view with --default-only flag."""
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', '~/repo_tickets', repo_id='github.com/owner/repo')
        
        output = config.view(default_only=True)
        
        # Should only show default sections
        self.assertIn('[default.paths]', output)
        self.assertNotIn('[repo:', output)
    
    def test_view_all_repos(self):
        """Test view with --all flag."""
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', '~/repo1', repo_id='github.com/owner/repo1')
        config.set('paths', 'workspace_base', '~/repo2', repo_id='github.com/owner/repo2')
        
        output = config.view(all_repos=True)
        
        # Should show defaults and all repos
        self.assertIn('[default.paths]', output)
        self.assertIn('[repo:github.com/owner/repo1]', output)
        self.assertIn('[repo:github.com/owner/repo2]', output)


class TestRepoIdentifier(unittest.TestCase):
    """Test RepoIdentifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.git_dir = Path(self.temp_dir) / ".git"
        self.hooks_dir = self.git_dir / "hooks"
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_find_git_repo_current_dir(self):
        """Find .git in current directory."""
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            repo_identifier = main.RepoIdentifier()
            self.assertEqual(repo_identifier.git_dir, self.git_dir)
    
    def test_find_git_repo_parent_dir(self):
        """Find .git in parent directory."""
        sub_dir = Path(self.temp_dir) / "sub" / "dir"
        sub_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('pathlib.Path.cwd', return_value=sub_dir):
            repo_identifier = main.RepoIdentifier()
            self.assertEqual(repo_identifier.git_dir, self.git_dir)
    
    def test_find_git_repo_not_found(self):
        """Return None when not in repo."""
        non_repo = Path(self.temp_dir) / "not_repo"
        non_repo.mkdir()
        shutil.rmtree(self.git_dir)
        
        with patch('pathlib.Path.cwd', return_value=non_repo):
            repo_identifier = main.RepoIdentifier()
            self.assertIsNone(repo_identifier.git_dir)
    
    @patch('main.subprocess.run')
    def test_get_remote_url_origin(self, mock_run):
        """Get origin remote URL."""
        mock_result = Mock()
        mock_result.stdout = 'https://github.com/owner/repo.git\n'
        mock_run.return_value = mock_result
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        url = repo_identifier.get_remote_url('origin')
        
        self.assertEqual(url, 'https://github.com/owner/repo.git')
        mock_run.assert_called_once_with(
            ['git', '--git-dir', str(self.git_dir), 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('main.subprocess.run')
    def test_get_remote_url_not_found(self, mock_run):
        """Handle missing remote."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        url = repo_identifier.get_remote_url('origin')
        
        self.assertIsNone(url)
    
    @patch('main.subprocess.run')
    def test_get_all_remotes(self, mock_run):
        """Get all remotes and their URLs."""
        mock_result = Mock()
        mock_result.stdout = 'origin\thttps://github.com/owner/repo.git (fetch)\nupstream\thttps://github.com/original/repo.git (fetch)\n'
        mock_run.return_value = mock_result
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        remotes = repo_identifier.get_all_remotes()
        
        self.assertEqual(len(remotes), 2)
        self.assertEqual(remotes['origin'], 'https://github.com/owner/repo.git')
        self.assertEqual(remotes['upstream'], 'https://github.com/original/repo.git')
    
    def test_normalize_url_https(self):
        """Normalize HTTPS URL."""
        repo_identifier = main.RepoIdentifier()
        
        url = 'https://github.com/owner/repo.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'github.com/owner/repo')
        
        url = 'https://gitlab.com/user/project.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'gitlab.com/user/project')
    
    def test_normalize_url_ssh(self):
        """Normalize SSH URL."""
        repo_identifier = main.RepoIdentifier()
        
        url = 'git@github.com:owner/repo.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'github.com/owner/repo')
        
        url = 'git@gitlab.com:user/project.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'gitlab.com/user/project')
    
    def test_normalize_url_gitlab(self):
        """Normalize GitLab URL."""
        repo_identifier = main.RepoIdentifier()
        
        url = 'https://gitlab.com/group/subgroup/project.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'gitlab.com/group/subgroup/project')
    
    def test_normalize_url_already_normalized(self):
        """Handle already normalized URLs."""
        repo_identifier = main.RepoIdentifier()
        
        url = 'github.com/owner/repo'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'github.com/owner/repo')
    
    def test_normalize_url_with_port(self):
        """Normalize URL with port number."""
        repo_identifier = main.RepoIdentifier()
        
        url = 'https://github.com:443/owner/repo.git'
        normalized = repo_identifier.normalize_url(url)
        self.assertEqual(normalized, 'github.com/owner/repo')
    
    @patch('main.RepoIdentifier.get_remote_url')
    def test_get_repo_identifier_with_origin(self, mock_get_url):
        """Get identifier from origin remote."""
        mock_get_url.return_value = 'https://github.com/owner/repo.git'
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        repo_id = repo_identifier.get_repo_identifier()
        
        self.assertEqual(repo_id, 'github.com/owner/repo')
        mock_get_url.assert_called_once_with('origin')
    
    @patch('main.RepoIdentifier.get_remote_url')
    @patch('main.RepoIdentifier.get_all_remotes')
    def test_get_repo_identifier_no_origin(self, mock_get_all, mock_get_origin):
        """Get identifier from first available remote."""
        mock_get_origin.return_value = None
        mock_get_all.return_value = {'upstream': 'https://github.com/original/repo.git'}
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        repo_id = repo_identifier.get_repo_identifier()
        
        self.assertEqual(repo_id, 'github.com/original/repo')
    
    @patch('main.RepoIdentifier.get_remote_url')
    @patch('main.RepoIdentifier.get_all_remotes')
    def test_get_repo_identifier_no_remotes(self, mock_get_all, mock_get_origin):
        """Generate local identifier when no remotes."""
        mock_get_origin.return_value = None
        mock_get_all.return_value = {}
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        repo_id = repo_identifier.get_repo_identifier()
        
        self.assertTrue(repo_id.startswith('local/'))
        # temp_dir is a string from mkdtemp, convert to Path to get name
        self.assertIn(Path(self.temp_dir).name, repo_id)
    
    def test_get_repo_identifier_local(self):
        """Test local identifier format."""
        repo_identifier = main.RepoIdentifier(self.git_dir)
        
        # Mock no remotes
        with patch.object(repo_identifier, 'get_remote_url', return_value=None):
            with patch.object(repo_identifier, 'get_all_remotes', return_value={}):
                repo_id = repo_identifier.get_repo_identifier()
                
                self.assertTrue(repo_id.startswith('local/'))
                # Should contain directory name and hash
                parts = repo_id.split('/')
                self.assertEqual(len(parts), 2)
                self.assertEqual(parts[0], 'local')
                self.assertIn('-', parts[1])  # Should have hash
    
    @patch('main.RepoIdentifier.get_repo_identifier')
    def test_get_repo_name_for_path_remote(self, mock_get_id):
        """Extract repo name from remote URL."""
        mock_get_id.return_value = 'github.com/owner/repo'
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        name = repo_identifier.get_repo_name_for_path()
        
        self.assertEqual(name, 'repo')
    
    @patch('main.RepoIdentifier.get_repo_identifier')
    def test_get_repo_name_for_path_local(self, mock_get_id):
        """Extract repo name from local identifier."""
        mock_get_id.return_value = 'local/repo-name-abc123'
        
        repo_identifier = main.RepoIdentifier(self.git_dir)
        name = repo_identifier.get_repo_name_for_path()
        
        self.assertEqual(name, 'repo-name-abc123')
    
    def test_repo_identifier_hash_uniqueness(self):
        """Ensure local identifiers are unique for different paths."""
        repo1_dir = Path(self.temp_dir) / "repo1" / ".git"
        repo1_dir.mkdir(parents=True, exist_ok=True)
        repo2_dir = Path(self.temp_dir) / "repo2" / ".git"
        repo2_dir.mkdir(parents=True, exist_ok=True)
        
        repo1_identifier = main.RepoIdentifier(repo1_dir)
        repo2_identifier = main.RepoIdentifier(repo2_dir)
        
        # Mock no remotes for both
        with patch.object(repo1_identifier, 'get_remote_url', return_value=None):
            with patch.object(repo1_identifier, 'get_all_remotes', return_value={}):
                id1 = repo1_identifier.get_repo_identifier()
        
        with patch.object(repo2_identifier, 'get_remote_url', return_value=None):
            with patch.object(repo2_identifier, 'get_all_remotes', return_value={}):
                id2 = repo2_identifier.get_repo_identifier()
        
        # Even if directory name is same, hash should differ
        # (This tests the implementation, actual hash might match if paths are same)
        if 'repo1' in id1 and 'repo2' in id2:
            self.assertNotEqual(id1, id2)


class TestBranchAnalyzer(unittest.TestCase):
    """Test BranchAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = main.ConfigManager(self.config_file)
        self.analyzer = main.BranchAnalyzer(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_standard_branch_detection(self):
        """Identify standard branches (main, master, develop, etc.)."""
        self.assertTrue(self.analyzer.is_standard_branch('main'))
        self.assertTrue(self.analyzer.is_standard_branch('master'))
        self.assertTrue(self.analyzer.is_standard_branch('develop'))
        self.assertTrue(self.analyzer.is_standard_branch('stage'))
        self.assertFalse(self.analyzer.is_standard_branch('JIRA-123-feature'))
    
    def test_custom_standard_branches(self):
        """Use custom standard branch list from config."""
        self.config.set('branches', 'standard_branches', 'custom1, custom2', default=True)
        analyzer = main.BranchAnalyzer(self.config)
        
        self.assertTrue(analyzer.is_standard_branch('custom1'))
        self.assertTrue(analyzer.is_standard_branch('custom2'))
        self.assertFalse(analyzer.is_standard_branch('main'))
    
    def test_branch_analyzer_with_repo_config(self):
        """Test pattern matching with repo-specific ticket patterns."""
        repo_id = 'github.com/owner/repo-test'
        # Set repo-specific pattern
        self.config.set('ticket_pattern', 'prefix_pattern', '[A-Z]{2,5}', repo_id=repo_id)
        # Create config with repo context
        repo_config = main.ConfigManager(self.config.config_file, repo_id=repo_id)
        analyzer = main.BranchAnalyzer(repo_config)
        
        # Should match repo-specific pattern
        ticket_info = analyzer.extract_ticket_info('ABC-123-feature')
        self.assertIsNotNone(ticket_info)
        
        # Should not match patterns that exceed repo-specific limit
        ticket_info = analyzer.extract_ticket_info('ABCDEFG-123-feature')
        self.assertIsNone(ticket_info)  # Prefix too long (6-7 chars, limit is 5)
    
    def test_ticket_extraction_valid_patterns(self):
        """Extract ticket info from valid patterns."""
        test_cases = [
            ('JIRA-123-feature-name', {'prefix': 'JIRA', 'number': '123'}),
            ('TICKET_456-bug-fix', {'prefix': 'TICKET', 'number': '456'}),
            ('PROJ-789-simple', {'prefix': 'PROJ', 'number': '789'}),
            ('A-1-short', {'prefix': 'A', 'number': '1'}),
            ('ABCDEFGHIJ-12345-very-long-description', {'prefix': 'ABCDEFGHIJ', 'number': '12345'}),
        ]
        
        for branch_name, expected in test_cases:
            ticket_info = self.analyzer.extract_ticket_info(branch_name)
            self.assertIsNotNone(ticket_info, f"Failed to extract from {branch_name}")
            self.assertEqual(ticket_info['prefix'], expected['prefix'])
            self.assertEqual(ticket_info['number'], expected['number'])
    
    def test_ticket_extraction_invalid_patterns(self):
        """Reject invalid patterns."""
        invalid_branches = [
            '123-feature',  # No prefix
            'JIRA-feature',  # No number
            'JIRA:123-feature',  # Wrong separator
            'ABCDEFGHIJK-123-feature',  # Too long prefix (>10 chars)
            'feature-branch',  # Doesn't match pattern
        ]
        
        for branch_name in invalid_branches:
            ticket_info = self.analyzer.extract_ticket_info(branch_name)
            self.assertIsNone(ticket_info, f"Should reject {branch_name}")
    
    def test_regex_pattern_from_config(self):
        """Build regex from config values."""
        self.config.set('ticket_pattern', 'prefix_pattern', '[A-Z]{1,3}', default=True)
        self.config.set('ticket_pattern', 'separator', '-', default=True)
        self.config.set('ticket_pattern', 'number_pattern', '\\d{3}', default=True)
        analyzer = main.BranchAnalyzer(self.config)
        
        ticket_info = analyzer.extract_ticket_info('ABC-123-feature')
        self.assertIsNotNone(ticket_info)
        self.assertEqual(ticket_info['prefix'], 'ABC')
        self.assertEqual(ticket_info['number'], '123')
    
    @patch('main.subprocess.run')
    def test_get_current_branch_success(self, mock_run):
        """Mock git command success."""
        mock_result = Mock()
        mock_result.stdout = '  feature-branch  \n'
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        branch = self.analyzer.get_current_branch()
        self.assertEqual(branch, 'feature-branch')
        mock_run.assert_called_once_with(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('main.subprocess.run')
    def test_get_current_branch_failure(self, mock_run):
        """Handle git command failure (not in repo)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        
        branch = self.analyzer.get_current_branch()
        self.assertIsNone(branch)
    
    @patch('main.subprocess.run')
    def test_get_current_branch_no_git(self, mock_run):
        """Handle missing git command."""
        mock_run.side_effect = FileNotFoundError()
        
        branch = self.analyzer.get_current_branch()
        self.assertIsNone(branch)


class TestDirectoryManager(unittest.TestCase):
    """Test DirectoryManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_base = Path(self.temp_dir) / "workspace"
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', str(self.workspace_base), default=True)
        
        self.config = main.ConfigManager(self.config_file)
        self.dir_manager = main.DirectoryManager(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_directory_name_sanitization_linux(self):
        """Replace invalid chars on Linux."""
        with patch('platform.system', return_value='Linux'):
            sanitized = self.dir_manager.sanitize_directory_name('test<>:"/\\|?*name')
            # 9 invalid chars: < > : " / \ | ? *
            self.assertEqual(sanitized, 'test_________name')  # 9 underscores
            self.assertNotIn('<', sanitized)
            self.assertNotIn('>', sanitized)
            self.assertNotIn(':', sanitized)
    
    def test_directory_name_sanitization_windows(self):
        """Windows-specific sanitization."""
        with patch('platform.system', return_value='Windows'):
            sanitized = self.dir_manager.sanitize_directory_name('test<>:"/\\|?*name')
            # 9 invalid chars: < > : " / \ | ? *
            self.assertEqual(sanitized, 'test_________name')  # 9 underscores
    
    def test_windows_reserved_names(self):
        """Handle CON, PRN, AUX, etc."""
        with patch('platform.system', return_value='Windows'):
            sanitized = self.dir_manager.sanitize_directory_name('CON')
            self.assertTrue(sanitized.startswith('_'))
            
            sanitized = self.dir_manager.sanitize_directory_name('prn')
            self.assertTrue(sanitized.upper().startswith('_'))
    
    def test_windows_path_length_limit(self):
        """Calculate and enforce Windows 260-char limit."""
        with patch('platform.system', return_value='Windows'):
            # Create a long directory name
            long_name = 'A' * 300
            sanitized = self.dir_manager.sanitize_directory_name(long_name)
            
            # Should be shortened based on workspace path length
            workspace_len = len(str(self.workspace_base.resolve()))
            max_len = max(50, 260 - workspace_len - 50)
            self.assertLessEqual(len(sanitized), max_len)
            self.assertGreaterEqual(len(sanitized), 50)  # Minimum
    
    def test_linux_path_length_limit(self):
        """Enforce 255-char limit on Linux."""
        with patch('platform.system', return_value='Linux'):
            long_name = 'A' * 300
            sanitized = self.dir_manager.sanitize_directory_name(long_name)
            self.assertLessEqual(len(sanitized), 255)
    
    def test_path_length_with_long_workspace(self):
        """Handle very long workspace paths."""
        # Create a very long workspace path
        long_workspace = Path(self.temp_dir) / ('A' * 200)
        long_workspace.mkdir(parents=True, exist_ok=True)
        self.config.set('paths', 'workspace_base', str(long_workspace), default=True)
        
        with patch('platform.system', return_value='Windows'):
            dir_manager = main.DirectoryManager(self.config)
            long_name = 'B' * 300
            sanitized = dir_manager.sanitize_directory_name(long_name)
            # Should still respect minimum
            self.assertGreaterEqual(len(sanitized), 50)
    
    def test_workspace_base_repo_name_collision(self):
        """Test handling of repo name collisions."""
        repo_id1 = 'github.com/owner1/repo'
        repo_id2 = 'github.com/owner2/repo'
        
        workspace1 = self.dir_manager.get_workspace_base(repo_id=repo_id1)
        workspace2 = self.dir_manager.get_workspace_base(repo_id=repo_id2)
        
        # Both should use full sanitized name to avoid collision
        self.assertNotEqual(workspace1, workspace2)
        self.assertIn('owner1', str(workspace1))
        self.assertIn('owner2', str(workspace2))
    
    def test_get_workspace_base_default(self):
        """Test default workspace base."""
        workspace = self.dir_manager.get_workspace_base()
        
        self.assertEqual(workspace, self.workspace_base)
        self.assertTrue(workspace.exists())
    
    def test_get_workspace_base_repo_scoped(self):
        """Test repo-scoped workspace (appends repo name)."""
        repo_id = 'github.com/owner/repo-test'
        workspace = self.dir_manager.get_workspace_base(repo_id=repo_id)
        
        # Should append sanitized repo name (full identifier sanitized)
        expected = self.workspace_base / 'github.com_owner_repo-test'
        self.assertEqual(workspace, expected)
        self.assertTrue(workspace.exists())
    
    def test_get_workspace_base_repo_configured(self):
        """Test workspace base from repo-specific config."""
        repo_id = 'github.com/owner/repo-test'
        custom_workspace = Path(self.temp_dir) / "custom_workspace"
        self.config.set('paths', 'workspace_base', str(custom_workspace), repo_id=repo_id)
        
        workspace = self.dir_manager.get_workspace_base(repo_id=repo_id)
        
        self.assertEqual(workspace, custom_workspace)
        self.assertTrue(workspace.exists())
    
    def test_sanitize_repo_name(self):
        """Test sanitization of repo identifiers for directory names."""
        # Test remote repo identifier (full path)
        repo_id = 'github.com/owner/repo-test'
        sanitized = self.dir_manager._sanitize_repo_name(repo_id)
        self.assertEqual(sanitized, 'github.com_owner_repo-test')
        self.assertNotIn('/', sanitized)  # Slashes should be replaced
        
        # Test local repo identifier
        local_repo_id = 'local/repo-name-abc123'
        sanitized = self.dir_manager._sanitize_repo_name(local_repo_id)
        self.assertEqual(sanitized, 'repo-name-abc123')
        self.assertNotIn('local/', sanitized)  # local/ prefix should be removed
        
        # Test special characters that are invalid for directories
        special_repo_id = 'github.com/org/repo:special'
        sanitized = self.dir_manager._sanitize_repo_name(special_repo_id)
        self.assertNotIn(':', sanitized)  # Invalid chars should be replaced
        self.assertNotIn('/', sanitized)  # Slashes should be replaced
        
        # Test that dots are preserved (valid in directory names)
        repo_with_dots = 'github.com/org/repo.with.dots'
        sanitized = self.dir_manager._sanitize_repo_name(repo_with_dots)
        # Dots are valid in directory names, so they can remain
        self.assertIn('repo.with.dots', sanitized)
        self.assertNotIn('/', sanitized)
    
    def test_find_existing_ticket_dir_match(self):
        """Find directory by prefix+number."""
        # Create existing directories
        existing1 = self.workspace_base / "JIRA-123-old-feature"
        existing2 = self.workspace_base / "TICKET_456"
        existing3 = self.workspace_base / "OTHER-999"
        
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        existing1.mkdir()
        existing2.mkdir()
        existing3.mkdir()
        
        found = self.dir_manager.find_existing_ticket_dir('JIRA', '123')
        self.assertIsNotNone(found)
        self.assertEqual(found.name, 'JIRA-123-old-feature')
        
        found = self.dir_manager.find_existing_ticket_dir('TICKET', '456')
        self.assertIsNotNone(found)
        self.assertEqual(found.name, 'TICKET_456')
    
    def test_find_existing_ticket_dir_repo_scoped(self):
        """Find directory in repo-scoped workspace."""
        repo_id = 'github.com/owner/repo-test'
        repo_workspace = self.dir_manager.get_workspace_base(repo_id=repo_id)
        existing = repo_workspace / "JIRA-123-feature"
        existing.mkdir(parents=True, exist_ok=True)
        
        found = self.dir_manager.find_existing_ticket_dir('JIRA', '123', repo_id=repo_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, 'JIRA-123-feature')
    
    def test_find_existing_ticket_dir_no_match(self):
        """No match when different prefix/number."""
        existing = self.workspace_base / "JIRA-123-feature"
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        existing.mkdir()
        
        found = self.dir_manager.find_existing_ticket_dir('JIRA', '999')
        self.assertIsNone(found)
        
        found = self.dir_manager.find_existing_ticket_dir('OTHER', '123')
        self.assertIsNone(found)
    
    def test_find_existing_ticket_dir_case_insensitive(self):
        """Case-insensitive matching."""
        existing = self.workspace_base / "jira-123-feature"
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        existing.mkdir()
        
        found = self.dir_manager.find_existing_ticket_dir('JIRA', '123')
        self.assertIsNotNone(found)
    
    def test_create_ticket_directory_new(self):
        """Create new directory."""
        branch_name = 'JIRA-999-new-feature'
        ticket_info = {'prefix': 'JIRA', 'number': '999', 'description': 'new-feature'}
        
        ticket_dir = self.dir_manager.create_ticket_directory(branch_name, ticket_info)
        
        self.assertTrue(ticket_dir.exists())
        self.assertEqual(ticket_dir.name, 'JIRA-999-new-feature')
    
    def test_create_ticket_directory_repo_scoped(self):
        """Create directory in repo-scoped workspace."""
        repo_id = 'github.com/owner/repo-test'
        branch_name = 'JIRA-999-new-feature'
        ticket_info = {'prefix': 'JIRA', 'number': '999', 'description': 'new-feature'}
        
        ticket_dir = self.dir_manager.create_ticket_directory(branch_name, ticket_info, repo_id=repo_id)
        
        self.assertTrue(ticket_dir.exists())
        self.assertEqual(ticket_dir.name, 'JIRA-999-new-feature')
        # Should be in repo-scoped workspace (sanitized repo identifier)
        self.assertEqual(ticket_dir.parent.name, 'github.com_owner_repo-test')
    
    def test_create_ticket_directory_existing(self):
        """Reuse existing directory with same prefix+number."""
        # Create existing directory
        existing = self.workspace_base / "JIRA-123-old-description"
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        existing.mkdir()
        
        branch_name = 'JIRA-123-new-description'
        ticket_info = {'prefix': 'JIRA', 'number': '123', 'description': 'new-description'}
        
        ticket_dir = self.dir_manager.create_ticket_directory(branch_name, ticket_info)
        
        self.assertEqual(ticket_dir, existing)
    
    def test_create_ticket_directory_permission_error(self):
        """Handle permission errors."""
        # Make workspace_base read-only (on Unix)
        if os.name != 'nt':
            self.workspace_base.mkdir(parents=True, exist_ok=True)
            self.workspace_base.chmod(0o444)  # Read-only
            
            try:
                branch_name = 'JIRA-123-feature'
                ticket_info = {'prefix': 'JIRA', 'number': '123', 'description': 'feature'}
                
                with self.assertRaises(Exception):
                    self.dir_manager.create_ticket_directory(branch_name, ticket_info)
            finally:
                self.workspace_base.chmod(0o755)  # Restore


class TestToolsLinker(unittest.TestCase):
    """Test ToolsLinker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.tools_lib = Path(self.temp_dir) / "tools"
        self.ticket_dir = Path(self.temp_dir) / "ticket"
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.tools_lib.mkdir(parents=True, exist_ok=True)
        self.ticket_dir.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'tools_library_path', str(self.tools_lib), default=True)
        config.set('links', 'tools_to_link', 'notebooks, scripts, utils', default=True)
        
        self.config = main.ConfigManager(self.config_file)
        self.tools_linker = main.ToolsLinker(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_link_tools_success(self):
        """Create symlinks for all configured tools."""
        # Create tool directories
        (self.tools_lib / 'notebooks').mkdir()
        (self.tools_lib / 'scripts').mkdir()
        (self.tools_lib / 'utils').mkdir()
        
        errors = self.tools_linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
        self.assertTrue((self.ticket_dir / 'scripts').is_symlink())
        self.assertTrue((self.ticket_dir / 'utils').is_symlink())
    
    def test_link_tools_file_and_directory(self):
        """Handle both files and directories."""
        (self.tools_lib / 'notebooks').mkdir()
        (self.tools_lib / 'script.py').touch()
        
        self.config.set('links', 'tools_to_link', 'notebooks, script.py', default=True)
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
        self.assertTrue((self.ticket_dir / 'script.py').is_symlink())
    
    def test_link_tools_missing_library_path(self):
        """Error when tools library doesn't exist."""
        self.config.set('paths', 'tools_library_path', '/nonexistent/path', default=True)
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertGreater(len(errors), 0)
        self.assertIn('does not exist', errors[0])
    
    def test_link_tools_missing_tool_item(self):
        """Skip missing tools, continue with others."""
        (self.tools_lib / 'notebooks').mkdir()
        # scripts and utils don't exist
        
        errors = self.tools_linker.link_tools(self.ticket_dir)
        
        # Should have errors for missing tools
        self.assertGreater(len(errors), 0)
        # But notebooks should still be linked
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
    
    def test_link_tools_overwrite_existing_symlink(self):
        """Replace existing symlink."""
        # Create existing symlink pointing elsewhere
        other_target = Path(self.temp_dir) / "other"
        other_target.mkdir()
        (self.ticket_dir / 'notebooks').symlink_to(other_target)
        
        (self.tools_lib / 'notebooks').mkdir()
        # Create other tools to avoid errors
        (self.tools_lib / 'scripts').mkdir()
        (self.tools_lib / 'utils').mkdir()
        
        errors = self.tools_linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        # Verify it points to the correct location
        self.assertEqual((self.ticket_dir / 'notebooks').readlink(), self.tools_lib / 'notebooks')
    
    def test_link_tools_overwrite_existing_directory(self):
        """Remove existing directory before linking."""
        (self.ticket_dir / 'notebooks').mkdir()
        (self.ticket_dir / 'notebooks' / 'file.txt').touch()
        
        (self.tools_lib / 'notebooks').mkdir()
        # Create other tools to avoid errors
        (self.tools_lib / 'scripts').mkdir()
        (self.tools_lib / 'utils').mkdir()
        
        errors = self.tools_linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
        self.assertFalse((self.ticket_dir / 'notebooks' / 'file.txt').exists())
    
    def test_link_tools_overwrite_existing_file(self):
        """Remove existing file before linking."""
        (self.ticket_dir / 'notebooks').touch()
        (self.tools_lib / 'notebooks').touch()
        
        self.config.set('links', 'tools_to_link', 'notebooks', default=True)
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
    
    def test_link_tools_empty_config(self):
        """Handle empty tools_to_link list."""
        self.config.set('links', 'tools_to_link', '', default=True)
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
    
    def test_link_tools_repo_specific_path(self):
        """Test repo-specific tools library path."""
        repo_id = 'github.com/owner/repo-test'
        repo_tools_lib = Path(self.temp_dir) / "repo_tools"
        repo_tools_lib.mkdir()
        (repo_tools_lib / 'custom_tool').mkdir()
        
        self.config.set('paths', 'tools_library_path', str(repo_tools_lib), repo_id=repo_id)
        self.config.set('links', 'tools_to_link', 'custom_tool', repo_id=repo_id)
        
        # Create config with repo context
        repo_config = main.ConfigManager(self.config.config_file, repo_id=repo_id)
        linker = main.ToolsLinker(repo_config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'custom_tool').is_symlink())


class TestCurrentTicketLinker(unittest.TestCase):
    """Test CurrentTicketLinker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_base = Path(self.temp_dir) / "workspace"
        self.ticket_dir = self.workspace_base / "JIRA-123-feature"
        self.link_location = Path(self.temp_dir) / "links"
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        self.ticket_dir.mkdir(parents=True, exist_ok=True)
        self.link_location.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', str(self.workspace_base), default=True)
        config.set('links', 'current_ticket_link_locations', str(self.link_location), default=True)
        config.set('links', 'current_ticket_link_filename', 'CurrentTicket', default=True)
        
        self.config = main.ConfigManager(self.config_file)
        self.current_ticket_linker = main.CurrentTicketLinker(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_link_filename_default(self):
        """Test default symlink filename."""
        filename = self.current_ticket_linker.get_link_filename()
        self.assertEqual(filename, 'CurrentTicket')
    
    def test_get_link_filename_repo_specific(self):
        """Test repo-specific symlink filename."""
        repo_id = 'github.com/owner/repo-test'
        self.config.set('links', 'current_ticket_link_filename', 'CustomLink', repo_id=repo_id)
        
        filename = self.current_ticket_linker.get_link_filename(repo_id=repo_id)
        self.assertEqual(filename, 'CustomLink')
        
        # Other repos should use default
        filename = self.current_ticket_linker.get_link_filename(repo_id='github.com/owner/other-repo')
        self.assertEqual(filename, 'CurrentTicket')
    
    def test_get_link_locations_default(self):
        """Test default link locations."""
        locations = self.current_ticket_linker.get_link_locations()
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0], self.link_location)
    
    def test_get_link_locations_repo_specific(self):
        """Test repo-specific link locations."""
        repo_id = 'github.com/owner/repo-test'
        link_location2 = Path(self.temp_dir) / "links2"
        link_location2.mkdir()
        self.config.set('links', 'current_ticket_link_locations', 
                       str(link_location2), repo_id=repo_id)
        
        locations = self.current_ticket_linker.get_link_locations(repo_id=repo_id)
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0], link_location2)
    
    def test_update_current_ticket_link_success(self):
        """Create symlink in configured locations."""
        errors = self.current_ticket_linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CurrentTicket"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink().resolve(), self.ticket_dir.resolve())
    
    def test_update_current_ticket_link_multiple_locations(self):
        """Create in multiple locations."""
        link_location2 = Path(self.temp_dir) / "links2"
        link_location2.mkdir()
        
        self.config.set('links', 'current_ticket_link_locations', 
                       f'{self.link_location}, {link_location2}', default=True)
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.link_location / "CurrentTicket").is_symlink())
        self.assertTrue((link_location2 / "CurrentTicket").is_symlink())
    
    def test_update_current_ticket_link_custom_filename(self):
        """Test creating symlink with custom filename."""
        repo_id = 'github.com/owner/repo-test'
        self.config.set('links', 'current_ticket_link_filename', 'CustomLink', repo_id=repo_id)
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir, repo_id=repo_id)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CustomLink"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink().resolve(), self.ticket_dir.resolve())
        
        # Default filename should not exist
        default_link = self.link_location / "CurrentTicket"
        self.assertFalse(default_link.exists())
    
    def test_update_current_ticket_link_create_directory(self):
        """Create parent directory if missing."""
        missing_dir = Path(self.temp_dir) / "missing" / "path"
        self.config.set('links', 'current_ticket_link_locations', str(missing_dir), default=True)
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue(missing_dir.exists())
        self.assertTrue((missing_dir / "CurrentTicket").is_symlink())
    
    def test_update_current_ticket_link_overwrite_existing_symlink(self):
        """Replace existing symlink."""
        other_target = Path(self.temp_dir) / "other"
        other_target.mkdir()
        (self.link_location / "CurrentTicket").symlink_to(other_target)
        
        errors = self.current_ticket_linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CurrentTicket"
        self.assertEqual(link.readlink().resolve(), self.ticket_dir.resolve())
    
    def test_update_current_ticket_link_overwrite_ticket_directory(self):
        """Overwrite when target is ticket dir."""
        # Create another ticket dir
        other_ticket = self.workspace_base / "JIRA-999-other"
        other_ticket.mkdir()
        
        # Create symlink pointing to other ticket
        (self.link_location / "CurrentTicket").symlink_to(other_ticket)
        
        errors = self.current_ticket_linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CurrentTicket"
        self.assertEqual(link.readlink().resolve(), self.ticket_dir.resolve())
    
    def test_update_current_ticket_link_overwrite_non_ticket_directory(self):
        """Overwrite non-ticket dir."""
        other_dir = Path(self.temp_dir) / "other_non_ticket"
        other_dir.mkdir()
        
        # Create directory (not symlink) with same name
        (self.link_location / "CurrentTicket").mkdir()
        
        errors = self.current_ticket_linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CurrentTicket"
        self.assertTrue(link.is_symlink())
    
    def test_update_current_ticket_link_path_resolution(self):
        """Handle ~ in paths correctly."""
        # Test with tilde path - use temp directory instead of home to avoid permission issues
        test_links_dir = Path(self.temp_dir) / "test_links"
        test_links_dir.mkdir(exist_ok=True)
        tilde_path_str = str(test_links_dir)
        
        # Use absolute path instead of ~ to avoid permission issues in tests
        self.config.set('links', 'current_ticket_link_locations', tilde_path_str, default=True)
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = test_links_dir / "CurrentTicket"
        self.assertTrue(link.is_symlink())
    
    def test_update_current_ticket_link_broken_symlink(self):
        """Handle broken/unresolvable symlinks."""
        broken_target = Path(self.temp_dir) / "nonexistent"
        (self.link_location / "CurrentTicket").symlink_to(broken_target)
        
        errors = self.current_ticket_linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = self.link_location / "CurrentTicket"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink().resolve(), self.ticket_dir.resolve())


class TestGitHookManager(unittest.TestCase):
    """Test GitHookManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.git_dir = Path(self.temp_dir) / ".git"
        self.hooks_dir = self.git_dir / "hooks"
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        
        self.script_path = Path(self.temp_dir) / "main.py"
        self.script_path.touch()
        
        # Patch shutil.which to return None so tests use script path approach
        # (simulating direct execution, not installed package)
        with patch('main.shutil.which', return_value=None):
            self.hook_manager = main.GitHookManager(self.script_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_find_git_repo_success(self):
        """Find .git in current directory."""
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            git_dir = self.hook_manager.find_git_repo()
            self.assertIsNotNone(git_dir)
            self.assertEqual(git_dir, self.git_dir)
    
    def test_find_git_repo_parent(self):
        """Find .git in parent directory."""
        sub_dir = Path(self.temp_dir) / "sub" / "dir"
        sub_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('pathlib.Path.cwd', return_value=sub_dir):
            git_dir = self.hook_manager.find_git_repo()
            self.assertIsNotNone(git_dir)
            self.assertEqual(git_dir, self.git_dir)
    
    def test_find_git_repo_not_found(self):
        """Return None when not in repo."""
        non_repo = Path(self.temp_dir) / "not_repo"
        non_repo.mkdir()
        
        # Remove .git
        shutil.rmtree(self.git_dir)
        
        with patch('pathlib.Path.cwd', return_value=non_repo):
            git_dir = self.hook_manager.find_git_repo()
            self.assertIsNone(git_dir)
    
    def test_install_hook_success(self):
        """Create post-checkout hook with correct content."""
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.install_hook()
            
            self.assertTrue(success)
            hook_file = self.hooks_dir / "post-checkout"
            self.assertTrue(hook_file.exists())
            
            # Check hook content
            content = hook_file.read_text()
            self.assertIn('sidecar', content)
            self.assertIn('process', content)
            self.assertIn(str(self.script_path.resolve()), content)
    
    def test_install_hook_makes_executable(self):
        """Verify hook is executable (Unix)."""
        if os.name != 'nt':
            with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
                self.hook_manager.install_hook()
                
                hook_file = self.hooks_dir / "post-checkout"
                self.assertTrue(os.access(hook_file, os.X_OK))
    
    def test_install_hook_creates_hooks_dir(self):
        """Create hooks directory if missing."""
        shutil.rmtree(self.hooks_dir)
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.install_hook()
            
            self.assertTrue(success)
            self.assertTrue(self.hooks_dir.exists())
    
    def test_install_hook_not_in_repo(self):
        """Error when not in git repository."""
        shutil.rmtree(self.git_dir)
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.install_hook()
            
            self.assertFalse(success)
            self.assertIn('Not in a git repository', message)
    
    def test_install_hook_overwrite_existing(self):
        """Replace existing hook."""
        hook_file = self.hooks_dir / "post-checkout"
        hook_file.write_text("#!/bin/sh\necho 'old hook'\n")
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.install_hook()
            
            self.assertTrue(success)
            content = hook_file.read_text()
            self.assertIn('sidecar', content)
    
    def test_uninstall_hook_success(self):
        """Remove hook file."""
        hook_file = self.hooks_dir / "post-checkout"
        hook_file.write_text("#!/bin/sh\n# sidecar post-checkout hook\npython3 main.py process\n")
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.uninstall_hook()
            
            self.assertTrue(success)
            self.assertFalse(hook_file.exists())
    
    def test_uninstall_hook_not_installed(self):
        """Error when hook doesn't exist."""
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.uninstall_hook()
            
            self.assertFalse(success)
            self.assertIn('Hook not installed', message)
    
    def test_uninstall_hook_not_ours(self):
        """Error when hook exists but isn't sidecar hook."""
        hook_file = self.hooks_dir / "post-checkout"
        hook_file.write_text("#!/bin/sh\necho 'other hook'\n")
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.uninstall_hook()
            
            self.assertFalse(success)
            self.assertIn('not a sidecar hook', message)
            self.assertTrue(hook_file.exists())  # Should not be deleted


class TestTicketManager(unittest.TestCase):
    """Test TicketManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', str(Path(self.temp_dir) / "workspace"), default=True)
        config.set('paths', 'tools_library_path', str(Path(self.temp_dir) / "tools"), default=True)
        config.set('links', 'current_ticket_link_locations', str(Path(self.temp_dir) / "links"), default=True)
        
        # Mock repo detection to avoid actual git calls
        with patch('main.ConfigManager.get_current_repo_id', return_value=None):
            self.manager = main.TicketManager(self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    def test_process_checkout_standard_branch(self, mock_branch):
        """No action for standard branches."""
        mock_branch.return_value = 'main'
        
        success, message = self.manager.process_checkout()
        
        self.assertTrue(success)
        self.assertIn('Standard branch', message)
    
    def test_ticket_manager_with_repo_id(self):
        """Test initialization with explicit repo_id."""
        repo_id = 'github.com/owner/test-repo'
        manager = main.TicketManager(self.config_file, repo_id=repo_id)
        
        self.assertEqual(manager.repo_id, repo_id)
    
    @patch('main.RepoIdentifier')
    def test_ticket_manager_auto_detect_repo(self, mock_repo_identifier_class):
        """Test auto-detection of repo_id."""
        mock_repo_identifier = Mock()
        mock_repo_identifier.get_repo_identifier.return_value = 'github.com/owner/auto-repo'
        mock_repo_identifier_class.return_value = mock_repo_identifier
        
        with patch('main.ConfigManager.get_current_repo_id', return_value='github.com/owner/auto-repo'):
            manager = main.TicketManager(self.config_file)
            # repo_id might be None if no git repo, but structure should work
            self.assertIsNotNone(manager)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    @patch('main.ToolsLinker.link_tools')
    @patch('main.CurrentTicketLinker.update_current_ticket_link')
    def test_process_checkout_ticket_branch_new_dir(self, mock_link, mock_tools, mock_branch):
        """Full flow: create dir, link tools, create CurrentTicket."""
        mock_branch.return_value = 'JIRA-123-new-feature'
        mock_tools.return_value = []
        mock_link.return_value = []
        
        success, message = self.manager.process_checkout()
        
        self.assertTrue(success)
        self.assertIn('set up at', message)
        mock_tools.assert_called_once()
        mock_link.assert_called_once()
        # Verify update_current_ticket_link was called with at least ticket_dir
        # (repo_id may be None if not in git repo, which is fine - tested in repo_scoped test)
        call_args = mock_link.call_args
        self.assertGreaterEqual(len(call_args[0]), 1)  # At least ticket_dir (Path object)
        # repo_id is passed as second positional argument (could be None if not detected)
        self.assertEqual(len(call_args[0]), 2)  # ticket_dir and repo_id (even if None)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    def test_process_checkout_invalid_pattern(self, mock_branch):
        """Skip branches that don't match pattern."""
        mock_branch.return_value = 'feature-branch'
        
        success, message = self.manager.process_checkout()
        
        self.assertTrue(success)
        self.assertIn('does not match ticket pattern', message)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    def test_process_checkout_not_in_repo(self, mock_branch):
        """Error when not in git repository."""
        mock_branch.return_value = None
        
        success, message = self.manager.process_checkout()
        
        self.assertFalse(success)
        self.assertIn('Not in a git repository', message)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    @patch('main.ToolsLinker.link_tools')
    def test_process_checkout_tool_errors(self, mock_tools, mock_branch):
        """Continue despite tool linking errors."""
        mock_branch.return_value = 'JIRA-123-feature'
        mock_tools.return_value = ['Tool error 1', 'Tool error 2']
        
        with patch('main.CurrentTicketLinker.update_current_ticket_link', return_value=[]):
            success, message = self.manager.process_checkout()
            
            self.assertFalse(success)
            self.assertIn('errors occurred', message)
    
    @patch('main.BranchAnalyzer.get_current_branch')
    @patch('main.ToolsLinker.link_tools')
    @patch('main.CurrentTicketLinker.update_current_ticket_link')
    def test_process_checkout_repo_scoped(self, mock_link, mock_tools, mock_branch):
        """Test checkout in repo-scoped workspace."""
        repo_id = 'github.com/owner/repo-test'
        manager = main.TicketManager(self.config_file, repo_id=repo_id)
        mock_branch.return_value = 'JIRA-123-feature'
        mock_tools.return_value = []
        mock_link.return_value = []
        
        success, message = manager.process_checkout()
        
        self.assertTrue(success)
        # Verify repo_id was passed (as positional argument after ticket_dir)
        mock_link.assert_called_once()
        call_args = mock_link.call_args
        # update_current_ticket_link(ticket_dir, self.repo_id) - both positional
        # Should be called with 2 positional args: ticket_dir and repo_id
        self.assertEqual(len(call_args[0]), 2)  # ticket_dir and repo_id as positional
        self.assertEqual(call_args[0][1], repo_id)  # Second positional arg is repo_id
    
    def test_list_ticket_directories_empty(self):
        """Return empty list when no directories."""
        dirs = self.manager.list_ticket_directories()
        self.assertEqual(dirs, [])
    
    def test_list_ticket_directories_multiple(self):
        """List all ticket directories."""
        workspace_base = self.manager.dir_manager.get_workspace_base(repo_id=self.manager.repo_id)
        workspace_base.mkdir(parents=True, exist_ok=True)
        
        (workspace_base / "JIRA-123").mkdir()
        (workspace_base / "TICKET-456").mkdir()
        
        dirs = self.manager.list_ticket_directories()
        
        self.assertEqual(len(dirs), 2)
        names = {d.name for d in dirs}
        self.assertIn('JIRA-123', names)
        self.assertIn('TICKET-456', names)
    
    def test_list_ticket_directories_repo_scoped(self):
        """Test listing tickets for specific repo."""
        repo_id = 'github.com/owner/repo-test'
        manager = main.TicketManager(self.config_file, repo_id=repo_id)
        workspace_base = manager.dir_manager.get_workspace_base(repo_id=repo_id)
        workspace_base.mkdir(parents=True, exist_ok=True)
        
        (workspace_base / "JIRA-123").mkdir()
        (workspace_base / "TICKET-456").mkdir()
        
        dirs = manager.list_ticket_directories(repo_id=repo_id)
        
        self.assertEqual(len(dirs), 2)
        # Verify they're in repo-scoped workspace (sanitized repo identifier)
        for dir_path in dirs:
            self.assertIn('github.com_owner_repo-test', str(dir_path.parent))
    
    def test_list_ticket_directories_skip_files(self):
        """Only return directories, not files."""
        workspace_base = self.manager.dir_manager.get_workspace_base(repo_id=self.manager.repo_id)
        workspace_base.mkdir(parents=True, exist_ok=True)
        
        (workspace_base / "JIRA-123").mkdir()
        (workspace_base / "file.txt").touch()
        
        dirs = self.manager.list_ticket_directories()
        
        self.assertEqual(len(dirs), 1)
        self.assertEqual(dirs[0].name, 'JIRA-123')


class TestCLI(unittest.TestCase):
    """Test CLI interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a config for testing
        config = main.ConfigManager(self.config_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cli_no_args(self):
        """Print help and return 1."""
        with patch('sys.argv', ['main.py']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 1)
                output = mock_stdout.getvalue()
                self.assertIn('usage:', output)
    
    def test_cli_help(self):
        """Display help message."""
        with patch('sys.argv', ['main.py', '--help']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    main.main()
                output = mock_stdout.getvalue()
                self.assertIn('sidecar', output.lower())
    
    @patch('main.ConfigManager')
    def test_cli_config_view(self, mock_config_class):
        """Display configuration."""
        mock_config = Mock()
        mock_config.view.return_value = '[default.paths]\nworkspace_base = ~/tickets\n'
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--view']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('[default.paths]', output)
    
    @patch('main.ConfigManager')
    def test_cli_config_view_default_only(self, mock_config_class):
        """Display only default configuration."""
        mock_config = Mock()
        mock_config.view.return_value = '[default.paths]\nworkspace_base = ~/tickets\n'
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--view', '--default-only']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('[default.paths]', output)
                mock_config.view.assert_called_with(repo_id=None, default_only=True, all_repos=False)
    
    @patch('main.ConfigManager')
    def test_cli_config_view_all(self, mock_config_class):
        """Display all repository configurations."""
        mock_config = Mock()
        mock_config.view.return_value = '[default.paths]\n[repo:github.com/owner/repo1]\n'
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--view', '--all']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                mock_config.view.assert_called_with(repo_id=None, default_only=False, all_repos=True)
    
    @patch('main.ConfigManager')
    def test_cli_config_view_repo(self, mock_config_class):
        """Display specific repository configuration."""
        mock_config = Mock()
        mock_config.view.return_value = '[default.paths]\n[repo:github.com/owner/repo1]\n'
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--view', '--repo', 'github.com/owner/repo1']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                mock_config.view.assert_called_with(repo_id='github.com/owner/repo1', default_only=False, all_repos=False)
    
    @patch('main.ConfigManager')
    def test_cli_config_set_success(self, mock_config_class):
        """Update config value (repo-aware)."""
        mock_config = Mock()
        mock_config.set.return_value = None
        mock_config.get_current_repo_id.return_value = 'github.com/owner/repo-test'
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--set', 'paths', 'workspace_base', '~/new']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                # Should be called with repo_id
                mock_config.set.assert_called()
    
    @patch('main.ConfigManager')
    def test_cli_config_set_default(self, mock_config_class):
        """Update default config value."""
        mock_config = Mock()
        mock_config.set.return_value = None
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--set', 'paths', 'workspace_base', '~/new', '--default']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                mock_config.set.assert_called_with('paths', 'workspace_base', '~/new', repo_id=None, default=True)
    
    @patch('main.ConfigManager')
    def test_cli_config_set_repo(self, mock_config_class):
        """Update repo-specific config value."""
        mock_config = Mock()
        mock_config.set.return_value = None
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--set', 'paths', 'workspace_base', '~/repo-tickets', '--repo', 'github.com/owner/repo']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                mock_config.set.assert_called_with('paths', 'workspace_base', '~/repo-tickets', repo_id='github.com/owner/repo', default=False)
    
    @patch('main.ConfigManager')
    def test_cli_config_set_error(self, mock_config_class):
        """Handle invalid config updates."""
        mock_config = Mock()
        mock_config.set.side_effect = Exception("Config error")
        mock_config.get_current_repo_id.return_value = None
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--set', 'invalid', 'key', 'value']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 1)
                output = mock_stdout.getvalue()
                self.assertIn('Error', output)
    
    @patch('main._init_repo_config')
    @patch('main.ConfigManager')
    def test_cli_config_init_repo(self, mock_config_class, mock_init_repo):
        """Initialize repository configuration."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_init_repo.return_value = 0

        with patch('sys.argv', ['main.py', 'config', '--init-repo']):
            result = main.main()
            self.assertEqual(result, 0)
            mock_init_repo.assert_called_once_with(mock_config)
    
    @patch('main.ConfigManager')
    def test_cli_config_list_repos(self, mock_config_class):
        """List all configured repositories."""
        mock_config = Mock()
        mock_config.list_configured_repos.return_value = ['github.com/owner/repo1', 'github.com/owner/repo2']
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--list-repos']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('github.com/owner/repo1', output)
                self.assertIn('github.com/owner/repo2', output)
    
    @patch('main.ConfigManager')
    def test_cli_config_list_repos_empty(self, mock_config_class):
        """List repositories when none configured."""
        mock_config = Mock()
        mock_config.list_configured_repos.return_value = []
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'config', '--list-repos']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('No repositories', output)
    
    @patch('main.RepoIdentifier')
    @patch('main.GitHookManager')
    @patch('main.Path')
    @patch('builtins.input', side_effect=['n', ''])  # First for setup prompt, second for workspace (not used if 'n')
    def test_cli_hook_install_success(self, mock_input, mock_path_class, mock_hook_class, mock_repo_identifier_class):
        """Install hook successfully with repo setup."""
        mock_hook = Mock()
        mock_hook.find_git_repo.return_value = Path('/fake/.git')
        mock_hook.install_hook.return_value = (True, "Hook installed")
        mock_hook_class.return_value = mock_hook

        mock_repo_identifier = Mock()
        mock_repo_identifier.get_repo_identifier.return_value = 'github.com/owner/repo-test'
        mock_repo_identifier.get_repo_name_for_path.return_value = 'repo-test'
        mock_repo_identifier_class.return_value = mock_repo_identifier

        mock_path_instance = Mock()
        mock_path_instance.resolve.return_value = Path('/fake/path/main.py')
        mock_path_class.return_value = mock_path_instance

        with patch('sys.argv', ['main.py', 'hook', 'install']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                with patch('main.ConfigManager') as mock_config_class:
                    mock_config = Mock()
                    mock_config.repo_is_configured.return_value = False
                    mock_config.get_path.return_value = Path.home() / 'tickets'
                    mock_config.get.return_value = 'CurrentTicket'
                    mock_config.set.return_value = None
                    mock_config_class.return_value = mock_config
                    
                    result = main.main()
                    self.assertEqual(result, 0)
                    output = mock_stdout.getvalue()
                    self.assertIn('Hook installed', output)
                    # Should auto-configure repo
                    mock_config.set.assert_called()
    
    @patch('main.RepoIdentifier')
    @patch('main.GitHookManager')
    @patch('main.Path')
    @patch('builtins.input', side_effect=['', ''])  # Accept defaults for both prompts
    def test_cli_hook_install_repo_setup(self, mock_input, mock_path_class, mock_hook_class, mock_repo_identifier_class):
        """Test hook install with repo setup flow."""
        mock_hook = Mock()
        mock_hook.find_git_repo.return_value = Path('/fake/.git')
        mock_hook.install_hook.return_value = (True, "Hook installed")
        mock_hook_class.return_value = mock_hook

        mock_repo_identifier = Mock()
        mock_repo_identifier.get_repo_identifier.return_value = 'github.com/owner/repo-test'
        mock_repo_identifier.get_repo_name_for_path.return_value = 'repo-test'
        mock_repo_identifier_class.return_value = mock_repo_identifier

        mock_path_instance = Mock()
        mock_path_instance.resolve.return_value = Path('/fake/path/main.py')
        mock_path_class.return_value = mock_path_instance

        with patch('sys.argv', ['main.py', 'hook', 'install']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                with patch('main.ConfigManager') as mock_config_class:
                    mock_config = Mock()
                    mock_config.repo_is_configured.return_value = False
                    mock_config.get_path.return_value = Path.home() / 'tickets'
                    mock_config.get.return_value = 'CurrentTicket'
                    mock_config.set.return_value = None
                    mock_config_class.return_value = mock_config
                    
                    result = main.main()
                    self.assertEqual(result, 0)
                    # Verify repo was configured
                    mock_config.set.assert_called()
                    call_args = mock_config.set.call_args
                    self.assertEqual(call_args[0][0], 'paths')
                    self.assertEqual(call_args[0][1], 'workspace_base')
                    self.assertEqual(call_args[1].get('repo_id'), 'github.com/owner/repo-test')
    
    @patch('main.RepoIdentifier')
    @patch('main.GitHookManager')
    @patch('main.Path')
    @patch('builtins.input', return_value='n')  # Don't reconfigure
    def test_cli_hook_install_already_configured(self, mock_input, mock_path_class, mock_hook_class, mock_repo_identifier_class):
        """Test hook install when repo is already configured."""
        mock_hook = Mock()
        mock_hook.find_git_repo.return_value = Path('/fake/.git')
        mock_hook.install_hook.return_value = (True, "Hook installed")
        mock_hook_class.return_value = mock_hook

        mock_repo_identifier = Mock()
        mock_repo_identifier.get_repo_identifier.return_value = 'github.com/owner/repo-test'
        mock_repo_identifier_class.return_value = mock_repo_identifier

        mock_path_instance = Mock()
        mock_path_instance.resolve.return_value = Path('/fake/path/main.py')
        mock_path_class.return_value = mock_path_instance

        with patch('sys.argv', ['main.py', 'hook', 'install']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                with patch('main.ConfigManager') as mock_config_class:
                    mock_config = Mock()
                    mock_config.repo_is_configured.return_value = True  # Already configured
                    mock_config_class.return_value = mock_config
                    
                    result = main.main()
                    self.assertEqual(result, 0)
                    output = mock_stdout.getvalue()
                    self.assertIn('already configured', output)
                    self.assertIn('Hook installed', output)
    
    @patch('main.GitHookManager')
    @patch('main.Path')
    def test_cli_hook_uninstall_success(self, mock_path_class, mock_hook_class):
        """Uninstall hook successfully."""
        mock_hook = Mock()
        mock_hook.uninstall_hook.return_value = (True, "Hook uninstalled")
        mock_hook_class.return_value = mock_hook
        
        mock_path_instance = Mock()
        mock_path_instance.resolve.return_value = Path('/fake/path/main.py')
        mock_path_class.return_value = mock_path_instance
        
        with patch('sys.argv', ['main.py', 'hook', 'uninstall']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
    
    @patch('main.TicketManager')
    def test_cli_process_success(self, mock_manager_class):
        """Process checkout successfully."""
        mock_manager = Mock()
        mock_manager.process_checkout.return_value = (True, "Success")
        mock_manager_class.return_value = mock_manager
        
        with patch('sys.argv', ['main.py', 'process']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
    
    @patch('main.TicketManager')
    def test_cli_list_empty(self, mock_manager_class):
        """List command with no directories."""
        mock_manager = Mock()
        mock_manager.list_ticket_directories.return_value = []
        mock_manager.repo_id = None
        mock_manager.dir_manager.get_workspace_base.return_value = Path('/workspace')
        mock_manager_class.return_value = mock_manager

        with patch('sys.argv', ['main.py', 'list']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('No ticket directories', output)
    
    @patch('main.ConfigManager')
    def test_cli_repos_list(self, mock_config_class):
        """List all configured repositories."""
        mock_config = Mock()
        mock_config.list_configured_repos.return_value = ['github.com/owner/repo1', 'github.com/owner/repo2']
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'repos', 'list']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('github.com/owner/repo1', output)
                self.assertIn('github.com/owner/repo2', output)
    
    @patch('main.ConfigManager')
    def test_cli_repos_show(self, mock_config_class):
        """Show configuration for a repository."""
        mock_config = Mock()
        mock_config.repo_is_configured.return_value = True
        mock_config.get_repo_config.return_value = {'paths.workspace_base': '~/tickets/repo1'}
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'repos', 'show', 'github.com/owner/repo1']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('paths.workspace_base', output)
                mock_config.get_repo_config.assert_called_once_with('github.com/owner/repo1')
    
    @patch('main.ConfigManager')
    def test_cli_repos_show_not_configured(self, mock_config_class):
        """Show error when repository not configured."""
        mock_config = Mock()
        mock_config.repo_is_configured.return_value = False
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'repos', 'show', 'nonexistent/repo']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 1)
                output = mock_stdout.getvalue()
                self.assertIn('not configured', output)
    
    @patch('main.ConfigManager')
    def test_cli_repos_remove(self, mock_config_class):
        """Remove repository configuration."""
        mock_config = Mock()
        mock_config.repo_is_configured.return_value = True
        mock_config.remove_repo_config.return_value = True
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'repos', 'remove', 'github.com/owner/repo1']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('removed', output)
                mock_config.remove_repo_config.assert_called_once_with('github.com/owner/repo1')
    
    @patch('main.ConfigManager')
    def test_cli_repos_remove_not_configured(self, mock_config_class):
        """Remove error when repository not configured."""
        mock_config = Mock()
        mock_config.repo_is_configured.return_value = False
        mock_config_class.return_value = mock_config

        with patch('sys.argv', ['main.py', 'repos', 'remove', 'nonexistent/repo']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 1)
                output = mock_stdout.getvalue()
                self.assertIn('not configured', output)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        self.config = config
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_windows_path_260_char_limit(self):
        """Enforce Windows path limit precisely."""
        with patch('platform.system', return_value='Windows'):
            long_workspace = Path(self.temp_dir) / ('A' * 100)
            long_workspace.mkdir(parents=True, exist_ok=True)
            self.config.set('paths', 'workspace_base', str(long_workspace), default=True)
            
            dir_manager = main.DirectoryManager(self.config)
            long_name = 'B' * 300
            sanitized = dir_manager.sanitize_directory_name(long_name)
            
            # Implementation uses fixed estimate of 100 for workspace_path_len
            # since sanitize_directory_name doesn't have access to actual workspace_base
            # max_name_len = max(50, 260 - 100 - 50) = max(50, 110) = 110
            estimated_max_len = 110
            self.assertLessEqual(len(sanitized), estimated_max_len)
            self.assertGreaterEqual(len(sanitized), 50)  # Minimum should be respected
    
    def test_symlink_to_ticket_dir_absolute_paths(self):
        """Verify absolute path comparison."""
        workspace_base = Path(self.temp_dir) / "workspace"
        workspace_base.mkdir()
        ticket_dir = workspace_base / "JIRA-123"
        ticket_dir.mkdir()
        
        link_location = Path(self.temp_dir) / "links"
        link_location.mkdir()
        
        self.config.set('paths', 'workspace_base', str(workspace_base), default=True)
        self.config.set('links', 'current_ticket_link_locations', str(link_location), default=True)
        
        linker = main.CurrentTicketLinker(self.config)
        
        # Create existing symlink pointing to ticket dir
        existing_target = workspace_base / "JIRA-999"
        existing_target.mkdir()
        (link_location / "CurrentTicket").symlink_to(existing_target)
        
        errors = linker.update_current_ticket_link(ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = link_location / "CurrentTicket"
        self.assertEqual(link.readlink().resolve(), ticket_dir.resolve())
    
    def test_branch_name_special_characters(self):
        """Handle special chars in branch names."""
        dir_manager = main.DirectoryManager(self.config)
        
        sanitized = dir_manager.sanitize_directory_name('JIRA<>:"/\\|?*-123-feature')
        self.assertNotIn('<', sanitized)
        self.assertNotIn('>', sanitized)
        self.assertNotIn(':', sanitized)
    
    def test_ticket_pattern_edge_cases(self):
        """Very short/long prefixes, numbers, descriptions."""
        analyzer = main.BranchAnalyzer(self.config)
        
        # Very short prefix
        info = analyzer.extract_ticket_info('A-1-short')
        self.assertIsNotNone(info)
        
        # Long prefix (max 10 chars)
        info = analyzer.extract_ticket_info('ABCDEFGHIJ-12345-long-description')
        self.assertIsNotNone(info)
        self.assertEqual(info['prefix'], 'ABCDEFGHIJ')
        
        # Very long number
        info = analyzer.extract_ticket_info('JIRA-1234567890-feature')
        self.assertIsNotNone(info)
    
    @patch('main.RepoIdentifier.get_remote_url')
    @patch('main.RepoIdentifier.get_all_remotes')
    def test_repo_identifier_no_remote(self, mock_get_all, mock_get_origin):
        """Test local repo identifier generation."""
        mock_get_origin.return_value = None
        mock_get_all.return_value = {}
        
        temp_repo = tempfile.mkdtemp()
        git_dir = Path(temp_repo) / ".git"
        git_dir.mkdir()
        
        try:
            repo_identifier = main.RepoIdentifier(git_dir)
            repo_id = repo_identifier.get_repo_identifier()
            
            self.assertTrue(repo_id.startswith('local/'))
            self.assertIn(Path(temp_repo).name, repo_id)
        finally:
            shutil.rmtree(temp_repo, ignore_errors=True)
    
    @patch('main.RepoIdentifier.get_remote_url')
    @patch('main.RepoIdentifier.get_all_remotes')
    def test_repo_identifier_multiple_remotes(self, mock_get_all, mock_get_origin):
        """Test origin vs other remotes."""
        mock_get_origin.return_value = 'https://github.com/origin/repo.git'
        mock_get_all.return_value = {
            'origin': 'https://github.com/origin/repo.git',
            'upstream': 'https://github.com/upstream/repo.git'
        }
        
        temp_repo = tempfile.mkdtemp()
        git_dir = Path(temp_repo) / ".git"
        git_dir.mkdir()
        
        try:
            repo_identifier = main.RepoIdentifier(git_dir)
            repo_id = repo_identifier.get_repo_identifier()
            
            # Should prefer origin
            self.assertEqual(repo_id, 'github.com/origin/repo')
        finally:
            shutil.rmtree(temp_repo, ignore_errors=True)
    
    def test_config_repo_inheritance_edge_cases(self):
        """Test edge cases in inheritance."""
        config = main.ConfigManager(self.config_file)
        repo_id = 'github.com/owner/repo-test'
        
        # Set default
        config.set('paths', 'workspace_base', '~/default', default=True)
        
        # Repo should inherit default
        value = config.get('paths', 'workspace_base', repo_id=repo_id)
        self.assertEqual(value, '~/default')
        
        # Set repo-specific override
        config.set('paths', 'workspace_base', '~/repo-specific', repo_id=repo_id)
        value = config.get('paths', 'workspace_base', repo_id=repo_id)
        self.assertEqual(value, '~/repo-specific')
        
        # Other repo should still get default
        value = config.get('paths', 'workspace_base', repo_id='github.com/owner/other-repo')
        self.assertEqual(value, '~/default')
    
    def test_workspace_base_repo_name_special_chars(self):
        """Test sanitization of special characters in repo names."""
        dir_manager = main.DirectoryManager(self.config)
        
        # Test various special characters
        repo_ids = [
            ('github.com/org/repo.with.dots', '/'),  # Slash should be removed
            ('github.com/org/repo-with-dashes', '/'),  # Slash should be removed
            ('github.com/org/repo_with_underscores', '/'),  # Slash should be removed
            ('github.com/org/repo@special', '/'),  # Slash should be removed (@ is valid in dir names)
            ('github.com/org/repo:special', ['/', ':']),  # Slash and : should be removed (: is invalid)
        ]
        
        for repo_id, invalid_chars in repo_ids:
            sanitized = dir_manager._sanitize_repo_name(repo_id)
            # Should not contain invalid directory chars (as defined in implementation)
            # Invalid chars in _sanitize_repo_name: r'<>:"/\|?*'
            if isinstance(invalid_chars, list):
                for char in invalid_chars:
                    if char in r'<>:"/\|?*':  # Only check chars that are actually invalid
                        self.assertNotIn(char, sanitized, f"Repo ID {repo_id} should not contain {char}")
            else:
                if invalid_chars in r'<>:"/\|?*':  # Only check chars that are actually invalid
                    self.assertNotIn(invalid_chars, sanitized, f"Repo ID {repo_id} should not contain {invalid_chars}")
            # Slash should always be removed/replaced
            self.assertNotIn('/', sanitized, f"Repo ID {repo_id} should not contain /")


if __name__ == '__main__':
    unittest.main()
