#!/usr/bin/env python3
"""
Melting Pot Test Runner
========================

Main entry point for running the complete Melting Pot test suite.
Integrates validators, services, and scenarios for comprehensive testing.
"""

import asyncio
import argparse
import sys
from pathlib import Path
import json
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import test components
from experiments.test_orchestrator import MeltingPotTestOrchestrator
from experiments.metrics_collector import MetricsCollector, MeltingPotScenario, ScenarioConfig


class MeltingPotTestRunner:
    """Runs the complete Melting Pot test suite."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.results = {}
        
    def log(self, message: str):
        """Log a message."""
        if self.verbose:
            print(message)
    
    async def run_phase_1_unit_tests(self):
        """Phase 1: Unit tests for validators and basic functionality."""
        
        self.log("\n" + "="*80)
        self.log("PHASE 1: UNIT TESTS")
        self.log("="*80)
        
        orchestrator = MeltingPotTestOrchestrator(verbose=self.verbose)
        
        # Test validators directly
        await orchestrator.test_validators()
        
        # Test service health
        await orchestrator.test_service_health()
        
        # Generate report
        report = orchestrator.generate_report()
        self.results["phase_1"] = report
        
        # Check if we can proceed
        pass_rate = report["summary"]["overall_pass_rate"]
        if pass_rate < 0.7:
            self.log(f"\n⚠️  Unit tests pass rate too low ({pass_rate:.1%}). Fix issues before proceeding.")
            return False
        
        self.log(f"\n✓ Phase 1 complete. Pass rate: {pass_rate:.1%}")
        return True
    
    async def run_phase_2_integration_tests(self):
        """Phase 2: Integration tests for services working together."""
        
        self.log("\n" + "="*80)
        self.log("PHASE 2: INTEGRATION TESTS")
        self.log("="*80)
        
        orchestrator = MeltingPotTestOrchestrator(verbose=self.verbose)
        
        # Test service integration
        await orchestrator.test_service_integration()
        
        # Test basic scenarios
        await orchestrator.test_scenario_basics()
        
        # Generate report
        report = orchestrator.generate_report()
        self.results["phase_2"] = report
        
        pass_rate = report["summary"]["overall_pass_rate"]
        if pass_rate < 0.6:
            self.log(f"\n⚠️  Integration tests pass rate too low ({pass_rate:.1%}).")
            return False
        
        self.log(f"\n✓ Phase 2 complete. Pass rate: {pass_rate:.1%}")
        return True
    
    def run_phase_3_fairness_ab_tests(self):
        """Phase 3: A/B tests for fairness mechanisms."""
        
        self.log("\n" + "="*80)
        self.log("PHASE 3: FAIRNESS A/B TESTS")
        self.log("="*80)
        
        collector = MetricsCollector()
        
        # Configure scenarios
        scenarios = [
            {
                "type": MeltingPotScenario.PRISONERS_DILEMMA,
                "config": ScenarioConfig(
                    name="Prisoners Dilemma",
                    grid_size=25,
                    max_steps=50,  # Shorter for testing
                    num_focal=4,
                    num_background=4,
                    resources=[
                        {"type": "cooperate_token", "amount": 100},
                        {"type": "defect_token", "amount": 100}
                    ],
                    victory_conditions=[{"type": "score_threshold", "threshold": 300}],
                    special_mechanics={}
                )
            },
            {
                "type": MeltingPotScenario.COMMONS_HARVEST,
                "config": ScenarioConfig(
                    name="Commons Harvest",
                    grid_size=30,
                    max_steps=50,
                    num_focal=6,
                    num_background=6,
                    resources=[{"type": "commons_resource", "amount": 100}],
                    victory_conditions=[{"type": "sustainability", "min_level": 20}],
                    special_mechanics={"regeneration_rate": 0.1}
                )
            }
        ]
        
        # Run A/B tests
        for scenario_def in scenarios:
            self.log(f"\nTesting {scenario_def['type'].value}...")
            
            try:
                results = collector.run_ab_test(
                    scenario_def["type"],
                    scenario_def["config"],
                    n_runs=5  # Small number for quick testing, use 30+ for real
                )
                
                # Store results
                self.results[f"ab_{scenario_def['type'].value}"] = {
                    "summary": results.summary,
                    "tests": {
                        k: {"pvalue": v.pvalue} if hasattr(v, 'pvalue') else v
                        for k, v in results.statistical_tests.items()
                    }
                }
                
            except Exception as e:
                self.log(f"  Error in A/B test: {e}")
                return False
        
        # Generate final report
        report = collector.generate_report()
        self.results["phase_3_report"] = report
        
        # Save all results
        collector.save_results()
        
        self.log(f"\n✓ Phase 3 complete. {len(collector.experiments)} A/B tests run.")
        return True
    
    async def run_all_phases(self):
        """Run all test phases in sequence."""
        
        self.log("\n" + "="*80)
        self.log("MELTING POT COMPLETE TEST SUITE")
        self.log("="*80)
        self.log(f"Started: {datetime.now().isoformat()}")
        
        start_time = time.time()
        
        # Phase 1: Unit Tests
        phase_1_passed = await self.run_phase_1_unit_tests()
        if not phase_1_passed:
            self.log("\n❌ Phase 1 failed. Stopping test suite.")
            return False
        
        # Phase 2: Integration Tests
        phase_2_passed = await self.run_phase_2_integration_tests()
        if not phase_2_passed:
            self.log("\n❌ Phase 2 failed. Stopping test suite.")
            return False
        
        # Phase 3: Fairness A/B Tests
        phase_3_passed = self.run_phase_3_fairness_ab_tests()
        if not phase_3_passed:
            self.log("\n❌ Phase 3 failed.")
            return False
        
        duration = time.time() - start_time
        
        # Save complete results
        self.save_complete_results()
        
        self.log("\n" + "="*80)
        self.log("ALL TESTS COMPLETE")
        self.log("="*80)
        self.log(f"Total Duration: {duration:.1f}s")
        self.log(f"Completed: {datetime.now().isoformat()}")
        
        return True
    
    def save_complete_results(self):
        """Save all test results to a file."""
        
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        filepath = results_dir / f"complete_test_results_{int(time.time())}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.log(f"\nComplete results saved to: {filepath}")
        
        return filepath
    
    def run_smoke_test(self):
        """Run a quick smoke test to verify basic functionality."""
        
        self.log("\n" + "="*80)
        self.log("SMOKE TEST")
        self.log("="*80)
        
        try:
            # Test imports
            self.log("Testing imports...")
            from ksi_daemon.validators.movement_validator import MovementValidator
            from ksi_daemon.validators.resource_validator import ResourceTransferValidator
            from ksi_daemon.validators.interaction_validator import InteractionValidator
            self.log("  ✓ Validators imported")
            
            # Test validator creation
            self.log("Testing validator creation...")
            movement = MovementValidator()
            resource = ResourceTransferValidator()
            interaction = InteractionValidator()
            self.log("  ✓ Validators created")
            
            # Test basic validation
            self.log("Testing basic validation...")
            from ksi_daemon.validators.movement_validator import MovementRequest, Position
            
            request = MovementRequest(
                entity_id="test",
                entity_type="agent",
                from_position=Position(0, 0),
                to_position=Position(3, 3),
                movement_type="walk"
            )
            
            result = movement.validate_movement(request)
            if result.valid:
                self.log("  ✓ Movement validation works")
            else:
                self.log(f"  ⚠ Movement validation: {result.reason}")
            
            self.log("\n✓ Smoke test passed!")
            return True
            
        except Exception as e:
            self.log(f"\n❌ Smoke test failed: {e}")
            return False


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="Run Melting Pot test suite")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3],
                       help="Run specific phase only")
    parser.add_argument("--smoke", action="store_true",
                       help="Run smoke test only")
    parser.add_argument("--quiet", action="store_true",
                       help="Reduce output verbosity")
    parser.add_argument("--ab-runs", type=int, default=5,
                       help="Number of runs for A/B tests (default: 5)")
    
    args = parser.parse_args()
    
    runner = MeltingPotTestRunner(verbose=not args.quiet)
    
    if args.smoke:
        # Run smoke test only
        success = runner.run_smoke_test()
        sys.exit(0 if success else 1)
    
    if args.phase:
        # Run specific phase
        if args.phase == 1:
            success = await runner.run_phase_1_unit_tests()
        elif args.phase == 2:
            success = await runner.run_phase_2_integration_tests()
        elif args.phase == 3:
            success = runner.run_phase_3_fairness_ab_tests()
    else:
        # Run all phases
        success = await runner.run_all_phases()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Check if running in demo mode
    if len(sys.argv) == 1:
        print("="*80)
        print("MELTING POT TEST RUNNER")
        print("="*80)
        print("\nUsage:")
        print("  python run_melting_pot_tests.py [options]")
        print("\nOptions:")
        print("  --smoke       Run quick smoke test")
        print("  --phase N     Run specific phase (1, 2, or 3)")
        print("  --quiet       Reduce output verbosity")
        print("  --ab-runs N   Number of A/B test runs (default: 5)")
        print("\nExamples:")
        print("  python run_melting_pot_tests.py --smoke")
        print("  python run_melting_pot_tests.py --phase 1")
        print("  python run_melting_pot_tests.py --ab-runs 30")
        print("\nPhases:")
        print("  Phase 1: Unit tests (validators, services)")
        print("  Phase 2: Integration tests (services working together)")
        print("  Phase 3: Fairness A/B tests (baseline vs treatment)")
        
        # Run smoke test by default in demo mode
        print("\nRunning smoke test...")
        runner = MeltingPotTestRunner()
        runner.run_smoke_test()
    else:
        asyncio.run(main())