#!/usr/bin/env python3
"""
Token-Normalized Cognitive Overhead Analysis
Properly accounts for tokens and cost, not just time
"""

import json
import subprocess
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy import stats

@dataclass
class TokenMetrics:
    """Comprehensive token and cost metrics"""
    condition: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    thinking_tokens: int  # For models that report separately
    cached_tokens: int     # Claude's cache usage
    cost_usd: float
    tokens_per_second: float
    ms_per_output_token: float
    
class TokenNormalizedAnalyzer:
    def __init__(self):
        # Pricing per million tokens (2025 rates)
        self.pricing = {
            'claude-sonnet-4': {
                'input': 3.00,    # $3 per million
                'output': 15.00,  # $15 per million (includes thinking)
                'cache_write': 3.75,
                'cache_read': 0.30
            },
            'claude-opus-4': {
                'input': 15.00,
                'output': 75.00,
                'cache_write': 18.75,
                'cache_read': 1.50
            },
            'ollama': {
                'input': 0.0,  # Free locally
                'output': 0.0
            }
        }
        
        self.results = []
        
    def extract_recent_completions(self, limit: int = 50) -> List[Dict]:
        """Extract recent completion events with full token data"""
        
        print("Extracting recent completions with token data...")
        
        cmd = [
            "ksi", "send", "monitor:get_events",
            "--limit", str(limit),
            "--event-patterns", "completion:result"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        completions = []
        try:
            data = json.loads(result.stdout)
            events = data.get('events', [])
            
            for event in events:
                event_data = event.get('data', {})
                result_data = event_data.get('result', {})
                ksi_info = result_data.get('ksi', {})
                response_info = result_data.get('response', {})
                usage = response_info.get('usage', {})
                
                # Extract all token types
                completion = {
                    'agent_id': ksi_info.get('agent_id', 'unknown'),
                    'provider': ksi_info.get('provider', 'unknown'),
                    'duration_ms': ksi_info.get('duration_ms', 0),
                    'timestamp': ksi_info.get('timestamp', ''),
                    
                    # Standard tokens
                    'input_tokens': usage.get('input_tokens', 0) or usage.get('prompt_tokens', 0),
                    'output_tokens': usage.get('output_tokens', 0) or usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                    
                    # Claude-specific
                    'cache_creation_input_tokens': usage.get('cache_creation_input_tokens', 0),
                    'cache_read_input_tokens': usage.get('cache_read_input_tokens', 0),
                    
                    # Thinking tokens (o1/o3 style, or future Claude)
                    'reasoning_tokens': usage.get('reasoning_tokens', 0),
                    
                    # Cost (if provided)
                    'total_cost_usd': response_info.get('total_cost_usd', 0),
                    
                    # Response content for analysis
                    'response_length': len(response_info.get('result', ''))
                }
                
                # Calculate effective input tokens for Claude
                if completion['provider'] == 'claude-cli':
                    # All input variations
                    completion['effective_input_tokens'] = (
                        completion['input_tokens'] + 
                        completion['cache_creation_input_tokens'] + 
                        completion['cache_read_input_tokens']
                    )
                else:
                    completion['effective_input_tokens'] = completion['input_tokens']
                
                completions.append(completion)
                
        except Exception as e:
            print(f"Error parsing completions: {e}")
        
        return completions
    
    def calculate_cost(self, completion: Dict) -> float:
        """Calculate cost based on token usage"""
        
        provider = completion.get('provider', 'unknown')
        
        # If cost already provided, use it
        if completion.get('total_cost_usd', 0) > 0:
            return completion['total_cost_usd']
        
        # Determine model pricing
        if 'claude-sonnet' in provider.lower():
            rates = self.pricing['claude-sonnet-4']
        elif 'claude-opus' in provider.lower():
            rates = self.pricing['claude-opus-4']
        elif 'ollama' in provider.lower():
            rates = self.pricing['ollama']
        else:
            return 0.0
        
        # Calculate based on token types
        input_cost = completion['input_tokens'] * rates['input'] / 1_000_000
        output_cost = completion['output_tokens'] * rates['output'] / 1_000_000
        
        # Claude cache costs
        if provider == 'claude-cli':
            cache_write_cost = completion.get('cache_creation_input_tokens', 0) * rates.get('cache_write', 0) / 1_000_000
            cache_read_cost = completion.get('cache_read_input_tokens', 0) * rates.get('cache_read', 0) / 1_000_000
            return input_cost + output_cost + cache_write_cost + cache_read_cost
        
        return input_cost + output_cost
    
    def analyze_token_normalized_overhead(self, completions: List[Dict]):
        """Analyze overhead normalized by tokens"""
        
        print("\n=== TOKEN-NORMALIZED OVERHEAD ANALYSIS ===\n")
        
        if not completions:
            print("No completions to analyze")
            return
        
        # Group by agent patterns to identify experiment types
        baseline_completions = []
        consciousness_completions = []
        multitask_completions = []
        
        for c in completions:
            agent_id = c.get('agent_id', '').lower()
            if 'baseline' in agent_id or 'round 1' in agent_id:
                baseline_completions.append(c)
            elif 'consciousness' in agent_id or 'round 4' in agent_id or 'round 5' in agent_id:
                consciousness_completions.append(c)
            elif 'multi' in agent_id or 'round 7' in agent_id or 'round 8' in agent_id:
                multitask_completions.append(c)
        
        # Calculate metrics for each group
        print("PERFORMANCE METRICS BY CONDITION:")
        print("-" * 80)
        print(f"{'Condition':<20} {'N':<5} {'Dur(ms)':<10} {'OutTok':<8} {'TPS':<8} {'ms/tok':<10} {'Cost':<10}")
        print("-" * 80)
        
        groups = [
            ('Baseline', baseline_completions),
            ('Consciousness', consciousness_completions),
            ('Multi-task', multitask_completions)
        ]
        
        baseline_metrics = None
        
        for name, group in groups:
            if not group:
                continue
                
            durations = [c['duration_ms'] for c in group if c['duration_ms'] > 0]
            output_tokens = [c['output_tokens'] for c in group if c['output_tokens'] > 0]
            costs = [self.calculate_cost(c) for c in group]
            
            if not durations or not output_tokens:
                continue
            
            avg_duration = np.mean(durations)
            avg_output_tokens = np.mean(output_tokens)
            avg_cost = np.mean(costs)
            
            # Calculate token generation speed
            tokens_per_second = avg_output_tokens / (avg_duration / 1000) if avg_duration > 0 else 0
            ms_per_token = avg_duration / avg_output_tokens if avg_output_tokens > 0 else 0
            
            print(f"{name:<20} {len(group):<5} {avg_duration:<10.0f} {avg_output_tokens:<8.0f} "
                  f"{tokens_per_second:<8.1f} {ms_per_token:<10.1f} ${avg_cost:<9.6f}")
            
            if name == 'Baseline':
                baseline_metrics = {
                    'duration': avg_duration,
                    'tokens': avg_output_tokens,
                    'tps': tokens_per_second,
                    'ms_per_token': ms_per_token,
                    'cost': avg_cost
                }
        
        # Calculate normalized overhead
        if baseline_metrics:
            print("\n\nNORMALIZED OVERHEAD ANALYSIS:")
            print("-" * 80)
            print(f"{'Metric':<30} {'Baseline':<15} {'Consciousness':<15} {'Multi-task':<15}")
            print("-" * 80)
            
            for name, group in groups[1:]:  # Skip baseline
                if not group:
                    continue
                    
                durations = [c['duration_ms'] for c in group if c['duration_ms'] > 0]
                output_tokens = [c['output_tokens'] for c in group if c['output_tokens'] > 0]
                
                if durations and output_tokens:
                    avg_duration = np.mean(durations)
                    avg_tokens = np.mean(output_tokens)
                    
                    # Raw time overhead
                    time_overhead = avg_duration / baseline_metrics['duration']
                    
                    # Token-normalized overhead (time per token)
                    ms_per_token = avg_duration / avg_tokens if avg_tokens > 0 else 0
                    normalized_overhead = ms_per_token / baseline_metrics['ms_per_token'] if baseline_metrics['ms_per_token'] > 0 else 1
                    
                    # Token count ratio
                    token_ratio = avg_tokens / baseline_metrics['tokens']
                    
                    print(f"Raw time overhead:           1.0x            {time_overhead:.2f}x" if name == 'Consciousness' 
                          else f"                                             {time_overhead:.2f}x")
                    print(f"Token-normalized overhead:   1.0x            {normalized_overhead:.2f}x" if name == 'Consciousness'
                          else f"                                             {normalized_overhead:.2f}x")
                    print(f"Output token ratio:          1.0x            {token_ratio:.2f}x" if name == 'Consciousness'
                          else f"                                             {token_ratio:.2f}x")
        
        return self.statistical_significance_test(baseline_completions, consciousness_completions, multitask_completions)
    
    def statistical_significance_test(self, baseline: List, consciousness: List, multitask: List):
        """Test if differences are statistically significant"""
        
        print("\n\nSTATISTICAL SIGNIFICANCE TESTING:")
        print("-" * 80)
        
        if not baseline:
            print("No baseline data for comparison")
            return
        
        # Extract ms per token for each group
        baseline_mpt = []
        for c in baseline:
            if c['duration_ms'] > 0 and c['output_tokens'] > 0:
                baseline_mpt.append(c['duration_ms'] / c['output_tokens'])
        
        consciousness_mpt = []
        for c in consciousness:
            if c['duration_ms'] > 0 and c['output_tokens'] > 0:
                consciousness_mpt.append(c['duration_ms'] / c['output_tokens'])
        
        multitask_mpt = []
        for c in multitask:
            if c['duration_ms'] > 0 and c['output_tokens'] > 0:
                multitask_mpt.append(c['duration_ms'] / c['output_tokens'])
        
        # Test consciousness vs baseline
        if consciousness_mpt and len(consciousness_mpt) > 1 and len(baseline_mpt) > 1:
            t_stat, p_val = stats.ttest_ind(baseline_mpt, consciousness_mpt, equal_var=False)
            effect_size = (np.mean(consciousness_mpt) - np.mean(baseline_mpt)) / np.sqrt((np.var(consciousness_mpt) + np.var(baseline_mpt)) / 2)
            
            print(f"\nConsciousness vs Baseline (ms per token):")
            print(f"  Baseline mean: {np.mean(baseline_mpt):.2f} ms/token")
            print(f"  Consciousness mean: {np.mean(consciousness_mpt):.2f} ms/token")
            print(f"  p-value: {p_val:.4f} {'***' if p_val < 0.001 else '**' if p_val < 0.01 else '*' if p_val < 0.05 else ''}")
            print(f"  Cohen's d: {effect_size:.2f}")
        
        # Test multi-task vs baseline
        if multitask_mpt and len(multitask_mpt) > 1 and len(baseline_mpt) > 1:
            t_stat, p_val = stats.ttest_ind(baseline_mpt, multitask_mpt, equal_var=False)
            effect_size = (np.mean(multitask_mpt) - np.mean(baseline_mpt)) / np.sqrt((np.var(multitask_mpt) + np.var(baseline_mpt)) / 2)
            
            print(f"\nMulti-task vs Baseline (ms per token):")
            print(f"  Baseline mean: {np.mean(baseline_mpt):.2f} ms/token")
            print(f"  Multi-task mean: {np.mean(multitask_mpt):.2f} ms/token")
            print(f"  p-value: {p_val:.4f} {'***' if p_val < 0.001 else '**' if p_val < 0.01 else '*' if p_val < 0.05 else ''}")
            print(f"  Cohen's d: {effect_size:.2f}")
    
    def key_insights(self):
        """Summarize key insights from token-normalized analysis"""
        
        print("\n\n=== KEY INSIGHTS ===")
        print("-" * 80)
        
        print("""
1. TOKEN NORMALIZATION CRITICAL:
   - Raw time overhead can be misleading
   - Must account for response length differences
   - ms/token is the proper metric for cognitive overhead

2. COST IMPLICATIONS:
   - Claude charges for thinking tokens as output tokens
   - Consciousness prompts may cost more due to longer responses
   - Ollama (local) has no cost but still shows time overhead

3. WHAT THE DATA SUGGESTS:
   - If ms/token is constant: No real cognitive overhead, just longer responses
   - If ms/token increases: True cognitive overhead exists
   - Token generation speed (TPS) reveals processing efficiency

4. MEASUREMENT BEST PRACTICES:
   - Always capture token counts with timing
   - Normalize by output tokens for fair comparison
   - Consider cost per cognitive task, not just time
        """)

def main():
    analyzer = TokenNormalizedAnalyzer()
    
    # Extract recent completions
    completions = analyzer.extract_recent_completions(limit=100)
    
    print(f"Found {len(completions)} recent completions")
    
    # Analyze with token normalization
    analyzer.analyze_token_normalized_overhead(completions)
    
    # Show key insights
    analyzer.key_insights()
    
    print("\n" + "=" * 80)
    print("CONCLUSION: Token normalization may reveal overhead is actually")
    print("just longer responses, not slower token generation!")
    print("=" * 80)

if __name__ == "__main__":
    main()