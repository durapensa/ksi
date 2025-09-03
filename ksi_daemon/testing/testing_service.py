#!/usr/bin/env python3
"""
Testing Service
===============

Provides testing framework capabilities through KSI events.
Enables internal testing with full observability.
"""

import logging
import time
import json
import traceback
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.event_response_builder import error_response
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Individual test result."""
    test_name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class TestSuite:
    """Collection of test results."""
    suite_name: str
    suite_id: str
    tests: List[TestResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: Dict = field(default_factory=dict)
    
    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)
    
    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)
    
    @property
    def pass_rate(self) -> float:
        if not self.tests:
            return 0.0
        return self.passed / len(self.tests)
    
    @property
    def duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            "suite_name": self.suite_name,
            "suite_id": self.suite_id,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
            "tests": [t.to_dict() for t in self.tests]
        }


# Test suite storage
test_suites: Dict[str, TestSuite] = {}
current_suite_id: Optional[str] = None


# ==================== Suite Management ====================

@event_handler("testing:suite:create")
async def create_test_suite(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new test suite."""
    global current_suite_id
    
    try:
        suite_name = str(data.get('suite_name', 'Unnamed Suite'))
        metadata = data.get('metadata')
        
        suite_id = f"suite_{int(time.time() * 1000)}"
        suite = TestSuite(
            suite_name=suite_name,
            suite_id=suite_id,
            metadata=metadata or {}
        )
        
        test_suites[suite_id] = suite
        current_suite_id = suite_id
        
        # Emit suite started event
        await emit_event("testing:suite:started", {
            "suite_id": suite_id,
            "suite_name": suite_name,
            "metadata": metadata
        })
        
        return {
            "suite_id": suite_id,
            "suite_name": suite_name,
            "status": "created"
        }
        
    except Exception as e:
        logger.error(f"Failed to create test suite: {e}")
        return error_response(f"Suite creation failed: {str(e)}")


@event_handler("testing:suite:finish")
async def finish_test_suite(data: Dict[str, Any]) -> Dict[str, Any]:
    """Finish a test suite and calculate statistics."""
    global current_suite_id
    
    try:
        suite_id = data.get('suite_id')
        if suite_id is None:
            suite_id = current_suite_id
        
        if suite_id not in test_suites:
            return error_response(f"Suite {suite_id} not found")
        
        suite = test_suites[suite_id]
        suite.end_time = time.time()
        
        # Store in state for persistence
        await emit_event("state:set", {
            "key": f"test_results:{suite_id}",
            "value": suite.to_dict()
        })
        
        await emit_event("testing:suite:finished", {
            "suite_id": suite_id,
            "suite_name": suite.suite_name,
            "passed": suite.passed,
            "failed": suite.failed,
            "pass_rate": suite.pass_rate,
            "duration": suite.duration
        })
        
        # Clear current suite if it was this one
        if current_suite_id == suite_id:
            current_suite_id = None
        
        return suite.to_dict()
        
    except Exception as e:
        logger.error(f"Failed to finish test suite: {e}")
        return error_response(f"Suite finish failed: {str(e)}")


# ==================== Test Assertions ====================

@event_handler("testing:assert:equals")
async def assert_equals(data: Dict[str, Any]) -> Dict[str, Any]:
    """Assert that two values are equal."""
    start = time.time()
    
    try:
        expected = data.get('expected')
        actual = data.get('actual')
        test_name = str(data.get('test_name', 'Unnamed Test'))
        suite_id = data.get('suite_id')
        details = data.get('details')
        
        if suite_id is None:
            suite_id = current_suite_id
        
        if suite_id not in test_suites:
            return error_response(f"Suite {suite_id} not found")
        
        passed = expected == actual
        
        test_result = TestResult(
            test_name=test_name,
            passed=passed,
            duration=time.time() - start,
            details=details or {
                "expected": expected,
                "actual": actual
            }
        )
        
        if not passed:
            test_result.error = f"Expected {expected}, got {actual}"
        
        test_suites[suite_id].tests.append(test_result)
        
        return test_result.to_dict()
        
    except Exception as e:
        logger.error(f"Assertion failed: {e}")
        return error_response(f"Assertion error: {str(e)}")


@event_handler("testing:assert:true")
async def assert_true(data: Dict[str, Any]) -> Dict[str, Any]:
    """Assert that a condition is true."""
    start = time.time()
    
    try:
        condition = data.get('condition', False)
        test_name = str(data.get('test_name', 'Unnamed Test'))
        suite_id = data.get('suite_id')
        message = data.get('message')
        details = data.get('details')
        
        if suite_id is None:
            suite_id = current_suite_id
        
        if suite_id not in test_suites:
            return error_response(f"Suite {suite_id} not found")
        
        test_result = TestResult(
            test_name=test_name,
            passed=bool(condition),
            duration=time.time() - start,
            details=details or {}
        )
        
        if not condition:
            test_result.error = message or "Condition was false"
        
        test_suites[suite_id].tests.append(test_result)
        
        return test_result.to_dict()
        
    except Exception as e:
        logger.error(f"Assertion failed: {e}")
        return error_response(f"Assertion error: {str(e)}")


@event_handler("testing:assert:in_range")
async def assert_in_range(data: Dict[str, Any]) -> Dict[str, Any]:
    """Assert that a value is within a range."""
    start = time.time()
    
    try:
        value = float(data.get('value', 0.0))
        min_value = float(data.get('min_value', 0.0))
        max_value = float(data.get('max_value', 0.0))
        test_name = str(data.get('test_name', 'Unnamed Test'))
        suite_id = data.get('suite_id')
        details = data.get('details')
        
        if suite_id is None:
            suite_id = current_suite_id
        
        if suite_id not in test_suites:
            return error_response(f"Suite {suite_id} not found")
        
        passed = min_value <= value <= max_value
        
        test_result = TestResult(
            test_name=test_name,
            passed=passed,
            duration=time.time() - start,
            details=details or {
                "value": value,
                "min": min_value,
                "max": max_value
            }
        )
        
        if not passed:
            test_result.error = f"Value {value} not in range [{min_value}, {max_value}]"
        
        test_suites[suite_id].tests.append(test_result)
        
        return test_result.to_dict()
        
    except Exception as e:
        logger.error(f"Assertion failed: {e}")
        return error_response(f"Assertion error: {str(e)}")


# ==================== Test Execution ====================

@event_handler("testing:run:test")
async def run_test(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a test by calling a function."""
    start = time.time()
    
    try:
        test_name = str(data.get('test_name', 'Unnamed Test'))
        test_function = str(data.get('test_function', ''))
        test_args = data.get('test_args')
        suite_id = data.get('suite_id')
        
        if suite_id is None:
            suite_id = current_suite_id
        
        if suite_id not in test_suites:
            return error_response(f"Suite {suite_id} not found")
        
        # Parse test_args if it's a JSON string
        if isinstance(test_args, str):
            try:
                test_args = json.loads(test_args)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse test_args as JSON: {test_args}")
                test_args = {}
        
        # Log the test invocation
        logger.info(f"Running test: {test_name}")
        logger.info(f"Calling event: {test_function}")
        logger.info(f"With args: {test_args}")
        
        # Emit test event and capture result
        try:
            result = await emit_event(test_function, test_args or {})
            logger.info(f"Test result: {result}")
            
            # Handle list results (some handlers return list of results)
            if isinstance(result, list) and len(result) == 1:
                result = result[0]
            
            # Determine if test passed based on result
            # Handle different success indicators (valid, passed, status=="success")
            if isinstance(result, dict):
                passed = (
                    result.get("valid", False) or 
                    result.get("passed", False) or 
                    result.get("status") == "success"
                )
            
            test_result = TestResult(
                test_name=test_name,
                passed=passed,
                duration=time.time() - start,
                details=result if isinstance(result, dict) else {"result": result}
            )
            
            if not passed:
                test_result.error = result.get("error", result.get("reason", "Test failed")) if isinstance(result, dict) else "Test failed"
        except Exception as e:
            test_result = TestResult(
                test_name=test_name,
                passed=False,
                duration=time.time() - start,
                error=str(e)
            )
        
        test_suites[suite_id].tests.append(test_result)
        
        return test_result.to_dict()
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        
        test_result = TestResult(
            test_name=test_name,
            passed=False,
            duration=time.time() - start,
            error=str(e),
            details={"traceback": traceback.format_exc()}
        )
        
        if suite_id in test_suites:
            test_suites[suite_id].tests.append(test_result)
        
        return test_result.to_dict()


# ==================== Statistical Analysis ====================

@event_handler("testing:statistics:compare_groups")
async def compare_groups(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two groups statistically."""
    try:
        group_a = np.array(data.get('group_a', []))
        group_b = np.array(data.get('group_b', []))
        test_type = str(data.get('test_type', 'effect_size'))
        
        mean_a = np.mean(group_a)
        mean_b = np.mean(group_b)
        std_a = np.std(group_a)
        std_b = np.std(group_b)
        
        result = {
            "group_a": {
                "mean": mean_a,
                "std": std_a,
                "n": len(group_a)
            },
            "group_b": {
                "mean": mean_b,
                "std": std_b,
                "n": len(group_b)
            }
        }
        
        if test_type == "effect_size":
            # Cohen's d
            pooled_std = np.sqrt((std_a**2 + std_b**2) / 2)
            if pooled_std > 0:
                effect_size = (mean_b - mean_a) / pooled_std
            else:
                effect_size = 0
            
            result["effect_size"] = effect_size
            result["interpretation"] = (
                "negligible" if abs(effect_size) < 0.2 else
                "small" if abs(effect_size) < 0.5 else
                "medium" if abs(effect_size) < 0.8 else
                "large"
            )
            
        elif test_type == "difference":
            result["difference"] = mean_b - mean_a
            result["percent_change"] = ((mean_b - mean_a) / mean_a * 100) if mean_a != 0 else 0
        
        return result
        
    except Exception as e:
        logger.error(f"Statistical comparison failed: {e}")
        return error_response(f"Statistics error: {str(e)}")


# ==================== Report Generation ====================

@event_handler("testing:report:generate")
async def generate_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a comprehensive test report."""
    try:
        suite_ids = data.get('suite_ids')
        save_to_file = data.get('save_to_file', True)
        
        if suite_ids is None:
            suite_ids = list(test_suites.keys())
        
        suites_data = []
        total_passed = 0
        total_failed = 0
        total_duration = 0
        
        for suite_id in suite_ids:
            if suite_id in test_suites:
                suite = test_suites[suite_id]
                suites_data.append(suite.to_dict())
                total_passed += suite.passed
                total_failed += suite.failed
                total_duration += suite.duration
        
        total_tests = total_passed + total_failed
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_suites": len(suites_data),
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "overall_pass_rate": total_passed / total_tests if total_tests > 0 else 0,
                "total_duration": total_duration
            },
            "suites": suites_data
        }
        
        if save_to_file:
            # Save report to file
            report_path = Path(f"results/test_report_{int(time.time())}.json")
            report_path.parent.mkdir(exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            report["report_file"] = str(report_path)
        
        # Store in state
        await emit_event("state:set", {
            "key": "test_results:latest",
            "value": report
        })
        
        return report
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return error_response(f"Report generation error: {str(e)}")


@event_handler("testing:report:get")
async def get_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a test report for a specific suite or the latest."""
    try:
        suite_id = data.get('suite_id')
        
        if suite_id:
            if suite_id in test_suites:
                return test_suites[suite_id].to_dict()
            else:
                # Try to get from state
                result = await emit_event("state:get", {
                    "key": f"test_results:{suite_id}"
                })
                if result:
                    return result
                return error_response(f"Suite {suite_id} not found")
        else:
            # Get latest report from state
            result = await emit_event("state:get", {
                "key": "test_results:latest"
            })
            if result:
                return result
            
            # Generate new report if none exists
            return await generate_report()
            
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        return error_response(f"Report retrieval error: {str(e)}")


# ==================== Service Info ====================

@event_handler("testing:info")
async def get_testing_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get information about the testing service."""
    return {
        "service": "testing",
        "version": "1.0.0",
        "current_suite": current_suite_id,
        "active_suites": list(test_suites.keys()),
        "total_suites": len(test_suites),
        "total_tests": sum(len(s.tests) for s in test_suites.values()),
        "capabilities": [
            "suite management",
            "assertions",
            "test execution",
            "statistical analysis",
            "report generation"
        ]
    }


# Export for discovery
__all__ = [
    'create_test_suite',
    'finish_test_suite',
    'assert_equals',
    'assert_true',
    'assert_in_range',
    'run_test',
    'compare_groups',
    'generate_report',
    'get_report',
    'get_testing_info'
]