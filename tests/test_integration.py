#!/usr/bin/env python3
"""
Enhanced Integration Test Suite

Comprehensive test orchestrator that runs all the new enhanced tests:
1. LiteLLM Provider Direct Tests
2. Completion Service Plugin Tests
3. End-to-End Error Propagation Tests
4. Enhanced Agent Messaging Tests (Multi-Socket)

Provides:
- Sequential test execution with dependency checking
- Comprehensive result aggregation
- System state verification before/after tests
- Final summary report for user review
- Integration with test result logging system
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test result logger
from test_result_logger import TestStatus, start_test, finish_test, skip_test, get_test_logger

# Import individual test suites
try:
    from test_claude_cli_provider_direct import run_all_tests as run_provider_tests
    provider_tests_available = True
except ImportError:
    provider_tests_available = False

# test_completion_service_plugin.py removed - imports non-existent event_bus
service_tests_available = False

try:
    from test_error_propagation import run_all_tests as run_error_tests
    error_tests_available = True
except ImportError:
    error_tests_available = False

try:
    from test_agent_messaging_multisocket import run_all_tests as run_messaging_tests
    messaging_tests_available = True
except ImportError:
    messaging_tests_available = False


class EnhancedIntegrationTestSuite:
    """Master test suite for all enhanced tests"""
    
    def __init__(self):
        self.test_file = "test_enhanced_integration.py"
        self.test_results: Dict[str, Any] = {}
        self.system_state: Dict[str, Any] = {}
    
    def check_system_prerequisites(self) -> Dict[str, Any]:
        """Check system prerequisites before running tests"""
        test_result = start_test("system_prerequisites_check", self.test_file)
        
        try:
            prerequisites = {
                "daemon_socket_exists": False,
                "python_version_ok": False,
                "required_modules_available": {},
                "test_files_exist": {},
                "daemon_running": False
            }
            
            # Check Python version
            python_version = sys.version_info
            prerequisites["python_version_ok"] = python_version >= (3, 8)
            
            # Check for daemon socket
            daemon_socket = Path("sockets/admin.sock")
            prerequisites["daemon_socket_exists"] = daemon_socket.exists()
            
            # Check if daemon is actually responding
            if prerequisites["daemon_socket_exists"]:
                try:
                    # Try to connect to check if daemon is running
                    import socket
                    test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    test_sock.settimeout(1.0)
                    test_sock.connect(str(daemon_socket))
                    test_sock.close()
                    prerequisites["daemon_running"] = True
                except Exception:
                    prerequisites["daemon_running"] = False
            
            # Check required modules
            required_modules = ["asyncio", "json", "pathlib", "unittest.mock"]
            for module in required_modules:
                try:
                    __import__(module)
                    prerequisites["required_modules_available"][module] = True
                except ImportError:
                    prerequisites["required_modules_available"][module] = False
            
            # Check test files exist
            test_files = [
                "test_claude_cli_provider_direct.py",
                "test_error_propagation.py",
                "test_agent_messaging_multisocket.py",
                "test_result_logger.py"
            ]
            
            for test_file in test_files:
                test_path = Path("tests") / test_file
                prerequisites["test_files_exist"][test_file] = test_path.exists()
            
            # Calculate overall readiness
            all_modules_ok = all(prerequisites["required_modules_available"].values())
            all_files_exist = all(prerequisites["test_files_exist"].values())
            prerequisites["system_ready"] = (
                prerequisites["python_version_ok"] and
                all_modules_ok and
                all_files_exist
            )
            
            finish_test(test_result, TestStatus.PASSED,
                       details=prerequisites)
            
            return prerequisites
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"system_ready": False, "error": str(e)}
    
    async def run_provider_direct_tests(self) -> Dict[str, Any]:
        """Run LiteLLM provider direct tests"""
        test_result = start_test("provider_direct_tests_suite", self.test_file)
        
        if not provider_tests_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Provider tests not available")
            return {"success": False, "reason": "not_available"}
        
        try:
            print("\n" + "="*60)
            print("RUNNING: LiteLLM Provider Direct Tests")
            print("="*60)
            
            success = await run_provider_tests()
            
            finish_test(test_result, 
                       TestStatus.PASSED if success else TestStatus.FAILED,
                       details={"all_tests_passed": success})
            
            return {"success": success, "test_suite": "provider_direct"}
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"success": False, "error": str(e)}
    
    async def run_completion_service_tests(self) -> Dict[str, Any]:
        """Run completion service plugin tests"""
        test_result = start_test("completion_service_tests_suite", self.test_file)
        
        if not service_tests_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Service tests not available")
            return {"success": False, "reason": "not_available"}
        
        try:
            print("\n" + "="*60)
            print("RUNNING: Completion Service Plugin Tests")
            print("="*60)
            
            success = await run_service_tests()
            
            finish_test(test_result,
                       TestStatus.PASSED if success else TestStatus.FAILED,
                       details={"all_tests_passed": success})
            
            return {"success": success, "test_suite": "completion_service"}
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"success": False, "error": str(e)}
    
    async def run_error_propagation_tests(self) -> Dict[str, Any]:
        """Run end-to-end error propagation tests"""
        test_result = start_test("error_propagation_tests_suite", self.test_file)
        
        if not error_tests_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Error tests not available")
            return {"success": False, "reason": "not_available"}
        
        try:
            print("\n" + "="*60)
            print("RUNNING: End-to-End Error Propagation Tests")
            print("="*60)
            
            success = await run_error_tests()
            
            finish_test(test_result,
                       TestStatus.PASSED if success else TestStatus.FAILED,
                       details={"all_tests_passed": success})
            
            return {"success": success, "test_suite": "error_propagation"}
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"success": False, "error": str(e)}
    
    async def run_agent_messaging_tests(self) -> Dict[str, Any]:
        """Run enhanced agent messaging tests"""
        test_result = start_test("agent_messaging_tests_suite", self.test_file)
        
        if not messaging_tests_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Messaging tests not available")
            return {"success": False, "reason": "not_available"}
        
        try:
            print("\n" + "="*60)
            print("RUNNING: Enhanced Agent Messaging Tests (Multi-Socket)")
            print("="*60)
            
            success = await run_messaging_tests()
            
            finish_test(test_result,
                       TestStatus.PASSED if success else TestStatus.FAILED,
                       details={"all_tests_passed": success})
            
            return {"success": success, "test_suite": "agent_messaging"}
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"success": False, "error": str(e)}
    
    def verify_system_state_after_tests(self) -> Dict[str, Any]:
        """Verify system state after all tests"""
        test_result = start_test("post_test_system_verification", self.test_file)
        
        try:
            post_state = {
                "daemon_still_running": False,
                "socket_files_present": False,
                "log_files_created": False,
                "result_files_present": False,
                "system_stable": True
            }
            
            # Check daemon socket still exists
            daemon_socket = Path("sockets/admin.sock")
            post_state["socket_files_present"] = daemon_socket.exists()
            
            # Check if daemon is still responding
            if post_state["socket_files_present"]:
                try:
                    import socket
                    test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    test_sock.settimeout(1.0)
                    test_sock.connect(str(daemon_socket))
                    test_sock.close()
                    post_state["daemon_still_running"] = True
                except Exception:
                    post_state["daemon_still_running"] = False
            
            # Check for test result files
            result_files = [
                Path("tests/test_results.json"),
                Path("tests/test_results.log")
            ]
            post_state["result_files_present"] = all(f.exists() for f in result_files)
            
            # Check for any created log files
            log_patterns = [
                Path("logs"),
                Path("claude_logs"), 
                Path("sockets")
            ]
            post_state["log_files_created"] = any(p.exists() for p in log_patterns)
            
            finish_test(test_result, TestStatus.PASSED, details=post_state)
            
            return post_state
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"system_stable": False, "error": str(e)}
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final report"""
        test_result = start_test("final_report_generation", self.test_file)
        
        try:
            # Get test result summary from logger
            logger = get_test_logger()
            summary = logger.generate_summary()
            
            # Calculate suite-specific results
            suite_results = {}
            for test_result_item in logger.test_results:
                test_file = test_result_item.test_file
                if test_file not in suite_results:
                    suite_results[test_file] = {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "skipped": 0,
                        "error": 0
                    }
                
                suite_results[test_file]["total"] += 1
                suite_results[test_file][test_result_item.status.value] += 1
            
            # Generate comprehensive report
            final_report = {
                "test_session": {
                    "start_time": min(r.start_time for r in logger.test_results) if logger.test_results else time.time(),
                    "end_time": time.time(),
                    "total_duration": summary.get("total_duration", 0)
                },
                "overall_summary": summary,
                "suite_breakdown": suite_results,
                "system_verification": self.system_state,
                "enhancement_coverage": {
                    "provider_testing": "test_claude_cli_provider_direct.py" in suite_results,
                    "service_testing": False,  # test_completion_service_plugin.py removed
                    "error_testing": "test_error_propagation.py" in suite_results,
                    "messaging_testing": "test_agent_messaging_multisocket.py" in suite_results,
                    "logging_system": "test_result_logger.py" in suite_results
                },
                "recommendations": []
            }
            
            # Add recommendations based on results
            if summary.get("pass_rate", 0) < 90:
                final_report["recommendations"].append(
                    "Pass rate below 90% - review failed tests for potential issues"
                )
            
            if not final_report["enhancement_coverage"]["provider_testing"]:
                final_report["recommendations"].append(
                    "Provider testing not executed - critical component needs testing"
                )
            
            if summary.get("total_tests", 0) == 0:
                final_report["recommendations"].append(
                    "No tests executed - check system prerequisites and test availability"
                )
            
            if not final_report["recommendations"]:
                final_report["recommendations"].append(
                    "All enhanced testing components executed successfully"
                )
            
            finish_test(test_result, TestStatus.PASSED,
                       details={"report_generated": True, "total_suites": len(suite_results)})
            
            return final_report
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return {"error": str(e)}
    
    def print_final_summary(self, report: Dict[str, Any]):
        """Print human-readable final summary"""
        print("\n" + "="*80)
        print("ENHANCED TEST SUITE - FINAL SUMMARY")
        print("="*80)
        
        if "error" in report:
            print(f"❌ Report generation failed: {report['error']}")
            return
        
        # Overall statistics
        summary = report.get("overall_summary", {})
        print(f"\n📊 OVERALL STATISTICS")
        print(f"   Total Tests: {summary.get('total_tests', 0)}")
        print(f"   Pass Rate: {summary.get('pass_rate', 0):.1f}%")
        print(f"   Total Duration: {summary.get('total_duration', 0):.2f}s")
        print(f"   Average Duration: {summary.get('average_duration', 0):.3f}s")
        
        # Status breakdown
        status_counts = summary.get('status_counts', {})
        print(f"\n📋 STATUS BREAKDOWN")
        for status, count in status_counts.items():
            if count > 0:
                symbols = {
                    "passed": "✅", "failed": "❌", "skipped": "⏭️", 
                    "error": "💥", "pending": "⏸️", "running": "🏃"
                }
                symbol = symbols.get(status, "❓")
                print(f"   {symbol} {status.upper()}: {count}")
        
        # Suite breakdown
        suite_results = report.get("suite_breakdown", {})
        print(f"\n🧪 TEST SUITE BREAKDOWN")
        for suite_file, results in suite_results.items():
            suite_name = suite_file.replace("test_", "").replace(".py", "").replace("_", " ").title()
            passed = results.get("passed", 0)
            total = results.get("total", 0)
            pass_rate = (passed / total * 100) if total > 0 else 0
            print(f"   {suite_name}: {passed}/{total} ({pass_rate:.1f}%)")
        
        # Enhancement coverage
        coverage = report.get("enhancement_coverage", {})
        print(f"\n🎯 ENHANCEMENT COVERAGE")
        coverage_items = [
            ("Provider Testing", coverage.get("provider_testing", False)),
            ("Service Testing", coverage.get("service_testing", False)),
            ("Error Testing", coverage.get("error_testing", False)),
            ("Messaging Testing", coverage.get("messaging_testing", False)),
            ("Logging System", coverage.get("logging_system", False))
        ]
        
        for item_name, covered in coverage_items:
            symbol = "✅" if covered else "❌"
            print(f"   {symbol} {item_name}")
        
        # Failed tests (if any)
        failed_tests = summary.get('failed_tests', [])
        if failed_tests:
            print(f"\n❌ FAILED TESTS ({len(failed_tests)})")
            for test in failed_tests:
                print(f"   • {test['name']} ({test['file']})")
                if test.get('error'):
                    print(f"     Error: {test['error']}")
        
        # Recommendations
        recommendations = report.get("recommendations", [])
        print(f"\n💡 RECOMMENDATIONS")
        for rec in recommendations:
            print(f"   • {rec}")
        
        # System state
        system_state = report.get("system_verification", {})
        if system_state:
            print(f"\n🔧 SYSTEM STATE")
            print(f"   Daemon Running: {'✅' if system_state.get('daemon_still_running', False) else '❌'}")
            print(f"   Result Files: {'✅' if system_state.get('result_files_present', False) else '❌'}")
            print(f"   System Stable: {'✅' if system_state.get('system_stable', False) else '❌'}")
        
        print("\n" + "="*80)
        
        # Final verdict
        pass_rate = summary.get('pass_rate', 0)
        if pass_rate >= 95:
            print("🎉 EXCELLENT: Enhanced test coverage is comprehensive and successful!")
        elif pass_rate >= 80:
            print("✅ GOOD: Enhanced testing mostly successful with minor issues to address.")
        elif pass_rate >= 60:
            print("⚠️  WARNING: Significant test failures - review and fix issues.")
        else:
            print("❌ CRITICAL: Major testing failures - immediate attention required.")
        
        print("="*80)


async def run_all_enhanced_tests():
    """Run the complete enhanced test suite"""
    print("🚀 Starting Enhanced Integration Test Suite")
    print("="*80)
    
    suite = EnhancedIntegrationTestSuite()
    
    # Step 1: Check system prerequisites
    print("\n📋 Checking System Prerequisites...")
    prerequisites = suite.check_system_prerequisites()
    suite.system_state.update(prerequisites)
    
    if not prerequisites.get("system_ready", False):
        print("❌ System not ready for testing")
        if "error" in prerequisites:
            print(f"Error: {prerequisites['error']}")
        return False
    
    print("✅ System prerequisites satisfied")
    
    # Step 2: Run test suites in sequence
    test_suites = [
        ("Provider Direct Tests", suite.run_provider_direct_tests),
        ("Completion Service Tests", suite.run_completion_service_tests),
        ("Error Propagation Tests", suite.run_error_propagation_tests),
        ("Agent Messaging Tests", suite.run_agent_messaging_tests)
    ]
    
    suite_results = []
    
    for suite_name, suite_runner in test_suites:
        print(f"\n🔄 Starting {suite_name}...")
        start_time = time.time()
        
        try:
            result = await suite_runner()
            result["duration"] = time.time() - start_time
            suite_results.append(result)
            
            if result.get("success", False):
                print(f"✅ {suite_name} completed successfully")
            else:
                print(f"❌ {suite_name} failed: {result.get('reason', 'unknown')}")
                
        except Exception as e:
            print(f"💥 {suite_name} crashed: {e}")
            suite_results.append({"success": False, "error": str(e)})
    
    # Step 3: Post-test system verification
    print("\n🔍 Verifying System State After Tests...")
    post_state = suite.verify_system_state_after_tests()
    suite.system_state.update(post_state)
    
    # Step 4: Generate final report
    print("\n📊 Generating Final Report...")
    final_report = suite.generate_final_report()
    
    # Step 5: Print summary
    suite.print_final_summary(final_report)
    
    # Calculate overall success
    successful_suites = sum(1 for result in suite_results if result.get("success", False))
    total_suites = len(suite_results)
    overall_success = successful_suites == total_suites and total_suites > 0
    
    return overall_success


if __name__ == "__main__":
    """Main entry point for enhanced integration tests"""
    
    # Set up test environment
    os.chdir(Path(__file__).parent.parent)  # Run from project root
    
    print("Enhanced Integration Test Suite for KSI Client/Daemon Refactor")
    print(f"Running from: {os.getcwd()}")
    
    # Run all tests
    start_time = time.time()
    success = asyncio.run(run_all_enhanced_tests())
    total_time = time.time() - start_time
    
    print(f"\n⏱️  Total execution time: {total_time:.2f}s")
    
    # Final exit
    if success:
        print("🎯 Enhanced integration tests completed successfully!")
        sys.exit(0)
    else:
        print("⚠️  Enhanced integration tests completed with issues.")
        sys.exit(1)