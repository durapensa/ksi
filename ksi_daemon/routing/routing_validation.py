#!/usr/bin/env python3
"""
Routing rule validation and conflict detection.

Validates routing rules for:
- Required fields and types
- Pattern syntax
- Priority conflicts
- Circular routing detection
- Rule overlap warnings
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("routing_validation")


class RoutingRuleValidator:
    """Validates routing rules and detects conflicts."""
    
    # Required fields for a routing rule
    REQUIRED_FIELDS = ["source_pattern", "target", "priority"]
    
    # Optional fields with defaults
    OPTIONAL_FIELDS = {
        "condition": None,
        "mapping": None,
        "ttl": None,
        "metadata": None
    }
    
    # Valid priority range
    MIN_PRIORITY = 0
    MAX_PRIORITY = 10000
    
    def __init__(self):
        """Initialize the validator."""
        self.logger = logger
    
    def validate_rule(self, rule: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a single routing rule.
        
        Returns:
            (is_valid, error_message)
        """
        # Ensure rule is a dictionary
        if not isinstance(rule, dict):
            return False, f"Rule must be a dictionary, got {type(rule).__name__}"
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in rule:
                return False, f"Missing required field: {field}"
        
        # Validate source pattern
        valid, error = self._validate_pattern(rule["source_pattern"])
        if not valid:
            return False, f"Invalid source pattern: {error}"
        
        # Validate target
        if not rule["target"] or not isinstance(rule["target"], str):
            return False, "Target must be a non-empty string"
        
        # Validate priority
        priority = rule.get("priority", 100)
        if not isinstance(priority, int):
            return False, "Priority must be an integer"
        if priority < self.MIN_PRIORITY or priority > self.MAX_PRIORITY:
            return False, f"Priority must be between {self.MIN_PRIORITY} and {self.MAX_PRIORITY}"
        
        # Validate TTL if present
        if "ttl" in rule and rule["ttl"] is not None:
            if not isinstance(rule["ttl"], int) or rule["ttl"] <= 0:
                return False, "TTL must be a positive integer (seconds)"
        
        # Validate condition if present
        if "condition" in rule and rule["condition"] is not None:
            valid, error = self._validate_condition(rule["condition"])
            if not valid:
                return False, f"Invalid condition: {error}"
        
        # Validate mapping if present
        if "mapping" in rule and rule["mapping"] is not None:
            if not isinstance(rule["mapping"], dict):
                return False, "Mapping must be a dictionary"
        
        return True, None
    
    def _validate_pattern(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """Validate event pattern syntax."""
        if not pattern:
            return False, "Pattern cannot be empty"
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9:_*]+$', pattern):
            return False, "Pattern can only contain alphanumeric, ':', '_', and '*'"
        
        # Check wildcard usage
        if '*' in pattern and not pattern.endswith('*'):
            return False, "Wildcard (*) can only be used at the end of pattern"
        
        # Check for double colons
        if '::' in pattern:
            return False, "Pattern cannot contain double colons"
        
        return True, None
    
    def _validate_condition(self, condition: str) -> Tuple[bool, Optional[str]]:
        """Validate condition expression."""
        # Basic validation - just check it's a non-empty string
        # More complex validation could parse the expression
        if not isinstance(condition, str) or not condition.strip():
            return False, "Condition must be a non-empty string"
        
        # Check for dangerous operations
        dangerous_patterns = ['exec', 'eval', '__import__', 'compile', 'open']
        for pattern in dangerous_patterns:
            if pattern in condition:
                return False, f"Condition contains forbidden operation: {pattern}"
        
        return True, None
    
    def detect_conflicts(self, new_rule: Dict[str, Any], 
                        existing_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect conflicts between a new rule and existing rules.
        
        Returns list of conflict warnings.
        """
        conflicts = []
        
        # Check for exact pattern matches at same priority
        for existing in existing_rules:
            if existing["rule_id"] == new_rule.get("rule_id"):
                continue  # Skip self
            
            # Exact pattern match
            if (existing["source_pattern"] == new_rule["source_pattern"] and 
                existing["priority"] == new_rule["priority"]):
                conflicts.append({
                    "type": "exact_match",
                    "severity": "high",
                    "message": f"Rule has same pattern and priority as {existing['rule_id']}",
                    "conflicting_rule": existing["rule_id"]
                })
            
            # Pattern overlap with same target (potential redundancy)
            if (self._patterns_overlap(new_rule["source_pattern"], existing["source_pattern"]) and
                existing["target"] == new_rule["target"]):
                conflicts.append({
                    "type": "redundant_routing",
                    "severity": "low",
                    "message": f"Rule overlaps with {existing['rule_id']} and routes to same target",
                    "conflicting_rule": existing["rule_id"]
                })
        
        # Check for circular routing
        circular = self._detect_circular_routing(new_rule, existing_rules)
        if circular:
            conflicts.append({
                "type": "circular_routing",
                "severity": "high",
                "message": f"Rule creates circular routing: {' -> '.join(circular)}",
                "circular_path": circular
            })
        
        return conflicts
    
    def _patterns_overlap(self, pattern1: str, pattern2: str) -> bool:
        """Check if two patterns might match the same events."""
        # Remove wildcards for comparison
        p1_base = pattern1.rstrip('*')
        p2_base = pattern2.rstrip('*')
        
        # If either is a wildcard, check prefix match
        if pattern1.endswith('*') or pattern2.endswith('*'):
            # The shorter base is a prefix of the longer one
            return p1_base.startswith(p2_base) or p2_base.startswith(p1_base)
        
        # Exact match only
        return pattern1 == pattern2
    
    def _detect_circular_routing(self, new_rule: Dict[str, Any],
                                existing_rules: List[Dict[str, Any]]) -> Optional[List[str]]:
        """
        Detect if the new rule creates a circular routing path.
        
        Returns the circular path if found, None otherwise.
        """
        # Build routing graph
        all_rules = existing_rules + [new_rule]
        routing_graph = {}
        
        for rule in all_rules:
            source = rule["source_pattern"]
            target = rule["target"]
            
            if source not in routing_graph:
                routing_graph[source] = []
            routing_graph[source].append(target)
        
        # Check for cycles starting from the new rule's target
        visited = set()
        path = []
        
        def has_cycle(node: str) -> bool:
            if node in path:
                # Found cycle
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            
            if node in visited:
                return None
            
            visited.add(node)
            path.append(node)
            
            # Check all possible targets for this node
            for pattern, targets in routing_graph.items():
                # Check if this node's events would match the pattern
                if self._event_matches_pattern(node, pattern):
                    for target in targets:
                        cycle = has_cycle(target)
                        if cycle:
                            return cycle
            
            path.pop()
            return None
        
        # Start from the new rule's target
        cycle = has_cycle(new_rule["target"])
        return cycle
    
    def _event_matches_pattern(self, event: str, pattern: str) -> bool:
        """Check if an event name would match a pattern."""
        if pattern.endswith('*'):
            # Wildcard pattern
            return event.startswith(pattern[:-1])
        else:
            # Exact match
            return event == pattern
    
    def suggest_improvements(self, rule: Dict[str, Any],
                           existing_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Suggest improvements for a routing rule.
        
        Returns list of suggestions.
        """
        suggestions = []
        
        # Check if pattern is too broad
        if rule["source_pattern"] == "*":
            suggestions.append({
                "type": "overly_broad_pattern",
                "message": "Pattern '*' will match all events. Consider using a more specific pattern.",
                "suggestion": "Use a namespace prefix like 'myservice:*'"
            })
        
        # Check if priority is in common range
        if rule["priority"] < 100 or rule["priority"] > 900:
            suggestions.append({
                "type": "unusual_priority",
                "message": f"Priority {rule['priority']} is outside common range (100-900)",
                "suggestion": "Use priorities 100-900 for normal rules, reserve extremes for special cases"
            })
        
        # Check for missing TTL on temporary rules
        if "temp" in rule.get("metadata", {}) and not rule.get("ttl"):
            suggestions.append({
                "type": "missing_ttl",
                "message": "Temporary rule without TTL will persist indefinitely",
                "suggestion": "Add a TTL for temporary routing rules"
            })
        
        return suggestions


def create_validator() -> RoutingRuleValidator:
    """Create a routing rule validator instance."""
    return RoutingRuleValidator()