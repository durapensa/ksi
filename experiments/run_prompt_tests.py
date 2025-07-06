#!/usr/bin/env python3
"""
Run prompt tests with safety controls.
"""

import asyncio
import json
from datetime import datetime
from prompt_testing_framework import PromptTestRunner
from prompt_test_suites import (
    create_prompt_complexity_suite,
    create_contamination_detection_suite,
    get_all_test_suites
)
from safety_utils import ExperimentSafetyGuard


async def run_quick_test():
    """Run a quick test with just a few prompts."""
    print("=== Quick Prompt Test ===\n")
    
    # Create safety guard with conservative limits
    safety = ExperimentSafetyGuard(
        max_agents=3,
        agent_timeout=60,
        spawn_cooldown=1.0
    )
    
    # Create test runner
    runner = PromptTestRunner(safety)
    
    # Select a few tests
    complexity_tests = create_prompt_complexity_suite()
    contamination_tests = create_contamination_detection_suite()
    
    # Run just the first 2 from each suite
    quick_suite = complexity_tests[:2] + contamination_tests[:2]
    
    # Run tests
    report = await runner.run_suite(quick_suite)
    
    # Print results
    print("\n=== Results ===")
    print(f"Summary: {json.dumps(report['summary'], indent=2)}")
    
    if report['contamination']['affected_tests'] > 0:
        print(f"\nContamination detected in {report['contamination']['affected_tests']} tests:")
        for detail in report['contamination']['details']:
            print(f"  - {detail['test']}: {detail['indicators']}")
    
    # Save report
    runner.save_report(report, f"quick_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


async def run_full_suite(suite_name: str):
    """Run a complete test suite."""
    print(f"=== Running {suite_name} Test Suite ===\n")
    
    # Get all suites
    all_suites = get_all_test_suites()
    
    if suite_name not in all_suites:
        print(f"Unknown suite: {suite_name}")
        print(f"Available: {list(all_suites.keys())}")
        return
    
    # Create safety guard
    safety = ExperimentSafetyGuard(
        max_agents=5,
        agent_timeout=120,
        spawn_cooldown=1.0
    )
    
    # Run selected suite
    runner = PromptTestRunner(safety)
    report = await runner.run_suite(all_suites[suite_name])
    
    # Print detailed results
    print("\n=== Detailed Results ===")
    print(f"Overall: {report['summary']['successful']}/{report['summary']['total_tests']} passed")
    print(f"Success rate: {report['summary']['success_rate']:.1%}")
    print(f"Avg response time: {report['summary']['avg_response_time']:.2f}s")
    
    # Results by tag
    if report['by_tag']:
        print("\nResults by tag:")
        for tag, results in report['by_tag'].items():
            success_rate = results['success'] / results['total'] if results['total'] > 0 else 0
            print(f"  {tag}: {results['success']}/{results['total']} ({success_rate:.1%})")
    
    # Save report
    runner.save_report(report, f"{suite_name}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


async def run_comparative_test():
    """Run tests comparing different prompt strategies."""
    print("=== Comparative Prompt Test ===\n")
    
    # Create custom comparative tests
    from prompt_testing_framework import PromptTest
    
    comparative_tests = [
        # Test 1: Simple vs detailed instructions
        PromptTest(
            name="simple_instruction",
            profile="base_single_agent",
            prompt="List 3 fruits",
            expected_behaviors=["fruit"],
            tags=["comparison:simple"]
        ),
        PromptTest(
            name="detailed_instruction",
            profile="base_single_agent",
            prompt="""List exactly 3 fruits following these rules:
- One fruit per line
- Capitalize the first letter
- No punctuation
- Common fruits only""",
            expected_behaviors=["fruit"],
            success_criteria=lambda r: r.get("response", "").count("\n") >= 2,
            tags=["comparison:detailed"]
        ),
        
        # Test 2: Direct vs roleplay
        PromptTest(
            name="direct_request",
            profile="base_single_agent",
            prompt="Explain what TCP/IP is in one sentence.",
            expected_behaviors=["TCP", "IP", "protocol"],
            tags=["comparison:direct"]
        ),
        PromptTest(
            name="roleplay_request",
            profile="base_single_agent",
            prompt="You are a network engineer. Explain what TCP/IP is in one sentence.",
            expected_behaviors=["TCP", "IP", "protocol"],
            tags=["comparison:roleplay"]
        ),
        
        # Test 3: Positive vs negative framing
        PromptTest(
            name="positive_framing",
            profile="base_single_agent",
            prompt="Write a 20-word description of summer.",
            success_criteria=lambda r: 15 <= len(r.get("response", "").split()) <= 25,
            tags=["comparison:positive"]
        ),
        PromptTest(
            name="negative_framing",
            profile="base_single_agent",
            prompt="Write about summer. Don't exceed 20 words.",
            success_criteria=lambda r: len(r.get("response", "").split()) <= 20,
            tags=["comparison:negative"]
        )
    ]
    
    # Run comparative tests
    safety = ExperimentSafetyGuard(max_agents=3, agent_timeout=60)
    runner = PromptTestRunner(safety)
    report = await runner.run_suite(comparative_tests)
    
    # Analyze comparisons
    print("\n=== Comparison Results ===")
    
    comparisons = ["simple vs detailed", "direct vs roleplay", "positive vs negative"]
    for i in range(0, len(comparative_tests), 2):
        if i+1 < len(comparative_tests):
            test1 = next(r for r in report['detailed_results'] if r['test'] == comparative_tests[i].name)
            test2 = next(r for r in report['detailed_results'] if r['test'] == comparative_tests[i+1].name)
            
            print(f"\n{comparisons[i//2]}:")
            print(f"  {test1['test']}: {'✓' if test1['success'] else '✗'} ({test1['response_time']:.2f}s)")
            print(f"  {test2['test']}: {'✓' if test2['success'] else '✗'} ({test2['response_time']:.2f}s)")
    
    # Save report
    runner.save_report(report, f"comparative_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            if sys.argv[1] == "quick":
                await run_quick_test()
            elif sys.argv[1] == "compare":
                await run_comparative_test()
            else:
                await run_full_suite(sys.argv[1])
        else:
            print("Usage:")
            print("  python run_prompt_tests.py quick      # Run quick test")
            print("  python run_prompt_tests.py compare    # Run comparative test")
            print("  python run_prompt_tests.py <suite>    # Run full suite")
            print("\nAvailable suites:")
            for suite in get_all_test_suites().keys():
                print(f"  - {suite}")
    
    asyncio.run(main())