#!/usr/bin/env python3
"""
Test suite for KSI Hook Monitor
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import json
import socket
import sys
import io
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ksi_claude_code.ksi_hook_monitor import (
    KSIHookMonitor, HookConfig, HookLogger, ExitStrategy,
    HookError, ConfigurationError, 
    MinimalSyncClient, KSIConnectionError, KSIResponseError
)

class TestHookConfig(unittest.TestCase):
    """Test configuration management"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = HookConfig()
        self.assertIsNone(config.socket_path)
        self.assertEqual(config.timestamp_file, "/tmp/ksi_hook_last_timestamp.txt")
        self.assertEqual(config.mode_file, "/tmp/ksi_hook_mode.txt")
        self.assertEqual(config.default_mode, "summary")
        self.assertEqual(config.event_limit, 20)
        self.assertEqual(config.connection_timeout, 2.0)
        self.assertFalse(config.debug_log)
    
    def test_config_from_env(self):
        """Test loading configuration from environment variables"""
        with patch.dict(os.environ, {
            'KSI_SOCKET_PATH': '/custom/socket.sock',
            'KSI_HOOK_MODE': 'verbose',
            'KSI_HOOK_EVENT_LIMIT': '50',
            'KSI_HOOK_TIMEOUT': '5.0',
            'KSI_HOOK_DEBUG': 'true'
        }):
            config = HookConfig.from_env()
            self.assertEqual(config.socket_path, '/custom/socket.sock')
            self.assertEqual(config.default_mode, 'verbose')
            self.assertEqual(config.event_limit, 50)
            self.assertEqual(config.connection_timeout, 5.0)
            self.assertTrue(config.debug_log)

class TestExitStrategy(unittest.TestCase):
    """Test exit strategy management"""
    
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_exit_with_feedback(self, mock_stdout):
        """Test exit with JSON feedback"""
        with self.assertRaises(SystemExit) as cm:
            ExitStrategy.exit_with_feedback("[KSI] Test message")
        
        self.assertEqual(cm.exception.code, 0)
        output = json.loads(mock_stdout.getvalue())
        self.assertEqual(output["decision"], "block")
        self.assertEqual(output["reason"], "[KSI] Test message")
    
    def test_exit_silent(self):
        """Test silent exit"""
        with self.assertRaises(SystemExit) as cm:
            ExitStrategy.exit_silent()
        
        self.assertEqual(cm.exception.code, 0)

class TestHookLogger(unittest.TestCase):
    """Test structured logging"""
    
    def setUp(self):
        self.config = HookConfig()
        self.logger = HookLogger(self.config)
    
    @patch('builtins.open', new_callable=mock_open)
    def test_log_diagnostic(self, mock_file):
        """Test diagnostic logging"""
        self.logger.log_diagnostic("Test message")
        mock_file.assert_called_with(Path("/tmp/ksi_hook_diagnostic.log"), "a")
        handle = mock_file()
        handle.write.assert_called()
        written = handle.write.call_args[0][0]
        self.assertIn("Test message", written)
    
    @patch('builtins.open', new_callable=mock_open)
    def test_log_debug_enabled(self, mock_file):
        """Test debug logging when enabled"""
        self.config.debug_log = True
        logger = HookLogger(self.config)
        logger.log_debug("Debug message")
        mock_file.assert_called_with(Path("/tmp/ksi_hook_debug.log"), "a")
        handle = mock_file()
        handle.write.assert_called()
        written = handle.write.call_args[0][0]
        self.assertIn("Debug message", written)
    
    def test_log_debug_disabled(self):
        """Test debug logging when disabled"""
        with patch('builtins.open', new_callable=mock_open) as mock_file:
            self.logger.log_debug("Debug message")
            # Should not open file when debug is disabled
            mock_file.assert_not_called()

class TestKSIHookMonitor(unittest.TestCase):
    """Test main hook monitor functionality"""
    
    def setUp(self):
        self.config = HookConfig(socket_path="/tmp/test.sock")
        with patch('ksi_claude_code.ksi_hook_monitor.MinimalSyncClient'):
            self.monitor = KSIHookMonitor(self.config)
    
    @patch('pathlib.Path.exists')
    def test_find_socket_path(self, mock_exists):
        """Test socket path discovery"""
        monitor = KSIHookMonitor()
        mock_exists.side_effect = [False, True]  # First path doesn't exist, second does
        
        path = monitor._find_socket_path()
        self.assertTrue(str(path).endswith("var/run/daemon.sock"))
    
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.exists')
    def test_load_last_timestamp(self, mock_exists, mock_read):
        """Test loading last timestamp"""
        monitor = KSIHookMonitor()
        mock_exists.return_value = True
        mock_read.return_value = "1234567890.5"
        
        timestamp = monitor._load_last_timestamp()
        self.assertEqual(timestamp, 1234567890.5)
    
    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.exists')
    def test_load_verbosity_mode(self, mock_exists, mock_read):
        """Test loading verbosity mode"""
        monitor = KSIHookMonitor()
        mock_exists.return_value = True
        mock_read.return_value = "verbose"
        
        mode = monitor._load_verbosity_mode()
        self.assertEqual(mode, "verbose")
    
    def test_group_repetitive_events(self):
        """Test event grouping logic"""
        events = [
            {"event_name": "completion:progress", "timestamp": 1},
            {"event_name": "completion:progress", "timestamp": 2},
            {"event_name": "completion:progress", "timestamp": 3},
            {"event_name": "agent:spawn", "timestamp": 4},
            {"event_name": "completion:progress", "timestamp": 5},
        ]
        
        grouped = self.monitor._group_repetitive_events(events)
        
        # Should group the 4 completion:progress events
        completion_groups = [g for g in grouped if g.get("type") == "completion:progress"]
        self.assertEqual(len(completion_groups), 1)
        self.assertEqual(completion_groups[0]["count"], 4)
    
    def test_format_event_summary(self):
        """Test event summary formatting"""
        events = [
            {"event_name": "agent:spawn:success", "timestamp": 1700000000, 
             "data": {"agent_id": "test123"}},
            {"event_name": "completion:result", "timestamp": 1700000001, 
             "data": {"session_id": "sess123", "result": {"response": {"is_error": False}}}},
        ]
        
        summary, _ = self.monitor.format_event_summary(events)
        
        self.assertIn("spawn:test123", summary)
        self.assertIn("completion:sess123", summary)
        self.assertIn("✓", summary)  # Success indicator
    
    def test_handle_mode_command(self):
        """Test mode command handling"""
        # Test mode change
        with patch.object(self.monitor, 'save_verbosity_mode') as mock_save:
            with self.assertRaises(SystemExit) as cm:
                handled = self.monitor.handle_mode_command("echo ksi_verbose")
            
            self.assertEqual(cm.exception.code, 0)
            mock_save.assert_called_with("verbose")
        
        # Test status command
        self.monitor.verbosity_mode = "summary"
        with self.assertRaises(SystemExit) as cm:
            handled = self.monitor.handle_mode_command("echo ksi_status")
        
        self.assertEqual(cm.exception.code, 0)
    
    def test_format_output_modes(self):
        """Test output formatting in different modes"""
        events = [{"event_name": "test:event", "timestamp": 1700000000}]
        agent_status = "No active agents."
        
        # Test summary mode
        self.monitor.verbosity_mode = "summary"
        output = self.monitor.format_output(events, agent_status)
        self.assertIn("[KSI:", output)
        self.assertIn("1 events", output)
        
        # Test verbose mode
        self.monitor.verbosity_mode = "verbose"
        output = self.monitor.format_output(events, agent_status)
        self.assertIn("[KSI: 1 new]", output)
        
        # Test silent mode
        self.monitor.verbosity_mode = "silent"
        output = self.monitor.format_output(events, agent_status)
        self.assertIsNone(output)
        
        # Test errors mode with no errors
        self.monitor.verbosity_mode = "errors"
        output = self.monitor.format_output(events, agent_status)
        self.assertIsNone(output)
    
    def test_should_process_command(self):
        """Test command filtering logic"""
        # Test skipped tools
        result = self.monitor.should_process_command("TodoRead", {})
        self.assertFalse(result)
        
        # Test unknown tool
        result = self.monitor.should_process_command("unknown", {})
        self.assertFalse(result)
        
        # Test KSI-related bash command
        with patch.object(self.monitor, '_load_ksi_indicators', return_value=["ksi_"]):
            result = self.monitor.should_process_command("Bash", {
                "tool_input": {"command": "ksi_check"}
            })
            self.assertTrue(result)
        
        # Test non-KSI bash command
        with patch.object(self.monitor, '_load_ksi_indicators', return_value=["ksi_"]):
            result = self.monitor.should_process_command("Bash", {
                "tool_input": {"command": "ls -la"}
            })
            self.assertFalse(result)
    
    @patch('builtins.open', new_callable=mock_open, read_data='ksi_\nKSI\nagent:\n')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_ksi_indicators(self, mock_exists, mock_file):
        """Test loading KSI indicators from file"""
        indicators = self.monitor._load_ksi_indicators()
        
        self.assertIn("ksi_", indicators)
        self.assertIn("KSI", indicators) 
        self.assertIn("agent:", indicators)
        self.assertEqual(len(indicators), 3)
    
    def test_get_recent_events(self):
        """Test getting recent events using MinimalSyncClient"""
        # Mock the client instance's send_event method
        self.monitor.client.send_event = Mock(return_value={"events": [{"event_name": "test", "timestamp": 123}]})
        
        events = self.monitor.get_recent_events()
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_name"], "test")
        self.monitor.client.send_event.assert_called_once_with("monitor:get_events", {
            "_silent": True,
            "event_patterns": None,
            "since": self.monitor.last_timestamp,
            "limit": 20,
            "reverse": True
        })
    
    def test_check_active_agents(self):
        """Test checking active agents using MinimalSyncClient"""
        # Mock the client instance's send_event method
        self.monitor.client.send_event = Mock(return_value={"agents": [
            {"agent_id": "agent1"},
            {"agent_id": "agent2"}
        ]})
        
        status = self.monitor.check_active_agents()
        
        self.assertEqual(status, "Agents[2]: agent1, agent2")
        self.monitor.client.send_event.assert_called_once_with("agent:list", {"_silent": True})

class TestMainFunction(unittest.TestCase):
    """Test main entry point"""
    
    @patch('sys.stdin')
    @patch('ksi_claude_code.ksi_hook_monitor.KSIHookMonitor')
    @patch('ksi_claude_code.ksi_hook_monitor.HookLogger')
    @patch('ksi_claude_code.ksi_hook_monitor.HookConfig.from_env')
    def test_main_success(self, mock_config, mock_logger, mock_monitor_class, mock_stdin):
        """Test successful main execution"""
        # Setup mocks
        mock_config.return_value = HookConfig()
        mock_stdin.read.return_value = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ksi_check"}
        })
        
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor
        mock_monitor.should_process_command.return_value = True
        mock_monitor.get_recent_events.return_value = []
        mock_monitor.check_active_agents.return_value = "No active agents."
        mock_monitor.format_output.return_value = "[KSI]"
        
        # Run main
        with self.assertRaises(SystemExit) as cm:
            from ksi_claude_code.ksi_hook_monitor import main
            main()
        
        self.assertEqual(cm.exception.code, 0)  # JSON feedback with exit 0
    
    @patch('sys.stdin')
    @patch('ksi_claude_code.ksi_hook_monitor.HookLogger')
    @patch('ksi_claude_code.ksi_hook_monitor.HookConfig.from_env')
    def test_main_invalid_input(self, mock_config, mock_logger, mock_stdin):
        """Test main with invalid JSON input"""
        mock_config.return_value = HookConfig()
        mock_stdin.read.return_value = "invalid json"
        
        with self.assertRaises(SystemExit) as cm:
            from ksi_claude_code.ksi_hook_monitor import main
            main()
        
        self.assertEqual(cm.exception.code, 0)  # Silent exit
    
    @patch('sys.stdin')
    @patch('ksi_claude_code.ksi_hook_monitor.KSIHookMonitor')
    @patch('ksi_claude_code.ksi_hook_monitor.HookLogger')
    @patch('ksi_claude_code.ksi_hook_monitor.HookConfig.from_env')
    def test_main_daemon_offline(self, mock_config, mock_logger, mock_monitor_class, mock_stdin):
        """Test main when daemon is offline"""
        # Setup mocks
        mock_config.return_value = HookConfig()
        mock_stdin.read.return_value = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ksi_check"}
        })
        
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor
        mock_monitor.should_process_command.return_value = True
        mock_monitor.get_recent_events.side_effect = KSIConnectionError("Connection refused")
        
        # Run main
        with self.assertRaises(SystemExit) as cm:
            from ksi_claude_code.ksi_hook_monitor import main
            main()
        
        self.assertEqual(cm.exception.code, 0)  # JSON feedback with exit 0

if __name__ == "__main__":
    unittest.main()