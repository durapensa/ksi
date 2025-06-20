#!/usr/bin/env python3

import json
import os
import statistics
from collections import defaultdict
from pathlib import Path

def analyze_cognitive_data():
    """Analyze cognitive data for entropy patterns"""
    
    data_dir = Path("cognitive_data")
    observations = []
    
    # Load all observation files
    for file_path in sorted(data_dir.glob("observation_*.json")):
        try:
            with open(file_path, 'r') as f:
                obs = json.load(f)
                observations.append(obs)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    if not observations:
        print("No observations found")
        return
    
    print(f"Analyzed {len(observations)} observations")
    
    # Extract entropy values and associated metrics
    entropies = [obs['entropy'] for obs in observations]
    content_lengths = [obs['content_length'] for obs in observations]
    token_counts = [obs['token_stats']['token_count'] for obs in observations]
    unique_tokens = [obs['token_stats']['unique_tokens'] for obs in observations]
    durations = [obs['duration_ms'] for obs in observations]
    costs = [obs['cost'] for obs in observations]
    
    # Calculate basic statistics
    stats = {
        'entropy': {
            'min': min(entropies),
            'max': max(entropies),
            'mean': statistics.mean(entropies),
            'median': statistics.median(entropies),
            'stdev': statistics.stdev(entropies) if len(entropies) > 1 else 0
        },
        'content_length': {
            'min': min(content_lengths),
            'max': max(content_lengths),
            'mean': statistics.mean(content_lengths),
            'median': statistics.median(content_lengths)
        },
        'token_count': {
            'min': min(token_counts),
            'max': max(token_counts),
            'mean': statistics.mean(token_counts),
            'median': statistics.median(token_counts)
        }
    }
    
    # Find entropy extremes
    sorted_by_entropy = sorted(observations, key=lambda x: x['entropy'])
    low_entropy = sorted_by_entropy[:10]  # Bottom 10
    high_entropy = sorted_by_entropy[-10:]  # Top 10
    
    # Analyze patterns
    low_entropy_patterns = analyze_patterns(low_entropy)
    high_entropy_patterns = analyze_patterns(high_entropy)
    
    # Time series analysis (chronological order)
    time_sorted = sorted(observations, key=lambda x: x['timestamp'])
    entropy_trend = [obs['entropy'] for obs in time_sorted]
    
    # Session analysis
    session_stats = defaultdict(list)
    for obs in observations:
        session_stats[obs['session_id']].append(obs['entropy'])
    
    session_entropy_means = {sid: statistics.mean(entropies) 
                           for sid, entropies in session_stats.items()}
    
    return {
        'stats': stats,
        'low_entropy': low_entropy,
        'high_entropy': high_entropy,
        'low_entropy_patterns': low_entropy_patterns,
        'high_entropy_patterns': high_entropy_patterns,
        'entropy_trend': entropy_trend,
        'session_entropy_means': session_entropy_means,
        'total_observations': len(observations)
    }

def analyze_patterns(observations):
    """Analyze patterns in a set of observations"""
    patterns = {
        'avg_content_length': statistics.mean([obs['content_length'] for obs in observations]),
        'avg_token_count': statistics.mean([obs['token_stats']['token_count'] for obs in observations]),
        'avg_unique_tokens': statistics.mean([obs['token_stats']['unique_tokens'] for obs in observations]),
        'avg_duration': statistics.mean([obs['duration_ms'] for obs in observations]),
        'common_frequent_tokens': [],
        'content_samples': []
    }
    
    # Find most common frequent tokens across observations
    token_frequency = defaultdict(int)
    for obs in observations:
        for token in obs['token_stats']['frequent_tokens']:
            token_frequency[token] += 1
    
    patterns['common_frequent_tokens'] = sorted(token_frequency.items(), 
                                               key=lambda x: x[1], reverse=True)[:10]
    
    # Sample content hashes for inspection
    patterns['content_samples'] = [(obs['content_hash'], obs['content_length'], obs['entropy']) 
                                  for obs in observations[:5]]
    
    return patterns

if __name__ == "__main__":
    results = analyze_cognitive_data()
    
    if results:
        print("\n=== ENTROPY ANALYSIS RESULTS ===")
        print(f"Total observations: {results['total_observations']}")
        print(f"\nEntropy Statistics:")
        print(f"  Min: {results['stats']['entropy']['min']:.3f}")
        print(f"  Max: {results['stats']['entropy']['max']:.3f}")
        print(f"  Mean: {results['stats']['entropy']['mean']:.3f}")
        print(f"  Median: {results['stats']['entropy']['median']:.3f}")
        print(f"  StdDev: {results['stats']['entropy']['stdev']:.3f}")
        
        print(f"\nLow Entropy Patterns (avg={results['low_entropy_patterns']['avg_content_length']:.1f} chars):")
        for token, freq in results['low_entropy_patterns']['common_frequent_tokens'][:5]:
            print(f"  '{token}': {freq} occurrences")
        
        print(f"\nHigh Entropy Patterns (avg={results['high_entropy_patterns']['avg_content_length']:.1f} chars):")
        for token, freq in results['high_entropy_patterns']['common_frequent_tokens'][:5]:
            print(f"  '{token}': {freq} occurrences")
        
        # Save detailed results
        with open('entropy_analysis_raw.json', 'w') as f:
            # Convert to JSON-serializable format
            serializable_results = {
                'stats': results['stats'],
                'total_observations': results['total_observations'],
                'low_entropy_sample': results['low_entropy'][:3],
                'high_entropy_sample': results['high_entropy'][:3],
                'low_entropy_patterns': results['low_entropy_patterns'],
                'high_entropy_patterns': results['high_entropy_patterns'],
                'session_count': len(results['session_entropy_means'])
            }
            json.dump(serializable_results, f, indent=2)
        
        print(f"\nDetailed results saved to entropy_analysis_raw.json")