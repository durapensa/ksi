#!/usr/bin/env python3
"""
Analyze Cross-Model Comparison Results
Compare cognitive overhead patterns between Claude and Gemini
"""

import json
import statistics
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

class ModelComparisonAnalyzer:
    def __init__(self):
        self.response_dir = Path("var/logs/responses")
        self.comparison_dir = Path("var/experiments/cognitive_overhead/gemini_comparison")
        
    def load_comparison_data(self, session_id):
        """Load both Gemini and Claude results"""
        
        gemini_file = self.comparison_dir / f"gemini_{session_id}.jsonl"
        claude_file = self.comparison_dir / f"claude_comparison_{session_id}.jsonl"
        
        gemini_data = []
        claude_data = []
        
        if gemini_file.exists():
            with open(gemini_file, 'r') as f:
                for line in f:
                    gemini_data.append(json.loads(line))
        
        if claude_file.exists():
            with open(claude_file, 'r') as f:
                for line in f:
                    claude_data.append(json.loads(line))
        
        return gemini_data, claude_data
    
    def extract_claude_metrics(self, agent_id):
        """Extract Claude metrics from response logs"""
        
        recent_files = sorted(
            self.response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:300]
        
        for filepath in recent_files:
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        ksi = data.get('ksi', {})
                        
                        if ksi.get('agent_id') == agent_id:
                            response = data.get('response', {})
                            return {
                                'found': True,
                                'num_turns': response.get('num_turns'),
                                'duration_ms': response.get('duration_ms')
                            }
            except:
                continue
        
        return {'found': False}
    
    def analyze_comparison(self, session_id):
        """Comprehensive cross-model analysis"""
        
        print(f"=== CROSS-MODEL COMPARISON ANALYSIS ===")
        print(f"Session: {session_id}\n")
        
        # Load data
        gemini_data, claude_data = self.load_comparison_data(session_id)
        
        print(f"Gemini tests: {len(gemini_data)}")
        print(f"Claude tests: {len(claude_data)}\n")
        
        # Enrich Claude data with metrics
        for test in claude_data:
            if test.get('agent_id'):
                metrics = self.extract_claude_metrics(test['agent_id'])
                test.update(metrics)
        
        # Group by condition
        gemini_conditions = {}
        claude_conditions = {}
        
        for test in gemini_data:
            if test.get('status') == 'success':
                key = test['test_name']
                if key not in gemini_conditions:
                    gemini_conditions[key] = []
                gemini_conditions[key].append({
                    'estimated_turns': test.get('estimated_turns', 1),
                    'duration_ms': test.get('duration_ms', 0),
                    'reasoning_indicators': test.get('reasoning_indicators', 0)
                })
        
        for test in claude_data:
            if test.get('found') and test.get('num_turns'):
                key = test['test_name']
                if key not in claude_conditions:
                    claude_conditions[key] = []
                claude_conditions[key].append({
                    'num_turns': test['num_turns'],
                    'duration_ms': test.get('duration_ms', 0)
                })
        
        # Comparative analysis
        print("=== CONDITION COMPARISON ===\n")
        print(f"{'Condition':<25} {'Claude Turns':<15} {'Gemini Est.':<15} {'Ratio':<10}")
        print("-" * 70)
        
        comparison_results = []
        
        for condition in sorted(set(gemini_conditions.keys()) | set(claude_conditions.keys())):
            claude_turns = []
            gemini_turns = []
            
            if condition in claude_conditions:
                claude_turns = [d['num_turns'] for d in claude_conditions[condition]]
            
            if condition in gemini_conditions:
                gemini_turns = [d['estimated_turns'] for d in gemini_conditions[condition]]
            
            if claude_turns and gemini_turns:
                claude_mean = statistics.mean(claude_turns)
                gemini_mean = statistics.mean(gemini_turns)
                ratio = claude_mean / gemini_mean if gemini_mean > 0 else float('inf')
                
                print(f"{condition:<25} {claude_mean:<15.2f} {gemini_mean:<15.2f} {ratio:<10.2f}")
                
                comparison_results.append({
                    'condition': condition,
                    'claude_mean': claude_mean,
                    'gemini_mean': gemini_mean,
                    'ratio': ratio
                })
        
        # Test for model-specific effects
        self.test_model_specificity(comparison_results)
        
        # Analyze reasoning indicators in Gemini
        self.analyze_gemini_reasoning(gemini_conditions)
        
        # Duration comparison
        self.compare_durations(claude_conditions, gemini_conditions)
        
        # Generate visualization
        self.create_comparison_plot(comparison_results, session_id)
        
        return comparison_results
    
    def test_model_specificity(self, results):
        """Test if overhead patterns are model-specific"""
        
        print("\n=== MODEL SPECIFICITY ANALYSIS ===\n")
        
        # Look for conditions with high Claude overhead
        high_overhead_claude = [r for r in results if r['claude_mean'] > 3]
        
        if high_overhead_claude:
            print("Conditions with high Claude overhead (>3 turns):")
            for r in high_overhead_claude:
                print(f"  {r['condition']}: Claude={r['claude_mean']:.2f}, Gemini={r['gemini_mean']:.2f}")
                
                if r['gemini_mean'] < 2:
                    print(f"    ✓ Claude-specific effect (Gemini shows no overhead)")
                elif r['gemini_mean'] > 3:
                    print(f"    ✓ Universal effect (both models show overhead)")
                else:
                    print(f"    ⚠ Partial effect (Gemini shows reduced overhead)")
        else:
            print("No high-overhead conditions found in Claude")
        
        # Calculate correlation
        if len(results) >= 3:
            claude_values = [r['claude_mean'] for r in results]
            gemini_values = [r['gemini_mean'] for r in results]
            
            if len(set(claude_values)) > 1 and len(set(gemini_values)) > 1:
                correlation = np.corrcoef(claude_values, gemini_values)[0, 1]
                print(f"\nCorrelation between models: {correlation:.3f}")
                
                if abs(correlation) > 0.7:
                    print("✓ Strong correlation - effects likely universal")
                elif abs(correlation) > 0.3:
                    print("⚠ Moderate correlation - mixed effects")
                else:
                    print("✗ Weak correlation - model-specific effects")
    
    def analyze_gemini_reasoning(self, gemini_conditions):
        """Analyze reasoning patterns in Gemini responses"""
        
        print("\n=== GEMINI REASONING ANALYSIS ===\n")
        
        for condition, data_points in gemini_conditions.items():
            if data_points:
                reasoning_counts = [d['reasoning_indicators'] for d in data_points]
                mean_reasoning = statistics.mean(reasoning_counts)
                
                if mean_reasoning > 3:
                    print(f"{condition}: High reasoning ({mean_reasoning:.1f} indicators)")
                elif mean_reasoning > 1:
                    print(f"{condition}: Moderate reasoning ({mean_reasoning:.1f} indicators)")
    
    def compare_durations(self, claude_conditions, gemini_conditions):
        """Compare execution durations between models"""
        
        print("\n=== DURATION COMPARISON ===\n")
        
        claude_durations = []
        gemini_durations = []
        
        for condition, data_points in claude_conditions.items():
            for d in data_points:
                if d.get('duration_ms'):
                    claude_durations.append(d['duration_ms'])
        
        for condition, data_points in gemini_conditions.items():
            for d in data_points:
                if d.get('duration_ms'):
                    gemini_durations.append(d['duration_ms'])
        
        if claude_durations and gemini_durations:
            print(f"Claude avg duration: {statistics.mean(claude_durations):.0f}ms")
            print(f"Gemini avg duration: {statistics.mean(gemini_durations):.0f}ms")
            
            ratio = statistics.mean(gemini_durations) / statistics.mean(claude_durations)
            print(f"Gemini/Claude ratio: {ratio:.2f}x")
    
    def create_comparison_plot(self, results, session_id):
        """Create visualization of model comparison"""
        
        if not results:
            return
        
        try:
            conditions = [r['condition'].replace('_', '\n') for r in results]
            claude_means = [r['claude_mean'] for r in results]
            gemini_means = [r['gemini_mean'] for r in results]
            
            x = np.arange(len(conditions))
            width = 0.35
            
            fig, ax = plt.subplots(figsize=(12, 6))
            bars1 = ax.bar(x - width/2, claude_means, width, label='Claude', color='#4A90E2')
            bars2 = ax.bar(x + width/2, gemini_means, width, label='Gemini', color='#F5A623')
            
            ax.set_xlabel('Test Condition')
            ax.set_ylabel('Turns / Complexity')
            ax.set_title('Cognitive Overhead: Claude vs Gemini Comparison')
            ax.set_xticks(x)
            ax.set_xticklabels(conditions, rotation=45, ha='right')
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            
            # Add value labels on bars
            for bar in bars1:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}', ha='center', va='bottom', fontsize=8)
            
            for bar in bars2:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}', ha='center', va='bottom', fontsize=8)
            
            plt.tight_layout()
            plot_file = self.comparison_dir / f"comparison_plot_{session_id}.png"
            plt.savefig(plot_file, dpi=150)
            print(f"\nPlot saved to: {plot_file}")
            plt.close()
            
        except Exception as e:
            print(f"Could not create plot: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_model_comparison.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    analyzer = ModelComparisonAnalyzer()
    analyzer.analyze_comparison(session_id)

if __name__ == "__main__":
    main()