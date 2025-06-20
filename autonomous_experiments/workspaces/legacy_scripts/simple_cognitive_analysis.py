#!/usr/bin/env python3

import json
import math
from pathlib import Path
from collections import defaultdict, Counter
import statistics

def load_cognitive_data():
    """Load all cognitive observation files."""
    cognitive_dir = Path("cognitive_data")
    observations = []
    
    if not cognitive_dir.exists():
        print("No cognitive_data directory found")
        return []
    
    for file_path in cognitive_dir.glob("observation_*.json"):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                observations.append(data)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return sorted(observations, key=lambda x: x['timestamp'])

def simple_clustering(observations, n_clusters=5):
    """Simple clustering based on entropy and content length."""
    if not observations:
        return {}
    
    # Extract key features for simple clustering
    features = []
    for obs in observations:
        entropy = obs.get('entropy', 0)
        content_length = obs.get('content_length', 0)
        token_count = obs.get('token_stats', {}).get('token_count', 0)
        unique_tokens = obs.get('token_stats', {}).get('unique_tokens', 0)
        duration = obs.get('duration_ms', 0) / 1000  # Convert to seconds
        
        # Calculate diversity ratio
        diversity = unique_tokens / max(token_count, 1)
        
        features.append({
            'observation': obs,
            'entropy': entropy,
            'content_length': content_length,
            'token_count': token_count,
            'diversity': diversity,
            'duration': duration,
            'complexity_score': entropy * math.log(content_length + 1)
        })
    
    # Simple clustering based on entropy ranges
    clusters = {
        'minimal_response': [],      # Very low entropy, short responses
        'focused_analytical': [],    # Medium-high entropy, structured responses
        'exploratory_creative': [],  # High entropy, varied vocabulary
        'technical_detailed': [],    # High complexity, long responses
        'conversational_flow': []    # Medium entropy, balanced responses
    }
    
    for feature in features:
        entropy = feature['entropy']
        content_length = feature['content_length']
        diversity = feature['diversity']
        complexity = feature['complexity_score']
        
        # Classification logic
        if entropy < 1.0 or content_length < 10:
            clusters['minimal_response'].append(feature)
        elif entropy > 4.5 and content_length > 1000:
            clusters['technical_detailed'].append(feature)
        elif entropy > 4.0 and diversity > 0.8:
            clusters['exploratory_creative'].append(feature)
        elif entropy > 3.5 and content_length > 200:
            clusters['focused_analytical'].append(feature)
        else:
            clusters['conversational_flow'].append(feature)
    
    return clusters

def analyze_temporal_patterns(observations):
    """Analyze temporal patterns in cognitive data."""
    if not observations:
        return {}
    
    # Sort by timestamp
    sorted_obs = sorted(observations, key=lambda x: x['timestamp'])
    
    # Calculate time-based metrics
    timestamps = [obs['timestamp'] for obs in sorted_obs]
    entropies = [obs.get('entropy', 0) for obs in sorted_obs]
    
    # Moving averages (window of 5)
    moving_entropies = []
    for i in range(len(entropies)):
        start_idx = max(0, i - 2)
        end_idx = min(len(entropies), i + 3)
        window = entropies[start_idx:end_idx]
        moving_entropies.append(statistics.mean(window))
    
    # Session analysis
    session_patterns = defaultdict(list)
    for obs in observations:
        session_id = obs.get('session_id', 'unknown')
        session_patterns[session_id].append({
            'timestamp': obs['timestamp'],
            'entropy': obs.get('entropy', 0),
            'content_length': obs.get('content_length', 0)
        })
    
    # Calculate session statistics
    session_stats = {}
    for session_id, session_data in session_patterns.items():
        if len(session_data) > 1:
            entropies = [d['entropy'] for d in session_data]
            session_stats[session_id] = {
                'observation_count': len(session_data),
                'avg_entropy': statistics.mean(entropies),
                'entropy_std': statistics.stdev(entropies) if len(entropies) > 1 else 0,
                'entropy_trend': calculate_trend(entropies),
                'duration_span': session_data[-1]['timestamp'] - session_data[0]['timestamp']
            }
    
    return {
        'total_span_hours': (timestamps[-1] - timestamps[0]) / 3600,
        'entropy_trend': calculate_trend(entropies),
        'moving_averages': moving_entropies,
        'session_statistics': session_stats,
        'entropy_statistics': {
            'mean': statistics.mean(entropies),
            'median': statistics.median(entropies),
            'std': statistics.stdev(entropies) if len(entropies) > 1 else 0,
            'min': min(entropies),
            'max': max(entropies)
        }
    }

def calculate_trend(values):
    """Calculate simple linear trend."""
    if len(values) < 2:
        return 0
    
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(values)
    
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    
    return numerator / denominator if denominator != 0 else 0

def identify_cognitive_attractors(clusters):
    """Identify cognitive attractors from clusters."""
    attractors = {}
    
    for cluster_name, cluster_data in clusters.items():
        if not cluster_data:
            continue
            
        # Calculate cluster statistics
        entropies = [d['entropy'] for d in cluster_data]
        content_lengths = [d['content_length'] for d in cluster_data]
        diversities = [d['diversity'] for d in cluster_data]
        durations = [d['duration'] for d in cluster_data]
        
        # Get sessions in this cluster
        sessions = [d['observation'].get('session_id', 'unknown') for d in cluster_data]
        session_distribution = Counter(sessions)
        
        # Sample observations
        samples = cluster_data[:3] if len(cluster_data) >= 3 else cluster_data
        
        attractors[cluster_name] = {
            'size': len(cluster_data),
            'percentage': len(cluster_data) / sum(len(c) for c in clusters.values()) * 100,
            'entropy_stats': {
                'mean': statistics.mean(entropies),
                'std': statistics.stdev(entropies) if len(entropies) > 1 else 0,
                'min': min(entropies),
                'max': max(entropies)
            },
            'content_stats': {
                'mean_length': statistics.mean(content_lengths),
                'std_length': statistics.stdev(content_lengths) if len(content_lengths) > 1 else 0
            },
            'diversity_stats': {
                'mean': statistics.mean(diversities),
                'std': statistics.stdev(diversities) if len(diversities) > 1 else 0
            },
            'temporal_stats': {
                'mean_duration': statistics.mean(durations),
                'std_duration': statistics.stdev(durations) if len(durations) > 1 else 0
            },
            'session_distribution': dict(session_distribution),
            'sample_observations': [
                {
                    'timestamp': d['observation']['timestamp'],
                    'session_id': d['observation'].get('session_id', 'unknown'),
                    'entropy': d['entropy'],
                    'content_length': d['content_length'],
                    'content_hash': d['observation'].get('content_hash', '')
                } for d in samples
            ]
        }
    
    return attractors

def analyze_cognitive_modes(attractors, temporal_patterns):
    """Analyze distinct cognitive modes."""
    modes = {}
    
    # Sort attractors by size
    sorted_attractors = sorted(attractors.items(), 
                             key=lambda x: x[1]['size'], reverse=True)
    
    for attractor_name, attractor_data in sorted_attractors:
        # Characterize the mode
        entropy_mean = attractor_data['entropy_stats']['mean']
        content_mean = attractor_data['content_stats']['mean_length']
        diversity_mean = attractor_data['diversity_stats']['mean']
        duration_mean = attractor_data['temporal_stats']['mean_duration']
        
        characteristics = []
        
        # Entropy characteristics
        if entropy_mean > 4.0:
            characteristics.append("high_entropy")
        elif entropy_mean < 2.0:
            characteristics.append("low_entropy")
        else:
            characteristics.append("medium_entropy")
            
        # Content characteristics
        if content_mean > 1000:
            characteristics.append("verbose")
        elif content_mean < 100:
            characteristics.append("concise")
        else:
            characteristics.append("moderate_length")
            
        # Diversity characteristics
        if diversity_mean > 0.8:
            characteristics.append("diverse_vocabulary")
        elif diversity_mean < 0.5:
            characteristics.append("repetitive_patterns")
        else:
            characteristics.append("balanced_vocabulary")
            
        # Duration characteristics
        if duration_mean > 30:
            characteristics.append("deliberative")
        elif duration_mean < 5:
            characteristics.append("rapid_response")
        else:
            characteristics.append("measured_response")
        
        modes[attractor_name] = {
            'size': attractor_data['size'],
            'percentage': attractor_data['percentage'],
            'characteristics': characteristics,
            'cognitive_signature': {
                'entropy_level': entropy_mean,
                'response_length': content_mean,
                'vocabulary_diversity': diversity_mean,
                'processing_time': duration_mean
            },
            'session_affinity': attractor_data['session_distribution']
        }
    
    return modes

def main():
    print("Loading cognitive data...")
    observations = load_cognitive_data()
    
    if len(observations) < 5:
        print(f"Insufficient data: only {len(observations)} observations found")
        return
    
    print(f"Loaded {len(observations)} observations")
    
    # Simple clustering
    print("Performing simple clustering analysis...")
    clusters = simple_clustering(observations)
    
    # Analyze temporal patterns
    print("Analyzing temporal patterns...")
    temporal_patterns = analyze_temporal_patterns(observations)
    
    # Identify cognitive attractors
    print("Identifying cognitive attractors...")
    attractors = identify_cognitive_attractors(clusters)
    
    # Analyze cognitive modes
    print("Analyzing cognitive modes...")
    cognitive_modes = analyze_cognitive_modes(attractors, temporal_patterns)
    
    # Compile results
    results = {
        'analysis_metadata': {
            'total_observations': len(observations),
            'analysis_timestamp': observations[-1]['timestamp'] if observations else 0,
            'time_span_hours': temporal_patterns.get('total_span_hours', 0)
        },
        'cognitive_attractors': attractors,
        'cognitive_modes': cognitive_modes,
        'temporal_patterns': temporal_patterns,
        'key_insights': {
            'dominant_mode': max(cognitive_modes.items(), key=lambda x: x[1]['size'])[0] if cognitive_modes else None,
            'entropy_trend': temporal_patterns.get('entropy_trend', 0),
            'session_count': len(temporal_patterns.get('session_statistics', {})),
            'cognitive_flexibility': len([m for m in cognitive_modes.values() if m['percentage'] > 10])
        },
        'distinct_cognitive_modes': {
            'question': "What are the distinct modes of Claude cognition?",
            'answer': {
                'identified_modes': list(cognitive_modes.keys()),
                'mode_descriptions': {
                    mode: {
                        'prevalence': f"{data['percentage']:.1f}%",
                        'key_traits': data['characteristics'],
                        'cognitive_profile': data['cognitive_signature']
                    } for mode, data in cognitive_modes.items()
                },
                'summary': f"Analysis identified {len(cognitive_modes)} distinct cognitive modes across {len(observations)} observations"
            }
        }
    }
    
    # Save results
    output_dir = Path("autonomous_experiments")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "attractors.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nAnalysis complete! Results saved to {output_file}")
    print("\n=== COGNITIVE MODES IDENTIFIED ===")
    
    for mode_name, mode_data in cognitive_modes.items():
        print(f"\n{mode_name.upper()}: {mode_data['percentage']:.1f}% of observations")
        print(f"  Characteristics: {', '.join(mode_data['characteristics'])}")
        print(f"  Avg Entropy: {mode_data['cognitive_signature']['entropy_level']:.2f}")
        print(f"  Avg Response Length: {mode_data['cognitive_signature']['response_length']:.0f} chars")
        print(f"  Processing Time: {mode_data['cognitive_signature']['processing_time']:.1f}s")
    
    print(f"\n=== KEY INSIGHTS ===")
    print(f"Dominant mode: {results['key_insights']['dominant_mode']}")
    print(f"Entropy trend: {results['key_insights']['entropy_trend']:.4f}")
    print(f"Cognitive flexibility: {results['key_insights']['cognitive_flexibility']} major modes")
    print(f"Session diversity: {results['key_insights']['session_count']} sessions")
    
    return results

if __name__ == "__main__":
    main()