#!/usr/bin/env python3
"""
Test Result Logger - Centralized test result collection and reporting

Provides a unified way to log test results across all enhanced test files.
Results are stored in both JSON format (machine-readable) and log format (human-readable).
"""

import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class TestStatus(Enum):
    """Test status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Individual test result data structure"""
    test_name: str
    test_file: str
    status: TestStatus
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    prompt_used: Optional[str] = None
    response_received: Optional[str] = None

    def finish(self, status: TestStatus, error_message: Optional[str] = None, 
               details: Optional[Dict[str, Any]] = None):
        """Mark test as finished with given status"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
        if error_message:
            self.error_message = error_message
        if details:
            self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['status'] = self.status.value
        result['start_time_iso'] = datetime.fromtimestamp(self.start_time).isoformat()
        if self.end_time:
            result['end_time_iso'] = datetime.fromtimestamp(self.end_time).isoformat()
        return result


class TestResultLogger:
    """Centralized test result logging system"""
    
    def __init__(self, results_dir: str = "tests"):
        """
        Initialize test result logger.
        
        Args:
            results_dir: Directory to store result files
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        
        # Result storage
        self.test_results: List[TestResult] = []
        self.current_test: Optional[TestResult] = None
        
        # File paths
        self.json_file = self.results_dir / "test_results.json"
        self.log_file = self.results_dir / "test_results.log"
        
        # Setup logging
        self._setup_logging()
        
        # Load existing results if they exist
        self._load_existing_results()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create logger
        self.logger = logging.getLogger('test_results')
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _load_existing_results(self):
        """Load existing results from JSON file if it exists"""
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r') as f:
                    data = json.load(f)
                    # Convert back to TestResult objects
                    for result_data in data.get('test_results', []):
                        result = TestResult(
                            test_name=result_data['test_name'],
                            test_file=result_data['test_file'],
                            status=TestStatus(result_data['status']),
                            start_time=result_data['start_time'],
                            end_time=result_data.get('end_time'),
                            duration=result_data.get('duration'),
                            error_message=result_data.get('error_message'),
                            details=result_data.get('details'),
                            prompt_used=result_data.get('prompt_used'),
                            response_received=result_data.get('response_received')
                        )
                        self.test_results.append(result)
            except Exception as e:
                self.logger.warning(f"Could not load existing results: {e}")
    
    def start_test(self, test_name: str, test_file: str, prompt: Optional[str] = None) -> TestResult:
        """
        Start a new test and return the test result object.
        
        Args:
            test_name: Name of the test
            test_file: File containing the test
            prompt: Optional prompt being tested
            
        Returns:
            TestResult object for this test
        """
        self.current_test = TestResult(
            test_name=test_name,
            test_file=test_file,
            status=TestStatus.RUNNING,
            start_time=time.time(),
            prompt_used=prompt
        )
        
        self.test_results.append(self.current_test)
        
        self.logger.info(f"Started test: {test_name} in {test_file}")
        if prompt:
            self.logger.info(f"  Prompt: {prompt}")
        
        return self.current_test
    
    def finish_test(self, test_result: TestResult, status: TestStatus, 
                    error_message: Optional[str] = None, 
                    details: Optional[Dict[str, Any]] = None,
                    response: Optional[str] = None):
        """
        Finish a test with the given status.
        
        Args:
            test_result: The TestResult object to finish
            status: Final status of the test
            error_message: Optional error message if test failed
            details: Optional additional details
            response: Optional response received from system
        """
        if response:
            test_result.response_received = response
        
        test_result.finish(status, error_message, details)
        
        # Log the result
        status_symbol = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌", 
            TestStatus.SKIPPED: "⏭️",
            TestStatus.ERROR: "💥"
        }.get(status, "❓")
        
        self.logger.info(f"{status_symbol} {test_result.test_name}: {status.value}")
        if test_result.duration:
            self.logger.info(f"  Duration: {test_result.duration:.3f}s")
        if error_message:
            self.logger.error(f"  Error: {error_message}")
        if response:
            # Truncate long responses
            short_response = response[:100] + "..." if len(response) > 100 else response
            self.logger.info(f"  Response: {short_response}")
        
        # Save results after each test completion
        self.save_results()
    
    def skip_test(self, test_name: str, test_file: str, reason: str):
        """
        Record a skipped test.
        
        Args:
            test_name: Name of the test
            test_file: File containing the test
            reason: Reason for skipping
        """
        test_result = self.start_test(test_name, test_file)
        self.finish_test(test_result, TestStatus.SKIPPED, error_message=reason)
    
    def save_results(self):
        """Save current results to JSON and log files"""
        try:
            # Prepare data for JSON export
            export_data = {
                "generated_at": datetime.now().isoformat(),
                "total_tests": len(self.test_results),
                "test_results": [result.to_dict() for result in self.test_results]
            }
            
            # Write JSON file
            with open(self.json_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Results saved to {self.json_file} and {self.log_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of all test results"""
        if not self.test_results:
            return {"message": "No test results available"}
        
        # Count by status
        status_counts = {}
        for status in TestStatus:
            status_counts[status.value] = sum(1 for r in self.test_results if r.status == status)
        
        # Calculate statistics
        completed_tests = [r for r in self.test_results if r.duration is not None]
        total_duration = sum(r.duration for r in completed_tests)
        avg_duration = total_duration / len(completed_tests) if completed_tests else 0
        
        # Find failed tests
        failed_tests = [r for r in self.test_results if r.status == TestStatus.FAILED]
        error_tests = [r for r in self.test_results if r.status == TestStatus.ERROR]
        
        summary = {
            "total_tests": len(self.test_results),
            "status_counts": status_counts,
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "pass_rate": status_counts.get("passed", 0) / len(self.test_results) * 100 if self.test_results else 0,
            "failed_tests": [{"name": r.test_name, "file": r.test_file, "error": r.error_message} for r in failed_tests],
            "error_tests": [{"name": r.test_name, "file": r.test_file, "error": r.error_message} for r in error_tests]
        }
        
        return summary
    
    def print_summary(self):
        """Print a human-readable summary of test results"""
        summary = self.generate_summary()
        
        if "message" in summary:
            print(summary["message"])
            return
        
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Pass Rate: {summary['pass_rate']:.1f}%")
        print(f"Total Duration: {summary['total_duration']:.2f}s")
        print(f"Average Duration: {summary['average_duration']:.3f}s")
        
        print("\nStatus Breakdown:")
        for status, count in summary['status_counts'].items():
            if count > 0:
                symbol = {
                    "passed": "✅",
                    "failed": "❌",
                    "skipped": "⏭️", 
                    "error": "💥",
                    "pending": "⏸️",
                    "running": "🏃"
                }.get(status, "❓")
                print(f"  {symbol} {status.upper()}: {count}")
        
        if summary['failed_tests']:
            print(f"\nFailed Tests ({len(summary['failed_tests'])}):")
            for test in summary['failed_tests']:
                print(f"  ❌ {test['name']} ({test['file']})")
                if test['error']:
                    print(f"     Error: {test['error']}")
        
        if summary['error_tests']:
            print(f"\nError Tests ({len(summary['error_tests'])}):")
            for test in summary['error_tests']:
                print(f"  💥 {test['name']} ({test['file']})")
                if test['error']:
                    print(f"     Error: {test['error']}")
        
        print("="*60)


# Global instance for easy access
_global_logger = None

def get_test_logger() -> TestResultLogger:
    """Get the global test result logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = TestResultLogger()
    return _global_logger


def start_test(test_name: str, test_file: str, prompt: Optional[str] = None) -> TestResult:
    """Convenience function to start a test"""
    return get_test_logger().start_test(test_name, test_file, prompt)


def finish_test(test_result: TestResult, status: TestStatus, 
                error_message: Optional[str] = None, 
                details: Optional[Dict[str, Any]] = None,
                response: Optional[str] = None):
    """Convenience function to finish a test"""
    get_test_logger().finish_test(test_result, status, error_message, details, response)


def skip_test(test_name: str, test_file: str, reason: str):
    """Convenience function to skip a test"""
    get_test_logger().skip_test(test_name, test_file, reason)


if __name__ == "__main__":
    """Example usage of the test result logger"""
    logger = TestResultLogger()
    
    # Example test 1 - passed
    test1 = logger.start_test("example_passing_test", "test_example.py", "quick: what's 2+2?")
    time.sleep(0.1)  # Simulate test execution
    logger.finish_test(test1, TestStatus.PASSED, response="4")
    
    # Example test 2 - failed  
    test2 = logger.start_test("example_failing_test", "test_example.py", "invalid: <<<broken")
    time.sleep(0.05)
    logger.finish_test(test2, TestStatus.FAILED, error_message="Invalid prompt format")
    
    # Example test 3 - skipped
    logger.skip_test("example_skipped_test", "test_example.py", "Daemon not running")
    
    # Print summary
    logger.print_summary()