#!/usr/bin/env python3
"""
Interaction Validator
=====================

Validates interactions between entities in spatial environments.
Handles cooperation, competition, communication, and complex multi-agent interactions.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of interactions between entities."""
    COMMUNICATE = "communicate"
    COOPERATE = "cooperate"
    COMPETE = "compete"
    TRADE = "trade"
    ATTACK = "attack"
    HELP = "help"
    BLOCK = "block"
    FOLLOW = "follow"
    AVOID = "avoid"
    COLLECT = "collect"
    HUNT_COOPERATIVE = "hunt_cooperative"
    HUNT_SOLO = "hunt_solo"
    PICKUP = "pickup"
    DROP = "drop"


@dataclass
class InteractionRequest:
    """An interaction validation request."""
    actor_id: str
    target_id: str
    interaction_type: InteractionType
    range_limit: float
    position_actor: Tuple[float, float]
    position_target: Tuple[float, float]
    parameters: Dict = None
    capabilities: List[str] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.capabilities is None:
            self.capabilities = []
    
    def distance(self) -> float:
        """Calculate distance between actor and target."""
        dx = self.position_actor[0] - self.position_target[0]
        dy = self.position_actor[1] - self.position_target[1]
        return math.sqrt(dx*dx + dy*dy)


@dataclass
class CooperationRequirements:
    """Requirements for cooperative interactions."""
    min_participants: int
    max_participants: int
    required_capabilities: List[str]
    coordination_radius: float
    success_threshold: float = 0.7


@dataclass
class ValidationResult:
    """Result of interaction validation."""
    valid: bool
    reason: str = ""
    required_participants: List[str] = None
    missing_capabilities: List[str] = None
    suggested_position: Optional[Tuple[float, float]] = None
    cooperation_score: float = 0.0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.required_participants is None:
            self.required_participants = []
        if self.missing_capabilities is None:
            self.missing_capabilities = []
        if self.warnings is None:
            self.warnings = []


class InteractionValidator:
    """Validates interactions between entities."""
    
    def __init__(self):
        self.interaction_rules = {
            InteractionType.COMMUNICATE: {"max_range": 10.0, "capabilities": []},
            InteractionType.COOPERATE: {"max_range": 5.0, "capabilities": ["cooperate"]},
            InteractionType.COMPETE: {"max_range": 3.0, "capabilities": []},
            InteractionType.TRADE: {"max_range": 2.0, "capabilities": ["trade"]},
            InteractionType.ATTACK: {"max_range": 2.0, "capabilities": ["attack"]},
            InteractionType.HELP: {"max_range": 3.0, "capabilities": ["help"]},
            InteractionType.BLOCK: {"max_range": 1.0, "capabilities": []},
            InteractionType.FOLLOW: {"max_range": 10.0, "capabilities": []},
            InteractionType.AVOID: {"max_range": 15.0, "capabilities": []},
            InteractionType.COLLECT: {"max_range": 2.0, "capabilities": []},
            InteractionType.HUNT_COOPERATIVE: {"max_range": 5.0, "capabilities": ["hunt"]},
            InteractionType.HUNT_SOLO: {"max_range": 3.0, "capabilities": ["hunt"]},
            InteractionType.PICKUP: {"max_range": 1.0, "capabilities": []},
            InteractionType.DROP: {"max_range": 0.0, "capabilities": []}
        }
        
        self.cooperation_requirements = {
            "stag_hunt": CooperationRequirements(
                min_participants=3,
                max_participants=5,
                required_capabilities=["hunt", "coordinate"],
                coordination_radius=5.0,
                success_threshold=0.8
            ),
            "collaborative_cooking": CooperationRequirements(
                min_participants=2,
                max_participants=4,
                required_capabilities=["cook"],
                coordination_radius=3.0,
                success_threshold=0.6
            )
        }
        
        self.interaction_history: List[InteractionRequest] = []
        self.entity_relationships: Dict[Tuple[str, str], float] = {}  # Trust scores
        
    def validate_interaction(self, request: InteractionRequest,
                            context: Optional[Dict] = None) -> ValidationResult:
        """Validate an interaction request."""
        
        # Check range
        if not self._check_range(request):
            distance = request.distance()
            max_range = self.interaction_rules[request.interaction_type]["max_range"]
            
            # Suggest closer position
            suggested = self._suggest_interaction_position(request)
            
            return ValidationResult(
                valid=False,
                reason=f"Distance {distance:.1f} exceeds max range {max_range}",
                suggested_position=suggested
            )
        
        # Check capabilities
        missing = self._check_capabilities(request)
        if missing:
            return ValidationResult(
                valid=False,
                reason=f"Missing required capabilities",
                missing_capabilities=missing
            )
        
        # Check line of sight for certain interactions
        if request.interaction_type in [InteractionType.ATTACK, InteractionType.COMMUNICATE]:
            if not self._check_line_of_sight(request, context):
                return ValidationResult(
                    valid=False,
                    reason="No line of sight to target"
                )
        
        # Check cooperation requirements
        if request.interaction_type == InteractionType.HUNT_COOPERATIVE:
            coop_result = self._check_cooperation_requirements(request, context)
            if not coop_result.valid:
                return coop_result
        
        # Check consent for certain interactions
        if request.interaction_type in [InteractionType.TRADE, InteractionType.COOPERATE]:
            if not self._check_consent(request, context):
                return ValidationResult(
                    valid=False,
                    reason="Target does not consent to interaction"
                )
        
        # Check game rules
        warnings = self._check_game_rules(request, context)
        
        # Calculate cooperation score
        coop_score = self._calculate_cooperation_score(request, context)
        
        # Record interaction
        self.interaction_history.append(request)
        self._update_relationship(request)
        
        return ValidationResult(
            valid=True,
            cooperation_score=coop_score,
            warnings=warnings
        )
    
    def _check_range(self, request: InteractionRequest) -> bool:
        """Check if entities are within interaction range."""
        distance = request.distance()
        max_range = self.interaction_rules[request.interaction_type]["max_range"]
        
        # Allow custom range if specified
        if request.range_limit > 0:
            max_range = min(max_range, request.range_limit)
        
        return distance <= max_range
    
    def _check_capabilities(self, request: InteractionRequest) -> List[str]:
        """Check if actor has required capabilities."""
        required = self.interaction_rules[request.interaction_type]["capabilities"]
        missing = [cap for cap in required if cap not in request.capabilities]
        return missing
    
    def _check_line_of_sight(self, request: InteractionRequest,
                            context: Optional[Dict]) -> bool:
        """Check if there's a clear line of sight."""
        if not context or "obstacles" not in context:
            return True
        
        # Simple line of sight check
        x1, y1 = request.position_actor
        x2, y2 = request.position_target
        
        # Check if any obstacle blocks the line
        for obstacle in context["obstacles"]:
            ox, oy = obstacle["x"], obstacle["y"]
            
            # Check if obstacle is on the line between actor and target
            # Using cross product to check if point is on line
            cross = (y2 - y1) * (ox - x1) - (x2 - x1) * (oy - y1)
            
            if abs(cross) < 0.5:  # Close to line
                # Check if between actor and target
                if min(x1, x2) <= ox <= max(x1, x2) and min(y1, y2) <= oy <= max(y1, y2):
                    return False
        
        return True
    
    def _check_cooperation_requirements(self, request: InteractionRequest,
                                       context: Optional[Dict]) -> ValidationResult:
        """Check requirements for cooperative interactions."""
        
        # Get cooperation type from parameters
        coop_type = request.parameters.get("cooperation_type", "stag_hunt")
        
        if coop_type not in self.cooperation_requirements:
            return ValidationResult(valid=True)  # No specific requirements
        
        requirements = self.cooperation_requirements[coop_type]
        
        # Check nearby participants
        if context and "nearby_entities" in context:
            nearby = context["nearby_entities"]
            
            # Filter entities within coordination radius
            participants = []
            for entity in nearby:
                if entity["entity_type"] == "agent":
                    ex, ey = entity["position"]["x"], entity["position"]["y"]
                    distance = math.sqrt(
                        (ex - request.position_actor[0])**2 + 
                        (ey - request.position_actor[1])**2
                    )
                    if distance <= requirements.coordination_radius:
                        participants.append(entity["entity_id"])
            
            # Check participant count
            if len(participants) < requirements.min_participants - 1:  # -1 for actor
                return ValidationResult(
                    valid=False,
                    reason=f"Need at least {requirements.min_participants} participants",
                    required_participants=participants
                )
            
            if len(participants) > requirements.max_participants - 1:
                return ValidationResult(
                    valid=False,
                    reason=f"Too many participants (max {requirements.max_participants})",
                    warnings=[f"Found {len(participants)+1} participants"]
                )
        
        return ValidationResult(valid=True, cooperation_score=0.8)
    
    def _check_consent(self, request: InteractionRequest,
                      context: Optional[Dict]) -> bool:
        """Check if target consents to interaction."""
        
        # Check relationship history
        relationship_key = (request.actor_id, request.target_id)
        trust_score = self.entity_relationships.get(relationship_key, 0.5)
        
        # Check recent interactions
        recent = self._get_recent_interactions(request.actor_id, request.target_id)
        
        # Calculate consent probability
        if recent:
            positive = sum(1 for r in recent if r.interaction_type in 
                         [InteractionType.COOPERATE, InteractionType.HELP, InteractionType.TRADE])
            negative = sum(1 for r in recent if r.interaction_type in 
                         [InteractionType.ATTACK, InteractionType.BLOCK])
            
            consent_prob = (positive + 1) / (positive + negative + 2)
        else:
            consent_prob = 0.7  # Default consent probability
        
        # Modify by trust score
        consent_prob = consent_prob * 0.5 + trust_score * 0.5
        
        # For now, return probabilistic consent
        import random
        return random.random() < consent_prob
    
    def _check_game_rules(self, request: InteractionRequest,
                         context: Optional[Dict]) -> List[str]:
        """Check for game rule violations or warnings."""
        warnings = []
        
        # Check if interaction affects victory conditions
        if context and "victory_conditions" in context:
            for condition in context["victory_conditions"]:
                if condition["type"] == "no_combat" and request.interaction_type == InteractionType.ATTACK:
                    warnings.append("Combat may violate victory conditions")
                elif condition["type"] == "cooperation" and request.interaction_type == InteractionType.COMPETE:
                    warnings.append("Competition may reduce cooperation score")
        
        # Check resource limits
        if request.interaction_type == InteractionType.COLLECT:
            if context and "resource_limits" in context:
                resource_type = request.parameters.get("resource_type")
                if resource_type in context["resource_limits"]:
                    limit = context["resource_limits"][resource_type]
                    warnings.append(f"Resource collection approaching limit ({limit})")
        
        return warnings
    
    def _calculate_cooperation_score(self, request: InteractionRequest,
                                    context: Optional[Dict]) -> float:
        """Calculate cooperation score for the interaction."""
        
        # Base scores for interaction types
        base_scores = {
            InteractionType.COOPERATE: 1.0,
            InteractionType.HELP: 0.9,
            InteractionType.TRADE: 0.7,
            InteractionType.COMMUNICATE: 0.5,
            InteractionType.FOLLOW: 0.4,
            InteractionType.COMPETE: -0.3,
            InteractionType.BLOCK: -0.5,
            InteractionType.ATTACK: -1.0,
            InteractionType.AVOID: -0.2
        }
        
        score = base_scores.get(request.interaction_type, 0.0)
        
        # Modify by relationship
        relationship_key = (request.actor_id, request.target_id)
        trust = self.entity_relationships.get(relationship_key, 0.5)
        
        # Positive interactions with high trust get bonus
        if score > 0 and trust > 0.7:
            score *= 1.2
        # Negative interactions with low trust get penalty
        elif score < 0 and trust < 0.3:
            score *= 1.2
        
        return max(-1.0, min(1.0, score))  # Clamp to [-1, 1]
    
    def _suggest_interaction_position(self, request: InteractionRequest) -> Tuple[float, float]:
        """Suggest a position where interaction would be valid."""
        
        max_range = self.interaction_rules[request.interaction_type]["max_range"]
        
        # Calculate direction vector
        dx = request.position_target[0] - request.position_actor[0]
        dy = request.position_target[1] - request.position_actor[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance == 0:
            return request.position_actor
        
        # Normalize and scale to valid range
        scale = (max_range * 0.9) / distance  # 90% of max range
        
        suggested_x = request.position_target[0] - dx * scale
        suggested_y = request.position_target[1] - dy * scale
        
        return (suggested_x, suggested_y)
    
    def _get_recent_interactions(self, actor: str, target: str,
                                limit: int = 10) -> List[InteractionRequest]:
        """Get recent interaction history between two entities."""
        recent = []
        for interaction in reversed(self.interaction_history):
            if ((interaction.actor_id == actor and interaction.target_id == target) or
                (interaction.actor_id == target and interaction.target_id == actor)):
                recent.append(interaction)
                if len(recent) >= limit:
                    break
        return recent
    
    def _update_relationship(self, request: InteractionRequest):
        """Update relationship score based on interaction."""
        
        # Update both directions
        key1 = (request.actor_id, request.target_id)
        key2 = (request.target_id, request.actor_id)
        
        # Get current trust scores
        trust1 = self.entity_relationships.get(key1, 0.5)
        trust2 = self.entity_relationships.get(key2, 0.5)
        
        # Calculate trust change
        coop_score = self._calculate_cooperation_score(request, None)
        trust_change = coop_score * 0.1  # 10% of cooperation score
        
        # Update trust scores
        self.entity_relationships[key1] = max(0, min(1, trust1 + trust_change))
        self.entity_relationships[key2] = max(0, min(1, trust2 + trust_change * 0.5))  # Asymmetric
    
    def get_relationship_score(self, entity1: str, entity2: str) -> float:
        """Get relationship/trust score between two entities."""
        return self.entity_relationships.get((entity1, entity2), 0.5)
    
    def validate_batch(self, requests: List[InteractionRequest],
                      context: Optional[Dict] = None) -> List[ValidationResult]:
        """Validate multiple interaction requests."""
        results = []
        for request in requests:
            results.append(self.validate_interaction(request, context))
        return results


# Export classes
__all__ = ['InteractionValidator', 'InteractionRequest', 'ValidationResult',
           'InteractionType', 'CooperationRequirements']