# Validation Agent Approach for KSI General Events

## Overview

This document describes how KSI uses independent validation agents (or DSPy programs) to validate spatial movements, resource transfers, and other interactions. This approach maintains system elegance while providing flexible, intelligent validation.

## Core Principle: Validation as a Service

Rather than hardcoding validation rules into each service, we treat validation as an independent concern handled by specialized agents or DSPy programs. This provides:

1. **Flexibility** - Validation logic can be updated without changing core services
2. **Intelligence** - LLM agents can handle complex, context-aware validation
3. **Reusability** - Same validators can work across different scenarios
4. **Auditability** - All validation decisions are logged and explainable

## Architecture

### Validation Flow

```
1. Action Request → 2. Validation Check → 3. Validation Agent → 4. Decision → 5. Action Execution
```

Example for spatial movement:
```python
# 1. Movement request received
"spatial:move" event with validate_path=true

# 2. Service checks if validation needed
if data.get("validate_path"):
    
    # 3. Request validation from agent
    await emit("validation:request", {
        "validator_id": "movement_validator",
        "validation_type": "spatial_movement",
        "context": movement_details
    })
    
    # 4. Agent makes decision
    # Agent analyzes path, checks rules, returns decision
    
    # 5. Execute or reject based on decision
    if validation_result["valid"]:
        execute_movement()
    else:
        return blocked_response()
```

## Validation Agent Types

### 1. Movement Validator Agent

```yaml
# components/validators/movement_validator.md
---
component_type: persona
name: movement_validator
version: 1.0.0
capabilities: [validation, spatial_reasoning]
---

You are a movement validation specialist for spatial environments.

When validating movement requests, check:
1. **Path Validity**: Is there a clear path from A to B?
2. **Obstacle Detection**: Are there solid objects blocking the way?
3. **Movement Capabilities**: Can this entity type make this movement?
4. **Speed Limits**: Is the distance reasonable for the movement type?
5. **Terrain Restrictions**: Is the terrain passable?

Respond with JSON:
{
  "valid": true/false,
  "reason": "explanation if invalid",
  "suggested_path": [...] // optional alternative
}
```

### 2. Resource Transfer Validator

```yaml
# components/validators/resource_validator.md
---
component_type: persona
name: resource_transfer_validator
version: 1.0.0
capabilities: [validation, economic_reasoning]
---

You validate resource transfers between entities.

Check:
1. **Ownership**: Does sender own the resources?
2. **Consent**: Has consent been granted for this transfer type?
3. **Limits**: Would this exceed any resource limits?
4. **Fairness**: Is this transfer exploitative?
5. **Conservation**: Are conservation laws maintained?

Consider our fairness principles:
- Prevent monopolization
- Block exploitative transfers
- Ensure consent for significant transfers
```

### 3. Interaction Validator

```yaml
# components/validators/interaction_validator.md
---
component_type: persona
name: interaction_validator
version: 1.0.0
capabilities: [validation, game_theory]
---

You validate interactions between entities in game environments.

Evaluate:
1. **Range**: Are entities close enough to interact?
2. **Capabilities**: Can actor perform this interaction type?
3. **Consent**: Does target consent to interaction?
4. **Game Rules**: Does this follow scenario rules?
5. **Fairness**: Does this create unfair advantage?
```

## DSPy Implementation Alternative

For scenarios requiring deterministic validation or high performance, we can use DSPy programs:

```python
# ksi_daemon/validation/dspy_validators.py

import dspy
from typing import Dict, Tuple

class MovementValidator(dspy.Module):
    """DSPy-based movement validation."""
    
    def __init__(self):
        super().__init__()
        
        # Define validation signature
        self.validate = dspy.ChainOfThought(
            "entity_type, current_position, target_position, movement_type, obstacles -> valid, reason"
        )
        
        # Define path finding signature
        self.find_path = dspy.Predict(
            "start, end, obstacles -> path"
        )
    
    def forward(self, entity_type: str, current_pos: Dict, 
                target_pos: Dict, movement_type: str,
                obstacles: List[Dict]) -> Tuple[bool, str]:
        """Validate movement request."""
        
        # Check basic constraints
        distance = calculate_distance(current_pos, target_pos)
        
        # Use DSPy for complex validation
        validation = self.validate(
            entity_type=entity_type,
            current_position=f"({current_pos['x']}, {current_pos['y']})",
            target_position=f"({target_pos['x']}, {target_pos['y']})",
            movement_type=movement_type,
            obstacles=format_obstacles(obstacles)
        )
        
        return validation.valid, validation.reason

class ResourceTransferValidator(dspy.Module):
    """DSPy-based resource transfer validation."""
    
    def __init__(self):
        super().__init__()
        
        self.check_consent = dspy.ChainOfThought(
            "sender, receiver, resource_type, amount, transfer_type, history -> consented, reason"
        )
        
        self.check_fairness = dspy.Predict(
            "current_distribution, proposed_transfer -> fair, gini_impact"
        )
    
    def forward(self, sender: str, receiver: str, 
                resource_type: str, amount: float,
                transfer_type: str) -> Dict:
        """Validate resource transfer."""
        
        # Check consent
        consent = self.check_consent(
            sender=sender,
            receiver=receiver,
            resource_type=resource_type,
            amount=amount,
            transfer_type=transfer_type,
            history=get_interaction_history(sender, receiver)
        )
        
        if not consent.consented:
            return {"valid": False, "reason": consent.reason}
        
        # Check fairness impact
        fairness = self.check_fairness(
            current_distribution=get_resource_distribution(),
            proposed_transfer=f"{sender} -> {receiver}: {amount} {resource_type}"
        )
        
        if not fairness.fair:
            return {
                "valid": False,
                "reason": f"Unfair transfer (Gini impact: {fairness.gini_impact})"
            }
        
        return {"valid": True}
```

## Permission Integration

Validation agents respect KSI's capability and permission system:

```python
# Check if validator has necessary permissions
async def can_validate(validator_id: str, validation_type: str) -> bool:
    """Check if validator has permission to validate."""
    
    result = await emit_event("permission:check", {
        "actor": validator_id,
        "action": f"validation:{validation_type}",
        "target": "system"
    })
    
    return result.get("allowed", False)

# Grant validation capability to agent
await emit_event("capability:grant", {
    "agent_id": "movement_validator",
    "capabilities": ["validation", "spatial_query", "state_read"]
})
```

## Consent Mechanism Integration

For interactions requiring consent, validators check the permission system:

```python
class ConsentValidator:
    """Validates consent for interactions."""
    
    async def check_consent(self, actor: str, target: str, 
                           action: str, context: Dict) -> Dict:
        """Check if target consents to action."""
        
        # Query permission system
        permission_result = await self.emit_event("permission:check", {
            "actor": actor,
            "target": target,
            "action": action,
            "context": context
        })
        
        if not permission_result["allowed"]:
            # Try negotiation if supported
            if "negotiation" in context.get("options", []):
                negotiation_result = await self.negotiate_consent(
                    actor, target, action, context
                )
                return negotiation_result
            
            return {
                "consented": False,
                "reason": permission_result.get("reason", "Permission denied")
            }
        
        return {"consented": True}
    
    async def negotiate_consent(self, actor: str, target: str,
                               action: str, context: Dict) -> Dict:
        """Negotiate consent through agent interaction."""
        
        # Send negotiation request to target agent
        await self.emit_event("completion:async", {
            "agent_id": target,
            "prompt": f"""
            {actor} requests permission to {action}.
            Context: {context}
            
            Will you consent? You may negotiate terms.
            Respond with JSON: {{"consent": bool, "terms": [...] or null}}
            """
        })
        
        # Process negotiation response
        # ...
```

## Validation Caching and Optimization

For performance, validation decisions can be cached:

```python
class ValidationCache:
    """Cache validation decisions for performance."""
    
    def __init__(self, ttl_seconds: int = 60):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get_cached_decision(self, validation_key: str) -> Optional[Dict]:
        """Get cached validation decision."""
        if validation_key in self.cache:
            decision, timestamp = self.cache[validation_key]
            if time.time() - timestamp < self.ttl:
                return decision
        return None
    
    def cache_decision(self, validation_key: str, decision: Dict):
        """Cache validation decision."""
        self.cache[validation_key] = (decision, time.time())
```

## Batch Validation

For efficiency, validators can handle batch requests:

```python
# Batch validation request
await emit_event("validation:batch", {
    "validator_id": "movement_validator",
    "requests": [
        {"entity": "agent_1", "from": pos1, "to": pos2},
        {"entity": "agent_2", "from": pos3, "to": pos4},
        # ... more requests
    ]
})

# Validator processes batch efficiently
class BatchValidator:
    async def validate_batch(self, requests: List[Dict]) -> List[Dict]:
        """Validate multiple requests efficiently."""
        
        # Group similar requests
        grouped = self.group_by_type(requests)
        
        # Process groups in parallel
        results = await asyncio.gather(*[
            self.validate_group(group) 
            for group in grouped.values()
        ])
        
        return flatten(results)
```

## Validation Events

### Request Validation

```python
"validation:request": {
    "validator_id": str,  # Which validator to use
    "validation_type": str,  # Type of validation
    "priority": str,  # urgent|normal|low
    "context": dict,  # What to validate
    "timeout_ms": int  # Max wait time
}
```

### Validation Response

```python
"validation:response": {
    "request_id": str,
    "valid": bool,
    "reason": str,  # Explanation if invalid
    "suggestions": list,  # Alternative actions
    "confidence": float,  # Validator confidence
    "validator_id": str
}
```

## Configuration

Validators can be configured per environment:

```yaml
# var/lib/validation/config.yaml
validators:
  movement:
    type: agent  # or dspy
    agent_id: movement_validator_001
    cache_ttl: 60
    batch_size: 10
    
  resource:
    type: dspy
    module: ResourceTransferValidator
    cache_ttl: 30
    
  interaction:
    type: agent
    agent_id: interaction_validator_001
    require_explanation: true

default_timeouts:
  movement: 100  # ms
  resource: 200
  interaction: 150

fairness_thresholds:
  max_gini_increase: 0.1
  min_consent_ratio: 0.7
  max_monopoly_share: 0.4
```

## Benefits of This Approach

### 1. Separation of Concerns
- Core services handle mechanics
- Validators handle rules and fairness
- Clean, maintainable architecture

### 2. Flexibility
- Swap validators without changing services
- A/B test different validation strategies
- Gradually improve validation logic

### 3. Explainability
- Validators provide reasons for decisions
- Audit trail of all validations
- Can query validator for explanation

### 4. Performance
- Async validation doesn't block operations
- Caching reduces redundant checks
- Batch processing for efficiency

### 5. Fairness Integration
- Validators enforce fairness principles
- Prevent exploitation naturally
- Consent checking built-in

## Example: Movement Validation in Practice

```python
# Player tries to move through wall
await emit_event("spatial:move", {
    "entity_id": "player_1",
    "to": {"x": 50, "y": 50},
    "movement_type": "walk",
    "validate_path": True,
    "validation_agent": "movement_validator_001"
})

# Validator checks:
# 1. Is there a wall between current position and target?
# 2. Can walking movement type pass through walls?
# 3. Is distance reasonable for walking?

# Validator responds:
{
    "valid": False,
    "reason": "Solid wall blocks path at (45, 50)",
    "suggestions": [
        {"action": "move", "to": {"x": 45, "y": 49}, "then": "move_around"},
        {"action": "use_ability", "ability": "phase_through_walls"}
    ]
}

# Service returns:
{
    "status": "blocked",
    "reason": "Solid wall blocks path at (45, 50)",
    "actual_position": {"x": 40, "y": 50}
}
```

## Conclusion

Using independent validation agents provides a flexible, intelligent, and maintainable approach to validation in KSI. This architecture:

1. **Keeps services simple** - They don't need complex validation logic
2. **Enables intelligence** - LLM agents can handle nuanced decisions
3. **Maintains fairness** - Validators enforce our fairness principles
4. **Provides flexibility** - Easy to update or swap validators
5. **Ensures explainability** - All decisions have explanations

The combination of agent-based and DSPy validation gives us the best of both worlds: intelligence when needed, performance when required.

---

*Document Version: 1.0*
*Created: 2025-08-28*
*Status: Implementation Ready*