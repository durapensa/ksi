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
        # Import daemon config to use the same socket path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ksi_common.config import config
        self.socket_path = str(config.socket_path)
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
        """Test JSON Protocol v2.0 COMPLETION command"""
        print("Testing JSON Protocol v2.0 COMPLETION format...")
        
        # Use the new JSON format
        command = {
            "version": "2.0",
            "command": "COMPLETION",
            "parameters": {
                "prompt": "Test prompt - respond with exactly 'PROTOCOL_TEST_OK'",
                "model": "sonnet",
                "client_id": "test-client-001"
            }
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
                    is_success = parsed.get('status') == 'success'
                    has_request_id = 'request_id' in parsed.get('result', {})
                    # Debug: print actual response
                    if not is_success:
                        print(f"  DEBUG: Response: {json.dumps(parsed, indent=2)}")
                    self.log_result("json_spawn_format", is_success, f"Got JSON response, request_id present: {has_request_id}")
                except Exception as e:
                    self.log_result("json_spawn_format", False, f"Failed to parse JSON: {e}")
            else:
                self.log_result("json_spawn_format", False, "No response received")
                
        except Exception as e:
            self.log_result("json_spawn_format", False, f"Error: {e}")
    
    def test_health_check(self):
        """Test HEALTH_CHECK command"""
        print("Testing HEALTH_CHECK command...")
        
        # Test health check
        command = {
            "version": "2.0",
            "command": "HEALTH_CHECK"
        }
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.settimeout(10.0)
            
            sock.sendall(json.dumps(command).encode() + b'\n')
            response = sock.recv(1024).decode()
            sock.close()
            
            if response:
                try:
                    parsed = json.loads(response)
                    is_healthy = parsed.get('result', {}).get('status') == 'healthy'
                    self.log_result("health_check", is_healthy, f"Daemon health status: {'healthy' if is_healthy else 'unhealthy'}")
                except Exception as e:
                    self.log_result("health_check", False, f"Failed to parse response: {e}")
            else:
                self.log_result("health_check", False, "No response received")
                
        except Exception as e:
            self.log_result("health_check", False, f"Error: {e}")
    
    def test_invalid_command(self):
        """Test error handling for invalid command"""
        print("Testing invalid command handling...")
        
        # Try an invalid command
        command = {
            "version": "2.0",
            "command": "INVALID_COMMAND"
        }
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.settimeout(5.0)
            
            sock.send(json.dumps(command).encode() + b'\n')
            response = sock.recv(4096).decode()
            sock.close()
            
            if response:
                try:
                    parsed = json.loads(response)
                    is_error = parsed.get('status') == 'error'
                    error_code = parsed.get('error', {}).get('code')
                    self.log_result("invalid_command", is_error, f"Got error response with code: {error_code}")
                except:
                    self.log_result("invalid_command", False, "Couldn't parse response JSON")
            else:
                self.log_result("invalid_command", False, "No response received")
                
        except Exception as e:
            self.log_result("invalid_command", False, f"Error: {e}")
    
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
        self.test_health_check() 
        self.test_invalid_command()
        
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
        report_file = Path("var/experiments/results/protocol_validation.json")
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
    if not Path(tester.socket_path).exists():
        print(f"❌ Daemon socket not found at {tester.socket_path}. Start daemon first:")
        print("   python3 ksi-daemon.py --foreground")
        sys.exit(1)
    
    tester.run_all_tests()

if __name__ == "__main__":
    main()