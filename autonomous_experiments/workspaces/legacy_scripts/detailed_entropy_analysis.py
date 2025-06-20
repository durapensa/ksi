#!/usr/bin/env python3

import json
import os
import statistics
from collections import defaultdict, Counter
from pathlib import Path
import re

def detailed_entropy_analysis():
    """Detailed analysis of entropy patterns and triggers"""
    
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
        return {}
    
    # Sort by entropy for analysis
    sorted_by_entropy = sorted(observations, key=lambda x: x['entropy'])
    
    # Define entropy categories
    low_entropy = [obs for obs in observations if obs['entropy'] < 2.0]
    medium_entropy = [obs for obs in observations if 2.0 <= obs['entropy'] < 4.5]
    high_entropy = [obs for obs in observations if obs['entropy'] >= 4.5]
    
    # Analyze patterns by category
    def analyze_category(category, name):
        if not category:
            return {"count": 0}
        
        return {
            "count": len(category),
            "avg_entropy": statistics.mean([obs['entropy'] for obs in category]),
            "avg_content_length": statistics.mean([obs['content_length'] for obs in category]),
            "avg_token_count": statistics.mean([obs['token_stats']['token_count'] for obs in category]),
            "avg_unique_tokens": statistics.mean([obs['token_stats']['unique_tokens'] for obs in category]),
            "avg_duration": statistics.mean([obs['duration_ms'] for obs in category]),
            "avg_cost": statistics.mean([obs['cost'] for obs in category]),
            "token_diversity": statistics.mean([
                obs['token_stats']['unique_tokens'] / max(obs['token_stats']['token_count'], 1) 
                for obs in category
            ]),
            "common_tokens": get_common_tokens(category),
            "session_distribution": get_session_distribution(category),
            "examples": category[:3]  # First 3 examples
        }
    
    low_analysis = analyze_category(low_entropy, "Low")
    medium_analysis = analyze_category(medium_entropy, "Medium") 
    high_analysis = analyze_category(high_entropy, "High")
    
    # Identify triggers
    triggers = identify_triggers(observations)
    
    # Time-based analysis
    time_analysis = analyze_time_patterns(observations)
    
    return {
        "overview": {
            "total_observations": len(observations),
            "entropy_range": {
                "min": min(obs['entropy'] for obs in observations),
                "max": max(obs['entropy'] for obs in observations),
                "mean": statistics.mean([obs['entropy'] for obs in observations])
            }
        },
        "categories": {
            "low_entropy": low_analysis,
            "medium_entropy": medium_analysis,
            "high_entropy": high_analysis
        },
        "triggers": triggers,
        "time_analysis": time_analysis
    }

def get_common_tokens(observations):
    """Get most common tokens across observations"""
    all_tokens = []
    for obs in observations:
        all_tokens.extend(obs['token_stats']['frequent_tokens'])
    
    return Counter(all_tokens).most_common(10)

def get_session_distribution(observations):
    """Get session distribution"""
    sessions = Counter(obs['session_id'] for obs in observations)
    return dict(sessions.most_common(5))

def identify_triggers(observations):
    """Identify what triggers high vs low entropy"""
    
    # Sort by entropy
    sorted_obs = sorted(observations, key=lambda x: x['entropy'])
    
    low_entropy = sorted_obs[:20]  # Bottom 20
    high_entropy = sorted_obs[-20:]  # Top 20
    
    triggers = {
        "low_entropy_triggers": {
            "content_characteristics": analyze_content_characteristics(low_entropy),
            "response_types": identify_response_types(low_entropy),
            "session_patterns": analyze_session_patterns(low_entropy)
        },
        "high_entropy_triggers": {
            "content_characteristics": analyze_content_characteristics(high_entropy),
            "response_types": identify_response_types(high_entropy),
            "session_patterns": analyze_session_patterns(high_entropy)
        }
    }
    
    return triggers

def analyze_content_characteristics(observations):
    """Analyze content characteristics"""
    characteristics = {
        "avg_content_length": statistics.mean([obs['content_length'] for obs in observations]),
        "length_distribution": {},
        "token_patterns": {},
        "concept_edge_patterns": {}
    }
    
    # Length distribution
    lengths = [obs['content_length'] for obs in observations]
    characteristics["length_distribution"] = {
        "very_short": len([l for l in lengths if l < 10]),
        "short": len([l for l in lengths if 10 <= l < 100]), 
        "medium": len([l for l in lengths if 100 <= l < 500]),
        "long": len([l for l in lengths if l >= 500])
    }
    
    # Token patterns
    avg_token_length = statistics.mean([obs['token_stats']['avg_token_length'] for obs in observations])
    token_diversity = statistics.mean([
        obs['token_stats']['unique_tokens'] / max(obs['token_stats']['token_count'], 1) 
        for obs in observations
    ])
    
    characteristics["token_patterns"] = {
        "avg_token_length": avg_token_length,
        "token_diversity": token_diversity
    }
    
    # Concept edges
    total_edges = sum(len(obs['concept_edges']) for obs in observations)
    characteristics["concept_edge_patterns"] = {
        "total_edges": total_edges,
        "avg_edges_per_observation": total_edges / len(observations)
    }
    
    return characteristics

def identify_response_types(observations):
    """Identify types of responses"""
    types = {
        "single_word": 0,
        "empty": 0,
        "short_confirmation": 0,
        "technical_discussion": 0,
        "error_handling": 0
    }
    
    for obs in observations:
        length = obs['content_length']
        tokens = obs['token_stats']['frequent_tokens']
        
        if length == 0:
            types["empty"] += 1
        elif length <= 10:
            types["single_word"] += 1
        elif length <= 100 and any(word in tokens for word in ['ready', 'done', 'yes', 'no', 'ok']):
            types["short_confirmation"] += 1
        elif any(word in tokens for word in ['autonomous', 'claude', 'system', 'spawn']):
            types["technical_discussion"] += 1
        elif any(word in tokens for word in ['error', 'problem', 'issue', 'broken']):
            types["error_handling"] += 1
    
    return types

def analyze_session_patterns(observations):
    """Analyze session-level patterns"""
    session_counts = Counter(obs['session_id'] for obs in observations)
    session_data = {}
    
    for session_id, count in session_counts.most_common(5):
        session_obs = [obs for obs in observations if obs['session_id'] == session_id]
        session_data[session_id] = {
            "observation_count": count,
            "avg_entropy": statistics.mean([obs['entropy'] for obs in session_obs]),
            "entropy_range": {
                "min": min(obs['entropy'] for obs in session_obs),
                "max": max(obs['entropy'] for obs in session_obs)
            }
        }
    
    return session_data

def analyze_time_patterns(observations):
    """Analyze temporal patterns"""
    # Sort chronologically 
    time_sorted = sorted(observations, key=lambda x: x['timestamp'])
    
    # Calculate moving averages
    window_size = 10
    moving_averages = []
    for i in range(len(time_sorted) - window_size + 1):
        window = time_sorted[i:i + window_size]
        avg_entropy = statistics.mean([obs['entropy'] for obs in window])
        moving_averages.append({
            "timestamp": window[-1]['timestamp'],
            "avg_entropy": avg_entropy
        })
    
    # Identify trends
    entropies = [obs['entropy'] for obs in time_sorted]
    
    return {
        "total_time_span": time_sorted[-1]['timestamp'] - time_sorted[0]['timestamp'],
        "entropy_trend": {
            "first_10_avg": statistics.mean(entropies[:10]) if len(entropies) >= 10 else None,
            "last_10_avg": statistics.mean(entropies[-10:]) if len(entropies) >= 10 else None
        },
        "moving_averages": moving_averages[-5:]  # Last 5 windows
    }

if __name__ == "__main__":
    results = detailed_entropy_analysis()
    
    # Save results
    with open('detailed_entropy_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("Detailed entropy analysis complete!")
    print(f"Total observations: {results['overview']['total_observations']}")
    print(f"Low entropy observations: {results['categories']['low_entropy']['count']}")
    print(f"High entropy observations: {results['categories']['high_entropy']['count']}")