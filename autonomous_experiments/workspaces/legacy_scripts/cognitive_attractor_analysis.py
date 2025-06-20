#!/usr/bin/env python3

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')

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

def extract_features(observations):
    """Extract features for clustering analysis."""
    features = []
    metadata = []
    
    for obs in observations:
        # Core cognitive features
        feature_vector = [
            obs.get('entropy', 0),
            obs.get('content_length', 0),
            obs.get('cost', 0),
            obs.get('duration_ms', 0) / 1000,  # Convert to seconds
            obs.get('token_stats', {}).get('token_count', 0),
            obs.get('token_stats', {}).get('unique_tokens', 0),
            obs.get('token_stats', {}).get('avg_token_length', 0),
            len(obs.get('concept_edges', [])),
            len(obs.get('token_stats', {}).get('frequent_tokens', [])),
        ]
        
        # Token diversity ratio
        token_count = obs.get('token_stats', {}).get('token_count', 1)
        unique_tokens = obs.get('token_stats', {}).get('unique_tokens', 0)
        diversity_ratio = unique_tokens / max(token_count, 1)
        feature_vector.append(diversity_ratio)
        
        # Response complexity metrics
        content_length = obs.get('content_length', 0)
        complexity_ratio = content_length / max(token_count, 1)
        feature_vector.append(complexity_ratio)
        
        features.append(feature_vector)
        metadata.append({
            'timestamp': obs['timestamp'],
            'session_id': obs.get('session_id', 'unknown'),
            'content_hash': obs.get('content_hash', ''),
            'entropy': obs.get('entropy', 0),
            'content_length': obs.get('content_length', 0)
        })
    
    return np.array(features), metadata

def find_optimal_clusters(X, max_k=10):
    """Find optimal number of clusters using elbow method and silhouette score."""
    inertias = []
    silhouette_scores = []
    K = range(2, min(max_k + 1, len(X)))
    
    for k in K:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X)
        inertias.append(kmeans.inertia_)
        score = silhouette_score(X, kmeans.labels_)
        silhouette_scores.append(score)
    
    # Find elbow point
    if len(silhouette_scores) > 0:
        best_k = K[np.argmax(silhouette_scores)]
        return best_k, dict(zip(K, silhouette_scores))
    else:
        return 3, {}

def analyze_temporal_patterns(observations, metadata):
    """Analyze temporal patterns in cognitive data."""
    # Convert to DataFrame for easier analysis
    df_data = []
    for obs, meta in zip(observations, metadata):
        df_data.append({
            'timestamp': meta['timestamp'],
            'session_id': meta['session_id'],
            'entropy': meta['entropy'],
            'content_length': meta['content_length'],
            'token_count': obs[4],  # From feature vector
            'unique_tokens': obs[5],
            'diversity_ratio': obs[9],
            'duration_sec': obs[3]
        })
    
    df = pd.DataFrame(df_data)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Temporal analysis
    temporal_patterns = {
        'total_span_hours': (df['timestamp'].max() - df['timestamp'].min()) / 3600,
        'observations_per_session': df['session_id'].value_counts().to_dict(),
        'entropy_over_time': {
            'correlation_with_time': df['entropy'].corr(df['timestamp']),
            'moving_average_window_10': df['entropy'].rolling(window=10, min_periods=1).mean().tolist(),
        },
        'session_patterns': {}
    }
    
    # Analyze patterns by session
    for session_id in df['session_id'].unique():
        session_df = df[df['session_id'] == session_id]
        if len(session_df) > 1:
            temporal_patterns['session_patterns'][session_id] = {
                'entropy_trend': session_df['entropy'].corr(session_df['timestamp']),
                'avg_entropy': session_df['entropy'].mean(),
                'entropy_variance': session_df['entropy'].var(),
                'duration_pattern': session_df['duration_sec'].describe().to_dict()
            }
    
    return temporal_patterns, df

def identify_cognitive_attractors(X, metadata, optimal_k):
    """Identify cognitive attractors using clustering."""
    # Apply K-means clustering
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X)
    
    # Also try DBSCAN for density-based clustering
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    dbscan = DBSCAN(eps=0.5, min_samples=5)
    dbscan_labels = dbscan.fit_predict(X_scaled)
    
    # Analyze K-means clusters
    attractors = {}
    feature_names = [
        'entropy', 'content_length', 'cost', 'duration_sec', 
        'token_count', 'unique_tokens', 'avg_token_length',
        'concept_edges', 'frequent_tokens_count', 'diversity_ratio',
        'complexity_ratio'
    ]
    
    for cluster_id in range(optimal_k):
        cluster_mask = cluster_labels == cluster_id
        cluster_observations = X[cluster_mask]
        cluster_metadata = [m for i, m in enumerate(metadata) if cluster_mask[i]]
        
        if len(cluster_observations) == 0:
            continue
            
        # Calculate cluster characteristics
        centroid = cluster_observations.mean(axis=0)
        std = cluster_observations.std(axis=0)
        
        # Identify sessions in this cluster
        sessions = [m['session_id'] for m in cluster_metadata]
        session_distribution = Counter(sessions)
        
        # Entropy characteristics
        entropies = [m['entropy'] for m in cluster_metadata]
        
        attractors[f"attractor_{cluster_id}"] = {
            'cluster_id': cluster_id,
            'size': len(cluster_observations),
            'percentage': len(cluster_observations) / len(X) * 100,
            'centroid': {feature_names[i]: float(centroid[i]) for i in range(len(feature_names))},
            'std_deviation': {feature_names[i]: float(std[i]) for i in range(len(feature_names))},
            'entropy_stats': {
                'mean': np.mean(entropies),
                'std': np.std(entropies),
                'min': np.min(entropies),
                'max': np.max(entropies)
            },
            'session_distribution': dict(session_distribution),
            'temporal_span': {
                'first_timestamp': min(m['timestamp'] for m in cluster_metadata),
                'last_timestamp': max(m['timestamp'] for m in cluster_metadata),
                'span_hours': (max(m['timestamp'] for m in cluster_metadata) - 
                              min(m['timestamp'] for m in cluster_metadata)) / 3600
            },
            'sample_observations': [
                {
                    'timestamp': m['timestamp'],
                    'session_id': m['session_id'],
                    'entropy': m['entropy'],
                    'content_hash': m['content_hash']
                } for m in cluster_metadata[:3]  # First 3 as samples
            ]
        }
    
    # DBSCAN analysis
    dbscan_analysis = {
        'n_clusters': len(set(dbscan_labels)) - (1 if -1 in dbscan_labels else 0),
        'n_noise': list(dbscan_labels).count(-1),
        'noise_percentage': list(dbscan_labels).count(-1) / len(dbscan_labels) * 100
    }
    
    return attractors, dbscan_analysis, cluster_labels

def analyze_cognitive_modes(attractors, temporal_patterns, observations_df):
    """Identify distinct cognitive modes from attractors."""
    modes = {}
    
    # Sort attractors by size to identify major modes
    sorted_attractors = sorted(attractors.items(), 
                             key=lambda x: x[1]['size'], reverse=True)
    
    mode_names = [
        "Focused_Analytical", "Exploratory_Creative", "Responsive_Brief",
        "Technical_Deep", "Conversational_Flow"
    ]
    
    for i, (attractor_id, attractor_data) in enumerate(sorted_attractors):
        mode_name = mode_names[i] if i < len(mode_names) else f"Mode_{i+1}"
        
        # Characterize the mode
        centroid = attractor_data['centroid']
        
        # Determine mode characteristics based on feature values
        characteristics = []
        
        if centroid['entropy'] > 4.0:
            characteristics.append("high_entropy")
        elif centroid['entropy'] < 2.0:
            characteristics.append("low_entropy")
        else:
            characteristics.append("medium_entropy")
            
        if centroid['content_length'] > 1000:
            characteristics.append("verbose")
        elif centroid['content_length'] < 100:
            characteristics.append("concise")
            
        if centroid['diversity_ratio'] > 0.8:
            characteristics.append("diverse_vocabulary")
        elif centroid['diversity_ratio'] < 0.5:
            characteristics.append("repetitive_patterns")
            
        if centroid['duration_sec'] > 30:
            characteristics.append("deliberative")
        elif centroid['duration_sec'] < 5:
            characteristics.append("rapid_response")
            
        modes[mode_name] = {
            'attractor_id': attractor_id,
            'size': attractor_data['size'],
            'percentage': attractor_data['percentage'],
            'characteristics': characteristics,
            'cognitive_signature': {
                'entropy_level': centroid['entropy'],
                'response_length': centroid['content_length'],
                'vocabulary_diversity': centroid['diversity_ratio'],
                'processing_time': centroid['duration_sec'],
                'conceptual_complexity': centroid['concept_edges'],
                'token_efficiency': centroid['token_count'] / max(centroid['content_length'], 1)
            },
            'temporal_behavior': attractor_data['temporal_span'],
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
    
    # Extract features
    print("Extracting features for clustering...")
    X, metadata = extract_features(observations)
    
    # Find optimal clusters
    print("Finding optimal number of clusters...")
    optimal_k, silhouette_scores = find_optimal_clusters(X)
    print(f"Optimal number of clusters: {optimal_k}")
    
    # Analyze temporal patterns
    print("Analyzing temporal patterns...")
    temporal_patterns, df = analyze_temporal_patterns(X, metadata)
    
    # Identify cognitive attractors
    print("Identifying cognitive attractors...")
    attractors, dbscan_analysis, cluster_labels = identify_cognitive_attractors(X, metadata, optimal_k)
    
    # Analyze cognitive modes
    print("Analyzing cognitive modes...")
    cognitive_modes = analyze_cognitive_modes(attractors, temporal_patterns, df)
    
    # Compile final results
    results = {
        'analysis_metadata': {
            'total_observations': len(observations),
            'feature_dimensions': X.shape[1] if len(X) > 0 else 0,
            'optimal_clusters': optimal_k,
            'silhouette_scores': silhouette_scores,
            'analysis_timestamp': observations[-1]['timestamp'] if observations else 0
        },
        'cognitive_attractors': attractors,
        'cognitive_modes': cognitive_modes,
        'temporal_patterns': temporal_patterns,
        'clustering_analysis': {
            'kmeans_clusters': optimal_k,
            'dbscan_analysis': dbscan_analysis
        },
        'key_insights': {
            'dominant_mode': max(cognitive_modes.items(), key=lambda x: x[1]['size'])[0] if cognitive_modes else None,
            'entropy_trend': temporal_patterns.get('entropy_over_time', {}).get('correlation_with_time', 0),
            'session_diversity': len(set(m['session_id'] for m in metadata)),
            'cognitive_flexibility': len([m for m in cognitive_modes.values() if m['percentage'] > 10])
        }
    }
    
    # Save results
    output_dir = Path("autonomous_experiments")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "attractors.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nAnalysis complete! Results saved to {output_file}")
    print("\n=== KEY FINDINGS ===")
    print(f"Identified {len(cognitive_modes)} distinct cognitive modes:")
    for mode_name, mode_data in cognitive_modes.items():
        print(f"  • {mode_name}: {mode_data['percentage']:.1f}% of observations")
        print(f"    Characteristics: {', '.join(mode_data['characteristics'])}")
    
    print(f"\nDominant cognitive mode: {results['key_insights']['dominant_mode']}")
    print(f"Entropy trend over time: {results['key_insights']['entropy_trend']:.3f}")
    print(f"Cognitive flexibility score: {results['key_insights']['cognitive_flexibility']}")
    
    return results

if __name__ == "__main__":
    main()