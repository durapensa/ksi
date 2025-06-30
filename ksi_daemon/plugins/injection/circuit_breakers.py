#!/usr/bin/env python3
"""
Circuit Breaker System

Prevents runaway completion chains and context poisoning through multiple
safety mechanisms including depth tracking, pattern detection, and resource limits.
"""

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set, Tuple
import hashlib
import json

from ksi_common.logging import get_logger
from ksi_common import TimestampManager

logger = get_logger("circuit_breakers")


def estimate_tokens(content: str) -> int:
    """
    Estimate token count for text content.
    
    Uses multiple heuristics for better accuracy:
    - Character count / 4 (common GPT-style tokenization ratio)
    - Word count * 1.3 (accounting for subword tokenization)
    - Takes the average and ensures minimum of 1
    
    Args:
        content: Text content to estimate
        
    Returns:
        Estimated token count (minimum 1)
    """
    if not content or not content.strip():
        return 1
    
    # Multiple estimation methods
    char_estimate = len(content) / 4.0  # ~4 chars per token average
    word_estimate = len(content.split()) * 1.3  # Words + subword tokenization
    
    # Take average of methods, with reasonable bounds
    avg_estimate = (char_estimate + word_estimate) / 2.0
    
    # Ensure minimum of 1 token and return as integer
    return max(1, int(avg_estimate))


@dataclass
class CompletionRecord:
    """Record of a completion in the chain."""
    request_id: str
    parent_request_id: Optional[str]
    timestamp: float
    content_hash: str
    content_length: int
    depth: int
    tokens_estimated: int


class RequestTracker:
    """Tracks completion request chains and relationships."""
    
    def __init__(self):
        self.requests: Dict[str, CompletionRecord] = {}
        self.chain_cache: Dict[str, List[CompletionRecord]] = {}
    
    def add_request(self, request_id: str, parent_id: Optional[str], 
                   content: str, tokens: Optional[int] = None):
        """Add a new request to tracking."""
        
        # Calculate depth
        depth = 0
        if parent_id and parent_id in self.requests:
            depth = self.requests[parent_id].depth + 1
        
        # Estimate tokens if not provided
        if tokens is None:
            tokens = estimate_tokens(content)
        
        # Create record
        record = CompletionRecord(
            request_id=request_id,
            parent_request_id=parent_id,
            timestamp=time.time(),
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            content_length=len(content),
            depth=depth,
            tokens_estimated=int(tokens)
        )
        
        self.requests[request_id] = record
        
        # Invalidate chain cache for parent
        if parent_id:
            self.chain_cache.pop(parent_id, None)
    
    def get_completion_chain(self, request_id: str) -> List[CompletionRecord]:
        """Get the full completion chain for a request."""
        
        # Check cache
        if request_id in self.chain_cache:
            return self.chain_cache[request_id]
        
        chain = []
        current_id = request_id
        seen = set()
        
        while current_id and current_id not in seen:
            if current_id in self.requests:
                record = self.requests[current_id]
                chain.append(record)
                seen.add(current_id)
                current_id = record.parent_request_id
            else:
                break
        
        # Cache the result
        self.chain_cache[request_id] = chain
        
        return chain
    
    def get_request(self, request_id: str) -> Optional[CompletionRecord]:
        """Get a specific request record."""
        return self.requests.get(request_id)


class ContextPoisoningDetector:
    """Detects patterns indicating context poisoning or degradation."""
    
    def __init__(self):
        self.patterns = {
            'recursive_self_reference': self.detect_recursive_references,
            'hallucination_cascade': self.detect_hallucination_patterns,
            'topic_drift': self.detect_excessive_drift,
            'coherence_degradation': self.detect_coherence_loss,
            'infinite_elaboration': self.detect_elaboration_loops,
            'circular_reasoning': self.detect_circular_reasoning
        }
        
        # Pattern detection regexes
        self.recursive_patterns = [
            r'(as I mentioned earlier|as stated above|as previously noted){3,}',
            r'(therefore|thus|hence|consequently){5,}',
            r'(to reiterate|to repeat|again){4,}'
        ]
        
        self.hallucination_indicators = [
            r'(I believe|I think|it seems|apparently){6,}',
            r'(possibly|probably|maybe|perhaps){8,}',
            r'(could be|might be|may be){6,}'
        ]
    
    def analyze_chain(self, completion_chain: List[CompletionRecord]) -> Dict[str, Any]:
        """Analyze completion chain for poisoning indicators."""
        
        if not completion_chain or len(completion_chain) < 2:
            return {'risk_score': 0, 'indicators': []}
        
        risk_score = 0
        indicators = []
        
        for pattern_name, detector in self.patterns.items():
            result = detector(completion_chain)
            if result:
                risk_score += result['weight']
                indicators.append({
                    'pattern': pattern_name,
                    'confidence': result['confidence'],
                    'details': result['details']
                })
        
        return {
            'risk_score': min(risk_score, 1.0),
            'indicators': indicators,
            'chain_length': len(completion_chain)
        }
    
    def detect_recursive_references(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect excessive self-referential patterns."""
        
        if len(chain) < 3:
            return None
        
        # Check for repeated content hashes (exact duplicates)
        hash_counts = defaultdict(int)
        for record in chain:
            hash_counts[record.content_hash] += 1
        
        max_repeats = max(hash_counts.values())
        if max_repeats >= 3:
            return {
                'weight': 0.4,
                'confidence': 0.9,
                'details': f"Content repeated {max_repeats} times"
            }
        
        # Check for recursive language patterns
        # (Would need actual content to check patterns - using length as proxy)
        length_variance = self._calculate_variance([r.content_length for r in chain])
        if length_variance < 0.1:  # Very similar lengths
            return {
                'weight': 0.2,
                'confidence': 0.5,
                'details': "Suspiciously uniform content lengths"
            }
        
        return None
    
    def detect_hallucination_patterns(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect cascading hallucination patterns."""
        
        if len(chain) < 4:
            return None
        
        # Check for exponential growth in content length
        lengths = [r.content_length for r in chain]
        growth_rates = []
        
        for i in range(1, len(lengths)):
            if lengths[i-1] > 0:
                growth_rate = lengths[i] / lengths[i-1]
                growth_rates.append(growth_rate)
        
        avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 1
        
        if avg_growth > 1.5:  # 50% average growth per step
            return {
                'weight': 0.3,
                'confidence': 0.7,
                'details': f"Exponential content growth: {avg_growth:.2f}x average"
            }
        
        return None
    
    def detect_excessive_drift(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect topic drift through the chain."""
        
        if len(chain) < 5:
            return None
        
        # Use content hash similarity as proxy for topic consistency
        # In real implementation, would use embeddings or semantic analysis
        hash_similarity = self._calculate_hash_similarity(chain)
        
        if hash_similarity < 0.3:  # Low similarity between start and end
            return {
                'weight': 0.25,
                'confidence': 0.6,
                'details': f"Low content similarity: {hash_similarity:.2f}"
            }
        
        return None
    
    def detect_coherence_loss(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect degradation in coherence."""
        
        if len(chain) < 3:
            return None
        
        # Check for very short or very long responses (coherence breakdown)
        lengths = [r.content_length for r in chain]
        
        very_short = sum(1 for l in lengths if l < 100)
        very_long = sum(1 for l in lengths if l > 10000)
        
        if very_short >= len(lengths) // 2:
            return {
                'weight': 0.3,
                'confidence': 0.8,
                'details': "Many very short responses indicating breakdown"
            }
        
        if very_long >= len(lengths) // 3:
            return {
                'weight': 0.25,
                'confidence': 0.7,
                'details': "Excessively long responses indicating rambling"
            }
        
        return None
    
    def detect_elaboration_loops(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect infinite elaboration patterns."""
        
        if len(chain) < 4:
            return None
        
        # Check for consistent growth without convergence
        lengths = [r.content_length for r in chain[-5:]]  # Last 5 entries
        
        if all(lengths[i] > lengths[i-1] for i in range(1, len(lengths))):
            total_growth = lengths[-1] / lengths[0] if lengths[0] > 0 else float('inf')
            
            if total_growth > 3:  # Tripled in size
                return {
                    'weight': 0.35,
                    'confidence': 0.8,
                    'details': f"Continuous elaboration: {total_growth:.1f}x growth"
                }
        
        return None
    
    def detect_circular_reasoning(self, chain: List[CompletionRecord]) -> Optional[Dict[str, Any]]:
        """Detect circular reasoning patterns."""
        
        if len(chain) < 6:
            return None
        
        # Check for cyclic patterns in content hashes
        # A -> B -> C -> A pattern
        hash_sequence = [r.content_hash[:8] for r in chain]
        
        for cycle_len in range(2, min(6, len(chain) // 2)):
            if self._has_cycle(hash_sequence, cycle_len):
                return {
                    'weight': 0.4,
                    'confidence': 0.85,
                    'details': f"Circular pattern detected with cycle length {cycle_len}"
                }
        
        return None
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance / (mean ** 2) if mean > 0 else 0  # Normalized variance
    
    def _calculate_hash_similarity(self, chain: List[CompletionRecord]) -> float:
        """Calculate similarity between first and last content hashes."""
        if len(chain) < 2:
            return 1.0
        
        # Simple character overlap as proxy
        hash1 = chain[0].content_hash
        hash2 = chain[-1].content_hash
        
        common = sum(1 for a, b in zip(hash1, hash2) if a == b)
        return common / len(hash1)
    
    def _has_cycle(self, sequence: List[str], cycle_len: int) -> bool:
        """Check if sequence has a repeating cycle of given length."""
        if len(sequence) < cycle_len * 2:
            return False
        
        for i in range(len(sequence) - cycle_len * 2 + 1):
            pattern = sequence[i:i + cycle_len]
            if sequence[i + cycle_len:i + cycle_len * 2] == pattern:
                return True
        
        return False


class TokenBudgetTracker:
    """Tracks token usage across completion chains."""
    
    def __init__(self):
        self.chain_tokens: Dict[str, int] = defaultdict(int)
        self.time_windows: Dict[str, deque] = defaultdict(deque)
    
    def add_tokens(self, request_id: str, parent_id: Optional[str], tokens: int):
        """Add token usage for a request."""
        
        # Add to current request
        self.chain_tokens[request_id] = tokens
        
        # Add to parent chain total
        if parent_id:
            self.chain_tokens[request_id] += self.chain_tokens.get(parent_id, 0)
        
        # Track time window usage
        timestamp = time.time()
        self.time_windows[request_id].append((timestamp, tokens))
    
    def check_budget(self, request_id: str, parent_id: Optional[str], 
                    budget: int, time_window: int) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within token budget."""
        
        # Check chain total
        chain_total = self.chain_tokens.get(parent_id, 0) if parent_id else 0
        
        if chain_total >= budget:
            return False, {
                'reason': 'chain_budget_exceeded',
                'chain_total': chain_total,
                'budget': budget
            }
        
        # Check time window usage
        if parent_id:
            window_usage = self._calculate_window_usage(parent_id, time_window)
            if window_usage >= budget:
                return False, {
                    'reason': 'time_window_budget_exceeded',
                    'window_usage': window_usage,
                    'budget': budget,
                    'time_window': time_window
                }
        
        return True, {'chain_total': chain_total, 'budget': budget}
    
    def _calculate_window_usage(self, request_id: str, window_seconds: int) -> int:
        """Calculate token usage within time window."""
        
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Clean old entries and sum recent usage
        window = self.time_windows[request_id]
        total = 0
        
        while window and window[0][0] < cutoff_time:
            window.popleft()
        
        for timestamp, tokens in window:
            total += tokens
        
        return total


class IdeationDepthTracker:
    """Tracks ideation depth to prevent excessive chains."""
    
    def __init__(self):
        self.depth_map: Dict[str, int] = {}
        self.chain_roots: Dict[str, str] = {}  # Maps requests to their root
    
    def calculate_depth(self, parent_request_id: Optional[str]) -> int:
        """Calculate the depth of a request in its chain."""
        
        if not parent_request_id:
            return 0
        
        if parent_request_id in self.depth_map:
            return self.depth_map[parent_request_id] + 1
        
        # If not found, assume depth 0 for parent
        return 1
    
    def set_depth(self, request_id: str, parent_id: Optional[str]):
        """Set the depth for a request."""
        
        if not parent_id:
            self.depth_map[request_id] = 0
            self.chain_roots[request_id] = request_id
        else:
            parent_depth = self.depth_map.get(parent_id, 0)
            self.depth_map[request_id] = parent_depth + 1
            
            # Propagate root
            if parent_id in self.chain_roots:
                self.chain_roots[request_id] = self.chain_roots[parent_id]
            else:
                self.chain_roots[request_id] = parent_id
    
    def get_chain_root(self, request_id: str) -> Optional[str]:
        """Get the root of a request's chain."""
        return self.chain_roots.get(request_id)


class CompletionCircuitBreaker:
    """Main circuit breaker combining all safety mechanisms."""
    
    def __init__(self):
        self.request_tracker = RequestTracker()
        self.pattern_detector = ContextPoisoningDetector()
        self.token_tracker = TokenBudgetTracker()
        self.depth_tracker = IdeationDepthTracker()
        
        # Track blocked requests
        self.blocked_requests: Set[str] = set()
        self.block_reasons: Dict[str, Dict[str, Any]] = {}
    
    def check_allowed(self, request: Dict[str, Any]) -> bool:
        """Check if request passes all circuit breaker conditions."""
        
        request_id = request.get('id')
        parent_id = request.get('circuit_breaker_config', {}).get('parent_request_id')
        
        # Check if already blocked
        if request_id in self.blocked_requests:
            logger.warning(f"Request {request_id} already blocked")
            return False
        
        # Run all checks
        checks = [
            self.check_ideation_depth(request),
            self.check_token_budget(request),
            self.check_time_window(request),
            self.check_circular_patterns(request),
            self.check_context_poisoning_risk(request)
        ]
        
        # If any check fails, block the request
        if not all(checks):
            self.blocked_requests.add(request_id)
            logger.warning(f"Request {request_id} blocked: {self.block_reasons.get(request_id)}")
            return False
        
        # Track the request
        content = request.get('prompt', '')
        tokens = request.get('estimated_tokens', estimate_tokens(content))
        
        self.request_tracker.add_request(request_id, parent_id, content, tokens)
        self.depth_tracker.set_depth(request_id, parent_id)
        self.token_tracker.add_tokens(request_id, parent_id, int(tokens))
        
        return True
    
    def check_ideation_depth(self, request: Dict[str, Any]) -> bool:
        """Check ideation depth limit."""
        
        request_id = request.get('id')
        config = request.get('circuit_breaker_config', {})
        parent_id = config.get('parent_request_id')
        max_depth = config.get('max_depth', 5)
        
        current_depth = self.depth_tracker.calculate_depth(parent_id)
        
        if current_depth >= max_depth:
            self.block_reasons[request_id] = {
                'check': 'ideation_depth',
                'current_depth': current_depth,
                'max_depth': max_depth
            }
            return False
        
        return True
    
    def check_token_budget(self, request: Dict[str, Any]) -> bool:
        """Check token budget limit."""
        
        request_id = request.get('id')
        config = request.get('circuit_breaker_config', {})
        parent_id = config.get('parent_request_id')
        token_budget = config.get('token_budget', 50000)
        time_window = config.get('time_window', 3600)
        
        passed, details = self.token_tracker.check_budget(
            request_id, parent_id, token_budget, time_window
        )
        
        if not passed:
            self.block_reasons[request_id] = {
                'check': 'token_budget',
                **details
            }
        
        return passed
    
    def check_time_window(self, request: Dict[str, Any]) -> bool:
        """Check time window constraints."""
        
        # Currently handled by token budget tracker
        # Could add separate time-based limits here
        return True
    
    def check_circular_patterns(self, request: Dict[str, Any]) -> bool:
        """Check for circular reasoning patterns."""
        
        request_id = request.get('id')
        parent_id = request.get('circuit_breaker_config', {}).get('parent_request_id')
        
        if not parent_id:
            return True
        
        # Get the chain
        chain = self.request_tracker.get_completion_chain(parent_id)
        
        if len(chain) >= 6:
            # Simple check: if we've seen similar content recently
            content = request.get('prompt', '')
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            recent_hashes = [r.content_hash for r in chain[-5:]]
            if content_hash in recent_hashes:
                self.block_reasons[request_id] = {
                    'check': 'circular_pattern',
                    'detail': 'Duplicate content detected in recent chain'
                }
                return False
        
        return True
    
    def check_context_poisoning_risk(self, request: Dict[str, Any]) -> bool:
        """Check for context poisoning patterns."""
        
        request_id = request.get('id')
        parent_id = request.get('circuit_breaker_config', {}).get('parent_request_id')
        
        if not parent_id:
            return True
        
        # Get the chain and analyze
        chain = self.request_tracker.get_completion_chain(parent_id)
        
        if len(chain) >= 2:
            analysis = self.pattern_detector.analyze_chain(chain)
            
            if analysis['risk_score'] > 0.7:
                self.block_reasons[request_id] = {
                    'check': 'context_poisoning',
                    'risk_score': analysis['risk_score'],
                    'indicators': analysis['indicators']
                }
                return False
        
        return True
    
    def get_block_reason(self, request: Dict[str, Any]) -> str:
        """Get human-readable block reason."""
        
        request_id = request.get('id')
        reason = self.block_reasons.get(request_id, {})
        
        check_type = reason.get('check', 'unknown')
        
        if check_type == 'ideation_depth':
            return f"Max ideation depth ({reason.get('max_depth')}) exceeded"
        elif check_type == 'token_budget':
            return f"Token budget ({reason.get('budget')}) exceeded"
        elif check_type == 'circular_pattern':
            return "Circular reasoning pattern detected"
        elif check_type == 'context_poisoning':
            return f"Context poisoning risk too high ({reason.get('risk_score', 0):.2f})"
        else:
            return "Request blocked by circuit breaker"
    
    def get_status(self, parent_request_id: Optional[str]) -> Dict[str, Any]:
        """Get current circuit breaker status for a chain."""
        
        if not parent_request_id:
            return {
                'depth': 0,
                'max_depth': 5,
                'tokens_used': 0,
                'token_budget': 50000,
                'time_elapsed': 0,
                'time_window': 3600,
                'risk_score': 0
            }
        
        # Get current metrics
        depth = self.depth_tracker.calculate_depth(parent_request_id)
        tokens_used = self.token_tracker.chain_tokens.get(parent_request_id, 0)
        
        # Get chain for analysis
        chain = self.request_tracker.get_completion_chain(parent_request_id)
        risk_analysis = self.pattern_detector.analyze_chain(chain) if chain else {'risk_score': 0}
        
        # Calculate time elapsed
        time_elapsed = 0
        if chain:
            time_elapsed = int(time.time() - chain[-1].timestamp)
        
        return {
            'depth': depth,
            'max_depth': 5,
            'tokens_used': tokens_used,
            'token_budget': 50000,
            'time_elapsed': time_elapsed,
            'time_window': 3600,
            'risk_score': risk_analysis['risk_score'],
            'chain_length': len(chain),
            'blocked_count': len(self.blocked_requests)
        }


# Module-level singleton instance
circuit_breaker = CompletionCircuitBreaker()


# Public interface
def check_completion_allowed(request: Dict[str, Any]) -> bool:
    """Check if a completion request should be allowed."""
    return circuit_breaker.check_allowed(request)


def get_circuit_breaker_status(parent_request_id: Optional[str] = None) -> Dict[str, Any]:
    """Get current circuit breaker status."""
    return circuit_breaker.get_status(parent_request_id)


def get_block_reason(request: Dict[str, Any]) -> str:
    """Get human-readable reason for why a request was blocked."""
    return circuit_breaker.get_block_reason(request)