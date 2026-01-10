#!/usr/bin/env python3
"""
Comprehensive test suite for DirTickets using Python standard library.
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
        self.config_dir = Path(self.temp_dir) / ".dirtickets"
        self.config_file = self.config_dir / "config.ini"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_config_creation(self):
        """Verify default config is created with correct sections/keys."""
        config = main.ConfigManager(self.config_file)
        
        self.assertTrue(self.config_file.exists())
        self.assertEqual(config.get('paths', 'workspace_base'), '~/tickets')
        self.assertEqual(config.get('paths', 'tools_library_path'), '~/tools')
        self.assertIn('main', config.get_list('branches', 'standard_branches'))
        self.assertEqual(config.get('ticket_pattern', 'prefix_pattern'), '[A-Za-z]{1,10}')
    
    def test_config_file_loading(self):
        """Load existing config file."""
        # Create a custom config file
        config_content = """[paths]
workspace_base = ~/custom_tickets
tools_library_path = ~/custom_tools

[branches]
standard_branches = main, develop

[ticket_pattern]
prefix_pattern = [A-Z]{1,5}
separator = [-_]
number_pattern = \\d+
description_pattern = .*

[links]
current_ticket_link_locations = ~/Desktop
tools_to_link = tool1, tool2
"""
        with open(self.config_file, 'w') as f:
            f.write(config_content)
        
        config = main.ConfigManager(self.config_file)
        
        self.assertEqual(config.get('paths', 'workspace_base'), '~/custom_tickets')
        self.assertEqual(config.get('paths', 'tools_library_path'), '~/custom_tools')
        self.assertEqual(len(config.get_list('branches', 'standard_branches')), 2)
    
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
        config.set('test', 'list_with_spaces', 'a, b, c')
        result = config.get_list('test', 'list_with_spaces')
        self.assertEqual(result, ['a', 'b', 'c'])
    
    def test_set_method(self):
        """Update config values, verify persistence."""
        config = main.ConfigManager(self.config_file)
        
        config.set('paths', 'workspace_base', '~/new_tickets')
        self.assertEqual(config.get('paths', 'workspace_base'), '~/new_tickets')
        
        # Reload and verify persistence
        config2 = main.ConfigManager(self.config_file)
        self.assertEqual(config2.get('paths', 'workspace_base'), '~/new_tickets')
    
    def test_set_new_section(self):
        """Create new section when setting value."""
        config = main.ConfigManager(self.config_file)
        
        config.set('new_section', 'new_key', 'new_value')
        self.assertTrue('new_section' in [s for s in config.config.sections()])
        self.assertEqual(config.get('new_section', 'new_key'), 'new_value')
    
    def test_view_method(self):
        """Format config output correctly."""
        config = main.ConfigManager(self.config_file)
        
        output = config.view()
        self.assertIn('[paths]', output)
        self.assertIn('workspace_base = ~/tickets', output)
        self.assertIn('[branches]', output)
    
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
        self.config.set('branches', 'standard_branches', 'custom1, custom2')
        analyzer = main.BranchAnalyzer(self.config)
        
        self.assertTrue(analyzer.is_standard_branch('custom1'))
        self.assertTrue(analyzer.is_standard_branch('custom2'))
        self.assertFalse(analyzer.is_standard_branch('main'))
    
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
        self.config.set('ticket_pattern', 'prefix_pattern', '[A-Z]{1,3}')
        self.config.set('ticket_pattern', 'separator', '-')
        self.config.set('ticket_pattern', 'number_pattern', '\\d{3}')
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
        config.set('paths', 'workspace_base', str(self.workspace_base))
        
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
        self.config.set('paths', 'workspace_base', str(long_workspace))
        
        with patch('platform.system', return_value='Windows'):
            dir_manager = main.DirectoryManager(self.config)
            long_name = 'B' * 300
            sanitized = dir_manager.sanitize_directory_name(long_name)
            # Should still respect minimum
            self.assertGreaterEqual(len(sanitized), 50)
    
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
        config.set('paths', 'tools_library_path', str(self.tools_lib))
        config.set('links', 'tools_to_link', 'notebooks, scripts, utils')
        
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
        
        self.config.set('links', 'tools_to_link', 'notebooks, script.py')
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
        self.assertTrue((self.ticket_dir / 'script.py').is_symlink())
    
    def test_link_tools_missing_library_path(self):
        """Error when tools library doesn't exist."""
        self.config.set('paths', 'tools_library_path', '/nonexistent/path')
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
        
        self.config.set('links', 'tools_to_link', 'notebooks')
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.ticket_dir / 'notebooks').is_symlink())
    
    def test_link_tools_empty_config(self):
        """Handle empty tools_to_link list."""
        self.config.set('links', 'tools_to_link', '')
        linker = main.ToolsLinker(self.config)
        
        errors = linker.link_tools(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)


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
        config.set('paths', 'workspace_base', str(self.workspace_base))
        config.set('links', 'current_ticket_link_locations', str(self.link_location))
        
        self.config = main.ConfigManager(self.config_file)
        self.current_ticket_linker = main.CurrentTicketLinker(self.config)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
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
                       f'{self.link_location}, {link_location2}')
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        self.assertTrue((self.link_location / "CurrentTicket").is_symlink())
        self.assertTrue((link_location2 / "CurrentTicket").is_symlink())
    
    def test_update_current_ticket_link_create_directory(self):
        """Create parent directory if missing."""
        missing_dir = Path(self.temp_dir) / "missing" / "path"
        self.config.set('links', 'current_ticket_link_locations', str(missing_dir))
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
        # Test with tilde path
        tilde_path = Path.home() / "test_links"
        tilde_path.mkdir(exist_ok=True)
        
        self.config.set('links', 'current_ticket_link_locations', '~/test_links')
        linker = main.CurrentTicketLinker(self.config)
        
        errors = linker.update_current_ticket_link(self.ticket_dir)
        
        self.assertEqual(len(errors), 0)
        link = tilde_path / "CurrentTicket"
        self.assertTrue(link.is_symlink())
        
        # Cleanup
        if link.exists():
            link.unlink()
        if tilde_path.exists():
            tilde_path.rmdir()
    
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
            self.assertIn('DirTickets', content)
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
            self.assertIn('DirTickets', content)
    
    def test_uninstall_hook_success(self):
        """Remove hook file."""
        hook_file = self.hooks_dir / "post-checkout"
        hook_file.write_text("#!/bin/sh\n# DirTickets post-checkout hook\npython3 main.py process\n")
        
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
        """Error when hook exists but isn't DirTickets hook."""
        hook_file = self.hooks_dir / "post-checkout"
        hook_file.write_text("#!/bin/sh\necho 'other hook'\n")
        
        with patch('pathlib.Path.cwd', return_value=Path(self.temp_dir)):
            success, message = self.hook_manager.uninstall_hook()
            
            self.assertFalse(success)
            self.assertIn('not a DirTickets hook', message)
            self.assertTrue(hook_file.exists())  # Should not be deleted


class TestTicketManager(unittest.TestCase):
    """Test TicketManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.ini"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = main.ConfigManager(self.config_file)
        config.set('paths', 'workspace_base', str(Path(self.temp_dir) / "workspace"))
        config.set('paths', 'tools_library_path', str(Path(self.temp_dir) / "tools"))
        config.set('links', 'current_ticket_link_locations', str(Path(self.temp_dir) / "links"))
        
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
    
    def test_list_ticket_directories_empty(self):
        """Return empty list when no directories."""
        dirs = self.manager.list_ticket_directories()
        self.assertEqual(dirs, [])
    
    def test_list_ticket_directories_multiple(self):
        """List all ticket directories."""
        workspace_base = self.manager.config.get_path('paths', 'workspace_base')
        workspace_base.mkdir(parents=True, exist_ok=True)
        
        (workspace_base / "JIRA-123").mkdir()
        (workspace_base / "TICKET-456").mkdir()
        
        dirs = self.manager.list_ticket_directories()
        
        self.assertEqual(len(dirs), 2)
        names = {d.name for d in dirs}
        self.assertIn('JIRA-123', names)
        self.assertIn('TICKET-456', names)
    
    def test_list_ticket_directories_skip_files(self):
        """Only return directories, not files."""
        workspace_base = self.manager.config.get_path('paths', 'workspace_base')
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
                self.assertIn('DirTickets', output)
    
    @patch('main.ConfigManager')
    def test_cli_config_view(self, mock_config_class):
        """Display configuration."""
        mock_config = Mock()
        mock_config.view.return_value = '[paths]\nworkspace_base = ~/tickets\n'
        mock_config_class.return_value = mock_config
        
        with patch('sys.argv', ['main.py', 'config', '--view']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('[paths]', output)
    
    @patch('main.ConfigManager')
    def test_cli_config_set_success(self, mock_config_class):
        """Update config value."""
        mock_config = Mock()
        mock_config.set.return_value = None
        mock_config_class.return_value = mock_config
        
        with patch('sys.argv', ['main.py', 'config', '--set', 'paths', 'workspace_base', '~/new']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                mock_config.set.assert_called_once_with('paths', 'workspace_base', '~/new')
    
    @patch('main.ConfigManager')
    def test_cli_config_set_error(self, mock_config_class):
        """Handle invalid config updates."""
        mock_config = Mock()
        mock_config.set.side_effect = Exception("Config error")
        mock_config_class.return_value = mock_config
        
        with patch('sys.argv', ['main.py', 'config', '--set', 'invalid', 'key', 'value']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 1)
                output = mock_stdout.getvalue()
                self.assertIn('Error', output)
    
    @patch('main.GitHookManager')
    @patch('main.Path')
    def test_cli_hook_install_success(self, mock_path_class, mock_hook_class):
        """Install hook successfully."""
        mock_hook = Mock()
        mock_hook.install_hook.return_value = (True, "Hook installed")
        mock_hook_class.return_value = mock_hook
        
        mock_path_instance = Mock()
        mock_path_instance.resolve.return_value = Path('/fake/path/main.py')
        mock_path_class.return_value = mock_path_instance
        
        with patch('sys.argv', ['main.py', 'hook', 'install']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
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
        mock_manager.config.get_path.return_value = Path('/workspace')
        mock_manager_class.return_value = mock_manager
        
        with patch('sys.argv', ['main.py', 'list']):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                result = main.main()
                self.assertEqual(result, 0)
                output = mock_stdout.getvalue()
                self.assertIn('No ticket directories', output)


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
            self.config.set('paths', 'workspace_base', str(long_workspace))
            
            dir_manager = main.DirectoryManager(self.config)
            long_name = 'B' * 300
            sanitized = dir_manager.sanitize_directory_name(long_name)
            
            workspace_len = len(str(long_workspace.resolve()))
            max_len = max(50, 260 - workspace_len - 50)
            self.assertLessEqual(len(sanitized), max_len)
    
    def test_symlink_to_ticket_dir_absolute_paths(self):
        """Verify absolute path comparison."""
        workspace_base = Path(self.temp_dir) / "workspace"
        workspace_base.mkdir()
        ticket_dir = workspace_base / "JIRA-123"
        ticket_dir.mkdir()
        
        link_location = Path(self.temp_dir) / "links"
        link_location.mkdir()
        
        self.config.set('paths', 'workspace_base', str(workspace_base))
        self.config.set('links', 'current_ticket_link_locations', str(link_location))
        
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


if __name__ == '__main__':
    unittest.main()
