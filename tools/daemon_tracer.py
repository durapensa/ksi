#!/usr/bin/env python3

"""
Comprehensive Daemon Testing and Tracing System
Systematically tests all daemon functionality and finds bugs
"""

import asyncio
import json
import time
import os
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging

# Set up tracing logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TRACER - %(message)s')
logger = logging.getLogger('tracer')

@dataclass
class TestResult:
    """Result of a single test"""
    test_name: str
    success: bool
    response: Any
    duration: float
    error: Optional[str] = None

@dataclass
class TraceSession:
    """Complete tracing session results"""
    start_time: float
    end_time: float
    total_tests: int
    passed: int
    failed: int
    results: List[TestResult]
    daemon_type: str
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        return (self.passed / self.total_tests) * 100 if self.total_tests > 0 else 0

class DaemonTracer:
    """Comprehensive daemon testing and bug detection"""
    
    def __init__(self, socket_path: str = 'sockets/claude_daemon.sock'):
        self.socket_path = socket_path
        self.results: List[TestResult] = []
    
    async def send_command(self, command: str, timeout: float = 5.0) -> tuple[bool, Any, float]:
        """Send command and measure response time"""
        start_time = time.time()
        try:
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            writer.write(f"{command}\n".encode())
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=timeout)
            duration = time.time() - start_time
            
            writer.close()
            await writer.wait_closed()
            
            response_str = response.decode().strip()
            
            # Try to parse as JSON
            try:
                response_data = json.loads(response_str)
                return True, response_data, duration
            except json.JSONDecodeError:
                return True, response_str, duration
                
        except Exception as e:
            duration = time.time() - start_time
            return False, str(e), duration
    
    async def test_command(self, test_name: str, command: str, expected_keys: List[str] = None, timeout: float = 5.0) -> TestResult:
        """Test a single command and validate response"""
        logger.info(f"Testing: {test_name}")
        
        success, response, duration = await self.send_command(command, timeout)
        
        # Validate response structure
        error = None
        if success and expected_keys:
            if isinstance(response, dict):
                missing_keys = [key for key in expected_keys if key not in response]
                if missing_keys:
                    success = False
                    error = f"Missing expected keys: {missing_keys}"
            else:
                success = False
                error = f"Expected dict response, got {type(response)}"
        
        if not success and not error:
            error = str(response)
        
        result = TestResult(
            test_name=test_name,
            success=success,
            response=response,
            duration=duration,
            error=error
        )
        
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"  {status} ({duration:.3f}s) - {test_name}")
        if error:
            logger.error(f"    Error: {error}")
        
        return result
    
    async def test_protocol_basics(self):
        """Test basic protocol functionality"""
        logger.info("🔍 Testing Basic Protocol")
        
        # Health check
        await self.test_command("Health Check", "HEALTH_CHECK")
        
        # Unknown command handling
        result = await self.test_command("Unknown Command", "INVALID_COMMAND")
        if result.success and isinstance(result.response, dict):
            if 'error' not in result.response:
                result.success = False
                result.error = "Should return error for unknown command"
    
    async def test_shared_state(self):
        """Test shared state functionality"""
        logger.info("🔍 Testing Shared State")
        
        # Set shared state
        await self.test_command("Set Shared State", "SET_SHARED:test_key:test_value", ['status', 'key'])
        
        # Get shared state
        result = await self.test_command("Get Shared State", "GET_SHARED:test_key", ['key', 'value'])
        if result.success and isinstance(result.response, dict):
            if result.response.get('value') != 'test_value':
                result.success = False
                result.error = f"Expected 'test_value', got '{result.response.get('value')}'"
        
        # Get non-existent key
        await self.test_command("Get Missing Key", "GET_SHARED:missing_key", ['key', 'value'])
        
        # Test edge cases
        await self.test_command("Set Empty Value", "SET_SHARED:empty_key:")
        await self.test_command("Set Special Chars", "SET_SHARED:special:value:with:colons")
        await self.test_command("Invalid Format", "SET_SHARED:no_value")
    
    async def test_agent_management(self):
        """Test agent registration and management"""
        logger.info("🔍 Testing Agent Management")
        
        # Register agent
        await self.test_command("Register Agent", "REGISTER_AGENT:test_agent:test_role:capability1,capability2", ['status', 'agent_id'])
        
        # Get agents
        result = await self.test_command("Get Agents", "GET_AGENTS", ['agents'])
        if result.success and isinstance(result.response, dict):
            agents = result.response.get('agents', {})
            if 'test_agent' not in agents:
                result.success = False
                result.error = "Registered agent not found in agent list"
        
        # Register agent with minimal info
        await self.test_command("Register Minimal Agent", "REGISTER_AGENT:minimal:role", ['status', 'agent_id'])
        
        # Invalid registration
        await self.test_command("Invalid Registration", "REGISTER_AGENT:only_id")
    
    async def test_state_persistence(self):
        """Test state persistence across operations"""
        logger.info("🔍 Testing State Persistence")
        
        # Set multiple state values
        test_states = {
            'persist1': 'value1',
            'persist2': 'value2', 
            'persist3': 'complex:value:with:colons'
        }
        
        for key, value in test_states.items():
            await self.test_command(f"Set {key}", f"SET_SHARED:{key}:{value}")
        
        # Verify all values persist
        for key, expected_value in test_states.items():
            result = await self.test_command(f"Verify {key}", f"GET_SHARED:{key}")
            if result.success and isinstance(result.response, dict):
                actual_value = result.response.get('value')
                if actual_value != expected_value:
                    result.success = False
                    result.error = f"Expected '{expected_value}', got '{actual_value}'"
    
    async def test_error_conditions(self):
        """Test error handling and edge cases"""
        logger.info("🔍 Testing Error Conditions")
        
        # Empty command
        await self.test_command("Empty Command", "")
        
        # Malformed commands
        await self.test_command("Command with only colons", ":::")
        await self.test_command("Very long command", "COMMAND:" + "x" * 10000)
        
        # Commands that should fail gracefully
        await self.test_command("Invalid JSON", "INVALID_JSON{}")
        await self.test_command("Null bytes", "TEST\x00NULL")
    
    async def test_performance(self):
        """Test performance characteristics"""
        logger.info("🔍 Testing Performance")
        
        # Rapid command sequence
        start_time = time.time()
        rapid_results = []
        
        for i in range(10):
            result = await self.test_command(f"Rapid Command {i}", f"SET_SHARED:rapid_{i}:value_{i}")
            rapid_results.append(result)
        
        total_time = time.time() - start_time
        avg_time = total_time / len(rapid_results)
        
        logger.info(f"  Rapid sequence: {len(rapid_results)} commands in {total_time:.3f}s (avg: {avg_time:.3f}s)")
        
        # Check for any timeouts or failures
        failures = [r for r in rapid_results if not r.success]
        if failures:
            logger.warning(f"  {len(failures)} failures in rapid sequence")
    
    async def test_hot_reload(self, daemon_script: str):
        """Test hot reload functionality"""
        logger.info("🔍 Testing Hot Reload")
        
        # Set state before reload
        await self.test_command("Pre-reload State", "SET_SHARED:reload_test:before_reload")
        await self.test_command("Pre-reload Agent", "REGISTER_AGENT:reload_agent:test_role")
        
        # Trigger hot reload
        result = await self.test_command("Hot Reload", "RELOAD_DAEMON", timeout=30.0)
        
        if result.success:
            # Wait for reload to complete
            await asyncio.sleep(2)
            
            # Verify state preserved
            await self.test_command("Post-reload Health", "HEALTH_CHECK")
            
            state_result = await self.test_command("Post-reload State", "GET_SHARED:reload_test")
            if state_result.success and isinstance(state_result.response, dict):
                if state_result.response.get('value') != 'before_reload':
                    state_result.success = False
                    state_result.error = "State not preserved across hot reload"
            
            agent_result = await self.test_command("Post-reload Agents", "GET_AGENTS")
            if agent_result.success and isinstance(agent_result.response, dict):
                agents = agent_result.response.get('agents', {})
                if 'reload_agent' not in agents:
                    agent_result.success = False
                    agent_result.error = "Agent not preserved across hot reload"
    
    async def run_comprehensive_trace(self, daemon_script: str = "daemon_minimal.py") -> TraceSession:
        """Run complete tracing session"""
        logger.info("🚀 Starting Comprehensive Daemon Trace")
        start_time = time.time()
        
        self.results = []  # Reset results
        
        # Check if daemon is running
        try:
            success, response, _ = await self.send_command("HEALTH_CHECK", timeout=2.0)
            if not success:
                logger.error("❌ Daemon not responding. Please start daemon first.")
                return None
        except (OSError, ConnectionError) as e:
            logger.error(f"❌ Cannot connect to daemon: {e}. Please start daemon first.")
            return None
        
        logger.info("✅ Daemon connection confirmed")
        
        # Run all test suites
        test_suites = [
            self.test_protocol_basics,
            self.test_shared_state, 
            self.test_agent_management,
            self.test_state_persistence,
            self.test_error_conditions,
            self.test_performance
        ]
        
        for test_suite in test_suites:
            try:
                await test_suite()
            except Exception as e:
                logger.error(f"Test suite failed: {test_suite.__name__}: {e}")
        
        # Test hot reload if daemon supports it
        try:
            await self.test_hot_reload(daemon_script)
        except Exception as e:
            logger.warning(f"Hot reload test failed: {e}")
        
        end_time = time.time()
        
        # Calculate results
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        
        session = TraceSession(
            start_time=start_time,
            end_time=end_time,
            total_tests=len(self.results),
            passed=passed,
            failed=failed,
            results=self.results,
            daemon_type=daemon_script
        )
        
        self.print_summary(session)
        return session
    
    def print_summary(self, session: TraceSession):
        """Print comprehensive test summary"""
        print("\n" + "="*80)
        print("🔍 DAEMON TRACE SUMMARY")
        print("="*80)
        print(f"Daemon Type: {session.daemon_type}")
        print(f"Duration: {session.duration:.2f}s")
        print(f"Total Tests: {session.total_tests}")
        print(f"Passed: {session.passed} (✅)")
        print(f"Failed: {session.failed} ({'❌' if session.failed > 0 else '✅'})")
        print(f"Success Rate: {session.success_rate:.1f}%")
        
        if session.failed > 0:
            print(f"\n❌ FAILED TESTS ({session.failed}):")
            print("-" * 40)
            for result in session.results:
                if not result.success:
                    print(f"  • {result.test_name}")
                    print(f"    Error: {result.error}")
                    print(f"    Response: {result.response}")
                    print()
        
        # Performance analysis
        durations = [r.duration for r in session.results if r.success]
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            print(f"\n⚡ PERFORMANCE ANALYSIS:")
            print(f"  Average response time: {avg_duration:.3f}s")
            print(f"  Maximum response time: {max_duration:.3f}s")
            
            slow_tests = [r for r in session.results if r.duration > 1.0]
            if slow_tests:
                print(f"  Slow tests (>1s): {len(slow_tests)}")
                for test in slow_tests:
                    print(f"    • {test.test_name}: {test.duration:.3f}s")
        
        print("\n" + "="*80)

async def main():
    """Run daemon tracing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive Daemon Tracer')
    parser.add_argument('--socket', default='sockets/claude_daemon.sock', help='Daemon socket path')
    parser.add_argument('--daemon', default='daemon_minimal.py', help='Daemon script being tested')
    args = parser.parse_args()
    
    tracer = DaemonTracer(args.socket)
    session = await tracer.run_comprehensive_trace(args.daemon)
    
    if session and session.failed > 0:
        exit(1)  # Exit with error code if tests failed

if __name__ == '__main__':
    asyncio.run(main())