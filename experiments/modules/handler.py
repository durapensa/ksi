#!/usr/bin/env python3
"""
Cognitive Observer - Track thought patterns and attractors in Claude responses

Information-theoretic analysis of conversation dynamics.
"""

import json
import time
import hashlib
import math
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
from pathlib import Path
from collections import defaultdict, Counter
import re

# Import config for proper path resolution
try:
    from ksi_common.config import config
    observations_base = config.experiments_cognitive_dir
except ImportError:
    # Fallback for standalone usage
    observations_base = Path("var/experiments/cognitive")

class CognitiveObserver:
    def __init__(self):
        self.observations_dir = observations_base
        self.observations_dir.mkdir(exist_ok=True)
        
        # Track patterns over time
        self.token_patterns = Counter()
        self.concept_graph = defaultdict(lambda: defaultdict(int))
        self.response_times = []
        self.entropy_history = []
        
        print("[CognitiveObserver] Initialized - beginning observation")
    
    def observe_response(self, output, daemon):
        """Main observation function called by daemon"""
        try:
            # Extract key metrics
            timestamp = time.time()
            session_id = output.get('sessionId') or output.get('session_id', 'unknown')
            content = output.get('result', output.get('content', ''))
            cost = output.get('total_cost_usd', 0)
            duration_ms = output.get('duration_ms', 0)
            
            # Information-theoretic analysis
            entropy = self._calculate_entropy(content)
            token_stats = self._analyze_tokens(content)
            concept_edges = self._extract_concept_edges(content)
            
            # Store observation
            observation = {
                'timestamp': timestamp,
                'session_id': session_id,
                'content_length': len(content),
                'cost': cost,
                'duration_ms': duration_ms,
                'entropy': entropy,
                'token_stats': token_stats,
                'concept_edges': concept_edges,
                'content_hash': hashlib.md5(content.encode()).hexdigest()[:8]
            }
            
            # Save to file
            obs_file = self.observations_dir / f"observation_{int(timestamp)}.json"
            with open(obs_file, 'w') as f:
                json.dump(observation, f, indent=2)
            
            # Update running statistics
            self.response_times.append(duration_ms)
            self.entropy_history.append(entropy)
            self.token_patterns.update(token_stats['frequent_tokens'])
            
            # Update concept graph
            for source, target in concept_edges:
                self.concept_graph[source][target] += 1
            
            print(f"[CognitiveObserver] Recorded: entropy={entropy:.3f}, tokens={len(token_stats['unique_tokens'])}, concepts={len(concept_edges)}")
            
            # Detect interesting patterns
            self._detect_attractors()
            
        except Exception as e:
            print(f"[CognitiveObserver] Error: {e}")
    
    def _calculate_entropy(self, text):
        """Calculate Shannon entropy of text"""
        if not text:
            return 0.0
        
        # Count character frequencies
        char_counts = Counter(text.lower())
        total_chars = len(text)
        
        # Calculate entropy
        entropy = 0.0
        for count in char_counts.values():
            probability = count / total_chars
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        return entropy
    
    def _analyze_tokens(self, text):
        """Extract token-level statistics"""
        # Simple tokenization (could be enhanced)
        tokens = re.findall(r'\b\w+\b', text.lower())
        
        return {
            'token_count': len(tokens),
            'unique_tokens': len(set(tokens)),
            'frequent_tokens': [word for word, count in Counter(tokens).most_common(10)],
            'avg_token_length': sum(len(token) for token in tokens) / max(len(tokens), 1)
        }
    
    def _extract_concept_edges(self, text):
        """Extract conceptual relationships (simple pattern matching)"""
        edges = []
        
        # Look for common relationship patterns
        patterns = [
            r'(\w+)\s+(?:is|are|was|were)\s+(\w+)',
            r'(\w+)\s+(?:uses|contains|includes)\s+(\w+)',
            r'(\w+)\s+(?:leads to|causes|results in)\s+(\w+)',
            r'(\w+)\s+and\s+(\w+)',  # Co-occurrence
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text.lower(), re.IGNORECASE)
            edges.extend(matches)
        
        return edges[:20]  # Limit to prevent explosion
    
    def _detect_attractors(self):
        """Detect recurring patterns that might indicate cognitive attractors"""
        if len(self.entropy_history) < 5:
            return
        
        # Simple attractor detection: look for entropy patterns
        recent_entropy = self.entropy_history[-5:]
        avg_entropy = sum(recent_entropy) / len(recent_entropy)
        
        # Low entropy might indicate attractor behavior
        if avg_entropy < 3.0:  # Threshold to tune
            print(f"[CognitiveObserver] Potential attractor detected - low entropy: {avg_entropy:.3f}")
        
        # Look for repeated token patterns
        recent_tokens = list(self.token_patterns.most_common(5))
        if recent_tokens:
            print(f"[CognitiveObserver] Top patterns: {recent_tokens}")
    
    def calculate_graph_centrality(self):
        """Calculate centrality metrics for concept graph"""
        if not self.concept_graph:
            return {}
        
        # Build adjacency data
        nodes = set()
        edges = []
        for source, targets in self.concept_graph.items():
            nodes.add(source)
            for target, weight in targets.items():
                nodes.add(target)
                edges.append((source, target, weight))
        
        if len(nodes) < 2:
            return {}
        
        # Calculate degree centrality (simple version)
        node_degrees = defaultdict(int)
        for source, target, weight in edges:
            node_degrees[source] += weight
            node_degrees[target] += weight
        
        total_possible = len(nodes) - 1
        centrality = {node: degree / total_possible for node, degree in node_degrees.items()}
        
        # Find most central concepts
        top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'top_central_concepts': top_central,
            'avg_centrality': sum(centrality.values()) / len(centrality)
        }
    
    def calculate_mutual_information(self):
        """Calculate mutual information between prompt characteristics and response entropy"""
        if len(self.entropy_history) < 10:
            return None
        
        # Read recent observations to get prompt/response pairs
        try:
            observations = []
            for obs_file in sorted(self.observations_dir.glob("*.json"))[-10:]:
                with open(obs_file, 'r') as f:
                    obs = json.load(f)
                    observations.append(obs)
            
            if len(observations) < 5:
                return None
            
            # Simple mutual information: entropy vs content length
            entropies = [obs['entropy'] for obs in observations]
            lengths = [obs['content_length'] for obs in observations]
            
            # Discretize for MI calculation (simple binning)
            entropy_bins = [0 if e < 2.0 else 1 if e < 4.0 else 2 for e in entropies]
            length_bins = [0 if l < 10 else 1 if l < 100 else 2 for l in lengths]
            
            # Calculate joint probabilities
            joint_counts = defaultdict(int)
            for e_bin, l_bin in zip(entropy_bins, length_bins):
                joint_counts[(e_bin, l_bin)] += 1
            
            total = len(observations)
            joint_probs = {k: v/total for k, v in joint_counts.items()}
            
            # Marginal probabilities
            entropy_probs = defaultdict(int)
            length_probs = defaultdict(int)
            for e_bin in entropy_bins:
                entropy_probs[e_bin] += 1
            for l_bin in length_bins:
                length_probs[l_bin] += 1
            
            entropy_probs = {k: v/total for k, v in entropy_probs.items()}
            length_probs = {k: v/total for k, v in length_probs.items()}
            
            # Mutual information calculation
            mi = 0.0
            for (e_bin, l_bin), joint_prob in joint_probs.items():
                if joint_prob > 0:
                    mi += joint_prob * math.log2(joint_prob / (entropy_probs[e_bin] * length_probs[l_bin]))
            
            return {
                'mutual_information': mi,
                'entropy_length_correlation': 'high' if mi > 0.5 else 'medium' if mi > 0.1 else 'low'
            }
            
        except Exception as e:
            print(f"[CognitiveObserver] Error calculating MI: {e}")
            return None
    
    def detect_phase_space_attractors(self):
        """Detect attractors in cognitive phase space (entropy vs response time)"""
        if len(self.entropy_history) < 10:
            return {}
        
        # Create phase space points (entropy, response_time, cost)
        try:
            observations = []
            for obs_file in sorted(self.observations_dir.glob("*.json"))[-20:]:
                with open(obs_file, 'r') as f:
                    obs = json.load(f)
                    observations.append((obs['entropy'], obs['duration_ms']/1000.0, obs['cost']))
            
            if len(observations) < 5:
                return {}
            
            # Simple clustering: find points that are close together
            clusters = []
            threshold = 1.0  # Distance threshold for clustering
            
            for i, point1 in enumerate(observations):
                cluster = [point1]
                for j, point2 in enumerate(observations):
                    if i != j:
                        # Euclidean distance (normalized)
                        dist = math.sqrt(
                            ((point1[0] - point2[0]) / 5.0) ** 2 +  # entropy scale
                            ((point1[1] - point2[1]) / 10.0) ** 2 +  # time scale 
                            ((point1[2] - point2[2]) / 0.1) ** 2    # cost scale
                        )
                        if dist < threshold:
                            cluster.append(point2)
                
                if len(cluster) >= 3:  # Potential attractor
                    clusters.append(cluster)
            
            # Deduplicate and analyze clusters
            unique_clusters = []
            for cluster in clusters:
                is_unique = True
                for existing in unique_clusters:
                    if len(set(cluster) & set(existing)) > len(cluster) * 0.7:
                        is_unique = False
                        break
                if is_unique:
                    unique_clusters.append(cluster)
            
            # Characterize attractors
            attractors = []
            for i, cluster in enumerate(unique_clusters[:3]):  # Top 3
                avg_entropy = sum(p[0] for p in cluster) / len(cluster)
                avg_time = sum(p[1] for p in cluster) / len(cluster)
                avg_cost = sum(p[2] for p in cluster) / len(cluster)
                
                attractors.append({
                    'id': f'attractor_{i+1}',
                    'size': len(cluster),
                    'avg_entropy': avg_entropy,
                    'avg_response_time': avg_time,
                    'avg_cost': avg_cost,
                    'type': 'low_entropy' if avg_entropy < 2.0 else 'high_entropy' if avg_entropy > 4.0 else 'medium_entropy'
                })
            
            return {
                'total_attractors': len(attractors),
                'attractors': attractors,
                'phase_space_size': len(observations)
            }
            
        except Exception as e:
            print(f"[CognitiveObserver] Error in phase space analysis: {e}")
            return {}
    
    def generate_enhanced_summary(self):
        """Generate comprehensive cognitive analysis report"""
        base_summary = self.get_summary()
        if base_summary == "No observations yet":
            return base_summary
        
        # Add advanced analyses
        centrality = self.calculate_graph_centrality()
        mutual_info = self.calculate_mutual_information()
        attractors = self.detect_phase_space_attractors()
        
        return {
            **base_summary,
            'graph_centrality': centrality,
            'mutual_information': mutual_info,
            'phase_space_attractors': attractors,
            'cognitive_modes_detected': len(attractors.get('attractors', [])),
            'analysis_timestamp': time.time()
        }
    
    def get_summary(self):
        """Return summary of observations"""
        if not self.entropy_history:
            return "No observations yet"
        
        return {
            'total_observations': len(self.entropy_history),
            'avg_entropy': sum(self.entropy_history) / len(self.entropy_history),
            'avg_response_time': sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            'top_tokens': list(self.token_patterns.most_common(10)),
            'concept_graph_size': len(self.concept_graph)
        }

# Global observer instance
observer = CognitiveObserver()

# Handler function that daemon expects
def handle_output(output, daemon):
    """Entry point called by daemon"""
    observer.observe_response(output, daemon)