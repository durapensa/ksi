#!/usr/bin/env python3

import json
import statistics
import math
from pathlib import Path
from collections import defaultdict

def pearsonr(x, y):
    """Simple Pearson correlation calculation"""
    if len(x) != len(y) or len(x) < 2:
        return (0, 1)
    
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)
    sum_y2 = sum(yi * yi for yi in y)
    
    numerator = n * sum_xy - sum_x * sum_y
    denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
    
    if denominator == 0:
        return (0, 1)
    
    r = numerator / denominator
    return (r, 0.05)  # Simplified p-value

def load_cognitive_observations():
    """Load all cognitive observations with cost, entropy, and quality metrics"""
    data_dir = Path("cognitive_data")
    observations = []
    
    for file_path in sorted(data_dir.glob("observation_*.json")):
        try:
            with open(file_path, 'r') as f:
                obs = json.load(f)
                observations.append(obs)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return observations

def calculate_quality_metrics(obs):
    """Calculate response quality indicators from observation data"""
    
    # Content complexity indicators
    content_length = obs['content_length'] 
    token_count = obs['token_stats']['token_count']
    unique_tokens = obs['token_stats']['unique_tokens']
    avg_token_length = obs['token_stats']['avg_token_length']
    
    # Quality proxies
    token_diversity = unique_tokens / max(token_count, 1)  # Higher = more diverse vocabulary
    conceptual_density = len(obs['concept_edges']) / max(content_length, 1)  # Concepts per character
    
    # Efficiency proxies
    chars_per_ms = content_length / max(obs['duration_ms'], 1)  # Generation speed
    tokens_per_dollar = token_count / max(obs['cost'], 0.001)  # Token efficiency
    
    # Information density
    info_density = obs['entropy'] * unique_tokens / max(content_length, 1)
    
    return {
        'token_diversity': token_diversity,
        'conceptual_density': conceptual_density,
        'chars_per_ms': chars_per_ms,
        'tokens_per_dollar': tokens_per_dollar,
        'info_density': info_density,
        'avg_token_length': avg_token_length,
        'concept_count': len(obs['concept_edges'])
    }

def analyze_cost_entropy_correlations(observations):
    """Analyze correlations between cost, entropy, and quality metrics"""
    
    # Extract base metrics
    costs = []
    entropies = []
    durations = []
    content_lengths = []
    quality_metrics = []
    
    valid_obs = []
    for obs in observations:
        if obs['cost'] > 0 and obs['content_length'] > 0:  # Valid observations only
            costs.append(obs['cost'])
            entropies.append(obs['entropy'])
            durations.append(obs['duration_ms'])
            content_lengths.append(obs['content_length'])
            quality_metrics.append(calculate_quality_metrics(obs))
            valid_obs.append(obs)
    
    if len(valid_obs) < 3:
        return {"error": "Insufficient valid observations"}
    
    # Calculate correlations
    correlations = {}
    
    # Core correlations
    try:
        correlations['cost_entropy'] = pearsonr(costs, entropies)
        correlations['cost_content_length'] = pearsonr(costs, content_lengths)
        correlations['entropy_content_length'] = pearsonr(entropies, content_lengths)
        correlations['duration_cost'] = pearsonr(durations, costs)
    except:
        correlations['calculation_error'] = True
    
    # Quality metric correlations
    quality_arrays = {}
    for metric in quality_metrics[0].keys():
        quality_arrays[metric] = [qm[metric] for qm in quality_metrics]
    
    # Correlate quality metrics with cost and entropy
    quality_correlations = {}
    for metric, values in quality_arrays.items():
        try:
            quality_correlations[f'{metric}_vs_cost'] = pearsonr(values, costs)
            quality_correlations[f'{metric}_vs_entropy'] = pearsonr(values, entropies)
        except:
            quality_correlations[f'{metric}_error'] = True
    
    return {
        'core_correlations': correlations,
        'quality_correlations': quality_correlations,
        'sample_size': len(valid_obs),
        'cost_stats': {
            'min': min(costs),
            'max': max(costs),
            'mean': statistics.mean(costs),
            'median': statistics.median(costs)
        },
        'entropy_stats': {
            'min': min(entropies),
            'max': max(entropies),
            'mean': statistics.mean(entropies),
            'median': statistics.median(entropies)
        }
    }

def identify_efficiency_patterns(observations):
    """Identify patterns for optimal cost/quality ratios"""
    
    valid_obs = [obs for obs in observations if obs['cost'] > 0 and obs['content_length'] > 0]
    
    if len(valid_obs) < 5:
        return {"error": "Insufficient data for pattern analysis"}
    
    # Calculate efficiency metrics for each observation
    efficiency_data = []
    for obs in valid_obs:
        quality = calculate_quality_metrics(obs)
        
        # Define efficiency scores
        cost_per_token = obs['cost'] / max(obs['token_stats']['token_count'], 1)
        cost_per_concept = obs['cost'] / max(len(obs['concept_edges']), 1)
        entropy_per_dollar = obs['entropy'] / max(obs['cost'], 0.001)
        quality_per_dollar = quality['token_diversity'] / max(obs['cost'], 0.001)
        
        efficiency_data.append({
            'session_id': obs['session_id'],
            'cost': obs['cost'],
            'entropy': obs['entropy'],
            'content_length': obs['content_length'],
            'cost_per_token': cost_per_token,
            'cost_per_concept': cost_per_concept,
            'entropy_per_dollar': entropy_per_dollar,
            'quality_per_dollar': quality_per_dollar,
            'token_diversity': quality['token_diversity'],
            'conceptual_density': quality['conceptual_density'],
            'info_density': quality['info_density']
        })
    
    # Sort by different efficiency metrics
    by_entropy_per_dollar = sorted(efficiency_data, key=lambda x: x['entropy_per_dollar'], reverse=True)
    by_quality_per_dollar = sorted(efficiency_data, key=lambda x: x['quality_per_dollar'], reverse=True)
    by_cost_per_token = sorted(efficiency_data, key=lambda x: x['cost_per_token'])
    
    # Identify optimal ranges
    top_10_pct = len(efficiency_data) // 10 or 1
    
    optimal_patterns = {
        'most_entropy_per_dollar': by_entropy_per_dollar[:top_10_pct],
        'most_quality_per_dollar': by_quality_per_dollar[:top_10_pct],
        'lowest_cost_per_token': by_cost_per_token[:top_10_pct]
    }
    
    # Calculate pattern statistics
    pattern_stats = {}
    for pattern_name, pattern_data in optimal_patterns.items():
        if pattern_data:
            pattern_stats[pattern_name] = {
                'avg_cost': statistics.mean([p['cost'] for p in pattern_data]),
                'avg_entropy': statistics.mean([p['entropy'] for p in pattern_data]),
                'avg_content_length': statistics.mean([p['content_length'] for p in pattern_data]),
                'avg_token_diversity': statistics.mean([p['token_diversity'] for p in pattern_data]),
                'count': len(pattern_data)
            }
    
    return {
        'optimal_patterns': optimal_patterns,
        'pattern_statistics': pattern_stats,
        'efficiency_distribution': {
            'entropy_per_dollar_range': [
                min(d['entropy_per_dollar'] for d in efficiency_data),
                max(d['entropy_per_dollar'] for d in efficiency_data)
            ],
            'quality_per_dollar_range': [
                min(d['quality_per_dollar'] for d in efficiency_data),
                max(d['quality_per_dollar'] for d in efficiency_data)
            ]
        }
    }

def generate_recommendations(correlations, patterns):
    """Generate actionable recommendations based on analysis"""
    
    recommendations = []
    
    # Cost-entropy relationship
    if 'core_correlations' in correlations:
        cost_entropy_corr = correlations['core_correlations'].get('cost_entropy')
        if cost_entropy_corr and cost_entropy_corr[0] > 0.3:
            recommendations.append({
                'type': 'cost_optimization',
                'finding': f'Strong positive correlation (r={cost_entropy_corr[0]:.3f}) between cost and entropy',
                'recommendation': 'Higher entropy responses cost more but may provide more information density',
                'action': 'Monitor entropy vs cost tradeoffs for specific use cases'
            })
    
    # Quality patterns
    if 'pattern_statistics' in patterns:
        for pattern_name, stats in patterns['pattern_statistics'].items():
            if 'entropy_per_dollar' in pattern_name and stats['count'] > 2:
                recommendations.append({
                    'type': 'efficiency_pattern',
                    'finding': f'Most entropy-efficient responses average {stats["avg_cost"]:.4f} cost',
                    'recommendation': f'Target cost range around {stats["avg_cost"]:.4f} for optimal entropy/cost ratio',
                    'action': f'Aim for {stats["avg_content_length"]:.0f} char responses with {stats["avg_entropy"]:.2f} entropy'
                })
    
    # Quality correlations
    if 'quality_correlations' in correlations:
        quality_corrs = correlations['quality_correlations']
        for metric, corr_data in quality_corrs.items():
            if isinstance(corr_data, tuple) and abs(corr_data[0]) > 0.4:
                recommendations.append({
                    'type': 'quality_insight',
                    'finding': f'Strong correlation: {metric} (r={corr_data[0]:.3f})',
                    'recommendation': f'Monitor {metric.replace("_", " ")} as quality indicator',
                    'action': 'Incorporate into prompt optimization strategy'
                })
    
    return recommendations

def main():
    """Main analysis execution"""
    print("Loading cognitive observations...")
    observations = load_cognitive_observations()
    
    if not observations:
        print("No observations found!")
        return
    
    print(f"Analyzing {len(observations)} observations...")
    
    # Perform correlation analysis
    correlations = analyze_cost_entropy_correlations(observations)
    
    # Identify efficiency patterns
    patterns = identify_efficiency_patterns(observations)
    
    # Generate recommendations
    recommendations = generate_recommendations(correlations, patterns)
    
    # Compile results
    results = {
        'analysis_metadata': {
            'total_observations': len(observations),
            'valid_observations': correlations.get('sample_size', 0),
            'analysis_timestamp': 1750400000  # Placeholder
        },
        'correlations': correlations,
        'efficiency_patterns': patterns,
        'recommendations': recommendations
    }
    
    # Save results
    with open('efficiency_correlation_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nAnalysis complete!")
    print(f"Processed {correlations.get('sample_size', 0)} valid observations")
    print(f"Generated {len(recommendations)} recommendations")
    print(f"Results saved to efficiency_correlation_results.json")
    
    return results

if __name__ == "__main__":
    main()