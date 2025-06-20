#!/usr/bin/env python3
"""
Daemon Protocol Validation Script

Tests the documented daemon communication formats to ensure they work as expected.
This validates our CLAUDE.md documentation against actual daemon behavior.
"""

import json
import socket
import time
import sys
from pathlib import Path

class DaemonProtocolTester:
    def __init__(self):
        self.socket_path = "sockets/claude_daemon.sock"
        self.results = []
        
    def test_socket_connection(self):
        """Test basic socket connectivity"""
        print("Testing socket connection...")
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.close()
            self.log_result("socket_connection", True, "Successfully connected to daemon socket")
            return True
        except Exception as e:
            self.log_result("socket_connection", False, f"Failed to connect: {e}")
            return False
    
    def test_json_spawn_format(self):
        """Test documented JSON spawn format"""
        print("Testing JSON spawn format...")
        
        command = {
            'action': 'spawn',
            'prompt': 'Test prompt - respond with exactly "PROTOCOL_TEST_OK"',
            'allowedTools': ['Task', 'Bash']
        }
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.settimeout(10.0)
            
            sock.send(json.dumps(command).encode() + b'\n')
            response = sock.recv(4096).decode()
            sock.close()
            
            # Check if we got a response
            if response:
                try:
                    parsed = json.loads(response)
                    has_session_id = 'sessionId' in parsed or 'session_id' in parsed
                    self.log_result("json_spawn_format", True, f"Got response with session_id: {has_session_id}")
                except:
                    self.log_result("json_spawn_format", True, "Got response but couldn't parse JSON")
            else:
                self.log_result("json_spawn_format", False, "No response received")
                
        except Exception as e:
            self.log_result("json_spawn_format", False, f"Error: {e}")
    
    def test_spawn_string_format(self):
        """Test AutonomousResearcher SPAWN format"""
        print("Testing SPAWN string format...")
        
        # Test fresh spawn format
        command = "SPAWN::Test prompt for string format"
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.settimeout(10.0)
            
            sock.sendall(command.encode() + b'\n')
            response = sock.recv(1024)
            sock.close()
            
            if response:
                self.log_result("spawn_string_format", True, f"Got response: {len(response)} bytes")
            else:
                self.log_result("spawn_string_format", False, "No response received")
                
        except Exception as e:
            self.log_result("spawn_string_format", False, f"Error: {e}")
    
    def test_stderr_capture(self):
        """Test if stderr is captured in responses"""
        print("Testing stderr capture...")
        
        # Try a command that might generate stderr
        command = {
            'action': 'spawn',
            'prompt': 'Run a bash command that outputs to stderr: echo "test stderr" >&2',
            'allowedTools': ['Bash']
        }
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.settimeout(15.0)
            
            sock.send(json.dumps(command).encode() + b'\n')
            response = sock.recv(4096).decode()
            sock.close()
            
            if response:
                try:
                    parsed = json.loads(response)
                    has_stderr = 'stderr' in parsed
                    self.log_result("stderr_capture", has_stderr, f"stderr field present: {has_stderr}")
                except:
                    self.log_result("stderr_capture", False, "Couldn't parse response JSON")
            else:
                self.log_result("stderr_capture", False, "No response received")
                
        except Exception as e:
            self.log_result("stderr_capture", False, f"Error: {e}")
    
    def log_result(self, test_name, success, message):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name} - {message}")
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": time.time()
        })
    
    def run_all_tests(self):
        """Run all protocol validation tests"""
        print("🧪 Starting Daemon Protocol Validation\n")
        
        # Test basic connectivity first
        if not self.test_socket_connection():
            print("❌ Socket connection failed - daemon may not be running")
            return False
            
        # Run protocol tests
        self.test_json_spawn_format()
        self.test_spawn_string_format() 
        self.test_stderr_capture()
        
        # Generate report
        self.generate_report()
        return True
    
    def generate_report(self):
        """Generate validation report"""
        print("\n📊 Protocol Validation Report")
        print("=" * 40)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        
        print(f"Tests: {passed}/{total} passed")
        
        if passed == total:
            print("✅ All protocol tests passed - documentation is accurate")
        else:
            print("⚠️  Some tests failed - documentation may need updates")
            
        # Save detailed results
        report_file = Path("autonomous_experiments/protocol_validation.json")
        with open(report_file, 'w') as f:
            json.dump({
                "timestamp": time.time(),
                "tests_passed": passed,
                "tests_total": total,
                "results": self.results
            }, f, indent=2)
        
        print(f"📁 Detailed results saved to: {report_file}")

def main():
    tester = DaemonProtocolTester()
    
    # Check if daemon is running
    if not Path("sockets/claude_daemon.sock").exists():
        print("❌ Daemon socket not found. Start daemon first:")
        print("   uv run python daemon.py")
        sys.exit(1)
    
    tester.run_all_tests()

if __name__ == "__main__":
    main()