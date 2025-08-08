#!/usr/bin/env python3
"""
Analyze cognitive overhead test results
Processes test runs and extracts metrics from KSI response logs
"""

import json
from pathlib import Path
from datetime import datetime
import statistics
import sys
from typing import Dict, List, Any

class ResultAnalyzer:
    def __init__(self):
        self.response_dir = Path("var/logs/responses")
        
    def load_test_run(self, results_file):
        """Load a test run file"""
        
        tests = []
        with open(results_file, 'r') as f:
            for line in f:
                tests.append(json.loads(line))
        
        return tests
    
    def extract_metrics(self, agent_id):
        """Extract metrics for a specific agent from response logs"""
        
        # Search recent response files
        recent_files = sorted(
            self.response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:100]  # Check last 100 files
        
        for filepath in recent_files:
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        ksi = data.get('ksi', {})
                        
                        if ksi.get('agent_id') == agent_id:
                            response = data.get('response', {})
                            usage = response.get('usage', {})
                            
                            return {
                                'found': True,
                                'num_turns': response.get('num_turns'),
                                'duration_ms': response.get('duration_ms'),
                                'duration_api_ms': response.get('duration_api_ms'),
                                'total_cost_usd': response.get('total_cost_usd'),
                                'input_tokens': usage.get('input_tokens'),
                                'output_tokens': usage.get('output_tokens'),
                                'cache_creation_tokens': usage.get('cache_creation_input_tokens', 0),
                                'cache_read_tokens': usage.get('cache_read_input_tokens', 0),
                                'total_tokens': sum([
                                    usage.get('input_tokens', 0),
                                    usage.get('output_tokens', 0),
                                    usage.get('cache_creation_input_tokens', 0),
                                    usage.get('cache_read_input_tokens', 0)
                                ])
                            }
            except:
                continue
        
        return {'found': False}
    
    def analyze_test_run(self, results_file):
        """Analyze a complete test run"""
        
        print(f"=== COGNITIVE OVERHEAD ANALYSIS ===")
        print(f"Analyzing: {results_file}\n")
        
        # Load test run
        tests = self.load_test_run(results_file)
        
        if not tests:
            print("No tests found in file")
            return
        
        session_id = tests[0].get('session_id', 'unknown')
        print(f"Session: {session_id}")
        print(f"Total tests: {len(tests)}\n")
        
        # Extract metrics for each test
        results = []
        missing = 0
        
        for test in tests:
            agent_id = test['agent_id']
            metrics = self.extract_metrics(agent_id)
            
            if metrics['found']:
                result = {**test, **metrics}
                results.append(result)
                print(f"✓ {agent_id}: {metrics.get('num_turns', '?')} turns")
            else:
                missing += 1
                print(f"✗ {agent_id}: metrics not found")
        
        if missing > 0:
            print(f"\nWarning: {missing} tests missing metrics")
        
        # Analyze by test type
        self.analyze_by_category(results)
        
        # Statistical analysis
        self.statistical_analysis(results)
        
        # Save enriched results
        self.save_analysis(results, results_file)
    
    def analyze_by_category(self, results):
        """Analyze results grouped by test category"""
        
        print("\n=== RESULTS BY CATEGORY ===\n")
        
        # Group by test name
        by_test = {}
        for r in results:
            test_name = r.get('test_name', 'unknown')
            if test_name not in by_test:
                by_test[test_name] = []
            if r.get('num_turns'):  # Only include if we have turn data
                by_test[test_name].append(r)
        
        # Calculate baseline average for normalization
        baseline_turns = []
        if 'baseline_arithmetic' in by_test:
            baseline_turns = [r['num_turns'] for r in by_test['baseline_arithmetic']]
            baseline_avg = statistics.mean(baseline_turns) if baseline_turns else 1.0
        else:
            baseline_avg = 1.0
        
        print(f"Baseline average: {baseline_avg:.1f} turns\n")
        
        # Display results for each category
        print(f"{'Test Name':<20} {'Trials':<8} {'Avg Turns':<12} {'Overhead':<10} {'Std Dev':<10} {'Range':<12}")
        print("-" * 80)
        
        for test_name in sorted(by_test.keys()):
            test_results = by_test[test_name]
            
            if test_results:
                turns = [r['num_turns'] for r in test_results]
                avg_turns = statistics.mean(turns)
                overhead = avg_turns / baseline_avg if baseline_avg > 0 else 1.0
                
                # Calculate standard deviation if we have multiple trials
                if len(turns) > 1:
                    std_dev = statistics.stdev(turns)
                    std_str = f"{std_dev:.2f}"
                else:
                    std_str = "N/A"
                
                # Range
                range_str = f"{min(turns)}-{max(turns)}" if len(turns) > 1 else str(turns[0])
                
                # Mark significant overhead
                marker = ""
                if overhead > 10:
                    marker = " 🔥"  # Extreme overhead
                elif overhead > 5:
                    marker = " ⚠️"  # High overhead
                elif overhead > 2:
                    marker = " 📈"  # Moderate overhead
                
                print(f"{test_name:<20} {len(turns):<8} {avg_turns:<12.1f} {overhead:<9.1f}x {std_str:<10} {range_str:<12}{marker}")
        
        # Show detailed turn distribution
        print("\n=== TURN DISTRIBUTION ===\n")
        
        for test_name in sorted(by_test.keys()):
            test_results = by_test[test_name]
            if test_results:
                turns = [r['num_turns'] for r in test_results]
                print(f"{test_name}: {turns}")
    
    def statistical_analysis(self, results):
        """Perform statistical analysis"""
        
        print("\n=== STATISTICAL ANALYSIS ===\n")
        
        # Extract all turn counts
        all_turns = [r['num_turns'] for r in results if r.get('num_turns')]
        
        if not all_turns:
            print("No turn data available for analysis")
            return
        
        # Basic statistics
        print(f"Total samples: {len(all_turns)}")
        print(f"Mean turns: {statistics.mean(all_turns):.2f}")
        print(f"Median turns: {statistics.median(all_turns):.1f}")
        print(f"Min turns: {min(all_turns)}")
        print(f"Max turns: {max(all_turns)}")
        
        if len(all_turns) > 1:
            print(f"Std deviation: {statistics.stdev(all_turns):.2f}")
            print(f"Variance: {statistics.variance(all_turns):.2f}")
        
        # Percentiles
        if len(all_turns) >= 4:
            sorted_turns = sorted(all_turns)
            n = len(sorted_turns)
            p25 = sorted_turns[n//4]
            p50 = sorted_turns[n//2]
            p75 = sorted_turns[3*n//4]
            
            print(f"\nPercentiles:")
            print(f"  25th: {p25}")
            print(f"  50th: {p50}")
            print(f"  75th: {p75}")
        
        # Token usage analysis
        total_tokens = [r['total_tokens'] for r in results if r.get('total_tokens')]
        if total_tokens:
            print(f"\nToken usage:")
            print(f"  Mean: {statistics.mean(total_tokens):.0f}")
            print(f"  Total: {sum(total_tokens)}")
        
        # Cost analysis
        costs = [r['total_cost_usd'] for r in results if r.get('total_cost_usd')]
        if costs:
            print(f"\nCost analysis:")
            print(f"  Total cost: ${sum(costs):.4f}")
            print(f"  Mean cost per test: ${statistics.mean(costs):.4f}")
    
    def save_analysis(self, results, original_file):
        """Save enriched analysis results"""
        
        # Create analysis filename
        analysis_file = original_file.parent / f"{original_file.stem}_analyzed.json"
        
        # Prepare analysis data
        analysis = {
            'original_file': str(original_file),
            'analysis_timestamp': datetime.now().isoformat(),
            'total_tests': len(results),
            'tests_with_metrics': len([r for r in results if r.get('found')]),
            'results': results
        }
        
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\nAnalysis saved to: {analysis_file}")


def main():
    """Main entry point"""
    
    if len(sys.argv) < 2:
        # Find most recent test run
        test_dir = Path("var/experiments/cognitive_overhead/clean_tests")
        if test_dir.exists():
            test_files = sorted(test_dir.glob("test_run_*.jsonl"), reverse=True)
            if test_files:
                results_file = test_files[0]
                print(f"Using most recent test run: {results_file.name}")
            else:
                print("No test runs found")
                print(f"Usage: {sys.argv[0]} <test_results.jsonl>")
                sys.exit(1)
        else:
            print("Test directory not found")
            sys.exit(1)
    else:
        results_file = Path(sys.argv[1])
        
        if not results_file.exists():
            print(f"File not found: {results_file}")
            sys.exit(1)
    
    # Run analysis
    analyzer = ResultAnalyzer()
    analyzer.analyze_test_run(results_file)


if __name__ == "__main__":
    main()